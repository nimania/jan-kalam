"""Trends / «بورس اخبار» — a ranked board of what is being covered most right now.

Computed from the currently published stories (no external calls):
  • topics ranked by how many stories carry them and how much total coverage
    (sum of independent-source counts) they attract, and
  • the "hottest" stories — those with the widest independent-source coverage.

It is a snapshot of the current build (not a historical time-series yet), so the
numbers answer "what is big right now", which is exactly what a news exchange board
should show.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import StoryStatus
from app.models.story import Story, StoryArticle
from app.models.taxonomy import StoryTopic, Topic


def compute_trends(db: Session, *, top_topics: int = 12, top_stories: int = 8) -> dict:
    stories = db.execute(
        select(Story)
        .where(Story.status == StoryStatus.published)
        .options(
            selectinload(Story.topic_links).selectinload(StoryTopic.topic),
            selectinload(Story.article_links).selectinload(StoryArticle.article),
        )
    ).scalars().unique().all()

    topic_stats: dict[str, dict] = {}
    cat_counts: dict[str, int] = {}
    for s in stories:
        cov = s.source_count or 0
        cat = getattr(s.category, "value", None) or str(s.category or "")
        if cat:
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
        for tl in s.topic_links:
            t = tl.topic
            if not t:
                continue
            st = topic_stats.setdefault(t.slug, {
                "slug": t.slug, "name_fa": t.name_fa, "name_en": t.name_en,
                "story_count": 0, "coverage": 0,
            })
            st["story_count"] += 1
            st["coverage"] += cov

    topics = list(topic_stats.values())
    # score = stories carried (weighted) + total independent-source coverage
    for t in topics:
        t["score"] = round(t["story_count"] * 2 + t["coverage"], 1)
    topics.sort(key=lambda t: (t["score"], t["story_count"]), reverse=True)
    topics = topics[:top_topics]
    max_score = max((t["score"] for t in topics), default=1) or 1
    for t in topics:
        t["pct"] = round(t["score"] / max_score * 100)

    hottest = sorted(
        stories, key=lambda s: (s.source_count or 0, s.importance_score or 0), reverse=True
    )[:top_stories]
    hot = [
        {
            "id": s.id,
            "headline_fa": s.headline_fa,
            "source_count": s.source_count or 0,
            "category": getattr(s.category, "value", None) or str(s.category or ""),
        }
        for s in hottest
    ]

    cats = sorted(
        ({"category": k, "count": v} for k, v in cat_counts.items()),
        key=lambda c: c["count"], reverse=True,
    )
    return {"topics": topics, "hottest": hot, "categories": cats,
            "story_total": len(stories)}
