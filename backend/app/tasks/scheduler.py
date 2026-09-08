"""Lightweight background ingestion runner (§19).

Intentionally minimal: a plain callable a scheduler (cron, APScheduler, or a
`while True: sleep` loop) can invoke. No Kafka/Celery until genuinely needed.
"""
from __future__ import annotations

from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.ingestion.service import ingest_all

logger = get_logger("scheduler")


def run_ingestion_cycle() -> dict:
    """Run one full ingestion pass over all enabled sources."""
    db = SessionLocal()
    try:
        results = ingest_all(db)
        summary = {
            "sources": len(results),
            "new": sum(r.new for r in results),
            "duplicates": sum(r.duplicates for r in results),
            "errors": sum(r.errors for r in results),
        }
        logger.info("ingestion cycle complete: %s", summary)
        return summary
    finally:
        db.close()


def run_full_cycle() -> dict:
    """The whole pipeline, once: ingest → cluster → rank → synthesize.
    This is what the background worker runs on a schedule in production."""
    from app.ai.pipeline import synthesize_drafts
    from app.clustering.service import cluster_articles
    from app.ranking.service import rank_stories

    db = SessionLocal()
    try:
        ing = ingest_all(db)
        clustered = cluster_articles(db)
        ranked = rank_stories(db)
        synthed = synthesize_drafts(db)
        summary = {
            "ingested_new": sum(r.new for r in ing),
            "clusters_new": clustered.get("new_stories", 0),
            "ranked": ranked.get("ranked", 0),
            "published": synthed.get("published", 0),
        }
        logger.info("full cycle complete: %s", summary)
        return summary
    finally:
        db.close()


if __name__ == "__main__":  # manual: python -m app.tasks.scheduler
    print(run_ingestion_cycle())
