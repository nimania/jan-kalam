"""Public Telegram periodical collector (no Telegram login required).

Reads public t.me/s/<channel> preview pages. Telegram is transport only:
the visible source is inferred from the publication filename/title.

This collector deliberately fails soft. If Telegram exposes a post but not a
publicly downloadable PDF URL, the item is recorded in quarantine rather than
breaking the site's normal build.
"""
from __future__ import annotations
import hashlib, html, json, re, urllib.parse, urllib.request
from pathlib import Path
from pypdf import PdfReader

CHANNELS = ("dailynewspaper88", "dailynewspaper88magzine")
OUT = Path("periodicals")
STATE = OUT / "state.json"
UA = "Mozilla/5.0 (compatible; JanKalamPeriodicals/1.0; +https://nimania.github.io/jan-kalam/)"

PUBLISHERS = [
    (re.compile(r"\b(?:the\s+)?wall\s*street\s+journal|\bwsj\b", re.I), "وال‌استریت ژورنال"),
    (re.compile(r"\bguardian\s+weekly\b", re.I), "هفته‌نامه گاردین"),
    (re.compile(r"\b(?:the\s+)?guardian\b", re.I), "گاردین"),
    (re.compile(r"\b(?:the\s+)?economist\b", re.I), "اکونومیست"),
    (re.compile(r"\bfinancial\s+times\b|\bft\b", re.I), "فایننشال تایمز"),
    (re.compile(r"\bnew\s*york\s+times\b|\bnyt\b", re.I), "نیویورک تایمز"),
    (re.compile(r"\bwashington\s+post\b", re.I), "واشنگتن پست"),
    (re.compile(r"\btime\b", re.I), "تایم"),
    (re.compile(r"(?:مجله|ماهنامه)?\s*تجربه(?!\s*و\s*شهر)", re.I), "تجربه"),
    (re.compile(r"(?:مجله|فصلنامه)?\s*آنگاه", re.I), "آنگاه"),
    (re.compile(r"(?:مجله)?\s*تراژدی", re.I), "تراژدی"),
    (re.compile(r"(?:مجله)?\s*روز\s*آ?\s*روز", re.I), "روزآروز"),
    (re.compile(r"(?:مجله)?\s*بخارا", re.I), "بخارا"),
    (re.compile(r"(?:مجله)?\s*تنور", re.I), "تنور"),
    (re.compile(r"(?:مجله)?\s*ناداستان", re.I), "ناداستان"),
    (re.compile(r"(?:مجله)?\s*عصر\s*اندیشه", re.I), "عصر اندیشه"),
    (re.compile(r"(?:مجله)?\s*شهریور", re.I), "شهریور"),
    (re.compile(r"(?:مجله)?\s*فریدون", re.I), "فریدون"),
    (re.compile(r"(?:مجله)?\s*اندیشه\s*پویا", re.I), "اندیشه پویا"),
    (re.compile(r"(?:مجله)?\s*مروارید", re.I), "مروارید"),
    (re.compile(r"(?:مجله)?\s*غروب", re.I), "غروب"),
    (re.compile(r"(?:مجله)?\s*تجربه\s*و\s*شهر", re.I), "تجربه و شهر"),
    (re.compile(r"(?:مجله)?\s*هنر\s*و\s*جامعه", re.I), "هنر و جامعه"),
    (re.compile(r"(?:مجله|ماهنامه)?\s*روزنامک", re.I), "روزنامک"),
]

def publisher_for(filename: str) -> str | None:
    stem = Path(filename).stem.replace("_", " ").replace("-", " ")
    for pattern, name in PUBLISHERS:
        if pattern.search(stem):
            return name
    return None

def fetch(url: str, binary: bool = False):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
        return data if binary else data.decode("utf-8", "replace")

def public_posts(channel: str) -> list[dict]:
    """Parse message ids, document names and any public file/CDN URLs."""
    raw = fetch(f"https://t.me/s/{channel}")
    blocks = re.split(r'(?=<div class="tgme_widget_message_wrap)', raw)
    rows = []
    for block in blocks:
        m = re.search(r'data-post="' + re.escape(channel) + r'/(\d+)"', block)
        if not m:
            continue
        mid = int(m.group(1))
        text = html.unescape(re.sub(r"<[^>]+>", " ", block))
        text = re.sub(r"\s+", " ", text).strip()
        pdf_names = re.findall(r'([^<>"/]{2,180}\.pdf)\b', text, re.I)
        hrefs = [html.unescape(x) for x in re.findall(r'href="([^"]+)"', block)]
        direct = next((u for u in hrefs if ".pdf" in u.lower() or "telegram-cdn" in u.lower()), None)
        photos = re.findall(r'background-image:url\\([\'"]?([^\'")]+)', block)
        photo = html.unescape(photos[0]) if photos else None
        rows.append({"id": mid, "text": text[:2000], "filename": pdf_names[0] if pdf_names else "",
                     "download_url": direct, "cover_url": photo})
    return rows

