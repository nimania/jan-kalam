"""جان‌کلام چهره‌ها — public commentators followed via their Telegram channels.

Figures are DATA, not code: add, remove or edit people here and the next build
picks it up (scripts/seed.py syncs this list into the `sources` table, marked
with region = FIGURE_REGION).

Editorial rules this list must keep:
  • Mix of viewpoints — the section is only fair if no single camp dominates.
  • `role_fa` is a neutral job description (historian, economist…), never a
    political label. Readers judge viewpoints from the posts themselves.
  • A figure's posts are OPINION. They never enter the news "facts" layer and
    never count as an independent news source (see clustering).
"""
from __future__ import annotations

from dataclasses import dataclass

FIGURE_REGION = "figure"   # Source.region value that marks a figure's channel


@dataclass(frozen=True, slots=True)
class Figure:
    handle: str        # Telegram channel username (without @)
    name_fa: str
    role_fa: str       # neutral description shown on the figure's page
    field: str         # politics | foreign | economy | history | culture
    # Their other public presence, as (kind, url). kind ∈ website|x|instagram|
    # youtube|facebook. The Telegram channel link is added automatically — don't
    # repeat it here. Only add links we have actually verified.
    social: tuple[tuple[str, str], ...] = ()


FIGURES: list[Figure] = [
    # --- سیاست و جامعه ---
    Figure("Garajetadayoni", "مهدی تدینی", "مورخ و مترجم", "politics"),
    Figure("ahmadzeidabad", "احمد زیدآبادی", "روزنامه‌نگار و تحلیلگر سیاسی", "politics"),
    Figure("abdiabbas", "عباس عبدی", "روزنامه‌نگار و پژوهشگر اجتماعی", "politics"),
    Figure("fazeli_mohammad", "محمد فاضلی", "جامعه‌شناس", "politics",
           (("website", "https://mohammadfazeli.ir"),)),
    Figure("miladdokhanchi", "میلاد دخانچی", "پژوهشگر مطالعات فرهنگی", "politics"),
    Figure("iranemana_official", "سجاد فتاحی", "پژوهشگر، کانال «ایرانِ مانا»", "politics",
           (("youtube", "https://youtube.com/@iran_mana"),)),
    Figure("iransocialproblems", "علی میرزامحمدی", "جامعه‌شناس", "politics"),
    Figure("rasaee", "حمید رسایی", "نماینده مجلس و مدیرمسئول هفته‌نامه ۹ دی", "politics"),
    # --- سیاست خارجی ---
    Figure("sahandiranmehr", "سهند ایرانمهر", "پژوهشگر روابط بین‌الملل", "foreign",
           (("x", "https://x.com/sahandiranmehr"),
            ("youtube", "https://youtube.com/@sahandiranmehr"))),
    Figure("IzadiFoad", "فواد ایزدی", "استاد دانشکده مطالعات جهان دانشگاه تهران", "foreign",
           (("x", "https://x.com/IzadiFoad"),
            ("instagram", "https://instagram.com/izadifoad"))),
    # --- تاریخ ---
    Figure("abdollahshahbazi", "عبدالله شهبازی", "مورخ", "history",
           (("website", "https://shahbazi.org"),
            ("x", "https://twitter.com/ashahb"),
            ("facebook", "https://facebook.com/abdollah.shahbazi"))),
    # --- اقتصاد ---
    Figure("ghaninejad_mousa", "موسی غنی‌نژاد", "اقتصاددان", "economy"),
    Figure("HosseinRaghfar", "حسین راغفر", "اقتصاددان", "economy"),
    Figure("farshad_momeni", "فرشاد مومنی", "اقتصاددان", "economy"),
    # --- فرهنگ و هنر ---
    Figure("bahman_babazadeh", "بهمن بابازاده", "خبرنگار موسیقی", "culture"),
]


SOCIAL_FA = {"website": "وب‌سایت", "x": "ایکس", "instagram": "اینستاگرام",
             "youtube": "یوتیوب", "facebook": "فیس‌بوک", "telegram": "تلگرام"}


def figure_social(f: Figure) -> list[dict]:
    """Public links for a figure, Telegram channel first."""
    links = [{"kind": "telegram", "label": SOCIAL_FA["telegram"],
              "url": f"https://t.me/{f.handle}"}]
    for kind, url in f.social:
        links.append({"kind": kind, "label": SOCIAL_FA.get(kind, kind), "url": url})
    return links


def figure_source_name(f: Figure) -> str:
    # Unique across `sources` (news outlets use their own names).
    return f"چهره: {f.name_fa}"


def figure_feed_url(f: Figure) -> str:
    return f"https://t.me/s/{f.handle}"


def figure_home_url(f: Figure) -> str:
    return f"https://t.me/{f.handle}"
