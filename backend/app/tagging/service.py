"""Automatic topic tagging — assign topics to each story by keyword match.

Real ingested stories arrive without topics, which left the «داغ‌ترین موضوع‌ها»
board and the موضوعات tab empty. This tags every published story (that isn't
tagged yet) against a Persian+English keyword rule set, so trends and topic
following become meaningful. Keyword-based and deterministic — no AI cost.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.logging import get_logger
from app.models.enums import StoryStatus
from app.models.story import Story, StoryArticle
from app.models.taxonomy import StoryTopic, Topic

logger = get_logger("tagging")

# slug, name_fa, name_en, keywords (matched case-insensitively in fa + en text)
RULES: list[tuple[str, str, str, list[str]]] = [
    ("economy", "اقتصاد", "Economy",
     ["اقتصاد", "تورم", "دلار", "ارز", "بورس", "بانک", "یارانه", "بودجه", "قیمت",
      "سکه", "طلا", "مسکن", "خودرو", "صادرات", "واردات", "تجارت", "تحریم",
      "economy", "inflation", "currency", "market", "bank", "budget", "trade",
      "sanction", "tariff", "export", "import", "stocks", "gdp"]),
    ("politics", "سیاست", "Politics",
     ["مجلس", "دولت", "انتخابات", "وزیر", "قوه", "رئیس‌جمهور", "رئیس جمهور",
      "نماینده", "سیاست", "کابینه", "پارلمان",
      "election", "parliament", "government", "minister", "president", "policy",
      "cabinet", "senate", "diplomacy"]),
    ("middle-east", "خاورمیانه", "Middle East",
     ["اسرائیل", "غزه", "فلسطین", "لبنان", "سوریه", "عربستان", "یمن", "حماس",
      "حزب‌الله", "حزب الله", "عراق", "قطر", "امارات",
      "israel", "gaza", "palestin", "lebanon", "syria", "saudi", "yemen",
      "hamas", "hezbollah", "iraq", "qatar", "emirates"]),
    ("us-politics", "سیاست آمریکا", "US Politics",
     ["آمریکا", "ترامپ", "واشنگتن", "بایدن", "کنگره", "کاخ سفید", "پنتاگون",
      "trump", "washington", "biden", "congress", "white house", "pentagon",
      "u.s.", "united states"]),
    ("energy", "انرژی", "Energy",
     ["نفت", "گاز", "اوپک", "انرژی", "بنزین", "برق", "پالایشگاه", "سوخت",
      "oil", "gas", "opec", "energy", "fuel", "gasoline", "electricity", "petrol"]),
    ("technology", "فناوری", "Technology",
     ["فناوری", "اینترنت", "گوگل", "اپل", "مایکروسافت", "نرم‌افزار", "موبایل",
      "استارتاپ", "تراشه", "فیلترینگ",
      "tech", "internet", "google", "apple", "microsoft", "software", "startup",
      "chip", "semiconductor", "smartphone"]),
    ("ai", "هوش مصنوعی", "AI",
     ["هوش مصنوعی", "چت‌بات", "مدل زبانی", "اوپن‌ای‌آی",
      "artificial intelligence", " ai ", "chatbot", "openai", "gpt", "llm",
      "gemini", "anthropic", "neural"]),
    ("russia-ukraine", "روسیه-اوکراین", "Russia-Ukraine",
     ["روسیه", "اوکراین", "پوتین", "زلنسکی", "مسکو", "کی‌یف", "کیف",
      "russia", "ukraine", "putin", "zelensky", "moscow", "kyiv", "kremlin"]),
    ("sport", "ورزش", "Sport",
     ["فوتبال", "ورزش", "تیم ملی", "لیگ", "والیبال", "المپیک", "جام", "قهرمانی",
      "football", "soccer", "sport", "league", "olympic", "world cup", "match",
      "championship"]),
    ("crypto", "رمزارز", "Crypto",
     ["بیت‌کوین", "بیت کوین", "رمزارز", "ارز دیجیتال", "اتریوم", "بلاکچین",
      "bitcoin", "crypto", "ethereum", "blockchain", "btc"]),
    ("iran", "ایران", "Iran",
     ["ایران", "تهران", "ایرانی", "iran", "tehran", "iranian"]),
]

_MAX_PER_STORY = 3


def ensure_topics(db: Session) -> dict[str, Topic]:
    """Create any missing Topic rows and return slug -> Topic."""
    out: dict[str, Topic] = {}
    for slug, fa, en, _ in RULES:
        t = db.query(Topic).filter_by(slug=slug).one_or_none()
        if not t:
            t = Topic(slug=slug, name_fa=fa, name_en=en)
            db.add(t)
        out[slug] = t
    db.commit()
    return out


def _story_text(story: Story) -> str:
    parts = [story.headline_fa or "", story.summary_fa or "",
             story.what_happened_fa or "", story.why_it_matters_fa or ""]
    for link in story.article_links:
        a = link.article
        if a:
            parts.append(a.title or "")
    return " ".join(parts).lower()


def tag_stories(db: Session) -> dict:
    """Tag every published story that has no topics yet. Returns a small summary."""
    topics = ensure_topics(db)
    stories = db.execute(
        select(Story)
        .where(Story.status == StoryStatus.published)
        .options(
            selectinload(Story.topic_links),
            selectinload(Story.article_links).selectinload(StoryArticle.article),
        )
    ).scalars().unique().all()

    tagged = 0
    for s in stories:
        if s.topic_links:  # already tagged (persists across cached builds)
            continue
        text = _story_text(s)
        scored: list[tuple[int, str]] = []
        for slug, _fa, _en, kws in RULES:
            hits = sum(1 for kw in kws if kw in text)
            if hits:
                scored.append((hits, slug))
        scored.sort(reverse=True)
        for _hits, slug in scored[:_MAX_PER_STORY]:
            db.add(StoryTopic(story_id=s.id, topic_id=topics[slug].id))
        if scored:
            tagged += 1
    db.commit()
    logger.info("tagged %d stories", tagged)
    return {"tagged": tagged, "topics": len(topics)}
