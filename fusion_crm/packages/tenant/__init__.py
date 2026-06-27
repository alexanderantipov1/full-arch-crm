"""Tenant domain — multi-tenancy root.

Owns the four ``tenant.*`` tables (``tenant``, ``location``,
``integration_credential``, ``setting``). Every other domain references
``tenant.tenant.id`` via plain UUID columns, so a row is always
attributable to exactly one tenant.

Public surface is ``TenantService``, ``LocationService``, and (new with
ENG-125) ``IntegrationCredentialService``. Repositories and models stay
private to the package — cross-domain callers MUST go through the
service.

See `docs/decisions/ADR-0003-tenant-domain-multi-tenancy.md` and
ENG-125 for the encrypted credential / multi-mailbox details.
"""
