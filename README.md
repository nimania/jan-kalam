# Jan Kalam (جان‌کلام)

AI-powered Persian-language news intelligence. This repo currently contains the
**backend (Phases 0–4)**. See `PRODUCT_SPEC.md`, `ARCHITECTURE.md`,
and `ROADMAP.md` for the full plan.

## What exists today (Phases 1–4)

- FastAPI app with a versioned API under `/api/v1`.
- All MVP database tables (SQLAlchemy 2.0 models): users, sources, articles,
  stories, story_articles, source_views, statements (facts/uncertainties/
  agreements/disagreements), entities, topics, story_topics, user_follows,
  ingestion_logs.
- Read API for the home feed and story page, the **Ask** endpoint (grounded,
  no-AI-yet answers), topic follow/unfollow, and a minimal internal **admin** API.
- **Ingestion (Phase 2):** RSS / Atom / JSON-Feed fetch → normalize → two-layer
  content-hash + URL dedup → persist, with per-run `ingestion_logs`. Parsing is
  pure and offline-testable; a lightweight `run_ingestion_cycle()` runner is ready
  for scheduling. Per-source usage rules (`allow_full_content`, `allow_image`)
  decide what is retained — the copyright policy is enforced in the parser.
- **Clustering + ranking (Phase 3):** explainable lexical + time-proximity
  similarity groups articles about the same event into one story ("3 outlets →
  1 story, 3 sources"); an explainable importance score (independent sources,
  reliability, coverage velocity, recency, Iran relevance) ranks the feed, and
  Iran relevance + category are derived from the clustered articles. Admin
  endpoints `POST /admin/cluster` and `POST /admin/rank`.
- **AI synthesis pipeline (Phase 4):** a draft (clustered) story → `provider.generate`
  → **validated** against a Pydantic contract (raw model output is never trusted)
  → the Persian Jan Kalam + four layers are persisted and the story is
  **published**. A provider adapter runs a deterministic **mock offline (no key)**
  so the whole pipeline works and is tested without any network or key; setting an
  Anthropic key switches to real Persian generation with no code change. Every
  call is cost-logged (`usage_logs`: tokens, model, cost estimate, latency), and
  output is produced once then served from the DB — never regenerated on read.
- The fact / source-view / synthesis / uncertainty separation is enforced in the
  data model and preserved in every API response.
- Three Alembic migrations for the whole schema; a seed script with sample sources
  (incl. Persian outlets), topics, and a demo story.
- **42 passing tests** (health, models, sources, stories, ranking, Ask, topics,
  ingestion, clustering, and AI: schema validation, publish flow, idempotency,
  provider-error and invalid-output handling, usage logging).

- **Web app v1 (PWA):** an installable, RTL Persian progressive web app in
  `backend/webapp/` (home feed, story page with the four layers, live **Ask**,
  topic follow). It is served by the backend itself at `/`, talks to the live
  `/api/v1`, works offline via a service worker, and installs to a phone home
  screen — no app store needed (well suited to distribution constraints). A
  native Android app is a possible later phase.

## Run the web app (the product)

```bash
cd backend
python -m scripts.seed        # sample data (or run the full ingest→cluster→rank→synthesize chain)
uvicorn app.main:app          # serves BOTH the API and the web app
# open http://127.0.0.1:8000/   → the Jan Kalam web app (installable PWA)
# http://127.0.0.1:8000/docs    → API docs
```

### Enabling real AI (optional)
Without a key the pipeline uses the offline mock. To generate real Persian
synthesis, set in `.env`:

```bash
AI_PROVIDER=anthropic
AI_API_KEY=sk-ant-...        # server-side only; never shipped to the app
AI_MODEL_STRONG=claude-3-5-sonnet-latest
```

Then run the pipeline (see below). The full chain is:
`ingest → cluster → rank → synthesize`, each exposed as an admin endpoint
(`POST /api/v1/admin/{ingest,cluster,rank,synthesize}`).

## Run ingestion

```bash
cd backend
python -m app.tasks.scheduler       # one full pass over all enabled sources
# or per source via the admin API:
#   POST /api/v1/admin/ingest
#   POST /api/v1/admin/sources/{id}/ingest
#   GET  /api/v1/admin/ingestion-logs
```

## Requirements

Python 3.11+. Postgres is the production database; **tests and local dev default
to SQLite**, so you need nothing external to run everything below.

## Setup

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then edit as needed; never commit .env
```

## Run the tests

```bash
cd backend
python -m pytest                # 18 tests, SQLite in-memory, no services needed
```

## Run the API (with sample data)

```bash
cd backend
python -m scripts.seed          # creates jankalam.db + sample sources/topics/story
uvicorn app.main:app --reload
# open http://127.0.0.1:8000/docs
```

Quick check:

```bash
curl localhost:8000/api/v1/health
curl localhost:8000/api/v1/stories          # home feed (ranked by importance)
curl localhost:8000/api/v1/stories/<id>      # story page with the four layers
curl -X POST localhost:8000/api/v1/stories/<id>/ask \
     -H 'content-type: application/json' -d '{"question":"چرا این خبر مهم است؟"}'
```

## Database migrations (Postgres)

```bash
cd backend
export DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/jankalam"
alembic upgrade head
```

The initial migration is in `alembic/versions/`. `pgvector` columns and
Postgres-only indexes will be added in a Phase-3 migration guarded by dialect so
the SQLite test path keeps working.

## API surface (Phase 1)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/health`, `/api/v1/health/ready` | liveness / readiness |
| GET | `/api/v1/stories` | home feed (importance-ranked; `?category=`, `?limit=`, `?offset=`) |
| GET | `/api/v1/stories/{id}` | story page (four layers + citations) |
| POST | `/api/v1/stories/{id}/ask` | ask about a story (grounded in its material) |
| GET | `/api/v1/topics`, `/api/v1/topics/{id}` | topics |
| POST/DELETE | `/api/v1/topics/{id}/follow` | follow / unfollow (uses `X-User-Id` header) |
| GET | `/api/v1/sources` | public source list |
| * | `/api/v1/admin/...` | internal QC: manage sources, inspect/flag/regenerate stories |

## Security & content notes

- All secrets come from environment variables. `.env` is git-ignored;
  `.env.example` documents the variables. No keys are hard-coded.
- The **admin** API has no auth in the MVP — put it behind a private network or
  add auth before any deployment.
- The product stores metadata, excerpts, and links — never full copyrighted
  articles. Per-source usage rules (`allow_full_content`, `allow_image`,
  `attribution_required`) live on the `sources` table so behavior varies by
  source without code changes.

## Project layout

```
jan-kalam/
├── PRODUCT_SPEC.md  ARCHITECTURE.md  ROADMAP.md  README.md
└── backend/
    ├── app/
    │   ├── core/ db/ models/ schemas/ repositories/ services/ api/v1/
    │   └── ingestion/ clustering/ ai/ ranking/ tasks/   # scaffolded for later phases
    ├── alembic/            # migrations
    ├── scripts/seed.py
    ├── tests/              # 18 tests
    ├── requirements.txt  .env.example  pytest.ini
```
