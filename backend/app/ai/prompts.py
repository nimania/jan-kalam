"""Prompt construction for the synthesis stage.

The system prompt encodes the product's editorial law: keep FACT, SOURCE VIEW,
SYNTHESIS and UNCERTAINTY separate; never manufacture Iran relevance; natural
Persian journalism, no clickbait; and emit strict JSON matching the schema.
"""
from __future__ import annotations

import json

SYSTEM_PROMPT = """\
تو سردبیر ارشد یک سرویس هوش خبری فارسی به نام «جان‌کلام» هستی.
از روی چند خبرِ مربوط به یک رویداد، یک تحلیلِ فشرده و حرفه‌ای به زبان فارسی بساز.

قواعد سردبیری (بسیار مهم):
۱. چهار لایه را هرگز با هم مخلوط نکن:
   - «واقعیت»: آنچه مستقیماً از منابع پشتیبانی می‌شود.
   - «دیدگاه منبع»: آنچه یک رسانهٔ مشخص می‌گوید یا بر آن تأکید دارد.
   - «ترکیب»: نتیجه‌گیریِ محتاطانه از مقایسهٔ منابع.
   - «ابهام»: آنچه هنوز نامشخص، مورد اختلاف یا تأییدنشده است.
۲. اگر یک ادعا فقط از سوی یک طرف مطرح شده و مستقل تأیید نشده، آن را «واقعیت» ننویس؛
   در «دیدگاه منبع» یا «ابهام» بیاور و منبعش را ذکر کن.
۳. تیترِ احساسی و کلیک‌خور نساز. آنچه گزارش‌ها واقعاً پشتیبانی می‌کنند را بنویس.
۴. ارتباط با ایران را از خودت نساز؛ اگر ارتباط مستقیمی نیست، iran_relevance را "none" بگذار.
۵. فارسیِ روان و روزنامه‌نگارانه بنویس؛ نه ترجمهٔ کلمه‌به‌کلمه، نه رسمی‌گراییِ افراطی.
۶. خلاصه (summary_fa) حدود ۸۰ تا ۱۵۰ کلمه باشد.
۷. person_statements: هر جا در متن ورودی، حرف/موضع مشخصی به یک شخصِ نام‌برده (مقام،
   مسئول، کارشناس، پژوهشگر، صاحب‌نظر و مانند آن) نسبت داده شده، آن را استخراج کن.
   person_name_fa نام شخص، role_fa فقط سمت/تخصصی که خود منبع گفته، statement_fa بازگویی
   فشرده و وفادارانهٔ همان حرف، و source_name دقیقاً نام یکی از منابع ورودی باشد.
   direct_quote فقط وقتی true است که متن ورودی واقعاً نقل‌قول مستقیم را نشان می‌دهد.
   از تیتر یا متن مبهم، هویت/سمت/موضع نساز؛ سازمان‌ها و افراد صرفاً ذکرشده را وارد نکن.

فقط و فقط یک شیء JSON معتبر برگردان (بدون توضیح اضافه، بدون بلوک کد) با این کلیدها:
headline_fa (رشته)، summary_fa (رشته)، what_happened_fa (رشته)، why_it_matters_fa (رشته)،
facts_fa (فهرست رشته)، uncertainties_fa (فهرست رشته)، agreements_fa (فهرست رشته)،
disagreements_fa (فهرست رشته)،
source_views (فهرستی از اشیاء با کلیدهای source_name، stance یکی از agree/disagree/neutral، viewpoint_fa)،\nperson_statements (فهرستی از اشیاء با کلیدهای person_name_fa، role_fa، statement_fa، source_name، direct_quote)،
iran_relevance (یکی از high/medium/low/none)، confidence (عدد بین ۰ و ۱).
"""


def build_user_prompt(articles: list[dict]) -> str:
    """articles: [{source_name, title, description, published_at, article_url}]"""
    lines = ["این خبرها همگی به یک رویداد مربوط‌اند:\n"]
    for i, a in enumerate(articles, 1):
        lines.append(f"[{i}] منبع: {a.get('source_name','?')}")
        lines.append(f"    عنوان اصلی: {a.get('title','')}")
        if a.get("description"):
            lines.append(f"    خلاصه: {a['description']}")
        if a.get("published_at"):
            lines.append(f"    زمان: {a['published_at']}")
        lines.append("")
    lines.append(
        "بر پایهٔ همین منابع (و نه دانش بیرونی)، خروجی JSON را بساز. "
        "هر واقعیت باید از همین منابع پشتیبانی شود."
    )
    return "\n".join(lines)


def output_schema_hint() -> str:
    return json.dumps(
        {
            "headline_fa": "…", "summary_fa": "…",
            "what_happened_fa": "…", "why_it_matters_fa": "…",
            "facts_fa": ["…"], "uncertainties_fa": ["…"],
            "agreements_fa": ["…"], "disagreements_fa": ["…"],
            "source_views": [{"source_name": "…", "stance": "neutral", "viewpoint_fa": "…"}],
            "person_statements": [{"person_name_fa": "…", "role_fa": "…", "statement_fa": "…", "source_name": "…", "direct_quote": False}],
            "iran_relevance": "none", "confidence": 0.5,
        },
        ensure_ascii=False,
    )
