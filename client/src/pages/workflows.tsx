import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useRoute } from "wouter";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { format } from "date-fns";
import {
  ArrowLeft,
  CheckCircle2,
  Clock,
  Loader2,
  PlayCircle,
  XCircle,
  AlertCircle,
  GitBranch,
} from "lucide-react";

interface WorkflowInstance {
  id: string;
  principalUserId: string;
  principalEmail: string | null;
  goal: string;
  status: string;
  endReason: string | null;
  finalAnswer: string | null;
  errorMessage: string | null;
  iterationsUsed: number;
  allowedToolNames: string[] | null;
  startedAt: string;
  completedAt: string | null;
}

interface WorkflowStep {
  id: string;
  instanceId: string;
  iteration: number;
  toolName: string;
  input: unknown;
  result: { ok: true; data: unknown } | { ok: false; error: { code: string; message: string } };
  durationMs: number;
  createdAt: string;
}

interface WorkflowDetail extends WorkflowInstance {
  steps: WorkflowStep[];
}

const statusMeta: Record<
  string,
  { label: string; icon: any; cls: string }
> = {
  running: { label: "Running", icon: PlayCircle, cls: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300" },
  completed: { label: "Completed", icon: CheckCircle2, cls: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300" },
  failed: { label: "Failed", icon: XCircle, cls: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300" },
  timeout: { label: "Timed out", icon: Clock, cls: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300" },
  max_iterations: { label: "Max iterations", icon: AlertCircle, cls: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300" },
};

function StatusBadge({ status }: { status: string }) {
  const meta = statusMeta[status] ?? { label: status, icon: AlertCircle, cls: "bg-muted text-muted-foreground" };
  const Icon = meta.icon;
  return (
    <Badge variant="outline" className={`${meta.cls} border-0 gap-1`}>
      <Icon className="h-3 w-3" />
      {meta.label}
    </Badge>
  );
}

// ── List view ──────────────────────────────────────────────────────────
export default function WorkflowsPage() {
  // Wouter route — if we matched /workflows/:id, render the detail page instead.
  const [matchDetail, params] = useRoute("/workflows/:id");
  if (matchDetail && params?.id) {
    return <WorkflowDetailView id={params.id} />;
  }
  return <WorkflowsList />;
}

function WorkflowsList() {
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const queryKey =
    statusFilter === "all"
      ? ["/api/workflows"]
      : ["/api/workflows", `?status=${statusFilter}`];

  const { data: workflows = [], isLoading } = useQuery<WorkflowInstance[]>({
    // Re-poll every 5s so the running queue stays live without a manual refresh.
    refetchInterval: 5000,
    queryKey,
    queryFn: async () => {
      const url =
        statusFilter === "all" ? "/api/workflows" : `/api/workflows?status=${statusFilter}`;
      const res = await fetch(url, { credentials: "include" });
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
  });

  return (
    <div className="container mx-auto p-6 max-w-6xl">
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-2">
            <GitBranch className="h-7 w-7" />
            Agent workflows
          </h1>
          <p className="text-muted-foreground mt-1">
            Multi-step AI agent runs. The list refreshes every 5 seconds so in-flight runs
            stay visible.
          </p>
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-48" data-testid="workflow-status-filter">
            <SelectValue placeholder="All statuses" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="running">Running</SelectItem>
            <SelectItem value="completed">Completed</SelectItem>
            <SelectItem value="failed">Failed</SelectItem>
            <SelectItem value="timeout">Timed out</SelectItem>
            <SelectItem value="max_iterations">Max iterations</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent runs</CardTitle>
          <CardDescription>
            Showing up to 50 by most recent. Click a row to see the full step trail.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="text-muted-foreground py-8 text-center">
              <Loader2 className="h-5 w-5 animate-spin inline-block mr-2" />
              Loading…
            </div>
          ) : workflows.length === 0 ? (
            <div className="text-muted-foreground py-8 text-center">
              No workflows yet. Trigger one via POST /api/workflows/run or the
              <code className="mx-1 px-1 py-0.5 rounded bg-muted text-xs">workflow.run</code>
              MCP tool.
            </div>
          ) : (
            <div className="divide-y">
              {workflows.map((w) => (
                <Link key={w.id} href={`/workflows/${w.id}`}>
                  <a
                    className="block py-3 hover:bg-muted/40 -mx-3 px-3 rounded-md cursor-pointer"
                    data-testid={`workflow-row-${w.id}`}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <StatusBadge status={w.status} />
                          <span className="text-xs text-muted-foreground font-mono">
                            {w.id.slice(0, 8)}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            {w.iterationsUsed} iteration{w.iterationsUsed === 1 ? "" : "s"}
                          </span>
                        </div>
                        <div className="text-sm mt-1 line-clamp-2">{w.goal}</div>
                        <div className="text-xs text-muted-foreground mt-1 space-x-3">
                          <span>by {w.principalEmail ?? w.principalUserId}</span>
                          <span>{format(new Date(w.startedAt), "yyyy-MM-dd HH:mm:ss")}</span>
                        </div>
                      </div>
                    </div>
                  </a>
                </Link>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// ── Detail view ────────────────────────────────────────────────────────
function WorkflowDetailView({ id }: { id: string }) {
  const { data, isLoading } = useQuery<WorkflowDetail>({
    queryKey: [`/api/workflows/${id}`],
    refetchInterval: (q) => {
      // Stop polling once the run is in a terminal state.
      const state = q.state.data?.status;
      if (state && state !== "running") return false;
      return 3000;
    },
  });

  return (
    <div className="container mx-auto p-6 max-w-5xl">
      <Link href="/workflows">
        <a>
          <Button variant="ghost" size="sm" className="mb-4">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to all workflows
          </Button>
        </a>
      </Link>

      {isLoading ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin inline-block mr-2" />
            Loading…
          </CardContent>
        </Card>
      ) : !data ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            Workflow not found
          </CardContent>
        </Card>
      ) : (
        <>
          <Card>
            <CardHeader>
              <div className="flex items-start justify-between gap-4">
                <div>
                  <CardTitle className="font-mono text-sm">{data.id}</CardTitle>
                  <CardDescription className="mt-1 whitespace-pre-wrap">
                    {data.goal}
                  </CardDescription>
                </div>
                <StatusBadge status={data.status} />
              </div>
            </CardHeader>
            <CardContent>
              <dl className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <dt className="text-xs text-muted-foreground">Triggered by</dt>
                  <dd className="font-mono">
                    {data.principalEmail ?? data.principalUserId}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">Started</dt>
                  <dd>{format(new Date(data.startedAt), "yyyy-MM-dd HH:mm:ss")}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">Completed</dt>
                  <dd>
                    {data.completedAt
                      ? format(new Date(data.completedAt), "yyyy-MM-dd HH:mm:ss")
                      : "—"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">Iterations</dt>
                  <dd>{data.iterationsUsed}</dd>
                </div>
                <div className="col-span-2">
                  <dt className="text-xs text-muted-foreground">Allowed tools</dt>
                  <dd className="flex flex-wrap gap-1 mt-1">
                    {(data.allowedToolNames ?? []).map((t) => (
                      <Badge key={t} variant="secondary" className="font-mono text-xs">
                        {t}
                      </Badge>
                    ))}
                  </dd>
                </div>
              </dl>

              {data.finalAnswer && (
                <div className="mt-4 pt-4 border-t">
                  <p className="text-xs text-muted-foreground mb-1">Final answer</p>
                  <pre className="text-sm whitespace-pre-wrap bg-muted/40 rounded p-3">
                    {data.finalAnswer}
                  </pre>
                </div>
              )}

              {data.errorMessage && (
                <div className="mt-4 pt-4 border-t">
                  <p className="text-xs text-red-600 mb-1">Error</p>
                  <pre className="text-sm whitespace-pre-wrap bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 rounded p-3">
                    {data.errorMessage}
                  </pre>
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="mt-6">
            <CardHeader>
              <CardTitle>Step trail</CardTitle>
              <CardDescription>
                Every tool the agent invoked, in order. Input + result is recorded so any
                run can be replayed mentally — or, later, re-run from a checkpoint.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {data.steps.length === 0 ? (
                <p className="text-muted-foreground text-sm">No steps yet.</p>
              ) : (
                <ol className="space-y-3">
                  {data.steps.map((s) => (
                    <li
                      key={s.id}
                      className="rounded-md border p-3 space-y-2"
                      data-testid={`workflow-step-${s.id}`}
                    >
                      <div className="flex items-center gap-2 flex-wrap">
                        <Badge variant="outline">#{s.iteration}</Badge>
                        <span className="font-mono text-sm">{s.toolName}</span>
                        {s.result.ok ? (
                          <Badge variant="outline" className="text-green-700 border-green-700">
                            ok
                          </Badge>
                        ) : (
                          <Badge variant="outline" className="text-red-700 border-red-700">
                            {s.result.error.code}
                          </Badge>
                        )}
                        <span className="text-xs text-muted-foreground ml-auto">
                          {s.durationMs} ms
                        </span>
                      </div>
                      <details className="text-xs">
                        <summary className="cursor-pointer text-muted-foreground">
                          input
                        </summary>
                        <pre className="bg-muted/40 rounded p-2 mt-1 overflow-x-auto">
                          {JSON.stringify(s.input, null, 2)}
                        </pre>
                      </details>
                      <details className="text-xs" open={!s.result.ok}>
                        <summary className="cursor-pointer text-muted-foreground">
                          result
                        </summary>
                        <pre className="bg-muted/40 rounded p-2 mt-1 overflow-x-auto">
                          {JSON.stringify(s.result, null, 2)}
                        </pre>
                      </details>
                    </li>
                  ))}
                </ol>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
