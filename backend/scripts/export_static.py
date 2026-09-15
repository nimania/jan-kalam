"""Export the published stories as STATIC JSON + a static front-end.

Run after the pipeline (ingest → cluster → rank → synthesize). Produces a
self-contained `public/` folder that any free static host (GitHub Pages,
Cloudflare Pages) can serve — no backend needed at serve time.

Also enriches each story with:
  • our own automated credibility signal (independent sources + agreement),
  • a best-effort link to a matching Factnameh professional fact-check,
and writes the trends board (بورس اخبار) and the Factnameh section.

    python -m scripts.export_static
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import shutil

from app.analytics import google_trends as gt_svc
from app.analytics import service as analytics_svc
from app.credibility import compute_credibility
from app.db.session import SessionLocal
from app.entities import service as entity_svc
from app.factcheck import service as fc_svc
from app.geo import countries as countries_svc
from app.geo import service as geo_svc
from app.prices import service as price_svc
from app.repositories import stories as story_repo
from app.repositories import topics as topic_repo
from app.weather import service as weather_svc
from app.services import ask as ask_svc
from app.services import stories as story_svc
from app.trends import service as trends_svc

OUT = os.environ.get("STATIC_OUT", "public")
DATA = os.path.join(OUT, "data")
WEB_STATIC = os.path.join(os.path.dirname(__file__), "..", "..", "web-static")
# Public base URL (no trailing slash) — used for canonical links, Open Graph and
# the sitemap. Override with SITE_URL for a custom domain.
SITE = os.environ.get("SITE_URL", "https://nimania.github.io/jan-kalam").rstrip("/")

# Answers are pre-baked at build time (static host can't run the AI live).
QUESTIONS = [
    "چرا این خبر مهم است؟",
    "منابع مختلف چه می‌گویند؟",
    "چه چیزی هنوز مشخص نیست؟",
    "این موضوع چه ارتباطی با ایران دارد؟",
]


def _write(path: str, obj) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))


def _write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _digest(path: str) -> str:
    """Short content hash of a file (empty string if missing)."""
    try:
        with open(path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()[:8]
    except OSError:
        return ""


def _cache_bust() -> str:
    """Stamp app.js / styles.css / iran-provinces.js in index.html with a
    content hash (?v=…) so a new deploy is fetched immediately instead of being
    served stale from the browser/CDN cache. Also bumps the service-worker
    cache name so it re-installs when the code changes. Returns the app hash."""
    idx = os.path.join(OUT, "index.html")
    assets = ["app.js", "styles.css", "iran-provinces.js"]
    vers = {a: _digest(os.path.join(OUT, a)) for a in assets}
    try:
        with open(idx, encoding="utf-8") as f:
            page = f.read()
    except OSError:
        return vers.get("app.js", "")
    for a, v in vers.items():
        if v:
            # add/refresh ?v=… on the src="a"/href="a" reference
            page = re.sub(r'((?:src|href)="' + re.escape(a) + r')(?:\?v=[0-9a-f]+)?(")',
                          r"\1?v=" + v + r"\2", page)
    _write_text(idx, page)

    app_v = vers.get("app.js", "")
    sw = os.path.join(OUT, "sw.js")
    if app_v and os.path.exists(sw):
        with open(sw, encoding="utf-8") as f:
            swtext = f.read()
        swtext = re.sub(r'const V = "[^"]*";',
                        'const V = "jankalam-' + app_v + '";', swtext, count=1)
        _write_text(sw, swtext)
    return app_v


def _clip(text: str, n: int = 180) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def _story_page(d: dict, app_v: str) -> str:
    """A crawlable, shareable static page per story: real <title>, meta
    description and Open Graph tags (so shared links unfurl with a preview and
    search engines can index each story), plus the جان‌کلام summary and a link
    into the interactive app. No auto-redirect — the page is real content."""
    sid = d["id"]
    title = _clip(d.get("headline_fa") or "خبر", 90)
    summary = _clip(d.get("summary_fa") or "", 200)
    url = f"{SITE}/s/{sid}/"
    app_url = f"{SITE}/#/story/{sid}"
    e = html.escape
    srcs = "، ".join((d.get("source_names") or [])[:6])
    what = d.get("what_happened_fa") or ""
    why = d.get("why_it_matters_fa") or ""
    blocks = "".join(
        f'<section><h2>{e(t)}</h2><p>{e(b)}</p></section>'
        for t, b in [("چه اتفاقی افتاد؟", what), ("چرا اهمیت دارد؟", why)] if b)
    return f"""<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)} — جان‌کلام</title>
