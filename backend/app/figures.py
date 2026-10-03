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
    bale: str | None = None  # verified public Bale channel handle (without @)
    external: bool = False  # profile is fed by non-Telegram collectors (Truth Social, web, etc.)
    aliases: tuple[str, ...] = ()  # alternate public names matched into the same profile


FIGURES: list[Figure] = [
    # ══════════════════════════════════════════════════════════════════════
    #  سیاست و جامعه
    # ══════════════════════════════════════════════════════════════════════
    Figure("Garajetadayoni", "مهدی تدینی", "مورخ و مترجم", "politics"),
    Figure("ahmadzeidabad", "احمد زیدآبادی", "روزنامه‌نگار و تحلیلگر سیاسی", "politics"),
    Figure("abdiabbas", "عباس عبدی", "روزنامه‌نگار و پژوهشگر اجتماعی", "politics", bale="ayandeha"),
    Figure("fazeli_mohammad", "محمد فاضلی", "جامعه‌شناس", "politics",
           (("website", "https://mohammadfazeli.ir"),)),
    Figure("miladdokhanchi", "میلاد دخانچی", "پژوهشگر مطالعات فرهنگی", "politics"),
    Figure("iranemana_official", "سجاد فتاحی", "پژوهشگر، کانال «ایرانِ مانا»", "politics",
           (("youtube", "https://youtube.com/@iran_mana"),)),
    Figure("iransocialproblems", "علی میرزامحمدی", "جامعه‌شناس", "politics"),
    Figure("rasaee", "حمید رسایی", "نماینده مجلس و مدیرمسئول هفته‌نامه ۹ دی", "politics"),
    Figure("sadeghzibakalam", "صادق زیباکلام", "استاد علوم سیاسی دانشگاه تهران", "politics",
           (("facebook", "https://facebook.com/SadeghZibakalam"),), bale="sadeghzibakalamofficial"),
    Figure("Parvanehsalahshouri", "پروانه سلحشوری", "جامعه‌شناس و نمایندهٔ سابق مجلس",
           "politics", (), "f"),
    Figure("SaeedHajarian", "سعید حجاریان", "نظریه‌پرداز سیاسی", "politics"),
    Figure("Mostafatajzadeh", "مصطفی تاجزاده", "فعال سیاسی اصلاح‌طلب", "politics"),
    Figure("Dr_hfalahatpisheh", "حشمت‌الله فلاحت‌پیشه",
           "نمایندهٔ سابق مجلس و تحلیلگر امنیت ملی", "politics"),
    Figure("emadbaghi", "عمادالدین باقی", "روزنامه‌نگار و فعال حقوق بشر", "law"),
    Figure("m_borhani57", "محسن برهانی", "حقوقدان و استاد حقوق جزا", "law"),
    Figure("Ghabl_enghelab", "وحید اشتری", "فعال اجتماعی و روزنامه‌نگار", "politics", bale="ghabl_enghelab"),
    Figure("sabety_ir", "امیرحسین ثابتی", "نماینده مجلس", "politics", bale="sabety_ir"),
    Figure("yaminpour", "وحید یامین‌پور", "نویسنده و پژوهشگر", "politics", bale="yaminpour"),
    Figure("ali_gholhaky", "علی قلهکی", "روزنامه‌نگار و تحلیلگر سیاسی", "politics", bale="ali_gholhaki"),
    Figure("MalekShariati_ir", "مالک شریعتی نیاسر", "نماینده مجلس", "politics", bale="malekshariati"),
    Figure("kasaeizade", "سید هادی کسایی‌زاده", "روزنامه‌نگار", "media",
           (("x", "https://x.com/seyedhadikasaei"),), bale="kasaeizade"),
    Figure("hasanabbasi_students", "حسن عباسی", "سخنران و پژوهشگر", "politics", bale="hasanabbasi_students"),

    # ══════════════════════════════════════════════════════════════════════
    #  چهره‌های تکمیلی — پروفایل واحد، منابع مستقیم و گفته در خبر
    # ══════════════════════════════════════════════════════════════════════
    Figure("reza-alijani", "رضا علیجانی", "روزنامه‌نگار و تحلیلگر سیاسی", "politics", external=True),
    Figure("mahmoud-farjami", "محمود فرجامی", "نویسنده و پژوهشگر رسانه", "media", external=True),
    Figure("rashid-kakavand", "رشید کاکاوند", "نویسنده و پژوهشگر ادبیات", "culture", external=True),
    Figure("mansour-zabetian", "منصور ضابطیان", "نویسنده و مجری", "media", external=True),
    Figure("nezameddin-mousavi", "نظام‌الدین موسوی", "فعال رسانه‌ای و سیاسی", "politics", external=True),
    Figure("jamshid-assadi", "جمشید اسدی", "اقتصاددان و استاد دانشگاه", "economy", external=True),
    Figure("reza-taghizadeh", "رضا تقی‌زاده", "روزنامه‌نگار و تحلیلگر", "foreign", external=True),
    Figure("asghar-sepehri", "اصغر سپهری", "فعال سیاسی", "politics",
           (("x", "https://x.com/AsgharSepehri"),), external=True),
    Figure("farzan-deljou", "فرزان دلجو", "هنرمند", "culture", external=True),
    Figure("shohreh-aghdashloo", "شهره آغداشلو", "بازیگر", "cinema", (), "f", external=True),
    Figure("mohsen-makhmalbaf", "محسن مخملباف", "فیلم‌ساز و نویسنده", "cinema", external=True),
    Figure("nader-fattourechi", "نادر فتوره‌چی", "نویسنده و روزنامه‌نگار", "media", external=True),
    Figure("hasan-shariatmadari", "حسن شریعتمداری", "فعال سیاسی", "politics", external=True),
    Figure("hossein-shariatmadari", "حسین شریعتمداری", "روزنامه‌نگار", "media", external=True),
    Figure("faraj-sarkouhi", "فرج سرکوهی", "نویسنده و روزنامه‌نگار", "media", external=True),
    Figure("fazel-nazari", "فاضل نظری", "شاعر و نویسنده", "culture", external=True),
    Figure("fardad-farahzad", "فرداد فرحزاد", "روزنامه‌نگار و مجری", "media", external=True),
    Figure("mirhossein-mousavi", "میرحسین موسوی", "فعال سیاسی", "politics", external=True),
    Figure("mehdi-karroubi", "مهدی کروبی", "فعال سیاسی", "politics", external=True),
    Figure("mohammad-khatami", "سیدمحمد خاتمی", "فعال سیاسی", "politics", external=True,
           aliases=("محمد خاتمی",)),
    Figure("hojat-kalashi", "حجت کلاشی", "پژوهشگر و فعال سیاسی", "politics", external=True),
    Figure("sepideh-gholian", "سپیده قلیان", "فعال مدنی", "law", (), "f", external=True),
    Figure("mazdak-bamdadan", "مزدک بامدادان (محسن بنایی)", "نویسنده و پژوهشگر تاریخ", "history",
           external=True, aliases=("مزدک بامدادان", "محسن بنایی", "محسن بنائی")),
    Figure("nasser-karami", "ناصر کرمی", "پژوهشگر محیط‌زیست", "environment", external=True),
    Figure("vahid-jalili", "وحید جلیلی", "فعال فرهنگی و رسانه‌ای", "media", external=True),
    Figure("mehdi-jamshidi", "مهدی جمشیدی", "پژوهشگر فرهنگ و اندیشه", "culture", external=True),
    Figure("shahriar-zarshenas", "شهریار زرشناس", "نویسنده و پژوهشگر فلسفه و سیاست", "culture", external=True),
    Figure("sajjad-saffar-harandi", "محمدسجاد صفار هرندی", "جامعه‌شناس و پژوهشگر فرهنگی", "society", external=True, aliases=("سجاد صفار هرندی", "محمد سجاد صفار هرندی")),
    Figure("hasan-shamaizadeh", "حسن شماعی‌زاده", "خواننده و آهنگساز", "culture", external=True),
    Figure("hila-sedighi", "هیلا صدیقی", "شاعر و هنرمند", "culture",
           (("website", "https://www.hilasedighi.com/"),), "f", external=True),
    Figure("yaghma-golrouee", "یغما گلرویی", "شاعر و ترانه‌سرا", "culture",
           (("telegram", "https://t.me/yaghmagolrouee"),), external=True),
    Figure("ebi-hamedi", "ابی (ابراهیم حامدی)", "خواننده", "culture",
           (("website", "https://ebihamedi.com/"),), external=True,
           aliases=("ابی", "ابراهیم حامدی")),
    Figure("dariush-eghbali", "داریوش اقبالی", "خواننده و فعال اجتماعی", "culture",
           (("website", "https://dariush2000.com/"),), external=True,
           aliases=("داریوش",)),
    Figure("leila-forouhar", "لیلا فروهر", "خواننده و بازیگر", "culture",
           (("telegram", "https://t.me/Leilaforouhar"),), "f", external=True),
    Figure("googoosh", "گوگوش", "خواننده و بازیگر", "culture",
           (("telegram", "https://t.me/Googoosh"),), "f", external=True,
           aliases=("فائقه آتشین", "فائقه آتشین گوگوش")),
    Figure("arash-azizi", "آرش عزیزی", "نویسنده و پژوهشگر تاریخ", "history", external=True),
    Figure("keyvan-abbassi", "کیوان عباسی", "مدیر رسانه", "media", external=True),
    Figure("javad-zarif", "محمدجواد ظریف", "دیپلمات", "foreign", external=True,
           aliases=("محمد جواد ظریف",)),
    Figure("masoud-behnoud", "مسعود بهنود", "روزنامه‌نگار و نویسنده", "media", external=True),
    Figure("shirin-ebadi", "شیرین عبادی", "حقوقدان و فعال حقوق بشر", "law", (), "f", external=True),
    Figure("narges-mohammadi", "نرگس محمدی", "فعال حقوق بشر", "law", (), "f", external=True),
    Figure("elnaz-shakerdoost", "الناز شاکردوست", "بازیگر", "cinema", (), "f", external=True),
    Figure("zagros-rashidi", "زاگرس رشیدی", "پژوهشگر ژئوپلیتیک", "foreign", external=True),
    Figure("hossein-entezami", "حسین انتظامی", "مدیر فرهنگی و رسانه‌ای", "media", external=True),
    Figure("mahnaz-shirali", "مهناز شیرالی", "جامعه‌شناس و پژوهشگر", "society", (), "f", external=True),
    Figure("fayaz-zahed", "فیاض زاهد", "روزنامه‌نگار و تحلیلگر سیاسی", "politics", external=True),

    # ══════════════════════════════════════════════════════════════════════
    #  چهره‌های بین‌المللی — منابع چندزبانه
    # ══════════════════════════════════════════════════════════════════════
    Figure("donald-trump", "دونالد ترامپ", "رئیس‌جمهور ایالات متحده", "foreign",
           (("website", "https://www.whitehouse.gov/administration/donald-j-trump/"),
            ("truthsocial", "https://truthsocial.com/@realDonaldTrump")), external=True),

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
    Figure("Karimipour_K", "یدالله کریمی‌پور", "پژوهشگر ژئوپلیتیک", "foreign"),
    Figure("MehdiMotaharnia1344", "مهدی مطهرنیا", "پژوهشگر آینده‌پژوهی و روابط بین‌الملل", "foreign"),
    Figure("majidtafreshi", "مجید تفرشی", "تاریخ‌نگار و پژوهشگر مسائل معاصر", "foreign",
           (("x", "https://x.com/majidtafreshi"),)),
    Figure("yekhezaran", "حسین جابری‌انصاری", "دیپلمات و پژوهشگر مسائل منطقه‌ای", "foreign",
           (("instagram", "https://instagram.com/jaberi_ansari"),)),
    Figure("covid_policy_dip", "کوروش احمدی", "دیپلمات بازنشسته و پژوهشگر روابط بین‌الملل", "foreign"),

    # ══════════════════════════════════════════════════════════════════════
    #  جامعه و اندیشهٔ اجتماعی
    # ══════════════════════════════════════════════════════════════════════
    Figure("mfarasatkhah", "مقصود فراستخواه", "جامعه‌شناس و استاد آموزش عالی", "society"),
    Figure("dr_bokharaei", "احمد بخارایی", "جامعه‌شناس", "society"),
    Figure("darwinsabouri", "داروین صبوری", "جامعه‌شناس", "society",
           (("youtube", "https://youtube.com/@darwinsabouri"),)),
    Figure("mostafadaneshgar", "مصطفی دانشگر", "نویسنده و پژوهشگر مسائل ایران", "society"),
    Figure("DrAzarakhshMokri", "آذرخش مکری", "روان‌پزشک و مدرس دانشگاه", "society",
           (("youtube", "https://youtube.com/@DrAzarakhshMokriOfficial"),
            ("instagram", "https://instagram.com/azarakhshmokri"))),
    Figure("bahadaf", "فرهنگ هلاکویی", "روان‌شناس و مدرس", "society",
           (("website", "https://bahadaf.ir"),
            ("instagram", "https://instagram.com/dr.f_holakouee"))),
    Figure("drsiminkazemi", "سیمین کاظمی", "پزشک و جامعه‌شناس", "society", (), "f"),
    Figure("hamidrezajalaeipour", "حمیدرضا جلایی‌پور", "جامعه‌شناس سیاسی", "society"),
    Figure("nasserfakouhi", "ناصر فکوهی", "انسان‌شناس و استاد دانشگاه", "society",
           (("website", "https://nasserfakouhi.com"),)),
    Figure("jalaeipour", "محمدرضا جلایی‌پور", "جامعه‌شناس و پژوهشگر سیاست‌گذاری اجتماعی", "society",
           (("instagram", "https://instagram.com/m.jalaeipour"),)),
    Figure("mostafamehraeen", "مصطفی مهرآیین", "جامعه‌شناس و پژوهشگر فرهنگ", "society"),
    Figure("DrNematallahFazeli", "نعمت‌الله فاضلی", "انسان‌شناس و پژوهشگر مطالعات فرهنگی", "society"),
    Figure("Renani_Mohsen", "محسن رنانی", "اقتصاددان و پژوهشگر توسعه", "society",
           (("website", "https://renani.net"),)),

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
    Figure("mohsenjalalpour", "محسن جلال‌پور", "فعال بخش خصوصی و تحلیلگر اقتصادی", "economy"),
    Figure("Sadegh_Alhosseini", "صادق الحسینی", "پژوهشگر اقتصاد و سیاست‌گذاری", "economy",
           (("x", "https://x.com/alhosseini"),
            ("instagram", "https://instagram.com/sadegh_alhosseini"))),
    Figure("ali_sarzaeem", "علی سرزعیم", "اقتصاددان", "economy",
           (("website", "https://sarzaeem.ir"),)),

    # ══════════════════════════════════════════════════════════════════════
    #  محیط‌زیست
    # ══════════════════════════════════════════════════════════════════════
    Figure("KavehMadani", "کاوه مدنی", "پژوهشگر آب و محیط‌زیست", "environment"),
    Figure("darvishnameh", "محمد درویش", "فعال محیط‌زیست", "environment", bale="darvishnameh"),

    # ══════════════════════════════════════════════════════════════════════
    #  رسانه و تحلیل
    # ══════════════════════════════════════════════════════════════════════
    Figure("HosseinBastaniChannel", "حسین باستانی", "روزنامه‌نگار و تحلیلگر", "media"),
    Figure("mohajerimohamad", "محمد مهاجری", "روزنامه‌نگار", "media",
           (("x", "https://x.com/mohmohajeri"),)),
    Figure("NegarMim", "نگار مرتضوی", "روزنامه‌نگار و تحلیلگر سیاسی", "media", (), "f"),
    Figure("hoderestan", "حسین درخشان", "نویسنده و پژوهشگر رسانه", "media"),
    Figure("iraj_mesdaghi", "ایرج مصداقی", "نویسنده و تحلیلگر سیاسی", "media",
           (("website", "https://irajmesdaghi.com"),)),
    Figure("iranoralhistory", "حسین دهباشی", "تاریخ‌پژوه و مستندساز", "media",
           (("instagram", "https://instagram.com/hossein.dehbashi2020"),)),
    Figure("KGhafouri", "کامبیز غفوری", "روزنامه‌نگار", "media",
           (("x", "https://x.com/KambizGhafouri"),
            ("instagram", "https://instagram.com/kambiz.ghafouri.public"))),
    Figure("mohamadaliabtahi", "محمدعلی ابطحی", "روحانی و فعال سیاسی", "media"),
    Figure("DrMahdiKhazali", "مهدی خزعلی", "پزشک و فعال سیاسی", "politics",
           (("x", "https://twitter.com/mahdi_khazali"),
            ("instagram", "https://instagram.com/mahdikhazali"))),
    Figure("vahidBahman1", "وحید بهمن", "پژوهشگر و تحلیلگر مسائل ایران و منطقه", "politics"),
    Figure("shahinnajafimusic", "شاهین نجفی", "خواننده و ترانه‌سرا", "culture"),
    Figure("Imansoleymaniamiri", "ایمان سلیمانی امیری", "نویسنده و منتقد دین", "religion",
           (("instagram", "https://instagram.com/imansoleimaniamiri"),
            ("youtube", "https://www.youtube.com/channel/UCTeJ9xtTseVNYCRnmV7Mtdw"))),
    Figure("FahimehKhezr", "فهیمه خضر حیدری", "روزنامه‌نگار و مجری", "media", (), "f"),
    Figure("MoradVaisi_Live", "مراد ویسی", "روزنامه‌نگار و تحلیلگر", "media"),
    Figure("farhoodi", "بیژن فرهودی", "روزنامه‌نگار و مصاحبه‌گر", "media"),
    Figure("mahdiehgolroo", "مهدیه گلرو", "فعال سیاسی", "politics", (), "f"),
    Figure("masih_alinejad", "مسیح علینژاد", "روزنامه‌نگار و فعال سیاسی", "media",
           (("x", "https://twitter.com/AlinejadMasih"),
            ("instagram", "https://instagram.com/masih.alinejad")), "f"),

    # ══════════════════════════════════════════════════════════════════════
    #  دین و اندیشهٔ دینی
    # ══════════════════════════════════════════════════════════════════════
    Figure("Baznegari", "امیر ترکاشوند", "پژوهشگر تاریخ و متون دینی", "religion"),
    Figure("abolghasemfanaei", "ابوالقاسم فنائی", "پژوهشگر فلسفه اخلاق و دین", "religion",
           (("instagram", "https://instagram.com/Abolghasemfanaei"),)),
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
    Figure("Mardihamorteza", "مرتضی مردیها", "پژوهشگر فلسفه و علوم انسانی", "philosophy",
           (("instagram", "https://instagram.com/mardihamorteza"),
            ("youtube", "https://youtube.com/@MortazaMardiha"))),
    Figure("khalajich", "مهدی خلجی", "پژوهشگر علوم انسانی و اندیشه", "philosophy"),
    Figure("Soroushdabbagh_Official", "سروش دباغ", "پژوهشگر فلسفه", "philosophy",
           (("x", "https://x.com/dabbaghsoroush"),
            ("instagram", "https://instagram.com/soroush_dabbagh"))),
    Figure("bijanabdolkarimi", "بیژن عبدالکریمی", "فیلسوف و استاد فلسفه", "philosophy", bale="bijanabdolkarimi"),

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
    Figure("Dr_Lashkarbolouki", "مجتبی لشکربلوکی", "پژوهشگر استراتژی و توسعه",
           "development", (("website", "https://lashkarbolouki.com"),)),
    Figure("sharenovate", "امیر ناظمی", "پژوهشگر سیاست‌گذاری علم، فناوری و توسعه",
           "development"),
    Figure("taghirahmani", "تقی رحمانی", "نویسنده و فعال سیاسی", "opposition"),
    Figure("mojvahedi", "مجتبی واحدی", "روزنامه‌نگار و تحلیلگر سیاسی", "opposition"),
    Figure("Reasondoubt", "غزال مدیریان", "پژوهشگر و فعال سیاسی", "opposition"),
    Figure("mohsensazegara", "محسن سازگارا", "تحلیلگر سیاسی", "opposition",
           (("youtube", "https://youtube.com/@MohsenSazegara"),)),

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
             "youtube": "یوتیوب", "facebook": "فیس‌بوک", "telegram": "تلگرام", "bale": "بله",
             "truthsocial": "تروث سوشیال", "eitaa": "ایتا", "rubika": "روبیکا",
             "soroush": "سروش‌پلاس", "igap": "آی‌گپ"}


def figure_social(f: Figure) -> list[dict]:
    """Public links for a figure, Telegram channel first."""
    links = [] if f.external else [{"kind": "telegram", "label": SOCIAL_FA["telegram"],
              "url": f"https://t.me/{f.handle}"}]
    if f.bale:
        links.append({"kind": "bale", "label": SOCIAL_FA["bale"], "url": f"https://ble.ir/{f.bale}"})
    for kind, url in f.social:
        links.append({"kind": kind, "label": SOCIAL_FA.get(kind, kind), "url": url})
    return links


def figure_source_name(f: Figure) -> str:
    # Unique across `sources` (news outlets use their own names).
    return f"چهره: {f.name_fa}"


def figure_feed_url(f: Figure) -> str:
    return "" if f.external else f"https://t.me/s/{f.handle}"


def figure_home_url(f: Figure) -> str:
    if f.external:
        return next((url for kind, url in f.social if kind in {"truthsocial", "website"}), "")
    return f"https://t.me/{f.handle}"
