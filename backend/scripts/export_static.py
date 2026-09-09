"""Export the published stories as STATIC JSON + a static front-end.

Run after the pipeline (ingest → cluster → rank → synthesize). Produces a
self-contained `public/` folder that any free static host (GitHub Pages,
Cloudflare Pages) can serve — no backend needed at serve time.

Also enriches each story with:
  • our own automated credibility signal (independent sources + agreement),
  • a best-effort link to a matching Factnameh professional fact-check,
and writes the trends board (بورس اخبار) and the Factnameh section.

    python -m scripts.export_static
"""
from __future__ import annotations

import json
import os
import shutil

from app.analytics import google_trends as gt_svc
from app.analytics import service as analytics_svc
from app.credibility import compute_credibility
from app.db.session import SessionLocal
from app.factcheck import service as fc_svc
from app.geo import service as geo_svc
from app.prices import service as price_svc
from app.repositories import stories as story_repo
from app.repositories import topics as topic_repo
from app.weather import service as weather_svc
from app.services import ask as ask_svc
from app.services import stories as story_svc
from app.trends import service as trends_svc

OUT = os.environ.get("STATIC_OUT", "public")
DATA = os.path.join(OUT, "data")
WEB_STATIC = os.path.join(os.path.dirname(__file__), "..", "..", "web-static")

# Answers are pre-baked at build time (static host can't run the AI live).
QUESTIONS = [
    "چرا این خبر مهم است؟",
    "منابع مختلف چه می‌گویند؟",
    "چه چیزی هنوز مشخص نیست؟",
    "این موضوع چه ارتباطی با ایران دارد؟",
]


def _write(path: str, obj) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))


def _story_match_texts(detail: dict) -> list[str | None]:
    texts: list[str | None] = [detail.get("headline_fa"), detail.get("summary_fa")]
    for sv in detail.get("source_views", []):
        texts.append(sv.get("original_headline"))
    return texts


def run() -> None:
    db = SessionLocal()
    os.makedirs(os.path.join(DATA, "story"), exist_ok=True)

    factchecks = fc_svc.fetch_factchecks(limit=12)

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    feed = story_svc.get_feed(db, limit=60, offset=0, category=None)
    cards = [c.model_dump(mode="json") for c in feed.items]

    # Build details + per-story trend metrics first; classify rising/hot across
    # the whole set (thresholds are relative to the day), THEN write everything.
    details: dict[str, dict] = {}
    metrics: dict[str, dict] = {}
    for card in cards:
        detail = story_svc.get_detail(db, card["id"])
        story = story_repo.get(db, card["id"])
        d = detail.model_dump(mode="json")
        d["asks"] = [{"q": q, "a": ask_svc.answer(story, q).answer_fa} for q in QUESTIONS]

        cred = compute_credibility(d)
        d["credibility"] = cred

        match = fc_svc.match_story(_story_match_texts(d), factchecks)
        if match:
            d["factcheck"] = match

        geo = geo_svc.classify(
            " ".join(t for t in _story_match_texts(d) + [d.get("what_happened_fa")] if t))
        d["geo"] = geo
        # Trust our geo detection over the AI's Iran-relevance guess: if a specific
        # Iranian province or a national context is found, it IS Iran-related.
        if geo["scope"] in ("local", "national"):
            d["iran_relevance"] = "high"
            card["iran_relevance"] = "high"

        metrics[card["id"]] = analytics_svc.momentum(story, now)
        details[card["id"]] = d

        # compact copies on the feed card so the list can show badges + filter by topic
        card["credibility"] = {"level": cred["level"], "label_fa": cred["label_fa"],
                               "needs_verification": cred["needs_verification"],
                               "disagreements": cred["disagreements"],
                               "independent_sources": cred["independent_sources"]}
        card["topics"] = [{"slug": t["slug"], "name_fa": t["name_fa"]}
                          for t in d.get("topics", [])]
        card["geo"] = geo
        if match:
            card["factcheck"] = {"url": match["url"]}

    analytics_svc.classify_rising_hot(list(metrics.values()))
    for card in cards:
        m = metrics[card["id"]]
        card["trend"] = {"ratio": m["ratio"], "velocity": m["velocity"],
                         "rising": m["rising"], "hot": m["hot"], "spark": m["spark"]}
        d = details[card["id"]]
        d["trend"] = m
        _write(os.path.join(DATA, "story", f"{card['id']}.json"), d)

    _write(os.path.join(DATA, "stories.json"), cards)

    topics = topic_repo.list_all(db)
    _write(os.path.join(DATA, "topics.json"),
           [{"id": t.id, "slug": t.slug, "name_fa": t.name_fa, "name_en": t.name_en}
            for t in topics])

    # Trends board + growth series (+ best-effort Google Trends overlay).
    trends = trends_svc.compute_trends(db)
    series = analytics_svc.topic_series(db, days=14, now=now)
    by_slug = {e["slug"]: e for e in series}
    for t in trends.get("topics", []):
        e = by_slug.get(t["slug"])
        if e:
            t["series"] = e["counts"]
            t["growth"] = e["growth"]
            t["last7"], t["prev7"] = e["last7"], e["prev7"]
    trends["topic_series"] = series
    trends["google"] = gt_svc.fetch([(e["slug"], e["name_fa"]) for e in series[:5]])
    _write(os.path.join(DATA, "trends.json"), trends)

    _write(os.path.join(DATA, "stats.json"), analytics_svc.stats(db, now=now))
    _write(os.path.join(DATA, "factchecks.json"), factchecks)
    _write(os.path.join(DATA, "prices.json"), price_svc.fetch_prices())
    _write(os.path.join(DATA, "weather.json"), weather_svc.fetch_weather())
    _write(os.path.join(DATA, "geo.json"), geo_svc.stats(cards))

    _write(os.path.join(DATA, "meta.json"),
           {"built": now.strftime("%Y-%m-%d %H:%M UTC"),
            "built_iso": now.isoformat(),
            "count": len(cards)})

    db.close()

    # Copy the static front-end (index.html, app.js, styles.css, icons, manifest).
    if os.path.isdir(WEB_STATIC):
        for item in os.listdir(WEB_STATIC):
            src = os.path.join(WEB_STATIC, item)
            dst = os.path.join(OUT, item)
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)

    print(f"exported {len(cards)} stories, {len(factchecks)} fact-checks to ./{OUT}")


if __name__ == "__main__":
    run()
