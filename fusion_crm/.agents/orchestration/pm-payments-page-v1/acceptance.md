# Acceptance — ENG-271

- [ ] `GET /dashboard/pm/payments` (mirror `/dashboard/pm/leads`): rows from
      `interaction.event` kind in (payment_recorded, payment_refunded,
      payment_reversed). Per-row SAFE fields: person_uid, display_name,
      lead_status + consultation_status (stage), amount, kind, transaction_type,
      occurred_at, location_id + location_name, source_external_id, raw_event_id.
      Filters: from/to, location_id, source_provider, q, limit. Tenant-scoped.
- [ ] `GET /ingest/dev/inspector/raw-events/{event_id}` returns the single
      tenant-scoped raw_event with verbatim payload (mirror the list endpoint).
- [ ] Sidebar: **Payments** under Leads in the Project Manager group
      (`/project-manager/payments`), staff page (not /dev/*).
- [ ] Page: filter bar (date window default 30d, location, provider, search) +
      table (person link, stage, amount, type, date, location) + per-row "view
      raw" → drawer/modal with the raw payload JSON. Zod + hook + MSW.
- [ ] LIST has NO clinical/PHI fields; raw drilldown = same exposure as inspector.
- [ ] Read-only, no new schema. Verify green: lint, mypy, test, alembic check.
- [ ] Tests: list filters + no-PHI-in-list + raw-by-id tenant scoping; FE render +
      filter + drilldown.
- [ ] Report at `reports/ENG-271-worker-report.md`.
