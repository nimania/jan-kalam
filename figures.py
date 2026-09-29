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
    field: str         # must be a key of FIELD_FA (see figure_posts.py)
    # Their other public presence, as (kind, url). kind ∈ website|x|instagram|
    # youtube|facebook. The Telegram channel link is added automatically — don't
    # repeat it here. Only add links we have actually verified.
    social: tuple[tuple[str, str], ...] = ()
    gender: str = "m"  # "m" | "f" — used for balance / future comparison stats


FIGURES: list[Figure] = [
    # ══════════════════════════════════════════════════════════════════════
    #  سیاست و جامعه
    # ══════════════════════════════════════════════════════════════════════
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
    Figure("sadeghzibakalam", "صادق زیباکلام", "استاد علوم سیاسی دانشگاه تهران", "politics",
           (("facebook", "https://facebook.com/SadeghZibakalam"),)),
    Figure("Parvanehsalahshouri", "پروانه سلحشوری", "جامعه‌شناس و نمایندهٔ سابق مجلس",
           "politics", (), "f"),
    Figure("SaeedHajarian", "سعید حجاریان", "نظریه‌پرداز سیاسی", "politics"),
    Figure("Mostafatajzadeh", "مصطفی تاجزاده", "فعال سیاسی اصلاح‌طلب", "politics"),
    Figure("Dr_hfalahatpisheh", "حشمت‌الله فلاحت‌پیشه",
           "نمایندهٔ سابق مجلس و تحلیلگر امنیت ملی", "politics"),
    Figure("emadbaghi", "عمادالدین باقی", "روزنامه‌نگار و فعال حقوق بشر", "law"),
    Figure("m_borhani57", "محسن برهانی", "حقوقدان و استاد حقوق جزا", "law"),

    # ══════════════════════════════════════════════════════════════════════
    #  سیاست خارجی
    # ══════════════════════════════════════════════════════════════════════
    Figure("sahandiranmehr", "سهند ایرانمهر", "پژوهشگر روابط بین‌الملل", "foreign",
           (("x", "https://x.com/sahandiranmehr"),
            ("youtube", "https://youtube.com/@sahandiranmehr"))),
    Figure("IzadiFoad", "فواد ایزدی", "استاد دانشکده مطالعات جهان دانشگاه تهران", "foreign",
           (("x", "https://x.com/IzadiFoad"),
            ("instagram", "https://instagram.com/izadifoad"))),
    Figure("rezanasrichannel", "رضا نصری", "حقوقدان بین‌المللی و تحلیلگر دیپلماسی", "foreign"),

    # ══════════════════════════════════════════════════════════════════════
    #  جامعه و اندیشهٔ اجتماعی
    # ══════════════════════════════════════════════════════════════════════
    Figure("mfarasatkhah", "مقصود فراستخواه", "جامعه‌شناس و استاد آموزش عالی", "society"),
    Figure("dr_bokharaei", "احمد بخارایی", "جامعه‌شناس", "society"),
    Figure("drsiminkazemi", "سیمین کاظمی", "پزشک و جامعه‌شناس", "society", (), "f"),
    Figure("hamidrezajalaeipour", "حمیدرضا جلایی‌پور", "جامعه‌شناس سیاسی", "society"),

    # ══════════════════════════════════════════════════════════════════════
    #  اقتصاد
    # ══════════════════════════════════════════════════════════════════════
    Figure("ghaninejad_mousa", "موسی غنی‌نژاد", "اقتصاددان", "economy"),
    Figure("HosseinRaghfar", "حسین راغفر", "اقتصاددان", "economy"),
    Figure("farshad_momeni", "فرشاد مومنی", "اقتصاددان", "economy"),
    Figure("masoudnili", "مسعود نیلی", "اقتصاددان و مشاور اقتصادی", "economy"),
    Figure("MohammadTabibian", "محمد طبیبیان", "اقتصاددان و استاد دانشگاه", "economy"),
    Figure("economics_and_finance", "پویا ناظران", "اقتصاددان", "economy"),
    Figure("ahemmati", "عبدالناصر همتی", "اقتصاددان و رئیس سابق بانک مرکزی", "economy"),

    # ══════════════════════════════════════════════════════════════════════
    #  محیط‌زیست
    # ══════════════════════════════════════════════════════════════════════
    Figure("KavehMadani", "کاوه مدنی", "پژوهشگر آب و محیط‌زیست", "environment"),
    Figure("darvishnameh", "محمد درویش", "فعال محیط‌زیست", "environment"),

    # ══════════════════════════════════════════════════════════════════════
    #  رسانه و تحلیل
    # ══════════════════════════════════════════════════════════════════════
    Figure("HosseinBastaniChannel", "حسین باستانی", "روزنامه‌نگار و تحلیلگر بی‌بی‌سی", "media"),
    Figure("NegarMim", "نگار مرتضوی", "روزنامه‌نگار و تحلیلگر سیاسی", "media", (), "f"),
    Figure("hoderestan", "حسین درخشان", "نویسنده و پژوهشگر رسانه", "media"),

    # ══════════════════════════════════════════════════════════════════════
    #  دین و اندیشهٔ دینی
    # ══════════════════════════════════════════════════════════════════════
    Figure("Mohsen_Kadivar_Official", "محسن کدیور", "پژوهشگر دین و فلسفهٔ دین", "religion",
           (("website", "https://kadivar.com"),)),
    Figure("mohammadsorooshmahallati", "محمد سروش محلاتی", "پژوهشگر فقه و اندیشهٔ دینی",
           "religion"),
    Figure("NewHasanMohaddesi", "حسن محدثی", "جامعه‌شناس دین", "religion"),
    Figure("nasiri42", "مهدی نصیری", "نویسنده و تحلیلگر دین و سیاست", "religion"),

    # ══════════════════════════════════════════════════════════════════════
    #  فلسفه و اندیشه
    # ══════════════════════════════════════════════════════════════════════
    Figure("mostafamalekian", "مصطفی ملکیان", "پژوهشگر فلسفه و اخلاق", "philosophy"),
    Figure("Soroushdabbagh_Official", "سروش دباغ", "پژوهشگر فلسفه", "philosophy",
           (("x", "https://x.com/dabbaghsoroush"),
            ("instagram", "https://instagram.com/soroush_dabbagh"))),
    Figure("bijanabdolkarimi", "بیژن عبدالکریمی", "فیلسوف و استاد فلسفه", "philosophy"),

    # ══════════════════════════════════════════════════════════════════════
    #  تاریخ
    # ══════════════════════════════════════════════════════════════════════
    Figure("abdollahshahbazi", "عبدالله شهبازی", "مورخ", "history",
           (("website", "https://shahbazi.org"),
            ("x", "https://twitter.com/ashahb"),
            ("facebook", "https://facebook.com/abdollah.shahbazi"))),

    # ══════════════════════════════════════════════════════════════════════
    #  علوم سیاسی و توسعه
    # ══════════════════════════════════════════════════════════════════════
    Figure("sariolghalam", "محمود سریع‌القلم", "استاد علوم سیاسی و روابط بین‌الملل",
           "development"),
    Figure("mohsensazegara", "محسن سازگارا", "تحلیلگر سیاسی", "opposition",
           (("youtube", "https://youtube.com/@MohsenSazegara"),)),
    Figure("OfficialRezaPahlavi", "رضا پهلوی", "چهرهٔ اپوزیسیون", "opposition",
           (("website", "https://rezapahlavi.org"),
            ("x", "https://x.com/PahsReza"))),

    # ══════════════════════════════════════════════════════════════════════
    #  سینما و نقد
    # ══════════════════════════════════════════════════════════════════════
    Figure("massoud_farassatI", "مسعود فراستی", "منتقد سینما و ادبیات", "cinema"),

    # ══════════════════════════════════════════════════════════════════════
    #  فرهنگ و هنر
    # ══════════════════════════════════════════════════════════════════════
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
