/**
 * Server-side mapping from CareStack rows → our wire format.
 *
 * Phase 1 v1 uses the verified `/api/v1.0/locations` endpoint to confirm
 * connectivity and exposes location count as the sync record count.
 * Patient/appointment normalization lands when we wire the search endpoints.
 */
import "server-only";
import crypto from "node:crypto";

export interface CSLocation {
  id: number;
  shortName: string;
  name: string;
  email: string | null;
  timeZone: string | null;
  phone1: string | null;
  phone2: string | null;
  fax: string | null;
  website: string | null;
  logoUrl: string | null;
}

const NS = "fusion-cs";

export function uuidFromCSId(kind: string, id: string | number): string {
  const hash = crypto.createHash("sha1").update(`${NS}:${kind}:${id}`).digest("hex");
  return [
    hash.slice(0, 8),
    hash.slice(8, 12),
    "5" + hash.slice(13, 16),
    "8" + hash.slice(17, 20),
    hash.slice(20, 32),
  ].join("-");
}
