# Verification — ENG-257 (surface partial payments)

Full repo loop (must be green before done):

```bash
make lint
mypy .
make test
cd packages/db && alembic check   # no drift AFTER the new revision is applied
```

Migration safety:
- `alembic upgrade head` then `alembic downgrade -1` then `upgrade head` round-trips clean.
- New revision's `down_revision` equals the prior head; do not edit shipped revisions.
- Models tuples == migration CHECK values (a mismatch makes alembic check drift).

Focused checks:
- Emission: PATIENTCREDIT/COLLECTIONCREDIT → `payment_recorded`; refund →
  `payment_refunded`; `isReversed=true` → `payment_reversed`. Charges /
  PATIENTPAYABLE / internal adjustment folios emit NO event.
- No-PHI: assert emitted event summary/payload contain only amount + type, no
  clinical codes, tooth numbers, or patient identifiers.
- Dashboard: `collected_total` sums payment events in range; `outstanding_total`
  sums latest payment-summary snapshot balance per patient. Tenant-scoped.
- A local CareStack pull produces `payment_recorded` events visible via
  `GET /persons/{uid}/operational-timeline` for a linked patient.
