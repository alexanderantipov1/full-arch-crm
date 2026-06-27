# CLAUDE.md — `apps/web/` (staff frontend, Next.js)

> The internal staff UI for Fusion CRM. **Phase 1 ships as a
> frontend-first mock-driven slice** — every API call goes through
> MSW until the matching backend endpoint lands. Read the root
> `CLAUDE.md` and `apps/CLAUDE.md` first.

## Mission

Internal browser UI for the dental clinic's front-desk and
marketing staff. Phase 1 surfaces:

- Login (staff session, no patient self-service)
- Integrations connect/status (Salesforce OAuth, CareStack API key)
- Dashboard (lead/consult counts, recent persons)
- Person card with timeline (SF + CareStack origin events)
- `/dev/*` inspector + graph pages (env-gated to local dev)

**This directory is staff-only.** Patient-facing UI lives in
`apps/portal/` (reserved for M11). Do not mix.

## Hard rules

1. **PHI is allowed on the staff frontend (updated 2026-06-01).** The
   previous "No PHI on the frontend, ever" line is OBSOLETE. Clinic
   managers and the AI agent layer operate as authorized BAs (OpenAI
   Enterprise BAA covers the agent path). Patient names, DOB, full
   phones, email, full address, clinical fields MAY flow to the staff
   UI when the operator role requires them. Prefer a click-to-reveal
   panel for the heavier fields (intentional access). What still does
   NOT change: PHI never appears in structured log values; schema
   separation (`phi.*` stays its own schema, reads still go through
   `PhiService`); append-only audit on `audit.access_log`; AI agents
   never touch the DB directly (still call services). Runtime gates
   (`PhiService.can_read_phi`, vendor BAA enforcement) remain DEFERRED
   per the strategic memory note. **Development-phase posture
   (2026-06-15):** pre-access-control, the only user is the doctor, so
   staff read surfaces — incl. verbatim raw-payload drill-downs and
   Inspector views — may show ALL captured data on every environment
   (prod included); do not env-gate or redact a read-only staff view
   for PHI reasons. Role-scoped access + field redaction are a later
   layer on top. See root `CLAUDE.md` → "Data visibility posture".
2. **No business logic.** This app is wiring + presentation.
   Decisions (who can see what, what counts as a "stale lead",
   etc.) live in `packages/` services and ship as API responses.
3. **One source of truth for API contract: Zod.** Every API call
   has a Zod schema in `lib/api/schemas/`. MSW handlers parse the
   request and return Zod-validated responses; React Query hooks
   parse responses against the same schema. Drift is a bug.
4. **Mocks are the contract until backend lands.** When the real
   endpoint arrives, the MSW handler is *deleted*, not "kept as
   a fallback". One handler per endpoint, no zombies.
5. **No client-side env secrets.** Anything that ends up in the
   browser bundle is public. OAuth client secrets, API keys, JWT
   signing keys live ONLY on the API side.
6. **Strict TypeScript.** `tsconfig.json` has `"strict": true`,
   `"noUncheckedIndexedAccess": true`. Don't loosen.
7. **Payments doc-sync rule (ENG-300).** `lib/docs/paymentsDoc.ts`
   is the staff-facing mirror of how CareStack payments are
   classified and how Collected is computed. If you change the
   payment classification (`_PAYMENT_CODE_TO_KIND` /
   `_CASH_REVERSAL_CODES` in
   `packages/ingest/carestack_accounting_transaction_service.py`) or
   the Collected formula
   (`get_treatment_payment_aggregate` in
   `packages/interaction/repository.py`), you MUST update
   `lib/docs/paymentsDoc.ts` in the same change — and keep BOTH the
   `en` and `ru` versions describing the same behaviour.

8. **Local `app/api/*/route.ts` handlers must never shadow a live
   FastAPI route.** The dev rewrite proxies `/api/:path*` →
   FastAPI `:8000/:path*`, but a Next.js route handler at the same
   path wins over the rewrite and silently serves stale/stub data
   (2026-06-10: a leftover `app/api/integrations/route.ts` hardcoded
   `last_sync_at: null`, hiding real sync state that FastAPI was
   already serving). Before adding a handler under `app/api/`, check
   `apps/api/routers/` prefixes; if the backend path exists, delete
   the local handler and let the proxy work. Same delete-on-landing
   rule as MSW handlers (rule 4).

## Stack (locked — do not swap without ADR)

- **Next.js 14** (App Router) + TypeScript strict
- **Tailwind CSS** + **shadcn/ui** (Radix-based primitives)
- **React Flow** (`@xyflow/react`) — required for identity merge
  graph, ingest pipeline viz, agent workflow builder, schema
  explorer
- **MSW 2.x** — browser worker for `npm run dev`, Node handlers
  for vitest
- **Zod** — API contract schemas
- **TanStack Query** (`@tanstack/react-query`) — server state
- **vitest** + **@testing-library/react** — unit / component tests
- **Playwright** — e2e (added when V1 lands)

Do not pull in: Redux, Mantine, Chakra, MUI, Apollo, Axios.
React Query covers fetching; `fetch` covers HTTP; shadcn covers
components.

## Layout

