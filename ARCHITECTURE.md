# Jan Kalam — Architecture

> Minimum viable architecture for the MVP. Deliberately simple; prepared for
> growth but not over-engineered (no microservices, Kafka, or Kubernetes).

## 1. High-level shape

```
            ┌────────────────────────── Backend (Python / FastAPI) ──────────────────────────┐
 Sources    │  Ingestion → Normalization → Dedup → Embedding → Clustering → AI pipeline →     │   Android
 (RSS/Atom/ │  Ranking → Persisted Stories                                                    │   (Kotlin /
  JSON/API) │                                                                                 │   Compose)
    ──────► │  PostgreSQL (+ pgvector)   ◄── Repositories ──►  Services  ──►  REST API  ──────►│  ◄──────
            └─────────────────────────────────────────────────────────────────────────────────┘
                         ▲                                                        │
                     Background jobs (scheduled polling / processing)      Admin API (internal QC)
```

Two deployables only: **the backend** and **the Android app**. Everything else is
a module inside the backend.

## 2. Backend module map

```
backend/
  app/
    core/         config, logging, security helpers
    db/           engine, session, Base
    models/       SQLAlchemy ORM (the tables)
    schemas/      Pydantic request/response models
    repositories/ data-access (query) layer, no business logic
    services/     business logic (stories, sources, topics, ask)
    api/          FastAPI routers (versioned under /api/v1)
    ingestion/    feed fetchers + normalizer + dedup (Phase 2)
    clustering/   similarity + story clustering (Phase 3)
    ai/           pipeline stages + provider adapters + validation (Phase 4)
    ranking/      importance scoring (Phase 3+)
    tasks/        background job orchestration (Phase 2+)
  alembic/        migrations
  tests/          pytest suite
```

### Layering rule
`api → services → repositories → models`. Routers never touch the ORM directly;
services never build SQL by hand — they call repositories. This keeps the AI and
ingestion subsystems swappable.

## 3. Data model (conceptual)

Tables: `users`, `sources`, `articles`, `stories`, `story_articles`,
`entities`, `topics`, `story_topics`, `source_views`, `facts`, `user_follows`.

Key relationships:

- An **article** belongs to exactly one **source**.
- A **story** is a cluster of many articles via **story_articles** (M:N with a
  relevance weight). This is how "3 outlets, 1 event" collapses to one story.
- **source_views**, **facts**, **entities** hang off a story and are the
  materialized four-layer output (fact / source-view / synthesis / uncertainty).
- **topics** link to stories via **story_topics**; **user_follows** links users
  to topics (or, later, entities).

The full four-layer AI output is stored on the story row as structured columns +
child rows so it is computed **once** and cached (see §7).

## 4. AI output schema (conceptual — see `ai/schemas`)

```jsonc
{
  "headline_fa": "...", "summary_fa": "...",
  "what_happened_fa": "...", "why_it_matters_fa": "...",
  "facts": [], "uncertainties": [],
  "source_views": [], "agreements": [], "disagreements": [],
  "entities": [], "topics": [],
  "importance_score": 0, "confidence_score": 0, "sources": []
}
```

The conceptual separation is preserved even if column layout differs. Every AI
stage has an explicit input/output JSON schema and every model response is
validated before it is trusted or stored.

## 5. AI pipeline (modular stages, never one giant prompt)

```
ARTICLE → Classification → Entity extraction → Fact extraction → Event extraction
→ Embedding → Story clustering → Source comparison → Synthesis → Persian Jan Kalam
→ Quality checks
```

**Model tiering for cost control:** cheap/fast models for classification, tagging,
dedup, entity extraction; stronger models for synthesis, source comparison, and
complex user questions. A provider-adapter interface (`ai/providers`) keeps the
app independent of any one vendor; keys live only in backend env.

## 6. Clustering

Combine normalized titles, extracted entities, publication-time proximity,
keyword overlap, and vector embeddings (pgvector cosine similarity). A candidate
article joins an existing story if its combined similarity clears a threshold;
otherwise it seeds a new story. Goal: no duplicate stories.

## 7. Cost control & caching

AI output is **never** regenerated on read. A story's Jan Kalam, facts, and source
views are generated once during processing and served from the DB. Regeneration
is explicit (admin action or new material joining the cluster). A usage log
records tokens, model, cost estimate, and latency per call.

## 8. Ranking

Importance score from explainable factors: number of *independent* sources,
geopolitical/economic significance, Iran relevance, event magnitude, novelty,
source reliability, coverage velocity, and user-followed topics. The feed sorts by
this score; the score is stored and explainable, not a black box.

## 9. Background jobs

A lightweight scheduler (APScheduler-style in-process to start; can move to a
worker + queue later) runs: poll sources → normalize → dedup → cluster → AI
process → rank. No Kafka/Celery unless genuinely required.

## 10. Security

Secrets via environment variables only (`.env`, never committed; `.env.example`
documents required vars). Model/DB keys never reach the Android client.
Authorization is enforced server-side. Tokens stored securely on device.

## 11. Observability

Structured logging; counters for ingestion failures, malformed feeds, AI
failures, clustering failures, API errors, and latency. `GET /health` (and
`/health/ready`) report liveness/readiness.

## 12. Android architecture

Clean architecture — `presentation` (Compose + Material 3, RTL-first) → `domain`
(use cases, models) → `data` (repositories) → `network` (Retrofit/Ktor) +
`database` (Room cache) + `di` + `core`. Persian-first design throughout.

## 13. Technology choices (and why)

| Concern | Choice | Rationale |
|---------|--------|-----------|
| API framework | FastAPI | async, typed, Pydantic-native, fast to build |
| ORM | SQLAlchemy 2.0 | mature, DB-agnostic, async-capable |
| Validation | Pydantic v2 | shared schema between API and AI I/O |
| DB | PostgreSQL + pgvector | relational integrity + semantic search in one store |
| Migrations | Alembic | versioned schema |
| Tests | pytest + SQLite | fast, hermetic; prod stays Postgres |
| Mobile | Kotlin + Jetpack Compose + Material 3 | modern, RTL-capable, native |

### Test/prod DB note
Models are written DB-agnostic so the suite runs on **SQLite** with zero external
services, while production targets **Postgres**. Postgres-only features
(pgvector columns, GIN indexes) are added via migrations guarded by dialect so
they never break the SQLite test path.
