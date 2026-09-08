"""Our own, automated credibility signal — deliberately simple and transparent.

It is NOT a truth verdict (that is what professional fact-checkers like Factnameh
do). It only reflects what our own pipeline can observe about a story:

  • how many INDEPENDENT sources reported it,
  • whether those sources AGREE or DISAGREE on specifics.

A single-source story is flagged as "needs independent verification". Everything
here is derived from data already in the story — no extra AI call.
"""
from __future__ import annotations


def compute_credibility(detail: dict) -> dict:
    n = int(detail.get("source_count") or 0)
    agreements = len(detail.get("agreements") or [])
    disagreements = len(detail.get("disagreements") or [])
    single = n <= 1

    if n >= 3 and disagreements == 0:
        level, label = "high", "چند منبع، بدون تناقض"
    elif n >= 2 and disagreements == 0:
        level, label = "medium", "دو منبع، بدون تناقض"
    elif n >= 2:
        level, label = "medium", "چند منبع، با نقاط اختلاف"
    else:
        level, label = "low", "تک‌منبع — نیازمند راستی‌آزمایی"

    parts: list[str] = []
    parts.append(
        f"این خبر را {_faN(n)} منبعِ مستقل گزارش کرده‌اند." if n
        else "برای این خبر منبعِ مستقلِ ثبت‌شده‌ای نیست."
    )
    if agreements:
        parts.append(f"{_faN(agreements)} نقطهٔ اشتراک میان منابع شناسایی شده است.")
    if disagreements:
        parts.append(f"{_faN(disagreements)} نقطهٔ اختلاف میان منابع وجود دارد؛ با احتیاط بخوانید.")
    if single:
        parts.append("چون فقط یک منبع آن را گزارش کرده، تا تأییدِ منبعِ مستقلِ دیگر قطعی نیست.")

    return {
        "level": level,
        "label_fa": label,
        "independent_sources": n,
        "agreements": agreements,
        "disagreements": disagreements,
        "single_source": single,
        "needs_verification": single,
        "note_fa": " ".join(parts),
    }


def _faN(x) -> str:
    return str(x).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
