"""Seed sample sources, topics, and one fully-formed demo story so the API and
Android app have realistic data during development.

Run:  python -m scripts.seed
Idempotent-ish: it creates tables if missing and skips sources/topics that exist.
The demo article text is synthetic (not copied from any publication).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.article import Article
from app.models.enums import (
    Category,
    FeedType,
    IranRelevance,
    StatementKind,
    StoryStatus,
)
from app.models.source import Source
from app.models.story import SourceView, Statement, Story, StoryArticle
from app.models.taxonomy import StoryTopic, Topic

SOURCES = [
    # NOTE: this list is pruned to feeds VERIFIED working from the GitHub Actions
    # runner (see the ingestion log). reliability_score is a starting internal
    # ranking input to be tuned — NOT a political label. Domestic and diaspora
    # outlets are BOTH included so the source-comparison layer can show where they
    # agree and differ.
    #
    # Removed because their feed did not work from GitHub's servers (DNS-blocked,
    # 403/404, or returned zero items). If you have a working RSS URL for any of
    # these, add it back: تسنیم, ایلنا, اقتصادنیوز, برترین‌ها, رادیو فردا,
    # صدای آمریکا (VOA), ایندیپندنت فارسی, ایران‌وایر, Reuters, Associated Press.

    # --- Global / international ---
    ("BBC", "https://www.bbc.com/news", "http://feeds.bbci.co.uk/news/world/rss.xml", "global", 0.85),
    ("The Guardian", "https://www.theguardian.com", "https://www.theguardian.com/world/rss", "global", 0.8),
    ("Al Jazeera", "https://www.aljazeera.com", "https://www.aljazeera.com/xml/rss/all.xml", "mena", 0.75),
    ("The Verge", "https://www.theverge.com", "https://www.theverge.com/rss/index.xml", "tech", 0.7),

    # --- Persian-language: domestic (agencies, portals, economic, sport) ---
    ("خبرگزاری ایرنا (IRNA)", "https://www.irna.ir", "https://www.irna.ir/rss", "iran", 0.6),
    ("خبرگزاری ایسنا (ISNA)", "https://www.isna.ir", "https://www.isna.ir/rss", "iran", 0.6),
    ("خبرگزاری مهر (Mehr)", "https://www.mehrnews.com", "https://www.mehrnews.com/rss", "iran", 0.6),
    # Fars: use the no-www host directly (www.farsnews.ir/rss 301-redirects to a 404).
    ("خبرگزاری فارس (Fars)", "https://farsnews.ir", "https://farsnews.ir/rss", "iran", 0.55),
    ("خبرآنلاین", "https://www.khabaronline.ir", "https://www.khabaronline.ir/rss", "iran", 0.6),
    ("همشهری آنلاین", "https://www.hamshahrionline.ir", "https://www.hamshahrionline.ir/rss", "iran", 0.55),
    ("خبرگزاری صداوسیما", "https://www.iribnews.ir", "https://www.iribnews.ir/fa/rss/allnews", "iran", 0.5),
    ("باشگاه خبرنگاران جوان", "https://www.yjc.ir", "https://www.yjc.ir/fa/rss/allnews", "iran", 0.5),
    ("تابناک", "https://www.tabnak.ir", "https://www.tabnak.ir/fa/rss/allnews", "iran", 0.55),
    ("فرارو", "https://fararu.com", "https://fararu.com/fa/rss/allnews", "iran", 0.55),
    ("انتخاب", "https://www.entekhab.ir", "https://www.entekhab.ir/fa/rss/allnews", "iran", 0.55),
    ("عصر ایران", "https://www.asriran.com", "https://www.asriran.com/fa/rss/allnews", "iran", 0.5),
    ("فردانیوز", "https://www.fardanews.com", "https://www.fardanews.com/fa/rss/allnews", "iran", 0.5),
    ("رویداد۲۴", "https://www.rouydad24.ir", "https://www.rouydad24.ir/fa/rss/allnews", "iran", 0.5),
    ("آفتاب‌نیوز", "https://aftabnews.ir", "https://aftabnews.ir/fa/rss/allnews", "iran", 0.5),
    ("مشرق نیوز", "https://www.mashreghnews.ir", "https://www.mashreghnews.ir/rss", "iran", 0.5),
    ("انصاف نیوز", "https://www.ensafnews.com", "https://www.ensafnews.com/feed", "iran", 0.5),
    ("روزنامه پیام‌ما", "https://payamema.ir", "https://payamema.ir/feed", "iran", 0.55),
    ("ورزش سه", "https://www.varzesh3.com", "https://www.varzesh3.com/rss/all", "iran", 0.45),

    # --- Persian-language: international / diaspora ---
    ("بی‌بی‌سی فارسی (BBC Persian)", "https://www.bbc.com/persian", "https://feeds.bbci.co.uk/persian/rss.xml", "iran-intl", 0.75),
    ("ایران اینترنشنال (Iran International)", "https://www.iranintl.com", "https://www.iranintl.com/feed", "iran-intl", 0.6),
    ("دویچه‌وله فارسی (DW Persian)", "https://www.dw.com/fa-ir", "https://rss.dw.com/rdf/rss-per-all", "iran-intl", 0.75),
    ("یورونیوز فارسی", "https://parsi.euronews.com", "https://parsi.euronews.com/rss", "iran-intl", 0.7),
    ("کیهان لندن", "https://kayhan.london", "https://kayhan.london/feed/", "iran-intl", 0.55),
    ("زیتون", "https://www.zeitoons.com", "https://www.zeitoons.com/feed", "iran-intl", 0.5),
]

TOPICS = [
    ("iran", "ایران", "Iran"),
    ("us-politics", "سیاست آمریکا", "US Politics"),
    ("ai", "هوش مصنوعی", "AI"),
    ("middle-east", "خاورمیانه", "Middle East"),
    ("russia-ukraine", "روسیه-اوکراین", "Russia-Ukraine"),
    ("bitcoin", "بیت‌کوین", "Bitcoin"),
]


def run() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Reconcile the sources table to match SOURCES on EVERY run. The build DB
        # is cached between runs, so a plain "skip if exists" would freeze the old
        # rows: edited feed URLs would never update and removed feeds would keep
        # being fetched. So we upsert every listed source (updating its feed_url
        # etc.) and DISABLE any source no longer in the list (we disable, never
        # delete, because articles reference sources via a FK).
        by_name: dict[str, Source] = {}
        wanted: set[str] = set()
        for name, home, feed, region, rel in SOURCES:
            wanted.add(name)
            lang = "fa" if region in ("iran", "iran-intl") else "en"
            existing = db.query(Source).filter_by(name=name).one_or_none()
            if existing:
                existing.homepage_url = home
                existing.feed_url = feed
                existing.region = region
                existing.language = lang
                existing.reliability_score = rel
                existing.enabled = True
                by_name[name] = existing
                continue
            s = Source(
                name=name,
                homepage_url=home,
                feed_url=feed,
                feed_type=FeedType.rss,
                region=region,
                language=lang,
                reliability_score=rel,
                attribution_required=True,
            )
            db.add(s)
            by_name[name] = s
        # Disable feeds that were pruned from SOURCES but still linger in the
        # cached DB (dead/blocked feeds — Reuters, AP, Tasnim, VOA, …).
        for s in db.query(Source).all():
            if s.name not in wanted and s.enabled:
                s.enabled = False
        db.commit()

        topics: dict[str, Topic] = {}
        for slug, fa, en in TOPICS:
            existing = db.query(Topic).filter_by(slug=slug).one_or_none()
            if existing:
                topics[slug] = existing
                continue
            t = Topic(slug=slug, name_fa=fa, name_en=en)
            db.add(t)
            topics[slug] = t
        db.commit()

        if db.query(Story).count() == 0:
            _create_demo_story(db, by_name, topics)
        print("Seed complete.")
    finally:
        db.close()


def _create_demo_story(db, by_name, topics) -> None:
    now = datetime.now(timezone.utc)
    story = Story(
        headline_fa="نشست بین‌المللی دربارهٔ قیمت جهانی انرژی",
        summary_fa=(
            "چند خبرگزاری معتبر از برگزاری نشستی بین‌المللی برای بررسی نوسان قیمت "
            "انرژی خبر داده‌اند. گزارش‌ها بر سر اصل برگزاری نشست هم‌نظرند، اما در "
            "جزئیات نتیجه و تعهدات مشخص تفاوت دارند."
        ),
        what_happened_fa="نمایندگان چند کشور برای گفت‌وگو دربارهٔ بازار انرژی گرد هم آمدند.",
        why_it_matters_fa="تغییر قیمت انرژی می‌تواند بر اقتصاد کشورهای وابسته به صادرات و واردات انرژی اثر بگذارد.",
        category=Category.economy,
        status=StoryStatus.published,
        iran_relevance=IranRelevance.medium,
        importance_score=0.72,
        confidence_score=0.6,
        source_count=2,
        event_time=now - timedelta(hours=5),
        published_at=now - timedelta(hours=4),
    )
    db.add(story)
    db.flush()

    guardian, bbc = by_name["The Guardian"], by_name["BBC"]
    a1 = Article(
        source_id=guardian.id, source_name=guardian.name, source_url=guardian.homepage_url,
        article_url="https://example-guardian.test/energy-summit-1",
        title="Nations meet to discuss global energy prices",
        description="Synthetic excerpt for development only.",
        published_at=now - timedelta(hours=5), language="en",
        category=Category.economy, hash="demo-hash-guardian-1",
    )
    a2 = Article(
        source_id=bbc.id, source_name=bbc.name, source_url=bbc.homepage_url,
        article_url="https://example-bbc.test/energy-summit-1",
        title="Countries hold talks on energy market",
        description="Synthetic excerpt for development only.",
        published_at=now - timedelta(hours=4, minutes=30), language="en",
        category=Category.economy, hash="demo-hash-bbc-1",
    )
    db.add_all([a1, a2])
    db.flush()
    db.add_all([
        StoryArticle(story_id=story.id, article_id=a1.id, relevance=0.95, is_primary=True),
        StoryArticle(story_id=story.id, article_id=a2.id, relevance=0.9),
    ])
    db.add_all([
        SourceView(
            story_id=story.id, source_id=guardian.id, source_name="The Guardian",
            original_headline="Nations meet to discuss global energy prices",
            article_url=a1.article_url, published_at=a1.published_at,
            viewpoint_fa="گاردین بر برگزاری نشست و شمار کشورهای شرکت‌کننده تأکید کرده است.",
        ),
        SourceView(
            story_id=story.id, source_id=bbc.id, source_name="BBC",
            original_headline="Countries hold talks on energy market",
            article_url=a2.article_url, published_at=a2.published_at,
            viewpoint_fa="بی‌بی‌سی بیشتر بر پیامدهای احتمالی نشست بر بازار تمرکز کرده است.",
        ),
    ])
    db.add_all([
        Statement(story_id=story.id, kind=StatementKind.fact,
                  text_fa="نشستی دربارهٔ قیمت انرژی برگزار شده است.", confidence=0.9),
        Statement(story_id=story.id, kind=StatementKind.uncertainty,
                  text_fa="جزئیات تعهدات نهایی هنوز روشن نیست.", confidence=0.4),
        Statement(story_id=story.id, kind=StatementKind.agreement,
                  text_fa="هر دو منبع بر اصل برگزاری نشست هم‌نظرند.", confidence=0.85),
        Statement(story_id=story.id, kind=StatementKind.disagreement,
                  text_fa="منابع در توصیف نتیجهٔ نشست تفاوت دارند.", confidence=0.5),
    ])
    db.add(StoryTopic(story_id=story.id, topic_id=topics["middle-east"].id))
    db.commit()


if __name__ == "__main__":
    run()
