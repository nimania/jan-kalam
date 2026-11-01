#!/usr/bin/env python3
"""Import only explicitly approved and independently sourced Simorgh news.

This modifies data/manual-news.json in the build workspace, not the source
repository; unreviewed Telegram posts never appear on the published site.
"""
from __future__ import annotations
import argparse
import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
QUEUE = "https://raw.githubusercontent.com/nimania/pendar/main/backend/data/simorgh-leads.json"
POST = re.compile(r"^https://t\.me/simorghdata369/[1-9][0-9]*$")


def iso(value):
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.isoformat() if dt.tzinfo is not None else None
    except (ValueError, TypeError):
        return None


def approved(row):
    if not isinstance(row, dict) or row.get("review_status") != "approved":
        return False
    if not POST.fullmatch(str(row.get("source_url") or "")):
        return False
    if len(str(row.get("reviewed_by") or "").strip()) < 2:
        return False
    if not iso(row.get("approved_at")):
        return False
    if len(str(row.get("approved_headline_fa") or "").strip()) < 18:
        return False
    if len(str(row.get("approved_summary_fa") or "").strip()) < 80:
        return False
    if len(str(row.get("why_it_matters_fa") or "").strip()) < 40:
        return False
    sources = row.get("independent_sources")
    if not isinstance(sources, list) or not sources:
        return False
    for src in sources:
        if not isinstance(src, dict) or not str(src.get("source_name") or "").strip():
            return False
        url = str(src.get("article_url") or "")
        parts = urlsplit(url)
        if parts.scheme != "https" or not parts.netloc:
            return False
        if parts.hostname in {"t.me", "telegram.me", "telegram.org"}:
            return False
    return True


def to_news(row):
    url = row["source_url"]
    sources = [{"source_name": s["source_name"].strip(),
                "article_url": s["article_url"].strip()}
               for s in row["independent_sources"]]
    return {
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "jan-kalam/simorgh/" + url)),
        "headline_fa": row["approved_headline_fa"].strip(),
        "summary_fa": row["approved_summary_fa"].strip(),
        "what_happened_fa": row["approved_summary_fa"].strip(),
        "why_it_matters_fa": row["why_it_matters_fa"].strip(),
        "source_names": list(dict.fromkeys(s["source_name"] for s in sources)),
        "source_count": len(sources),
        "sources": sources,
        "discovery_source": "آشیان سیمرغ",
        "discovery_source_url": url,
        "status": "published",
        "category": "iran",
        "iran_relevance": "high",
        "published_at": iso(row["approved_at"]),
        "original_published_at": iso(row.get("source_published_at")),
        "topics": ["ایران", "سیگنال‌های راهبردی"],
        "editorial_report": False,
        "reviewed_by": row["reviewed_by"],
    }


def merge(existing, dataset):
    if not isinstance(existing, list) or not isinstance(dataset, dict):
        raise ValueError("Input format invalid")
    if not isinstance(dataset.get("leads"), list):
        raise ValueError("No editorial leads array")
    items = {str(x.get("id")): x for x in existing
             if isinstance(x, dict) and x.get("id")}
    count = 0
    for row in dataset["leads"]:
        if not approved(row):
            continue
        news = to_news(row)
        if news["id"] not in items:
            items[news["id"]] = news
            count += 1
    return sorted(items.values(), key=lambda x: str(x.get("published_at") or ""), reverse=True), count


def fetch():
    req = Request(QUEUE, headers={"User-Agent": "JanKalam-ApprovedSignals/1.0"})
    with urlopen(req, timeout=25) as resp:
        raw = resp.read(3_000_001)
    if len(raw) > 3_000_000:
        raise ValueError("Approval queue too large")
    return json.loads(raw.decode("utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, help="Offline approved queue fixture")
    parser.add_argument("--out", type=Path, default=ROOT / "data/manual-news.json")
    args = parser.parse_args()
    source = json.loads(args.input.read_text(encoding="utf-8")) if args.input else fetch()
    present = json.loads(args.out.read_text(encoding="utf-8")) if args.out.exists() else []
    results, added = merge(present, source)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Approved, independently verified Simorgh news imported:", added,
          "; total curated articles:", len(results))


if __name__ == "__main__":
    main()
