"""Collect recent article metadata from validated RSS/Atom feeds in the press registry.

Publishes only feed-supplied metadata/snippets and provenance. It does not copy
full article bodies. These rows are merged into Jan-e Jaraid periodical cards by
publish_periodicals.py.
"""
from __future__ import annotations
import hashlib, html, json, re, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

HEALTH=Path("public/data/press-registry-health.json")
OUT=Path("periodicals/site_articles.json")
UA="Mozilla/5.0 (compatible; JanKalamPressFeeds/1.0; +https://nimania.github.io/jan-kalam/)"

def clean(s):
    s=re.sub(r"<[^>]+>"," ",s or "")
    return re.sub(r"\s+"," ",html.unescape(s)).strip()

def first_text(el,names):
    for child in list(el):
        if child.tag.split("}")[-1].lower() in names and (child.text or "").strip():
            return clean(child.text)
    return ""

def main():
    health=json.loads(HEALTH.read_text(encoding="utf-8")) if HEALTH.exists() else []
    rows=[]
    for src in health:
        feed=src.get("feed_url")
        if src.get("state")!="active" or not feed: continue
        try:
            req=urllib.request.Request(feed,headers={"User-Agent":UA})
            raw=urllib.request.urlopen(req,timeout=25).read(2_000_000)
            root=ET.fromstring(raw)
            items=[x for x in root.iter() if x.tag.split("}")[-1].lower() in {"item","entry"}][:20]
            for it in items:
                title=first_text(it,{"title"})
                summary=first_text(it,{"description","summary","content","encoded"})
                link=first_text(it,{"link","guid"})
                if not link:
                    for ch in list(it):
                        if ch.tag.split("}")[-1].lower()=="link" and ch.attrib.get("href"):
                            link=ch.attrib["href"]; break
                link=urllib.parse.urljoin(src.get("homepage") or feed,link)
                if not title or not link: continue
                ident=hashlib.sha1((src["source_name"]+"|"+link).encode()).hexdigest()
                rows.append({"id":"site:"+ident,"publisher":src["source_name"],"kind":"site_feed",
                  "title_original":title,"text":summary[:5000],"article_url":link,
                  "transport":"rss:"+feed,"page":None})
        except Exception as exc:
            print("press feeds:",src.get("source_name"),"failed:",str(exc)[:180])
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(rows,ensure_ascii=False),encoding="utf-8")
    print("press feeds: collected",len(rows),"article candidates")

if __name__=="__main__": main()
