"""Lightweight, explainable similarity for clustering articles into stories.

MVP uses lexical overlap (title/description tokens) + publication-time
proximity — no embeddings required, so it runs anywhere and is easy to reason
about. The AI/embedding path (pgvector) slots in behind the same `score`
interface in a later iteration without changing callers.
"""
from __future__ import annotations

import re
from datetime import datetime

_TOKEN_RE = re.compile(r"[a-z0-9؀-ۿ]+")

# Small stopword set (EN + a few Persian) — kept short on purpose.
_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "as", "at",
    "by", "with", "from", "is", "are", "was", "were", "be", "been", "it", "its",
    "that", "this", "after", "over", "amid", "say", "says", "said", "new",
    "us", "u", "s", "news", "live", "update", "updates", "report", "reports",
    "و", "در", "به", "از", "که", "را", "با", "این", "است", "برای",
}


def tokenize(*texts: str | None) -> set[str]:
    tokens: set[str] = set()
    for text in texts:
        if not text:
            continue
        for tok in _TOKEN_RE.findall(text.lower()):
            if len(tok) > 1 and tok not in _STOP:
                tokens.add(tok)
    return tokens


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def time_proximity(t1: datetime | None, t2: datetime | None, window_hours: float) -> float:
    """1.0 when simultaneous, decaying to 0 at `window_hours` apart."""
    if t1 is None or t2 is None:
        return 0.5  # neutral when unknown
    delta_h = abs((t1 - t2).total_seconds()) / 3600.0
    return max(0.0, 1.0 - delta_h / window_hours)


def score(
    tokens_a: set[str],
    tokens_b: set[str],
    time_a: datetime | None,
    time_b: datetime | None,
    *,
    window_hours: float = 72.0,
) -> float:
    """Combined 0..1 similarity: mostly lexical, nudged by time proximity."""
    lexical = jaccard(tokens_a, tokens_b)
    proximity = time_proximity(time_a, time_b, window_hours)
    return round(0.78 * lexical + 0.22 * proximity, 4)
