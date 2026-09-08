"""Helpers to turn raw feed entries into clean, normalized fields."""
from __future__ import annotations

import calendar
import hashlib
import re
from datetime import datetime, timezone

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def strip_html(text: str | None) -> str | None:
    if not text:
        return text
    return _WS_RE.sub(" ", _TAG_RE.sub(" ", text)).strip()


def normalize_title(title: str) -> str:
    """Lowercase, collapse whitespace — used for clustering & hashing."""
    return _WS_RE.sub(" ", title.strip()).lower()


def content_hash(source_name: str, title: str, url: str) -> str:
    """Stable fingerprint for exact-duplicate detection."""
    basis = f"{source_name}::{normalize_title(title)}::{url.strip()}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def struct_to_datetime(struct) -> datetime | None:
    """feedparser gives a time.struct_time in UTC; convert to aware datetime."""
    if not struct:
        return None
    try:
        return datetime.fromtimestamp(calendar.timegm(struct), tz=timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None
