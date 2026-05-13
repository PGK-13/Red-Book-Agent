# AGENTS.md

Guidance for Codex and other agentic coding tools working in this repository.

## Canonical Project Rules

The canonical development rules live in `.kiro/steering/`. Treat those files as
the source of truth. Before making code changes, read the relevant steering
files listed below and follow their `inclusion` / `fileMatchPattern` intent:

- `.kiro/steering/project-overview.md` — always read for project context.
- `.kiro/steering/architecture-layers.md` — always read for backend, worker,
  agent, data-access, and module-boundary changes.
- `.kiro/steering/code-style.md` — always read for Python and TypeScript style.
- `.kiro/steering/deployment-safety.md` — always read; never run direct remote
  deployment or production mutation commands.
- `.kiro/steering/model-function-overview.md` — always read for module/page
  scope and expected product surfaces.
- `.kiro/steering/api-conventions.md` — read when touching APIs, schemas,
  routers, routes, or response/error handling.
- `.kiro/steering/frontend-design.md` — read when touching `frontend/**`.
- `.kiro/steering/security.md` — read when touching auth, tokens, secrets,
  encryption, dependencies, or security-sensitive code.
- `.kiro/steering/git-workflow.md` — read when touching GitHub workflow,
  changelog, contributing, PR, or release docs.

If a rule here conflicts with a `.kiro/steering` file, prefer the steering file.

## Quick Context

This is a Xiaohongshu marketing automation agent platform using:

- FastAPI, SQLAlchemy 2.0 async, Pydantic v2, PostgreSQL, Redis, Qdrant.
- LangGraph / LangChain for agent orchestration.
- Celery + RabbitMQ for async tasks.
- Next.js App Router and TypeScript for the merchant dashboard and HITL
  workbench.

## Non-Negotiable Rules

- Keep business logic in `backend/app/services/`; routers only validate,
  authorize, call services, and format responses.
- All data queries must preserve merchant isolation with `merchant_id` filters.
- Celery tasks reuse service-layer logic; they must not become a second business
  layer.
- LangGraph agents use service/tool functions; they must not access the
  database directly.
- Risk scanning must complete synchronously before any outbound content is
  published.
- Secrets, tokens, cookies, proxy URLs, and API keys must never be hardcoded,
  logged, or returned in raw form.
- Encrypted database fields use the `_enc` suffix.
- API responses follow `{ "code": 0, "message": "success", "data": ... }`.
- Use async IO in async Python contexts.
- Do not execute remote deployment, production database, SSH, `kubectl apply`,
  `helm upgrade`, or similar commands. Local development commands are allowed.

## Local Commands

Use paths relative to this repository root:

```bash
docker compose -f infra/docker-compose.yml up -d
cd backend && pytest
cd backend && uvicorn app.main:app --reload --port 8000
cd worker && celery -A celery_app worker --loglevel=info
cd frontend && npm run dev
```

