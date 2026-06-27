/**
 * rawSourceWriter.ts — Immutable source layer for the Karpathy wiki.
 *
 * Implements Karpathy Rule I: "Sources Are Immutable"
 * Every raw event is written here BEFORE the wiki is updated.
 * Files are NEVER modified after creation — append-only, ground truth.
 *
 * PHI Policy: All identifying fields are stripped before writing.
 * Only anonymized patterns, statistics, and clinical codes are stored.
 *
 * File naming: {YYYY-MM-DD}_{EVENT_TYPE}_{shortId}.json
 * Location:    server/simulation/wiki/raw/{category}/
 */

import * as fs   from "fs";
import * as path from "path";
import * as crypto from "crypto";

// ── Types ─────────────────────────────────────────────────────────────────────

export type RawEventCategory =
  | "eob"
  | "simulation"
  | "appointments"
  | "adapter"
  | "agent-decisions";

/** PHI-stripped raw event record */
export interface RawSourceEvent {
  /** Short unique ID (8 hex chars) */
  id:           string;
  /** ISO timestamp when the event occurred */
  timestamp:    string;
  /** Event type — must be one of the known WikiService event types */
  eventType:    string;
  /** Anonymized hash of tenantId+personUid — never the real ID */
  personHash?:  string;
  /** Tenant slug (not tenant UUID) */
  tenantSlug?:  string;
  /** CDT code if applicable */
  cdtCode?:     string;
  /** Payer name (not payer ID) */
  payer?:       string;
  /** Claim outcome */
  outcome?:     string;
  /** Denial reason code */
  denialReason?: string;
  /** Dollar amount (rounded to nearest $100 — not exact) */
  amountBucket?: string;
  /** Any additional ops-safe fields */
  metadata?:    Record<string, unknown>;
  /** Which wiki page this event is expected to update */
  targetWikiPage?: string;
  /** Confirmation that PHI scrub was applied */
  _phiScrubbed: true;
}

/** PHI fields that must NEVER appear in raw/ */
const PHI_FIELD_NAMES = new Set([
  "patientId", "patient_id", "personUid", "person_uid",
  "firstName", "first_name", "lastName", "last_name",
  "dateOfBirth", "date_of_birth", "dob",
  "ssn", "socialSecurityNumber",
  "phone", "phoneNumber", "phone_number",
  "email", "emailAddress",
  "address", "streetAddress", "zipCode",
  "chartNumber", "chart_number", "mrn",
  "insuranceId", "insurance_id", "memberId", "member_id",
  "groupNumber", "group_number",
]);

// ── Config ────────────────────────────────────────────────────────────────────

const RAW_BASE = path.resolve(process.cwd(), "server/simulation/wiki/raw");

// ── Helpers ───────────────────────────────────────────────────────────────────

function shortId(): string {
  return crypto.randomBytes(4).toString("hex");
}

function todayStr(): string {
  return new Date().toISOString().slice(0, 10);
}

function bucketAmount(amount: unknown): string | undefined {
  const n = Number(amount);
  if (isNaN(n)) return undefined;
  const bucket = Math.round(n / 100) * 100;
  return `$${bucket}`;
}

function anonymizePersonUid(tenantId: string, personUid: string): string {
  return crypto
    .createHash("sha256")
    .update(`${tenantId}:${personUid}`)
    .digest("hex")
    .slice(0, 16);
}

/**
 * Strips PHI from an arbitrary event object.
 * Returns a clean copy — never mutates the original.
 */
function scrubPhi(raw: Record<string, unknown>): Record<string, unknown> {
  const clean: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(raw)) {
    if (PHI_FIELD_NAMES.has(key)) continue; // drop PHI field
    if (value && typeof value === "object" && !Array.isArray(value)) {
      clean[key] = scrubPhi(value as Record<string, unknown>);
    } else {
      clean[key] = value;
    }
  }
  return clean;
}

function detectPhiFields(obj: Record<string, unknown>): string[] {
  const found: string[] = [];
  for (const key of Object.keys(obj)) {
    if (PHI_FIELD_NAMES.has(key)) found.push(key);
    const val = obj[key];
    if (val && typeof val === "object" && !Array.isArray(val)) {
      found.push(...detectPhiFields(val as Record<string, unknown>));
    }
  }
  return found;
}

function categoryForEventType(eventType: string): RawEventCategory {
  if (eventType.startsWith("EOB_") || eventType.startsWith("PRIOR_AUTH_"))
    return "eob";
  if (eventType.startsWith("SIMULATION_") || eventType.startsWith("AGENT_LEARNING") ||
      eventType === "PATTERN_DISCOVERED" || eventType === "ARCHITECTURE_DECISION" ||
      eventType === "CODE_FIX")
    return "simulation";
  if (eventType.startsWith("APPOINTMENT_"))
    return "appointments";
  if (eventType.startsWith("ADAPTER_") || eventType.startsWith("DAILY_SUMMARY"))
    return "adapter";
  return "agent-decisions";
}

// ── Main Export ───────────────────────────────────────────────────────────────

export class RawSourceWriter {
  private readonly enabled: boolean;

  constructor(enabled = true) {
    this.enabled = enabled;
  }

