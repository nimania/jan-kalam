"""Generic site monitor for Jan-e Jaraid registry.

This is an operational reachability/discovery monitor, not the article
ingestion pipeline.  It probes each registered homepage, discovers RSS/Atom
links when advertised, and records a compact status snapshot consumed by the
static press UI.  Article ingestion remains source-specific until a feed has
been validated.
"""
from __future__ import annotations
import json, re, time, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from app.press_registry import PRESS_REGISTRY

OUT = Path("public/data/press-registry-health.json")
UA = "Mozilla/5.0 (compatible; JanKalamPressMonitor/1.0; +https://nimania.github.io/jan-kalam/)"

def fetch(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept":"text/html,application/xhtml+xml,application/rss+xml,application/atom+xml;q=0.9,*/*;q=0.7"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.geturl(), r.status, r.headers.get("content-type",""), r.read(1_000_000).decode("utf-8","replace")

def discover_feed(base: str, html: str) -> str | None:
    for tag in re.findall(r"<link\b[^>]*>", html, re.I):
        if not re.search(r'rel=["\'][^"\']*alternate', tag, re.I): continue
        if not re.search(r'type=["\']application/(?:rss\+xml|atom\+xml)', tag, re.I): continue
        m=re.search(r'href=["\']([^"\']+)', tag, re.I)
        if m: return urllib.parse.urljoin(base, m.group(1))
    return None

def main():
    rows=[]
    for name, homepage, lang, scope in PRESS_REGISTRY:
        started=time.time()
        row={"source_name":name,"homepage":homepage,"lang":lang,"scope":scope,"state":"error","method":"site","feed_url":None,"http_status":None,"last_error":None}
        try:
            final,status,ctype,body=fetch(homepage)
            row["homepage"]=final; row["http_status"]=status
            feed=discover_feed(final,body)
            if feed:
                row["method"]="rss"; row["feed_url"]=feed
                try:
                    _,fs,fc,fb=fetch(feed)
                    looks_feed=("xml" in fc.lower()) or ("<rss" in fb[:1000].lower()) or ("<feed" in fb[:1000].lower())
                    row["state"]="active" if fs < 400 and looks_feed else "empty"
                except Exception as exc:
                    row["state"]="error"; row["last_error"]="feed: "+str(exc)[:220]
            else:
                row["state"]="active" if status < 400 and len(body)>500 else "empty"
        except Exception as exc:
            row["last_error"]=str(exc)[:240]
        row["last_run"]=datetime.now(timezone.utc).isoformat()
        row["duration_ms"]=round((time.time()-started)*1000)
        rows.append(row)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding="utf-8")
    print("press monitor:",sum(x["state"]=="active" for x in rows),"active /",len(rows),"total")

if __name__=="__main__":
    main()
