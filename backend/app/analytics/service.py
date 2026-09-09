"""Analytics for جان‌کلام — counts over time, topic growth, and the rising/hot
signal — computed at build time from data we already store (no new tables).

Two timestamps carry everything:
  • Story.created_at        — when a story first entered the system,
  • StoryArticle.created_at — when each source's coverage was attached.

From the first we get "how many stories arrived in the last N hours / today /
this week …" and per-topic growth curves. From the second we get each story's
*coverage velocity* — how fast independent sources are piling onto it right now —
which is what "در حال رشد" (rising) and "داغ" (hot) mean.

Everything is deterministic and explainable; the formulas are documented inline.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import StoryStatus
from app.models.story import Story, StoryArticle
from app.models.taxonomy import StoryTopic

# Iran uses UTC+03:30 year-round (DST abolished in 2022), so day/week boundaries
# for "امروز / این هفته" are computed against this fixed offset.
TEHRAN = timezone(timedelta(hours=3, minutes=30))


def _ms(dt: datetime | None) -> int | None:
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _published(db: Session) -> list[Story]:
    return db.execute(
        select(Story)
        .where(Story.status == StoryStatus.published)
        .options(
            selectinload(Story.topic_links).selectinload(StoryTopic.topic),
            selectinload(Story.article_links),
        )
    ).scalars().unique().all()


def _story_ts(s: Story) -> datetime:
    """Best 'entered system' time: earliest of created_at / published_at."""
    cands = [t for t in (s.created_at, s.published_at) if t]
    dt = min(cands) if cands else datetime.now(timezone.utc)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _link_times(s: Story) -> list[datetime]:
    out = []
    for al in s.article_links:
        t = al.created_at
        if t:
            out.append(t if t.tzinfo else t.replace(tzinfo=timezone.utc))
    if not out:
        out = [_story_ts(s)]
    return sorted(out)


# ---------------------------------------------------------------- counts ----

def _tehran_day(dt: datetime) -> datetime:
    """Midnight (Tehran) of the day containing dt, as an aware UTC datetime."""
    local = dt.astimezone(TEHRAN)
    start_local = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_local.astimezone(timezone.utc)


def stats(db: Session, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    stories = _published(db)
    times = sorted(_story_ts(s) for s in stories)

    # Rolling windows (timezone-independent) — also recomputed live in the client
    # from `timeline`, so these are a fallback for the moment of the build.
    def since(hours):
        cut = now - timedelta(hours=hours)
        return sum(1 for t in times if t >= cut)

    # Calendar windows (Tehran)
    today0 = _tehran_day(now)
    yest0 = today0 - timedelta(days=1)
    # week starts Saturday in Iran; find the most recent Saturday <= today
    local_today = now.astimezone(TEHRAN)
    # Python weekday(): Mon=0..Sun=6 → Saturday=5
    days_since_sat = (local_today.weekday() - 5) % 7
    week0 = _tehran_day(now - timedelta(days=days_since_sat))
    lastweek0 = week0 - timedelta(days=7)
    month0 = _tehran_day(now.astimezone(TEHRAN).replace(day=1).astimezone(timezone.utc))

    def between(a, b=None):
        return sum(1 for t in times if t >= a and (b is None or t < b))

    # Daily activity for the last 14 Tehran-days (for the bar chart)
    daily = []
    for i in range(13, -1, -1):
        d0 = today0 - timedelta(days=i)
        d1 = d0 + timedelta(days=1)
        label = d0.astimezone(TEHRAN).strftime("%Y-%m-%d")
        daily.append({"d": label, "n": between(d0, d1)})

    return {
        "total": len(stories),
        "generated_ms": _ms(now),
        "rolling": {"h4": since(4), "h8": since(8), "h12": since(12), "h24": since(24)},
        "calendar": {
            "today": between(today0),
            "yesterday": between(yest0, today0),
            "this_week": between(week0),
            "last_week": between(lastweek0, week0),
            "this_month": between(month0),
        },
        "activity_daily": daily,
        "timeline": [_ms(t) for t in times],
    }


# ------------------------------------------------------------- topic growth ----

def topic_series(db: Session, *, days: int = 14, now: datetime | None = None) -> list[dict]:
    """Per-topic daily story counts over `days`, plus a week-over-week growth %.
    growth% = (stories in last 7d − stories in prior 7d) / max(prior,1) × 100."""
    now = now or datetime.now(timezone.utc)
    stories = _published(db)
    today0 = _tehran_day(now)
    edges = [today0 - timedelta(days=i) for i in range(days - 1, -1, -1)] + [today0 + timedelta(days=1)]

    series: dict[str, dict] = {}
    for s in stories:
        t = _story_ts(s)
        for tl in s.topic_links:
            tp = tl.topic
            if not tp:
                continue
            e = series.setdefault(tp.slug, {
                "slug": tp.slug, "name_fa": tp.name_fa, "name_en": tp.name_en,
                "counts": [0] * days, "total": 0,
            })
            e["total"] += 1
            for i in range(days):
                if edges[i] <= t < edges[i + 1]:
                    e["counts"][i] += 1
                    break

    out = []
    for e in series.values():
        c = e["counts"]
        last7, prev7 = sum(c[-7:]), sum(c[-14:-7]) if days >= 14 else 0
        e["last7"], e["prev7"] = last7, prev7
        e["growth"] = round((last7 - prev7) / max(prev7, 1) * 100) if (last7 or prev7) else 0
        out.append(e)
    # rank by recent activity, then total
    out.sort(key=lambda e: (e["last7"], e["total"]), reverse=True)
    return out


# ------------------------------------------------------ rising / hot signal ----

def _hourly_counts(times: list[datetime], now: datetime, hours: int, bucket_h: int) -> list[int]:
    n = hours // bucket_h
    buckets = [0] * n
    start = now - timedelta(hours=hours)
    for t in times:
        if t < start:
            continue
        idx = int((t - start).total_seconds() // (bucket_h * 3600))
        if 0 <= idx < n:
            buckets[idx] += 1
    return buckets


def momentum(s: Story, now: datetime) -> dict:
    """Coverage velocity for one story.

    velocity   = independent-source arrivals in the last 6h,
    base_rate  = the story's own lifetime arrivals-per-6h (its normal pace),
    ratio      = velocity / base_rate → how many× faster than usual right now.
    A ratio well above 1 means coverage is accelerating (going viral)."""
    lt = _link_times(s)
    first = lt[0]
    age_h = max((now - first).total_seconds() / 3600, 1.0)
    total = len(lt)
    recent6 = sum(1 for t in lt if t >= now - timedelta(hours=6))
    base_6h = max(total / (age_h / 6.0), 0.5)      # expected arrivals per 6h
    ratio = round(recent6 / base_6h, 2)
    # cumulative coverage curve over the last 48h in 3h steps (for the detail chart)
    steps = _hourly_counts(lt, now, hours=48, bucket_h=3)
    cum, run = [], 0
    base_before = sum(1 for t in lt if t < now - timedelta(hours=48))
    run = base_before
    for b in steps:
        run += b
        cum.append(run)
    return {
        "velocity": recent6,
        "ratio": ratio,
        "age_h": round(age_h, 1),
        "total_sources": total,
        "curve": cum,               # cumulative source count, 16 points (48h/3h)
        "spark": steps,             # arrivals per 3h, 16 points
    }


def classify_rising_hot(metrics: list[dict]) -> None:
    """Mutate each metric dict in-place adding `rising` / `hot` booleans.

    rising : coverage clearly accelerating (ratio ≥ 1.6) with real recent volume,
    hot    : rising AND in the extreme tail versus every other active story today
             (top decile of ratio, or ≥ 3× with heavy recent volume).
    Thresholds adapt to the day's distribution so a quiet day still surfaces its
    fastest-moving story, and a busy day doesn't flag everything."""
    active = [m for m in metrics if m["velocity"] >= 2]
    ratios = sorted((m["ratio"] for m in active), reverse=True)
    p90 = ratios[max(0, int(len(ratios) * 0.10) - 1)] if ratios else 999
    hot_cut = max(p90, 2.2)
    for m in metrics:
        m["rising"] = m["ratio"] >= 1.6 and m["velocity"] >= 2
        m["hot"] = m["rising"] and (
            (m["velocity"] >= 3 and m["ratio"] >= hot_cut) or
            (m["velocity"] >= 4 and m["ratio"] >= 3.0)
        )