<meta name="description" content="{e(summary)}">
<link rel="canonical" href="{e(url)}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="جان‌کلام">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(summary)}">
<meta property="og:url" content="{e(url)}">
{('<meta property="og:image" content="' + e(d["image_url"]) + '"><meta name="twitter:card" content="summary_large_image">') if d.get("image_url") else '<meta name="twitter:card" content="summary">'}
<meta name="theme-color" content="#155a4f">
<link rel="icon" href="{SITE}/icons/icon.svg" type="image/svg+xml">
<style>
:root{{color-scheme:light dark}}
body{{margin:0;background:#0f1512;color:#e8efe9;font-family:Vazirmatn,'Noto Naskh Arabic',system-ui,sans-serif;line-height:1.9}}
.hero{{width:100%;aspect-ratio:16/9;object-fit:cover;border-radius:12px;margin:14px 0;background:#16201b}}
.wrap{{max-width:680px;margin:0 auto;padding:26px 20px 60px}}
a{{color:#3ec99f}}
.brand{{font-weight:700;color:#3ec99f;font-size:20px;text-decoration:none}}
h1{{font-size:26px;line-height:1.5;margin:18px 0 6px}}
.sum{{font-size:17px;color:#cfe0d6;background:#16201b;border:1px solid #24352d;border-radius:14px;padding:16px 18px;margin:14px 0}}
.meta{{color:#8fa89b;font-size:14px;margin:4px 0 10px}}
h2{{font-size:16px;color:#a9c4b7;margin:22px 0 4px}}
section p{{margin:0;color:#dce8e1}}
.cta{{display:inline-block;margin-top:26px;background:#1a9d7e;color:#04120d;font-weight:700;text-decoration:none;padding:12px 20px;border-radius:12px}}
.home{{display:block;margin-top:18px;color:#8fa89b}}
@media(prefers-color-scheme:light){{body{{background:#f6f8f7;color:#16201b}}.sum{{background:#fff;border-color:#e2e9e5;color:#2a3a32}}section p{{color:#2a3a32}}}}
</style>
</head>
<body>
<div class="wrap">
<a class="brand" href="{SITE}/">جان‌کلام</a>
<div class="meta">هوش خبری فارسی — واقعیت جدا از تحلیل، هر منبع به‌تفکیک</div>
<h1>{e(d.get("headline_fa") or "")}</h1>
<div class="meta">{e(str(d.get("source_count") or 0))} منبع{(' · ' + e(srcs)) if srcs else ''}</div>
{('<img class="hero" src="' + e(d["image_url"]) + '" alt="" loading="lazy" onerror="this.remove()">') if d.get("image_url") else ''}
<p class="sum">{e(d.get("summary_fa") or "")}</p>
{blocks}
<a class="cta" href="{e(app_url)}">باز کردن در جان‌کلام — منابع، واقعیت و ابهام</a>
<a class="home" href="{SITE}/">← همهٔ خبرها</a>
</div>
</body>
</html>
"""


def _entity_page(ent: dict, cards: list[dict]) -> str:
    """A crawlable, shareable page per figure: their recent stories in one place,
    with proper meta/OG tags and a link into the interactive جان‌کلام feed."""
    slug, name = ent["slug"], ent["name_fa"]
    e = html.escape
    url = f"{SITE}/e/{slug}/"
    app_url = f"{SITE}/#/person/{slug}"
    kind_fa = "نهاد" if ent.get("kind") == "body" else "چهره"
    desc = _clip(f"همهٔ خبرهای مرتبط با {name} در جان‌کلام — از چند منبع، با تفکیکِ "
                 f"واقعیت از دیدگاه. {ent.get('count', 0)} خبر.", 200)
    items = "".join(
        f'<li><a href="{SITE}/s/{c["id"]}/">{e(c.get("headline_fa") or "")}</a></li>'
        for c in cards)
    return f"""<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(name)} — خبرها در جان‌کلام</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{e(url)}">
<meta property="og:type" content="profile">
<meta property="og:site_name" content="جان‌کلام">
<meta property="og:title" content="{e(name)} — خبرها">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{e(url)}">
<meta name="theme-color" content="#155a4f">
<link rel="icon" href="{SITE}/icons/icon.svg" type="image/svg+xml">
<style>
:root{{color-scheme:light dark}}
body{{margin:0;background:#0f1512;color:#e8efe9;font-family:Vazirmatn,'Noto Naskh Arabic',system-ui,sans-serif;line-height:1.9}}
.wrap{{max-width:680px;margin:0 auto;padding:26px 20px 60px}}
a{{color:#3ec99f;text-decoration:none}}
.brand{{font-weight:700;color:#3ec99f;font-size:20px}}
.meta{{color:#8fa89b;font-size:14px;margin:4px 0}}
h1{{font-size:26px;margin:16px 0 2px}}
ul{{list-style:none;padding:0;margin:16px 0}}
li{{border-bottom:1px solid #24352d;padding:12px 0}}
li a{{color:#dce8e1;font-size:17px}}
.cta{{display:inline-block;margin-top:20px;background:#1a9d7e;color:#04120d;font-weight:700;padding:12px 20px;border-radius:12px}}
@media(prefers-color-scheme:light){{body{{background:#f6f8f7;color:#16201b}}li{{border-color:#e2e9e5}}li a{{color:#26332c}}}}
</style>
</head>
<body>
<div class="wrap">
<a class="brand" href="{SITE}/">جان‌کلام</a>
<div class="meta">{kind_fa} · هوش خبری فارسی</div>
<h1>خبرهای {e(name)}</h1>
<div class="meta">{e(str(ent.get("count", 0)))} خبر مرتبط</div>
<ul>{items}</ul>
<a class="cta" href="{e(app_url)}">دنبال‌کردن در جان‌کلام</a>
</div>
</body>
</html>
"""


def _story_match_texts(detail: dict) -> list[str | None]:
    texts: list[str | None] = [detail.get("headline_fa"), detail.get("summary_fa")]
    for sv in detail.get("source_views", []):
        texts.append(sv.get("original_headline"))
    return texts


def run() -> None:
    db = SessionLocal()
    os.makedirs(os.path.join(DATA, "story"), exist_ok=True)

    factchecks = fc_svc.fetch_factchecks(limit=12)

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    feed = story_svc.get_feed(db, limit=60, offset=0, category=None)
    cards = [c.model_dump(mode="json") for c in feed.items]

    # Build details + per-story trend metrics first; classify rising/hot across
    # the whole set (thresholds are relative to the day), THEN write everything.
    details: dict[str, dict] = {}
    metrics: dict[str, dict] = {}
    for card in cards:
        detail = story_svc.get_detail(db, card["id"])
        story = story_repo.get(db, card["id"])
        d = detail.model_dump(mode="json")
        d["asks"] = [{"q": q, "a": ask_svc.answer(story, q).answer_fa} for q in QUESTIONS]

        cred = compute_credibility(d)
        d["credibility"] = cred

        match = fc_svc.match_story(_story_match_texts(d), factchecks)
        if match:
            d["factcheck"] = match

        geo = geo_svc.classify(
            " ".join(t for t in _story_match_texts(d) + [d.get("what_happened_fa")] if t))
        d["geo"] = geo
        # Trust our geo detection over the AI's Iran-relevance guess: if a specific
        # Iranian province or a national context is found, it IS Iran-related.
        if geo["scope"] in ("local", "national"):
            d["iran_relevance"] = "high"
            card["iran_relevance"] = "high"

        # Named figures mentioned in the story (curated gazetteer) — powers the
        # clickable name chips and the per-person pages.
        _text = " ".join(t for t in _story_match_texts(d)
            + [d.get("what_happened_fa"), d.get("why_it_matters_fa")] if t)
        d["entities"] = entity_svc.detect(_text)
        # Countries mentioned — powers the mini world-map badge on each story.
        d["countries"] = countries_svc.detect(_text)

        # Best image from the story's linked articles: use whatever the outlet's
        # RSS feed explicitly published in media:thumbnail / media:content, and
        # only when that outlet's policy allows it. We hotlink to the outlet —
        # we never rehost, and the source link stays right on the card.
        img_url = None
        img_credit = None
        for link in (story.article_links or []):
            a = link.article
            if a and a.image_url_if_permitted and a.source and a.source.allow_image:
                img_url = a.image_url_if_permitted
                img_credit = a.source_name
                break
        if img_url:
            d["image_url"] = img_url
            d["image_credit"] = img_credit

        metrics[card["id"]] = analytics_svc.momentum(story, now)
        details[card["id"]] = d

        # compact copies on the feed card so the list can show badges + filter by topic
        card["credibility"] = {"level": cred["level"], "label_fa": cred["label_fa"],
                               "needs_verification": cred["needs_verification"],
                               "disagreements": cred["disagreements"],
                               "independent_sources": cred["independent_sources"]}
        card["topics"] = [{"slug": t["slug"], "name_fa": t["name_fa"]}
                          for t in d.get("topics", [])]
        card["entities"] = d["entities"]
        card["countries"] = d["countries"]
        card["geo"] = geo
        if d.get("image_url"):
            card["image_url"] = d["image_url"]
            card["image_credit"] = d.get("image_credit")
        if match:
            card["factcheck"] = {"url": match["url"]}

    analytics_svc.classify_rising_hot(list(metrics.values()))
    for card in cards:
        m = metrics[card["id"]]
        card["trend"] = {"ratio": m["ratio"], "velocity": m["velocity"],
                         "rising": m["rising"], "hot": m["hot"], "spark": m["spark"]}
        d = details[card["id"]]
        d["trend"] = m
        _write(os.path.join(DATA, "story", f"{card['id']}.json"), d)

    _write(os.path.join(DATA, "stories.json"), cards)

    topics = topic_repo.list_all(db)
    _write(os.path.join(DATA, "topics.json"),
           [{"id": t.id, "slug": t.slug, "name_fa": t.name_fa, "name_en": t.name_en}
            for t in topics])

    # People / bodies index: which figures appear and in how many stories.
    ent_counts: dict[str, int] = {}
    ent_meta: dict[str, dict] = {}
    for card in cards:
        for e in card.get("entities", []):
            ent_counts[e["slug"]] = ent_counts.get(e["slug"], 0) + 1
            ent_meta[e["slug"]] = e
    entities_list = sorted(
        [{"slug": s, "name_fa": ent_meta[s]["name_fa"], "kind": ent_meta[s]["kind"],
          "count": n} for s, n in ent_counts.items()],
        key=lambda x: -x["count"])
    _write(os.path.join(DATA, "entities.json"), entities_list)

    # Trends board + growth series (+ best-effort Google Trends overlay).
    trends = trends_svc.compute_trends(db)
    series = analytics_svc.topic_series(db, days=14, now=now)
    by_slug = {e["slug"]: e for e in series}
    for t in trends.get("topics", []):
        e = by_slug.get(t["slug"])
        if e:
            t["series"] = e["counts"]
            t["growth"] = e["growth"]
            t["last7"], t["prev7"] = e["last7"], e["prev7"]
    trends["topic_series"] = series
    trends["google"] = gt_svc.fetch([(e["slug"], e["name_fa"]) for e in series[:5]])
    _write(os.path.join(DATA, "trends.json"), trends)

    _write(os.path.join(DATA, "stats.json"), analytics_svc.stats(db, now=now))
    _write(os.path.join(DATA, "factchecks.json"), factchecks)
    _write(os.path.join(DATA, "prices.json"), price_svc.fetch_prices())
    _write(os.path.join(DATA, "weather.json"), weather_svc.fetch_weather())
    _write(os.path.join(DATA, "geo.json"), geo_svc.stats(cards))

    _write(os.path.join(DATA, "meta.json"),
           {"built": now.strftime("%Y-%m-%d %H:%M UTC"),
            "built_iso": now.isoformat(),
            "count": len(cards)})

    db.close()

    # Copy the static front-end (index.html, app.js, styles.css, icons, manifest).
    if os.path.isdir(WEB_STATIC):
        for item in os.listdir(WEB_STATIC):
            src = os.path.join(WEB_STATIC, item)
            dst = os.path.join(OUT, item)
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)

    # Version the shell so a new deploy is fetched immediately (not stale-cached).
    app_v = _cache_bust()

    # A crawlable, shareable static page per story + sitemap + robots.
    urls = [f"{SITE}/"]
    for card in cards:
        d = details.get(card["id"])
        if not d:
            continue
        _write_text(os.path.join(OUT, "s", card["id"], "index.html"), _story_page(d, app_v))
        urls.append(f"{SITE}/s/{card['id']}/")
    # A page per figure (their stories in one place) + include in the sitemap.
    for ent in entities_list:
        ecards = [c for c in cards
                  if any(x["slug"] == ent["slug"] for x in c.get("entities", []))]
        _write_text(os.path.join(OUT, "e", ent["slug"], "index.html"), _entity_page(ent, ecards))
        urls.append(f"{SITE}/e/{ent['slug']}/")
    sitemap = ('<?xml version="1.0" encoding="UTF-8"?>\n'
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
               + "".join(f"  <url><loc>{u}</loc></url>\n" for u in urls)
               + "</urlset>\n")
    _write_text(os.path.join(OUT, "sitemap.xml"), sitemap)
    _write_text(os.path.join(OUT, "robots.txt"),
                f"User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n")

    print(f"exported {len(cards)} stories, {len(factchecks)} fact-checks, "
          f"{len(urls) - 1} story pages to ./{OUT}")


if __name__ == "__main__":
    run()
