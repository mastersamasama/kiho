// kiho theme-contrast-guard — runtime dev warner (Layer 3)
//
// Wires into ThemeProvider in __DEV__ to console.warn() on low-contrast pairs
// at render time. Catches dynamic colour composition that Layer 1 (static
// token matrix) cannot model: state-driven colour, prop overrides, conditional
// styles, computed gradients, etc.
//
// Production builds: noop. Bundle size in prod = 0 bytes (the entire body is
// gated behind `if (__DEV__)`).
//
// Usage:
//   1. Copy this file to apps/<your-app>/src/theme/runtime-contrast-warner.ts
//   2. In ThemeProvider.tsx (or wherever your theme root is):
//        import { installContrastWarner } from './runtime-contrast-warner';
//        useEffect(() => {
//          if (__DEV__) installContrastWarner({ threshold: 4.5 });
//        }, []);
//   3. (Optional) Enable strict mode by setting process.env.KIHO_CONTRAST_STRICT
//      = 'true' or passing { strict: true } — low-contrast pairs will then
//      throw in dev render rather than warn.
//
// Platform strategy (Turn 1.5 — architectural fix):
//   * Web (RN-Web): a `MutationObserver` watches `document.body` for added
//     text-bearing nodes. For each, we read the element's computed `color`
//     and walk DOM ancestors to find the nearest non-transparent
//     `backgroundColor`. This is necessary because RN convention splits
//     foreground (`<Text color>`) and background (`<View bg>`) across
//     components — a same-element check finds 0 pairs in practice.
//   * Native (iOS/Android): keeps the original `Text.render` monkey-patch
//     with same-element-only style inspection. DOM walking isn't available;
//     full coverage is deferred to Phase 3 (selector hook / context split).
//     A one-time `console.info` advertises the limitation.

import { Text, Platform } from "react-native";
import type { ComponentType } from "react";

// ---------------------------------------------------------------------------
// WCAG 2.x contrast — port of bin/contrast_audit.py (~25 LOC)
// ---------------------------------------------------------------------------

type RGB = [number, number, number];
type RGBA = [number, number, number, number];

function parseColor(s: string): RGBA | null {
  if (!s) return null;
  s = s.trim();
  if (!s) return null;
  // #rgb / #rrggbb / #rrggbbaa
  if (s.startsWith("#")) {
    const h = s.slice(1);
    if (h.length === 3) {
      return [
        parseInt(h[0] + h[0], 16),
        parseInt(h[1] + h[1], 16),
        parseInt(h[2] + h[2], 16),
        1,
      ];
    }
    if (h.length === 6) {
      return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16), 1];
    }
    if (h.length === 8) {
      return [
        parseInt(h.slice(0, 2), 16),
        parseInt(h.slice(2, 4), 16),
        parseInt(h.slice(4, 6), 16),
        parseInt(h.slice(6, 8), 16) / 255,
      ];
    }
    return null;
  }
  // rgb(r,g,b) / rgba(r,g,b,a)
  const m = /^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+))?\s*\)$/i.exec(s);
  if (m) return [Number(m[1]), Number(m[2]), Number(m[3]), m[4] !== undefined ? Number(m[4]) : 1];
  return null;
}

function channel(c: number): number {
  const v = c / 255;
  return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
}

