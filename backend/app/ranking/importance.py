"""Explainable importance scoring (§14). Every factor is a named component so
the score can always be explained — never a black box."""
from __future__ import annotations

from dataclasses import dataclass

IRAN_KEYWORDS = (
    "iran", "iranian", "tehran", "hormuz", "khamenei", "irgc", "persian gulf",
    "revolutionary guard", "ایران", "تهران", "هرمز",
)


@dataclass(slots=True)
class ImportanceBreakdown:
    independent_sources: float
    source_reliability: float
    coverage_velocity: float
    recency: float
    iran_relevance: float

    @property
    def total(self) -> float:
        return round(
            self.independent_sources + self.source_reliability
            + self.coverage_velocity + self.recency + self.iran_relevance,
            2,
        )

    def as_dict(self) -> dict:
        return {
            "independent_sources": self.independent_sources,
            "source_reliability": self.source_reliability,
            "coverage_velocity": self.coverage_velocity,
            "recency": self.recency,
            "iran_relevance": self.iran_relevance,
            "total": self.total,
        }


def score_importance(
    *,
    distinct_sources: int,
    article_count: int,
    avg_reliability: float,
    hours_since_latest: float | None,
    iran_hits: int,
) -> ImportanceBreakdown:
    sources = min(distinct_sources, 5) / 5 * 35          # up to 35
    reliability = max(0.0, min(avg_reliability, 1.0)) * 20  # up to 20
    velocity = min(article_count, 6) / 6 * 15            # up to 15
    if hours_since_latest is None:
        recency = 10.0
    else:
        recency = max(0.0, 1.0 - hours_since_latest / 48.0) * 20  # up to 20
    iran = min(iran_hits, 3) / 3 * 10                    # up to 10
    return ImportanceBreakdown(
        independent_sources=round(sources, 2),
        source_reliability=round(reliability, 2),
        coverage_velocity=round(velocity, 2),
        recency=round(recency, 2),
        iran_relevance=round(iran, 2),
    )


def count_iran_hits(*texts: str | None) -> int:
    blob = " ".join(t.lower() for t in texts if t)
    return sum(1 for kw in IRAN_KEYWORDS if kw in blob)


def iran_relevance_label(iran_hits: int) -> str:
    if iran_hits >= 3:
        return "high"
    if iran_hits >= 1:
        return "medium"
    return "none"
