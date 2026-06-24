import { describe, expect, it } from "vitest";
import { buildIngestPipelineGraph } from "@/lib/graph/ingestPipeline";
import { buildIdentityMergeGraph } from "@/lib/graph/identityMerge";
import { personDetails } from "@/lib/msw/fixtures/persons";

describe("graph builders", () => {
  it("ingest pipeline has unique node IDs and connected edges", () => {
    const { nodes, edges } = buildIngestPipelineGraph();
    const ids = new Set(nodes.map((n) => n.id));
    expect(ids.size).toBe(nodes.length);
    for (const e of edges) {
      expect(ids.has(e.source)).toBe(true);
      expect(ids.has(e.target)).toBe(true);
    }
  });

  it("identity merge graph has unique node IDs and connected edges", () => {
    const details = Object.values(personDetails);
    const { nodes, edges } = buildIdentityMergeGraph(details);
    const ids = new Set(nodes.map((n) => n.id));
    expect(ids.size).toBe(nodes.length);
    expect(nodes.length).toBeGreaterThanOrEqual(details.length);
    for (const e of edges) {
      expect(ids.has(e.source)).toBe(true);
      expect(ids.has(e.target)).toBe(true);
    }
  });
});