function luminance([r, g, b]: RGB): number {
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

function contrast(a: RGB, b: RGB): number {
  const la = luminance(a);
  const lb = luminance(b);
  const [hi, lo] = la >= lb ? [la, lb] : [lb, la];
  return (hi + 0.05) / (lo + 0.05);
}

function compositeOn(fg: RGBA, bg: RGB): RGB {
  const a = fg[3];
  if (a >= 1) return [fg[0], fg[1], fg[2]];
  return [
    Math.round(fg[0] * a + bg[0] * (1 - a)),
    Math.round(fg[1] * a + bg[1] * (1 - a)),
    Math.round(fg[2] * a + bg[2] * (1 - a)),
  ];
}

// ---------------------------------------------------------------------------
// Style cascade walker
// ---------------------------------------------------------------------------

interface InstallOptions {
  /** Body-text minimum ratio. Default 4.5 (WCAG SC 1.4.3 AA). */
  threshold?: number;
  /** When true, throw in dev render on any low-contrast finding. Default
   *  reads `process.env.KIHO_CONTRAST_STRICT === 'true'` (false otherwise). */
  strict?: boolean;
  /** Hero token names that bump threshold to 7.0. */
  heroTokens?: readonly string[];
}

interface FlatStyle {
  color?: string;
  backgroundColor?: string;
  fontSize?: number;
  fontWeight?: string | number;
  [k: string]: unknown;
}

/** Flatten a RN style prop (object | array | falsy | id) into a single object.
 *  We only need `color` / `backgroundColor` / `fontSize` / `fontWeight`. */
function flattenStyle(style: unknown): FlatStyle {
  if (!style) return {};
  if (typeof style === "number") return {}; // RN registered style id; not resolvable here
  if (Array.isArray(style)) {
    const out: FlatStyle = {};
    for (const s of style) Object.assign(out, flattenStyle(s));
    return out;
  }
  if (typeof style === "object") return style as FlatStyle;
  return {};
}

let _installed = false;
let _webObserver: unknown = null;

// ---------------------------------------------------------------------------
// Shared evaluator — given fg + bg color strings + size hints, decide whether
// to warn / throw. Returns a stable cache key on report.
// ---------------------------------------------------------------------------

interface EvalContext {
  threshold: number;
  strict: boolean;
  heroTokens: Set<string>;
  seen: Set<string>;
}

function evaluatePair(
  ctx: EvalContext,
  fg: string,
  bg: string,
  componentName: string,
  fontSize: number,
  isBold: boolean,
  tokenName: string,
): void {
  const fgRGBA = parseColor(fg);
  const bgRGBA = parseColor(bg);
  if (!fgRGBA || !bgRGBA) return;

  const bgRGB: RGB =
    bgRGBA[3] >= 1
      ? [bgRGBA[0], bgRGBA[1], bgRGBA[2]]
      : compositeOn(bgRGBA, [255, 255, 255]); // assume white under translucent
  const fgRGB =
    fgRGBA[3] >= 1
      ? ([fgRGBA[0], fgRGBA[1], fgRGBA[2]] as RGB)
      : compositeOn(fgRGBA, bgRGB);
  const ratio = contrast(fgRGB, bgRGB);

  const isLargeText = fontSize >= 18 || (fontSize >= 14 && isBold);
  const isHero = ctx.heroTokens.has(tokenName);
  const required = isHero ? 7.0 : isLargeText ? 3.0 : ctx.threshold;

  if (ratio + 1e-6 < required) {
    const cacheKey = `${fg}|${bg}|${required}`;
    if (!ctx.seen.has(cacheKey)) {
      ctx.seen.add(cacheKey);
      const msg =
        `[contrast] ${componentName} color=${fg} on bg=${bg} ratio=${ratio.toFixed(2)} ` +
        `(required ${required}${isHero ? ", hero" : isLargeText ? ", large" : ""})`;
      if (ctx.strict) {
        throw new Error(msg);
      }
      // eslint-disable-next-line no-console
      console.warn(msg);
    }
  }
}

// ---------------------------------------------------------------------------
// Web platform — DOM walker + MutationObserver
// ---------------------------------------------------------------------------

/** Walk DOM ancestors and return the first non-transparent computed
 *  `backgroundColor`, or null if none found / DOM lifecycle is not ready. */
function getEffectiveBackground(node: Element): string | null {
  let current: Element | null = node;
  while (current) {
    let style: CSSStyleDeclaration | null = null;
    try {
      style = window.getComputedStyle(current);
    } catch {
      style = null;
    }
    // Defensive: getComputedStyle can return null/undefined for detached nodes
    // and an empty string for elements not yet in the live render tree.
    const bg = style?.backgroundColor;
    if (bg && bg !== "transparent" && bg !== "rgba(0, 0, 0, 0)") {
      return bg;
    }
    current = current.parentElement;
  }
  return null;
}

/** True when the element renders meaningful text (used to avoid evaluating
 *  every wrapper div). RN-Web emits text content into `div`/`span` with the
 *  `dir` attr OR explicitly inside elements whose direct childNodes include
 *  a non-empty TEXT_NODE. */
function hasOwnText(el: Element): boolean {
  const cn = el.childNodes;
  for (let i = 0; i < cn.length; i++) {
    const n = cn[i];
    if (!n) continue;
    if (n.nodeType === 3 /* TEXT_NODE */) {
      // Cast via `unknown` to a DOM-Text-shaped type — RN's `Text` import
      // shadows the global DOM Text in this module.
      const t = (n as unknown as { nodeValue: string | null }).nodeValue;
      if (t && t.trim().length > 0) return true;
    }
  }
  return false;
}

function installWebObserver(ctx: EvalContext): void {
  if (typeof window === "undefined" || typeof document === "undefined") return;
  if (typeof MutationObserver === "undefined") return;

  // Per-element computed-style fingerprint cache. Skip re-eval when the
  // (color, bg, fontSize, fontWeight) tuple hasn't changed.
  const elCache = new WeakMap<Element, string>();
  // Pending batch of elements to evaluate; flushed every 200ms.
  const pending = new Set<Element>();
  let flushScheduled = false;

  const evaluateElement = (el: Element): void => {
    let cs: CSSStyleDeclaration | null = null;
    try {
      cs = window.getComputedStyle(el);
    } catch {
      cs = null;
    }
    if (!cs) return;
    const fg = cs.color;
    if (!fg) return; // empty string — DOM not ready yet
    const fontSizePx = parseFloat(cs.fontSize || "14") || 14;
    const fontWeight = cs.fontWeight || "";
    const bg = getEffectiveBackground(el);
    if (!bg) return; // body/html with no bg, or detached subtree

    const fingerprint = `${fg}|${bg}|${fontSizePx}|${fontWeight}`;
    if (elCache.get(el) === fingerprint) return;
    elCache.set(el, fingerprint);

    const isBold = /^(?:[6-9]00|bold)$/i.test(String(fontWeight));
    const tokenName =
      (el.getAttribute && el.getAttribute("data-token")) ||
      (el.getAttribute && el.getAttribute("data-testid")) ||
      "";
    const componentName =
      (el.getAttribute && el.getAttribute("data-testid")) ||
      (el.getAttribute && el.getAttribute("aria-label")) ||
      el.tagName.toLowerCase();

    evaluatePair(ctx, fg, bg, componentName, fontSizePx, isBold, tokenName);
  };

  const flush = (): void => {
    flushScheduled = false;
    const batch = Array.from(pending);
    pending.clear();
    for (const el of batch) {
      try {
        if (el.isConnected) evaluateElement(el);
      } catch (err) {
        if (ctx.strict) throw err;
        // Silent in non-strict — never crash due to the warner
      }
    }
  };

  const schedule = (): void => {
    if (flushScheduled) return;
    flushScheduled = true;
    setTimeout(flush, 200);
  };

  const enqueueSubtree = (root: Element): void => {
    if (hasOwnText(root)) pending.add(root);
    // Also descend; RN-Web wraps text in nested spans.
    const all = root.querySelectorAll ? root.querySelectorAll("*") : [];
    for (let i = 0; i < all.length; i++) {
      const el = all[i];
      if (el && hasOwnText(el)) pending.add(el);
    }
    schedule();
  };

  const observer = new MutationObserver((mutations) => {
    for (const m of mutations) {
      if (m.type === "childList") {
        m.addedNodes.forEach((n) => {
          if (n.nodeType === 1 /* ELEMENT_NODE */) {
            enqueueSubtree(n as Element);
          }
        });
      } else if (m.type === "characterData") {
        const parent = (m.target as Node).parentElement;
        if (parent) {
          pending.add(parent);
          schedule();
        }
      } else if (m.type === "attributes") {
        if (m.target.nodeType === 1) {
          pending.add(m.target as Element);
          schedule();
        }
      }
    }
  });

  // Seed with whatever's already mounted (theme provider effect runs after
  // first paint, so initial body content would otherwise be missed).
  if (document.body) enqueueSubtree(document.body);

  observer.observe(document.body, {
    childList: true,
    subtree: true,
    characterData: true,
    attributes: true,
    attributeFilter: ["style", "class"],
  });

  _webObserver = observer;
}

// ---------------------------------------------------------------------------
// Native platform — same-element Text.render patch (legacy behaviour)
// ---------------------------------------------------------------------------

function installNativeTextPatch(ctx: EvalContext): boolean {
  const TextAny = Text as unknown as ComponentType<unknown> & {
    render?: (props: Record<string, unknown>, ref: unknown) => unknown;
  };
  const original = TextAny.render;
  if (typeof original !== "function") {
    // RN-Web shim may not expose render; fall back to a wrapper at the
    // theme provider level instead. Skip silently.
    return false;
  }

  TextAny.render = function patchedTextRender(props: Record<string, unknown>, ref: unknown) {
    try {
      const style = flattenStyle(props?.style);
      const fg = typeof style.color === "string" ? style.color : undefined;
      const bg =
        (typeof style.backgroundColor === "string" ? style.backgroundColor : undefined) ??
        (typeof props?.contextBg === "string" ? (props.contextBg as string) : undefined);

      if (fg && bg) {
        const fontSize = typeof style.fontSize === "number" ? style.fontSize : 14;
        const isBold =
          String(style.fontWeight ?? "").match(/^(?:[6-9]00|bold)$/i) !== null;
        const tokenName = typeof props?.["data-token"] === "string" ? (props["data-token"] as string) : "";
        const componentName =
          (props?.testID as string) || (props?.accessibilityLabel as string) || "<Text>";
        evaluatePair(ctx, fg, bg, componentName, fontSize, isBold, tokenName);
      }
    } catch (err) {
      if (ctx.strict) throw err;
      // Silent in non-strict — never crash render due to the warner
    }
    return original.call(this, props, ref);
  };
  return true;
}

let _nativeNoticeShown = false;

export function installContrastWarner(options: InstallOptions = {}): void {
  if (_installed) return;
  if (typeof __DEV__ !== "undefined" && !__DEV__) return;
  _installed = true;

  const threshold = options.threshold ?? 4.5;
  const strict =
    options.strict ??
    (typeof process !== "undefined" && process.env?.KIHO_CONTRAST_STRICT === "true");
  const heroTokens = new Set(options.heroTokens ?? ["heroNumber", "netWorth"]);

  const ctx: EvalContext = {
    threshold,
    strict,
    heroTokens,
    seen: new Set<string>(),
  };

  if (Platform.OS === "web") {
    // Preferred: observe ACTUAL rendered DOM. Catches RN's split
    // <View bg> <Text color> pattern that the same-element check missed.
    installWebObserver(ctx);
  } else {
    // iOS / Android — same-element best-effort only.
    const ok = installNativeTextPatch(ctx);
    if (ok && !_nativeNoticeShown) {
      _nativeNoticeShown = true;
      // eslint-disable-next-line no-console
      console.info(
        "[contrast] native contrast detection limited to same-element style; " +
          "full coverage requires Phase 3 context split (selector hook).",
      );
    }
    if (!ok) {
      _installed = false;
    }
  }
}

/** Test-only — restore install flag. Called from setup files. */
export function uninstallContrastWarner(): void {
  if (_webObserver && typeof (_webObserver as { disconnect?: () => void }).disconnect === "function") {
    try {
      (_webObserver as { disconnect: () => void }).disconnect();
    } catch {
      /* noop */
    }
  }
  _webObserver = null;
  _nativeNoticeShown = false;
  _installed = false;
}
