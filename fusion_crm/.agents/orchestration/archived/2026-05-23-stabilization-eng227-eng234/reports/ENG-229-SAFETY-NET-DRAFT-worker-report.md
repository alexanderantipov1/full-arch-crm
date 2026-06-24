# ENG-229-SAFETY-NET-DRAFT Worker Report

Linear issue: ENG-229
Linear URL: https://linear.app/fusion-dental-implants/issue/ENG-229/define-tenant-isolation-safety-net-exceptions-and-root-tenant-contract

## Scope

Prepared a bounded tenant-isolation safety-net patch. Product code was not
changed.

## Changed Files

- `tests/integration/test_tenant_isolation.py`

## Changes

- Added a method-level `ROOT_OR_GLOBAL_READ_ALLOWLIST` for legitimate root or
  global reads only.
- Documented each allowlisted method with a per-method justification:
  - `TenantRepository.get_by_slug`
  - `TenantRepository.list_all`
  - `SendRepository.get_global`
  - `SendRepository.find_by_message_id_global`
- Kept repository-class exemptions empty.
- Kept `TenantRepository.get_credential` out of the allowlist.
- Added a meta-test that verifies allowlist entries are discovered, documented,
  still missing `tenant_id`, and do not include `TenantRepository.get_credential`.
- Left the Phase B live isolation shim unchanged for ENG-231.

## Verification

Commands run:

```bash
.venv/bin/python -m pytest -q tests/integration/test_tenant_isolation.py::test_at_least_one_repository_read_method_was_discovered tests/integration/test_tenant_isolation.py::test_repository_read_method_takes_tenant_id tests/integration/test_tenant_isolation.py::test_root_or_global_read_allowlist_is_narrow_and_documented
```

Result: `1 failed, 66 passed`. The only failure was the intended residual
failure:

- `TenantRepository.get_credential` is missing `tenant_id`.

```bash
.venv/bin/python -m pytest -q tests/integration/test_tenant_isolation.py::test_meta_compliant_stub_is_classified_as_safe tests/integration/test_tenant_isolation.py::test_meta_leaky_stub_is_classified_as_unsafe tests/integration/test_tenant_isolation.py::test_meta_failure_message_names_file_and_method
```

Result: `3 passed`.

```bash
.venv/bin/ruff check tests/integration/test_tenant_isolation.py
.venv/bin/ruff format --check tests/integration/test_tenant_isolation.py
```

Result: both passed after formatting the file with:

```bash
.venv/bin/ruff format tests/integration/test_tenant_isolation.py
```

```bash
.venv/bin/python -m pytest -q tests/integration/test_tenant_isolation.py::test_emit_repository_inventory -s
```

Result: `1 passed`; inventory shows 65 discovered read methods and 5 missing
`tenant_id` before the method-level allowlist is applied.

## Residual Failures

- `TenantRepository.get_credential` remains a structural failure and should be
  fixed by ENG-230 with a tenant-scoped credential read.
- Full `tests/integration/test_tenant_isolation.py` still has the Phase B live
  isolation shim failures. This was intentionally not skipped or xfailed because
  ENG-231 owns the live harness implementation.

## Risks

- The allowlist is only as strong as the documented caller contracts. The
  outreach global send lookups must continue deriving or verifying
  `send.tenant_id` before tenant-scoped writes.
- `TenantRepository.list_all` is a root/admin surface. Any operator-facing route
  that exposes it needs authorization outside this structural repository test.

## Do-Not-Merge Conditions

- Do not merge a full-suite-green claim while `TenantRepository.get_credential`
  remains unfixed.
- Do not add `TenantRepository.get_credential` to the allowlist without a new
  architecture decision.
- Do not broaden the Phase B live harness skip/xfail as part of ENG-229.
