"""Minimal internal admin/QC API (§30). Not for end users; no auth in MVP —
gate behind network/infra before any real deployment (documented in README)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.pipeline import synthesize_drafts, synthesize_story
from app.clustering.service import cluster_articles
from app.db.session import get_db
from app.ingestion.service import ingest_all, ingest_source
from app.models.usage_log import UsageLog
from app.ranking.service import rank_stories
from app.models.enums import StoryStatus
from app.models.ingestion_log import IngestionLog
from app.models.source import Source
from app.models.story import Story
from app.repositories import sources as source_repo
from app.schemas.source import SourceCreate, SourceOut, SourceUpdate

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/sources", response_model=list[SourceOut])
def admin_list_sources(db: Session = Depends(get_db)) -> list[SourceOut]:
    return [SourceOut.model_validate(s) for s in source_repo.list_all(db)]


@router.post("/sources", response_model=SourceOut, status_code=201)
def admin_create_source(payload: SourceCreate, db: Session = Depends(get_db)) -> SourceOut:
    if source_repo.get_by_name(db, payload.name):
        raise HTTPException(status_code=409, detail="source_name_exists")
    source = Source(**payload.model_dump())
    return SourceOut.model_validate(source_repo.create(db, source))


@router.patch("/sources/{source_id}", response_model=SourceOut)
def admin_update_source(
    source_id: str, payload: SourceUpdate, db: Session = Depends(get_db)
) -> SourceOut:
    source = source_repo.get(db, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="source_not_found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(source, field, value)
    db.commit()
    db.refresh(source)
    return SourceOut.model_validate(source)


@router.get("/stories")
def admin_list_stories(db: Session = Depends(get_db)) -> list[dict]:
    """All stories regardless of status, for cluster/AI-output inspection."""
    rows = db.execute(select(Story).order_by(Story.created_at.desc())).scalars().all()
    return [
        {
            "id": s.id,
            "status": s.status.value,
            "category": s.category.value if s.category else None,
            "headline_fa": s.headline_fa,
            "importance_score": s.importance_score,
            "source_count": s.source_count,
            "article_count": len(s.article_links),
        }
        for s in rows
    ]


@router.post("/stories/{story_id}/flag")
def admin_flag_story(story_id: str, db: Session = Depends(get_db)) -> dict:
    story = db.get(Story, story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="story_not_found")
    story.status = StoryStatus.flagged
    db.commit()
    return {"id": story.id, "status": story.status.value}


@router.post("/ingest")
def admin_ingest_all(db: Session = Depends(get_db)) -> dict:
    """Trigger an ingestion pass over all enabled sources (§19)."""
    results = ingest_all(db)
    return {
        "sources": len(results),
        "new": sum(r.new for r in results),
        "duplicates": sum(r.duplicates for r in results),
        "errors": sum(r.errors for r in results),
        "detail": [
            {"source": r.source_name, "status": r.status, "new": r.new,
             "duplicates": r.duplicates, "errors": r.errors, "message": r.message}
            for r in results
        ],
    }


@router.post("/sources/{source_id}/ingest")
def admin_ingest_source(source_id: str, db: Session = Depends(get_db)) -> dict:
    source = source_repo.get(db, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="source_not_found")
    r = ingest_source(db, source)
    return {
        "source": r.source_name, "status": r.status, "fetched": r.fetched,
        "new": r.new, "duplicates": r.duplicates, "errors": r.errors, "message": r.message,
    }


@router.post("/cluster")
def admin_cluster(db: Session = Depends(get_db)) -> dict:
    """Group unclustered articles into stories (Phase 3)."""
    return cluster_articles(db)


@router.post("/rank")
def admin_rank(db: Session = Depends(get_db)) -> dict:
    """Recompute importance / Iran relevance / category for all stories."""
    return rank_stories(db)


@router.get("/ingestion-logs")
def admin_ingestion_logs(limit: int = 50, db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(
        select(IngestionLog).order_by(IngestionLog.started_at.desc()).limit(limit)
    ).scalars().all()
    return [
        {
            "id": r.id, "source_name": r.source_name, "status": r.status,
            "fetched": r.fetched_count, "new": r.new_count,
            "duplicates": r.duplicate_count, "errors": r.error_count,
            "message": r.message,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        }
        for r in rows
    ]


@router.post("/synthesize")
def admin_synthesize_drafts(limit: int = 20, db: Session = Depends(get_db)) -> dict:
    """Generate the Persian Jan Kalam for draft (clustered) stories and publish
    them. Uses the mock provider unless an AI key is configured."""
    return synthesize_drafts(db, limit=limit)


@router.post("/stories/{story_id}/synthesize")
def admin_synthesize_story(story_id: str, db: Session = Depends(get_db)) -> dict:
    story = db.get(Story, story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="story_not_found")
    return synthesize_story(db, story)


@router.post("/stories/{story_id}/regenerate", status_code=202)
def admin_regenerate_story(story_id: str, db: Session = Depends(get_db)) -> dict:
    """Explicitly re-run synthesis for one story. AI output is cached and never
    regenerated on read — only here, on demand."""
    story = db.get(Story, story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="story_not_found")
    return synthesize_story(db, story)


@router.get("/usage-logs")
def admin_usage_logs(limit: int = 50, db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(
        select(UsageLog).order_by(UsageLog.created_at.desc()).limit(limit)
    ).scalars().all()
    return [
        {
            "id": r.id, "story_id": r.story_id, "stage": r.stage,
            "provider": r.provider, "model": r.model,
            "prompt_tokens": r.prompt_tokens, "completion_tokens": r.completion_tokens,
            "cost_estimate": r.cost_estimate, "latency_ms": r.latency_ms,
            "status": r.status,
        }
        for r in rows
    ]
