"""Parse RSS / Atom / JSON-Feed content into NormalizedItem objects.

Parsing is pure (no network), so it is fully unit-testable with fixtures.
Per-source usage rules decide whether full content / images are retained —
the copyright policy is enforced here, not bolted on later.
"""
from __future__ import annotations

import json

import feedparser

from app.ingestion.normalize import strip_html, struct_to_datetime
from app.ingestion.schemas import NormalizedItem
from app.models.source import Source


def _image_from_entry(entry) -> str | None:
    media = entry.get("media_content") or entry.get("media_thumbnail")
    if media and isinstance(media, list) and media[0].get("url"):
        return media[0]["url"]
    for enc in entry.get("enclosures", []) or []:
        if str(enc.get("type", "")).startswith("image"):
            return enc.get("href") or enc.get("url")
    return None


def _full_content(entry) -> str | None:
    content = entry.get("content")
    if content and isinstance(content, list) and content[0].get("value"):
        return strip_html(content[0]["value"])
    return None


def parse_rss_atom(raw: str | bytes, source: Source) -> list[NormalizedItem]:
    parsed = feedparser.parse(raw)
    items: list[NormalizedItem] = []
    for entry in parsed.entries:
        title = (entry.get("title") or "").strip()
        link = (entry.get("link") or "").strip()
        if not title or not link:
            continue  # unusable entry
        items.append(
            NormalizedItem(
                title=title,
                article_url=link,
                description=strip_html(entry.get("summary") or entry.get("description")),
                published_at=struct_to_datetime(
                    entry.get("published_parsed") or entry.get("updated_parsed")
                ),
                author=entry.get("author"),
                language=parsed.feed.get("language") or source.language,
                image_url=_image_from_entry(entry) if source.allow_image else None,
                raw_content=_full_content(entry) if source.allow_full_content else None,
            )
        )
    return items


def parse_json_feed(raw: str | bytes, source: Source) -> list[NormalizedItem]:
    """Minimal JSON Feed (jsonfeed.org) support."""
    data = json.loads(raw)
    items: list[NormalizedItem] = []
    for it in data.get("items", []):
        title = (it.get("title") or "").strip()
        url = (it.get("url") or it.get("id") or "").strip()
        if not title or not url:
            continue
        published = it.get("date_published")
        published_at = None
        if published:
            from datetime import datetime

            try:
                published_at = datetime.fromisoformat(published.replace("Z", "+00:00"))
            except ValueError:
                published_at = None
        author = None
        if isinstance(it.get("author"), dict):
            author = it["author"].get("name")
        items.append(
            NormalizedItem(
                title=title,
                article_url=url,
                description=strip_html(it.get("summary") or it.get("content_text")),
                published_at=published_at,
                author=author,
                language=source.language,
                image_url=it.get("image") if source.allow_image else None,
                raw_content=(
                    strip_html(it.get("content_html")) if source.allow_full_content else None
                ),
            )
        )
    return items


def parse_feed(raw: str | bytes, source: Source) -> list[NormalizedItem]:
    """Dispatch by the source's declared feed type."""
    if source.feed_type.value == "json":
        return parse_json_feed(raw, source)
    return parse_rss_atom(raw, source)
