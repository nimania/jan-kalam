"""Build a real Jan-e Jaraid issue overview from public web metadata.

No copyrighted PDF/full text is republished. Public issue/article metadata is
used to create an original Persian issue overview with the project's AI provider.
"""
from __future__ import annotations
import json,re
from pathlib import Path
import httpx
from bs4 import BeautifulSoup
from app.ai.providers import get_provider
from app.core.config import settings

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"public"/"data"/"periodicals.json"
SOURCES=[
 "https://shows.acast.com/the-economist-weekly-edition/episodes",
 "https://www.hindustantimes.com/theeconomist",
]

def public_context()->str:
    parts=[]
    for url in SOURCES:
        r=httpx.get(url,timeout=30,follow_redirects=True,headers={"User-Agent":settings.ingest_user_agent})
        r.raise_for_status()
        text=" ".join(BeautifulSoup(r.text,"html.parser").stripped_strings)
        parts.append(f"SOURCE {url}\n{text[:18000]}")
    return "\n\n".join(parts)

def run()->dict:
    OUT.parent.mkdir(parents=True,exist_ok=True)
    if not settings.ai_api_key:
        print("Jan-e Jaraid skipped: AI_API_KEY missing"); return {"articles":0}
    context=public_context()
    provider=get_provider()
    system="""Return JSON only with headline_fa, summary_fa, body_fa, issue_date.
Write a neutral Persian OVERVIEW of the latest completed weekly issue of The
Economist represented in the supplied public metadata. This is an original
overview, not a translation. Do not invent article details beyond the metadata.
body_fa should be detailed but only as detailed as the evidence permits. Clearly
attribute arguments/opinions to The Economist."""
    user="Create the Jan-e Jaraid issue overview from these public sources:\n\n"+context
    res=provider.generate(system=system,user=user,context={})
    d=res.data
    date=str(d.get("issue_date") or "2026-09-26")[:10]
    row={"id":f"economist-{date}","publisher":"The Economist","issue":date,
      "published_at":f"{date}T00:00:00Z","title_original":f"The Economist — {date}",
      "headline_fa":d.get("headline_fa") or "مرور شماره تازه اکونومیست",
      "summary_fa":d.get("summary_fa") or "مرور فارسی شماره تازه اکونومیست",
      "body_fa":d.get("body_fa") or d.get("summary_fa") or "",
      "content_mode":"issue_overview",
      "source_url":"https://www.economist.com/"}
    OUT.write_text(json.dumps([row],ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    print(f"Jan-e Jaraid: exported {date} via {res.model}")
    return {"articles":1,"issue":date}

if __name__=="__main__": run()
