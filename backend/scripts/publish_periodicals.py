"""Turn extracted periodical page candidates into safe Persian press cards.

Uses the project's configured AI provider. Raw copyrighted page text stays in
the workflow workspace; only headline/summary/key points and provenance are
published. Existing archive is merged by id and capped.
"""
from __future__ import annotations
import json, os, re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from app.ai.providers import get_provider

ROOT=Path("periodicals")
IN=ROOT/"articles.json"
SITE_IN=ROOT/"site_articles.json"
ARCHIVE=ROOT/"archive.json"
PUBLIC=Path("public/data/periodicals.json")
DIRECTORY=Path("public/data/press-directory.json")
MAX_ITEMS=800

SYSTEM="""You are a meticulous Persian periodical editor and SEO writer. Return JSON only.
The input may contain a full source article, an RSS excerpt, or a PDF page candidate.

Create an original Persian article based on the source facts and arguments. Do not copy
the source sentence-by-sentence or imitate its exact wording/structure. Preserve claims,
qualifications, chronology and attribution; do not add facts. For Persian sources, rewrite
into a clear independent article. For non-Persian sources, translate and synthesize faithfully.
The result should be useful on its own while clearly attributing the original publisher.

SEO requirements:
- headline_fa: very short, accurate and natural; normally 3-6 Persian words. Remove
  explanatory clauses, subtitles and filler. Keep only the central subject/action.
- seo_title_fa: concise and search-friendly; preferably <= 45 Persian characters.
- meta_description_fa: 120-165 Persian characters when practical.
- body_fa: structured, coherent and substantially detailed. When the source contains enough
  material, you may make the article up to roughly three times more detailed than the former
  concise format: typically 6-12 purposeful paragraphs (about 800-1400 Persian words for a
  rich long-form source). Short sources must stay short. Never pad for length.
- Every paragraph must add a distinct fact, argument, example, context point or consequence.
  Do not repeat the lead, summary, key points or another paragraph in different words.
- summary_fa should be a compact lead, not a duplicate of the first body paragraph.
- key_points_fa: 3-5 concrete points that complement rather than repeat the body verbatim.
- seo_keywords_fa: 3-8 short relevant phrases.
- section_fa: one useful section such as سیاست، اقتصاد، جهان، ایران، فناوری، فرهنگ،
  جامعه، علم، کسب‌وکار or سبک زندگی.
- If the article announces or describes a real-world event, extract the event metadata.
  Keep the Persian display wording in date_fa/time_fa/location_fa/address_fa. When the
  source gives enough information to identify an exact time, also provide start_iso and
  end_iso as ISO-8601 with timezone offset. For Iranian events use Asia/Tehran unless the
  source clearly indicates another timezone. Never invent a missing date, time or address.

Output:
{"publish":true|false,"headline_fa":"","seo_title_fa":"","meta_description_fa":"",
 "summary_fa":"","body_fa":"","section_fa":"","key_points_fa":[""],
 "seo_keywords_fa":[""],
 "event":{"is_event":false,"date_fa":"","time_fa":"","start_iso":"","end_iso":"",
          "timezone":"","location_fa":"","address_fa":""}}.
"""


def _persian_text(s):
    return bool(re.search(r"[\u0600-\u06ff]", str(s or "")))

