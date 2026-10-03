"""Build the Jan Kalam book/publisher/person knowledge layer.

Evidence-first rules:
- Broad title candidates are extracted privately from published Jan-e Jaraid articles.
- A candidate is auto-published only when the same source text explicitly supplies
  a book title + creator + publisher (high-confidence bibliographic context).
- Hand-verified enrichments can add pages/original title/cover/direct shop links,
  but are never required for discovery.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ARCHIVE = ROOT / "periodicals" / "archive.json"
OUT = ROOT / "public" / "data" / "books.json"
OUT_JS = ROOT / "public" / "data" / "books.js"
CANDIDATES = ROOT / "periodicals" / "book_candidates.json"

# Hand-verified seed/enrichment. Automatic discoveries merge into this registry.
MANUAL_BOOKS = [
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
            {"slug": "ali-dehbashi", "name_fa": "علی دهباشی", "role_fa": "به‌کوشش / گردآورنده"}
        ],
        "publisher": {"slug": "daniyar", "name_fa": "نشر دانیار"},
        "purchase_links": [
            {
                "store": "دیجی بوک شهر",
                "url": "https://digibookshahr.com/product/%D8%AE%D8%B1%DB%8C%D8%AF-%DA%A9%D8%AA%D8%A7%D8%A8-%D9%86%D8%A7%D9%85%D9%87-%D9%87%D8%A7%DB%8C-%DA%A9%D9%85%D8%A7%D9%84-%D8%A7%D9%84%D9%85%D9%84%DA%A9-%D8%A8%D9%87-%DA%A9%D9%88%D8%B4%D8%B4-%D8%B9%D9%84/",
                "format_fa": "نسخهٔ چاپی",
                "exact": True,
            },
        ],
        "source_meta": [
            {"label": "بخارا", "url": "https://bukharamag.com/1405.05.27862.html"},
            {"label": "دیجی بوک شهر", "url": "https://digibookshahr.com/product/%D8%AE%D8%B1%DB%8C%D8%AF-%DA%A9%D8%AA%D8%A7%D8%A8-%D9%86%D8%A7%D9%85%D9%87-%D9%87%D8%A7%DB%8C-%DA%A9%D9%85%D8%A7%D9%84-%D8%A7%D9%84%D9%85%D9%84%DA%A9-%D8%A8%D9%87-%DA%A9%D9%88%D8%B4%D8%B4-%D8%B9%D9%84/"},
        ],
    },
]

# Metadata confirmed from publisher/bookseller records. These rows enrich titles
# that the automatic high-confidence extractor discovers in Jan Kalam content.
ENRICHMENTS = {
    "زیتون و انجیر": {
        "slug": "zeytoon-o-anjir",
        "subtitle_fa": "دوازده مقالهٔ اجتماعی",
        "original_title": "Politische Schriften und Reden",
        "original_year": 1968,
        "description_fa": "گزیده‌ای از مقاله‌ها و نوشته‌های اجتماعی توماس مان، با ترجمهٔ محمود حدادی.",
        "category_fa": "مقاله، جامعه و ادبیات",
        "pages": 147,
    },
    "ملال گریز": {
        "slug": "malal-goriz",
        "subtitle_fa": "ناصرالدین‌شاهِ معمار و عمارت‌هایش",
        "description_fa": "روایتی پژوهشی دربارهٔ ناصرالدین‌شاه و جهان معماری او، با تمرکز بر تجربهٔ زیسته، ساخت‌وساز و تاریخ فرهنگی ایران.",
        "category_fa": "تاریخ فرهنگی و معماری",
        "pages": 280,
        "publication_year_fa": "۱۴۰۵",
        "publisher_url": "https://atraf.ir/",
    },
}

BOOK_RE = re.compile(
    r"(?:کتاب|رمان|نقد\s+و\s+بررسی\s+کتاب|بررسی\s+کتاب)\s*[«\"“]([^»\"”]{2,120})[»\"”]"
)

# High confidence: the article itself names the book, creator and publisher.
VERIFIED_RE = re.compile(
    r"(?:کتاب\s*)?[«\"“](?P<title>[^»\"”]{2,120})[»\"”]"
    r"(?:\s*\((?P<subtitle>[^)]{2,180})\))?"
    r"\s*[,،]?\s*(?:(?:نوشته|اثر)(?:ٔ|‌ی|ی)?\s+(?P<author>[^،,\n]{2,90}?)(?=\s+که\s+از\s+سوی|\s+از\s+سوی|[,،]|$))?"
    r"(?:\s*[,،]\s*ترجمه(?:ٔ|‌ی|ی)?\s+(?P<translator>[^،,\n]{2,90}?)(?=\s+که\s+از\s+سوی|\s+از\s+سوی|[,،]|$))?"
    r"(?P<middle>.{0,180}?)"
    r"(?:که\s+)?از\s+سوی\s+(?P<publisher>(?:نشر|انتشارات)\s+[^،,.\n]{2,80})\s+منتشر",
    re.S,
)

# Bukhara sometimes uses "به کوشش" instead of "نوشتهٔ".
CURATED_RE = re.compile(
    r"(?:کتاب\s*)?[«\"“](?P<title>[^»\"”]{2,120})[»\"”]"
    r"\s*[,،]?\s*به\s+کوشش\s+(?P<curator>[^،,\n]{2,90}?)"
    r"\s*[,،]\s*(?:که\s+)?از\s+سوی\s+(?P<publisher>(?:نشر|انتشارات)\s+[^،,.\n]{2,80})\s+منتشر",
    re.S,
)


def _norm(s: str) -> str:
    return " ".join(
        str(s or "")
        .replace("ي", "ی").replace("ى", "ی").replace("ك", "ک")
        .replace("‌", " ").replace("ـ", "")
        .split()
    ).strip()


def _stable_slug(prefix: str, text: str) -> str:
    return prefix + "-" + hashlib.sha1(_norm(text).encode("utf-8")).hexdigest()[:10]


def _person_slug(name: str) -> str:
    known = {
        _norm("علی دهباشی"): "ali-dehbashi",
        _norm("توماس مان"): "thomas-mann",
        _norm("محمود حدادی"): "mahmoud-haddadi",
        _norm("حمیدرضا پیشوایی"): "hamidreza-pishvaei",
    }
    return known.get(_norm(name), _stable_slug("person", name))


def _publisher_slug(name: str) -> str:
    known = {
        _norm("نشر دانیار"): "daniyar",
        _norm("نشر فرهنگ سیادت"): "farhang-siadat",
        _norm("نشر اطراف"): "atraf",
    }
    return known.get(_norm(name), _stable_slug("publisher", name))


def _search_links(title: str) -> list[dict]:
    q = quote(title)
    return [
        {"store": "دیجی‌کالا", "url": f"https://www.digikala.com/search/?q={q}",
         "format_fa": "جست‌وجوی این عنوان", "exact": False},
        {"store": "طاقچه", "url": f"https://taaghche.com/search?q={q}",
         "format_fa": "جست‌وجوی این عنوان", "exact": False},
        {"store": "فیدیبو", "url": f"https://fidibo.com/search?q={q}",
         "format_fa": "جست‌وجوی این عنوان", "exact": False},
    ]


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


def _creator(name: str, role: str) -> dict:
    return {"slug": _person_slug(name), "name_fa": name.strip(), "role_fa": role}


def _auto_verified(archive: list[dict]) -> dict[str, dict]:
    verified: dict[str, dict] = {}
    for article in archive:
        text = _article_text(article)
        for m in VERIFIED_RE.finditer(text):
            title = m.group("title").strip()
            author = (m.group("author") or "").strip()
            translator = (m.group("translator") or "").strip()
            publisher = (m.group("publisher") or "").strip()
            # At least one creator + explicit publisher is required.
            if not publisher or not (author or translator):
                continue
            key = _norm(title)
            row = verified.setdefault(key, {
                "slug": _stable_slug("book", title),
                "title_fa": title,
                "subtitle_fa": (m.group("subtitle") or "").strip(),
                "description_fa": "",
                "category_fa": "کتاب",
                "pages": None,
                "isbn": "",
                "cover_url": "",
                "creators": [],
                "publisher": {"slug": _publisher_slug(publisher), "name_fa": publisher},
                "purchase_links": _search_links(title),
                "source_meta": [],
                "mentions": [],
                "confidence": "high",
                "discovery": "automatic",
            })
            if author and not any(_norm(c["name_fa"]) == _norm(author) for c in row["creators"]):
                row["creators"].append(_creator(author, "نویسنده"))
            if translator and not any(_norm(c["name_fa"]) == _norm(translator) for c in row["creators"]):
                row["creators"].append(_creator(translator, "مترجم"))
            row["mentions"].append(_mention(article))
            if article.get("source_url"):
                row["source_meta"].append({"label": article.get("publisher") or "منبع", "url": article["source_url"]})

        for m in CURATED_RE.finditer(text):
            title = m.group("title").strip()
            curator = m.group("curator").strip()
            publisher = m.group("publisher").strip()
            key = _norm(title)
            row = verified.setdefault(key, {
                "slug": _stable_slug("book", title),
                "title_fa": title,
                "subtitle_fa": "",
                "description_fa": "",
                "category_fa": "کتاب",
                "pages": None,
                "isbn": "",
                "cover_url": "",
                "creators": [],
                "publisher": {"slug": _publisher_slug(publisher), "name_fa": publisher},
                "purchase_links": _search_links(title),
                "source_meta": [],
                "mentions": [],
                "confidence": "high",
                "discovery": "automatic",
            })
            if curator and not any(_norm(c["name_fa"]) == _norm(curator) for c in row["creators"]):
                row["creators"].append(_creator(curator, "به‌کوشش / گردآورنده"))
            row["mentions"].append(_mention(article))
    return verified


def _merge_enrichment(book: dict) -> dict:
    extra = ENRICHMENTS.get(_norm(book.get("title_fa") or ""))
    if not extra:
        return book
    for k, v in extra.items():
        if v not in (None, "", [], {}):
            book[k] = v
    if book.get("publisher_url"):
        book.setdefault("purchase_links", []).insert(0, {
            "store": book.get("publisher", {}).get("name_fa") or "ناشر",
            "url": book["publisher_url"],
            "format_fa": "سایت ناشر / خرید",
            "exact": False,
        })
    return book


def _dedupe_mentions(rows: list[dict]) -> list[dict]:
    out, seen = [], set()
    for m in rows:
        key = str(m.get("article_id") or m.get("url") or "")
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        out.append(m)
    return out


def build() -> dict:
    archive = _load_archive()

    # Broad private candidate queue.
    candidates: dict[str, dict] = {}
    for x in archive:
        text = _article_text(x)
        for title in BOOK_RE.findall(text):
            key = _norm(title)
            if len(key) < 2:
                continue
            row = candidates.setdefault(key, {"title_fa": title.strip(), "mentions": [], "status": "candidate"})
            row["mentions"].append(_mention(x))

    auto = _auto_verified(archive)
    for key, row in auto.items():
        cand = candidates.setdefault(key, {"title_fa": row["title_fa"], "mentions": [], "status": "candidate"})
        cand["status"] = "auto_verified"
        cand["confidence"] = "high"
        cand["creators"] = row.get("creators", [])
        cand["publisher"] = row.get("publisher")
        cand["mentions"] = _dedupe_mentions((cand.get("mentions") or []) + (row.get("mentions") or []))

    CANDIDATES.parent.mkdir(parents=True, exist_ok=True)
    CANDIDATES.write_text(
        json.dumps(list(candidates.values()), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    by_title: dict[str, dict] = {}
    for raw in MANUAL_BOOKS:
        b = json.loads(json.dumps(raw, ensure_ascii=False))
        b["confidence"] = "verified"
        b["discovery"] = "manual"
        by_title[_norm(b["title_fa"])] = b
    for key, raw in auto.items():
        if key in by_title:
            continue
        by_title[key] = _merge_enrichment(raw)

    # Attach every matching mention from the archive, not just the discovery article.
    public_books = []
    for key, b in by_title.items():
        mentions = list(b.get("mentions") or [])
        for x in archive:
            if key and key in _norm(_article_text(x)):
                mentions.append(_mention(x))
        b["mentions"] = _dedupe_mentions(mentions)
        b["mention_count"] = len(b["mentions"])
        if not b.get("purchase_links"):
            b["purchase_links"] = _search_links(b["title_fa"])
        public_books.append(b)

    public_books.sort(key=lambda b: (-int(b.get("mention_count") or 0), b.get("title_fa") or ""))

    people: dict[str, dict] = {}
    publishers: dict[str, dict] = {}
    for b in public_books:
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
            if b["slug"] not in p["book_slugs"]:
                p["book_slugs"].append(b["slug"])
            if b.get("category_fa") and b["category_fa"] not in p["categories_fa"]:
                p["categories_fa"].append(b["category_fa"])

    payload = {
        "books": public_books,
        "people": list(people.values()),
        "publishers": list(publishers.values()),
        "candidate_count": len(candidates),
        "auto_verified_count": sum(1 for x in candidates.values() if x.get("status") == "auto_verified"),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    compact=json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    OUT.write_text(compact, encoding="utf-8")
    OUT_JS.write_text("window.__BOOKS_DATA__="+compact+";\n", encoding="utf-8")
    print(
        f"books: published {len(public_books)} books "
        f"({payload['auto_verified_count']} auto-verified candidates), "
        f"{len(people)} people, {len(publishers)} publishers"
    )
    return payload


if __name__ == "__main__":
    build()
