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
SITE_IN=ROOT/"site_articles.json"
ARCHIVE=ROOT/"archive.json"
PUBLIC=Path("public/data/periodicals.json")
MAX_ITEMS=300

SYSTEM="""You are a meticulous Persian periodical editor. Return JSON only.
From the supplied PDF page candidate, determine whether it contains a coherent article.
If it does, create a faithful Persian rendering that preserves the article's claims,
qualifications, sequence and attribution without adding facts. It must read naturally in
Persian and must not invent missing text. When a page is only a fragment that clearly
continues elsewhere, be conservative. Classify it into one useful section such as
سیاست، اقتصاد، جهان، ایران، فناوری، فرهنگ، جامعه، علم، کسب‌وکار or سبک زندگی.
Output:
{"publish":true|false,"headline_fa":"","summary_fa":"","body_fa":"",
 "section_fa":"","key_points_fa":["",""]}.
body_fa should be a detailed Persian rendering of the available article text, not a short card."""

def main():
    rows=json.loads(IN.read_text(encoding="utf-8")) if IN.exists() else []
    if SITE_IN.exists():
        rows += json.loads(SITE_IN.read_text(encoding="utf-8"))
    old=json.loads(ARCHIVE.read_text(encoding="utf-8")) if ARCHIVE.exists() else []
    provider=get_provider()
    if getattr(provider,"name","mock")=="mock":
        print("periodicals: AI provider unavailable; no raw text will be published")
        fresh=[]
    else:
        fresh=[]
        covers=[x for x in rows if x.get("kind")=="issue_cover"]
        article_rows=[x for x in rows if x.get("kind")!="issue_cover"]
        for x in article_rows[:40]:
            try:
                r=provider.generate(system=SYSTEM,user=("Publisher: "+x["publisher"]+"\nText:\n"+x["text"][:10000]),context={"articles":[]}).data
                if not r.get("publish") or not r.get("headline_fa") or not r.get("summary_fa"):
                    continue
                fresh.append({
                    "id":x["id"],"publisher":x["publisher"],
                    "headline_fa":str(r["headline_fa"]).strip(),
                    "summary_fa":str(r["summary_fa"]).strip(),
                    "body_fa":str(r.get("body_fa") or "").strip(),
                    "section_fa":str(r.get("section_fa") or "سایر").strip(),
                    "key_points_fa":[str(v).strip() for v in (r.get("key_points_fa") or [])[:4] if str(v).strip()],
                    "telegram_post_url":x.get("telegram_post_url"),
                    "article_url":x.get("article_url"),
                    "transport":x.get("transport"),"page":x.get("page"),
                    "image_url":x.get("image_url"),
                    "issue_key":f'{x.get("publisher","")}:{x.get("transport","")}:{x.get("telegram_message_id","")}',
                    "cover_url":next((v.get("cover_url") for v in sorted(covers,key=lambda z:abs(int(z.get("telegram_message_id",0))-int(x.get("telegram_message_id",0)))) if v.get("publisher")==x.get("publisher") and abs(int(v.get("telegram_message_id",0))-int(x.get("telegram_message_id",0)))<=3),None),
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
