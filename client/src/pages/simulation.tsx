import { useQuery, useMutation } from "@tanstack/react-query";
import { apiRequest, queryClient } from "@/lib/queryClient";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Brain,
  Play,
  RotateCcw,
  Download,
  Repeat,
  Check,
  X,
  TrendingUp,
  FlaskConical,
  Lightbulb,
  DollarSign,
  Activity,
} from "lucide-react";

interface SimPatient {
  id: string;
  name: string;
  scenario: string;
}

interface SimEpisode {
  id: string;
  patientId: string;
  agentName: string;
  action: string;
  outcome: string;
  revenueImpact: number;
  timestamp: string;
  score: number;
}

interface SimPattern {
  id: string;
  name: string;
  description: string;
  triggerConditions: string[];
  successRate: number;
  avgRevenueImpact: number;
  sampleSize: number;
  confidence: "low" | "medium" | "high";
}

interface SimHypothesis {
  id: string;
  title: string;
  rationale: string;
  proposedChange: string;
  expectedImpact: string;
  status: "pending" | "approved" | "rejected" | "testing";
  createdAt: string;
}

interface SimEvolution {
  id: string;
  hypothesisId: string;
  change: string;
  baselineScore: number;
  newScore: number;
  implementedAt: string;
}

interface SimState {
  runCount: number;
  totalEpisodes: number;
  avgScore: number;
  totalRevenueSim: number;
  patients: SimPatient[];
  episodes: SimEpisode[];
  patterns: SimPattern[];
  hypotheses: SimHypothesis[];
  evolutions: SimEvolution[];
  lastRunAt: string | null;
  isRunning: boolean;
}

const STATE_KEY = ["/api/simulation/state"];

function scoreColor(score: number): string {
  if (score > 70) return "text-green-600 dark:text-green-400";
  if (score >= 50) return "text-yellow-600 dark:text-yellow-400";
  return "text-destructive";
}

const OUTCOME_VARIANTS: Record<
  string,
  "default" | "secondary" | "destructive" | "outline"
> = {
  converted: "default",
  scheduled: "default",
  referred: "secondary",
  no_response: "outline",
  declined: "destructive",
  lost: "destructive",
};

const CONFIDENCE_VARIANTS: Record<
  string,
  "default" | "secondary" | "outline"
> = {
  high: "default",
  medium: "secondary",
  low: "outline",
};

function currency(n: number): string {
  return `$${Math.round(n).toLocaleString()}`;
}

