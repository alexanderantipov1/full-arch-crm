# `apps/web` — Fusion CRM staff frontend

Next.js 14 (App Router) + Tailwind + shadcn/ui + React Flow, mock-driven
via MSW. See [`CLAUDE.md`](./CLAUDE.md) for the rules; this README is the
quickstart.

## Run

```bash
cd apps/web
cp .env.example .env.local
npm install
npx msw init public --save     # one-time: generates public/mockServiceWorker.js
npm run dev
# open http://localhost:3000  (login: any email + password "demo")
```

`NEXT_PUBLIC_API_MOCKING=enabled` in `.env.local` keeps MSW on. Once
the real backend (PR-2) lands, flip to `disabled` to hit the API.

## Test / lint / typecheck

```bash
npm run test
npm run lint
npm run typecheck
```

## What you should see

- `/login` — staff login (mock auth, password is `demo`)
- `/dashboard` — pipeline counts + recent persons
- `/integrations` — Salesforce (OAuth) + CareStack (API key) cards;
  Connect → Sync now → status flips to "Syncing…" → "Connected"
- `/persons` — unified list across SF + CareStack
- `/persons/{uid}` — person card with merged timeline
- `/dev/inspector` — verbatim raw payloads (local-only)
- `/dev/graph` — React Flow visualizer:
  - **Ingest pipeline** — SF/CareStack → ingest → ops → interaction → UI
  - **Identity merge** — external IDs collapsed to person rows
