"""The AI output contract for one story's Persian "Jan Kalam".

Raw model output is NEVER trusted: every response is validated against these
Pydantic models before it is stored. Validation failure => the story is not
published and the failure is logged.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

Stance = Literal["agree", "disagree", "neutral"]
IranRel = Literal["high", "medium", "low", "none"]


class SourceViewItem(BaseModel):
    source_name: str = Field(min_length=1, max_length=200)
    stance: Stance = "neutral"
    viewpoint_fa: str = Field(min_length=1)


class JanKalamOutput(BaseModel):
    """One story's full synthesized output, four layers kept separate."""

    headline_fa: str = Field(min_length=1, max_length=500)
    summary_fa: str = Field(min_length=1)               # the Jan Kalam (~80-150 words)
    what_happened_fa: str = Field(min_length=1)
    why_it_matters_fa: str = Field(min_length=1)

    facts_fa: list[str] = Field(default_factory=list)          # supported by sources
    uncertainties_fa: list[str] = Field(default_factory=list)  # unknown / disputed
    agreements_fa: list[str] = Field(default_factory=list)
    disagreements_fa: list[str] = Field(default_factory=list)

    source_views: list[SourceViewItem] = Field(default_factory=list)

    iran_relevance: IranRel = "none"
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("facts_fa", "uncertainties_fa", "agreements_fa", "disagreements_fa")
    @classmethod
    def _strip_empty(cls, v: list[str]) -> list[str]:
        return [s.strip() for s in v if s and s.strip()]

    @field_validator("summary_fa")
    @classmethod
    def _not_placeholder_english(cls, v: str) -> str:
        # A light guard: the synthesis must contain Persian characters, so we
        # never silently publish an all-English blob as the "Persian" summary.
        if not any("؀" <= ch <= "ۿ" for ch in v):
            raise ValueError("summary_fa must contain Persian text")
        return v
