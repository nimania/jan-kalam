# Jan Kalam — Roadmap

Phased delivery. Each phase ends with a report: **COMPLETED · FILES · TESTS ·
DECISIONS · NEXT**. Do not advance while the current phase's tests fail.

## Phase 0 — Discovery & specs  ✅ (this milestone)
Inspect environment, define the product and minimum viable architecture.
Deliverables: `PRODUCT_SPEC.md`, `ARCHITECTURE.md`, `ROADMAP.md`, `README.md`.

## Phase 1 — Backend foundation  ✅ (this milestone)
FastAPI app · config · SQLAlchemy models (all MVP tables) · Alembic migration ·
basic read API (sources, stories, topics) · health checks · seed script · tests
green on SQLite.

## Phase 2 — Ingestion  ⏳ next
RSS/Atom/JSON fetchers · normalization into the `Article` model · content-hash
dedup · per-source usage-rule config · ingestion logs. Verified with test feeds /
fixtures (no reliance on live copyrighted content in tests).

## Phase 3 — Story clustering & ranking
Embeddings + similarity · cluster articles into stories · story/article
relationships with weights · explainable importance ranking. Tested with
synthetic articles describing the same event.

## Phase 4 — AI pipeline
Classification → entities → fact extraction → source-view extraction →
uncertainty → synthesis → Persian Jan Kalam. Structured outputs, every response
validated, model tiering for cost, usage logging. Provider adapter behind an
interface; keys server-side only.

## Phase 5 — Android app
Home · Story page · Source comparison · Ask · Topics · Follow. Mocked data first,
then wired to the backend. RTL-first Compose UI.

## Phase 6 — Quality
UI polish · RTL audit · accessibility · loading/error/empty states · caching ·
performance · crash prevention.

## Phase 7 — Release prep (human-reviewed, never auto-published)
Release build · signing · AAB · icon · splash · screenshots · store description ·
privacy policy · data-safety form · Play Store checklist.

## Guardrails carried through every phase
Source attribution and the fact/view/synthesis/uncertainty separation are
invariants. Secrets in env only. AI output cached, never regenerated on read.
Copyright-safe by design. No overbuild.
