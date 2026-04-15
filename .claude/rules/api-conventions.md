---
paths:
  - "**/api/**"
  - "**/schemas/**"
  - "**/routers/**"
  - "**/routes/**"
---

# API Conventions

## Response Format
All APIs return:
```json
{ "code": 0, "message": "success", "data": {} }
```
- `code: 0` = success, non-zero = business error
- HTTP status codes only for transport semantics (200/400/401/403/404/500)
- Never use 4xx/5xx in successful responses

## Error Code Ranges
| Range | Module |
|-------|--------|
| 40001–40099 | Account |
| 40101–40199 | Knowledge |
| 40201–40299 | Content |
| 40301–40399 | Interaction |
| 40401–40499 | Risk |
| 50001–50099 | Internal |

## Pagination
- Use **cursor-based pagination** only — never offset pagination
- `GET /api/v1/accounts?limit=20&cursor=<opaque_cursor>`
- `limit` max 100, default 20

## Async Tasks
- Long-running operations return `task_id`, client polls status
- `POST /api/v1/content/generate` → `{ "task_id": "xxx" }`
- Poll `GET /api/v1/content/tasks/{task_id}` → `{ "status": "pending|running|success|failed", "result": {} }`

## Versioning
- Current version: `/api/v1/`
- Breaking changes require version bump; keep old version at least 3 months
