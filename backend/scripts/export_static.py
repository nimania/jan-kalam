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

from app.credibility import compute_credibility
from app.db.session import SessionLocal
from app.factcheck import service as fc_svc
from app.prices import service as price_svc
from app.repositories import stories as story_repo
from app.repositories import topics as topic_repo
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

    feed = story_svc.get_feed(db, limit=60, offset=0, category=None)
    cards = [c.model_dump(mode="json") for c in feed.items]

    # Build details, enrich, and back-fill the card badges from the same data.
    card_by_id = {c["id"]: c for c in cards}
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

        _write(os.path.join(DATA, "story", f"{card['id']}.json"), d)

        # compact copies on the feed card so the list can show badges
        card["credibility"] = {"level": cred["level"], "label_fa": cred["label_fa"],
                               "needs_verification": cred["needs_verification"]}
        if match:
            card["factcheck"] = {"url": match["url"]}

    _write(os.path.join(DATA, "stories.json"), cards)

    topics = topic_repo.list_all(db)
    _write(os.path.join(DATA, "topics.json"),
           [{"id": t.id, "slug": t.slug, "name_fa": t.name_fa, "name_en": t.name_en}
            for t in topics])

    _write(os.path.join(DATA, "trends.json"), trends_svc.compute_trends(db))
    _write(os.path.join(DATA, "factchecks.json"), factchecks)
    _write(os.path.join(DATA, "prices.json"), price_svc.fetch_prices())

    from datetime import datetime, timezone
    _write(os.path.join(DATA, "meta.json"),
           {"built": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
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
