"""Collect recent article metadata from RSS/Atom and source-aware HTML collectors."""
from __future__ import annotations
import hashlib, html, json, re, urllib.parse, urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from concurrent.futures import ThreadPoolExecutor
import xml.etree.ElementTree as ET
from pathlib import Path
from bs4 import BeautifulSoup
from app.ingestion.service import _EXCLUDED_SOURCE_TERMS, _EXCLUDED_SOURCE_DOMAINS

HEALTH=Path("public/data/press-registry-health.json")
OUT=Path("periodicals/site_articles.json")
DIAG_OUT=Path("periodicals/site_articles_diag.json")
ARCHIVE=Path("periodicals/archive.json")
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

def parse_published(value):
    value=(value or "").strip()
    if not value: return None
    try:
        d=parsedate_to_datetime(value)
        if d.tzinfo is None: d=d.replace(tzinfo=timezone.utc)
        return d.isoformat()
    except Exception:
        pass
    try:
        d=datetime.fromisoformat(value.replace("Z","+00:00"))
        if d.tzinfo is None: d=d.replace(tzinfo=timezone.utc)
        return d.isoformat()
    except Exception:
        return None

def make_row(src,title,link,text,transport,published=None):
    ident=hashlib.sha1((src["source_name"]+"|"+link).encode()).hexdigest()
    row={"id":"site:"+ident,"publisher":src["source_name"],"kind":"site_feed","title_original":title,
      "text":text[:5000],"article_url":link,"transport":transport,"page":None,"lang":src.get("lang"),
      "scope":src.get("scope"),"source_homepage":src.get("homepage")}
    if published: row["source_published_at"]=published
    return row

def enrich_full_article(row):
    """Fetch article HTML for transformation. Raw source text stays workflow-local."""
    link=row.get("article_url")
    if not link: return row
    try:
        req=urllib.request.Request(link,headers={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml"})
        raw=urllib.request.urlopen(req,timeout=12).read(3_000_000)
        soup=BeautifulSoup(raw,"html.parser")
        for node in soup.select("script,style,noscript,nav,footer,header,aside,form,.share,.social,.related,.comments,.comment"):
            node.decompose()
        selectors=["[itemprop='articleBody']","article .entry-content","article .post-content",
                   ".td-post-content",".single-content",".article-content",".post-body",
                   ".entry-content",".post-content","article","main"]
        candidates=[]
        for sel in selectors:
            for node in soup.select(sel):
                txt=re.sub(r"\s+"," ",node.get_text(" ",strip=True)).strip()
                if len(txt)>=300: candidates.append(txt)
        full=max(candidates,key=len) if candidates else ""
        if full:
            row={**row,"source_text":full[:26000]}
        og=soup.find("meta",attrs={"property":"og:image"}) or soup.find("meta",attrs={"name":"twitter:image"})
        if og and og.get("content"):
            row={**row,"image_url":urllib.parse.urljoin(link,og.get("content"))}
        pub=(soup.find("meta",attrs={"property":"article:published_time"})
             or soup.find("meta",attrs={"itemprop":"datePublished"})
             or soup.find("meta",attrs={"name":"date"}))
        if pub and pub.get("content"):
            row={**row,"source_published_at":pub.get("content")}
    except Exception as exc:
        row={**row,"fulltext_error":str(exc)[:180]}
    return row

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

def collect_source(src):
    if src.get("state")!="active" or excluded(src):
        return [], None
    feed=src.get("feed_url")
    if not feed:
        try:
            found=html_candidates(src)
            return found, f"press sites: {src.get('source_name')} collected {len(found)} HTML candidates"
        except Exception as exc:
            return [], f"press sites: {src.get('source_name')} failed: {str(exc)[:180]}"
    try:
        req=urllib.request.Request(feed,headers={"User-Agent":UA})
        raw=urllib.request.urlopen(req,timeout=18).read(2_000_000)
        root=ET.fromstring(raw)
        out=[]
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
            published=parse_published(first_text(it,{"pubdate","published","updated","date"}))
            if not title or not link: continue
            if excluded({**src,"feed_url":link}): continue
            out.append(make_row(src,title,link,summary,"rss:"+feed,published))
        return out, f"press feeds: {src.get('source_name')} collected {len(out)} RSS candidates"
    except Exception as exc:
        return [], f"press feeds: {src.get('source_name')} failed: {str(exc)[:180]}"

def main():
    health=json.loads(HEALTH.read_text(encoding="utf-8")) if HEALTH.exists() else []
    active=[src for src in health if src.get("state")=="active" and not excluded(src)]
    rows=[]
    # Feed fetches are independent; bounded concurrency keeps a few slow outlets
    # from stretching an every-30-minute run into an hour.
    with ThreadPoolExecutor(max_workers=10) as pool:
        batches=list(pool.map(collect_source,active))
    for found,msg in batches:
        rows.extend(found)
        if msg: print(msg)
    rows=list({x["id"]:x for x in rows}.values())

    # Fetch full pages fairly across publishers. The least-enriched publishers
    # go first, so adding many feeds does not let the first/high-volume outlets
    # monopolize long-form processing.
    old=[]
    if ARCHIVE.exists():
        try: old=json.loads(ARCHIVE.read_text(encoding="utf-8"))
        except Exception: old=[]
    done_full={x.get("id") for x in old if x.get("id") and x.get("enrichment_state")=="ai_fulltext"}
    done_counts=Counter(
        x.get("publisher") for x in old
        if x.get("publisher") and x.get("enrichment_state")=="ai_fulltext"
    )
    by_pub=defaultdict(list)
    pub_scope={}
    pub_order={}
    for idx,x in enumerate(rows):
        p=x.get("publisher") or ""
        if not p: continue
        by_pub[p].append(x)
        pub_scope[p]=x.get("scope")
        pub_order.setdefault(p,idx)
    scope_priority={"iran-agency":0,"iran-paper":0,"diaspora":1,"world":2,"iran-magazine":3}
    publishers=sorted(
        by_pub,
        key=lambda p:(done_counts.get(p,0),scope_priority.get(pub_scope.get(p),4),pub_order[p])
    )
    full_ids=set()
    for p in publishers:
        candidate=next((x for x in by_pub[p] if x.get("id") not in done_full),None)
        if candidate:
            full_ids.add(candidate["id"])
        if len(full_ids)>=48: break
    with ThreadPoolExecutor(max_workers=8) as pool:
        enriched=list(pool.map(enrich_full_article,[x for x in rows if x["id"] in full_ids]))
    enriched_by_id={x["id"]:x for x in enriched}
    rows=[enriched_by_id.get(x["id"],x) for x in rows]

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(rows,ensure_ascii=False),encoding="utf-8")
    # Diagnostics intentionally omit full copyrighted source text.
    diag=[{k:v for k,v in x.items() if k!="source_text"} for x in rows]
    DIAG_OUT.write_text(json.dumps(diag,ensure_ascii=False),encoding="utf-8")
    print("press feeds: collected",len(rows),"article candidates from",len(set(x["publisher"] for x in rows)),"publishers; full text",sum(bool(x.get("source_text")) for x in rows))

if __name__=="__main__": main()
