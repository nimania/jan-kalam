"""Parse a public Telegram channel's web preview (https://t.me/s/<handle>).

The preview page needs no login and no API key, and GitHub's servers can reach
it. It shows roughly the latest 20 posts, which is plenty when the build runs
every 15 minutes.

Copyright policy (same as for news feeds): we keep only a short excerpt plus a
link to the original post — never the full text of a long post.

Parsing is pure (no network), so it is unit-testable with a saved page.
"""
from __future__ import annotations

from datetime import datetime

from bs4 import BeautifulSoup

from app.ingestion.normalize import strip_html
from app.ingestion.schemas import NormalizedItem
from app.models.source import Source

TITLE_MAX = 140        # a post has no headline, so we use its opening words
EXCERPT_MAX = 700      # enough context for the AI to classify the post later
FORWARD_PREFIX = "بازنشر از: "   # stored in `author` for forwarded posts


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut + "…"


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_telegram_channel(raw: str | bytes, source: Source) -> list[NormalizedItem]:
    soup = BeautifulSoup(raw, "html.parser")
    items: list[NormalizedItem] = []

    for msg in soup.select("div.tgme_widget_message[data-post]"):
        classes = msg.get("class") or []
        if "service_message" in classes:
            continue  # "channel pinned a message" and similar

        text_el = msg.select_one("div.tgme_widget_message_text")
        if text_el is None:
            continue  # photo/video/voice with no caption — nothing to read
        # Keep line breaks as spaces; strip links/formatting.
        for br in text_el.find_all("br"):
            br.replace_with("\n")
        raw_text = text_el.get_text(" ").strip()
        first_line = next((ln.strip() for ln in raw_text.split("\n") if ln.strip()), "")
        text = strip_html(raw_text) or ""
        if len(text) < 20:
            continue  # "به‌زودی…", a lone emoji, etc.

        post_id = msg["data-post"]                 # "<handle>/<number>"
        url = f"https://t.me/{post_id}"

        time_el = msg.select_one("a.tgme_widget_message_date time[datetime]") or msg.select_one(
            "time[datetime]"
        )
        published = _parse_time(time_el.get("datetime") if time_el else None)

        author = source.name
        fwd = msg.select_one(".tgme_widget_message_forwarded_from_name") or msg.select_one(
            ".tgme_widget_message_forwarded_from"
        )
        if fwd is not None:
            origin = fwd.get_text(" ").replace("Forwarded from", "").strip()
            author = FORWARD_PREFIX + (origin or "نامشخص")

        # Preserve only the fact that Telegram has media; never copy/rehost the
        # media URL. The UI can then use Telegram's official post embed.
        media_type = None
        if msg.select_one("video, .tgme_widget_message_video_player, .tgme_widget_message_video_thumb"):
            media_type = "video"
        elif msg.select_one(".tgme_widget_message_photo_wrap, .tgme_widget_message_photo"):
            media_type = "photo"
        elif msg.select_one(".tgme_widget_message_document, .tgme_widget_message_voice_player, audio"):
            media_type = "media"

        items.append(
            NormalizedItem(
                title=_clip(strip_html(first_line) or text, TITLE_MAX),
                article_url=url,
                description=_clip(text, EXCERPT_MAX),
                published_at=published,
                author=author[:300],
                language=source.language,
                image_url=f"telegram-media:{media_type}" if media_type else None,  # metadata only
                raw_content=None,        # never keep full post text
            )
        )
    return items


def is_forwarded(author: str | None) -> bool:
    return bool(author) and author.startswith(FORWARD_PREFIX)
