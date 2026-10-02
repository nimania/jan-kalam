"""Turn extracted periodical page candidates into safe Persian press cards.

Uses the project's configured AI provider. Raw copyrighted page text stays in
the workflow workspace; only headline/summary/key points and provenance are
published. Existing archive is merged by id and capped.
"""
from __future__ import annotations
import json, os
from datetime import datetime, timezone
from pathlib import Path
from app.ai.providers import get_provider

ROOT=Path("periodicals")
IN=ROOT/"articles.json"
ARCHIVE=ROOT/"archive.json"
PUBLIC=Path("public/data/periodicals.json")
MAX_ITEMS=300

SYSTEM="""You are a Persian news editor. Return JSON only. Do not reproduce the source article.
Create a faithful Persian headline and concise original summary from the supplied page candidate.
Do not add facts. If the page is not a coherent article/news item, set publish=false.
Output: {"publish":true|false,"headline_fa":"","summary_fa":"","key_points_fa":["",""]}."""

def main():
    rows=json.loads(IN.read_text(encoding="utf-8")) if IN.exists() else []
    old=json.loads(ARCHIVE.read_text(encoding="utf-8")) if ARCHIVE.exists() else []
    provider=get_provider()
    if getattr(provider,"name","mock")=="mock":
        print("periodicals: AI provider unavailable; no raw text will be published")
        fresh=[]
    else:
        fresh=[]
        for x in rows[:40]:
            try:
                r=provider.generate(system=SYSTEM,user=("Publisher: "+x["publisher"]+"\nText:\n"+x["text"][:10000]),context={"articles":[]}).data
                if not r.get("publish") or not r.get("headline_fa") or not r.get("summary_fa"):
                    continue
                fresh.append({
                    "id":x["id"],"publisher":x["publisher"],
                    "headline_fa":str(r["headline_fa"]).strip(),
                    "summary_fa":str(r["summary_fa"]).strip(),
                    "key_points_fa":[str(v).strip() for v in (r.get("key_points_fa") or [])[:4] if str(v).strip()],
                    "telegram_post_url":x.get("telegram_post_url"),
                    "transport":x.get("transport"),"page":x.get("page"),
                    "published_at":datetime.now(timezone.utc).isoformat(),
                })
            except Exception as exc:
                print("periodicals: synthesis skipped",x.get("id"),str(exc)[:160])
    merged={x["id"]:x for x in old if x.get("id")}
    for x in fresh: merged[x["id"]]=x
    out=list(merged.values())[-MAX_ITEMS:]
    ROOT.mkdir(exist_ok=True); ARCHIVE.write_text(json.dumps(out,ensure_ascii=False),encoding="utf-8")
    PUBLIC.parent.mkdir(parents=True,exist_ok=True); PUBLIC.write_text(json.dumps(out,ensure_ascii=False),encoding="utf-8")
    print(f"periodicals: published archive {len(out)} items (+{len(fresh)} new)")

if __name__=="__main__": main()
