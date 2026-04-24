#!/usr/bin/env python3
"""
embedding_util.py — lightweight similarity & clustering helper for kiho v6
consolidation cycles (§3.8).

Tier preference:
  1. sentence-transformers (best quality; optional install)
  2. sklearn TfidfVectorizer + cosine_similarity (common in modern envs)
  3. Pure-Python TF-IDF via collections.Counter (always available)

No hard dependency on numpy/sklearn. Graceful degrade: when nothing usable
is available (shouldn't happen — tier 3 is stdlib), clustering returns
singletons.

Public API:
    text_similarity(a: str, b: str) -> float  # 0.0 .. 1.0
    cluster_files(paths: list[Path], threshold: float = 0.70) -> list[list[Path]]
    cluster_texts(texts: list[str], threshold: float = 0.70) -> list[list[int]]

CLI (for quick debugging from shell):
    python bin/embedding_util.py similarity <file_a> <file_b>
    python bin/embedding_util.py cluster <dir> [--threshold 0.70] [--ext .md]
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

# Tier availability flags
_HAS_SBERT = False
_HAS_SKLEARN = False

try:
    from sentence_transformers import SentenceTransformer  # type: ignore
    _HAS_SBERT = True
except Exception:  # pragma: no cover
    SentenceTransformer = None  # type: ignore

if not _HAS_SBERT:
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore
        from sklearn.metrics.pairwise import cosine_similarity  # type: ignore
        import numpy as np  # type: ignore
        _HAS_SKLEARN = True
    except Exception:  # pragma: no cover
        pass


# ---------------------------------------------------------------------------
# Tokenization + IDF (pure stdlib)
# ---------------------------------------------------------------------------


_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")
_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "but", "if", "then", "else", "to",
    "of", "in", "on", "at", "for", "from", "by", "with", "is", "are",
    "was", "were", "be", "been", "being", "has", "have", "had", "do",
    "does", "did", "it", "its", "this", "that", "these", "those", "as",
    "which", "who", "whom", "whose", "what", "when", "where", "why", "how",
})


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text) if t.lower() not in _STOPWORDS]


def _tf(tokens: list[str]) -> dict[str, float]:
    c = Counter(tokens)
    total = sum(c.values()) or 1
    return {t: n / total for t, n in c.items()}


def _idf(docs_tokens: list[list[str]]) -> dict[str, float]:
    n_docs = len(docs_tokens) or 1
    df: Counter = Counter()
    for toks in docs_tokens:
        df.update(set(toks))
    return {t: math.log((n_docs + 1) / (n + 1)) + 1 for t, n in df.items()}


def _tfidf_vector(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    tf = _tf(tokens)
    return {t: tf[t] * idf.get(t, 0.0) for t in tf}


def _cosine_sparse(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    common = set(a.keys()) & set(b.keys())
    dot = sum(a[t] * b[t] for t in common)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def text_similarity(a: str, b: str) -> float:
    """Return cosine similarity in [0, 1] between two text strings.

    Uses the best available backend.
    """
    if _HAS_SBERT:
        try:
            model = _sbert_model()
            va = model.encode(a, normalize_embeddings=True)  # type: ignore[attr-defined]
            vb = model.encode(b, normalize_embeddings=True)  # type: ignore[attr-defined]
            return float(sum(x * y for x, y in zip(va, vb)))
        except Exception:
            pass
    if _HAS_SKLEARN:
        try:
            v = TfidfVectorizer().fit_transform([a, b])  # type: ignore
            return float(cosine_similarity(v[0], v[1])[0][0])  # type: ignore
        except Exception:
            pass
    # Pure fallback
    toks_a = _tokenize(a)
    toks_b = _tokenize(b)
    idf = _idf([toks_a, toks_b])
    return _cosine_sparse(_tfidf_vector(toks_a, idf), _tfidf_vector(toks_b, idf))


_SBERT_MODEL = None


def _sbert_model():
    global _SBERT_MODEL
    if _SBERT_MODEL is None:
        _SBERT_MODEL = SentenceTransformer("all-MiniLM-L6-v2")  # type: ignore
    return _SBERT_MODEL


def cluster_texts(texts: list[str], threshold: float = 0.70) -> list[list[int]]:
    """Return a list of clusters, each being a list of input indices.

    Greedy threshold-based clustering: walk the texts in order and assign to
    the first existing cluster whose centroid (represented by any member)
    exceeds the threshold, else open a new cluster.
    """
    if not texts:
        return []
    # Precompute all vectors once
    docs_tokens = [_tokenize(t) for t in texts]

    use_sbert = _HAS_SBERT
    use_sk = _HAS_SKLEARN and not use_sbert
    vectors: list = []

    if use_sbert:
        try:
            model = _sbert_model()
            vectors = [
                model.encode(t, normalize_embeddings=True)  # type: ignore[attr-defined]
                for t in texts
            ]
        except Exception:
            use_sbert = False
    if not use_sbert and use_sk:
        try:
            mat = TfidfVectorizer().fit_transform(texts)  # type: ignore
            vectors = [mat[i] for i in range(mat.shape[0])]
        except Exception:
            use_sk = False
    if not use_sbert and not use_sk:
        idf = _idf(docs_tokens)
        vectors = [_tfidf_vector(toks, idf) for toks in docs_tokens]

    def sim(i: int, j: int) -> float:
        if use_sbert:
            return float(sum(x * y for x, y in zip(vectors[i], vectors[j])))
        if use_sk:
            try:
                return float(cosine_similarity(vectors[i], vectors[j])[0][0])  # type: ignore
            except Exception:
                return 0.0
        return _cosine_sparse(vectors[i], vectors[j])

    clusters: list[list[int]] = []
    for i in range(len(texts)):
        placed = False
        for c in clusters:
            if sim(i, c[0]) >= threshold:
                c.append(i)
                placed = True
                break
        if not placed:
            clusters.append([i])
    return clusters


def cluster_files(paths: list[Path], threshold: float = 0.70) -> list[list[Path]]:
    """Read text from each path and cluster using `cluster_texts`.

    Unreadable paths are dropped from the result (with a stderr note).
    """
    texts: list[str] = []
    usable: list[Path] = []
    for p in paths:
        try:
            texts.append(p.read_text(encoding="utf-8", errors="replace"))
            usable.append(p)
        except OSError as e:
            print(f"embedding_util: skip {p}: {e!r}", file=sys.stderr)
    idx_clusters = cluster_texts(texts, threshold)
    return [[usable[i] for i in c] for c in idx_clusters]


def backend_name() -> str:
    if _HAS_SBERT:
        return "sentence-transformers"
    if _HAS_SKLEARN:
        return "sklearn-tfidf"
    return "stdlib-tfidf"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _cmd_similarity(args: argparse.Namespace) -> int:
    a = Path(args.file_a).read_text(encoding="utf-8", errors="replace")
    b = Path(args.file_b).read_text(encoding="utf-8", errors="replace")
    print(json.dumps({
        "backend": backend_name(),
        "similarity": round(text_similarity(a, b), 4),
    }))
    return 0


def _cmd_cluster(args: argparse.Namespace) -> int:
    root = Path(args.dir)
    ext = args.ext
    files = sorted(root.rglob(f"*{ext}"))
    clusters = cluster_files(files, threshold=args.threshold)
    result = [
        {"size": len(c), "members": [str(p) for p in c]} for c in clusters
    ]
    print(json.dumps({
        "backend": backend_name(),
        "threshold": args.threshold,
        "total_files": len(files),
        "cluster_count": len(clusters),
        "clusters": result,
    }, indent=2, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="kiho v6 embedding/similarity helper")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("similarity", help="compare two files, print cosine sim")
    s.add_argument("file_a")
    s.add_argument("file_b")
    s.set_defaults(func=_cmd_similarity)

    c = sub.add_parser("cluster", help="cluster files under a directory")
    c.add_argument("dir")
    c.add_argument("--threshold", type=float, default=0.70)
    c.add_argument("--ext", default=".md")
    c.set_defaults(func=_cmd_cluster)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
