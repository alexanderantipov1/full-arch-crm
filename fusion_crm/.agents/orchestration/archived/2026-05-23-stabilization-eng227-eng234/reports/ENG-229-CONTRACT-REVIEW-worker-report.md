# ENG-229 Contract Review Worker Report

Linear issue: ENG-229
Linear URL: https://linear.app/fusion-dental-implants/issue/ENG-229/define-tenant-isolation-safety-net-exceptions-and-root-tenant-contract
Task id: ENG-229-CONTRACT-REVIEW
Worker role: read-only tenant isolation contract review
Status: Completed, recommendation only

## Summary

I did not change product or test code. I reviewed the tenant isolation
safety-net, tenant/outreach repository methods, and call sites for the five
repository read methods that currently lack a `tenant_id` parameter.

Recommended contract:

- Keep the default rule strict: every repository read that returns tenant-owned
  data must accept `tenant_id` and filter by it in SQL.
- Allow method-level exceptions only for root/control-plane reads where there is
  no caller tenant yet, or where a signed recipient token is the security
  boundary and the returned row's `tenant_id` is immediately used or verified
  before side effects.
- Do not exempt entire repository classes. Exceptions must be exact
  `Class.method` entries with a category, required guard, justification, and
  owner comment.
- Treat credential reads by raw id as tenant-owned data, not a root/global
  exception.

## Required Context Read

- `CLAUDE.md`
- `AGENTS.md`
- `tests/integration/test_tenant_isolation.py`
- `tests/_tenant_helpers.py`
- `tests/conftest.py`
- `packages/tenant/CLAUDE.md`
- `packages/outreach/CLAUDE.md`
- `.agents/CLAUDE.md`
- `.agents/AGENTS.md`
- `.agents/orchestration/CLAUDE.md`
- `.agents/orchestration/AGENTS.md`
- `docs/decisions/ADR-0003-tenant-domain-multi-tenancy.md`
- `packages/tenant/repository.py`
- `packages/outreach/repository.py`
- call sites for `TenantRepository.get_by_slug`, `TenantRepository.list_all`,
  `TenantRepository.get_credential`, `SendRepository.get_global`, and
  `SendRepository.find_by_message_id_global`

## Current Inventory

Repository discovery reports:

- discovered read methods: 65
- missing `tenant_id`: 5

Missing `tenant_id` methods:

- `SendRepository.find_by_message_id_global`
- `SendRepository.get_global`
- `TenantRepository.get_by_slug`
- `TenantRepository.get_credential`
- `TenantRepository.list_all`

## Recommended Allowlist Shape

Replace the current empty repository-class exemption set with an exact
method-level allowlist. Suggested shape:

```python
@dataclass(frozen=True)
class TenantReadException:
    category: Literal[
        "tenant_root_lookup",
        "tenant_root_enumeration",
        "signed_recipient_token_lookup",
        "verified_global_fallback",
    ]
    justification: str
    required_guard: str
    owner: str


TENANT_READ_EXCEPTIONS: dict[str, TenantReadException] = {
    "TenantRepository.get_by_slug": TenantReadException(
        category="tenant_root_lookup",
        justification="Resolves the bootstrap/request tenant before a tenant_id exists.",
        required_guard="May return only tenant.tenant rows; caller must convert result to TenantId before tenant-owned reads.",
        owner="packages.tenant",
    ),
    ...
}
```

The structural test should first check `method.qualified_name in
TENANT_READ_EXCEPTIONS`; if present, assert the method is still limited to a
documented exception category. The allowlist should live in
`tests/integration/test_tenant_isolation.py` with comments close to the failing
safety-net, not in product code.

## Per-method Recommendation

### `TenantRepository.get_by_slug`

Recommendation: allowlist as `tenant_root_lookup`.

Justification: This reads `tenant.tenant`, which ADR-0003 classifies as global
by nature. It is used by `TenantService.resolve_default` to turn
`Settings.tenant_default_slug` into the request `TenantId` before normal
tenant-scoped service/repository calls can happen.

Required guard: the method must remain limited to `Tenant`; it must not join to
tenant-owned domain tables or return credentials/settings/locations.

### `TenantRepository.list_all`

