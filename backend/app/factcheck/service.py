"""Factnameh (فکت‌نامه) integration.

Factnameh is an independent Persian fact-checking outlet and a Meta third-party
fact-checking partner. We do TWO copyright-safe things with its public Atom feed:

  1) surface its latest fact-checks as their own section (title + short summary +
     link back to Factnameh — never the full text), and
  2) best-effort match a fact-check to one of our stories by keyword overlap, so
     a matching story can show a "راستی‌آزمایی‌شده در فکت‌نامه" badge + link.

This is HUMAN, professional fact-checking — kept clearly separate from our own
automated credibility signal.
"""
from __future__ import annotations

import re
import time

import feedparser
import httpx

from app.core.logging import get_logger

logger = get_logger("factcheck")

FEED_URL = "https://factnameh.com/fa/feed"

# Persian/Arabic + latin word characters; everything else is a separator.
_WORD_RE = re.compile(r"[0-9A-Za-z؀-ۿ]+")

# Very common Persian words that carry no matching signal.
_STOP = {
    "و", "در", "به", "از", "که", "را", "با", "این", "آن", "است", "بر", "های",
    "ها", "یک", "برای", "تا", "هم", "یا", "بود", "شد", "می", "کرد", "کند",
    "خبر", "گزارش", "درباره", "دربارهٔ", "روی", "چه", "چند", "شده", "کردن",
}


def _tokens(text: str | None) -> set[str]:
    if not text:
        return set()
    return {
        w for w in _WORD_RE.findall(text.lower())
        if len(w) >= 3 and w not in _STOP
    }


def fetch_factchecks(limit: int = 12, timeout: float = 20.0) -> list[dict]:
    """Latest Factnameh fact-checks: [{title, summary, url, published}]. Never raises."""
    try:
        resp = httpx.get(FEED_URL, timeout=timeout,
                         headers={"user-agent": "JanKalam/1.0 (+news aggregator)"})
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("could not fetch Factnameh feed: %s", exc)
        return []

    parsed = feedparser.parse(resp.content)
    out: list[dict] = []
    for e in parsed.entries[:limit]:
        summary = re.sub(r"<[^>]+>", "", getattr(e, "summary", "") or "").strip()
        out.append({
            "title": (getattr(e, "title", "") or "").strip(),
            "summary": summary[:280],
            "url": getattr(e, "link", "") or "",
            "published": getattr(e, "published", "") or getattr(e, "updated", "") or "",
        })
    logger.info("fetched %d Factnameh fact-checks", len(out))
    return out


def match_story(story_texts: list[str | None], factchecks: list[dict],
                min_overlap: int = 3) -> dict | None:
    """Return the best-matching fact-check for a story, or None.

    Matching is deliberately conservative (keyword-overlap threshold) — Factnameh
    checks specific claims, so most stories will NOT match, and that is correct.
    """
    story_tok = set()
    for t in story_texts:
        story_tok |= _tokens(t)
    if len(story_tok) < min_overlap:
        return None

    best, best_n = None, 0
    for fc in factchecks:
        n = len(story_tok & _tokens(fc.get("title")))
        if n > best_n:
            best, best_n = fc, n
    if best is not None and best_n >= min_overlap:
        return {"title": best["title"], "url": best["url"], "overlap": best_n}
    return None
