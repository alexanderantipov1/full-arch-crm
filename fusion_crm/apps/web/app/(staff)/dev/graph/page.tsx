"use client";

import { useMemo, useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { FlowCanvas } from "@/components/graph/FlowCanvas";
import { buildIngestPipelineGraph } from "@/lib/graph/ingestPipeline";
import { buildIdentityMergeGraph } from "@/lib/graph/identityMerge";
import { personDetails } from "@/lib/msw/fixtures/persons";

type Mode = "pipeline" | "identity";

export default function GraphPage() {
  const [mode, setMode] = useState<Mode>("pipeline");

  const pipeline = useMemo(() => buildIngestPipelineGraph(), []);
  const identity = useMemo(
    () => buildIdentityMergeGraph(Object.values(personDetails)),
    [],
  );

  const graph = mode === "pipeline" ? pipeline : identity;

  return (
    <div className="space-y-6 p-8">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            System graph
          </h1>
          <p className="text-sm text-muted-foreground">
            Visual map of how data moves through Fusion CRM. Powered by React Flow.
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant={mode === "pipeline" ? "default" : "outline"}
            size="sm"
            onClick={() => setMode("pipeline")}
          >
            Ingest pipeline
          </Button>
          <Button
            variant={mode === "identity" ? "default" : "outline"}
            size="sm"
            onClick={() => setMode("identity")}
          >
            Identity merge
          </Button>
        </div>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>
            {mode === "pipeline"
              ? "Ingest pipeline"
              : "Identity merge graph"}
          </CardTitle>
          <CardDescription>
            {mode === "pipeline"
              ? "External providers → ingest.raw_event → normalizer → ops domain → interaction.event → frontend."
              : "External IDs (SF Lead, CareStack Patient) collapsed onto unified person rows. Edge weight = match confidence."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <FlowCanvas nodes={graph.nodes} edges={graph.edges} height={620} />
        </CardContent>
      </Card>
    </div>
  );
}
