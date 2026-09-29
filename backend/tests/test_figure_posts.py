"""جان‌کلام چهره‌ها — stage 2: classifying commentator posts."""
from datetime import datetime, timezone

from app.ai.providers.base import ProviderResult
from app.figure_posts import MAX_PER_RUN, classify_figure_posts
from app.ingestion.service import ingest_source
from app.models.figure_post import FigurePost
from app.models.usage_log import UsageLog
from tests.test_telegram import PAGE, _figure_source

NOW = datetime(2026, 9, 29, 6, 0, tzinfo=timezone.utc)


class FakeProvider:
    name = "fake"

    def __init__(self, reply=None, fail=False):
        self.calls = []
        self.reply = reply
        self.fail = fail

    def generate(self, *, system, user, context):
        self.calls.append(user)
        if self.fail:
            raise RuntimeError("boom")
        if self.reply is not None:
            return ProviderResult(data=self.reply, model="fake-1")
        # label post 1 as analysis, post 2 as chatter
        return ProviderResult(model="fake-1", data={"posts": [
            {"id": "1", "kind": "analysis", "topic_fa": "مذاکرات ایران و آمریکا",
             "summary_fa": "به باور او طرف ایرانی فعلاً وارد مذاکرهٔ هسته‌ای نمی‌شود.",
             "relayed_from": None, "confidence": 0.8},
            {"id": "2", "kind": "chatter", "topic_fa": "", "summary_fa": "",
             "relayed_from": "", "confidence": 0.7},
        ]})


class MockLike:
    name = "mock"

    def generate(self, **kw):  # pragma: no cover - must not be called
        raise AssertionError("mock must be skipped")


def _setup(db):
    src = _figure_source(db)
    ingest_source(db, src, raw_content=PAGE)  # 3 posts; post 102 is forwarded
    return src


def test_forwarded_is_relay_without_ai(db):
    _setup(db)
    p = FakeProvider()
    s = classify_figure_posts(db, provider=p, now=NOW)
    assert s["relay_rule"] == 1
    relay = db.query(FigurePost).filter_by(kind="relay").one()
    assert relay.relayed_from == "خبرگزاری نمونه"
    assert relay.shown is False
    # only the 2 non-forwarded posts went to the AI, in ONE call
    assert len(p.calls) == 1
    assert "خبرگزاری نمونه" not in p.calls[0]


def test_ai_labels_are_stored_and_only_views_are_shown(db):
    _setup(db)
    s = classify_figure_posts(db, provider=FakeProvider(), now=NOW)
    assert s["ai_labeled"] == 2
    shown = db.query(FigurePost).filter_by(shown=True).all()
    assert len(shown) == 1 and shown[0].kind == "analysis"
    assert shown[0].summary_fa.startswith("به باور او")
    assert db.query(UsageLog).filter_by(stage="figures", status="ok").count() == 1


def test_classified_once(db):
    _setup(db)
    classify_figure_posts(db, provider=FakeProvider(), now=NOW)
    p = FakeProvider()
    s = classify_figure_posts(db, provider=p, now=NOW)
    assert s["pending"] == 0 and p.calls == []
    assert db.query(FigurePost).count() == 3


def test_no_ai_key_stores_no_fake_labels(db):
    _setup(db)
    s = classify_figure_posts(db, provider=MockLike(), now=NOW)
    assert s["skipped"] == "no_ai_key"
    assert db.query(FigurePost).filter(FigurePost.kind != "relay").count() == 0


def test_bad_ai_output_is_rejected_and_retried_later(db):
    _setup(db)
    bad = FakeProvider(reply={"posts": [{"id": "1", "kind": "opinion!!"}]})
    s = classify_figure_posts(db, provider=bad, now=NOW)
    assert s["failed_batches"] == 1
    assert db.query(UsageLog).filter_by(status="validation_error").count() == 1
    # the two posts stay pending for the next build
    assert classify_figure_posts(db, provider=FakeProvider(), now=NOW)["ai_labeled"] == 2


def test_provider_error_does_not_raise(db):
    _setup(db)
    s = classify_figure_posts(db, provider=FakeProvider(fail=True), now=NOW)
    assert s["failed_batches"] == 1


def test_analysis_without_summary_is_hidden(db):
    _setup(db)
    reply = {"posts": [{"id": "1", "kind": "analysis", "summary_fa": ""},
                       {"id": "2", "kind": "promo"}]}
    classify_figure_posts(db, provider=FakeProvider(reply=reply), now=NOW)
    assert db.query(FigurePost).filter_by(shown=True).count() == 0


def test_old_posts_are_skipped(db):
    _setup(db)
    later = datetime(2026, 10, 10, tzinfo=timezone.utc)
    assert classify_figure_posts(db, provider=FakeProvider(), now=later)["pending"] == 0


def test_run_cap():
    assert MAX_PER_RUN <= 60


# --- stage 3: export -----------------------------------------------------------
from app.figure_posts import figures_index, match_story, recent_shown_posts  # noqa: E402
from app.figures import FIGURES  # noqa: E402
from app.models.enums import FeedType  # noqa: E402
from app.models.source import Source  # noqa: E402
from app.figures import FIGURE_REGION  # noqa: E402


def _real_figure_setup(db):
    """Same fixture page, but under a real figure's channel."""
    f = FIGURES[0]
    src = Source(name="چهره: " + f.name_fa, homepage_url=f"https://t.me/{f.handle}",
                 feed_url=f"https://t.me/s/{f.handle}", feed_type=FeedType.telegram,
                 region=FIGURE_REGION, language="fa")
    db.add(src)
    db.commit()
    ingest_source(db, src, raw_content=PAGE.replace("testfig", f.handle))
    classify_figure_posts(db, provider=FakeProvider(), now=NOW)
    return f


def test_recent_shown_posts_and_index(db):
    f = _real_figure_setup(db)
    posts = recent_shown_posts(db, now=NOW)
    assert len(posts) == 1 and posts[0]["handle"] == f.handle
    assert posts[0]["url"].startswith(f"https://t.me/{f.handle}/")
    idx = figures_index(posts)
    assert len(idx["figures"]) == len(FIGURES)          # every figure listed
    me = next(x for x in idx["figures"] if x["handle"] == f.handle)
    assert me["count"] == 1 and "_tokens" not in me["posts"][0]


def test_match_story_same_topic_only(db):
    _real_figure_setup(db)
    posts = recent_shown_posts(db, now=NOW)
    t = datetime(2026, 9, 28, 20, tzinfo=timezone.utc)
    on_topic = ["مذاکرات هسته‌ای ایران و آمریکا بر سر تنگه هرمز",
                "طرف ایرانی دربارهٔ مذاکره هسته‌ای و پایان جنگ با آمریکا گفت‌وگو می‌کند."]
    hit = match_story(on_topic, t, posts)
    assert len(hit) == 1 and hit[0]["kind"] == "analysis"
    off_topic = ["قیمت طلا و سکه در بازار تهران", "نرخ سکه امروز افزایش یافت."]
    assert match_story(off_topic, t, posts) == []
    # too far in time → no match
    assert match_story(on_topic, datetime(2026, 10, 5, tzinfo=timezone.utc), posts) == []
