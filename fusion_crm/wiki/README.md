# fusion_crm — Intelligence Storage

This directory stores intelligence patterns pushed from full-arch-crm's Karpathy wiki.

**Important architectural note:** fusion_crm is Fusion Dental's specific backend database.
The Karpathy wiki (the self-learning knowledge base) lives inside **full-arch-crm**,
which is the universal SaaS layer that any dental clinic connects to.

fusion_crm's role in the intelligence loop:
- **Receives** anonymized patterns via `POST /api/v1/intelligence/ingest`
- **Stores** those patterns locally so clinic-level workflows (InsuranceCallAgent, claim submission) can benefit
- **Returns** raw clinic data via `GET /api/v1/intelligence/query` which full-arch-crm uses to bootstrap its wiki

The wiki schema, WikiService, and all learning logic lives in:
  `full-arch-crm/server/simulation/wiki/`

## Intelligence Endpoints

| Endpoint | Direction | Description |
|---|---|---|
| `POST /api/v1/intelligence/ingest` | full-arch-crm → fusion_crm | Pushes validated patterns |
| `GET /api/v1/intelligence/query` | full-arch-crm ← fusion_crm | Pulls clinic's raw patterns |
| `POST /api/v1/intelligence/insurance-patterns` | full-arch-crm → fusion_crm | Single payer pattern |
| `POST /api/v1/intelligence/cdt-documentation-tips` | full-arch-crm → fusion_crm | Doc tips |
| `POST /api/v1/intelligence/appeal-templates` | full-arch-crm → fusion_crm | Appeal letter templates |
| `GET /api/v1/intelligence/claim-prediction/{id}` | full-arch-crm ← fusion_crm | ML prediction |
