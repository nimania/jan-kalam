"""The 'Ask about this story' feature.

Phase 1 provides an honest, deterministic answer built ONLY from the story's
stored material (facts, uncertainties, source views). It never invents content.
Phase 4 plugs a validated LLM into `_answer_with_ai` behind the same interface,
still constrained to the story's own material and still labelling fact vs.
inference.
"""
from __future__ import annotations

from app.core.config import settings
from app.models.enums import StatementKind
from app.models.story import Story
from app.schemas.story import AskAnswer


def _facts(story: Story) -> list[str]:
    return [s.text_fa for s in story.statements if s.kind == StatementKind.fact]


def _uncertainties(story: Story) -> list[str]:
    return [s.text_fa for s in story.statements if s.kind == StatementKind.uncertainty]


def answer(story: Story, question: str) -> AskAnswer:
    ai_on = settings.ai_provider != "none" and bool(settings.ai_api_key)
    facts = _facts(story)

    # Phase 1: grounded, template-based Persian answer from stored material only.
    parts: list[str] = []
    if story.summary_fa:
        parts.append(story.summary_fa)
    if facts:
        parts.append("آنچه قطعی است: " + "؛ ".join(facts))
    unc = _uncertainties(story)
    if unc:
        parts.append("آنچه هنوز نامشخص است: " + "؛ ".join(unc))

    if not parts:
        answer_fa = "برای این خبر هنوز اطلاعات کافی پردازش نشده است."
    else:
        answer_fa = " ".join(parts)

    note = (
        None
        if ai_on
        else "پاسخ فقط از روی اطلاعات ذخیره‌شدهٔ همین خبر ساخته شده است "
        "(پاسخ‌گویی هوش مصنوعی در فاز ۴ فعال می‌شود)."
    )
    return AskAnswer(
        story_id=story.id,
        question=question,
        answer_fa=answer_fa,
        used_facts=facts,
        inferred=False,
        ai_available=ai_on,
        note=note,
    )
