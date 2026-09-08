"""Export the published stories as STATIC JSON + a static front-end.

Run after the pipeline (ingest → cluster → rank → synthesize). Produces a
self-contained `public/` folder that any free static host (GitHub Pages,
Cloudflare Pages) can serve — no backend needed at serve time.

    python -m scripts.export_static
"""
from __future__ import annotations

import json
import os
import shutil

from app.db.session import SessionLocal
from app.repositories import stories as story_repo
from app.repositories import topics as topic_repo
from app.services import ask as ask_svc
from app.services import stories as story_svc

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


def run() -> None:
    db = SessionLocal()
    os.makedirs(os.path.join(DATA, "story"), exist_ok=True)

    feed = story_svc.get_feed(db, limit=60, offset=0, category=None)
    _write(os.path.join(DATA, "stories.json"),
           [c.model_dump(mode="json") for c in feed.items])

    for card in feed.items:
        detail = story_svc.get_detail(db, card.id)
        story = story_repo.get(db, card.id)
        d = detail.model_dump(mode="json")
        d["asks"] = [{"q": q, "a": ask_svc.answer(story, q).answer_fa} for q in QUESTIONS]
        _write(os.path.join(DATA, "story", f"{card.id}.json"), d)

    topics = topic_repo.list_all(db)
    _write(os.path.join(DATA, "topics.json"),
           [{"id": t.id, "slug": t.slug, "name_fa": t.name_fa, "name_en": t.name_en}
            for t in topics])

    from datetime import datetime, timezone
    _write(os.path.join(DATA, "meta.json"),
           {"built": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "count": len(feed.items)})

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

    print(f"exported {len(feed.items)} stories to ./{OUT}")


if __name__ == "__main__":
    run()
