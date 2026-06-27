# Mission Goal — analytics-dashboards-v1 (ENG-468)

Rebuild the Replit `DataBase_Fusion` marketing/funnel analytics views as our own
read-only staff-frontend pages, each a separate entry in the left-nav "Analytics"
section, sourced from our ingested data (`marketing.*`) + existing ops/identity/
interaction data.

Epic: ENG-468. Child tickets: ENG-469 (discovery/mapping, DO FIRST),
ENG-470 (Marketing), ENG-471 (SEO/GA4+GSC), ENG-472 (Full Funnel),
ENG-473 (Sales Pipeline), ENG-474 (Calls shell — partial, Phase-3 blocked).

Read-only. Dev-phase full-visibility (staff may see all data). Layering
route → service → repository → DB; no business logic in routes; tenant-scoped
via `get_principal_with_tenant`; typed FastAPI `*Out` ⇄ Zod parity.
