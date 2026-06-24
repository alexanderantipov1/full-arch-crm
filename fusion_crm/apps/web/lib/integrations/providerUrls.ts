/**
 * Synthesise an external "open in provider" URL from a SourceLink row.
 *
 * Returns `null` when the provider / entity combination has no stable
 * deep-link pattern. UI must hide the link when null instead of rendering
 * a broken anchor.
 *
 * The patterns here mirror what the backend `OAUTH_REDIRECT_BASE_URL` /
 * provider docs publish; ENG-218 introduces them on the client so we can
 * render the link without an extra API call. Backend ships its own copy
 * eventually (when persons endpoint goes real).
 */
export type ProviderUrlBases = {
  salesforceLightningBaseUrl?: string | null;
  carestackAppBaseUrl?: string | null;
};

type TenantSettingLike = {
  key: string;
  value?: unknown;
};

export function providerUrlFor(
  provider: string,
  entity: string,
  externalId: string,
  bases: ProviderUrlBases = {},
): string | null {
  const normalizedEntity = entity.trim().toLowerCase();
  switch (provider) {
    case "salesforce": {
      // Salesforce Lightning URL pattern: {SF_BASE}/lightning/r/{Object}/{Id}/view.
      const obj = SF_OBJECT_BY_ENTITY[normalizedEntity] ?? entity;
      const base = normalizeBaseUrl(bases.salesforceLightningBaseUrl) ?? SALESFORCE_FALLBACK_BASE;
      return `${base}/lightning/r/${obj}/${encodeURIComponent(
        externalId,
      )}/view`;
    }
    case "carestack": {
      const path = CARESTACK_PATH_BY_ENTITY[normalizedEntity] ?? "patient";
      const base = normalizeBaseUrl(bases.carestackAppBaseUrl) ?? CARESTACK_FALLBACK_BASE;
      return `${base}/${path}/${encodeURIComponent(
        externalId,
      )}`;
    }
    case "hubspot":
    case "google_workspace":
    case "microsoft_365":
      // These integrations exist on the tenant credential surface but do not
      // have a per-record "open in provider" URL today.
      return null;
    default:
      return null;
  }
}

export function providerUrlBasesFromTenantSettings(
  settings: TenantSettingLike[],
): ProviderUrlBases {
  const out: ProviderUrlBases = {};
  for (const setting of settings) {
    if (setting.key === "provider_link_bases" && isRecord(setting.value)) {
      out.salesforceLightningBaseUrl = stringValue(
        setting.value.salesforce_lightning_base_url,
      );
      out.carestackAppBaseUrl = stringValue(setting.value.carestack_app_base_url);
      continue;
    }
    if (setting.key === "salesforce.lightning_base_url") {
      out.salesforceLightningBaseUrl = stringValue(setting.value);
      continue;
    }
    if (setting.key === "carestack.app_base_url") {
      out.carestackAppBaseUrl = stringValue(setting.value);
    }
  }
  return out;
}

const SALESFORCE_FALLBACK_BASE = "https://login.salesforce.com";
const CARESTACK_FALLBACK_BASE = "https://app.carestack.com";

const SF_OBJECT_BY_ENTITY: Record<string, string> = {
  lead: "Lead",
  contact: "Contact",
  account: "Account",
  opportunity: "Opportunity",
  event: "Event",
  task: "Task",
};

const CARESTACK_PATH_BY_ENTITY: Record<string, string> = {
  patient: "patient",
  appointment: "appointment",
};

function normalizeBaseUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  const trimmed = value.trim();
  if (!trimmed) return null;
  return trimmed.replace(/\/+$/, "");
}

function stringValue(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
