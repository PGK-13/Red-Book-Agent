# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

小红书营销自动化 Agent (Red Book Marketing Automation Agent) — a platform for Xiaohongshu (Little Red Book) merchants covering account management, content generation, interaction routing, risk control, and analytics. The system uses LangGraph for agent orchestration, FastAPI for REST APIs, Celery + RabbitMQ for async tasks, and Next.js for the merchant dashboard.

## Quick Start

```bash
# 1. Start local infrastructure
cp infra/.env.example .env
docker-compose -f infra/docker-compose.yml up -d

# 2. Start backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# 3. Start Celery worker
cd worker
celery -A celery_app worker --loglevel=info

# 4. Start frontend
cd frontend && npm install && npm run dev
```

## Running Tests

```bash
cd backend
pytest                          # all tests
pytest tests/test_file.py       # single file
pytest -k "test_name"          # by keyword
pytest --cov=app               # with coverage
pytest --cov=app --hypothesis-show-statistics  # property-based tests
```

Tests use `httpx.AsyncClient` with `ASGITransport` against the FastAPI app. Property-based tests use Hypothesis (100+ iterations per property).

## Architecture

### Layered Architecture + Hexagonal Design

```
API Router (FastAPI) → Service (Business Logic) → ORM (SQLAlchemy) → PostgreSQL
                      ↓
              Celery Worker (async tasks, reuse Service layer)
```

**Non-negotiable layering rules:**
1. API routes only do parameter validation and response formatting — no business logic
2. Service layer is the only business logic orchestrator — no raw SQL
3. ORM models contain zero business logic — complex queries go in Repository functions
4. LangGraph Agents never access the database directly — they use Tool functions from the Service layer
5. Celery Tasks contain zero business logic — they reuse Service layer functions
6. Risk scanning (Module E) must complete synchronously before any outbound content is published
7. All queries must include `merchant_id` filter for data isolation

### Six Business Modules

| Module | Responsibility |
|--------|----------------|
| A — Account | OAuth, Cookie management, proxy config, profile sync, status monitoring |
| B — Knowledge | Document chunking, vector indexing, hybrid retrieval, viral copy weighting, trend analysis |
| C — Content | Copy generation, cover rendering, publishing schedule, draft management |
| D — Interaction | Comment monitoring, OCR, intent classification, DM triggering, real-time customer service, HITL |
| E — Risk | Sensitive word scan, rate limiting, content deduplication, competitor filtering |
| F — Analytics | Conversion funnel, HITL audit workbench, alert center, data export |

### Module Communication

- **Synchronous REST**: Service layer functions call each other directly (e.g., D calls B for retrieval, D calls E for risk scanning)
- **Async (Celery + RabbitMQ)**: Content generation, scheduled publishing, data sync tasks
- **Event-driven (Redis Pub/Sub)**: Account status change notifications, real-time messages to frontend WebSocket

### Tech Stack

- **Backend**: FastAPI (async), SQLAlchemy 2.0 (async), Pydantic v2, Alembic migrations
- **Agent**: LangGraph + LangChain, GPT-4o (default), BaseLLM interface for model swapping
- **Database**: PostgreSQL (JSONB, TEXT[], pg_trgm), Qdrant (hybrid vector + BM25 search)
- **Cache/Queue**: Redis (session cache, rate limiting, Pub/Sub), Celery + RabbitMQ
- **Browser Automation**: Playwright (multi-account context isolation)
- **OCR**: PaddleOCR (local, Chinese-optimized)
- **Frontend**: Next.js App Router (SSR + React Server Components)

## Code Conventions

### Python Style
- Python 3.11+, `black` (88 char line width), `isort` (profile=black)
- All function parameters and returns must have type annotations
- Public functions/classes use Google-style docstrings
- IO operations always use `async/await` — never synchronous blocking calls in async context

### Naming
| Type | Style | Example |
|------|-------|---------|
| Python variables/functions | snake_case | `account_id` |
| Python classes | PascalCase | `AccountService` |
| Python constants | UPPER_SNAKE_CASE | `MAX_RETRY_COUNT` |
| TypeScript variables/functions | camelCase | `accountId` |
| TypeScript components/types | PascalCase | `AccountCard` |
| Database table names | snake_case plural | `accounts` |
| API paths | kebab-case | `/api/v1/viral-copies` |

