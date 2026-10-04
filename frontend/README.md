# SolarAI Frontend

Contract-first frontend for the SolarAI multi-agent solar farm optimization project.

## Current phase: Phase 1 â€” Data Foundation

The frontend now consumes the existing repository fixture:

`../data/mock/sample_full_frontend_data.json`

through a single server-side loader:

`src/lib/frontend-data.server.ts`

The payload is validated at runtime with Zod before any UI renders.

### Data flow

```text
data/mock/sample_full_frontend_data.json
                â†“
frontend-data.server.ts
                â†“
frontendDataSchema (Zod)
                â†“
FrontendData (TypeScript)
                â†“
selectors / formatters
                â†“
React server-rendered UI
```

The frontend deliberately does **not** duplicate the shared JSON fixture and does not recalculate model, optimizer, safety, or control decisions.

## Stack

- Next.js
- React
- TypeScript
- App Router
- Tailwind CSS
- shadcn/ui-compatible primitives
- Lucide React
- Recharts
- Zod
- Vitest

## Commands

Install:

```bash
npm install
```

Development:

```bash
npm run dev
```

Lint:

```bash
npm run lint
```

Contract/unit tests:

```bash
npm test
```

Production build:

```bash
npm run build
```

## Mock-data provenance

The current fixture is explicitly labeled `MOCK`. It is synthetic development data, not measured farm data, trained-model performance, or hardware authorization.

The UI must preserve that provenance and must not relabel mock values as live.

## Ownership boundary

Frontend work lives in `frontend/`.

Do not change the shared Python schemas, AI agents, models, optimizer, pipeline, or backend interfaces from the frontend without explicit team agreement.

## Next phase

Phase 2 establishes the reusable SolarAI application shell and design system: navigation, sidebar, page layout, responsive dashboard primitives, state badges, and shared chart containers. Business-facing dashboard features remain contract-driven.
