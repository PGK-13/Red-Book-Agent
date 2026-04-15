---
paths:
  - "frontend/**"
---

# Frontend Design Rules

## TypeScript
- Strict TypeScript mode — **no `any`**
- Components use PascalCase, utilities use camelCase
- Prefer React Server Components; use `"use client"` only when interaction is needed

## State Management
- Server state via React Server Components and fetch
- Client state only for UI-specific ephemeral state
- API calls go through `frontend/lib/api-client.ts`

## UI Conventions
- Responsive design for merchant dashboard (admin-facing, desktop-first)
- HITL workbench requires real-time updates (consider WebSocket or SSE)

## Naming
| Type | Style | Example |
|------|-------|---------|
| Components | PascalCase | `AccountCard` |
| Hooks | camelCase, `use` prefix | `useAccountList` |
| Utilities | camelCase | `formatDate` |
| Types/Interfaces | PascalCase | `AccountResponse` |