### API Response Format
```json
{ "code": 0, "message": "success", "data": {} }
```
- `code: 0` = success, non-zero = business error
- HTTP status codes only for transport semantics (200/400/401/403/404/500)
- Cursor pagination: `GET /api/v1/accounts?limit=20&cursor=<opaque_cursor>`
- Async tasks: `POST /api/v1/content/generate` → `{ "task_id": "xxx" }`, poll `GET /api/v1/content/tasks/{task_id}`

### Error Code Ranges
| Range | Module |
|-------|--------|
| 40001–40099 | Account |
| 40101–40199 | Knowledge |
| 40201–40299 | Content |
| 40301–40399 | Interaction |
| 40401–40499 | Risk |
| 50001–50099 | Internal |

### Security Rules
- Sensitive fields encrypted via `core/security.py`, fields named with `_enc` suffix (e.g., `oauth_token_enc`, `cookie_enc`)
- All secrets via environment variables — no hardcoding, `.env` never committed
- HMAC signature verification for webhook endpoints
- All `/api/v1/` endpoints require JWT authentication via `dependencies.py:get_current_merchant`
- Provider webhooks deduplicated by platform IDs (`xhs_comment_id`, `xhs_note_id`)

## Key File Locations

```
backend/app/
├── main.py              # FastAPI app entry
├── config.py            # pydantic-settings configuration
├── dependencies.py      # DI (DB session, auth)
├── api/v1/              # Route handlers (accounts, knowledge, content, interaction, risk, analytics)
├── services/            # Business logic (one file per module)
├── models/              # SQLAlchemy ORM (account, knowledge, content, interaction, risk, analytics)
├── schemas/             # Pydantic request/response schemas
├── core/
│   ├── security.py      # encrypt/decrypt for tokens, cookies, proxy URLs
│   ├── notifications.py  # alert推送 (webhook/email)
│   └── rate_limiter.py   # Redis frequency limiting
└── db/
    ├── session.py        # async DB connection pool
    └── migrations/        # Alembic migration scripts

agent/
├── graphs/              # LangGraph agent graphs (intent_router, content_generator, customer_service)
├── tools/               # LangChain Tools (RAG retrieval, crawler, risk scan, DM sender, etc.)
├── memory/              # Redis short-term (session context), PostgreSQL long-term (user preferences)
├── llm/                 # LLM interface abstraction (BaseLLM, OpenAILLM, DeepSeekLLM)
└── prompts/             # Prompt templates

worker/
├── celery_app.py         # Celery app config
├── tasks/               # Celery tasks (publish, data_sync, industry_crawl, trend_analysis, etc.)
└── beat_schedule.py     # Celery Beat cron config

.kiro/specs/
├── architecture.md      # Full architecture document (data models, API specs, critical flows, correctness properties)
├── module-a-account/    # Module A design docs and requirements
└── steering/            # Development guidelines (git-workflow, code-style, api-conventions, security, etc.)
```

## Git Workflow

Branch strategy: `main` (production), `develop` (integration), `feature/*`, `fix/*`, `chore/*`

Commits follow Conventional Commits: `feat(account): add OAuth callback`, `fix(risk): correct keyword replacement`, etc.

PRs use `.github/pull_request_template.md` and require at least 1 code review. Squash merge to keep history clean.

## Property-Based Testing

The codebase uses Hypothesis for property-based testing. Each property test runs 100+ iterations and is annotated with the corresponding correctness property from `architecture.md`. Key properties:
- Cookie expiration triggers warning at <24h, status change at 0h
- Document chunking: all chunks ≤512 tokens with 50-token overlap
- RAG weight adjustment: 1.5x engagement → weight ×1.2, 0.5x → weight ×0.9
- Hybrid retrieval: ≤5 results, empty if all similarity <0.6
- Title character count: [20, 30] for viral title optimization
- Deduplication: same intent comment in 24h triggers exactly 1 DM
- Context window: last 10 turns retained, older truncated
- Rate limits: ≤20 comment replies/hour, ≤50 DMs/hour per account
- Reply similarity: <0.85 vs last 100 replies, rewrite if exceeded
