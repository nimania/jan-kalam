"""Build Jan-e Jaraid data from locally supplied periodical JSON.

The ingestion/extraction stage may write backend/periodicals_inbox/*.json.  This
exporter is deliberately isolated from the news feed: periodical articles never
become Story rows or figure-timeline items.

Accepted item fields:
 id, publisher, issue, published_at, title_original, headline_fa, summary_fa,
 body_fa (or longform_fa), sections_fa, source_url.

For copyrighted publications body_fa is a detailed Persian retelling, not a
line-by-line/full translation.  The original PDF/body is never exported.
"""
from __future__ import annotations
import json, os, re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
INBOX=Path(os.environ.get("PERIODICAL_INBOX", ROOT/"periodicals_inbox"))
OUT=Path(os.environ.get("STATIC_OUT", ROOT/"public"))/"data"/"periodicals.json"

def _slug(s: str) -> str:
    s=re.sub(r"[^a-zA-Z0-9\u0600-\u06ff]+","-",s or "").strip("-")
    return s[:80] or "periodical"

def run() -> dict:
    rows=[]
    if INBOX.exists():
        for path in sorted(INBOX.glob("*.json")):
            try:
                raw=json.loads(path.read_text(encoding="utf-8"))
                items=raw if isinstance(raw,list) else raw.get("articles",[raw])
                for i,x in enumerate(items):
                    if not isinstance(x,dict) or not x.get("publisher"): continue
                    if not (x.get("headline_fa") or x.get("title_fa") or x.get("title_original")): continue
                    y={k:v for k,v in x.items() if k not in ("raw_text","pdf_text","full_text","original_body")}
                    y.setdefault("id",f"{_slug(str(x.get('publisher')))}-{_slug(str(x.get('issue') or path.stem))}-{i+1}")
                    y["content_mode"]="detailed_retelling"
                    rows.append(y)
            except Exception as exc:
                print(f"periodical skipped {path.name}: {exc}")
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(rows,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    print(f"Jan-e Jaraid: exported {len(rows)} article(s)")
    return {"articles":len(rows)}

if __name__=="__main__": run()
