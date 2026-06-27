# Goal — ENG-310: person-card identity surfaces (names + PHI panel + household links)

Three person-card additions, all surfaced under the 2026-06-01 PHI policy
(`feedback_phi_on_staff_frontend_allowed`):

- **A. Per-pid names** in the multi-link expander (Gaiane / Gaiane / Eduard
  instead of bare pids).
- **B. Patient details panel** — click-to-reveal DOB / phones / email /
  address per linked pid.
- **C. Household links** — bidirectional navigational links to OTHER
  persons sharing a normalized phone/email (NOT accountId — verified
  clinic-level default on 55K pids). Financials/consultations stay
  separate; only a "shares contact with — not the same person" link.

Household key = normalized **phone/email**. Same signal the old resolver
mis-MERGED on; ENG-309 stopped the merge, this surfaces it as a soft link.

Linear: ENG-310 (full detail in the ticket).
Parent: ENG-250 — Related: ENG-308 (expander), ENG-309 (merge block),
ENG-311 (split that created separate Eduard/Gaiane).
