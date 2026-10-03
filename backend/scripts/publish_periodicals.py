"""Turn extracted periodical page candidates into safe Persian press cards.

Uses the project's configured AI provider. Raw copyrighted page text stays in
the workflow workspace; only headline/summary/key points and provenance are
published. Existing archive is merged by id and capped.
"""
from __future__ import annotations
import json, os, re
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


def _persian_text(s):
    return bool(re.search(r"[\u0600-\u06ff]", str(s or "")))

def fallback_site_card(x):
    """Publish a metadata-only card for trusted Persian RSS when AI is unavailable.

    Never republishes raw article text: only the original title, provenance and a
    short generated notice are exposed. This keeps official RSS sources visible
    without making AI availability a prerequisite for ingestion.
    """
    if x.get("kind")!="site_feed" or not str(x.get("transport") or "").startswith("rss:"):
        return None
    title=str(x.get("title_original") or "").strip()
    if not title or not (_persian_text(title) or str(x.get("lang") or "").lower() in {"fa","fa-ir","persian"}):
        return None
    publisher=str(x.get("publisher") or "این نشریه").strip()
    return {
        "id":x["id"],"publisher":publisher,
        "title_original":title,
        "source_lang":x.get("lang"),
        "headline_fa":title,
        "summary_fa":f"این مطلب در {publisher} منتشر شده است. برای خواندن متن کامل به منبع اصلی مراجعه کنید.",
        "body_fa":"",
        "section_fa":"سایر",
        "key_points_fa":[],
        "telegram_post_url":x.get("telegram_post_url"),
        "article_url":x.get("article_url"),
        "transport":x.get("transport"),"page":x.get("page"),
        "image_url":x.get("image_url"),
        "issue_key":f'{publisher}:article:{x.get("id","")}',
        "cover_url":None,
        "published_at":datetime.now(timezone.utc).isoformat(),
        "enrichment_state":"metadata_fallback",
    }

def main():
    rows=json.loads(IN.read_text(encoding="utf-8")) if IN.exists() else []
    if SITE_IN.exists():
        rows += json.loads(SITE_IN.read_text(encoding="utf-8"))
    old=json.loads(ARCHIVE.read_text(encoding="utf-8")) if ARCHIVE.exists() else []
    provider=get_provider()
    fresh=[]
    covers=[x for x in rows if x.get("kind")=="issue_cover"]
    all_article_rows=[x for x in rows if x.get("kind")!="issue_cover"]
    site_rows=[x for x in all_article_rows if x.get("kind")=="site_feed"]
    pdf_rows=[x for x in all_article_rows if x.get("kind")!="site_feed"]

    # Trusted Persian RSS is metadata-safe and already in the target language.
    # Publish every such item immediately; AI enrichment must never gate presence
    # on a source page.
    metadata_ids=set()
    for x in site_rows:
        fb=fallback_site_card(x)
        if fb:
            fresh.append(fb)
            metadata_ids.add(x.get("id"))

    # AI is reserved for items that actually need transformation/translation.
    ai_site_rows=[x for x in site_rows if x.get("id") not in metadata_ids]
    article_rows=(ai_site_rows[:24] + pdf_rows[:16])[:40]

    if getattr(provider,"name","mock")=="mock":
        print("periodicals: AI provider unavailable; Persian RSS metadata cards already published")
    else:
        consecutive_provider_errors=0
        for idx,x in enumerate(article_rows):
            try:
                prompt_kind = "RSS/site article metadata or snippet" if x.get("kind")=="site_feed" else "PDF page candidate"
                r=provider.generate(system=SYSTEM,user=("Input type: "+prompt_kind+"\nPublisher: "+x["publisher"]+"\nText:\n"+x["text"][:10000]),context={"articles":[]}).data
                consecutive_provider_errors=0
                if not r.get("publish") or not r.get("headline_fa") or not r.get("summary_fa"):
                    fb=fallback_site_card(x)
                    if fb: fresh.append(fb)
                    continue
                fresh.append({
                    "id":x["id"],"publisher":x["publisher"],
                    "title_original":x.get("title_original"),
                    "source_lang":x.get("lang"),
                    "headline_fa":str(r["headline_fa"]).strip(),
                    "summary_fa":str(r["summary_fa"]).strip(),
                    "body_fa":str(r.get("body_fa") or "").strip(),
                    "section_fa":str(r.get("section_fa") or "سایر").strip(),
                    "key_points_fa":[str(v).strip() for v in (r.get("key_points_fa") or [])[:4] if str(v).strip()],
                    "telegram_post_url":x.get("telegram_post_url"),
                    "article_url":x.get("article_url"),
                    "transport":x.get("transport"),"page":x.get("page"),
                    "image_url":x.get("image_url"),
                    "issue_key":(f'{x.get("publisher","")}:article:{x.get("id","")}' if x.get("kind")=="site_feed" else f'{x.get("publisher","")}:{x.get("transport","")}:{x.get("telegram_message_id","")}'),
                    "cover_url":next((v.get("cover_url") for v in sorted(covers,key=lambda z:abs(int(z.get("telegram_message_id",0))-int(x.get("telegram_message_id",0)))) if v.get("publisher")==x.get("publisher") and abs(int(v.get("telegram_message_id",0))-int(x.get("telegram_message_id",0)))<=3),None),
                    "published_at":datetime.now(timezone.utc).isoformat(),
                    "enrichment_state":"ai",
                })
            except Exception as exc:
                consecutive_provider_errors += 1
                print("periodicals: synthesis skipped",x.get("id"),str(exc)[:160])
                fb=fallback_site_card(x)
                if fb: fresh.append(fb)
                # A provider-wide quota outage can otherwise spend tens of minutes
                # retrying every candidate. Preserve PDF safety, but publish safe
                # metadata-only cards for the remaining trusted Persian RSS items.
                if consecutive_provider_errors >= 2:
                    print("periodicals: provider circuit breaker opened; using RSS metadata fallbacks")
                    for y in article_rows[idx+1:]:
                        yfb=fallback_site_card(y)
                        if yfb: fresh.append(yfb)
                    break
    merged={x["id"]:x for x in old if x.get("id")}
    for x in fresh: merged[x["id"]]=x
    out=list(merged.values())[-MAX_ITEMS:]
    ROOT.mkdir(exist_ok=True); ARCHIVE.write_text(json.dumps(out,ensure_ascii=False),encoding="utf-8")
    PUBLIC.parent.mkdir(parents=True,exist_ok=True); PUBLIC.write_text(json.dumps(out,ensure_ascii=False),encoding="utf-8")
    print(f"periodicals: published archive {len(out)} items (+{len(fresh)} new)")

if __name__=="__main__": main()