def _fallback_event(text: str) -> dict:
    text=re.sub(r"\s+"," ",str(text or "")).strip()
    out={"is_event":False,"date_fa":"","time_fa":"","start_iso":"","end_iso":"","timezone":"","location_fa":"","address_fa":""}
    if not text or not re.search(r"(نشست|مراسم|رونمایی|نمایش فیلم|شب‌های|شب |برگزار|همایش|سخنرانی)",text):
        return out
    months="فروردین|اردیبهشت|خرداد|تیر|مرداد|امرداد|شهریور|مهر|آبان|آذر|دی|بهمن|اسفند"
    days="شنبه|یکشنبه|یک‌شنبه|دوشنبه|سه‌شنبه|سه شنبه|چهارشنبه|پنجشنبه|پنج‌شنبه|جمعه"
    dm=re.search(rf"((?:{days})\s+[۰-۹0-9]+\s+(?:{months})\s+[۰-۹0-9]{{4}})",text)
    if dm: out["date_fa"]=dm.group(1).strip()
    tm=re.search(r"ساعت\s+([^،.]{1,28}?)(?=\s+(?:روز|در|با|برگزار|آغاز)|[،.])",text)
    if tm: out["time_fa"]=tm.group(1).strip()
    am=re.search(r"(?:نشانی|آدرس)\s*[:：]\s*([^\n.]{5,160})",text)
    if am: out["address_fa"]=am.group(1).strip(" ،؛")
    lm=re.search(r"((?:عمارت|خانۀ|خانهٔ|خانه|دانشگاه|مؤسسۀ|مؤسسه|موسسه|کتابفروشی|شهرکتاب|تالار|مرکز|فرهنگسرا)\s+[^،.]{2,110})",text)
    if lm: out["location_fa"]=lm.group(1).strip(" ،؛")
    out["is_event"]=bool(out["date_fa"] or out["time_fa"] or out["location_fa"] or out["address_fa"])
    return out

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
    raw_source=str(x.get("source_text") or x.get("text") or "")
    excerpt=re.sub(r"\\s+"," ",str(x.get("text") or "")).strip()
    excerpt=re.sub(r"\\s*\\[(?:…|\\.\\.\\.)\\]\\s*$","",excerpt).strip()
    # RSS descriptions are already source-authored summaries/excerpts. Keep them
    # short and clearly attributed rather than replacing them with a generic notice.
    body=""
    summary=excerpt[:1400].strip()
    if len(excerpt)>1400: summary=summary.rstrip()+"…"
    if len(summary)>360:
        cut=max(summary.rfind("。",0,360),summary.rfind("؟",0,360),summary.rfind("!",0,360),summary.rfind(".",0,360))
        summary=(summary[:cut+1] if cut>140 else summary[:360].rstrip()+"…")
    if not summary:
        summary=f"این مطلب در {publisher} منتشر شده است. برای خواندن متن کامل به منبع اصلی مراجعه کنید."
    return {
        "id":x["id"],"publisher":publisher,
        "title_original":title,
        "source_lang":x.get("lang"),
        "headline_fa":title,
        "summary_fa":summary,
        "body_fa":body,
        "section_fa":"سایر",
        "key_points_fa":[],
        "telegram_post_url":x.get("telegram_post_url"),
        "article_url":x.get("article_url"),
        "source_url":x.get("article_url"),
        "source_published_at":x.get("source_published_at"),
        "transport":x.get("transport"),"page":x.get("page"),
        "image_url":x.get("image_url"),
        "issue_key":f'{publisher}:article:{x.get("id","")}',
        "cover_url":None,
        "published_at":datetime.now(timezone.utc).isoformat(),
        "enrichment_state":"metadata_fallback",
    }

def select_fair_site_rows(site_rows, old_by_id, old, limit=16):
    """Choose AI work across publishers instead of by raw feed order."""
    done_counts=Counter(
        x.get("publisher") for x in old
        if x.get("publisher") and x.get("enrichment_state") in {"ai","ai_fulltext"}
    )
    by_pub=defaultdict(list); pub_scope={}; pub_order={}
    for idx,x in enumerate(site_rows):
        p=x.get("publisher") or ""
        if not p: continue
        by_pub[p].append(x); pub_scope[p]=x.get("scope"); pub_order.setdefault(p,idx)
    scope_priority={"iran-agency":0,"iran-paper":0,"diaspora":1,"world":2,"iran-magazine":3}
    pubs=sorted(by_pub,key=lambda p:(done_counts.get(p,0),scope_priority.get(pub_scope.get(p),4),pub_order[p]))
    chosen=[]
    # First pass: one best unfinished item per source.
    for p in pubs:
        candidates=sorted(
            by_pub[p],
            key=lambda x:(
                old_by_id.get(x.get("id"),{}).get("enrichment_state")=="ai_fulltext",
                not bool(x.get("source_text")),
                old_by_id.get(x.get("id"),{}).get("enrichment_state") in {"ai","ai_fulltext"},
            )
        )
        x=next((z for z in candidates if old_by_id.get(z.get("id"),{}).get("enrichment_state")!="ai_fulltext"),None)
        if x: chosen.append(x)
        if len(chosen)>=limit: return chosen
    # Second pass: use remaining budget for another unfinished item per source.
    seen={x.get("id") for x in chosen}
    for p in pubs:
        x=next((z for z in by_pub[p] if z.get("id") not in seen and old_by_id.get(z.get("id"),{}).get("enrichment_state")!="ai_fulltext"),None)
        if x: chosen.append(x)
        if len(chosen)>=limit: break
    return chosen

