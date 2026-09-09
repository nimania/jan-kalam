"""Geographic classification of stories: which Iranian province(s) and scope.

Keyword-based and deterministic (no AI). Each story is classified as:
  • local        (استانی/محلی) — a specific Iranian province/city is named,
  • national     (کشوری)       — Iran-wide but no specific province,
  • international (بین‌المللی)  — no Iran relevance.

Province keywords are the province name + a few of its notable cities. Full
two-word province names (e.g. «آذربایجان غربی») avoid cross-matching.
"""
from __future__ import annotations

import re

# A keyword matches only as a whole word — not inside another word (so the city
# «لار» does not match inside «دلار»). Boundary = not a letter/digit/ZWNJ.
_B = r"[A-Za-z0-9؀-ۿ‌]"


def _compile(words: list[str]) -> list:
    return [re.compile(rf"(?<!{_B}){re.escape(w)}(?!{_B})") for w in words]


# slug -> (name_fa, [keywords])
PROVINCES: dict[str, tuple[str, list[str]]] = {
    "west-azerbaijan": ("آذربایجان غربی", ["آذربایجان غربی", "ارومیه", "مهاباد", "خوی", "میاندوآب", "بوکان"]),
    "east-azerbaijan": ("آذربایجان شرقی", ["آذربایجان شرقی", "تبریز", "مراغه", "مرند", "اهر"]),
    "ardabil": ("اردبیل", ["اردبیل", "مشگین‌شهر", "پارس‌آباد", "خلخال"]),
    "gilan": ("گیلان", ["گیلان", "رشت", "انزلی", "لاهیجان", "بندرانزلی", "رودسر"]),
    "mazandaran": ("مازندران", ["مازندران", "ساری", "بابل", "آمل", "نوشهر", "چالوس", "قائم‌شهر", "تنکابن"]),
    "golestan": ("گلستان", ["گلستان", "گرگان", "گنبد", "علی‌آباد", "آق‌قلا"]),
    "north-khorasan": ("خراسان شمالی", ["خراسان شمالی", "بجنورد", "شیروان", "اسفراین"]),
    "razavi-khorasan": ("خراسان رضوی", ["خراسان رضوی", "مشهد", "نیشابور", "سبزوار", "تربت"]),
    "south-khorasan": ("خراسان جنوبی", ["خراسان جنوبی", "بیرجند", "قائن", "طبس"]),
    "semnan": ("سمنان", ["سمنان", "شاهرود", "گرمسار", "دامغان"]),
    "tehran": ("تهران", ["تهران", "شهرری", "ورامین", "اسلامشهر", "شمیرانات", "پاکدشت"]),
    "alborz": ("البرز", ["البرز", "کرج", "فردیس", "نظرآباد", "هشتگرد"]),
    "qazvin": ("قزوین", ["قزوین", "تاکستان", "آبیک", "الوند"]),
    "zanjan": ("زنجان", ["زنجان", "ابهر", "خدابنده", "خرمدره"]),
    "hamadan": ("همدان", ["همدان", "ملایر", "نهاوند", "اسدآباد"]),
    "kurdistan": ("کردستان", ["کردستان", "سنندج", "سقز", "مریوان", "بانه", "قروه"]),
    "kermanshah": ("کرمانشاه", ["کرمانشاه", "اسلام‌آباد غرب", "هرسین", "سنقر", "جوانرود"]),
    "ilam": ("ایلام", ["ایلام", "دهلران", "مهران", "آبدانان", "ایوان"]),
    "lorestan": ("لرستان", ["لرستان", "خرم‌آباد", "بروجرد", "دورود", "الیگودرز"]),
    "markazi": ("مرکزی", ["استان مرکزی", "اراک", "ساوه", "خمین", "محلات"]),
    "qom": ("قم", ["قم", "قمرود", "جمکران"]),
    "isfahan": ("اصفهان", ["اصفهان", "کاشان", "نجف‌آباد", "خمینی‌شهر", "شاهین‌شهر", "فولادشهر"]),
    "chaharmahal": ("چهارمحال و بختیاری", ["چهارمحال", "بختیاری", "شهرکرد", "بروجن", "فارسان"]),
    "khuzestan": ("خوزستان", ["خوزستان", "اهواز", "آبادان", "خرمشهر", "دزفول", "ماهشهر", "بهبهان", "ایذه"]),
    "kohgiluyeh": ("کهگیلویه و بویراحمد", ["کهگیلویه", "بویراحمد", "یاسوج", "گچساران", "دوگنبدان"]),
    "bushehr": ("بوشهر", ["بوشهر", "برازجان", "گناوه", "دیر", "کنگان", "عسلویه"]),
    "fars": ("فارس", ["فارس", "شیراز", "مرودشت", "کازرون", "جهرم", "فسا", "لار", "داراب"]),
    "hormozgan": ("هرمزگان", ["هرمزگان", "بندرعباس", "بندرلنگه", "میناب", "قشم", "کیش"]),
    "kerman": ("کرمان", ["کرمان", "رفسنجان", "سیرجان", "جیرفت", "بم", "زرند"]),
    "yazd": ("یزد", ["یزد", "میبد", "اردکان", "بافق", "مهریز"]),
    "sistan": ("سیستان و بلوچستان", ["سیستان", "بلوچستان", "زاهدان", "زابل", "چابهار", "ایرانشهر", "سراوان"]),
}

# Iran-wide (national) indicators — matched only when no province is found.
NATIONAL = [
    "ایران", "کشور", "سراسری", "دولت", "مجلس شورای اسلامی", "مجلس", "وزارت", "وزیر",
    "قوه قضاییه", "رئیس‌جمهور", "رئیس جمهور", "بانک مرکزی", "شورای نگهبان", "ملی",
    "iran", "tehran", "iranian",
]

SCOPE_FA = {"local": "استانی", "national": "کشوری", "international": "بین‌المللی"}

# Precompiled boundary-aware matchers.
_PROV_PATS = {slug: (fa, _compile(kws)) for slug, (fa, kws) in PROVINCES.items()}
_NAT_PATS = _compile(NATIONAL)


def classify(text: str | None) -> dict:
    """Return {scope, provinces:[{slug,name_fa}]} for a story's combined text."""
    t = text or ""
    provinces: list[dict] = []
    for slug, (fa, pats) in _PROV_PATS.items():
        if any(p.search(t) for p in pats):
            provinces.append({"slug": slug, "name_fa": fa})
        if len(provinces) >= 2:
            break
    if provinces:
        return {"scope": "local", "provinces": provinces}
    if any(p.search(t) for p in _NAT_PATS):
        return {"scope": "national", "provinces": []}
    return {"scope": "international", "provinces": []}


def stats(cards: list[dict]) -> dict:
    """Aggregate province counts + scope counts across the feed cards."""
    prov: dict[str, int] = {}
    scope = {"local": 0, "national": 0, "international": 0}
    for c in cards:
        g = c.get("geo") or {}
        s = g.get("scope", "international")
        scope[s] = scope.get(s, 0) + 1
        for p in g.get("provinces", []):
            prov[p["slug"]] = prov.get(p["slug"], 0) + 1
    return {"provinces": prov, "scope": scope}
