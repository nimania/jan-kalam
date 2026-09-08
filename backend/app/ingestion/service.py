"""Ingestion orchestration: fetch → parse → dedup → persist, with a log.

Deduplication is two-layered: a content hash (source+title+url) and the unique
`article_url`. Both are checked before insert so re-running a feed adds nothing
new — the pipeline is idempotent.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.ingestion.feeds import parse_feed
from app.ingestion.fetcher import fetch_url
from app.ingestion.normalize import content_hash
from app.models.article import Article
from app.models.ingestion_log import IngestionLog
from app.models.source import Source

logger = get_logger("ingestion")

Fetcher = Callable[[str], str]


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

    result.fetched = len(items)
    for item in items:
        h = content_hash(source.name, item.title, item.article_url)
        exists = db.execute(
            select(Article.id).where(
                (Article.hash == h) | (Article.article_url == item.article_url)
            )
        ).first()
        if exists:
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
