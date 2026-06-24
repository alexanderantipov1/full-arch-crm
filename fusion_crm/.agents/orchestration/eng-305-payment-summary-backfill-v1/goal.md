# Goal — ENG-305: Throttled payment-summary backfill → authoritative balance

Bring the per-patient **authoritative balance** into Fusion CRM by pulling
CareStack `payment-summary` (`balanceDuePatient` + `balanceDueInsurance`,
`appliedPatientPayment` + `appliedInsPayments`) for every linked patient that
has payments — today we have it for **50** patients vs **1803** that need it.

The authoritative balance CANNOT be derived from the accounting journal (full
double-entry; per-folio debit−credit nets to 0 — verified on patient 1751021).
The trustworthy source is `payment-summary`, which we already consume for
dashboard Outstanding / AR-risk.

This ticket is **data-only**: harden the ingest service, wire a live signal,
add a backfill script, and prove it with tests. The UI for Billed / Adjustments
/ Paid / Balance on the person card ships in a separate follow-up ticket
**after** the data lands.

Linear: ENG-305
URL: https://linear.app/fusion-dental-implants/issue/ENG-305/throttled-payment-summary-backfill-authoritative-patient-balance
