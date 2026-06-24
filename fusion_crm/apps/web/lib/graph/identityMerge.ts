import type { Edge, Node } from "@xyflow/react";
import type {
  OperationalTimelineEntry,
  PersonDetail,
} from "@/lib/api/schemas";

export type IdentityNodeData = {
  label: string;
  sub?: string;
  kind: "person" | "provider" | "event";
  provider?: string;
  eventKind?: string;
  dataClass?: string;
};

const PROVIDER_STYLE: Record<
  string,
  { bg: string; border: string; accent: string }
> = {
  salesforce: {
    bg: "hsl(217 91% 60% / 0.06)",
    border: "hsl(217 91% 60% / 0.4)",
    accent: "hsl(217 91% 60%)",
  },
  carestack: {
    bg: "hsl(160 84% 39% / 0.06)",
    border: "hsl(160 84% 39% / 0.4)",
    accent: "hsl(160 84% 39%)",
  },
};

const DEFAULT_STYLE = {
  bg: "hsl(215 16% 47% / 0.06)",
  border: "hsl(215 16% 47% / 0.4)",
  accent: "hsl(215 16% 47%)",
};

const KIND_LABELS: Record<string, string> = {
  lead_created: "Lead created",
  lead_updated: "Lead updated",
  consultation_scheduled: "Consultation scheduled",
  consultation_created: "Consultation",
  consultation_rescheduled: "Rescheduled",
  consultation_cancelled: "Cancelled",
  consultation_completed: "Consultation completed",
  consultation_no_show: "No-show",
  task_created: "Task created",
  task_completed: "Task completed",
  call_logged: "Call logged",
  call_reference_found: "Call reference",
  case_opened: "Case opened",
  case_closed: "Case closed",
  opportunity_created: "Opportunity",
  opportunity_won: "Opportunity won",
  opportunity_lost: "Opportunity lost",
  treatment_proposed: "Treatment proposed",
  treatment_completed: "Treatment completed",
  invoice_created: "Invoice",
};

function kindLabel(kind: string): string {
  return KIND_LABELS[kind] ?? kind.replace(/_/g, " ");
}

function providerLabel(provider: string): string {
  if (provider === "salesforce") return "Salesforce";
  if (provider === "carestack") return "CareStack";
  return provider;
}

export function buildIdentityMergeGraph(
  details: PersonDetail[],
  timelineEvents?: OperationalTimelineEntry[],
): { nodes: Node<IdentityNodeData>[]; edges: Edge[] } {
  const nodes: Node<IdentityNodeData>[] = [];
  const edges: Edge[] = [];

  const firstDetail = details[0];
  if (!firstDetail) return { nodes, edges };

  const personId = `person:${firstDetail.summary.id}`;

  nodes.push({
    id: personId,
    position: { x: 300, y: 0 },
    data: {
      label: firstDetail.summary.display_name,
      sub: firstDetail.summary.email ?? undefined,
      kind: "person",
    },
    type: "default",
    style: {
      background: "hsl(222 47% 31% / 0.08)",
      border: "2px solid hsl(222 47% 31%)",
      borderRadius: 8,
      padding: 10,
      width: 240,
      textAlign: "center" as const,
    },
  });

  const providerGroups = new Map<
    string,
    {
      sourceLinks: typeof firstDetail.source_links;
      events: { kind: string; count: number }[];
    }
  >();

  for (const sl of firstDetail.source_links) {
    const existing = providerGroups.get(sl.provider) ?? {
      sourceLinks: [],
      events: [],
    };
    existing.sourceLinks.push(sl);
    providerGroups.set(sl.provider, existing);
  }

  if (timelineEvents) {
    const eventsByProviderKind = new Map<string, number>();
    for (const ev of timelineEvents) {
      const key = `${ev.source_provider}::${ev.kind}`;
      eventsByProviderKind.set(key, (eventsByProviderKind.get(key) ?? 0) + 1);
    }
    for (const [key, count] of eventsByProviderKind) {
      const [provider, kind] = key.split("::");
      if (!provider || !kind) continue;
      const existing = providerGroups.get(provider) ?? {
        sourceLinks: [],
        events: [],
      };
      existing.events.push({ kind, count });
      providerGroups.set(provider, existing);
    }
  }

  const providers = [...providerGroups.keys()];
  const totalProviders = providers.length;
  const spacing = 400;
  const startX = 300 - ((totalProviders - 1) * spacing) / 2;

  providers.forEach((provider, pIdx) => {
    const group = providerGroups.get(provider);
    if (!group) return;
    const style = PROVIDER_STYLE[provider] ?? DEFAULT_STYLE;
    const providerNodeId = `provider:${provider}`;
    const px = startX + pIdx * spacing;
    const py = 140;

    nodes.push({
      id: providerNodeId,
      position: { x: px, y: py },
      data: {
        label: providerLabel(provider),
        sub: `${group.sourceLinks.length} link${group.sourceLinks.length !== 1 ? "s" : ""}, ${group.events.reduce((s, e) => s + e.count, 0)} events`,
        kind: "provider",
        provider,
      },
      type: "default",
      style: {
        background: style.bg,
        border: `2px solid ${style.border}`,
        borderRadius: 8,
        padding: 8,
        width: 220,
        textAlign: "center" as const,
        fontWeight: 600,
      },
    });

    const confidence =
      group.sourceLinks.length > 0
        ? Math.max(...group.sourceLinks.map((sl) => sl.confidence))
        : 1;
    edges.push({
      id: `e:${providerNodeId}`,
      source: personId,
      target: providerNodeId,
      label: confidence < 1 ? confidence.toFixed(2) : undefined,
      labelStyle: { fontSize: 10, fill: "hsl(215 16% 47%)" },
      style: {
        stroke: style.accent,
        strokeWidth: 2,
      },
    });

    let childRow = 0;

    for (const sl of group.sourceLinks) {
      const linkId = `link:${provider}:${sl.external_id}`;
      nodes.push({
        id: linkId,
        position: { x: px - 20, y: py + 90 + childRow * 56 },
        data: {
          label: `${sl.entity}: ${sl.external_id}`,
          kind: "provider",
          provider,
        },
        type: "default",
        style: {
          background: "white",
          border: `1px solid ${style.border}`,
          borderRadius: 4,
          padding: 4,
          width: 200,
          fontSize: 10,
        },
      });
      edges.push({
        id: `e:${linkId}`,
        source: providerNodeId,
        target: linkId,
        style: { stroke: style.border, strokeWidth: 1 },
      });
      childRow++;
    }

    for (const ev of group.events) {
      const eventId = `event:${provider}:${ev.kind}`;
      nodes.push({
        id: eventId,
        position: { x: px - 20, y: py + 90 + childRow * 56 },
        data: {
          label: `${kindLabel(ev.kind)}${ev.count > 1 ? ` (${ev.count})` : ""}`,
          kind: "event",
          provider,
          eventKind: ev.kind,
        },
        type: "default",
        style: {
          background: style.bg,
          border: `1px dashed ${style.border}`,
          borderRadius: 4,
          padding: 4,
          width: 200,
          fontSize: 10,
        },
      });
      edges.push({
        id: `e:${eventId}`,
        source: providerNodeId,
        target: eventId,
        style: {
          stroke: style.border,
          strokeWidth: 1,
          strokeDasharray: "4 2",
        },
      });
      childRow++;
    }
  });

  return { nodes, edges };
}
