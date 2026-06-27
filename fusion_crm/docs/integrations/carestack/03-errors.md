# Errors

Standard HTTP status semantics; body is a JSON error envelope. The
spec includes an "Error Response Signatures" section listing codes
with per-endpoint explanations — see `_source/carestack-v1.0.45.txt`
for the full list and grep by code.

## Status bands

| Band | Meaning | Typical causes |
|---|---|---|
| `2xx` | Success | 200 OK, 201 Created, 204 No Content |
| `400` | Bad request | malformed body, unknown enum value |
| `401` | Unauthorized | token missing / expired / bad credentials |
| `403` | Forbidden | account lacks feature, endpoint not enabled |
| `404` | Not found | path ID doesn't exist |
| `409` | Conflict | unique-constraint collision, state mismatch |
| `422` | Validation | field-level validation failure |
| `429` | Too many requests | client-side backoff |
| `5xx` | Server side | transient — retry with backoff |

## Error envelope (typical)

```json
{
  "errorCode": "PATIENT_NOT_FOUND",
  "message": "Patient with id 1234 was not found"
}
```

Exact shape can vary by endpoint; some return a list of field
errors. Always parse defensively and log `errorCode` + `message`.

## Retry / backoff policy (our side)

- 401 once → refresh token → retry once. Second 401 → raise
  `IntegrationError`.
- 429 / 5xx → exponential backoff via `tenacity`:
  `wait_exponential(multiplier=1, min=1, max=30)`, `stop_after_attempt(5)`.
- 4xx other than 401/429 → raise `IntegrationError` (do not retry;
  it's a client bug or a state mismatch).

## Mapping to Fusion exceptions

- Any non-2xx in the CareStack client → `packages.core.exceptions.IntegrationError`
  with `code="carestack_<errorCode>"` and original body in `details`.
- Timeouts / connection errors → same `IntegrationError` with
  `code="carestack_transport"`.