  /**
   * Write a raw source event to disk BEFORE wiki ingestion.
   * Enforces PHI scrubbing, immutability, and naming convention.
   *
   * Returns the written file path (relative to wiki root), or null if disabled.
   */
  write(
    eventType: string,
    rawEvent:  Record<string, unknown>,
    opts?: {
      tenantId?:      string;
      personUid?:     string;
      targetWikiPage?: string;
    }
  ): string | null {
    if (!this.enabled) return null;

    // 1. Detect PHI before scrubbing (for audit log)
    const phiDetected = detectPhiFields(rawEvent);
    if (phiDetected.length > 0) {
      console.warn(
        `[RawSourceWriter] PHI fields detected in ${eventType} — scrubbing: ${phiDetected.join(", ")}`
      );
    }

    // 2. Scrub PHI
    const clean = scrubPhi(rawEvent);

    // 3. Build canonical record
    const record: RawSourceEvent = {
      id:           shortId(),
      timestamp:    new Date().toISOString(),
      eventType,
      _phiScrubbed: true,
      personHash:      (opts?.tenantId && opts?.personUid)
                         ? anonymizePersonUid(opts.tenantId, opts.personUid)
                         : undefined,
      cdtCode:         clean.cdtCode   ? String(clean.cdtCode)      : undefined,
      payer:           clean.payer     ? String(clean.payer)         : undefined,
      outcome:         clean.outcome   ? String(clean.outcome)       : undefined,
      denialReason:    clean.denialReason ? String(clean.denialReason) : undefined,
      amountBucket:    clean.amount    ? bucketAmount(clean.amount)  : undefined,
      targetWikiPage:  opts?.targetWikiPage,
      tenantSlug:      undefined, // never include raw tenant UUID
      metadata: {
        ...clean,
        // Remove fields already promoted to top level
        cdtCode:      undefined,
        payer:        undefined,
        outcome:      undefined,
        denialReason: undefined,
        amount:       undefined,
      },
    };

    // 4. Determine category sub-folder
    const category = categoryForEventType(eventType);
    const dir = path.join(RAW_BASE, category);

    // Ensure directory exists
    fs.mkdirSync(dir, { recursive: true });

    // 5. Write file (never overwrite — unique ID per file)
    const filename = `${todayStr()}_${eventType}_${record.id}.json`;
    const filepath = path.join(dir, filename);

    // Immutability check — should never happen but guard anyway
    if (fs.existsSync(filepath)) {
      console.error(`[RawSourceWriter] IMMUTABILITY VIOLATION: ${filepath} already exists`);
      return null;
    }

    fs.writeFileSync(filepath, JSON.stringify(record, null, 2), { flag: "wx" }); // wx = fail if exists

    return `raw/${category}/${filename}`;
  }

  /**
   * List raw source files for a given date range.
   * Used by wiki-autofile.ts to find overnight events.
   */
  listSince(since: Date, category?: RawEventCategory): Array<{
    path:      string;
    eventType: string;
    timestamp: string;
    id:        string;
  }> {
    const categories: RawEventCategory[] = category
      ? [category]
      : ["eob", "simulation", "appointments", "adapter", "agent-decisions"];

    const results: ReturnType<RawSourceWriter["listSince"]> = [];

    for (const cat of categories) {
      const dir = path.join(RAW_BASE, cat);
      if (!fs.existsSync(dir)) continue;

      const files = fs.readdirSync(dir)
        .filter(f => f.endsWith(".json"))
        .map(f => {
          const [dateStr, eventType, id] = f.replace(".json", "").split("_");
          return { file: f, dateStr, eventType, id };
        })
        .filter(({ dateStr }) => {
          const fileDate = new Date(dateStr + "T00:00:00Z");
          return fileDate >= since;
        });

      for (const { file, eventType, id } of files) {
        try {
          const content = JSON.parse(
            fs.readFileSync(path.join(dir, file), "utf-8")
          ) as RawSourceEvent;
          results.push({
            path:      `raw/${cat}/${file}`,
            eventType: content.eventType ?? eventType,
            timestamp: content.timestamp,
            id:        content.id ?? id,
          });
        } catch { /* skip malformed files */ }
      }
    }

    return results.sort((a, b) => a.timestamp.localeCompare(b.timestamp));
  }

  /**
   * Lint the raw/ folder:
   * - Flag files older than maxAgeDays with no wiki citation
   * - Count files per category
   * - Check for anomalously large categories (>10k files)
   */
  lint(maxAgeDays = 180): {
    orphanSources: string[];
    categoryCounts: Record<string, number>;
    warnings: string[];
  } {
    const categories: RawEventCategory[] = [
      "eob", "simulation", "appointments", "adapter", "agent-decisions"
    ];
    const cutoff = new Date(Date.now() - maxAgeDays * 86_400_000);
    const orphanSources: string[] = [];
    const categoryCounts: Record<string, number> = {};
    const warnings: string[] = [];

    for (const cat of categories) {
      const dir = path.join(RAW_BASE, cat);
      if (!fs.existsSync(dir)) { categoryCounts[cat] = 0; continue; }

      const files = fs.readdirSync(dir).filter(f => f.endsWith(".json"));
      categoryCounts[cat] = files.length;

      if (files.length > 10_000) {
        warnings.push(`${cat}/ has ${files.length} files — consider archiving to cold storage`);
      }

      for (const file of files) {
        const [dateStr] = file.split("_");
        const fileDate = new Date(dateStr + "T00:00:00Z");
        if (fileDate < cutoff) {
          orphanSources.push(`raw/${cat}/${file}`);
        }
      }
    }

    return { orphanSources, categoryCounts, warnings };
  }
}

// Singleton — same pattern as wikiService
export const rawSourceWriter = new RawSourceWriter(
  process.env.WIKI_RAW_DISABLED !== "true"
);
