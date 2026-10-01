"""جان‌کلام چهره‌ها — stage 2: classify each commentator post once.

Flow per build:
  1. Forwarded posts are classified by rule as `relay` (no AI cost).
  2. Remaining unclassified posts from the last few days are sent to the AI in
     batches (one call per batch) and validated with Pydantic.
  3. Results are stored in `figure_posts` and never re-classified.

If no AI key is configured (mock provider) the stage does nothing, so posts stay
unclassified until a real model is available — we never store fake labels.
A failure here must never break the build: callers wrap it.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.providers import get_provider
from app.ai.providers.base import Provider, ProviderResult
from app.core.config import settings
from app.core.logging import get_logger
from app.figures import FIGURE_REGION, FIGURES, figure_source_name
from app.ingestion.telegram import FORWARD_PREFIX, is_forwarded
from app.models.article import Article
from app.models.figure_post import FigurePost
from app.models.source import Source
from app.models.usage_log import UsageLog

logger = get_logger("figures")

Kind = Literal["analysis", "relay", "party_claim", "chatter", "promo"]
SHOWN_KINDS = {"analysis", "party_claim"}

# Bump when the prompt below changes so cached posts are re-labeled with the new
# instructions (e.g. v1 → v2 = fuller summaries). Rule-based relay rows are left
# alone; only AI-labeled rows from an older version are re-sent.
PROMPT_VERSION = "v3"

BATCH_SIZE = 20
MAX_PER_RUN = 60          # ≤ 3 AI calls per build
LOOKBACK_DAYS = 8         # window for new posts + re-labeling the shown backlog

_ROLE = {figure_source_name(f): f.role_fa for f in FIGURES}

SYSTEM_PROMPT = """\
تو دستیار سردبیری «جان‌کلام» هستی. فهرستی از پست‌های کانال تلگرام چند چهرهٔ عمومی
(تحلیلگر، اقتصاددان، مورخ، روزنامه‌نگار) به تو داده می‌شود. هر پست را جداگانه دسته‌بندی کن.

دسته‌ها (kind):
- "analysis": نظر، تحلیل یا استدلالِ خودِ این شخص دربارهٔ یک موضوع عمومی.
- "relay": پست عمدتاً خبرِ دیگران را نقل می‌کند (خبرگزاری، رسانه، مقام رسمی) و نظر
  چشمگیری از خود شخص ندارد. اگر نقل خبر همراه با نظر روشن شخص است، "analysis" بگذار.
- "party_claim": شخص خودش طرفِ ماجراست (پروندهٔ خودش، دعوای شخصی‌اش، دفاع از خودش،
  حمایت دیگران از خودش).
- "chatter": شوخی، طعنه، حملهٔ شخصی یا توهین به افراد، احوال‌پرسی، مطالب بی‌ربط به امور عمومی.
- "promo": تبلیغ کتاب، کارگاه، کلاس، درخواست حمایت مالی، «ویدیو را در یوتیوب ببینید»،
  اطلاعیه‌های شخصی.

برای هر پست:
- topic_fa: موضوع در حداکثر ۸ کلمه (مثلاً «مذاکرات ایران و آمریکا»).
- summary_fa: فقط برای analysis و party_claim؛ یک بازگوییِ کاملِ استدلالِ شخص در
  حدودِ ۳ تا ۶ جمله (یک پاراگراف). نکاتِ اصلی، دلیل‌ها، مثال‌ها و نتیجه‌گیریِ او را
  با انسجام بیاور، طوری که خواننده بدونِ خواندنِ متنِ اصلی هم جانِ کلامِ او را بفهمد.
  چون نام و هویت گوینده جداگانه بالای کارت نمایش داده می‌شود، summary_fa را مستقیم با
  خودِ ادعا، استدلال یا موضوع شروع کن و از آغازهای تکراری مانند «فلانی می‌گوید»،
  «به باور او»، «او معتقد است» و «از نظر او» پرهیز کن. با این حال متن باید روشن بماند
  که دیدگاه است، نه واقعیت قطعی. توهین‌ها و الفاظ تند را بازتولید نکن و به زبان خنثی
  بازگو کن. متن پست را عیناً کپی نکن، بلکه خلاصه و بازنویسی کن.
  برای بقیهٔ دسته‌ها رشتهٔ خالی.
