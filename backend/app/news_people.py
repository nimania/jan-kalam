"""Merge attributed statements from news articles into the Figures product layer."""
from __future__ import annotations

import hashlib
import re
from urllib.parse import quote

import httpx
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.figures import FIGURES
from app.models.news_person_statement import NewsPersonStatement

_BY_NAME = {}
for _f in FIGURES:
    _BY_NAME[_f.name_fa.replace("‌", " ").strip()] = _f
    for _alias in getattr(_f, "aliases", ()):
        _BY_NAME[_alias.replace("‌", " ").strip()] = _f

# Editorial hard block: never create a person/profile record for these names.
# Matching is normalized and also covers names containing these tokens.
_PROFILE_BLOCK_EXACT = {"خمینی", "خامنه‌ای", "خامنه ای", "سید علی خامنه‌ای", "سید علی خامنه ای",
                        "سید مجتبی خامنه‌ای", "سید مجتبی خامنه ای", "پهلوی"}
_PROFILE_BLOCK_TOKENS = ("خمینی", "خامنه", "پهلوی")


def _norm_name(s: str) -> str:
    return " ".join((s or "").replace("‌", " ").split())


def _profile_blocked(name: str) -> bool:
    n = _norm_name(name)
    return n in _PROFILE_BLOCK_EXACT or any(token in n for token in _PROFILE_BLOCK_TOKENS)


# Generic titles are not people. If the model could not supply a real personal
# name, the item must never become a profile (or even survive export).
_ROLE_PREFIX_RE = re.compile(r"^(?:(?:یک|یکی از)\\s+)?(?:رئیس|رییس|معاون|مدیر|مسئول|سخنگو|وزیر|استاندار|فرماندار|نماینده|عضو|دبیر|مشاور|کارشناس|مقام|منبع)\\b")
_ORG_ONLY_RE = re.compile(r"(?:سازمان|وزارت|اداره|نهاد|شرکت|بانک|دانشگاه|کمیسیون|شورا|ستاد|دفتر|مرکز|خبرگزاری)")


def is_named_person_name(name: str) -> bool:
    """True only for a plausible explicit personal name, never a bare job title."""
    n = _norm_name(name)
    if not n or _profile_blocked(n) or _ROLE_PREFIX_RE.search(n):
        return False
    words = [w for w in n.split() if len(w) > 1]
    if len(words) < 2:
        return False
    if _ORG_ONLY_RE.search(n) and any(w in n for w in ("رئیس", "رییس", "مدیر", "مسئول", "سخنگو")):
        return False
    return True


def _public_avatar(name: str) -> str | None:
    """Best-effort exact Persian-Wikipedia portrait URL for news-only people."""
    try:
        r = httpx.get(
            "https://fa.wikipedia.org/api/rest_v1/page/summary/" + quote(name, safe=""),
            headers={"User-Agent": "JanKalam/1.0 (public profile thumbnails)"},
            timeout=8.0,
            follow_redirects=True,
        )
        if r.status_code != 200:
            return None
        d = r.json()
        if d.get("type") == "disambiguation":
            return None
        return (d.get("thumbnail") or {}).get("source")
    except Exception:
        return None


def _quote_handle(name: str) -> str:
    return "news-" + hashlib.sha1(_norm_name(name).encode("utf-8")).hexdigest()[:12]


def merge_news_people(index: dict, db: Session, *, now: datetime | None = None,
                      days: int = 7, per_figure: int = 15,
                      avatars: dict[str, str] | None = None) -> dict:
    """Add evidence-backed news statements to figures.json.

    Existing curated figures are merged by normalized Persian name. New people get
    stable synthetic handles. A one-off person has a profile/timeline item but is
    excluded from the main directory until seen in >=2 distinct news sources.
    """
    now = now or datetime.now(timezone.utc)
    avatars = avatars or {}
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
        if not is_named_person_name(name):
            continue
        curated = _BY_NAME.get(name)
        handle = curated.handle if curated else _quote_handle(name)
        source_count = len({x.source_name for x in items})
        if handle not in by_handle:
            newest_role = next((x.role_fa for x in items if x.role_fa), "") or "چهرهٔ حاضر در خبر"
            f = {
                "handle": handle, "name_fa": items[0].person_name_fa,
                "role_fa": newest_role, "field": "news", "field_fa": "گفته‌ها در خبر",
                "gender": "", "channel_url": None,
                "avatar": avatars.get(handle) or (None if curated else _public_avatar(name)), "social": [],
                "count": 0, "posts": [], "directory": source_count >= 2,
                "news_source_count": source_count,
            }
            figures.append(f)
            by_handle[handle] = f
        f = by_handle[handle]
        if curated and avatars.get(handle):
            f["avatar"] = avatars[handle]
        f["directory"] = True if curated else source_count >= 2
        f["news_source_count"] = source_count
        existing_ids = {str(p.get("id")) for p in f.get("posts", [])}
        news_posts = []
        for x in items:
            pid = "news:" + str(x.id)
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

    # Cross-link statements conservatively when the text explicitly names another
    # indexed person. We call these "related exchanges", not a verified reply,
    # unless the source text itself contains reply/response language.
    all_people = [x for x in figures if not _profile_blocked(x.get("name_fa", ""))]
    reply_words = ("پاسخ", "جواب", "واکنش", "در واکنش", "خطاب به")
    for person in all_people:
        for post in person.get("posts", []):
            text = _norm_name(post.get("summary_fa", ""))
            rel = []
            for other in all_people:
                if other.get("handle") == person.get("handle"):
                    continue
                other_name = _norm_name(other.get("name_fa", ""))
                if other_name and other_name in text:
                    rel.append({
                        "handle": other.get("handle"),
                        "name_fa": other.get("name_fa"),
                        "relation": "response" if any(w in text for w in reply_words) else "mentions",
                    })
            if rel:
                post["related_people"] = rel[:6]

    return index
