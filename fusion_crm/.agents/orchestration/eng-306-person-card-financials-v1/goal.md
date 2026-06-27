# Goal — ENG-306: Person-card financial summary + Payments balance badge

Surface the authoritative per-patient balance landed by ENG-305 in the operator
UI:

- **Person/patient detail card** — show **Billed**, **Adjustments**, **Paid**,
  **Balance** with the snapshot timestamp. Paid + Balance come from the
  authoritative `payment-summary` snapshot (latest per CareStack patient_id);
  Billed + Adjustments are gross context from the accounting journal
  (deduped by `external_id`, latest `received_at`).
- **`/project-manager/payments` row** — compact balance pill next to the patient
  name, sourced from the same authoritative `payment-summary` snapshot.

Empty state: when no snapshot exists yet for a patient (the ENG-305 backfill
has not yet covered them), show `"—"` — never `"$0"` (we must not imply we
know the balance is zero).

Frontend only. No backend logic changes (only a thin per-patient flavor of
the existing `LatestPaymentSummaryBalancesOut` aggregate if needed). No PHI in
logs. No schema change.

Linear: ENG-306
URL: https://linear.app/fusion-dental-implants/issue/ENG-306/person-card-financial-summary-payments-badge-from-authoritative
Parent: ENG-250 — Related: ENG-305 (data path, merged 50da948).
