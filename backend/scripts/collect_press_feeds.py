"""Collect recent article metadata from validated RSS/Atom feeds in the press registry.

Publishes only feed-supplied metadata/snippets and provenance. It does not copy
full article bodies. These rows are merged into Jan-e Jaraid periodical cards by
publish_periodicals.py.
"""
from __future__ import annotations
import hashlib, html, json, re, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from bs4 import BeautifulSoup
from app.ingestion.service import _EXCLUDED_SOURCE_TERMS, _EXCLUDED_SOURCE_DOMAINS

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

def excluded(src):
    name=(src.get("source_name") or "").casefold()
    urls=" ".join(str(src.get(k) or "").casefold() for k in ("homepage","feed_url"))
    # Keep the standalone press collectors under the same source-level editorial denylist.
    if any(t.casefold() in name for t in _EXCLUDED_SOURCE_TERMS): return True
    return any(d in urls for d in _EXCLUDED_SOURCE_DOMAINS)

def html_candidates(src):
    """Fallback for monitored sites that expose articles but advertise no RSS."""
    home=src.get("homepage")
    if not home: return []
    req=urllib.request.Request(home,headers={"User-Agent":UA})
    raw=urllib.request.urlopen(req,timeout=25).read(2_000_000)
    soup=BeautifulSoup(raw,"html.parser")
    host=urllib.parse.urlparse(home).netloc.lower().removeprefix("www.")
    seen=set(); out=[]
    bad_parts=("/tag/","/category/","/author/","/page/","/search","/login","/contact","/about")
    for a in soup.find_all("a",href=True):
        title=clean(a.get_text(" ",strip=True))
        if len(title)<18 or len(title)>240: continue
        link=urllib.parse.urljoin(home,a["href"])
        u=urllib.parse.urlparse(link)
        if u.scheme not in {"http","https"}: continue
        if u.netloc.lower().removeprefix("www.") != host: continue
        if any(p in u.path.lower() for p in bad_parts): continue
        if u.path in {"","/"} or link in seen: continue
        seen.add(link)
        ident=hashlib.sha1((src["source_name"]+"|"+link).encode()).hexdigest()
        out.append({"id":"site:"+ident,"publisher":src["source_name"],"kind":"site_feed",
          "title_original":title,"text":title,"article_url":link,
          "transport":"site:"+home,"page":None,"lang":src.get("lang"),
          "source_homepage":home})
        if len(out)>=20: break
    return out

def main():
    health=json.loads(HEALTH.read_text(encoding="utf-8")) if HEALTH.exists() else []
    rows=[]
    for src in health:
        if src.get("state")!="active" or excluded(src): continue
        feed=src.get("feed_url")
        if not feed:
            try:
                found=html_candidates(src); rows.extend(found)
                print("press sites:",src.get("source_name"),"collected",len(found),"HTML candidates")
            except Exception as exc:
                print("press sites:",src.get("source_name"),"failed:",str(exc)[:180])
            continue
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
                  "transport":"rss:"+feed,"page":None,"lang":src.get("lang"),
                  "source_homepage":src.get("homepage")})
        except Exception as exc:
            print("press feeds:",src.get("source_name"),"failed:",str(exc)[:180])
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(rows,ensure_ascii=False),encoding="utf-8")
    print("press feeds: collected",len(rows),"article candidates")

if __name__=="__main__": main()
