# ENG-502 — Secret leak via httpx request-line logging

Branch: `eng-489-marketing-creds-provider-kinds` (working tree only — NOT committed/pushed).
Parent: ENG-488. Linear: https://linear.app/fusion-dental-implants/issue/ENG-502

## What leaked

The integration HTTP clients use `httpx`. `httpx` emits an **INFO**-level
record under logger name `"httpx"`:

```
logger.info('HTTP Request: %s %s "%s %d %s"', method, url, ...)
```

The `url` arg is the **full request URL including the query string**. For the
marketing/SEO pulls that string can carry a secret:

- **Meta Ads** (`packages/integrations/meta_ads/client.py`): `_get_paginated`
  passes `access_token` as a **query param** (`{**params, "access_token": ...}`)
  and follows `paging.next` cursor URLs **with the token baked in**. So every
  Graph request logged the line:
  `HTTP Request: GET https://graph.facebook.com/.../insights?...&access_token=<TOKEN>`
- **Google OAuth token refresh** (all 4 Google clients): the
  `https://oauth2.googleapis.com/token` POST URL has no token in the query, but
  the same INFO line is emitted for every request; the `?access_token=` risk is
  concretely realised by Meta.

Reproduced the leak (handler capturing stdlib records, httpx at default INFO):
1 record leaked the literal token value. After the fix: 0.

The Google Ads / GA4 / GSC clients send tokens in the **`Authorization`
header** (never in the URL query), so their own risk is lower, but the httpx
INFO line still logs full URLs and is clamped uniformly.

### Our own client logs — audited, CLEAN

Every `log.*` call in the marketing/SEO/SF/CareStack clients carries only safe
fields: event codes (`*.token.refreshed`, `*.401_refreshing`), `customer_id`,
`property_id`, `site_url` (a domain, not a secret), `path` (path segment only,
no query string), `expires_in`. **No client logs a full URL, a token, or any
secret query param.** No code change was needed in the clients.

## The fix

### Primary — clamp the HTTP-client loggers (`packages/core/logging.py`)

In `configure_logging()`:

```python
for noisy in ("httpx", "httpcore"):
    logging.getLogger(noisy).setLevel(logging.WARNING)
```

Verified logger names against the installed libs: httpx logs under `"httpx"`
(`_client.py:117`); httpcore under `"httpcore.connection"` / `.http11` / etc.
(parent `"httpcore"` covers all children). WARNING+ still surfaces real
HTTP/connection errors — only the INFO request line (with the URL) is silenced.

### Defense-in-depth — `redact_url()` helper (`packages/core/logging.py`)

A reusable helper that masks secret-bearing query-param values (`***`) while
preserving the path + non-secret params, for any URL we *might* choose to log
later. Secret key set: `access_token, token, refresh_token, id_token,
fb_exchange_token, client_secret, developer_token, key, api_key, code,
password, secret, assertion`. No current caller logs a URL, so this is a
sanctioned utility, not wired into a new log line (we deliberately do NOT add
new URL logging — "prefer not logging full URLs at all").

## Files changed

- `packages/core/logging.py` — clamp httpx/httpcore loggers; add `redact_url()`.
- `tests/core/test_log_secret_redaction.py` — new. Unit tests for `redact_url`
  (Meta + OAuth params, passthrough) and the clamp (httpx/httpcore at WARNING,
  INFO disabled, WARNING enabled).
- `tests/integrations/meta_ads/test_client_no_token_in_logs.py` — new.
  Mocks the Meta transport (respx), makes a paginating request whose URL holds
  a known token, captures **every** stdlib log record (root level forced to
  DEBUG so a regression fails loudly), asserts the token value appears in NO
  record's message/getMessage/args.

## Verification

- `pytest tests/core/test_log_secret_redaction.py tests/integrations/meta_ads/test_client_no_token_in_logs.py` → 5 passed.
- `pytest tests/integrations/{meta_ads,google_ads,google_analytics,google_search_console}` → 39 passed (no regression).
- Negative control: with the clamp removed, the leak test sees 1 leaking httpx
  INFO record carrying the token; with the clamp, 0.
- `ruff check` on changed files → all checks passed.
- `mypy packages/core/logging.py` → success, no issues.
- `grep` of all client `log.*` calls → none carry a URL/token/secret.

## Constraints honoured

No `.env*` touched. No migration. No commit/push. No PHI/secret in code or tests
(token values are obvious fixtures). Legitimate error logging preserved
(WARNING+ unaffected).