def _page_image(page, pdf: Path, page_no: int) -> str | None:
    """Extract the largest embedded raster image from a PDF page for article artwork."""
    try:
        images = list(getattr(page, "images", []) or [])
        if not images:
            return None
        def area(im):
            obj = getattr(im, "image", None)
            size = getattr(obj, "size", (0, 0))
            return int(size[0] or 0) * int(size[1] or 0)
        best = max(images, key=area)
        if area(best) < 120000:
            return None
        ext = Path(getattr(best, "name", "") or "").suffix.lower()
        if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
            ext = ".jpg"
        rel = Path("assets") / "periodicals" / f"{pdf.stem}-p{page_no}{ext}"
        out = Path("web-static") / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(best.data)
        return "/" + rel.as_posix()
    except Exception as exc:
        print(f"periodicals: image extraction failed {pdf.name} p{page_no}: {exc}")
        return None


def page_articles(pdf: Path, publisher: str, origin: str, message_id: int) -> list[dict]:
    rows = []
    reader = PdfReader(str(pdf))
    for page_no, page in enumerate(reader.pages, 1):
        text = re.sub(r"\s+", " ", page.extract_text() or "").strip()
        if len(text) < 350:
            continue
        title = text[:180].rsplit(" ", 1)[0]
        rows.append({
            "id": hashlib.sha1(f"{origin}:{message_id}:{page_no}".encode()).hexdigest(),
            "publisher": publisher,
            "transport": f"telegram-public:@{origin}",
            "telegram_message_id": message_id,
            "telegram_post_url": f"https://t.me/{origin}/{message_id}",
            "page": page_no,
            "title_original": title,
            "text": text[:12000],
            "image_url": _page_image(page, pdf, page_no),
        })
    return rows

def main() -> None:
    OUT.mkdir(exist_ok=True)
    state = json.loads(STATE.read_text() if STATE.exists() else "{}")
    output, quarantine = [], []
    for channel in CHANNELS:
        after = int(state.get(channel, 0))
        newest = after
        try:
            posts = public_posts(channel)
        except Exception as exc:
            print(f"periodicals: preview failed @{channel}: {exc}")
            continue
        for post in sorted(posts, key=lambda x: x["id"]):
            mid = post["id"]; newest = max(newest, mid)
            if mid <= after:
                continue
            filename = post["filename"]
            publisher = publisher_for(filename or post["text"])
            if not publisher:
                quarantine.append({"channel": channel, "message_id": mid, "reason": "unknown_publisher", "label": filename or post["text"][:240]})
                continue
            url = post["download_url"]
            if not url:
                # Standalone image posts are often issue covers. Keep them so the
                # publisher can attach the nearest preceding cover to the next PDF issue.
                if post.get("cover_url"):
                    output.append({
                        "id": f"cover:{channel}:{mid}", "kind": "issue_cover",
                        "publisher": publisher, "transport": f"telegram-public:@{channel}",
                        "telegram_message_id": mid, "telegram_post_url": f"https://t.me/{channel}/{mid}",
                        "cover_url": post["cover_url"], "text": post["text"][:500],
                    })
                    continue
                quarantine.append({"channel": channel, "message_id": mid, "reason": "pdf_not_publicly_exposed", "publisher": publisher, "label": filename})
                continue
            pdf = OUT / f"{channel}-{mid}.pdf"
            try:
                data = fetch(urllib.parse.urljoin("https://t.me/", url), binary=True)
                if not data.startswith(b"%PDF"):
                    raise ValueError("download target is not a PDF")
                pdf.write_bytes(data)
                output.extend(page_articles(pdf, publisher, channel, mid))
            except Exception as exc:
                quarantine.append({"channel": channel, "message_id": mid, "reason": "download_or_parse_failed", "publisher": publisher, "error": str(exc)[:240]})
            finally:
                pdf.unlink(missing_ok=True)
        state[channel] = newest
    (OUT / "articles.json").write_text(json.dumps(output, ensure_ascii=False), encoding="utf-8")
    (OUT / "quarantine.json").write_text(json.dumps(quarantine, ensure_ascii=False), encoding="utf-8")
    STATE.write_text(json.dumps(state), encoding="utf-8")
    print(f"periodicals: extracted {len(output)} page candidates; quarantined {len(quarantine)}")

if __name__ == "__main__":
    main()