def main():
    rows=json.loads(IN.read_text(encoding="utf-8")) if IN.exists() else []
    if SITE_IN.exists():
        rows += json.loads(SITE_IN.read_text(encoding="utf-8"))
    old=json.loads(ARCHIVE.read_text(encoding="utf-8")) if ARCHIVE.exists() else []
    old_by_id={x.get("id"):x for x in old if x.get("id")}
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
    # Publish a small newest slice from every Persian source immediately, but
    # never replace a previously AI-enriched article with a metadata fallback.
    fallback_counts=Counter()
    for x in site_rows:
        if fallback_counts[x.get("publisher")]>=4: continue
        prev=old_by_id.get(x.get("id"),{})
        if prev.get("enrichment_state") in {"ai","ai_fulltext"}: continue
        fb=fallback_site_card(x)
        if fb:
            fresh.append(fb)
            metadata_ids.add(x.get("id"))
            fallback_counts[x.get("publisher")]+=1

    # AI budget is allocated fairly across publishers; news/papers are currently
    # prioritized, then diaspora/world sources, then magazines.
    ai_site_rows=select_fair_site_rows(site_rows,old_by_id,old,limit=16)
    article_rows=(ai_site_rows + pdf_rows[:4])[:20]

    if getattr(provider,"name","mock")=="mock":
        print("periodicals: AI provider unavailable; Persian RSS metadata cards already published")
    else:
        consecutive_provider_errors=0
        for idx,x in enumerate(article_rows):
            try:
                prompt_kind = "full source article" if x.get("source_text") else ("RSS/site article metadata or snippet" if x.get("kind")=="site_feed" else "PDF page candidate")
                source_text=(x.get("source_text") or x.get("text") or "")[:24000]
                r=provider.generate(system=SYSTEM,user=("Input type: "+prompt_kind+"\nPublisher: "+x["publisher"]+"\nOriginal title: "+str(x.get("title_original") or "")+"\nSource URL: "+str(x.get("article_url") or x.get("telegram_post_url") or "")+"\nText:\n"+source_text),context={"articles":[]}).data
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
                    "seo_title_fa":str(r.get("seo_title_fa") or r["headline_fa"]).strip(),
                    "meta_description_fa":str(r.get("meta_description_fa") or r["summary_fa"]).strip(),
                    "summary_fa":str(r["summary_fa"]).strip(),
                    "body_fa":str(r.get("body_fa") or "").strip(),
                    "section_fa":str(r.get("section_fa") or "سایر").strip(),
                    "key_points_fa":[str(v).strip() for v in (r.get("key_points_fa") or [])[:5] if str(v).strip()],
                    "seo_keywords_fa":[str(v).strip() for v in (r.get("seo_keywords_fa") or [])[:8] if str(v).strip()],
                    "event":({
                        "is_event":bool((r.get("event") or {}).get("is_event")),
                        "date_fa":str((r.get("event") or {}).get("date_fa") or "").strip(),
                        "time_fa":str((r.get("event") or {}).get("time_fa") or "").strip(),
                        "start_iso":str((r.get("event") or {}).get("start_iso") or "").strip(),
                        "end_iso":str((r.get("event") or {}).get("end_iso") or "").strip(),
                        "timezone":str((r.get("event") or {}).get("timezone") or "").strip(),
                        "location_fa":str((r.get("event") or {}).get("location_fa") or "").strip(),
                        "address_fa":str((r.get("event") or {}).get("address_fa") or "").strip(),
                    }),
                    "telegram_post_url":x.get("telegram_post_url"),
                    "article_url":x.get("article_url"),
                    "source_url":x.get("article_url") or x.get("telegram_post_url"),
                    "source_published_at":x.get("source_published_at"),
                    "transport":x.get("transport"),"page":x.get("page"),
                    "image_url":x.get("image_url"),
                    "issue_key":(f'{x.get("publisher","")}:article:{x.get("id","")}' if x.get("kind")=="site_feed" else f'{x.get("publisher","")}:{x.get("transport","")}:{x.get("telegram_message_id","")}'),
                    "cover_url":next((v.get("cover_url") for v in sorted(covers,key=lambda z:abs(int(z.get("telegram_message_id",0))-int(x.get("telegram_message_id",0)))) if v.get("publisher")==x.get("publisher") and abs(int(v.get("telegram_message_id",0))-int(x.get("telegram_message_id",0)))<=3),None),
                    "published_at":datetime.now(timezone.utc).isoformat(),
                    "enrichment_state":("ai_fulltext" if x.get("source_text") else "ai"),
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
    out=sorted(
        merged.values(),
        key=lambda x:str(x.get("source_published_at") or x.get("published_at") or ""),
        reverse=True,
    )[:MAX_ITEMS]
    ROOT.mkdir(exist_ok=True); ARCHIVE.write_text(json.dumps(out,ensure_ascii=False),encoding="utf-8")
    PUBLIC.parent.mkdir(parents=True,exist_ok=True); PUBLIC.write_text(json.dumps(out,ensure_ascii=False),encoding="utf-8")
    directory={}
    for x in out:
        p=str(x.get("publisher") or "").strip()
        if not p: continue
        row=directory.setdefault(p,{"source_name":p,"count":0,"latest_at":None})
        row["count"]+=1
        stamp=x.get("source_published_at") or x.get("published_at")
        if stamp and (not row["latest_at"] or str(stamp)>str(row["latest_at"])):
            row["latest_at"]=stamp
    DIRECTORY.write_text(
        json.dumps(sorted(directory.values(),key=lambda x:(-x["count"],x["source_name"])),ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"periodicals: published archive {len(out)} items from {len(directory)} publishers (+{len(fresh)} new)")

if __name__=="__main__": main()
