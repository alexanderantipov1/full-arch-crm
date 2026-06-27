# Lessons — dev-lead-sources-explorer-v1

(none yet)
- ENG-408: an idempotent provider re-pull (ENG-381 LastModifiedDate skip) can NEVER enrich existing rows with newly-projected fields - adding a field to the SF projection only covers future modifications. Dataset-wide enrichment needs a one-off script (see infra/scripts/backfill_lead_owner_names.py); also SF lead ownership is polymorphic: 00G ids are Groups/queues, not Users.
