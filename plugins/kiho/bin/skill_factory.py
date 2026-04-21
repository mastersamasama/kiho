#!/usr/bin/env python3
"""
skill_factory.py — top-level orchestrator for kiho skill generation pipeline.

Chains the 10-step SOP for each skill in a batch and emits a per-batch report
(_meta/batch-report-<id>.md) with green / yellow / red verdicts so the CEO
makes a single bulk decision per batch.

Phase 1 wires steps 1-3, 8, 10 (deterministic Python only).
Phase 2 wires steps 4-7, 9 via the **bundle-emit-or-merge** pattern: each step
either (a) parses a previously written subagent response file passed via
`--<step>-output <path>` and merges it into the verdict, or (b) writes a
request bundle to `_meta-runtime/<step>-requests/<step>-request-<id>.json`
and returns `status: yellow` with `next_step: invoke <subagent> then re-enter`
instructions. Python cannot spawn LLM subagents — the caller (CEO via Task
tool) invokes the subagent and re-runs the factory with the response path.
Deferred steps that have not been merged are loud yellow, never silent green.

Modes:
    --batch <spec.md>    — process a YAML batch spec (multi-skill)
    --regen <skill_path> — single-skill regen via the factory pipeline
    --dry-run            — verdict + tree-diff preview, no file writes
    --phase 1 | full     — limit to Phase 1 deterministic steps (default 1)

Exit codes (0/1/2/3 per v5.15.2 Pattern 9):
    0 — all skills in batch verdict green
    1 — at least one skill verdict yellow or red (CEO must triage)
    2 — usage error (missing args, unreadable batch spec)
    3 — internal error (orchestrator crash)

Usage:
    skill_factory.py --regen skills/core/harness/org-sync/SKILL.md
    skill_factory.py --batch _meta/batch-spec-2026-04.md --dry-run
    skill_factory.py --regen skills/core/hr/recruit/SKILL.md --phase 1

Grounding: v5.17 research findings + Backstage Software Templates ordered-step
pattern + Cognition Labs single-checkpoint reduction.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = PLUGIN_ROOT / "skills"
META_DIR = PLUGIN_ROOT / "_meta-runtime"
FACTORY_VERDICTS_JSONL = META_DIR / "factory-verdicts.jsonl"

DRY_RUN_SCRIPT = SKILLS_ROOT / "_meta" / "skill-spec" / "scripts" / "dry_run.py"
GRAPH_SCAN_SCRIPT = SKILLS_ROOT / "_meta" / "skill-structural-gate" / "scripts" / "graph_scan.py"
PARITY_DIFF_SCRIPT = SKILLS_ROOT / "_meta" / "skill-structural-gate" / "scripts" / "parity_diff.py"
EXTRACT_SIGNALS_SCRIPT = SKILLS_ROOT / "_meta" / "skill-spec" / "scripts" / "extract_signals.py"
PROPOSE_SPEC_SCRIPT = SKILLS_ROOT / "_meta" / "skill-spec" / "scripts" / "propose_spec.py"
OBSERVE_SIBLINGS_SCRIPT = SKILLS_ROOT / "_meta" / "skill-spec" / "scripts" / "observe_siblings.py"

ANCHOR_PATHS = ["CLAUDE.md", "README.md"]


def run_subprocess(cmd: list[str], timeout: int = 60, stdin: str | None = None) -> tuple[int, dict[str, Any] | None, str]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                                input=stdin)
        try:
            payload = json.loads(result.stdout) if result.stdout.strip() else None
        except json.JSONDecodeError:
            payload = None
        return result.returncode, payload, result.stderr
    except (subprocess.TimeoutExpired, OSError) as exc:
        return 99, None, str(exc)


def step_1_spec(target: Path) -> dict[str, Any]:
    """Phase 1 — derive a minimal skill_spec from existing SKILL.md frontmatter."""
    text = target.read_text(encoding="utf-8")
    fm_match = re.match(r"^---\n(.+?)\n---\n", text, re.S)
    if not fm_match:
        return {"step": 1, "name": "skill-spec", "status": "red", "reason": "no frontmatter"}

    fm = fm_match.group(1)
    name_match = re.search(r"^name:\s*(\S+)", fm, re.M)
    cap_match = re.search(r"^\s+capability:\s*(\S+)", fm, re.M)
    tags_match = re.search(r"^\s+topic_tags:\s*\[(.+?)\]", fm, re.M)

    if not name_match:
        return {"step": 1, "name": "skill-spec", "status": "red", "reason": "no name in frontmatter"}

    return {
        "step": 1,
        "name": "skill-spec",
        "status": "green",
        "evidence": {
            "name": name_match.group(1),
            "capability": cap_match.group(1) if cap_match else None,
            "topic_tags": [t.strip().strip("'\"") for t in tags_match.group(1).split(",")] if tags_match else [],
        },
    }


def step_2_graph(target: Path) -> dict[str, Any]:
    if not GRAPH_SCAN_SCRIPT.exists():
        return {"step": 2, "name": "skill-graph", "status": "red", "reason": "graph_scan.py not found"}
    code, payload, stderr = run_subprocess([
        sys.executable, str(GRAPH_SCAN_SCRIPT),
        "--target", str(target), "--mode", "pre-regen",
    ])
    if payload is None:
        return {"step": 2, "name": "skill-graph", "status": "red", "reason": f"graph_scan crash: {stderr[:120]}"}
    if payload.get("status") in ("ok", "ok_with_warnings"):
        return {"step": 2, "name": "skill-graph", "status": "green", "evidence": payload}
    return {"step": 2, "name": "skill-graph", "status": "red", "reason": payload.get("status"), "evidence": payload}


def step_3_parity(target: Path) -> dict[str, Any]:
    if not PARITY_DIFF_SCRIPT.exists():
        return {"step": 3, "name": "skill-parity", "status": "red", "reason": "parity_diff.py not found"}
    code, payload, stderr = run_subprocess([
        sys.executable, str(PARITY_DIFF_SCRIPT),
        "--target", str(target), "--mode", "pre-regen",
    ])
    if payload is None:
        return {"step": 3, "name": "skill-parity", "status": "red", "reason": f"parity_diff crash: {stderr[:120]}"}
    if payload.get("status") in ("ok", "ok_with_exception"):
        return {"step": 3, "name": "skill-parity", "status": "green", "evidence": payload}
    return {"step": 3, "name": "skill-parity", "status": "red", "reason": payload.get("status"), "evidence": payload}


def step_8_citation_grep(target: Path) -> dict[str, Any]:
    """Verbatim check: every blockquote MUST be a substring of its cited source.
    Phase 1 is offline-only — checks that every blockquote pairs with at least one
    URL in the same Grounding bullet (cannot fetch source content without network).
    Online verification is Phase 2.
    """
    text = target.read_text(encoding="utf-8")
    grounding_match = re.search(r"^##\s+Grounding\b(.+?)(?=^##\s|\Z)", text, re.M | re.S)
    if not grounding_match:
        return {"step": 8, "name": "citation-grep", "status": "yellow",
                "reason": "no Grounding section (skill may not require citations)"}

    grounding = grounding_match.group(1)
    blockquote_count = len(re.findall(r"^[ \t]*>\s+\*\*", grounding, re.M))
    url_count = len(re.findall(r"https?://\S+", grounding))

    if blockquote_count == 0:
        return {"step": 8, "name": "citation-grep", "status": "yellow",
                "reason": "Grounding present but no blockquote citations"}
    if url_count < blockquote_count - 1:
        return {"step": 8, "name": "citation-grep", "status": "yellow",
                "reason": f"{blockquote_count} blockquotes but only {url_count} URLs — pair check fails"}
    return {"step": 8, "name": "citation-grep", "status": "green",
            "evidence": {"blockquotes": blockquote_count, "urls": url_count, "online_verify": "deferred to Phase 2"}}


def step_10_stale_path(target: Path) -> dict[str, Any]:
    """Re-run skill-graph's stale-path scan as a defense-in-depth check."""
    if not GRAPH_SCAN_SCRIPT.exists():
        return {"step": 10, "name": "stale-path-scan", "status": "yellow", "reason": "graph_scan.py not found"}
    code, payload, stderr = run_subprocess([
        sys.executable, str(GRAPH_SCAN_SCRIPT),
        "--target", str(target), "--mode", "pre-regen",
    ])
    if payload is None:
        return {"step": 10, "name": "stale-path-scan", "status": "yellow",
                "reason": f"graph_scan crash: {stderr[:120]}"}
    stale = payload.get("stale_path_findings", [])
    if not stale:
        return {"step": 10, "name": "stale-path-scan", "status": "green",
                "evidence": {"stale_count": 0}}
    return {"step": 10, "name": "stale-path-scan", "status": "red",
            "reason": f"{len(stale)} stale path reference(s)",
            "evidence": stale}


