"""Generic site monitor for Jan-e Jaraid registry.

Probes every registered source, discovers advertised RSS/Atom feeds and also
validates a small set of conventional feed endpoints.
"""
from __future__ import annotations
import json, re, time, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from app.press_registry import PRESS_REGISTRY
from app.ingestion.service import _EXCLUDED_SOURCE_TERMS, _EXCLUDED_SOURCE_DOMAINS

OUT = Path("public/data/press-registry-health.json")
UA = "Mozilla/5.0 (compatible; JanKalamPressMonitor/1.1; +https://nimania.github.io/jan-kalam/)"
PINNED_FEEDS = {
    # Verified official feeds. Keep these independent from homepage discovery so
    # transient markup/redirect changes cannot silently disconnect a source.
    "بخارا": "https://bukharamag.com/feed",
}

def excluded(name: str, url: str) -> bool:
    n=(name or "").casefold(); u=(url or "").casefold()
    return any(t.casefold() in n for t in _EXCLUDED_SOURCE_TERMS) or any(d in u for d in _EXCLUDED_SOURCE_DOMAINS)

def fetch(url: str, timeout: int = 20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept":"text/html,application/xhtml+xml,application/rss+xml,application/atom+xml;q=0.9,*/*;q=0.7"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.geturl(), r.status, r.headers.get("content-type",""), r.read(1_000_000).decode("utf-8","replace")

def looks_feed(ctype: str, body: str) -> bool:
    head=body[:2500].lower()
    return "xml" in (ctype or "").lower() or "<rss" in head or "<feed" in head or "<rdf:rdf" in head

def discover_feed(base: str, html: str) -> list[str]:
    found=[]
    for tag in re.findall(r"<link\b[^>]*>", html, re.I):
        if not re.search(r'rel=["\'][^"\']*alternate', tag, re.I): continue
        if not re.search(r'type=["\']application/(?:rss\+xml|atom\+xml)', tag, re.I): continue
        mm=re.search(r'href=["\']([^"\']+)', tag, re.I)
        if mm: found.append(urllib.parse.urljoin(base, mm.group(1)))
    root=urllib.parse.urljoin(base, "/")
    found += [urllib.parse.urljoin(root,"feed"), urllib.parse.urljoin(root,"feed/"), urllib.parse.urljoin(root,"rss.xml")]
    return list(dict.fromkeys(found))

def main():
    rows=[]
    for name, homepage, lang, scope in PRESS_REGISTRY:
        started=time.time()
        row={"source_name":name,"homepage":homepage,"lang":lang,"scope":scope,"state":"error","method":"site","collector_mode":"none","feed_url":None,"http_status":None,"last_error":None}
        if excluded(name,homepage):
            row.update(state="excluded",collector_mode="denylist",last_error="source denylist")
            rows.append(row); continue
        try:
            final,status,ctype,body=fetch(homepage)
            row["homepage"]=final; row["http_status"]=status
            feed=None
            candidates=[]
            if PINNED_FEEDS.get(name): candidates.append(PINNED_FEEDS[name])
            candidates += discover_feed(final,body)
            for candidate in dict.fromkeys(candidates):
                if excluded(name,candidate): continue
                try:
                    _,fs,fc,fb=fetch(candidate, 6)
                    if fs < 400 and looks_feed(fc,fb): feed=candidate; break
                except Exception: pass
            if feed:
                row.update(method="rss",collector_mode="rss",feed_url=feed,state="active")
            elif status < 400 and len(body)>500:
                row.update(state="active",collector_mode="html")
            else:
                row.update(state="empty",collector_mode="none")
        except Exception as exc:
            row["last_error"]=str(exc)[:240]
        row["last_run"]=datetime.now(timezone.utc).isoformat()
        row["duration_ms"]=round((time.time()-started)*1000)
        rows.append(row)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding="utf-8")
    print("press monitor:",sum(x["state"]=="active" for x in rows),"active /",len(rows),"total; rss",sum(x.get("collector_mode")=="rss" for x in rows),"html",sum(x.get("collector_mode")=="html" for x in rows))

if __name__=="__main__": main()
