"""Named-entity (people / bodies) detection for stories — a curated gazetteer,
matched deterministically against a story's text. No AI cost, fully controllable:
add or prune a figure by editing ENTITIES below, and only listed figures get a
page. Distinctive name forms only, to avoid false positives.

Used by scripts.export_static to tag each story with the figures it mentions and
to build per-person pages (/e/<slug>/) — "click a name → all their news, جان‌کلامی".
"""
from __future__ import annotations

import re

# slug, display name (fa), english, kind (person|body), aliases (distinctive forms).
# Keep aliases distinctive: a bare short word that is also common Persian is risky.
ENTITIES: list[dict] = [
    # --- Iran: state / officials ---
    {"slug": "khamenei", "fa": "علی خامنه‌ای", "en": "Ali Khamenei", "kind": "person",
     "aliases": ["خامنه‌ای", "خامنه ای", "رهبر انقلاب", "رهبر معظم انقلاب", "مقام معظم رهبری"]},
    {"slug": "pezeshkian", "fa": "مسعود پزشکیان", "en": "Masoud Pezeshkian", "kind": "person",
     "aliases": ["پزشکیان"]},
    {"slug": "ghalibaf", "fa": "محمدباقر قالیباف", "en": "Mohammad Bagher Ghalibaf", "kind": "person",
     "aliases": ["قالیباف"]},
    {"slug": "araghchi", "fa": "عباس عراقچی", "en": "Abbas Araghchi", "kind": "person",
     "aliases": ["عراقچی"]},
    {"slug": "aref", "fa": "محمدرضا عارف", "en": "Mohammad Reza Aref", "kind": "person",
     "aliases": ["محمدرضا عارف", "معاون اول رئیس‌جمهور"]},
    {"slug": "eslami", "fa": "محمد اسلامی", "en": "Mohammad Eslami", "kind": "person",
     "aliases": ["محمد اسلامی", "رئیس سازمان انرژی اتمی"]},
    {"slug": "mohseni-ejei", "fa": "غلامحسین محسنی اژه‌ای", "en": "Mohseni-Eje'i", "kind": "person",
     "aliases": ["محسنی اژه‌ای", "محسنی‌اژه‌ای", "اژه‌ای"]},
    {"slug": "zarif", "fa": "محمدجواد ظریف", "en": "Javad Zarif", "kind": "person",
     "aliases": ["ظریف", "محمدجواد ظریف"]},
    {"slug": "salami", "fa": "حسین سلامی", "en": "Hossein Salami", "kind": "person",
     "aliases": ["سرلشکر سلامی", "حسین سلامی", "فرمانده کل سپاه"]},
    {"slug": "raisi", "fa": "ابراهیم رئیسی", "en": "Ebrahim Raisi", "kind": "person",
     "aliases": ["ابراهیم رئیسی", "رئیسی"]},
    {"slug": "mokhber", "fa": "محمد مخبر", "en": "Mohammad Mokhber", "kind": "person",
     "aliases": ["محمد مخبر", "مخبر"]},

    # --- Iran: bodies ---
    {"slug": "irgc", "fa": "سپاه پاسداران", "en": "IRGC", "kind": "body",
     "aliases": ["سپاه پاسداران", "سپاه"]},
    {"slug": "iran-mfa", "fa": "وزارت خارجه ایران", "en": "Iran MFA", "kind": "body",
     "aliases": ["وزارت امور خارجه", "وزارت خارجه"]},
    {"slug": "aeoi", "fa": "سازمان انرژی اتمی ایران", "en": "AEOI", "kind": "body",
     "aliases": ["سازمان انرژی اتمی"]},

    # --- USA / West ---
    {"slug": "trump", "fa": "دونالد ترامپ", "en": "Donald Trump", "kind": "person",
     "aliases": ["ترامپ", "دونالد ترامپ"]},
    {"slug": "vance", "fa": "جی‌دی ونس", "en": "JD Vance", "kind": "person",
     "aliases": ["جی‌دی ونس", "جی دی ونس", "ونس"]},
    {"slug": "biden", "fa": "جو بایدن", "en": "Joe Biden", "kind": "person",
     "aliases": ["بایدن"]},
    {"slug": "rubio", "fa": "مارکو روبیو", "en": "Marco Rubio", "kind": "person",
     "aliases": ["روبیو", "مارکو روبیو"]},
    {"slug": "macron", "fa": "امانوئل مکرون", "en": "Emmanuel Macron", "kind": "person",
     "aliases": ["مکرون"]},

    # --- Region ---
    {"slug": "netanyahu", "fa": "بنیامین نتانیاهو", "en": "Benjamin Netanyahu", "kind": "person",
     "aliases": ["نتانیاهو"]},
    {"slug": "erdogan", "fa": "رجب طیب اردوغان", "en": "Recep Tayyip Erdogan", "kind": "person",
     "aliases": ["اردوغان"]},
    {"slug": "mbs", "fa": "محمد بن سلمان", "en": "Mohammed bin Salman", "kind": "person",
     "aliases": ["بن سلمان", "محمد بن سلمان"]},
    {"slug": "sisi", "fa": "عبدالفتاح السیسی", "en": "Abdel Fattah el-Sisi", "kind": "person",
     "aliases": ["السیسی", "عبدالفتاح السیسی"]},
    {"slug": "abbas", "fa": "محمود عباس", "en": "Mahmoud Abbas", "kind": "person",
     "aliases": ["محمود عباس"]},
    {"slug": "assad", "fa": "بشار اسد", "en": "Bashar al-Assad", "kind": "person",
     "aliases": ["بشار اسد"]},

    # --- Russia / China / world bodies ---
    {"slug": "putin", "fa": "ولادیمیر پوتین", "en": "Vladimir Putin", "kind": "person",
     "aliases": ["پوتین"]},
    {"slug": "zelensky", "fa": "ولودیمیر زلنسکی", "en": "Volodymyr Zelensky", "kind": "person",
     "aliases": ["زلنسکی", "زلینسکی"]},
    {"slug": "xi", "fa": "شی جین‌پینگ", "en": "Xi Jinping", "kind": "person",
     "aliases": ["شی جین‌پینگ", "شی جین پینگ"]},
    {"slug": "grossi", "fa": "رافائل گروسی", "en": "Rafael Grossi", "kind": "person",
     "aliases": ["گروسی", "رافائل گروسی"]},
    {"slug": "guterres", "fa": "آنتونیو گوترش", "en": "Antonio Guterres", "kind": "person",
     "aliases": ["گوترش"]},
    {"slug": "iaea", "fa": "آژانس بین‌المللی انرژی اتمی", "en": "IAEA", "kind": "body",
     "aliases": ["آژانس بین‌المللی انرژی اتمی", "آژانس اتمی"]},

    # --- Sport (appears a lot in Persian feeds) ---
    {"slug": "azmoun", "fa": "سردار آزمون", "en": "Sardar Azmoun", "kind": "person",
     "aliases": ["سردار آزمون", "آزمون"]},
    {"slug": "gholmohammadi", "fa": "یحیی گل‌محمدی", "en": "Yahya Golmohammadi", "kind": "person",
     "aliases": ["گل‌محمدی", "گل محمدی", "یحیی گل‌محمدی"]},
]