def step_deferred(step_num: int, name: str,
                  reason: str = "Phase 2 step deferred — caller did not supply --<step>-output and did not request bundle emit") -> dict[str, Any]:
    """Loud-yellow placeholder. Replaces the v5.17 silent-green step_stub.

    Used when a Phase 2 step is genuinely skipped (Phase 1 mode, or the caller
    explicitly wants to no-op). The verdict is YELLOW so a forgotten subagent
    invocation cannot ship as green.
    """
    return {"step": step_num, "name": name, "status": "yellow", "reason": reason}


def emit_bundle_or_merge(
    step_num: int,
    step_name: str,
    subagent_type: str,
    target: Path,
    prior_results: list[dict[str, Any]],
    output_path: Path | None,
    intent: str | None = None,
) -> dict[str, Any]:
    """Phase 2 unified helper: parse a supplied response, or emit a request bundle.

    Mirrors step_0_architect's contract. Python has no LLM-subagent invocation
    primitive; the caller (CEO via Task tool) reads `evidence.bundle_path`,
    spawns the named subagent on it, and re-enters this script with
    `--<step_name>-output <expected_output_path>`. The response file is a JSON
    document with at least:

        {
          "verdict": "green" | "yellow" | "red",
          "summary": "<one-line human-readable>",
          "<step-specific evidence keys>": ...
        }

    Verdicts roll up into the batch report exactly like deterministic-step
    verdicts. A red response from any Phase 2 step blocks the skill.
    """
    # Path A: caller already invoked subagent and supplied response path
    if output_path is not None and output_path.is_file():
        try:
            response = json.loads(output_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            return {"step": step_num, "name": step_name, "status": "red",
                    "reason": f"--{step_name}-output parse failed: {exc}"}
        verdict = response.get("verdict")
        if verdict not in ("green", "yellow", "red"):
            return {"step": step_num, "name": step_name, "status": "red",
                    "reason": f"response missing valid 'verdict'; got {verdict!r}"}
        evidence: dict[str, Any] = {
            "merged_from": str(output_path).replace("\\", "/"),
            "summary": response.get("summary", ""),
        }
        for k, v in response.items():
            if k not in ("verdict", "summary"):
                evidence[k] = v
        return {"step": step_num, "name": step_name, "status": verdict,
                "evidence": evidence}

    # Path B: no response yet — write bundle, return loud-yellow with instructions
    request_id = str(uuid.uuid4())[:8]
    bundle = {
        "step": step_num,
        "step_name": step_name,
        "subagent_type": subagent_type,
        "target": str(target.relative_to(PLUGIN_ROOT)).replace("\\", "/"),
        "intent": intent,
        "prior_results": [
            {
                "step": r.get("step"),
                "name": r.get("name"),
                "status": r.get("status"),
                "reason": r.get("reason"),
                "evidence_keys": list(r.get("evidence", {}).keys())
                                 if isinstance(r.get("evidence"), dict) else None,
            }
            for r in prior_results
        ],
        "request_id": request_id,
    }
    bundle_dir = META_DIR / f"{step_name}-requests"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = bundle_dir / f"{step_name}-request-{request_id}.json"
    bundle_path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    bundle_rel = str(bundle_path.relative_to(PLUGIN_ROOT)).replace("\\", "/")
    expected_output_rel = f"_meta-runtime/{step_name}-requests/{step_name}-response-{request_id}.json"

    target_rel = str(target.relative_to(PLUGIN_ROOT)).replace("\\", "/")
    cli_flag = f"--{step_name}-output"
    return {
        "step": step_num,
        "name": step_name,
        "status": "yellow",
        "reason": f"Phase 2 deferred — invoke {subagent_type} subagent on {bundle_rel}, then re-enter with {cli_flag} <response-path>",
        "evidence": {
            "bundle_path": bundle_rel,
            "expected_output_path": expected_output_rel,
            "invocation_instructions": {
                "subagent_type": subagent_type,
                "input_path": bundle_rel,
                "expected_output_path": expected_output_rel,
                "after_completion": (
                    f"bin/skill_factory.py --regen {target_rel} --phase full "
                    f"{cli_flag} {expected_output_rel}"
                ),
            },
        },
    }


# SOP-step → subagent mapping (v5.21+ remediation).
# The 10-step SOP names describe phases, not skill names. Each Phase 2 step is
# dispatched to a concrete subagent that already exists under skills/_meta/
# (or a freshly-authored one). Keep CLI flag and bundle-dir names tied to the
# SOP step name (stable contract); change only the subagent_type the CEO
# invokes via Task tool.
#
#   step | SOP name        | subagent_type invoked          | rationale
#   -----+-----------------+--------------------------------+-----------------
#     4  | skill-generate  | skill-create                   | both produce a SKILL.md draft from a spec/intake artifact
#     5  | skill-critic    | skill-critic                   | exact match
#     6  | skill-optimize  | skill-improve                  | skill-improve applies FIX patches + version bumps
#     7  | skill-verify    | skill-critic (re-invocation)   | post-optimize critic re-run = verification pass
#     9  | cousin-prompt   | skill-cousin-prompt            | new skill — divergence vs semantic siblings


def step_4_generate(target: Path, prior_results: list[dict[str, Any]],
                    output_path: Path | None) -> dict[str, Any]:
    """SOP step 4 — skill-generate. Dispatches to skill-create subagent."""
    return emit_bundle_or_merge(4, "skill-generate", "skill-create",
                                target, prior_results, output_path)


def step_5_critic(target: Path, prior_results: list[dict[str, Any]],
                  output_path: Path | None) -> dict[str, Any]:
    """SOP step 5 — skill-critic. 8-axis deterministic-rubric subagent review."""
    return emit_bundle_or_merge(5, "skill-critic", "skill-critic",
                                target, prior_results, output_path)


def step_6_optimize(target: Path, prior_results: list[dict[str, Any]],
                    output_path: Path | None) -> dict[str, Any]:
    """SOP step 6 — skill-optimize. Dispatches to skill-improve (FIX-patch + version-bump)."""
    return emit_bundle_or_merge(6, "skill-optimize", "skill-improve",
                                target, prior_results, output_path)


def step_7_verify(target: Path, prior_results: list[dict[str, Any]],
                  output_path: Path | None) -> dict[str, Any]:
    """SOP step 7 — skill-verify. Re-invokes skill-critic post-optimize to confirm fixes."""
    return emit_bundle_or_merge(7, "skill-verify", "skill-critic",
                                target, prior_results, output_path)


def step_9_cousin_prompt(target: Path, prior_results: list[dict[str, Any]],
                         output_path: Path | None) -> dict[str, Any]:
    """SOP step 9 — cousin-prompt. Subagent compares against semantic siblings for divergence."""
    return emit_bundle_or_merge(9, "cousin-prompt", "skill-cousin-prompt",
                                target, prior_results, output_path)


def step_0_architect(intent: str, critic_output_path: Path | None = None,
                     always_critic: bool = False) -> dict[str, Any]:
    """v5.18 Phase 2.0 + v5.18.1: invoke skill-spec --from-intent (Step A + B + C)
    and conditionally prepare a Step D critic-request bundle when
    confidence is low or sibling divergence is high.

    Critic invocation itself happens in the calling Claude Code session via
    Task tool — Python cannot spawn LLM subagents. This function emits the
    bundle path; the caller spawns the critic and re-invokes with
    --critic-output <path> to merge the response into proposal_v1.
    """
    if not all(p.exists() for p in (EXTRACT_SIGNALS_SCRIPT, PROPOSE_SPEC_SCRIPT, OBSERVE_SIBLINGS_SCRIPT)):
        return {"step": 0, "name": "skill-spec (--from-intent)", "status": "yellow",
                "reason": "architect scripts not found; skipping Step 0"}

    code, signals, stderr = run_subprocess([
        sys.executable, str(EXTRACT_SIGNALS_SCRIPT), "--intent", intent,
    ])
    if signals is None:
        return {"step": 0, "name": "skill-spec (--from-intent)", "status": "red",
                "reason": f"extract_signals crashed: {stderr[:120]}"}

    code, proposal, stderr = run_subprocess([
        sys.executable, str(PROPOSE_SPEC_SCRIPT), "--signals", "-",
    ], stdin=json.dumps(signals))
    if proposal is None:
        return {"step": 0, "name": "skill-spec (--from-intent)", "status": "red",
                "reason": f"propose_spec crashed: {stderr[:120]}"}

    proposed_layout = proposal.get("spec", {}).get("parity_layout")
    proposed_domain = proposal.get("spec", {}).get("parent_domain")
    sibling_evidence: dict[str, Any] = {}
    divergence_score = 0.0
    if proposed_domain:
        code, sib, _ = run_subprocess([
            sys.executable, str(OBSERVE_SIBLINGS_SCRIPT),
            "--domain", proposed_domain,
            "--proposal-layout", proposed_layout or "standard",
        ])
        if sib:
            sibling_evidence = sib
            divergence_score = sib.get("divergence", {}).get("divergence_score", 0.0)

    propose_flags = proposal.get("flags", {})
    overall_conf = proposal.get("confidence", {}).get("overall", 0.0)
    needs_critic = (
        always_critic
        or propose_flags.get("needs_critic", False)
        or overall_conf < 0.85
        or divergence_score > 0.30
    )

    critic_request_path: str | None = None
    proposal_v1 = proposal
    critic_response: dict[str, Any] | None = None

    if critic_output_path is not None and critic_output_path.is_file():
        try:
            loaded = json.loads(critic_output_path.read_text(encoding="utf-8"))
            critic_response = loaded
            proposal_v1 = merge_critic_response(proposal, loaded)
            needs_critic = False
        except (json.JSONDecodeError, OSError) as exc:
            return {"step": 0, "name": "skill-spec (--from-intent)", "status": "red",
                    "reason": f"critic-output parse failed: {exc}"}
    elif needs_critic:
        bundle = {
            "intent_text": intent,
            "signals": signals,
            "proposal_v0": proposal,
            "sibling_evidence": sibling_evidence,
            "trigger_reason": (
                "always_critic flag" if always_critic
                else f"overall_confidence={overall_conf:.2f} (<0.85)" if overall_conf < 0.85
                else f"sibling_divergence={divergence_score:.2f} (>0.30)" if divergence_score > 0.30
                else "propose_spec flags.needs_critic=true"
            ),
        }
        bundle_dir = META_DIR / "critic-requests"
        bundle_dir.mkdir(parents=True, exist_ok=True)
        bundle_id = str(uuid.uuid4())[:8]
        bundle_path = bundle_dir / f"critic-request-{bundle_id}.json"
        bundle_path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
        critic_request_path = str(bundle_path.relative_to(PLUGIN_ROOT)).replace("\\", "/")

    return {
        "step": 0,
        "name": "skill-spec (--from-intent)",
        "status": "green",
        "evidence": {
            "spec": proposal_v1.get("spec"),
            "rationales": proposal_v1.get("rationales"),
            "confidence": proposal_v1.get("confidence"),
            "sibling_evidence": sibling_evidence,
            "needs_critic": needs_critic,
            "critic_request_path": critic_request_path,
            "critic_merged": critic_response is not None,
            "next_step": (
                "invoke_critic_then_render"
                if (needs_critic and critic_response is None)
                else "user_confirmation_required"
            ),
            "critic_invocation_instructions": (
                {
                    "subagent_type": "skill-spec-critic",
                    "input_path": critic_request_path,
                    "expected_output_path": f"_meta-runtime/critic-requests/critic-response-{critic_request_path.split('-')[-1] if critic_request_path else '<missing-request-id>'}",
                    "after_completion": (
                        "Re-invoke: bin/skill_factory.py --from-intent <intent> "
                        "--critic-output <expected_output_path>"
                    ),
                } if (needs_critic and critic_response is None) else None
            ),
        },
    }


def merge_critic_response(proposal_v0: dict[str, Any], critic: dict[str, Any]) -> dict[str, Any]:
    """Apply critic field_decisions over proposal_v0 to produce proposal_v1."""
    field_decisions = critic.get("field_decisions", {})
    spec = dict(proposal_v0.get("spec", {}))
    rationales = dict(proposal_v0.get("rationales", {}))
    overrides_applied: list[str] = []
    user_input_needed: list[str] = []
    for field, decision in field_decisions.items():
        action = decision.get("action")
        if action == "override":
            spec[field] = decision.get("value")
            rationales[field] = f"[critic override] {decision.get('rationale', '')}"
            overrides_applied.append(field)
        elif action == "user_input_needed":
            user_input_needed.append(field)
            rationales[field] = f"[critic flagged] {decision.get('rationale', '')}"
    confidence = dict(proposal_v0.get("confidence", {}))
    if "overall_confidence" in critic:
        confidence["overall"] = critic["overall_confidence"]
    flags = dict(proposal_v0.get("flags", {}))
    flags["critic_overrides_applied"] = overrides_applied
    flags["critic_user_input_needed"] = user_input_needed
    flags["needs_critic"] = False
    return {
        "status": "proposed",
        "spec": spec,
        "rationales": rationales,
        "confidence": confidence,
        "flags": flags,
        "critic_summary": critic.get("summary", ""),
        "critic_telemetry_notes": critic.get("telemetry_notes", ""),
    }


def run_pipeline(target: Path, phase: str = "1", intent: str | None = None,
                 phase2_outputs: dict[str, Path | None] | None = None) -> dict[str, Any]:
    """Execute the 10-step SOP and return a per-skill verdict bundle.

    Phase 1 mode runs deterministic steps 1-3, 8, 10 only. Phase 2 ("full")
    additionally invokes Phase 2 steps 4-7, 9 via emit_bundle_or_merge: each
    either merges a previously-supplied subagent response (`phase2_outputs`)
    or emits a request bundle and returns a yellow verdict. Yellow blocks
    auto-ship; the CEO must invoke the named subagents and re-enter.
    """
    p2 = phase2_outputs or {}
    results: list[dict[str, Any]] = []
    if intent:
        results.append(step_0_architect(intent))
    results.append(step_1_spec(target))
    results.append(step_2_graph(target))
    results.append(step_3_parity(target))
    if phase == "full":
        results.append(step_4_generate(target, results, p2.get("skill-generate")))
        results.append(step_5_critic(target, results, p2.get("skill-critic")))
        results.append(step_6_optimize(target, results, p2.get("skill-optimize")))
        results.append(step_7_verify(target, results, p2.get("skill-verify")))
    results.append(step_8_citation_grep(target))
    if phase == "full":
        results.append(step_9_cousin_prompt(target, results, p2.get("cousin-prompt")))
    results.append(step_10_stale_path(target))

    statuses = [r["status"] for r in results]
    if "red" in statuses:
        verdict = "red"
    elif "yellow" in statuses:
        verdict = "yellow"
    else:
        verdict = "green"

    return {
        "name": target.parent.name,
        "path": str(target.relative_to(PLUGIN_ROOT)).replace("\\", "/"),
        "verdict": verdict,
        "step_results": results,
    }


def append_factory_verdicts_jsonl(results: list[dict[str, Any]], batch_id: str, phase: str) -> None:
    """Append one JSONL row per skill to _meta-runtime/factory-verdicts.jsonl.

    The JSONL is the authoritative source-of-truth for factory verdicts (data-storage-matrix
    row `skill-factory-verdicts`). The markdown batch-report becomes a rendered view that
    can be re-derived via `bin/render_batch_report.py --batch-id <id>`.
    """
    META_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with FACTORY_VERDICTS_JSONL.open("a", encoding="utf-8") as fp:
        for r in results:
            step_results: dict[str, str] = {}
            fail_reasons: list[str] = []
            for step in r.get("step_results", []):
                step_results[str(step.get("step"))] = step.get("status", "unknown")
                if step.get("status") == "red" and step.get("reason"):
                    fail_reasons.append(f"step{step.get('step')}: {step.get('reason')}")
            row = {
                "ts": ts,
                "batch_id": batch_id,
                "skill_id": r.get("name"),
                "skill_path": r.get("path"),
                "verdict": r.get("verdict"),
                "step_results": step_results,
                "fail_reason": "; ".join(fail_reasons) if fail_reasons else None,
                "ceo_decision": None,
                "phase": phase,
            }
            fp.write(json.dumps(row, ensure_ascii=False) + "\n")


def render_batch_report(results: list[dict[str, Any]], batch_id: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    counts = {"green": 0, "yellow": 0, "red": 0}
    for r in results:
        counts[r["verdict"]] += 1

    lines = [
        f"# Factory batch report — {timestamp}",
        "",
        f"**Batch ID**: `{batch_id}`",
        "",
        "## Summary",
        "",
        f"- Batch size: {len(results)} skill(s)",
        f"- Verdicts: {counts['green']} green / {counts['yellow']} yellow / {counts['red']} red",
        "",
        "## Per-skill verdicts",
        "",
    ]
    for r in results:
        lines.append(f"### {r['name']} — {r['verdict']}")
        lines.append("")
        for step in r["step_results"]:
            evid = step.get("reason") or step.get("evidence") or ""
            evid_str = json.dumps(evid)[:160] if not isinstance(evid, str) else evid[:160]
            lines.append(f"- Step {step['step']} ({step['name']}): **{step['status']}** — {evid_str}")
        lines.append("")
    lines.extend([
        "## CEO bulk decision",
        "",
        "Reply with one of:",
        "",
        "- `ship green, defer yellow, discuss red` — auto-ships green, queues yellow for next batch, opens red for discussion",
        "- `ship green+yellow, discuss red` — accepts yellow caveats",
        "- `discuss all` — manual review per skill (escape hatch)",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="kiho skill factory orchestrator (v5.18 Phase 2.0 + v5.17 Phase 1)")
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--regen", help="single skill SKILL.md path")
    grp.add_argument("--batch", help="batch-spec.md path (one skill per line or table)")
    grp.add_argument("--from-intent", help="raw intent text; runs Step 0 architect, then full pipeline (proposes spec; user confirms before any write)")
    ap.add_argument("--phase", choices=["1", "full"], default="1")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--critic-output", type=Path,
                    help="(Step 0 architect) path to architect-critic response; merges critic decisions into proposal_v1")
    ap.add_argument("--always-critic", action="store_true",
                    help="(Step 0 architect) force critic-request bundle generation even when confidence is high")
    # Phase 2 per-step response paths (each merges a subagent JSON response
    # generated from the corresponding bundle in _meta-runtime/<step>-requests/).
    ap.add_argument("--skill-generate-output", type=Path,
                    help="(Phase 2 step 4) path to skill-generate subagent response JSON")
    ap.add_argument("--skill-critic-output", type=Path,
                    help="(Phase 2 step 5) path to skill-critic subagent response JSON")
    ap.add_argument("--skill-optimize-output", type=Path,
                    help="(Phase 2 step 6) path to skill-optimize subagent response JSON")
    ap.add_argument("--skill-verify-output", type=Path,
                    help="(Phase 2 step 7) path to skill-verify subagent response JSON")
    ap.add_argument("--cousin-prompt-output", type=Path,
                    help="(Phase 2 step 9) path to cousin-prompt subagent response JSON")
    args = ap.parse_args()
    phase2_outputs: dict[str, Path | None] = {
        "skill-generate":  args.skill_generate_output,
        "skill-critic":    args.skill_critic_output,
        "skill-optimize":  args.skill_optimize_output,
        "skill-verify":    args.skill_verify_output,
        "cousin-prompt":   args.cousin_prompt_output,
    }

    try:
        if args.from_intent:
            architect_result = step_0_architect(
                args.from_intent,
                critic_output_path=args.critic_output,
                always_critic=args.always_critic,
            )
            print(json.dumps({
                "mode": "architect-only",
                "intent": args.from_intent[:120],
                "architect_output": architect_result,
                "next_step": (
                    "user reviews proposal; on accept, re-invoke with --regen <new_skill_path> after files are scaffolded"
                    if not architect_result.get("evidence", {}).get("needs_critic")
                    else "invoke critic subagent via Task tool (instructions in evidence.critic_invocation_instructions); then re-invoke with --critic-output"
                ),
            }, indent=2))
            return 0 if architect_result.get("status") == "green" else 1

        targets: list[Path] = []
        if args.regen:
            target = PLUGIN_ROOT / args.regen if not Path(args.regen).is_absolute() else Path(args.regen)
            if not target.is_file():
                print(json.dumps({"status": "error", "message": f"target not found: {args.regen}"}))
                return 2
            targets = [target]
        else:
            spec_path = PLUGIN_ROOT / args.batch if not Path(args.batch).is_absolute() else Path(args.batch)
            if not spec_path.is_file():
                print(json.dumps({"status": "error", "message": f"batch spec not found: {args.batch}"}))
                return 2
            for line in spec_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and ("SKILL.md" in line or line.endswith(".md")):
                    p = PLUGIN_ROOT / line if not Path(line).is_absolute() else Path(line)
                    if p.is_file():
                        targets.append(p)

        if not targets:
            print(json.dumps({"status": "error", "message": "no valid targets resolved"}))
            return 2

        batch_id = str(uuid.uuid4())[:8]
        results = [run_pipeline(t, args.phase, phase2_outputs=phase2_outputs)
                   for t in targets]

        report_md = render_batch_report(results, batch_id)
        if args.dry_run:
            print(report_md)
        else:
            META_DIR.mkdir(parents=True, exist_ok=True)
            report_path = META_DIR / f"batch-report-{batch_id}.md"
            report_path.write_text(report_md, encoding="utf-8")
            append_factory_verdicts_jsonl(results, batch_id, args.phase)
            print(json.dumps({
                "status": "ok",
                "batch_id": batch_id,
                "report_path": str(report_path.relative_to(PLUGIN_ROOT)).replace("\\", "/"),
                "verdicts_jsonl": str(FACTORY_VERDICTS_JSONL.relative_to(PLUGIN_ROOT)).replace("\\", "/"),
                "verdicts": {v: sum(1 for r in results if r["verdict"] == v) for v in ("green", "yellow", "red")},
                "ceo_action_required": any(r["verdict"] != "green" for r in results),
            }, indent=2))

        return 0 if all(r["verdict"] == "green" for r in results) else 1

    except SystemExit:
        raise
    except Exception as exc:
        print(f"internal error: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
