"""Build the Jan Kalam book/publisher/person knowledge layer.

Phase 1 is intentionally evidence-first: only books with verified metadata are public.
Mentions are linked from the existing periodical archive when the title is present.
Future collectors can append verified books without changing the public JSON schema.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ARCHIVE = ROOT / "periodicals" / "archive.json"
OUT = ROOT / "public" / "data" / "books.json"
CANDIDATES = ROOT / "periodicals" / "book_candidates.json"

BOOKS = [
    {
        "slug": "namehaye-kamalolmolk",
        "title_fa": "نامه‌های کمال‌الملک",
        "subtitle_fa": "نامه‌های کمال‌الملک به دکتر قاسم غنی",
        "description_fa": (
            "مجموعه‌ای از نامه‌های کمال‌الملک به دکتر قاسم غنی؛ نامه‌هایی که "
            "بازه‌ای از سال ۱۳۰۶ تا ۱۳۱۹ را در بر می‌گیرند و بخشی از زندگی، "
            "ارتباطات و روزگار این نقاش ایرانی را از خلال مکاتبات او نشان می‌دهند."
        ),
        "category_fa": "ادبیات، نامه‌ها و تاریخ هنر",
        "pages": 252,
        "isbn": "",
        "cover_url": "https://digibookshahr.com/wp-content/uploads/2026/08/processed_Cover-front-300x400.webp",
        "creators": [
            {
                "slug": "ali-dehbashi",
                "name_fa": "علی دهباشی",
                "role_fa": "به‌کوشش / گردآورنده",
            }
        ],
        "publisher": {
            "slug": "daniyar",
            "name_fa": "نشر دانیار",
        },
        "purchase_links": [
            {
                "store": "دیجی بوک شهر",
                "url": "https://digibookshahr.com/product/%D8%AE%D8%B1%DB%8C%D8%AF-%DA%A9%D8%AA%D8%A7%D8%A8-%D9%86%D8%A7%D9%85%D9%87-%D9%87%D8%A7%DB%8C-%DA%A9%D9%85%D8%A7%D9%84-%D8%A7%D9%84%D9%85%D9%84%DA%A9-%D8%A8%D9%87-%DA%A9%D9%88%D8%B4%D8%B4-%D8%B9%D9%84/",
                "format_fa": "نسخهٔ چاپی",
            },
        ],
        "source_meta": [
            {"label": "بخارا", "url": "https://bukharamag.com/1405.05.27862.html"},
            {"label": "دیجی بوک شهر", "url": "https://digibookshahr.com/product/%D8%AE%D8%B1%DB%8C%D8%AF-%DA%A9%D8%AA%D8%A7%D8%A8-%D9%86%D8%A7%D9%85%D9%87-%D9%87%D8%A7%DB%8C-%DA%A9%D9%85%D8%A7%D9%84-%D8%A7%D9%84%D9%85%D9%84%DA%A9-%D8%A8%D9%87-%DA%A9%D9%88%D8%B4%D8%B4-%D8%B9%D9%84/"},
        ],
    },
]

BOOK_RE = re.compile(
    r"(?:کتاب|رمان|نقد\s+و\s+بررسی\s+کتاب|بررسی\s+کتاب)\s*[«\"“]([^»\"”]{2,120})[»\"”]"
)


def _norm(s: str) -> str:
    return " ".join(
        str(s or "")
        .replace("ي", "ی")
        .replace("ى", "ی")
        .replace("ك", "ک")
        .replace("‌", " ")
        .split()
    ).strip()


def _load_archive() -> list[dict]:
    try:
        data = json.loads(ARCHIVE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _article_text(x: dict) -> str:
    vals = [
        x.get("title_original"), x.get("headline_fa"), x.get("summary_fa"),
        x.get("body_fa"), " ".join(x.get("key_points_fa") or []),
    ]
    return "\n".join(str(v or "") for v in vals)


def _mention(x: dict) -> dict:
    return {
        "kind": "press",
        "source_name": x.get("publisher") or "منبع",
        "article_id": x.get("id"),
        "headline_fa": x.get("headline_fa") or x.get("title_original") or "",
        "summary_fa": x.get("summary_fa") or "",
        "url": x.get("source_url") or x.get("article_url") or x.get("telegram_post_url"),
        "published_at": x.get("source_published_at") or x.get("published_at"),
    }


def build() -> dict:
    archive = _load_archive()

    # Candidate extraction is deliberately broad but private. Nothing becomes a
    # public book until its metadata is verified and added to BOOKS.
    candidates: dict[str, dict] = {}
    for x in archive:
        text = _article_text(x)
        for title in BOOK_RE.findall(text):
            key = _norm(title)
            if len(key) < 2:
                continue
            row = candidates.setdefault(key, {"title_fa": title.strip(), "mentions": []})
            row["mentions"].append(_mention(x))
    CANDIDATES.parent.mkdir(parents=True, exist_ok=True)
    CANDIDATES.write_text(
        json.dumps(list(candidates.values()), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    public_books = []
    people: dict[str, dict] = {}
    publishers: dict[str, dict] = {}
    for raw in BOOKS:
        b = dict(raw)
        wanted = _norm(b["title_fa"])
        mentions = []
        seen = set()
        for x in archive:
            text = _norm(_article_text(x))
            if wanted and wanted in text:
                m = _mention(x)
                key = str(m.get("article_id") or m.get("url") or "")
                if key and key not in seen:
                    mentions.append(m)
                    seen.add(key)
        # First verified book is known from Bukhara even if an older cache has
        # not yet carried the article row into archive.json.
        if not mentions and b["slug"] == "namehaye-kamalolmolk":
            mentions.append({
                "kind": "press",
                "source_name": "بخارا",
                "article_id": None,
                "headline_fa": "عصر چهارشنبه‌های بخارا",
                "summary_fa": "نشست بخارا به بررسی کتاب «نامه‌های کمال‌الملک» اختصاص یافت.",
                "url": "https://bukharamag.com/1405.05.27862.html",
                "published_at": None,
            })
        b["mentions"] = mentions
        b["mention_count"] = len(mentions)
        public_books.append(b)

        for cr in b.get("creators", []):
            p = people.setdefault(cr["slug"], {
                "slug": cr["slug"], "name_fa": cr["name_fa"],
                "roles_fa": [], "book_slugs": [],
            })
            if cr["role_fa"] not in p["roles_fa"]:
                p["roles_fa"].append(cr["role_fa"])
            if b["slug"] not in p["book_slugs"]:
                p["book_slugs"].append(b["slug"])

        pub = b.get("publisher") or {}
        if pub.get("slug"):
            p = publishers.setdefault(pub["slug"], {
                "slug": pub["slug"], "name_fa": pub["name_fa"],
                "book_slugs": [], "categories_fa": [],
            })
            p["book_slugs"].append(b["slug"])
            if b.get("category_fa") and b["category_fa"] not in p["categories_fa"]:
                p["categories_fa"].append(b["category_fa"])

    payload = {
        "books": public_books,
        "people": list(people.values()),
        "publishers": list(publishers.values()),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"books: published {len(public_books)} verified books, {len(people)} people, {len(publishers)} publishers")
    return payload


if __name__ == "__main__":
    build()
