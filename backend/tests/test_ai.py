from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.ai.pipeline import synthesize_drafts, synthesize_story
from app.ai.providers.base import ProviderResult
from app.ai.providers.mock import MockProvider
from app.ai.schemas import JanKalamOutput
from app.models.article import Article
from app.models.enums import IranRelevance, StatementKind, StoryStatus
from app.models.story import SourceView, Statement, Story, StoryArticle
from app.models.usage_log import UsageLog
from tests.conftest import make_source

NOW = datetime.now(timezone.utc)


def _draft_story(db, n=3, iran=True) -> Story:
    story = Story(status=StoryStatus.draft, source_count=n)
    db.add(story)
    db.flush()
    for i in range(n):
        src = make_source(db, name=f"Src{i}")
        title = ("Iran Hormuz clash escalates" if iran else "New phone chip unveiled") + f" {i}"
        a = Article(
            source_id=src.id, source_name=src.name, article_url=f"https://x.test/{i}",
            title=title, description="excerpt", hash=f"h{i}", published_at=NOW,
        )
        db.add(a)
        db.flush()
        db.add(StoryArticle(story_id=story.id, article_id=a.id))
    db.commit()
    return db.get(Story, story.id)


# --- schema/validation ---
def test_mock_output_validates():
    p = MockProvider()
    r = p.generate(system="s", user="u", context={"articles": [
        {"source_name": "Reuters", "title": "Iran Hormuz clash"},
        {"source_name": "BBC", "title": "Iran Hormuz tensions"},
    ]})
    out = JanKalamOutput.model_validate(r.data)   # must not raise
    assert out.iran_relevance in ("high", "medium", "low", "none")
    assert len(out.source_views) == 2


def test_validation_rejects_non_persian_summary():
    with pytest.raises(ValidationError):
        JanKalamOutput(
            headline_fa="x", summary_fa="all english text only",
            what_happened_fa="x", why_it_matters_fa="x", confidence=0.5,
        )


def test_confidence_bounds():
    with pytest.raises(ValidationError):
        JanKalamOutput(
            headline_fa="x", summary_fa="خلاصهٔ فارسی", what_happened_fa="چه",
            why_it_matters_fa="چرا", confidence=1.5,
        )


# --- pipeline ---
def test_synthesize_publishes_and_creates_layers(db):
    story = _draft_story(db, n=3, iran=True)
    res = synthesize_story(db, story, provider=MockProvider())
    assert res["status"] == "published"

    db.refresh(story)
    assert story.status == StoryStatus.published
    assert story.summary_fa and story.published_at is not None
    assert story.iran_relevance in (IranRelevance.high, IranRelevance.medium)
    # facts: one per article (mock); source_views: one per article
    facts = db.query(Statement).filter_by(story_id=story.id, kind=StatementKind.fact).count()
    assert facts == 3
    assert db.query(SourceView).filter_by(story_id=story.id).count() == 3
    # usage logged
    log = db.query(UsageLog).filter_by(story_id=story.id, status="ok").first()
    assert log is not None and log.model == "mock"


def test_synthesize_is_idempotent(db):
    story = _draft_story(db, n=2)
    synthesize_story(db, story, provider=MockProvider())
    synthesize_story(db, story, provider=MockProvider())  # re-run
    # children not duplicated
    assert db.query(SourceView).filter_by(story_id=story.id).count() == 2


def test_published_story_appears_in_feed(client, db):
    story = _draft_story(db, n=2)
    synthesize_story(db, story, provider=MockProvider())
    feed = client.get("/api/v1/stories").json()
    assert any(item["id"] == story.id for item in feed["items"])


def test_provider_error_keeps_story_draft(db):
    class Boom:
        name = "boom"
        def generate(self, *, system, user, context):
            raise RuntimeError("network down")

    story = _draft_story(db, n=2)
    res = synthesize_story(db, story, provider=Boom())
    assert res["status"] == "provider_error"
    db.refresh(story)
    assert story.status == StoryStatus.draft  # not published
    assert db.query(UsageLog).filter_by(status="provider_error").count() == 1


def test_invalid_model_output_is_rejected(db):
    class Bad:
        name = "bad"
        def generate(self, *, system, user, context):
            # summary has no Persian -> must fail validation
            return ProviderResult(data={
                "headline_fa": "x", "summary_fa": "english only",
                "what_happened_fa": "x", "why_it_matters_fa": "x", "confidence": 0.5,
            }, model="bad")

    story = _draft_story(db, n=2)
    res = synthesize_story(db, story, provider=Bad())
    assert res["status"] == "validation_error"
    db.refresh(story)
    assert story.status == StoryStatus.draft
    assert db.query(UsageLog).filter_by(status="validation_error").count() == 1


def test_gemini_response_parsing():
    from app.ai.providers.gemini import GeminiProvider
    # A realistic Gemini response body shape (offline — no network call).
    body = {
        "candidates": [{"content": {"parts": [{"text": '{"headline_fa":"خبر","confidence":0.5}'}]}}],
        "usageMetadata": {"promptTokenCount": 900, "candidatesTokenCount": 1100},
    }
    text = GeminiProvider._extract_text(body)
    data = GeminiProvider._parse_json(text)
    assert data["headline_fa"] == "خبر"
    # tolerant parse of JSON wrapped in prose
    assert GeminiProvider._parse_json('```json\n{"a":1}\n```')["a"] == 1


def test_admin_synthesize_endpoint(client, db):
    _draft_story(db, n=2)
    r = client.post("/api/v1/admin/synthesize")
    assert r.status_code == 200
    assert r.json()["published"] >= 1
