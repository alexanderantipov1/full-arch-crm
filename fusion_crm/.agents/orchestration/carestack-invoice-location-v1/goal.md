# Goal — location-scope CareStack invoice events (ENG-268)

Attach `location_id` to `invoice_created` events (mirror ENG-267, invoice service
only) so the dashboard **Invoices** count and **Payments** ($ invoiced) recalculate
per location. The aggregate already filters `invoice_created` by location — only the
emit side is missing.

No new schema (payload-based). Read-only CareStack. No PHI. Linear: ENG-268.
