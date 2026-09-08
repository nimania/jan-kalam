"""Deterministic offline provider — used when no AI key is configured.

It builds a STRUCTURALLY valid Jan Kalam output from the clustered articles
themselves (real source names and headlines), but it does NOT invent Persian
synthesis: the summary plainly says the automatic Jan Kalam is produced once an
AI key is added. This keeps the whole pipeline runnable and testable offline
without ever passing placeholder text off as real analysis.
"""
from __future__ import annotations

import time

from app.ai.providers.base import ProviderResult
from app.ranking.importance import count_iran_hits, iran_relevance_label


class MockProvider:
    name = "mock"

    def generate(self, *, system: str, user: str, context: dict) -> ProviderResult:
        started = time.perf_counter()
        articles: list[dict] = context.get("articles", [])
        names: list[str] = []
        for a in articles:
            n = a.get("source_name")
            if n and n not in names:
                names.append(n)
        n = len(names)
        joined = "، ".join(names) if names else "چند منبع"

        iran_hits = count_iran_hits(
            *[a.get("title") for a in articles],
            *[a.get("description") for a in articles],
        )

        data = {
            "headline_fa": f"رویداد خبری با پوشش {n} منبع مستقل",
            "summary_fa": (
                f"این رویداد را {n} منبع پوشش داده‌اند ({joined}). "
                "خوشه‌بندی و تفکیک منابع انجام شده است؛ جان‌کلامِ خودکارِ فارسی و "
                "تحلیل چهار‌لایه پس از افزودن کلید هوش مصنوعی (مدل واقعی) تولید می‌شود."
            ),
            "what_happened_fa": (
                f"چند منبع مستقل یک رویداد واحد را گزارش کرده‌اند و سیستم آن‌ها را در "
                "یک خبر خوشه‌بندی کرده است."
            ),
            "why_it_matters_fa": (
                "ارزیابی اهمیت و زمینه، پس از تولید جان‌کلام با مدل هوش مصنوعی کامل می‌شود."
            ),
            "facts_fa": [f"«{a.get('source_name','?')}» این رویداد را گزارش کرده است."
                         for a in articles],
            "uncertainties_fa": [
                "تحلیل تفصیلیِ واقعیت‌ها و ابهام‌ها پس از پردازش با مدل هوش مصنوعی افزوده می‌شود."
            ],
            "agreements_fa": [],
            "disagreements_fa": [],
            "source_views": [
                {
                    "source_name": a.get("source_name", "?"),
                    "stance": "neutral",
                    "viewpoint_fa": f"عنوان اصلی این منبع: «{a.get('title','')}».",
                }
                for a in articles
            ],
            "iran_relevance": iran_relevance_label(iran_hits),
            "confidence": 0.3,
        }
        latency = int((time.perf_counter() - started) * 1000)
        return ProviderResult(data=data, model="mock", latency_ms=latency)
