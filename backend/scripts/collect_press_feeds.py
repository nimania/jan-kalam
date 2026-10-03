"""Collect recent article metadata from RSS/Atom and source-aware HTML collectors."""
from __future__ import annotations
import hashlib, html, json, re, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from bs4 import BeautifulSoup
from app.ingestion.service import _EXCLUDED_SOURCE_TERMS, _EXCLUDED_SOURCE_DOMAINS

HEALTH=Path("public/data/press-registry-health.json")
OUT=Path("periodicals/site_articles.json")
UA="Mozilla/5.0 (compatible; JanKalamPressFeeds/1.1; +https://nimania.github.io/jan-kalam/)"

ARTICLE_RULES={
 "ترجمان": [r"^/(?!shop(?:/|$)).+"],
 "سپیده دانایی": [r"/magazine/", r"/article/"],
 "مهرنامه": [r"/(?:post|article|content|news)/", r"/\d{3,}"],
 "دالان": [r"/(?:post|article|notes?|magazine)/", r"/\d{3,}"],
 "اندیشه پویا": [r"/(?:post|article|content|news)/", r"/\d{3,}"],
 "آنگاه": [r"/\d{3,}/"],
 "روزآروز": [r"/(?:post|article|content|news)/", r"/\d{3,}"],
 "بخارا": [r"/14\d{2}\.\d{2}\.\d+\.html$"],
 "چشم‌انداز ایران": [r"/(?:post|article|content|news)/", r"/\d{3,}"],
 "آزما": [r"/(?:post|article|content|news)/", r"/\d{3,}"],
 "آگاهی نو": [r"/(?:post|article|content|news)/", r"/\d{3,}"],
 "کتابنامه آگاهی نو": [r"/(?:post|article|content|news)/", r"/\d{3,}"],
 "وزن دنیا": [r"/(?:post|article|content|news)/", r"/\d{3,}"],
}

def clean(s):
    s=re.sub(r"<[^>]+>"," ",s or "")
    return re.sub(r"\s+"," ",html.unescape(s)).strip()

def first_text(el,names):
    for child in list(el):
        if child.tag.split("}")[-1].lower() in names and (child.text or "").strip(): return clean(child.text)
    return ""

def excluded(src):
    name=(src.get("source_name") or "").casefold()
    urls=" ".join(str(src.get(k) or "").casefold() for k in ("homepage","feed_url"))
    if any(t.casefold() in name for t in _EXCLUDED_SOURCE_TERMS): return True
    return any(d in urls for d in _EXCLUDED_SOURCE_DOMAINS)

def allowed_article(src, path):
    rules=ARTICLE_RULES.get(src.get("source_name"))
    if not rules: return True
    return any(re.search(p,path,re.I) for p in rules)

def make_row(src,title,link,text,transport):
    ident=hashlib.sha1((src["source_name"]+"|"+link).encode()).hexdigest()
    return {"id":"site:"+ident,"publisher":src["source_name"],"kind":"site_feed","title_original":title,
      "text":text[:5000],"article_url":link,"transport":transport,"page":None,"lang":src.get("lang"),
      "source_homepage":src.get("homepage")}

def html_candidates(src):
    home=src.get("homepage")
    if not home: return []
    req=urllib.request.Request(home,headers={"User-Agent":UA})
    raw=urllib.request.urlopen(req,timeout=25).read(2_000_000)
    soup=BeautifulSoup(raw,"html.parser")
    host=urllib.parse.urlparse(home).netloc.lower().removeprefix("www.")
    seen=set(); out=[]
    bad_parts=("/tag/","/category/","/author/","/page/","/search","/login","/contact","/about","/cart","/product/")
    anchors=[]
    for node in soup.select("article, main, .post, .posts, .entry, .news, .content"):
        anchors.extend(node.find_all("a",href=True))
    anchors += soup.find_all("a",href=True)
    for a in anchors:
        title=clean(a.get_text(" ",strip=True) or a.get("title") or "")
        if len(title)<14 or len(title)>240: continue
        link=urllib.parse.urljoin(home,a["href"]); u=urllib.parse.urlparse(link)
        if u.scheme not in {"http","https"}: continue
        if u.netloc.lower().removeprefix("www.") != host: continue
        if any(p in u.path.lower() for p in bad_parts) or u.path in {"","/"}: continue
        if not allowed_article(src,u.path): continue
        link=urllib.parse.urlunparse((u.scheme,u.netloc,u.path,u.params,u.query,""))
        if link in seen: continue
        seen.add(link); out.append(make_row(src,title,link,title,"site:"+home))
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
            except Exception as exc: print("press sites:",src.get("source_name"),"failed:",str(exc)[:180])
            continue
        try:
            req=urllib.request.Request(feed,headers={"User-Agent":UA})
            raw=urllib.request.urlopen(req,timeout=25).read(2_000_000); root=ET.fromstring(raw)
            items=[x for x in root.iter() if x.tag.split("}")[-1].lower() in {"item","entry"}][:20]
            for it in items:
                title=first_text(it,{"title"}); summary=first_text(it,{"description","summary","content","encoded"})
                link=first_text(it,{"link","guid"})
                if not link:
                    for ch in list(it):
                        if ch.tag.split("}")[-1].lower()=="link" and ch.attrib.get("href"): link=ch.attrib["href"]; break
                link=urllib.parse.urljoin(src.get("homepage") or feed,link)
                if not title or not link: continue
                if excluded({**src,"feed_url":link}): continue
                rows.append(make_row(src,title,link,summary,"rss:"+feed))
            print("press feeds:",src.get("source_name"),"collected",sum(1 for x in rows if x["publisher"]==src["source_name"]),"RSS candidates")
        except Exception as exc: print("press feeds:",src.get("source_name"),"failed:",str(exc)[:180])
    rows=list({x["id"]:x for x in rows}.values())
    OUT.parent.mkdir(exist_ok=True); OUT.write_text(json.dumps(rows,ensure_ascii=False),encoding="utf-8")
    print("press feeds: collected",len(rows),"article candidates from",len(set(x["publisher"] for x in rows)),"publishers")

if __name__=="__main__": main()
