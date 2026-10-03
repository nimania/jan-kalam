"""جان‌کلام چهره‌ها — profile pictures.

Downloads each figure's Telegram channel avatar during the build (GitHub Actions,
outside Iran) and caches the bytes in the build DB so they aren't re-fetched every
15 minutes. At export time the bytes are written into the static site, so avatars
load for everyone — including inside Iran, where t.me/telesco.pe are filtered.

Fully best-effort: any failure just means that figure falls back to initials.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.figures import FIGURES
from app.models.figure_asset import FigureAsset

logger = get_logger("figures.assets")

_OG_RE = re.compile(r'<meta property="og:image" content="([^"]+)"', re.IGNORECASE)
REFRESH_DAYS = 7
_TIMEOUT = 20.0
_MAX_BYTES = 600_000


def _fetch_avatar(handle: str) -> tuple[bytes, str] | None:
    """Return (jpeg_bytes, ext) for a channel avatar, or None."""
    headers = {"User-Agent": settings.ingest_user_agent}
    page = httpx.get(f"https://t.me/s/{handle}", headers=headers,
                     timeout=_TIMEOUT, follow_redirects=True)
    page.raise_for_status()
    m = _OG_RE.search(page.text)
    if not m:
        return None
    img_url = m.group(1).replace("&amp;", "&")
    img = httpx.get(img_url, headers=headers, timeout=_TIMEOUT, follow_redirects=True)
    img.raise_for_status()
    data = img.content
    if not data or len(data) > _MAX_BYTES:
        return None
    ext = "png" if data[:8] == b"\x89PNG\r\n\x1a\n" else "jpg"
    return data, ext


def refresh_avatars(db, *, now: datetime | None = None, fetcher=_fetch_avatar) -> dict:
    """Download avatars that are missing or older than REFRESH_DAYS. Best-effort."""
    now = now or datetime.now(timezone.utc)
    have = {a.handle: a for a in db.query(FigureAsset).all()}
    fresh = now - timedelta(days=REFRESH_DAYS)
    got = failed = skipped = 0
    for f in FIGURES:
        a = have.get(f.handle)
        if a is not None:
            ft = a.fetched_at if a.fetched_at.tzinfo else a.fetched_at.replace(tzinfo=timezone.utc)
            if ft >= fresh:
                skipped += 1
                continue
        try:
            res = fetcher(f.handle)
        except Exception as exc:  # network / HTTP — never break the build
            logger.warning("avatar fetch failed for %s: %s", f.handle, exc)
            failed += 1
            continue
        if not res:
            failed += 1
            continue
        data, ext = res
        if a is None:
            db.add(FigureAsset(handle=f.handle, ext=ext, data=data, fetched_at=now))
        else:
            a.ext, a.data, a.fetched_at = ext, data, now
        got += 1
    db.commit()
    summary = {"downloaded": got, "cached": skipped, "failed": failed}
    logger.info("avatars: %s", summary)
    return summary


def avatar_paths(db) -> dict[str, str]:
    """Return the stable self-hosted paths for all cached figure assets."""
    external = {f.handle for f in FIGURES if f.external}\n    return {a.handle: f"figures/{a.handle}.{a.ext}" for a in db.query(FigureAsset).all() if a.handle not in external}


def write_avatars(db, out_dir: str) -> dict[str, str]:
    """Write cached avatars into <out_dir>/figures/ and return {handle: rel_path}."""
    dest = os.path.join(out_dir, "figures")
    os.makedirs(dest, exist_ok=True)
    paths: dict[str, str] = {}
    for a in db.query(FigureAsset).all():
        fname = f"{a.handle}.{a.ext}"
        with open(os.path.join(dest, fname), "wb") as fh:
            fh.write(a.data)
        paths[a.handle] = f"figures/{fname}"
    return paths


def export_avatars(db, out_dir: str, *, now: datetime | None = None) -> dict[str, str]:
    """Refresh (best-effort) then write. Returns {handle: rel_path}."""
    try:
        refresh_avatars(db, now=now)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("avatar refresh skipped: %s", exc)
    try:
        return write_avatars(db, out_dir)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("avatar write skipped: %s", exc)
        return {}
