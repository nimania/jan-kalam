"""Network fetch, kept separate from parsing so ingestion is testable offline
(tests inject a fake fetcher or pass raw content directly)."""
from __future__ import annotations

import httpx

from app.core.config import settings

DEFAULT_TIMEOUT = 20.0


def fetch_url(url: str, *, timeout: float = DEFAULT_TIMEOUT) -> str:
    headers = {"User-Agent": settings.ingest_user_agent}
    resp = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
    resp.raise_for_status()
    return resp.text
