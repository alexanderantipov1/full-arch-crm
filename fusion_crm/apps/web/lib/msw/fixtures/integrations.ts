import type { IntegrationAccount } from "@/lib/api/schemas";

/** Mutable in-memory store so the UI can flip status during the session. */
export const integrationStore: Record<string, IntegrationAccount> = {
  salesforce: {
    id: "ddee0001-0000-0000-0000-000000000001",
    provider: "salesforce",
    status: "disconnected",
    display_name: null,
    last_sync_at: null,
    last_sync_summary: null,
    error_message: null,
  },
  carestack: {
    id: "ddee0002-0000-0000-0000-000000000002",
    provider: "carestack",
    status: "disconnected",
    display_name: null,
    last_sync_at: null,
    last_sync_summary: null,
    error_message: null,
  },
};