# "letter" = Latin/Persian letters, Persian digits and ZWNJ — but NOT Persian
# punctuation (،؛؟ live at U+060C/061B/061F, below the letter block), so a name
# followed by a comma still matches.
# Pre-baked encyclopedia links for each figure — reader can compare framings.
# Grokipedia is AI-generated and English-only, Persian Wikipedia is community-
# curated; showing both alongside en.wikipedia lets the reader triangulate.
from urllib.parse import quote

def reference_links(ent: dict) -> list[dict]:
    fa = quote(ent["fa"].replace(" ", "_"))
    en = quote(ent["en"].replace(" ", "_"))
    return [
        {"src": "ویکی‌پدیا", "label": "فارسی", "url": f"https://fa.wikipedia.org/wiki/{fa}"},
        {"src": "Wikipedia", "label": "English", "url": f"https://en.wikipedia.org/wiki/{en}"},
        {"src": "Grokipedia", "label": "English", "url": f"https://grokipedia.com/search?q={quote(ent['en'])}"},
    ]


_LETTER = r"[A-Za-z0-9ء-ۓ۰-۹‌]"


def _compile(alias: str) -> re.Pattern:
    # match the alias only when it is not glued to another (Persian/Latin) letter
    return re.compile(r"(?<!" + _LETTER + r")" + re.escape(alias) + r"(?!" + _LETTER + r")")


_COMPILED = [(e, [_compile(a) for a in e["aliases"]]) for e in ENTITIES]


def detect(text: str) -> list[dict]:
    """Return the figures mentioned in `text`, as compact
    {slug, name_fa, kind, refs}."""
    if not text:
        return []
    found = []
    for e, pats in _COMPILED:
        if any(p.search(text) for p in pats):
            found.append({"slug": e["slug"], "name_fa": e["fa"], "kind": e["kind"],
                          "refs": reference_links(e)})
    return found


def by_slug(slug: str) -> dict | None:
    for e in ENTITIES:
        if e["slug"] == slug:
            return e
    return None
