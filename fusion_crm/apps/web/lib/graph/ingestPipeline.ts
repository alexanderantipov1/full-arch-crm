import type { Edge, Node } from "@xyflow/react";

export type PipelineNodeData = {
  label: string;
  sub?: string;
};

const baseStyle = {
  border: "1px solid hsl(214 32% 80%)",
  borderRadius: 8,
  padding: 10,
  background: "white",
  fontSize: 13,
  width: 200,
};

const accentStyle = {
  ...baseStyle,
  border: "2px solid hsl(222 47% 31%)",
  background: "hsl(222 47% 31% / 0.08)",
};

export function buildIngestPipelineGraph(): {
  nodes: Node<PipelineNodeData>[];
  edges: Edge[];
} {
  const nodes: Node<PipelineNodeData>[] = [
    {
      id: "src:salesforce",
      position: { x: 0, y: 0 },
      data: { label: "Salesforce", sub: "OAuth, REST" },
      type: "input",
      style: baseStyle,
    },
    {
      id: "src:carestack",
      position: { x: 0, y: 160 },
      data: { label: "CareStack", sub: "API key" },
      type: "input",
      style: baseStyle,
    },
    {
      id: "ingest:raw",
      position: { x: 280, y: 80 },
      data: { label: "ingest.raw_event", sub: "verbatim JSON" },
      style: accentStyle,
    },
    {
      id: "norm",
      position: { x: 560, y: 80 },
      data: { label: "Normalizer", sub: "W1 / W2 worker" },
      style: baseStyle,
    },
    {
      id: "ops:lead",
      position: { x: 840, y: 0 },
      data: { label: "ops.lead", sub: "+ ops.account" },
      style: accentStyle,
    },
    {
      id: "ops:consult",
      position: { x: 840, y: 160 },
      data: { label: "ops.consultation" },
      style: accentStyle,
    },
    {
      id: "interaction",
      position: { x: 1120, y: 80 },
      data: { label: "interaction.event", sub: "person timeline" },
      style: accentStyle,
    },
    {
      id: "frontend",
      position: { x: 1400, y: 80 },
      data: { label: "Frontend", sub: "/dashboard, /persons/..." },
      type: "output",
      style: baseStyle,
    },
  ];

  const edge = (id: string, source: string, target: string, label?: string): Edge => ({
    id,
    source,
    target,
    label,
    labelStyle: { fontSize: 10, fill: "hsl(215 16% 47%)" },
    style: { stroke: "hsl(215 16% 47%)", strokeWidth: 1.5 },
    animated: true,
  });

  const edges: Edge[] = [
    edge("e1", "src:salesforce", "ingest:raw"),
    edge("e2", "src:carestack", "ingest:raw"),
    edge("e3", "ingest:raw", "norm"),
    edge("e4", "norm", "ops:lead", "Lead"),
    edge("e5", "norm", "ops:consult", "Appointment"),
    edge("e6", "ops:lead", "interaction", "lead_*"),
    edge("e7", "ops:consult", "interaction", "consultation_*"),
    edge("e8", "interaction", "frontend"),
  ];

  return { nodes, edges };
}
