"""Country detection in story text — a curated gazetteer keyed by ISO A2 code.

Mirrors the entities module: distinctive Persian/English aliases matched
deterministically. Used to power the mini world-map badge on each story.
"""
from __future__ import annotations

import re

# code, fa, en, aliases (distinctive forms only)
COUNTRIES: list[dict] = [
    {"code": "US", "fa": "ایالات متحده", "en": "United States",
     "aliases": ["ایالات متحده", "آمریکا", "واشنگتن", "کاخ سفید", "پنتاگون"]},
    {"code": "GB", "fa": "بریتانیا", "en": "United Kingdom",
     "aliases": ["بریتانیا", "انگلیس", "انگلستان", "لندن", "داونینگ"]},
    {"code": "FR", "fa": "فرانسه", "en": "France",
     "aliases": ["فرانسه", "پاریس", "الیزه"]},
    {"code": "DE", "fa": "آلمان", "en": "Germany",
     "aliases": ["آلمان", "برلین"]},
    {"code": "IT", "fa": "ایتالیا", "en": "Italy", "aliases": ["ایتالیا", "رم"]},
    {"code": "ES", "fa": "اسپانیا", "en": "Spain", "aliases": ["اسپانیا", "مادرید"]},
    {"code": "RU", "fa": "روسیه", "en": "Russia",
     "aliases": ["روسیه", "مسکو", "کرملین", "پوتین"]},
    {"code": "UA", "fa": "اوکراین", "en": "Ukraine",
     "aliases": ["اوکراین", "کی‌یف", "کییف", "زلنسکی"]},
    {"code": "TR", "fa": "ترکیه", "en": "Turkey",
     "aliases": ["ترکیه", "آنکارا", "استانبول", "اردوغان"]},
    {"code": "IL", "fa": "اسرائیل", "en": "Israel",
     "aliases": ["اسرائیل", "رژیم صهیونیستی", "تل‌آویو", "تل آویو", "نتانیاهو"]},
    {"code": "PS", "fa": "فلسطین", "en": "Palestine",
     "aliases": ["فلسطین", "غزه", "کرانه باختری", "رام‌الله"]},
    {"code": "SA", "fa": "عربستان سعودی", "en": "Saudi Arabia",
     "aliases": ["عربستان سعودی", "عربستان", "ریاض", "بن سلمان"]},
    {"code": "AE", "fa": "امارات", "en": "UAE",
     "aliases": ["امارات", "ابوظبی", "دبی"]},
    {"code": "QA", "fa": "قطر", "en": "Qatar",
     "aliases": ["قطر", "دوحه"]},
    {"code": "KW", "fa": "کویت", "en": "Kuwait", "aliases": ["کویت"]},
    {"code": "OM", "fa": "عمان", "en": "Oman",
     "aliases": ["عمان", "مسقط", "صلاله"]},
    {"code": "BH", "fa": "بحرین", "en": "Bahrain", "aliases": ["بحرین"]},
    {"code": "IQ", "fa": "عراق", "en": "Iraq",
     "aliases": ["عراق", "بغداد", "دهوک", "اربیل"]},
    {"code": "SY", "fa": "سوریه", "en": "Syria",
     "aliases": ["سوریه", "دمشق"]},
    {"code": "LB", "fa": "لبنان", "en": "Lebanon",
     "aliases": ["لبنان", "بیروت", "حزب الله", "حزب‌الله"]},
    {"code": "YE", "fa": "یمن", "en": "Yemen",
     "aliases": ["یمن", "صنعا", "انصارالله"]},
    {"code": "JO", "fa": "اردن", "en": "Jordan",
     "aliases": ["اردن", "امان", "عمان(اردن)"]},
    {"code": "EG", "fa": "مصر", "en": "Egypt",
     "aliases": ["مصر", "قاهره", "السیسی"]},
    {"code": "LY", "fa": "لیبی", "en": "Libya", "aliases": ["لیبی", "طرابلس"]},
    {"code": "SD", "fa": "سودان", "en": "Sudan", "aliases": ["سودان", "خارطوم"]},
    {"code": "SO", "fa": "سومالی", "en": "Somalia", "aliases": ["سومالی"]},
    {"code": "AF", "fa": "افغانستان", "en": "Afghanistan",
     "aliases": ["افغانستان", "کابل", "طالبان"]},
    {"code": "PK", "fa": "پاکستان", "en": "Pakistan",
     "aliases": ["پاکستان", "اسلام‌آباد", "اسلام آباد"]},
    {"code": "IN", "fa": "هند", "en": "India",
     "aliases": ["هندوستان", "دهلی نو", "دهلی‌نو", "مودی"]},
    {"code": "CN", "fa": "چین", "en": "China",
     "aliases": ["چین", "پکن", "شی جین‌پینگ", "شی جین پینگ"]},
    {"code": "JP", "fa": "ژاپن", "en": "Japan", "aliases": ["ژاپن", "توکیو"]},
    {"code": "KR", "fa": "کره جنوبی", "en": "South Korea",
     "aliases": ["کره جنوبی", "سئول"]},
    {"code": "KP", "fa": "کره شمالی", "en": "North Korea",
     "aliases": ["کره شمالی", "پیونگ یانگ", "پیونگ‌یانگ", "کیم جونگ"]},
    {"code": "AZ", "fa": "آذربایجان", "en": "Azerbaijan",
     "aliases": ["جمهوری آذربایجان", "باکو", "علی اف"]},
    {"code": "AM", "fa": "ارمنستان", "en": "Armenia",
     "aliases": ["ارمنستان", "ایروان"]},
    {"code": "GE", "fa": "گرجستان", "en": "Georgia", "aliases": ["گرجستان", "تفلیس"]},
    {"code": "TM", "fa": "ترکمنستان", "en": "Turkmenistan",
     "aliases": ["ترکمنستان", "عشق‌آباد", "عشق آباد"]},
    {"code": "AT", "fa": "اتریش", "en": "Austria",
     "aliases": ["اتریش", "وین"]},
    {"code": "CH", "fa": "سوئیس", "en": "Switzerland",
     "aliases": ["سوئیس", "ژنو", "زوریخ"]},
    {"code": "NL", "fa": "هلند", "en": "Netherlands", "aliases": ["هلند", "آمستردام"]},
    {"code": "BE", "fa": "بلژیک", "en": "Belgium", "aliases": ["بلژیک", "بروکسل"]},
    {"code": "PL", "fa": "لهستان", "en": "Poland", "aliases": ["لهستان", "ورشو"]},
    {"code": "SE", "fa": "سوئد", "en": "Sweden", "aliases": ["سوئد", "استکهلم"]},
    {"code": "NO", "fa": "نروژ", "en": "Norway", "aliases": ["نروژ", "اسلو"]},
    {"code": "CA", "fa": "کانادا", "en": "Canada",
     "aliases": ["کانادا", "اتاوا", "تورنتو"]},
    {"code": "MX", "fa": "مکزیک", "en": "Mexico", "aliases": ["مکزیک", "مکزیکو"]},
    {"code": "BR", "fa": "برزیل", "en": "Brazil", "aliases": ["برزیل", "برازیلیا"]},
    {"code": "AR", "fa": "آرژانتین", "en": "Argentina",
     "aliases": ["آرژانتین", "بوینس آیرس", "بوینس‌آیرس"]},
    {"code": "VE", "fa": "ونزوئلا", "en": "Venezuela", "aliases": ["ونزوئلا", "کاراکاس"]},
    {"code": "AU", "fa": "استرالیا", "en": "Australia", "aliases": ["استرالیا", "کانبرا"]},
    {"code": "NZ", "fa": "نیوزیلند", "en": "New Zealand", "aliases": ["نیوزیلند"]},
    {"code": "ZA", "fa": "آفریقای جنوبی", "en": "South Africa",
     "aliases": ["آفریقای جنوبی", "پرتوریا"]},
]

_LETTER = r"[A-Za-z0-9ء-ۓ۰-۹‌]"


def _compile(alias: str) -> re.Pattern:
    return re.compile(r"(?<!" + _LETTER + r")" + re.escape(alias) + r"(?!" + _LETTER + r")")


_COMPILED = [(c, [_compile(a) for a in c["aliases"]]) for c in COUNTRIES]


def detect(text: str) -> list[dict]:
    """Return countries mentioned in `text`, as [{code, name_fa}]."""
    if not text:
        return []
    out = []
    for c, pats in _COMPILED:
        if any(p.search(text) for p in pats):
            out.append({"code": c["code"], "name_fa": c["fa"]})
    return out
