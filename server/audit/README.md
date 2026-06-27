# HIPAA Audit Trail

Immutable, append-only audit logging for all Protected Health Information (PHI)
access — required under HIPAA Security Rule **§164.312(b)**.

---

## HIPAA Requirement — §164.312(b)

The HIPAA Security Rule requires covered entities and business associates to:

> "Implement hardware, software, and/or procedural mechanisms that record and
> examine activity in information systems that contain or use electronic
> protected health information."

This module satisfies that requirement by logging every create, read, update,
delete, and export operation on PHI resources to tamper-evident, append-only
log files.

---

## Log Retention Policy

**Minimum retention: 6 years** (aligned with HIPAA's general documentation
retention requirement at 45 CFR §164.530(j)).

| Item | Requirement |
|------|-------------|
| Retention period | 6 years from date of creation or last effective date |
| Storage format | Newline-delimited JSON (`.log`), one file per calendar day |
| Access controls | Read-only for all application roles; write via append-only logger only |
| Backup | Include `server/audit/logs/` in your off-site backup schedule |
| Destruction | Logs may not be destroyed before the retention period expires |

> **Recommendation:** Forward logs to a write-once S3 bucket (Object Lock) or
> an immutable SIEM (Splunk, Datadog, etc.) in production. Local-disk logs
> should be treated as the primary replica, not the only replica.

---

## What IS Logged

Every audit entry is a JSON object on a single line:

```json
{
  "timestamp": "2026-06-27T20:00:00.000Z",
  "requestId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "tenantId": "clinic-42",
  "userId": "usr_8f3a9",
  "action": "READ",
  "resource": "patient",
  "resourceId": "pat_00123",
  "outcome": "SUCCESS",
  "ipAddress": "192.0.2.1",
  "userAgent": "Mozilla/5.0 ...",
  "phiFields": ["firstName", "lastName", "dateOfBirth", "diagnosisCode"],
  "reason": "Routine follow-up appointment"
}
```

| Field | Description |
|-------|-------------|
| `timestamp` | ISO 8601 UTC — when the event occurred |
| `requestId` | UUID v4 — correlates events within one HTTP request |
| `tenantId` | Multi-tenant clinic/organisation identifier |
| `userId` | Who performed the action (`system` for automated agents) |
| `action` | `READ`, `WRITE`, `DELETE`, `EXPORT`, `LOGIN`, `LOGOUT`, `QUERY` |
| `resource` | Resource type: `patient`, `treatment_plan`, `insurance_claim`, etc. |
| `resourceId` | Opaque resource identifier — e.g. the patient record ID |
| `outcome` | `SUCCESS`, `FAILURE`, or `DENIED` |
| `ipAddress` | Client IP (from `X-Forwarded-For` or socket) |
| `userAgent` | Browser/client string from the HTTP request |
| `phiFields` | **Names** of PHI fields accessed — never their values |
| `reason` | Optional business justification for sensitive queries |

### Auto-covered PHI Routes (middleware)

| Route prefix | Audited actions |
|---|---|
| `/api/patients/*` | READ (GET), WRITE (POST/PUT/PATCH), DELETE |
| `/api/appointments/*` | READ (GET), WRITE (POST/PUT/PATCH), DELETE |
| `/api/claims/*` | READ (GET), WRITE (POST/PUT/PATCH), DELETE |

---

## What is NOT Logged

| What | Why |
|------|-----|
| **PHI values** | HIPAA audit logs must not become a secondary PHI store. Only field *names* are recorded. |
| **Passwords / secrets** | Never included in any log. |
| **Non-PHI API routes** | Routes outside the covered prefixes are not audited by default. |
| **Internal health-check endpoints** | `/health`, `/metrics`, etc. are excluded. |

---

## Log File Format

Files are stored at:

```
server/audit/logs/audit-YYYY-MM-DD.log
```

Each line is a complete, self-contained JSON object (NDJSON). Files are
**never** truncated or overwritten — only appended to.

Example (two lines from the same file):
```
{"timestamp":"2026-06-27T09:00:00.000Z","requestId":"...","action":"LOGIN",...}
{"timestamp":"2026-06-27T09:01:05.123Z","requestId":"...","action":"READ",...}
```

---

## Usage

### 1. Attach the middleware (global)

```typescript
import express from 'express';
import { auditMiddleware } from './audit/audit-middleware.js';

const app = express();
app.use(auditMiddleware);   // must come before route definitions
```

### 2. Enrich a route with PHI field names

```typescript
import { setAuditPhiFields, setAuditReason } from './audit/audit-middleware.js';

router.get('/patients/:id', async (req, res) => {
  setAuditPhiFields(res, ['firstName', 'lastName', 'dateOfBirth', 'ssn']);
  setAuditReason(res, 'Routine care access');

  const patient = await db.patients.findById(req.params.id);
  res.json(patient);
});
```

### 3. Log manually (agent/system actions)

```typescript
import { AuditLogger } from './audit/audit-logger.js';

AuditLogger.log({
  requestId: uuidv4(),
  tenantId: 'clinic-42',
  userId: 'system',
  action: 'EXPORT',
  resource: 'patient',
  resourceId: 'pat_00123',
  outcome: 'SUCCESS',
  phiFields: ['fullRecord'],
  reason: 'Monthly compliance report generation',
});
```

---

## Running a Compliance Report

Use `AuditLogger.query()` to generate filtered compliance reports:

```typescript
import { AuditLogger } from './audit/audit-logger.js';

// All accesses by a specific tenant in June 2026
const entries = AuditLogger.query({
  tenantId: 'clinic-42',
  startDate: new Date('2026-06-01'),
  endDate:   new Date('2026-06-30'),
});

// All denied access attempts this week
const denied = AuditLogger.query({
  startDate: new Date('2026-06-21'),
  endDate:   new Date('2026-06-27'),
}).filter(e => e.outcome === 'DENIED');

console.table(denied);
```

### Available filters

| Filter | Type | Description |
|--------|------|-------------|
| `tenantId` | `string` | Filter by tenant |
| `startDate` | `Date` | Inclusive start (UTC) |
| `endDate` | `Date` | Inclusive end (UTC, to end-of-day) |
| `action` | `AuditAction` | One of READ, WRITE, DELETE, etc. |
| `resource` | `string` | Resource type, e.g. `'patient'` |

---

## Security Considerations

- **Immutability:** The `appendLine` helper uses the `wx`-then-`a` flag pattern
  — the file is never opened for writing from the start, so accidental
  truncation is prevented.
- **No delete API:** `AuditLogger` deliberately exposes no delete or overwrite
  method. Removal of log lines must go through out-of-band processes with
  documented justification.
- **Audit of the auditor:** If the audit logger itself fails (disk full,
  permission denied), it writes to `stderr` and does **not** silently swallow
  the error — hook into your ops alerting on that stream.
- **Production hardening:** In production, replicate logs to an immutable
  off-site store (AWS S3 Object Lock, Azure Immutable Blob, Splunk, etc.).

---

## Related Regulatory References

| Reference | Description |
|-----------|-------------|
| 45 CFR §164.312(b) | Audit controls — technical safeguard |
| 45 CFR §164.312(a)(2)(i) | Unique user identification |
| 45 CFR §164.312(c)(1) | Integrity controls |
| 45 CFR §164.530(j) | Documentation retention (6 years) |
| NIST SP 800-66r2 | Implementing the HIPAA Security Rule |
