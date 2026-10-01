"""Merge attributed statements from news articles into the Figures product layer."""
from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.figures import FIGURES
from app.models.news_person_statement import NewsPersonStatement

_BY_NAME = {f.name_fa.replace("‌", " ").strip(): f for f in FIGURES}


def _norm_name(s: str) -> str:
    return " ".join((s or "").replace("‌", " ").split())


def _quote_handle(name: str) -> str:
    return "news-" + hashlib.sha1(_norm_name(name).encode("utf-8")).hexdigest()[:12]


def merge_news_people(index: dict, db: Session, *, now: datetime | None = None,
                      days: int = 7, per_figure: int = 15) -> dict:
    """Add evidence-backed news statements to figures.json.

    Existing curated figures are merged by normalized Persian name. New people get
    stable synthetic handles. A one-off person has a profile/timeline item but is
    excluded from the main directory until seen in >=2 distinct news sources.
    """
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    rows = list(db.execute(
        select(NewsPersonStatement)
        .where((NewsPersonStatement.published_at.is_(None)) |
               (NewsPersonStatement.published_at >= since))
        .order_by(NewsPersonStatement.published_at.desc().nullslast())
    ).scalars().all())
    if not rows:
        return index

    figures = index.setdefault("figures", [])
    index.setdefault("fields", {})["news"] = "گفته‌ها در خبر"
    by_handle = {f["handle"]: f for f in figures}
    grouped: dict[str, list[NewsPersonStatement]] = defaultdict(list)
    for row in rows:
        grouped[_norm_name(row.person_name_fa)].append(row)

    for name, items in grouped.items():
        curated = _BY_NAME.get(name)
        handle = curated.handle if curated else _quote_handle(name)
        source_count = len({x.source_name for x in items})
        if handle not in by_handle:
            newest_role = next((x.role_fa for x in items if x.role_fa), "") or "چهرهٔ حاضر در خبر"
            f = {
                "handle": handle, "name_fa": items[0].person_name_fa,
                "role_fa": newest_role, "field": "news", "field_fa": "گفته‌ها در خبر",
                "gender": "", "channel_url": None, "avatar": None, "social": [],
                "count": 0, "posts": [], "directory": source_count >= 2,
                "news_source_count": source_count,
            }
            figures.append(f)
            by_handle[handle] = f
        f = by_handle[handle]
        f["directory"] = True if curated else source_count >= 2
        f["news_source_count"] = source_count
        existing_ids = {str(p.get("id")) for p in f.get("posts", [])}
        news_posts = []
        for x in items:
            pid = "news:" + x.id
            if pid in existing_ids:
                continue
            news_posts.append({
                "id": pid, "handle": handle, "name_fa": f["name_fa"],
                "role_fa": x.role_fa or f.get("role_fa", ""),
                "field": f.get("field", "news"), "avatar": f.get("avatar"),
                "kind": "news_statement",
                "topic_fa": "گفته در خبر",
                "summary_fa": x.statement_fa,
                "url": x.article_url,
                "source_name": x.source_name,
                "direct_quote": bool(x.direct_quote),
                "published_at": x.published_at.isoformat() if x.published_at else None,
            })
        combined = list(f.get("posts", [])) + news_posts
        combined.sort(key=lambda p: str(p.get("published_at") or ""), reverse=True)
        f["posts"] = combined[:per_figure]
        f["count"] = len(combined)

    return index
