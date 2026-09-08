"""Synthesis pipeline: clustered story → validated Persian Jan Kalam → published.

Flow: gather the story's articles → provider.generate → validate against
JanKalamOutput (raw output is never trusted) → persist the four layers →
publish. Every call is logged (tokens / model / cost / latency). AI output is
produced ONCE here and then served from the DB — never regenerated on read.
"""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.ai.prompts import SYSTEM_PROMPT, build_user_prompt
from app.ai.providers import ProviderResult, get_provider
from app.ai.providers.base import Provider
from app.ai.schemas import JanKalamOutput
from app.core.config import settings
from app.core.logging import get_logger
from app.models.enums import IranRelevance, StatementKind, StoryStatus
from app.models.story import SourceView, Statement, Story, StoryArticle
from app.models.usage_log import UsageLog

logger = get_logger("ai.pipeline")


def _cost(r: ProviderResult) -> float:
    return round(
        r.prompt_tokens / 1_000_000 * settings.ai_price_in_per_mtok
        + r.completion_tokens / 1_000_000 * settings.ai_price_out_per_mtok,
        6,
    )


def _log(db: Session, story_id: str, r: ProviderResult | None, status: str,
         message: str | None = None) -> None:
    db.add(UsageLog(
        story_id=story_id, stage="synthesis",
        provider=(getattr(r, "model", "") or "").split("-")[0] or "mock",
        model=getattr(r, "model", "") or "",
        prompt_tokens=getattr(r, "prompt_tokens", 0),
        completion_tokens=getattr(r, "completion_tokens", 0),
        cost_estimate=_cost(r) if r else 0.0,
        latency_ms=getattr(r, "latency_ms", 0),
        status=status, message=message,
    ))
    db.commit()


def _articles_of(story: Story) -> list:
    return [l.article for l in story.article_links if l.article]


def synthesize_story(db: Session, story: Story, *, provider: Provider | None = None) -> dict:
    provider = provider or get_provider()
    articles = _articles_of(story)
    if not articles:
        return {"story_id": story.id, "status": "skipped", "reason": "no_articles"}

    art_dicts = [
        {
            "source_name": a.source_name,
            "title": a.title,
            "description": a.description,
            "published_at": a.published_at.isoformat() if a.published_at else None,
            "article_url": a.article_url,
        }
        for a in articles
    ]
    context = {"articles": art_dicts}

    # 1) call provider
    try:
        result = provider.generate(
            system=SYSTEM_PROMPT, user=build_user_prompt(art_dicts), context=context
        )
    except Exception as exc:  # network / provider error
        logger.warning("provider error on %s: %s", story.id, exc)
        _log(db, story.id, None, "provider_error", str(exc))
        return {"story_id": story.id, "status": "provider_error", "detail": str(exc)}

    # 2) validate — never trust raw model output
    try:
        out = JanKalamOutput.model_validate(result.data)
    except ValidationError as exc:
        logger.warning("validation error on %s: %s", story.id, exc)
        _log(db, story.id, result, "validation_error", str(exc)[:500])
        return {"story_id": story.id, "status": "validation_error"}

    # 3) persist (idempotent: clear prior AI children first)
    _clear_children(db, story.id)
    _apply(db, story, out, articles)
    db.commit()
    _log(db, story.id, result, "ok")

    logger.info("synthesized %s (model=%s)", story.id, result.model)
    return {
        "story_id": story.id, "status": "published", "model": result.model,
        "facts": len(out.facts_fa), "source_views": len(out.source_views),
        "cost_estimate": _cost(result),
    }


def _clear_children(db: Session, story_id: str) -> None:
    for row in db.execute(
        select(Statement).where(Statement.story_id == story_id)
    ).scalars().all():
        db.delete(row)
    for row in db.execute(
        select(SourceView).where(SourceView.story_id == story_id)
    ).scalars().all():
        db.delete(row)
    db.flush()


def _apply(db: Session, story: Story, out: JanKalamOutput, articles: list) -> None:
    story.headline_fa = out.headline_fa
    story.summary_fa = out.summary_fa
    story.what_happened_fa = out.what_happened_fa
    story.why_it_matters_fa = out.why_it_matters_fa
    story.confidence_score = out.confidence
    story.iran_relevance = IranRelevance(out.iran_relevance)
    story.source_count = len({a.source_id for a in articles})
    story.status = StoryStatus.published
    story.published_at = datetime.now(timezone.utc)

    by_name = {a.source_name: a for a in articles}
    for kind, items in (
        (StatementKind.fact, out.facts_fa),
        (StatementKind.uncertainty, out.uncertainties_fa),
        (StatementKind.agreement, out.agreements_fa),
        (StatementKind.disagreement, out.disagreements_fa),
    ):
        for text in items:
            db.add(Statement(story_id=story.id, kind=kind, text_fa=text,
                             confidence=out.confidence))

    for sv in out.source_views:
        a = by_name.get(sv.source_name)
        db.add(SourceView(
            story_id=story.id,
            source_id=a.source_id if a else None,
            source_name=sv.source_name,
            original_headline=a.title if a else None,
            article_url=a.article_url if a else None,
            published_at=a.published_at if a else None,
            viewpoint_fa=sv.viewpoint_fa,
        ))


def synthesize_drafts(db: Session, *, limit: int = 20,
                      provider: Provider | None = None) -> dict:
    provider = provider or get_provider()
    stories = db.execute(
        select(Story)
        .where(Story.status == StoryStatus.draft)
        .options(selectinload(Story.article_links).selectinload(StoryArticle.article))
        .order_by(Story.importance_score.desc())
        .limit(limit)
    ).scalars().unique().all()
    results = [synthesize_story(db, s, provider=provider) for s in stories]
    return {
        "processed": len(results),
        "published": sum(1 for r in results if r.get("status") == "published"),
        "failed": sum(1 for r in results if r.get("status") in
                      ("validation_error", "provider_error")),
    }