export default function SimulationPage() {
  const { data: state } = useQuery<SimState>({
    queryKey: STATE_KEY,
    refetchInterval: (query) =>
      query.state.data?.isRunning ? 5000 : false,
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: STATE_KEY });

  const runMutation = useMutation({
    mutationFn: async () => {
      const res = await apiRequest("POST", "/api/simulation/run", {
        patientCount: 20,
      });
      return res.json();
    },
    onSuccess: (data: SimState) => queryClient.setQueryData(STATE_KEY, data),
  });

  const continuousMutation = useMutation({
    mutationFn: async () => {
      const res = await apiRequest("POST", "/api/simulation/run-continuous", {
        iterations: 5,
      });
      return res.json();
    },
    onSuccess: () => invalidate(),
  });

  const resetMutation = useMutation({
    mutationFn: async () => {
      const res = await apiRequest("POST", "/api/simulation/reset");
      return res.json();
    },
    onSuccess: (data: SimState) => queryClient.setQueryData(STATE_KEY, data),
  });

  const decisionMutation = useMutation({
    mutationFn: async ({
      id,
      decision,
    }: {
      id: string;
      decision: "approve" | "reject";
    }) => {
      const res = await apiRequest(
        "POST",
        `/api/simulation/${decision}/${id}`,
      );
      return res.json();
    },
    onSuccess: (data: SimState) => queryClient.setQueryData(STATE_KEY, data),
  });

  const patientName = (id: string) =>
    state?.patients.find((p) => p.id === id)?.name ?? "—";

  const avg = state?.avgScore ?? 0;
  const pendingHypotheses =
    state?.hypotheses.filter((h) => h.status === "pending") ?? [];

  const kpis = [
    { label: "Total Runs", value: state?.runCount ?? 0, icon: Repeat },
    {
      label: "Total Episodes",
      value: state?.totalEpisodes ?? 0,
      icon: Activity,
    },
    {
      label: "Avg Score",
      value: avg.toFixed(1),
      icon: TrendingUp,
      color: scoreColor(avg),
    },
    {
      label: "Simulated Revenue",
      value: currency(state?.totalRevenueSim ?? 0),
      icon: DollarSign,
    },
    {
      label: "Patterns Found",
      value: state?.patterns.length ?? 0,
      icon: FlaskConical,
    },
    {
      label: "Hypotheses",
      value: state?.hypotheses.length ?? 0,
      icon: Lightbulb,
    },
  ];

  return (
    <div className="p-6 space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Brain className="h-8 w-8 text-primary" />
          <div>
            <h1 className="text-2xl font-bold">
              AI Simulation &amp; Self-Improvement
            </h1>
            <p className="text-sm text-muted-foreground">
              Synthetic patient scenarios — no real PHI.
              {state?.lastRunAt
                ? ` Last run ${new Date(state.lastRunAt).toLocaleString()}.`
                : " No runs yet."}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            onClick={() => runMutation.mutate()}
            disabled={runMutation.isPending || state?.isRunning}
            data-testid="button-run-simulation"
          >
            <Play className="mr-2 h-4 w-4" />
            {runMutation.isPending || state?.isRunning
              ? "Running…"
              : "Run Simulation"}
          </Button>
          <Button
            variant="secondary"
            onClick={() => continuousMutation.mutate()}
            disabled={continuousMutation.isPending || state?.isRunning}
          >
            <Repeat className="mr-2 h-4 w-4" />
            Run Continuous (5)
          </Button>
          <Button variant="outline" asChild>
            <a href="/api/simulation/export" download>
              <Download className="mr-2 h-4 w-4" />
              Export
            </a>
          </Button>
          <Button
            variant="outline"
            onClick={() => resetMutation.mutate()}
            disabled={resetMutation.isPending}
          >
            <RotateCcw className="mr-2 h-4 w-4" />
            Reset
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
        {kpis.map((kpi) => (
          <Card key={kpi.label}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {kpi.label}
              </CardTitle>
              <kpi.icon className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div
                className={`text-2xl font-bold ${kpi.color ?? ""}`}
                data-testid={`kpi-${kpi.label}`}
              >
                {kpi.value}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Episodes</CardTitle>
        </CardHeader>
        <CardContent>
          {state && state.episodes.length > 0 ? (
            <div className="max-h-[420px] overflow-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Patient</TableHead>
                    <TableHead>Agent</TableHead>
                    <TableHead>Action</TableHead>
                    <TableHead>Outcome</TableHead>
                    <TableHead className="text-right">Score</TableHead>
                    <TableHead className="text-right">Revenue</TableHead>
                    <TableHead>Time</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {state.episodes.slice(0, 120).map((ep) => (
                    <TableRow key={ep.id}>
                      <TableCell>{patientName(ep.patientId)}</TableCell>
                      <TableCell>{ep.agentName}</TableCell>
                      <TableCell className="max-w-[280px] truncate">
                        {ep.action}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={OUTCOME_VARIANTS[ep.outcome] ?? "outline"}
                        >
                          {ep.outcome}
                        </Badge>
                      </TableCell>
                      <TableCell
                        className={`text-right font-medium ${scoreColor(ep.score)}`}
                      >
                        {ep.score}
                      </TableCell>
                      <TableCell className="text-right">
                        {currency(ep.revenueImpact)}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {new Date(ep.timestamp).toLocaleTimeString()}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              No episodes yet. Run a simulation to generate data.
            </p>
          )}
        </CardContent>
      </Card>

      <div>
        <h2 className="mb-3 text-lg font-semibold">Learned Patterns</h2>
        {state && state.patterns.length > 0 ? (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {state.patterns.map((pattern) => (
              <Card key={pattern.id}>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between gap-2">
                    <CardTitle className="text-base">{pattern.name}</CardTitle>
                    <Badge
                      variant={
                        CONFIDENCE_VARIANTS[pattern.confidence] ?? "outline"
                      }
                    >
                      {pattern.confidence}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent className="space-y-2">
                  <p className="text-sm text-muted-foreground">
                    {pattern.description}
                  </p>
                  <div className="flex items-center justify-between text-sm">
                    <span>Success rate</span>
                    <span className="font-medium">
                      {Math.round(pattern.successRate * 100)}%
                    </span>
                  </div>
                  <Progress value={pattern.successRate * 100} />
                  <div className="flex justify-between text-xs text-muted-foreground">
                    <span>n = {pattern.sampleSize}</span>
                    <span>avg {currency(pattern.avgRevenueImpact)}</span>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            No patterns extracted yet.
          </p>
        )}
      </div>

      <div>
        <h2 className="mb-3 text-lg font-semibold">
          Improvement Hypotheses
          {pendingHypotheses.length > 0
            ? ` (${pendingHypotheses.length} pending)`
            : ""}
        </h2>
        {state && state.hypotheses.length > 0 ? (
          <div className="space-y-3">
            {state.hypotheses.map((h) => (
              <Card key={h.id}>
                <CardContent className="flex flex-col gap-3 pt-6 md:flex-row md:items-start md:justify-between">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{h.title}</span>
                      <Badge
                        variant={
                          h.status === "approved"
                            ? "default"
                            : h.status === "rejected"
                              ? "destructive"
                              : "outline"
                        }
                      >
                        {h.status}
                      </Badge>
                    </div>
                    <p className="text-sm text-muted-foreground">
                      {h.rationale}
                    </p>
                    <p className="text-sm">
                      <span className="font-medium">Proposed: </span>
                      {h.proposedChange}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      {h.expectedImpact}
                    </p>
                  </div>
                  {h.status === "pending" && (
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        onClick={() =>
                          decisionMutation.mutate({
                            id: h.id,
                            decision: "approve",
                          })
                        }
                        disabled={decisionMutation.isPending}
                        data-testid={`button-approve-${h.id}`}
                      >
                        <Check className="mr-1 h-4 w-4" />
                        Approve
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() =>
                          decisionMutation.mutate({
                            id: h.id,
                            decision: "reject",
                          })
                        }
                        disabled={decisionMutation.isPending}
                      >
                        <X className="mr-1 h-4 w-4" />
                        Reject
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            No hypotheses generated yet.
          </p>
        )}
      </div>

      <div>
        <h2 className="mb-3 text-lg font-semibold">Evolutions</h2>
        {state && state.evolutions.length > 0 ? (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {state.evolutions.map((evo) => (
              <Card key={evo.id}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">{evo.change}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  <div className="flex items-center gap-2 text-sm">
                    <span className={scoreColor(evo.baselineScore)}>
                      {evo.baselineScore.toFixed(1)}
                    </span>
                    <TrendingUp className="h-4 w-4 text-muted-foreground" />
                    <span className={scoreColor(evo.newScore)}>
                      {evo.newScore.toFixed(1)}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      (+{(evo.newScore - evo.baselineScore).toFixed(1)})
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {new Date(evo.implementedAt).toLocaleString()}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            No evolutions yet. Approve a hypothesis to record one.
          </p>
        )}
      </div>
    </div>
  );
}
