"""Business logic: assemble API story representations from ORM objects,
preserving the fact / source-view / synthesis / uncertainty separation."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.enums import Category, StatementKind
from app.models.story import Story
from app.repositories import stories as repo
from app.schemas.story import (
    SourceRef,
    SourceViewOut,
    StoryCard,
    StoryDetail,
    StoryFeed,
    TopicRef,
)


def _source_names(story: Story) -> list[str]:
    names: list[str] = []
    if story.source_views:
        names = [sv.source_name for sv in story.source_views]
    else:
        names = [link.article.source_name for link in story.article_links if link.article]
    # de-duplicate, preserve order
    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def to_card(story: Story) -> StoryCard:
    return StoryCard(
        id=story.id,
        headline_fa=story.headline_fa,
        summary_fa=story.summary_fa,
        category=story.category,
        status=story.status,
        iran_relevance=story.iran_relevance,
        importance_score=story.importance_score,
        source_count=story.source_count or len(_source_names(story)),
        published_at=story.published_at,
        source_names=_source_names(story),
    )


def _by_kind(story: Story, kind: StatementKind) -> list[str]:
    return [s.text_fa for s in story.statements if s.kind == kind]


def to_detail(story: Story) -> StoryDetail:
    source_views = [
        SourceViewOut(
            id=sv.id,
            source_name=sv.source_name,
            original_headline=sv.original_headline,
            article_url=sv.article_url,
            published_at=sv.published_at,
            viewpoint_fa=sv.viewpoint_fa,
        )
        for sv in story.source_views
    ]
    sources = [
        SourceRef(
            source_name=sv.source_name,
            original_headline=sv.original_headline,
            article_url=sv.article_url,
            published_at=sv.published_at,
        )
        for sv in story.source_views
    ]
    # Fall back to article links for citations if no source_views yet.
    if not sources:
        for link in story.article_links:
            a = link.article
            if a:
                sources.append(
                    SourceRef(
                        source_name=a.source_name,
                        original_headline=a.title,
                        article_url=a.article_url,
                        published_at=a.published_at,
                    )
                )
    topics = [
        TopicRef(id=tl.topic.id, slug=tl.topic.slug, name_fa=tl.topic.name_fa)
        for tl in story.topic_links
        if tl.topic
    ]

    base = to_card(story)
    return StoryDetail(
        **base.model_dump(),
        what_happened_fa=story.what_happened_fa,
        why_it_matters_fa=story.why_it_matters_fa,
        confidence_score=story.confidence_score,
        facts=_by_kind(story, StatementKind.fact),
        uncertainties=_by_kind(story, StatementKind.uncertainty),
        agreements=_by_kind(story, StatementKind.agreement),
        disagreements=_by_kind(story, StatementKind.disagreement),
        source_views=source_views,
        sources=sources,
        topics=topics,
    )


def get_feed(
    db: Session, *, limit: int, offset: int, category: Category | None
) -> StoryFeed:
    items, total = repo.list_published(
        db, limit=limit, offset=offset, category=category
    )
    return StoryFeed(
        total=total,
        limit=limit,
        offset=offset,
        items=[to_card(s) for s in items],
    )


def get_detail(db: Session, story_id: str) -> StoryDetail | None:
    story = repo.get(db, story_id)
    return to_detail(story) if story else None
