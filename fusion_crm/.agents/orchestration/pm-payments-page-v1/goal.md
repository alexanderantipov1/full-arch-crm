# Goal — PM Payments page (ENG-271)

New **Payments** item under Project Manager → Leads (`/project-manager/payments`):
a date/location-filterable list of CareStack payment transactions — person, their
pipeline stage, amount, type, date, location. Each row drills down to the full
verbatim raw payload (like /dev/inspector). Mirror the PM Leads page.

- List = safe fields (person/stage/amount/location). Drilldown = verbatim
  raw_event payload (inspector carve-out, already ungated on prod).
- Backend: `GET /dashboard/pm/payments` + `GET /ingest/dev/inspector/raw-events/{id}`.
- Read-only, no new schema. Linear: ENG-271.
