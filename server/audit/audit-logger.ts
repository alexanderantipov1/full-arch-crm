/**
 * HIPAA-Compliant Audit Logger
 *
 * Immutable, append-only audit trail for all PHI (Protected Health Information)
 * access events. Required under HIPAA Security Rule §164.312(b).
 *
 * IMPORTANT: This logger NEVER records PHI values — only field names,
 * resource identifiers, and action metadata.
 */

import fs from 'fs';
import path from 'path';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type AuditAction =
  | 'READ'
  | 'WRITE'
  | 'DELETE'
  | 'EXPORT'
  | 'LOGIN'
  | 'LOGOUT'
  | 'QUERY';

export type AuditOutcome = 'SUCCESS' | 'FAILURE' | 'DENIED';

export interface AuditEntry {
  /** ISO 8601 UTC timestamp — set automatically by AuditLogger.log() */
  timestamp: string;
  /** UUID v4 — correlates a single request across log lines */
  requestId: string;
  /** Tenant/organisation identifier */
  tenantId: string;
  /** Authenticated user ID, or 'system' for automated/agent actions */
  userId: string;
  /** The operation performed */
  action: AuditAction;
  /** Resource type, e.g. 'patient', 'treatment_plan', 'insurance_claim' */
  resource: string;
  /** Opaque resource identifier — no PHI values, just the ID */
  resourceId: string;
  /** Whether the operation succeeded, failed, or was denied */
  outcome: AuditOutcome;
  /** Client IP address (optional) */
  ipAddress?: string;
  /** HTTP User-Agent string (optional) */
  userAgent?: string;
  /**
   * Names of PHI fields that were accessed or modified.
   * Record NAMES ONLY — never values.
   * Example: ['firstName', 'dateOfBirth', 'diagnosisCode']
   */
  phiFields?: string[];
  /** Business justification for sensitive queries */
  reason?: string;
}

// The public API omits `timestamp`; the logger stamps it automatically.
export type AuditEntryInput = Omit<AuditEntry, 'timestamp'>;

// Filters for compliance report queries
export interface AuditQueryFilters {
  tenantId?: string;
  startDate?: Date;
  endDate?: Date;
  action?: AuditAction;
  resource?: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Returns the log directory (configurable via AUDIT_LOG_DIR env var). */
function logDir(): string {
  return (
    process.env.AUDIT_LOG_DIR ??
    path.resolve(process.cwd(), 'server', 'audit', 'logs')
  );
}

/** Returns today's log file path: audit-YYYY-MM-DD.log */
function todayLogPath(date: Date = new Date()): string {
  const yyyy = date.getUTCFullYear();
  const mm = String(date.getUTCMonth() + 1).padStart(2, '0');
  const dd = String(date.getUTCDate()).padStart(2, '0');
  return path.join(logDir(), `audit-${yyyy}-${mm}-${dd}.log`);
}

/** Ensures the log directory exists (idempotent). */
function ensureLogDir(): void {
  const dir = logDir();
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

/**
 * Appends a newline-delimited JSON line to the log file.
 *
 * Uses the `wx`-then-`a` flag pattern:
 *   1. Try `wx` (create-new, exclusive) for the very first write of the day.
 *   2. On EEXIST fall through to `a` (append).
 *
 * This guarantees the file is never truncated or overwritten.
 */
function appendLine(filePath: string, line: string): void {
  ensureLogDir();
  const payload = line + '\n';
  try {
    // Attempt exclusive create — succeeds on first write of the day
    fs.appendFileSync(filePath, payload, { flag: 'wx', encoding: 'utf8' });
  } catch (err: unknown) {
    if ((err as NodeJS.ErrnoException).code === 'EEXIST') {
      // File already exists — safe to append
      fs.appendFileSync(filePath, payload, { flag: 'a', encoding: 'utf8' });
    } else {
      // Re-throw unexpected errors (disk full, permissions, etc.)
      throw err;
    }
  }
}

// ---------------------------------------------------------------------------
// AuditLogger
// ---------------------------------------------------------------------------

export const AuditLogger = {
  /**
   * Appends an immutable audit entry to today's log file.
   *
   * @param entry  All fields except `timestamp` (stamped automatically).
   */
  log(entry: AuditEntryInput): void {
    const fullEntry: AuditEntry = {
      ...entry,
      timestamp: new Date().toISOString(),
    };

    // Paranoia: strip any attempt to include PHI values in phiFields.
    // phiFields must only contain NAMES (strings), not objects/arrays with data.
    if (fullEntry.phiFields) {
      fullEntry.phiFields = fullEntry.phiFields.map((f) => String(f));
    }

    const line = JSON.stringify(fullEntry);
    const filePath = todayLogPath();

    try {
      appendLine(filePath, line);
    } catch (writeErr) {
      // Audit failures must not silently disappear — write to stderr at minimum.
      // In production, hook this up to an alerting system.
      process.stderr.write(
        `[AUDIT CRITICAL] Failed to write audit log: ${String(writeErr)}\n` +
          `Entry: ${line}\n`
      );
    }
  },

  /**
   * Reads and filters audit log entries for compliance reports.
   *
   * Scans log files in the date range [startDate, endDate] (inclusive).
   * Defaults to today if neither is specified.
   *
   * @param filters  Optional filters; all are AND-combined.
   * @returns        Matching AuditEntry objects, in chronological order.
   */
  query(filters: AuditQueryFilters = {}): AuditEntry[] {
    const { tenantId, startDate, endDate, action, resource } = filters;

    // Build the set of dates to scan
    const start = startDate ?? new Date();
    const end = endDate ?? new Date();
    const dates = dateBetween(start, end);

    const results: AuditEntry[] = [];

    for (const date of dates) {
      const filePath = todayLogPath(date);
      if (!fs.existsSync(filePath)) continue;

      const lines = fs.readFileSync(filePath, 'utf8').split('\n');
      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;

        let entry: AuditEntry;
        try {
          entry = JSON.parse(trimmed) as AuditEntry;
        } catch {
          // Malformed line — skip, do not throw (log may be partially written)
          continue;
        }

        if (tenantId && entry.tenantId !== tenantId) continue;
        if (action && entry.action !== action) continue;
        if (resource && entry.resource !== resource) continue;

        // Date-range filter against the entry's own timestamp
        if (startDate) {
          const ts = new Date(entry.timestamp);
          if (ts < startDate) continue;
        }
        if (endDate) {
          const ts = new Date(entry.timestamp);
          // Include entries up to end of endDate day
          const endOfDay = new Date(endDate);
          endOfDay.setUTCHours(23, 59, 59, 999);
          if (ts > endOfDay) continue;
        }

        results.push(entry);
      }
    }

    return results;
  },
} as const;

// ---------------------------------------------------------------------------
// Internal utility
// ---------------------------------------------------------------------------

/** Returns an array of Date objects for each calendar day from start to end (UTC). */
function dateBetween(start: Date, end: Date): Date[] {
  const dates: Date[] = [];
  // Normalise to UTC midnight
  const cursor = new Date(
    Date.UTC(start.getUTCFullYear(), start.getUTCMonth(), start.getUTCDate())
  );
  const endNorm = new Date(
    Date.UTC(end.getUTCFullYear(), end.getUTCMonth(), end.getUTCDate())
  );

  while (cursor <= endNorm) {
    dates.push(new Date(cursor));
    cursor.setUTCDate(cursor.getUTCDate() + 1);
  }
  return dates;
}
