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
    # --- Global / international ---
    ("Reuters", "https://www.reuters.com", "https://feeds.reuters.com/reuters/worldNews", "global", 0.9),
    ("Associated Press", "https://apnews.com", "https://apnews.com/hub/ap-top-news?output=rss", "global", 0.9),
    ("BBC", "https://www.bbc.com/news", "http://feeds.bbci.co.uk/news/world/rss.xml", "global", 0.85),
    ("The Guardian", "https://www.theguardian.com", "https://www.theguardian.com/world/rss", "global", 0.8),
    ("Al Jazeera", "https://www.aljazeera.com", "https://www.aljazeera.com/xml/rss/all.xml", "mena", 0.75),
    ("The Verge", "https://www.theverge.com", "https://www.theverge.com/rss/index.xml", "tech", 0.7),
    # --- Persian-language: domestic (state / semi-state) ---
    # reliability_score is a starting internal ranking input to be tuned — NOT a
    # political label. Domestic and diaspora outlets are BOTH included so the
    # source-comparison layer can show where they agree and differ.
    ("خبرگزاری ایرنا (IRNA)", "https://www.irna.ir", "https://www.irna.ir/rss", "iran", 0.6),
    ("خبرگزاری ایسنا (ISNA)", "https://www.isna.ir", "https://www.isna.ir/rss", "iran", 0.6),
    ("خبرگزاری تسنیم (Tasnim)", "https://www.tasnimnews.com", "https://www.tasnimnews.com/fa/rss/feed/0/7/0", "iran", 0.55),
    # --- Persian-language: international / diaspora ---
    ("بی‌بی‌سی فارسی (BBC Persian)", "https://www.bbc.com/persian", "https://feeds.bbci.co.uk/persian/rss.xml", "iran-intl", 0.75),
    ("ایران اینترنشنال (Iran International)", "https://www.iranintl.com", "https://www.iranintl.com/en/rss", "iran-intl", 0.6),
    ("رادیو فردا (Radio Farda)", "https://www.radiofarda.com", "https://www.radiofarda.com/api/zrqiteuuir", "iran-intl", 0.65),
    ("دویچه‌وله فارسی (DW Persian)", "https://www.dw.com/fa-ir", "https://rss.dw.com/rdf/rss-per-all", "iran-intl", 0.75),
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
        by_name: dict[str, Source] = {}
        for name, home, feed, region, rel in SOURCES:
            existing = db.query(Source).filter_by(name=name).one_or_none()
            if existing:
                by_name[name] = existing
                continue
            s = Source(
                name=name,
                homepage_url=home,
                feed_url=feed,
                feed_type=FeedType.rss,
                region=region,
                language="fa" if region in ("iran", "iran-intl") else "en",
                reliability_score=rel,
                attribution_required=True,
            )
            db.add(s)
            by_name[name] = s
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

    reuters, bbc = by_name["Reuters"], by_name["BBC"]
    a1 = Article(
        source_id=reuters.id, source_name=reuters.name, source_url=reuters.homepage_url,
        article_url="https://example-reuters.test/energy-summit-1",
        title="Nations meet to discuss global energy prices",
        description="Synthetic excerpt for development only.",
        published_at=now - timedelta(hours=5), language="en",
        category=Category.economy, hash="demo-hash-reuters-1",
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
            story_id=story.id, source_id=reuters.id, source_name="Reuters",
            original_headline="Nations meet to discuss global energy prices",
            article_url=a1.article_url, published_at=a1.published_at,
            viewpoint_fa="رویترز بر برگزاری نشست و شمار کشورهای شرکت‌کننده تأکید کرده است.",
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