- relayed_from: فقط برای relay؛ نام منبعِ اصلی خبر اگر در متن آمده (مثل «رویترز»)، وگرنه خالی.
- confidence: عددی بین ۰ و ۱.

فقط یک شیء JSON معتبر برگردان با کلید "posts": فهرستی از اشیاء با کلیدهای
id، kind، topic_fa، summary_fa، relayed_from، confidence. برای هر پستِ ورودی دقیقاً یک خروجی.
"""


class PostLabel(BaseModel):
    id: str
    kind: Kind
    topic_fa: str = Field(default="", max_length=200)
    summary_fa: str = ""
    relayed_from: str = Field(default="", max_length=200)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    @field_validator("topic_fa", "summary_fa", "relayed_from", mode="before")
    @classmethod
    def _none_to_empty(cls, v):
        return (v or "").strip() if isinstance(v, str) or v is None else v


class BatchLabels(BaseModel):
    posts: list[PostLabel]


def build_user_prompt(batch: list[Article]) -> str:
    rows = []
    for i, a in enumerate(batch, 1):
        rows.append({
            "id": str(i),
            "person": a.source_name.removeprefix("چهره: "),
            "role": _ROLE.get(a.source_name, ""),
            "text": a.description or a.title,
        })
    return "پست‌ها:\n" + json.dumps(rows, ensure_ascii=False, indent=1)


def _pending(db: Session, now: datetime) -> list[Article]:
    """Figure articles that need (re)labeling: never labeled, or labeled by an
    older prompt version. Rule-based relay rows and current-version AI rows are
    considered done."""
    figure_ids = select(Source.id).where(Source.region == FIGURE_REGION)
    done = select(FigurePost.article_id).where(
        FigurePost.classified_by.like("rule%")
        | FigurePost.classified_by.like(f"{PROMPT_VERSION}:%")
    )
    since = now - timedelta(days=LOOKBACK_DAYS)
    return list(db.execute(
        select(Article)
        .where(Article.source_id.in_(figure_ids))
        .where(Article.id.not_in(done))
        .where((Article.published_at.is_(None)) | (Article.published_at >= since))
        .order_by(Article.published_at.desc().nullslast())
    ).scalars().all())


def _store(db: Session, a: Article, *, kind: str, topic: str = "", summary: str = "",
           relayed_from: str = "", confidence: float = 0.5, by: str = "rule") -> None:
    if kind in SHOWN_KINDS and not summary:
        kind = "chatter" if kind == "analysis" else kind  # nothing to show → hide
    fp = db.query(FigurePost).filter_by(article_id=a.id).one_or_none()
    if fp is None:
        fp = FigurePost(article_id=a.id, source_id=a.source_id)
        db.add(fp)
    fp.kind = kind
    fp.topic_fa = topic or None
    fp.summary_fa = summary or None
    fp.relayed_from = relayed_from or None
    fp.confidence = confidence
    fp.classified_by = by[:40]
    fp.published_at = a.published_at
    fp.shown = kind in SHOWN_KINDS and bool(summary)


def _log(db: Session, r: ProviderResult | None, status: str, msg: str | None = None) -> None:
    cost = 0.0
    if r:
        cost = round(r.prompt_tokens / 1e6 * settings.ai_price_in_per_mtok
                     + r.completion_tokens / 1e6 * settings.ai_price_out_per_mtok, 6)
    db.add(UsageLog(
        stage="figures", provider="gemini" if r else "", model=getattr(r, "model", "") or "",
        prompt_tokens=getattr(r, "prompt_tokens", 0),
        completion_tokens=getattr(r, "completion_tokens", 0),
        cost_estimate=cost, latency_ms=getattr(r, "latency_ms", 0),
        status=status, message=(msg or "")[:500] or None,
    ))


def classify_figure_posts(db: Session, *, provider: Provider | None = None,
                          now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    pending = _pending(db, now)
    summary = {"pending": len(pending), "relay_rule": 0, "ai_labeled": 0,
               "shown": 0, "failed_batches": 0, "skipped": ""}

    # 1) forwarded posts → relay, free
    rest: list[Article] = []
    for a in pending:
        if is_forwarded(a.author):
            _store(db, a, kind="relay",
                   relayed_from=a.author.removeprefix(FORWARD_PREFIX), confidence=0.9)
            summary["relay_rule"] += 1
        else:
            rest.append(a)
    db.commit()

    # 2) AI batches
    provider = provider or get_provider()
    if getattr(provider, "name", "") == "mock":
        summary["skipped"] = "no_ai_key"
        logger.info("figures: %s", summary)
        return summary

    todo = rest[:MAX_PER_RUN]
    for start in range(0, len(todo), BATCH_SIZE):
        batch = todo[start:start + BATCH_SIZE]
        try:
            result = provider.generate(system=SYSTEM_PROMPT,
                                       user=build_user_prompt(batch), context={})
        except Exception as exc:
            logger.warning("figures: provider error: %s", exc)
            _log(db, None, "provider_error", str(exc))
            db.commit()
            summary["failed_batches"] += 1
            continue
        try:
            labels = BatchLabels.model_validate(result.data)
        except ValidationError as exc:
            logger.warning("figures: validation error: %s", exc)
            _log(db, result, "validation_error", str(exc))
            db.commit()
            summary["failed_batches"] += 1
            continue

        by_id = {l.id: l for l in labels.posts}
        for i, a in enumerate(batch, 1):
            lab = by_id.get(str(i))
            if lab is None:
                continue  # left for the next build
            _store(db, a, kind=lab.kind, topic=lab.topic_fa, summary=lab.summary_fa,
                   relayed_from=lab.relayed_from, confidence=lab.confidence,
                   by=f"{PROMPT_VERSION}:{result.model or 'ai'}")
            summary["ai_labeled"] += 1
        _log(db, result, "ok")
        db.commit()

    summary["shown"] = db.query(FigurePost).filter(FigurePost.shown.is_(True)).count()
    logger.info("figures: %s", summary)
    return summary


# ---------------------------------------------------------------------------
# Stage 3 — export for the static site
# ---------------------------------------------------------------------------
from app.clustering.similarity import tokenize  # noqa: E402

_BY_HANDLE = {f.handle.lower(): f for f in FIGURES}
# Field slugs → Persian section titles. Order here is the display order.
FIELD_FA = {
    "politics": "سیاست و جامعه",
    "foreign": "سیاست خارجی",
    "society": "جامعه و اندیشهٔ اجتماعی",
    "economy": "اقتصاد",
    "environment": "محیط‌زیست",
    "law": "حقوق و جامعهٔ مدنی",
    "media": "رسانه و تحلیل",
    "development": "علوم سیاسی و توسعه",
    "opposition": "اپوزیسیون و گذار",
    "religion": "دین و اندیشهٔ دینی",
    "philosophy": "فلسفه و اندیشه",
    "history": "تاریخ",
    "cinema": "سینما و نقد",
    "culture": "فرهنگ و هنر",
}

# Words too common in Persian news/commentary to signal "same topic".
_MATCH_STOP = {
    "او", "باور", "معتقد", "می", "ها", "های", "هم", "یک", "اما", "نیز", "خود",
    "شود", "شد", "کند", "کرد", "دارد", "دارند", "تا", "بر", "هر", "آن", "ای",
    "شده", "کرده", "اشاره", "استدلال", "نظر", "دیدگاه", "ایران", "ایرانی",
    "کشور", "گفت", "گفته", "باید", "نمی", "بین", "پس", "یا", "اگر", "چه",
    "درباره", "دربارهٔ", "موضوع", "وضعیت", "فعلا", "فعلاً", "بسیار", "حتی",
}
MATCH_MIN_SHARED = 4        # significant (non-stopword) tokens in common
MATCH_MIN_OVERLAP = 0.25    # relative to the shorter side
MATCH_WINDOW_H = 48
MAX_PER_STORY = 4


def _handle(source_home: str | None) -> str:
    return (source_home or "").rstrip("/").rsplit("/", 1)[-1]


def _mtokens(*texts: str | None) -> set[str]:
    return {t for t in tokenize(*texts) if t not in _MATCH_STOP}


def recent_shown_posts(db: Session, *, now: datetime | None = None,
                       days: int = 7, avatars: dict[str, str] | None = None) -> list[dict]:
    """Shown (analysis / party_claim) posts from the last `days`, newest first,
    as plain dicts ready for JSON."""
    now = now or datetime.now(timezone.utc)
    avatars = avatars or {}
    since = now - timedelta(days=days)
    rows = db.execute(
        select(FigurePost, Article, Source)
        .join(Article, FigurePost.article_id == Article.id)
        .join(Source, FigurePost.source_id == Source.id)
        .where(FigurePost.shown.is_(True))
        .where((FigurePost.published_at.is_(None)) | (FigurePost.published_at >= since))
        .order_by(FigurePost.published_at.desc().nullslast())
    ).all()
    out: list[dict] = []
    for fp, art, src in rows:
        h = _handle(src.homepage_url)
        fig = _BY_HANDLE.get(h.lower())
        if fig is None:
            continue  # figure removed from the list
        out.append({
            "id": fp.id,
            "handle": fig.handle,
            "name_fa": fig.name_fa,
            "role_fa": fig.role_fa,
            "field": fig.field,
            "avatar": avatars.get(fig.handle),
            "kind": fp.kind,
            "topic_fa": fp.topic_fa or "",
            "summary_fa": fp.summary_fa or "",
            "url": art.article_url,
            "published_at": fp.published_at.isoformat() if fp.published_at else None,
            "_tokens": _mtokens(fp.topic_fa, fp.summary_fa, art.description),
            "_time": fp.published_at,
        })
    return out


def _public(p: dict) -> dict:
    return {k: v for k, v in p.items() if not k.startswith("_")}


def match_story(texts: list[str | None], story_time: datetime | None,
                posts: list[dict]) -> list[dict]:
    """Figures' views that are about this story (one per figure, best first).
    Lexical match on AI-written topic/summary + the post excerpt, within
    ±MATCH_WINDOW_H of the story."""
    s_tok = _mtokens(*texts)
    if not s_tok:
        return []
    best: dict[str, tuple[float, dict]] = {}
    for p in posts:
        if story_time and p["_time"]:
            st = story_time if story_time.tzinfo else story_time.replace(tzinfo=timezone.utc)
            pt = p["_time"] if p["_time"].tzinfo else p["_time"].replace(tzinfo=timezone.utc)
            if abs((st - pt).total_seconds()) > MATCH_WINDOW_H * 3600:
                continue
        shared = s_tok & p["_tokens"]
        if len(shared) < MATCH_MIN_SHARED:
            continue
        overlap = len(shared) / max(1, min(len(p["_tokens"]), len(s_tok)))
        if overlap < MATCH_MIN_OVERLAP:
            continue
        prev = best.get(p["handle"])
        if prev is None or overlap > prev[0]:
            best[p["handle"]] = (overlap, p)
    ranked = sorted(best.values(), key=lambda x: -x[0])[:MAX_PER_STORY]
    # analysis before party claims
    ranked.sort(key=lambda x: (x[1]["kind"] != "analysis", -x[0]))
    return [_public(p) for _, p in ranked]


def figures_index(posts: list[dict], *, per_figure: int = 15,
                  avatars: dict[str, str] | None = None) -> dict:
    """data/figures.json — every figure (even with no recent views) + latest views."""
    from app.figures import figure_social

    avatars = avatars or {}
    by: dict[str, list[dict]] = {}
    for p in posts:
        by.setdefault(p["handle"], []).append(_public(p))
    figures = []
    for f in FIGURES:
        items = by.get(f.handle, [])[:per_figure]
        figures.append({
            "handle": f.handle, "name_fa": f.name_fa, "role_fa": f.role_fa,
            "field": f.field, "field_fa": FIELD_FA.get(f.field, ""),
            "gender": f.gender,
            "channel_url": f"https://t.me/{f.handle}",
            "avatar": avatars.get(f.handle),
            "social": figure_social(f),
            "count": len(by.get(f.handle, [])), "posts": items,
        })
    return {"fields": FIELD_FA, "figures": figures}