```
apps/web/
├── package.json
├── tsconfig.json
├── next.config.mjs
├── tailwind.config.ts
├── postcss.config.mjs
├── .env.example                public client env vars only
├── public/
│   └── mockServiceWorker.js   generated by `npx msw init`
├── app/                        Next.js App Router
│   ├── layout.tsx              root layout (providers wrap here)
│   ├── page.tsx                redirect to /dashboard or /login
│   ├── login/page.tsx
│   ├── (staff)/                authed layout group
│   │   ├── layout.tsx
│   │   ├── dashboard/page.tsx
│   │   ├── integrations/page.tsx
│   │   ├── persons/[uid]/page.tsx
│   │   └── dev/
│   │       ├── inspector/page.tsx
│   │       └── graph/page.tsx
│   └── api/                    Next.js route handlers (only if needed
│                               for non-API-backend tasks; in Phase 1
│                               we proxy to apps/api directly)
├── components/
│   ├── ui/                     shadcn-generated primitives
│   ├── layout/                 Sidebar, TopBar, AppShell
│   ├── person/                 PersonCard, TimelineEntry, ...
│   ├── integrations/           ProviderCard, ConnectButton, ...
│   └── graph/                  React Flow nodes + edges
├── lib/
│   ├── api/
│   │   ├── client.ts           fetch wrapper, error envelope parsing
│   │   ├── schemas/            Zod schemas — one file per resource
│   │   └── hooks/              TanStack Query hooks per endpoint
│   ├── auth/                   session helpers (cookie read, etc.)
│   ├── msw/
│   │   ├── browser.ts          MSW worker setup for the browser
│   │   ├── server.ts           MSW server setup for vitest
│   │   ├── handlers.ts         all handlers — split by resource later
│   │   └── fixtures/           static seed data
│   └── graph/                  React Flow graph builders (pure, tested)
├── tests/
│   ├── unit/                   vitest
│   └── e2e/                    playwright (later)
└── CLAUDE.md (this file) + AGENTS.md
```

## API contract & MSW

The backend API surface ships in PR-2 (`A1`–`A4` tickets). For
Phase 1, the contract lives entirely in `lib/api/schemas/` as Zod.
Every API endpoint follows the convention:

```ts
// lib/api/schemas/person.ts
export const PersonSchema = z.object({ id: z.string().uuid(), … });
export type Person = z.infer<typeof PersonSchema>;

// lib/msw/handlers.ts
http.get('/api/persons', () => HttpResponse.json(personListFixture))

// lib/api/hooks/usePersons.ts
useQuery({
  queryKey: ['persons'],
  queryFn: async () => PersonListSchema.parse(await client.get('/persons'))
})
```

When the real backend endpoint lands:
1. Verify the Pydantic schema matches the Zod schema *exactly*
   (field names, optionality, enums).
2. Delete the MSW handler.
3. Run the e2e smoke against the live endpoint.

Do not keep the MSW handler "in case the backend is down". MSW
runs in dev mode only (gated by `NEXT_PUBLIC_API_MOCKING=enabled`);
production builds bundle no MSW code.

### Datetime fields — always use the `Datetime` alias

Never write `z.string().datetime()` directly. Use `Datetime` from
`lib/api/schemas/common.ts`:

```ts
import { Datetime } from "./common";
export const FooSchema = z.object({ created_at: Datetime });
```

`Datetime` is `z.string().datetime({ offset: true })`. Python's
`datetime.isoformat()` emits `+00:00` for UTC, which the raw
`.datetime()` (no `offset`) rejects. A schema parse failure inside
a TanStack Query `queryFn` puts the query into an error state with
**no console output** — components reading `!data` render `null`,
producing an empty page that's painful to debug. See
`feedback_prod_deploy_traps.md` (trap #1) and ENG-143.

## Error envelope

The backend returns:
```json
{ "error": { "code": "AUTH_INVALID", "message": "...", "details": {} } }
```

`lib/api/client.ts` parses this and throws `ApiError(code, message)`.
Components show user-facing messages from a code → copy lookup, not
from `error.message` directly (so we control the UX layer).

## React Flow conventions

Pure graph data — nodes, edges, layout — lives in `lib/graph/` and
is testable without rendering. Components in `components/graph/`
take `{nodes, edges}` props and render. Layout via `dagre` for
hierarchical graphs (identity merge tree, ingest pipeline).

Each graph kind has its own builder file:
- `lib/graph/identityMerge.ts` — Person + linked external IDs
- `lib/graph/ingestPipeline.ts` — SF/CareStack → raw_event → ops
- `lib/graph/agentWorkflow.ts` — future, when M-series workflow lands

## Auth (Phase 1)

Cookie-based session, set by `POST /api/auth/login` from the API
backend. The frontend reads a `staff_session` cookie via Next.js
middleware and redirects unauthenticated requests to `/login`.

`/dev/*` pages additionally check `NEXT_PUBLIC_ENVIRONMENT === 'local'`
and 404 otherwise — local-only inspector carve-out per the strategic
memory note.

## Run / build / test

```bash
cd apps/web
npm install
npm run dev           # http://localhost:3000 (with MSW)
npm run build && npm run start
npm run test          # vitest
npm run lint          # eslint + tsc --noEmit
```

`make web-dev` from repo root will eventually wrap the above.

## Adding a page

1. Create the route file under `app/`.
2. Define / extend Zod schema for any new API call in
   `lib/api/schemas/`.
3. Add MSW handler + fixture (`lib/msw/handlers.ts`,
   `lib/msw/fixtures/`).
4. Add TanStack Query hook in `lib/api/hooks/`.
5. Build the component, render the data, handle loading/error/empty.
6. Add a vitest component test covering the loading + success path.

## Adding a backend endpoint (PR-2 phase)

1. Confirm Zod schema in `lib/api/schemas/` is the truth.
2. Backend: implement Pydantic schema + service + repository to
   match (field names, types, enums) exactly.
3. Replace the MSW handler with a deletion.
4. Smoke-test the page in `npm run dev` with `NEXT_PUBLIC_API_MOCKING`
   disabled — it should hit the real API.

## What does NOT live here

- Patient-facing UI → `apps/portal/` (M11)
- AI agent tools → `packages/tools/` (server-side, called by MCP)
- Background jobs → `apps/worker/`
- Email / SMS templates → server-side (TBD)
