"""Parse recent public Bale channel posts from https://ble.ir/s/<handle>.

Bale's public preview is a Next.js app. Recent messages are embedded in React
Server Component payloads (self.__next_f.push). We only read that anonymous
preview and keep the same short excerpt policy as Telegram ingestion.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from app.ingestion.normalize import strip_html
from app.ingestion.schemas import NormalizedItem
from app.models.source import Source

TITLE_MAX = 140
EXCERPT_MAX = 700

_NEXT_RE = re.compile(r'self\.__next_f\.push\(\[1,\s*"((?:[^"\\\\]|\\\\.)*)"\]\)')


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut + "…"


def _balanced_array(text: str, key: str) -> str | None:
    idx = text.find(f'"{key}":[')
    if idx < 0:
        return None
    start = text.index("[", idx)
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def _blob(raw: str | bytes) -> str:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    parts: list[str] = []
    for encoded in _NEXT_RE.findall(raw):
        try:
            parts.append(json.loads('"' + encoded + '"'))
        except json.JSONDecodeError:
            continue
    return "".join(parts)


def _text(msg: dict) -> str:
    inner = msg.get("message") or {}
    doc = inner.get("documentMessage") or {}
    caption = doc.get("caption") or {}
    if caption.get("text"):
        return str(caption["text"])
    txt = inner.get("textMessage") or {}
    return str(txt.get("text") or "")


def _time(ms) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def parse_bale_channel(raw: str | bytes, source: Source, handle: str) -> list[NormalizedItem]:
    blob = _blob(raw)
    arr = _balanced_array(blob, "messages")
    if not arr:
        return []
    try:
        messages = json.loads(arr)
    except json.JSONDecodeError:
        return []

    items: list[NormalizedItem] = []
    seen: set[str] = set()
    for msg in messages:
        text = strip_html(_text(msg)) or ""
        if len(text) < 20:
            continue
        rid = str(msg.get("rid") or "").strip()
        if not rid or rid in seen:
            continue
        seen.add(rid)
        first = next((x.strip() for x in text.splitlines() if x.strip()), text)
        items.append(NormalizedItem(
            title=_clip(first, TITLE_MAX),
            article_url=f"https://ble.ir/{handle}/{rid}",
            description=_clip(text, EXCERPT_MAX),
            published_at=_time(msg.get("date")),
            author=source.name,
            language=source.language,
            image_url=None,
            raw_content=None,
        ))
    return items