Recommendation: allowlist as `tenant_root_enumeration`, but only for background
control-plane style jobs that intentionally iterate tenants.

Justification: `bounce_poll` and `ingest_scheduled` run once per cron tick and
then iterate tenant ids, calling tenant-scoped work per tenant. There is no
single request tenant at the point of enumeration.

Required guard: consumers must immediately project rows to tenant ids and run
subsequent domain work under one tenant at a time. This is not an operator UI
or cross-tenant data browsing primitive.

### `TenantRepository.get_credential`

Recommendation: do not allowlist. Treat as a real tenant-scoped leak.

Justification: `tenant.integration_credential` is tenant-owned configuration
with encrypted payload metadata. `TenantService.revoke_credential` currently
loads by raw credential id and checks `cred.tenant_id` after the read. That is
the exact post-read filtering pattern the safety-net exists to prevent.

Required fix: change the repository/service contract to read by
`(tenant_id, credential_id)` in SQL, or route all remaining callers through the
already tenant-scoped `IntegrationCredentialService` methods.

### `SendRepository.get_global`

Recommendation: allowlist as `signed_recipient_token_lookup`, narrowly.

Justification: recipient-facing open tracking and unsubscribe routes have no
request tenant context. The HMAC token gates access to a single `send_id`; the
route then derives or verifies `tenant_id` from the returned send row before
mutating campaign/send/suppression/audit state.

Required guard:

- Open tracking may derive `tenant_id` from the send row only after a valid
  open-token signature.
- Unsubscribe must verify `send.tenant_id == payload.tenant_id` and verify the
  recipient email hash before suppression or audit writes.
- No caller may expose returned row contents to a recipient or operator.

### `SendRepository.find_by_message_id_global`

Recommendation: allowlist as `verified_global_fallback`, narrowly.

Justification: the bounce poller first tries the tenant-scoped
`find_by_message_id(tenant_id, message_id)`. The global lookup is a fallback
for provider message-id shape drift and records nothing unless
`send.tenant_id == tenant_id`.

Required guard: it must remain fallback-only after the tenant-scoped lookup,
and every side effect must be blocked unless the returned send row belongs to
the tenant currently being polled.

## Do-not-merge Conditions

- Do not replace the safety-net with a repository-class exemption such as
  exempting all of `TenantRepository` or `SendRepository`.
- Do not allowlist `TenantRepository.get_credential`.
- Do not allow global outreach lookups unless guard tests assert tenant/token
  verification before suppression, audit, campaign, or send mutation.
- Do not weaken or skip the Phase B live isolation shim to make the suite green.
  It needs a real implementation, not an xfail.
- Do not add any exception that returns PHI or joins into `phi.*`.
- Do not allow `list_all` to become an operator/admin browsing surface without
  a separate authorization and audit contract.

## Suggested Follow-up Work

1. ENG-229 implementation patch: add the method-level allowlist and guard-shape
   tests for the four legitimate exceptions.
2. ENG-230: harden credential reads by replacing raw-id repository loads with
   tenant-filtered SQL.
3. ENG-231: implement the Phase B live two-tenant harness for compliant
   repository methods.

## Verification

Read-only verification performed:

```text
PYTHONPATH=tests:. .venv/bin/python - <<'PY'
from tests.integration import test_tenant_isolation as t
missing = [m for m in t._DISCOVERED if not m.has_tenant_id]
print(f"discovered={len(t._DISCOVERED)} missing={len(missing)}")
for m in missing:
    print(f"{m.qualified_name} {m.file_path}:{m.line_number}")
PY
```

Output:

```text
discovered=65 missing=5
SendRepository.find_by_message_id_global .../packages/outreach/repository.py:194
SendRepository.get_global .../packages/outreach/repository.py:164
TenantRepository.get_by_slug .../packages/tenant/repository.py:27
TenantRepository.get_credential .../packages/tenant/repository.py:57
TenantRepository.list_all .../packages/tenant/repository.py:36
```

No product tests were run because this was a read-only contract review and no
product/test code was changed.

## Changed Files

- `.agents/orchestration/current/reports/ENG-229-CONTRACT-REVIEW-worker-report.md`
