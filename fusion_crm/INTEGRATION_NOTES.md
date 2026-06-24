# Fusion CRM — Backend Integration Reference

Copied from https://github.com/alexanderantipov1/fusion_crm (mirror of FUSIONDENTALAI/fusion_crm).

## Key Components
- HIPAA-compliant PHI gating via PhiService
- 11 database schemas: identity, ops, phi, audit, ingest, actor, auth, tenant, integrations, interaction, outreach, analytics
- Governed AI agent runtime — proposals require human review before execution
- CareStack OAuth2 integration (v1.0.45)
- Multi-tenant: tenant.tenant + tenant.location + tenant.integration_credential
- Self-improving insight engine (arq hourly jobs)
- AI tools: CDT/CPT coding, medical necessity letters, prosthetic matching

## What to integrate into full-arch-crm
- `apps/api/` — FastAPI routes
- `packages/integrations/` — CareStack client, fullarch-ai bridge
- `packages/tools/` — governed AI tools
- `packages/insight/` — self-improving learning engine
- `alembic/` — database migrations

## Both repos stay separate
This folder is a reference copy only.
