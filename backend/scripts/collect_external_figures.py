"""Collect public Truth Social posts for external figure profiles.

Best-effort collector. It uses Truth Social's public Mastodon-compatible account/status
endpoints when available. Failure never breaks the main news build; the last committed
external-figure-posts.json remains the fallback.

Raw English is sent to the configured Jan Kalam AI provider. The model returns a faithful
Persian paraphrase; the public export keeps provenance, original URL and source language.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.ai.providers import get_provider

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "data" / "external-figure-posts.json"
BASE = "https://truthsocial.com"
ACCOUNT = "realDonaldTrump"
LIMIT = 30

SYSTEM = """تو ویراستار «جان کلام» هستی. پست‌های عمومی یک چهره را از زبان اصلی دریافت می‌کنی.
فقط محتوای دارای موضع، ادعا، تصمیم، استدلال یا پیام عمومی معنادار را publish=true کن.
تبلیغ، تبریک ساده، بازنشر بدون نظر تازه، محتوای تکراری و پست تقریباً خالی را publish=false کن.
برای موارد منتشرشدنی topic_fa حداکثر ۸ کلمه و summary_fa بازگویی دقیق و خنثی فارسی در ۱ تا ۴
جمله باشد. چیزی اضافه نکن، شدت لحن را تغییر نده و ترجمه را نقل‌قول مستقیم فارسی جا نزن.
خروجی فقط JSON با کلید posts و برای هر id: publish, topic_fa, summary_fa."""
    

def _get(client: httpx.Client, path: str):
    r = client.get(BASE + path)
    r.raise_for_status()
    return r.json()


def fetch_truth() -> list[dict]:
    headers = {"User-Agent": "JanKalam/1.0 (+https://nimania.github.io/jan-kalam/)",
               "Accept": "application/json"}
    with httpx.Client(headers=headers, timeout=25, follow_redirects=True) as client:
        accounts = _get(client, f"/api/v1/accounts/lookup?acct={ACCOUNT}")
        aid = accounts["id"]
        rows = _get(client, f"/api/v1/accounts/{aid}/statuses?exclude_replies=true&limit={LIMIT}")
    out = []
    for s in rows if isinstance(rows, list) else []:
        # A reblog/retruth with no original commentary is not Trump's own statement.
        if s.get("reblog"):
            continue
        text = str(s.get("content") or "")
        if not text.strip():
            continue
        out.append({"id": str(s["id"]), "text_html": text, "url": s.get("url") or s.get("uri"),
                    "created_at": s.get("created_at"), "media": s.get("media_attachments") or []})
    return out


def classify(rows: list[dict]) -> list[dict]:
    provider = get_provider()
    if getattr(provider, "name", "") == "mock" or not rows:
        return []
    prompt = "پست‌ها:\n" + json.dumps(
        [{"id": x["id"], "text_html": x["text_html"]} for x in rows], ensure_ascii=False)
    result = provider.generate(system=SYSTEM, user=prompt, context={"posts": rows})
    labels = {str(x.get("id")): x for x in result.data.get("posts", []) if isinstance(x, dict)}
    public = []
    for row in rows:
        lab = labels.get(row["id"], {})
        if lab.get("publish") is not True or not str(lab.get("summary_fa") or "").strip():
            continue
        media = row.get("media") or []
        public.append({
            "id": "truthsocial-" + row["id"], "handle": "donald-trump",
            "name_fa": "دونالد ترامپ", "role_fa": "رئیس‌جمهور ایالات متحده",
            "field": "foreign", "kind": "analysis", "platform": "truthsocial",
            "source_language": "en", "translation_label_fa": "بازگویی از انگلیسی",
            "topic_fa": str(lab.get("topic_fa") or "تروث سوشیال").strip(),
            "summary_fa": str(lab.get("summary_fa") or "").strip(),
            "url": row.get("url"), "published_at": row.get("created_at"),
            "media_url": (media[0].get("url") if media and isinstance(media[0], dict) else None),
        })
    return public


def load_old() -> list[dict]:
    try:
        data = json.loads(OUT.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def run() -> int:
    old = load_old()
    try:
        fresh = classify(fetch_truth())
    except Exception as exc:
        print(f"truth collector: keeping existing data ({type(exc).__name__})")
        return 0
    # Replace collected Truth Social rows by ID while preserving other platforms/figures.
    by_id = {str(x.get("id")): x for x in old if isinstance(x, dict)}
    for x in fresh:
        by_id[str(x["id"])] = x
    merged = sorted(by_id.values(), key=lambda x: str(x.get("published_at") or ""), reverse=True)
    # Bound repository data; 100 substantive posts per external figure is ample history.
    trump, other = [], []
    for x in merged:
        (trump if x.get("handle") == "donald-trump" else other).append(x)
    merged = other + trump[:100]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"truth collector: {len(fresh)} fresh substantive posts; {len(trump[:100])} Trump rows kept")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
