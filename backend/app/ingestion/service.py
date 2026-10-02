"""Ingestion orchestration: fetch → parse → dedup → persist, with a log.

Deduplication is two-layered: a content hash (source+title+url) and the unique
`article_url`. Both are checked before insert so re-running a feed adds nothing
new — the pipeline is idempotent.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.ingestion.feeds import parse_feed
from app.ingestion.fetcher import fetch_url
from app.ingestion.normalize import content_hash
from app.models.article import Article
from app.models.ingestion_log import IngestionLog
from app.models.source import Source
from app.figures import FIGURES, FIGURE_REGION

logger = get_logger("ingestion")

Fetcher = Callable[[str], str]

_URL_RE = re.compile(r"https?://\\S+", re.I)
_WS_RE = re.compile(r"\\s+")


def _mirror_key(text: str | None) -> str:
    """Platform-neutral key for Telegram/Bale mirrors of the same post."""
    s = _URL_RE.sub("", text or "").replace("\u200c", " ")
    return _WS_RE.sub(" ", s).strip().casefold()[:600]


def _figure_bale_handle(source: Source) -> str | None:
    if source.region != FIGURE_REGION:
        return None
    tg = (source.homepage_url or "").rstrip("/").rsplit("/", 1)[-1].lower()
    for f in FIGURES:
        if f.handle.lower() == tg:
            return f.bale
    return None


@dataclass(slots=True)
class IngestResult:
    source_name: str
    status: str
    fetched: int = 0
    new: int = 0
    duplicates: int = 0
    errors: int = 0
    message: str | None = None


def ingest_source(
    db: Session,
    source: Source,
    *,
    raw_content: str | None = None,
    fetcher: Fetcher = fetch_url,
) -> IngestResult:
    """Ingest one source. Pass `raw_content` to skip the network (tests)."""
    started = datetime.now(timezone.utc)
    result = IngestResult(source_name=source.name, status="ok")

    try:
        raw = raw_content if raw_content is not None else fetcher(source.feed_url)
    except Exception as exc:  # network / HTTP error
        logger.warning("fetch failed for %s: %s", source.name, exc)
        result.status = "error"
        result.errors = 1
        result.message = f"fetch_failed: {exc}"
        _write_log(db, source, result, started)
        return result

    try:
        items = parse_feed(raw, source)
    except Exception as exc:  # malformed feed
        logger.warning("parse failed for %s: %s", source.name, exc)
        result.status = "error"
        result.errors = 1
        result.message = f"parse_failed: {exc}"
        _write_log(db, source, result, started)
        return result

    # Figures may have a verified Bale mirror. Telegram stays primary: ingest it
    # first, then append Bale-only posts. A Bale outage never breaks Telegram.
    bale_handle = _figure_bale_handle(source)
    if bale_handle:
        try:
            from app.ingestion.bale import parse_bale_channel
            bale_raw = fetcher(f"https://ble.ir/s/{bale_handle}")
            items.extend(parse_bale_channel(bale_raw, source, bale_handle))
        except Exception as exc:
            logger.warning("Bale mirror failed for %s: %s", source.name, exc)
            result.message = "bale_mirror_failed"

    result.fetched = len(items)
    since = datetime.now(timezone.utc) - timedelta(days=3)
    existing_articles = db.execute(
        select(Article).where(
            Article.source_id == source.id,
            (Article.published_at.is_(None)) | (Article.published_at >= since),
        )
    ).scalars().all()
    mirror_articles = {
        _mirror_key(a.description or a.title): a for a in existing_articles
        if _mirror_key(a.description or a.title)
    }
    mirror_keys = set(mirror_articles)

    for item in items:
        mkey = _mirror_key(item.description or item.title)
        if mkey and mkey in mirror_keys:
            # If Bale was available during an earlier Telegram outage, upgrade
            # the mirrored record to Telegram as soon as Telegram returns.
            prev = mirror_articles.get(mkey)
            if (prev is not None and item.article_url.startswith("https://t.me/")
                    and (prev.article_url or "").startswith("https://ble.ir/")):
                prev.article_url = item.article_url
                prev.title = item.title
                prev.description = item.description
                prev.published_at = item.published_at or prev.published_at
                prev.author = item.author
                if item.image_url and item.image_url.startswith("telegram-media:"):
                    prev.image_url_if_permitted = item.image_url
            result.duplicates += 1
            continue
        h = content_hash(source.name, item.title, item.article_url)
        exists = db.execute(
            select(Article.id).where(
                (Article.hash == h) | (Article.article_url == item.article_url)
            )
        ).first()
        if exists:
            # Existing Telegram figure posts can gain media metadata on a later
            # parse (e.g. after this feature ships) without creating duplicates.
            if item.image_url and item.image_url.startswith("telegram-media:"):
                prev = db.execute(select(Article).where(
                    (Article.hash == h) | (Article.article_url == item.article_url)
                )).scalars().first()
                if prev is not None:
                    prev.image_url_if_permitted = item.image_url
                    db.commit()
            result.duplicates += 1
            continue
        db.add(
            Article(
                source_id=source.id,
                source_name=source.name,
                source_url=source.homepage_url,
                article_url=item.article_url,
                title=item.title,
                description=item.description,
                published_at=item.published_at,
                author=item.author,
                language=item.language or source.language,
                category=source.default_category,
                image_url_if_permitted=item.image_url,
                raw_content_if_permitted=item.raw_content,
                hash=h,
            )
        )
        result.new += 1
        if mkey:
            mirror_keys.add(mkey)
            # Keep the in-batch object so a later Telegram/Bale mirror can be
            # resolved without another query.
            mirror_articles[mkey] = next(
                (a for a in db.new if isinstance(a, Article) and a.article_url == item.article_url),
                mirror_articles.get(mkey),
            )

    db.commit()
    _write_log(db, source, result, started)
    logger.info(
        "ingested %s: fetched=%d new=%d dup=%d",
        source.name, result.fetched, result.new, result.duplicates,
    )
    return result


def ingest_all(db: Session, *, fetcher: Fetcher = fetch_url) -> list[IngestResult]:
    sources = db.execute(
        select(Source).where(Source.enabled.is_(True))
    ).scalars().all()
    return [ingest_source(db, s, fetcher=fetcher) for s in sources]


def _write_log(db: Session, source: Source, r: IngestResult, started: datetime) -> None:
    db.add(
        IngestionLog(
            source_id=source.id,
            source_name=source.name,
            status=r.status,
            fetched_count=r.fetched,
            new_count=r.new,
            duplicate_count=r.duplicates,
            error_count=r.errors,
            message=r.message,
            started_at=started,
            finished_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
