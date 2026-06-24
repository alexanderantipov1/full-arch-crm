"use client";

import { useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  type Edge,
  type Node,
} from "@xyflow/react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { buildIdentityMergeGraph, type IdentityNodeData } from "@/lib/graph/identityMerge";
import type { OperationalTimelineEntry, PersonDetail } from "@/lib/api/schemas";

import "@xyflow/react/dist/style.css";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  detail: PersonDetail;
  timelineEvents?: OperationalTimelineEntry[];
}

/**
 * Visualises the identity-merge graph for a single person:
 * - centre node: the canonical `identity.person`
 * - leaves: each `identity.source_link` (Salesforce Lead / CareStack Patient / etc.)
 * - edges: provider → person with confidence-coloured stroke
 *
 * Source data is the same `PersonDetail` payload already rendered by the
 * page; we just hand it to the existing `buildIdentityMergeGraph` builder
 * and let React Flow do the layout.
 */
export function IdentityGraphModal({ open, onOpenChange, detail, timelineEvents }: Props) {
  const { nodes, edges } = useMemo<{ nodes: Node<IdentityNodeData>[]; edges: Edge[] }>(
    () => buildIdentityMergeGraph([detail], timelineEvents),
    [detail, timelineEvents],
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl">
        <DialogHeader>
          <DialogTitle>Identity graph — {detail.summary.display_name}</DialogTitle>
          <DialogDescription>
            One canonical person, every external system and event that knows
            them. Left: source links. Right: timeline events.
          </DialogDescription>
        </DialogHeader>
        <div className="h-[480px] rounded-md border bg-muted/30">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            proOptions={{ hideAttribution: true }}
            nodesDraggable={false}
            nodesConnectable={false}
            edgesFocusable={false}
            elementsSelectable={false}
            zoomOnScroll={true}
            panOnDrag={true}
          >
            <Background gap={16} size={1} />
            <Controls showInteractive={false} />
          </ReactFlow>
        </div>
      </DialogContent>
    </Dialog>
  );
}
