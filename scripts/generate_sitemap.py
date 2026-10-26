#!/usr/bin/env python3
"""Build crawlable story URLs for the standalone Jan Kalam snapshot."""
import gzip
import html
import json
import re
from pathlib import Path

BASE_URL = "https://nimania.github.io/jan-kalam/"
SNAPSHOT = Path("data/snapshot.json.gz")
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)

with gzip.open(SNAPSHOT, "rt", encoding="utf-8") as source:
    snapshot = json.load(source)

urls = [(BASE_URL, None)]
for key, story in snapshot.items():
    if not key.startswith("story/") or not key.endswith(".json"):
        continue
    story_id = key[len("story/"):-len(".json")]
    if not UUID_RE.fullmatch(story_id):
        continue
    url = f"{BASE_URL}?story={story_id}"
    lastmod = ""
    if isinstance(story, dict):
        date = str(story.get("updated_at") or story.get("published_at") or "")[:10]
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            lastmod = f"<lastmod>{html.escape(date)}</lastmod>"
    urls.append((url, lastmod or None))

entries = []
for url, lastmod in urls:
    entries.append(f"<url><loc>{html.escape(url)}</loc>{lastmod or ''}</url>")

xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
xml += "\n".join(entries)
xml += "\n</urlset>\n"
Path("sitemap.xml").write_text(xml, encoding="utf-8")
print(f"Generated sitemap.xml with {len(urls) - 1} story URLs.")
