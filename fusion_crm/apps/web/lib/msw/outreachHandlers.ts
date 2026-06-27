import { http, HttpResponse, delay } from "msw";
import {
  CampaignInSchema,
  TemplateInSchema,
  TemplateUpdateSchema,
  type CampaignOut,
  type SendOut,
  type TemplateOut,
} from "@/lib/api/schemas/outreach";
import { IntegrationCredentialBootstrapInputSchema } from "@/lib/api/schemas/tenant";
import {
  newCampaignId,
  newTemplateId,
  nowIso,
  outreachStore,
  recipientPool,
} from "./fixtures/outreach";

/**
 * MSW handlers backing the outreach UI (templates + campaigns + suppressions)
 * during Phase 1 before the FastAPI outreach routes land. Per
 * `apps/web/CLAUDE.md` these handlers will be DELETED once the backend
 * endpoints ship — they are NOT a fallback.
 */

const apiError = (
  status: number,
  code: string,
  message: string,
  details: Record<string, unknown> = {},
) =>
  HttpResponse.json({ error: { code, message, details } }, { status });

function findTemplate(id: string): TemplateOut | undefined {
  return outreachStore.templates.find((t) => t.id === id);
}

function findCampaign(id: string): CampaignOut | undefined {
  return outreachStore.campaigns.find((c) => c.id === id);
}

function buildRenderedFor(t: TemplateOut) {
  // Sample render context — chosen so the MSW preview shows recognisable
  // copy without hitting any real PHI. The renderer on the server uses
  // packages.outreach.render; this is a thin facsimile.
  const ctx: Record<string, string> = {
    "patient.first_name": "Jane",
    "patient.last_name": "Doe",
    "patient.full_name": "Jane Doe",
    "lead.status": "new",
    "lead.source": "Google Ads",
    "appointment.date": "05/15/2026",
    "appointment.time": "2:30 PM",
    "appointment.location_name": "Galleria",
    "location.name": "Galleria Oral Surgery & Dental Implants",
    "location.address": "911 Reserve Drive, Suite 150, Roseville CA",
    "location.phone": "(916) 783-2110",
    "tenant.name": "Fusion Dental Implants",
  };
  const substitute = (s: string) =>
    s.replace(/\{\{\s*([\w.]+)\s*\}\}/g, (_, key) =>
      ctx[key] !== undefined ? ctx[key] : "",
    );
  const subject = substitute(t.subject_template);
  const text = substitute(t.body_template);
  const html =
    `<!doctype html><html><body style="font-family:system-ui,sans-serif;line-height:1.5;padding:24px;color:#111">` +
    text.replace(/\n/g, "<br/>") +
    `</body></html>`;
  return {
    subject,
    body_html: html,
    body_text: text,
    list_unsubscribe_header:
      "<https://example.com/u/abc>, <mailto:unsubscribe@example.com?subject=u:abc>",
  };
}

