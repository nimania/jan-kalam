from app.ingestion.service import ingest_all, ingest_source
from app.models.article import Article
from app.models.enums import FeedType
from app.models.ingestion_log import IngestionLog
from app.models.source import Source
from tests.conftest import make_source

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:content="http://purl.org/rss/1.0/modules/content/"
     xmlns:media="http://search.yahoo.com/mrss/">
  <channel>
    <title>Test Wire</title>
    <language>en</language>
    <item>
      <title>Nations meet to discuss energy prices</title>
      <link>https://wire.test/energy-1</link>
      <description>&lt;p&gt;A short excerpt.&lt;/p&gt;</description>
      <pubDate>Mon, 07 Sep 2026 06:00:00 GMT</pubDate>
      <author>reporter@wire.test</author>
      <content:encoded>&lt;p&gt;Full article body here.&lt;/p&gt;</content:encoded>
      <media:content url="https://wire.test/img1.jpg" type="image/jpeg"/>
    </item>
    <item>
      <title>Second story headline</title>
      <link>https://wire.test/story-2</link>
      <description>Another excerpt</description>
      <pubDate>Mon, 07 Sep 2026 05:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""

SAMPLE_JSON = """{
  "version": "https://jsonfeed.org/version/1",
  "title": "JSON Wire",
  "items": [
    {"id":"https://j.test/1","url":"https://j.test/1","title":"JSON story one",
     "summary":"sum","date_published":"2026-09-07T06:00:00Z","author":{"name":"A"}},
    {"id":"https://j.test/2","url":"https://j.test/2","title":"JSON story two",
     "content_text":"body"}
  ]
}"""


def test_rss_parse_and_insert(db):
    src = make_source(db, name="Test Wire")
    result = ingest_source(db, src, raw_content=SAMPLE_RSS)
    assert result.status == "ok"
    assert result.fetched == 2
    assert result.new == 2
    assert result.duplicates == 0
    arts = db.query(Article).order_by(Article.published_at.desc()).all()
    assert len(arts) == 2
    assert arts[0].title == "Nations meet to discuss energy prices"
    assert arts[0].published_at is not None
    # HTML stripped from the excerpt
    assert "<p>" not in (arts[0].description or "")


def test_dedup_is_idempotent(db):
    src = make_source(db, name="Test Wire")
    ingest_source(db, src, raw_content=SAMPLE_RSS)
    second = ingest_source(db, src, raw_content=SAMPLE_RSS)
    assert second.new == 0
    assert second.duplicates == 2
    assert db.query(Article).count() == 2  # no duplicates persisted


def test_source_usage_rules_control_full_content_and_image(db):
    # Default source: full content + image NOT permitted.
    strict = make_source(db, name="Strict Source")
    ingest_source(db, strict, raw_content=SAMPLE_RSS)
    a = db.query(Article).filter_by(source_name="Strict Source").first()
    assert a.raw_content_if_permitted is None
    assert a.image_url_if_permitted is None

    # Permissive source: both allowed.
    permissive = Source(
        name="Permissive Source",
        feed_url="https://p.test/rss",
        allow_full_content=True,
        allow_image=True,
    )
    db.add(permissive)
    db.commit()
    # Distinct URLs (a real second source never shares another's article URLs).
    ingest_source(db, permissive, raw_content=SAMPLE_RSS.replace("wire.test", "wire2.test"))
    b = db.query(Article).filter_by(source_name="Permissive Source").first()
    assert b.raw_content_if_permitted == "Full article body here."
    assert b.image_url_if_permitted == "https://wire2.test/img1.jpg"


def test_json_feed_parse(db):
    src = Source(name="JSON Wire", feed_url="https://j.test/feed.json", feed_type=FeedType.json)
    db.add(src)
    db.commit()
    result = ingest_source(db, src, raw_content=SAMPLE_JSON)
    assert result.new == 2
    a = db.query(Article).filter_by(article_url="https://j.test/1").first()
    assert a.title == "JSON story one"
    assert a.author == "A"


def test_malformed_feed_is_handled(db):
    src = Source(name="Broken JSON", feed_url="https://b.test/feed.json", feed_type=FeedType.json)
    db.add(src)
    db.commit()
    result = ingest_source(db, src, raw_content="{ this is not valid json")
    assert result.status == "error"
    assert result.errors == 1
    assert db.query(Article).count() == 0


def test_ingestion_log_written(db):
    src = make_source(db, name="Test Wire")
    ingest_source(db, src, raw_content=SAMPLE_RSS)
    log = db.query(IngestionLog).filter_by(source_name="Test Wire").first()
    assert log is not None
    assert log.new_count == 2
    assert log.started_at is not None and log.finished_at is not None


def test_ingest_all_only_enabled(db):
    enabled = make_source(db, name="Enabled Src")
    disabled = Source(name="Disabled Src", feed_url="https://d.test/rss", enabled=False)
    db.add(disabled)
    db.commit()

    def fake_fetch(url):
        return SAMPLE_RSS

    results = ingest_all(db, fetcher=fake_fetch)
    names = {r.source_name for r in results}
    assert "Enabled Src" in names
    assert "Disabled Src" not in names


def test_admin_ingestion_logs_endpoint(client, db):
    src = make_source(db, name="Logged Src")
    ingest_source(db, src, raw_content=SAMPLE_RSS)
    r = client.get("/api/v1/admin/ingestion-logs")
    assert r.status_code == 200
    assert any(row["source_name"] == "Logged Src" and row["new"] == 2 for row in r.json())
