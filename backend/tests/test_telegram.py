"""جان‌کلام چهره‌ها — Telegram channel ingestion (stage 1).

The fixture mirrors the markup of a real https://t.me/s/<handle> preview page.
"""
from app.clustering.service import cluster_articles
from app.figures import FIGURE_REGION, FIGURES
from app.ingestion.service import ingest_source
from app.ingestion.telegram import FORWARD_PREFIX, parse_telegram_channel
from app.models.article import Article
from app.models.enums import FeedType
from app.models.source import Source
from app.models.story import StoryArticle
from tests.conftest import make_source

LONG = "تحلیل " * 400

PAGE = f"""<!DOCTYPE html><html><body><section class="tgme_channel_history js-message_history">
<div class="tgme_widget_message_wrap js-widget_message_wrap">
  <div class="tgme_widget_message text_not_supported_wrap js-widget_message" data-post="testfig/101" data-view="x">
    <div class="tgme_widget_message_bubble">
      <div class="tgme_widget_message_author accent_color"><a class="tgme_widget_message_owner_name" href="https://t.me/testfig"><span dir="auto">چهره آزمایشی</span></a></div>
      <div class="tgme_widget_message_text js-message_text" dir="auto"><b>بعید می‌دانم طرف ایرانی فعلاً دربارهٔ هسته‌ای مذاکره کند</b><br/><br/>فقط دربارهٔ تنگه و پایان جنگ گفت‌وگو می‌کند. <a href="https://t.me/testfig">@testfig</a></div>
      <div class="tgme_widget_message_footer compact js-message_footer"><div class="tgme_widget_message_info short js-message_info">
        <span class="tgme_widget_message_views">18.6K</span>
        <span class="copyonclick"><a class="tgme_widget_message_date" href="https://t.me/testfig/101"><time datetime="2026-09-28T19:17:00+00:00" class="time">19:17</time></a></span>
      </div></div>
    </div>
  </div>
</div>
<div class="tgme_widget_message_wrap js-widget_message_wrap">
  <div class="tgme_widget_message js-widget_message" data-post="testfig/102">
    <div class="tgme_widget_message_bubble">
      <div class="tgme_widget_message_forwarded_from accent_color">Forwarded from <a class="tgme_widget_message_forwarded_from_name" href="https://t.me/somenews/5"><span dir="auto">خبرگزاری نمونه</span></a></div>
      <div class="tgme_widget_message_text js-message_text" dir="auto">یک منبع به رویترز: میانجی‌ها امروز یا فردا با دو طرف جداگانه گفتگو خواهند کرد.</div>
      <a class="tgme_widget_message_date" href="https://t.me/testfig/102"><time datetime="2026-09-28T14:26:00+00:00">14:26</time></a>
    </div>
  </div>
</div>
<div class="tgme_widget_message_wrap js-widget_message_wrap">
  <div class="tgme_widget_message js-widget_message" data-post="testfig/103">
    <div class="tgme_widget_message_bubble">
      <a class="tgme_widget_message_video_player" href="https://t.me/testfig/103"></a>
      <a class="tgme_widget_message_date" href="https://t.me/testfig/103"><time datetime="2026-09-28T15:00:00+00:00">15:00</time></a>
    </div>
  </div>
</div>
<div class="tgme_widget_message_wrap js-widget_message_wrap">
  <div class="tgme_widget_message service_message js-widget_message" data-post="testfig/104">
    <div class="tgme_widget_message_text js-message_text">چهره آزمایشی pinned a file and something long enough</div>
  </div>
</div>
<div class="tgme_widget_message_wrap js-widget_message_wrap">
  <div class="tgme_widget_message js-widget_message" data-post="testfig/105">
    <div class="tgme_widget_message_text js-message_text">به‌زودی…</div>
    <a class="tgme_widget_message_date"><time datetime="2026-09-28T16:00:00+00:00">16:00</time></a>
  </div>
</div>
<div class="tgme_widget_message_wrap js-widget_message_wrap">
  <div class="tgme_widget_message js-widget_message" data-post="testfig/106">
    <div class="tgme_widget_message_text js-message_text">{LONG}</div>
    <a class="tgme_widget_message_date"><time datetime="2026-09-28T17:00:00+00:00">17:00</time></a>
  </div>
</div>
</section></body></html>"""


def _figure_source(db) -> Source:
    s = Source(
        name="چهره: آزمایشی",
        homepage_url="https://t.me/testfig",
        feed_url="https://t.me/s/testfig",
        feed_type=FeedType.telegram,
        region=FIGURE_REGION,
        language="fa",
        reliability_score=0.3,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def test_parse_keeps_text_posts_only(db):
    items = parse_telegram_channel(PAGE, _figure_source(db))
    urls = [i.article_url for i in items]
    # media-only (103), service message (104) and too-short (105) are skipped
    assert urls == [
        "https://t.me/testfig/101",
        "https://t.me/testfig/102",
        "https://t.me/testfig/106",
    ]


def test_parse_fields(db):
    first, fwd, long_ = parse_telegram_channel(PAGE, _figure_source(db))
    # Title = the post's opening line only
    assert first.title == "بعید می‌دانم طرف ایرانی فعلاً دربارهٔ هسته‌ای مذاکره کند"
    assert "تنگه" in first.description
    assert first.published_at.isoformat().startswith("2026-09-28T19:17")
    assert first.author == "چهره: آزمایشی"
    # Forwarded posts are marked so later stages treat them as relayed news
    assert fwd.author == FORWARD_PREFIX + "خبرگزاری نمونه"
    # Copyright: excerpt only, never the full post, never media
    assert len(long_.description) <= 701
    assert len(long_.title) <= 141
    assert all(i.raw_content is None and i.image_url is None for i in (first, fwd, long_))


def test_ingest_is_idempotent(db):
    src = _figure_source(db)
    r1 = ingest_source(db, src, raw_content=PAGE)
    r2 = ingest_source(db, src, raw_content=PAGE)
    assert (r1.status, r1.new) == ("ok", 3)
    assert (r2.new, r2.duplicates) == (0, 3)


def test_figure_posts_stay_out_of_news_stories(db):
    fig = _figure_source(db)
    ingest_source(db, fig, raw_content=PAGE)
    news = make_source(db, name="Test Wire")
    ingest_source(db, news, raw_content="""<?xml version="1.0"?><rss version="2.0"><channel>
      <item><title>Mediators to hold separate talks with both sides</title>
      <link>https://wire.test/talks</link><pubDate>Mon, 28 Sep 2026 14:00:00 GMT</pubDate></item>
      </channel></rss>""")
    summary = cluster_articles(db)
    assert summary["pending"] == 1  # only the news article
    fig_article_ids = {a.id for a in db.query(Article).filter_by(source_id=fig.id)}
    linked = {row.article_id for row in db.query(StoryArticle)}
    assert not (fig_article_ids & linked)


def test_figures_list_is_well_formed():
    handles = [f.handle for f in FIGURES]
    assert len(handles) == len(set(h.lower() for h in handles))
    assert all(f.field in {"politics", "foreign", "economy", "history", "culture"} for f in FIGURES)
    assert all(f.name_fa and f.role_fa for f in FIGURES)