export const outreachHandlers = [
  // ----------------------------------------------------------- templates
  http.get("/api/outreach/templates", () =>
    HttpResponse.json({ items: outreachStore.templates }),
  ),

  http.get("/api/outreach/templates/:id", ({ params }) => {
    const t = findTemplate(String(params.id));
    if (!t) return apiError(404, "NOT_FOUND", "Template not found");
    return HttpResponse.json(t);
  }),

  http.post("/api/outreach/templates", async ({ request }) => {
    const json = (await request.json()) as unknown;
    const parsed = TemplateInSchema.safeParse(json);
    if (!parsed.success) {
      return apiError(400, "VALIDATION", "Invalid template payload", {
        issues: parsed.error.issues,
      });
    }
    const now = nowIso();
    const created: TemplateOut = {
      id: newTemplateId(),
      tenant_id: "11111111-1111-1111-1111-111111111111",
      name: parsed.data.name,
      description: parsed.data.description ?? null,
      subject_template: parsed.data.subject_template,
      body_template: parsed.data.body_template,
      body_format: parsed.data.body_format,
      category: parsed.data.category,
      tracking_enabled: parsed.data.tracking_enabled,
      intent_tags: parsed.data.intent_tags,
      version: 1,
      status: "draft",
      created_by_actor_id: null,
      created_at: now,
      updated_at: now,
    };
    outreachStore.templates = [created, ...outreachStore.templates];
    await delay(150);
    return HttpResponse.json(created, { status: 201 });
  }),

  http.put("/api/outreach/templates/:id", async ({ params, request }) => {
    const id = String(params.id);
    const existing = findTemplate(id);
    if (!existing) return apiError(404, "NOT_FOUND", "Template not found");
    const json = (await request.json()) as unknown;
    const parsed = TemplateUpdateSchema.safeParse(json);
    if (!parsed.success) {
      return apiError(400, "VALIDATION", "Invalid template patch", {
        issues: parsed.error.issues,
      });
    }
    const patched: TemplateOut = {
      ...existing,
      ...Object.fromEntries(
        Object.entries(parsed.data).filter(([, v]) => v !== undefined),
      ),
      version: existing.version + 1,
      updated_at: nowIso(),
    };
    outreachStore.templates = outreachStore.templates.map((t) =>
      t.id === id ? patched : t,
    );
    await delay(150);
    return HttpResponse.json(patched);
  }),

  http.delete("/api/outreach/templates/:id", async ({ params }) => {
    const id = String(params.id);
    const existing = findTemplate(id);
    if (!existing) return apiError(404, "NOT_FOUND", "Template not found");
    const patched: TemplateOut = {
      ...existing,
      status: "archived",
      updated_at: nowIso(),
    };
    outreachStore.templates = outreachStore.templates.map((t) =>
      t.id === id ? patched : t,
    );
    await delay(100);
    return HttpResponse.json(patched);
  }),

  http.post("/api/outreach/templates/:id/preview", async ({ params }) => {
    const t = findTemplate(String(params.id));
    if (!t) return apiError(404, "NOT_FOUND", "Template not found");
    await delay(120);
    return HttpResponse.json(buildRenderedFor(t));
  }),

  // ----------------------------------------------------------- campaigns
  http.get("/api/outreach/campaigns", () =>
    HttpResponse.json({ items: outreachStore.campaigns }),
  ),

  http.get("/api/outreach/campaigns/:id", ({ params }) => {
    const c = findCampaign(String(params.id));
    if (!c) return apiError(404, "NOT_FOUND", "Campaign not found");
    return HttpResponse.json(c);
  }),

  http.get("/api/outreach/campaigns/:id/sends", ({ params }) => {
    const id = String(params.id);
    const items = outreachStore.sends.filter((s) => s.campaign_id === id);
    return HttpResponse.json({ items, total: items.length });
  }),

  http.post("/api/outreach/campaigns", async ({ request }) => {
    const json = (await request.json()) as unknown;
    const parsed = CampaignInSchema.safeParse(json);
    if (!parsed.success) {
      return apiError(400, "VALIDATION", "Invalid campaign payload", {
        issues: parsed.error.issues,
      });
    }
    const now = nowIso();
    const created: CampaignOut = {
      id: newCampaignId(),
      tenant_id: "11111111-1111-1111-1111-111111111111",
      template_id: parsed.data.template_id,
      name: parsed.data.name,
      recipient_query: parsed.data.recipient_query,
      mailbox_credential_id: parsed.data.mailbox_credential_id ?? null,
      mailbox_strategy: parsed.data.mailbox_strategy,
      scheduled_for: parsed.data.scheduled_for ?? null,
      sent_count: 0,
      opened_count: 0,
      bounced_count: 0,
      unsubscribed_count: 0,
      status: "draft",
      created_by_actor_id: null,
      created_at: now,
      updated_at: now,
    };
    outreachStore.campaigns = [created, ...outreachStore.campaigns];
    await delay(150);
    return HttpResponse.json(created, { status: 201 });
  }),

  http.post("/api/outreach/campaigns/:id/schedule", async ({ params }) => {
    const id = String(params.id);
    const existing = findCampaign(id);
    if (!existing) return apiError(404, "NOT_FOUND", "Campaign not found");
    const patched: CampaignOut = {
      ...existing,
      status: "queued",
      scheduled_for: existing.scheduled_for ?? nowIso(),
      updated_at: nowIso(),
    };
    outreachStore.campaigns = outreachStore.campaigns.map((c) =>
      c.id === id ? patched : c,
    );

    // Synthesise a couple of send rows so the campaign detail page has
    // something to render. Real campaigns get their send rows from
    // SendService.enqueue_campaign; the MSW path stays purely cosmetic.
    const newSends: SendOut[] = recipientPool.slice(0, 3).map((p, idx) => ({
      id: `cc${Date.now()}${idx}-0000-0000-0000-000000000099`,
      tenant_id: "11111111-1111-1111-1111-111111111111",
      campaign_id: id,
      person_uid: p.person_uid,
      recipient_email: p.primary_email ?? "unknown@example.com",
      message_id: null,
      mailbox_credential_id:
        existing.mailbox_credential_id ??
        "33333333-0000-0000-0000-000000000006",
      status: "queued",
      sent_at: null,
      error_text: null,
      created_at: nowIso(),
      updated_at: nowIso(),
    }));
    outreachStore.sends = [...outreachStore.sends, ...newSends];

    // After a couple of seconds, flip everything terminal. This drives the
    // 5s auto-refresh loop on the detail page so the operator sees the
    // counters move without standing up the real dispatcher.
    setTimeout(() => {
      outreachStore.campaigns = outreachStore.campaigns.map((c) =>
        c.id === id
          ? {
              ...c,
              status: "sent",
              sent_count: newSends.length,
              updated_at: nowIso(),
            }
          : c,
      );
      outreachStore.sends = outreachStore.sends.map((s) =>
        s.campaign_id === id && s.status === "queued"
          ? {
              ...s,
              status: "sent",
              message_id: `<msw-${s.id}@local>`,
              sent_at: nowIso(),
              updated_at: nowIso(),
            }
          : s,
      );
    }, 4000);

    await delay(120);
    return HttpResponse.json(patched);
  }),

  http.post(
    "/api/outreach/campaigns/preview-recipients",
    async ({ request }) => {
      const json = (await request.json()) as Record<string, unknown>;
      const rawLimit = json["limit"];
      const limit = typeof rawLimit === "number" ? rawLimit : 5;
      const items = recipientPool.slice(0, Math.min(Math.max(limit, 0), 10));
      await delay(80);
      return HttpResponse.json({ items, total: recipientPool.length });
    },
  ),

  // ----------------------------------------------------------- suppressions
  http.get("/api/outreach/suppressions", () =>
    HttpResponse.json({ items: outreachStore.suppressions }),
  ),

  http.delete("/api/outreach/suppressions/:email", async ({ params }) => {
    const email = decodeURIComponent(String(params.email));
    outreachStore.suppressions = outreachStore.suppressions.filter(
      (s) => s.recipient_email_normalised !== email,
    );
    await delay(120);
    return HttpResponse.json({ ok: true });
  }),

  // ----------------------------------------------------------- credentials
  http.post("/api/tenant/credentials", async ({ request }) => {
    const json = (await request.json()) as unknown;
    const parsed = IntegrationCredentialBootstrapInputSchema.safeParse(json);
    if (!parsed.success) {
      return apiError(400, "VALIDATION", "Invalid credential payload", {
        issues: parsed.error.issues,
      });
    }
    const credential = parsed.data;
    await delay(120);
    return HttpResponse.json({
      id: "ff000077-0000-0000-0000-000000000077",
      tenant_id: "11111111-1111-1111-1111-111111111111",
      provider_kind: credential.provider_kind,
      credential_kind:
        credential.provider_kind === "carestack" ? "password_grant" : "api_key",
      display_name: credential.display_name ?? null,
      status: "active",
      expires_at: null,
      last_refreshed_at: null,
      mailbox_email: null,
      location_id: null,
      is_default: credential.provider_kind !== "salesforce",
      tags: [],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
  }),

  http.post(
    "/api/tenant/credentials/:id/set-default",
    async () => {
      await delay(80);
      return HttpResponse.json({ ok: true });
    },
  ),

  http.put("/api/tenant/credentials/:id", async () => {
    await delay(80);
    return HttpResponse.json({ ok: true });
  }),

  http.delete("/api/tenant/credentials/:id", async () => {
    await delay(80);
    return HttpResponse.json({ ok: true });
  }),

  // ----------------------------------------------------------- OAuth start
  // Mailbox OAuth connect — only intercepts in MSW dev mode. In a real
  // backend deploy the Next.js rewrite forwards to FastAPI (ENG-131).
  http.get(
    "/api/integrations/:provider/connect/start",
    async ({ params, request }) => {
      const provider = String(params.provider);
      if (provider !== "google_workspace" && provider !== "microsoft_365") {
        // Defer to the existing salesforce/carestack handlers (they're
        // declared elsewhere) or fall through to the Next.js rewrite.
        return HttpResponse.json(
          { error: { code: "UNHANDLED", message: "no mock", details: {} } },
          { status: 404 },
        );
      }
      const url = new URL(request.url);
      const locationId = url.searchParams.get("location_id");
      const displayName = url.searchParams.get("display_name");
      // The real backend returns the provider's authorize URL. In dev we
      // return a self-referential URL that hits a placeholder callback so
      // the operator can complete the round-trip without a real OAuth app.
      const callback = `${url.origin}/settings/tenant?connected=${provider}&mailbox=${
        displayName ?? "demo@" + provider.replace("_", "-") + ".local"
      }`;
      await delay(150);
      return HttpResponse.json({
        authorize_url: callback,
        location_id: locationId,
      });
    },
  ),
];
