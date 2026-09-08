# Jan Kalam (جان‌کلام) — Product Specification

> AI-powered Persian-language news intelligence. Version 0.1 (MVP scope).

## 1. Vision

Persian-speaking users should not have to read 20 articles or search the web to
understand what is happening in the world. Jan Kalam turns the global information
stream into concise, contextual, source-aware Persian intelligence.

It is **not** an RSS reader, **not** a translation app, and **not** an
article-republishing platform. It is a new *information layer* on top of
legitimate news sources.

Core workflow:

```
SOURCE MATERIAL → NEWS EVENTS → STORY CLUSTERS → FACT EXTRACTION
→ SOURCE/VIEWPOINT ANALYSIS → AI SYNTHESIS → PERSIAN "JAN KALAM"
→ USER QUESTIONS → CONTEXT OVER TIME
```

## 2. Target user

Persian speakers who care about Iran, international affairs, geopolitics,
economics, technology, AI, and culture, and who have limited time. They want the
answers to five questions for any story:

1. What happened?
2. What matters?
3. What are different sources saying?
4. What is fact vs. interpretation?
5. Why does this matter to me (and to Iran)?

## 3. Core product principle — the four layers

Every story separates four kinds of statement and never silently mixes them:

| Layer | Meaning |
|-------|---------|
| **FACT** | Directly supported by sources. |
| **SOURCE VIEW** | What a specific publication or commentator says/argues. |
| **SYNTHESIS** | What the AI can reasonably infer by comparing material. |
| **UNCERTAINTY** | What remains unknown, disputed, or unverified. |

The data model, the AI output schema, and the UI all preserve this separation.

## 4. MVP features (and only these)

### A. Home feed
Important current stories, **ranked by importance, not chronology**. Each card:
category, Persian headline, Persian Jan Kalam summary, importance indicator,
number of sources, timestamp, source names.

Categories: `iran`, `world`, `politics`, `economy`, `technology`, `ai`, `culture`.

### B. Story page
Persian headline · Jan Kalam synthesis (80–150 Persian words) · What happened? ·
Why does it matter? · What are sources saying? (each source's viewpoint shown
separately) · What is known? (bullets) · What is uncertain? (bullets) · Sources
(name, original headline, publication time, link). Full articles are never
reproduced.

### C. Ask
"Ask about this" on every story. The AI answers **only** from the story and its
sources, and clearly distinguishes fact from inference. Suggested Persian
prompts: چرا این خبر مهم است؟ · ساده‌تر توضیح بده · منابع مختلف چه می‌گویند؟ ·
چه چیزی هنوز مشخص نیست؟ · این موضوع چه ارتباطی با ایران دارد؟

### D. Follow topics
Users follow topics (Iran, US Politics, AI, Bitcoin, Russia-Ukraine, …). Backend
maintains topic relationships; architecture supports future personalized alerts.
For MVP, follow persistence may be local or basic server-side.

## 5. Content & copyright policy (by design, not bolted on)

The product is built around **summarization, synthesis, attribution, and
linking**. It must never reproduce full articles, provide full translations of
copyrighted articles, copy source images unless permitted, or make the original
article unnecessary to access. Every story shows source + original headline +
brief AI summary + link to the original. Per-source usage rules are
**configuration**, so extraction behavior varies by source — the architecture
never *requires* full-text republication.

## 6. Editorial quality

No clickbait. If a source headline is sensational, Jan Kalam reports what the
underlying material actually supports, distinguishing reported fact from headline
framing. No manufactured ideological differences and no political labels unless
supported by reliable metadata.

## 7. Iran relevance

A differentiator is explaining world developments through relevance to
Persian-speaking users — but relevance is never manufactured. When there is none,
the story says plainly: «ارتباط مستقیمی با ایران ندارد.»

## 8. Persian language bar

Natural Persian journalistic prose, not sentence-by-sentence machine translation.
Avoid excessive formalism, unnecessary Arabic constructions, sensationalism, and
unsupported conclusions. Correct RTL. Designed Persian-first — never an English UI
"flipped" later.

## 9. Explicitly out of scope for MVP

Social networking, comments, complex recommenders, payments, ads, iOS, desktop,
elaborate admin dashboards, microservices, Kubernetes, event streaming. The
architecture is *prepared* for later direction (morning/evening briefs, alerts,
voice/podcast, topic timelines, "what changed since yesterday?", reliability
indicators, web/iOS, subscriptions) but none is built yet.

## 10. Quality bar

Prioritize, in order: correctness · source attribution · factual separation ·
Persian language quality · speed · simple UX · maintainability · cost efficiency ·
security · visual polish. Optimize for **trust and usefulness**, not feature count.
