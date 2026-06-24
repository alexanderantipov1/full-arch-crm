import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { apiRequest, queryClient } from "@/lib/queryClient";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
  Square,
  HeartPulse,
  AlertTriangle,
  ArrowUp,
  ArrowRight,
  ArrowDown,
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

interface OrchestrationCycle {
  id: string;
  cycleNumber: number;
  startedAt: string;
  completedAt: string | null;
  episodesThisCycle: number;
  avgScoreThisCycle: number;
  patternsExtracted: number;
  hypothesesGenerated: number;
  selfCheckPassed: boolean;
  nextAction: "continue" | "pause_for_review" | "apply_hypothesis" | "stop";
  reasoning: string;
}

interface CyclesResponse {
  cycles: OrchestrationCycle[];
  isLooping: boolean;
}

interface AgentHealthMetric {
  agentName: string;
  avgScore: number;
  successRate: number;
  health: "strong" | "average" | "weak";
}

interface HealthReport {
  timestamp: string;
  overallHealth: "excellent" | "good" | "degraded" | "critical";
  scoreTrajectory: "improving" | "stable" | "declining";
  agentPerformance: AgentHealthMetric[];
  patternQuality: "rich" | "sparse" | "stale";
  recommendedInterventions: string[];
  aiAnalysis: string;
}

const STATE_KEY = ["/api/simulation/state"];
const CYCLES_KEY = ["/api/simulation/orchestrate/cycles"];

const NEXT_ACTION_VARIANTS: Record<
  OrchestrationCycle["nextAction"],
  "default" | "secondary" | "destructive" | "outline"
> = {
  continue: "secondary",
  apply_hypothesis: "default",
  pause_for_review: "outline",
  stop: "destructive",
};

const HEALTH_VARIANTS: Record<
  HealthReport["overallHealth"],
  "default" | "secondary" | "destructive" | "outline"
> = {
  excellent: "default",
  good: "secondary",
  degraded: "outline",
  critical: "destructive",
};

const HEALTH_COLOR: Record<HealthReport["overallHealth"], string> = {
  excellent: "text-emerald-600 dark:text-emerald-400",
  good: "text-blue-600 dark:text-blue-400",
  degraded: "text-amber-600 dark:text-amber-400",
  critical: "text-destructive",
};

const AGENT_HEALTH_VARIANTS: Record<
  AgentHealthMetric["health"],
  "default" | "secondary" | "outline"
> = {
  strong: "default",
  average: "secondary",
  weak: "outline",
};

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

  // --- Orchestration control state ---
  const [maxCycles, setMaxCycles] = useState(20);
  const [targetScore, setTargetScore] = useState(85);
  const [orchPatientCount, setOrchPatientCount] = useState(20);
  const [health, setHealth] = useState<HealthReport | null>(null);

  const { data: cyclesData } = useQuery<CyclesResponse>({
    queryKey: CYCLES_KEY,
    refetchInterval: (query) => (query.state.data?.isLooping ? 3000 : false),
  });
  const cycles = cyclesData?.cycles ?? [];
  const isLooping = cyclesData?.isLooping ?? false;
  const lastCycle = cycles[cycles.length - 1];

  const invalidateCycles = () =>
    queryClient.invalidateQueries({ queryKey: CYCLES_KEY });

  const runCycleMutation = useMutation({
    mutationFn: async () => {
      const res = await apiRequest(
        "POST",
        "/api/simulation/orchestrate/run-cycle",
        { patientCount: orchPatientCount },
      );
      return res.json();
    },
    onSuccess: () => {
      invalidateCycles();
      invalidate();
    },
  });

  const startLoopMutation = useMutation({
    mutationFn: async () => {
      const res = await apiRequest(
        "POST",
        "/api/simulation/orchestrate/run-loop",
        { maxCycles, targetScore, patientCount: orchPatientCount },
      );
      return res.json();
    },
    onSuccess: () => invalidateCycles(),
  });

  const stopLoopMutation = useMutation({
    mutationFn: async () => {
      const res = await apiRequest(
        "POST",
        "/api/simulation/orchestrate/stop-loop",
      );
      return res.json();
    },
    onSuccess: () => invalidateCycles(),
  });

  const healthCheckMutation = useMutation({
    mutationFn: async () => {
      const res = await apiRequest("GET", "/api/simulation/self-check");
      return res.json();
    },
    onSuccess: (data: HealthReport) => setHealth(data),
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

      <div className="space-y-4">
        <h2 className="text-lg font-semibold">Orchestration Control</h2>

        {/* A. Loop config + controls */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Autonomous Loop</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <label className="space-y-1 text-sm">
                <span className="text-muted-foreground">Max Cycles</span>
                <Input
                  type="number"
                  min={1}
                  max={100}
                  value={maxCycles}
                  onChange={(e) => setMaxCycles(Number(e.target.value))}
                  disabled={isLooping}
                  data-testid="input-max-cycles"
                />
              </label>
              <label className="space-y-1 text-sm">
                <span className="text-muted-foreground">Target Score</span>
                <Input
                  type="number"
                  min={50}
                  max={100}
                  value={targetScore}
                  onChange={(e) => setTargetScore(Number(e.target.value))}
                  disabled={isLooping}
                  data-testid="input-target-score"
                />
              </label>
              <label className="space-y-1 text-sm">
                <span className="text-muted-foreground">Patients / Cycle</span>
                <Input
                  type="number"
                  min={5}
                  max={100}
                  value={orchPatientCount}
                  onChange={(e) => setOrchPatientCount(Number(e.target.value))}
                  disabled={isLooping}
                  data-testid="input-patient-count"
                />
              </label>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="secondary"
                onClick={() => runCycleMutation.mutate()}
                disabled={runCycleMutation.isPending || isLooping}
                data-testid="button-run-cycle"
              >
                <Play className="mr-2 h-4 w-4" />
                {runCycleMutation.isPending ? "Running…" : "Run One Cycle"}
              </Button>
              <Button
                className="bg-emerald-600 text-white hover:bg-emerald-700"
                onClick={() => startLoopMutation.mutate()}
                disabled={startLoopMutation.isPending || isLooping}
                data-testid="button-start-loop"
              >
                <Repeat className="mr-2 h-4 w-4" />
                Start Loop
              </Button>
              <Button
                variant="destructive"
                onClick={() => stopLoopMutation.mutate()}
                disabled={!isLooping || stopLoopMutation.isPending}
                data-testid="button-stop-loop"
              >
                <Square className="mr-2 h-4 w-4" />
                Stop Loop
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* B. Loop status banner */}
        {isLooping && (
          <div
            className="flex items-center gap-3 rounded-md border border-emerald-500/40 bg-emerald-500/10 px-4 py-3 text-sm"
            data-testid="banner-loop-status"
          >
            <span className="relative flex h-3 w-3">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-500 opacity-75" />
              <span className="relative inline-flex h-3 w-3 rounded-full bg-emerald-600" />
            </span>
            <span>
              Loop running — Cycle {cycles.length} | Avg Score{" "}
              <span className={scoreColor(lastCycle?.avgScoreThisCycle ?? 0)}>
                {(lastCycle?.avgScoreThisCycle ?? 0).toFixed(1)}
              </span>
              /100 → Target {targetScore}
            </span>
          </div>
        )}

        {/* C. Cycle history table */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Cycle History</CardTitle>
          </CardHeader>
          <CardContent>
            {cycles.length > 0 ? (
              <div className="max-h-[420px] overflow-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Cycle #</TableHead>
                      <TableHead className="text-right">Avg Score</TableHead>
                      <TableHead className="text-right">Episodes</TableHead>
                      <TableHead className="text-right">Patterns</TableHead>
                      <TableHead className="text-right">Hypotheses</TableHead>
                      <TableHead>Self-Check</TableHead>
                      <TableHead>Next Action</TableHead>
                      <TableHead className="text-right">Duration</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {[...cycles].reverse().map((c) => {
                      const duration =
                        c.completedAt && c.startedAt
                          ? new Date(c.completedAt).getTime() -
                            new Date(c.startedAt).getTime()
                          : 0;
                      return (
                        <TableRow
                          key={c.id}
                          data-testid={`row-cycle-${c.cycleNumber}`}
                        >
                          <TableCell>{c.cycleNumber}</TableCell>
                          <TableCell
                            className={`text-right font-medium ${scoreColor(
                              c.avgScoreThisCycle,
                            )}`}
                          >
                            {c.avgScoreThisCycle.toFixed(1)}
                          </TableCell>
                          <TableCell className="text-right">
                            {c.episodesThisCycle}
                          </TableCell>
                          <TableCell className="text-right">
                            {c.patternsExtracted}
                          </TableCell>
                          <TableCell className="text-right">
                            {c.hypothesesGenerated}
                          </TableCell>
                          <TableCell>
                            {c.selfCheckPassed ? (
                              <span className="text-green-600 dark:text-green-400">
                                ✓
                              </span>
                            ) : (
                              <span className="text-destructive">✗</span>
                            )}
                          </TableCell>
                          <TableCell>
                            <Badge variant={NEXT_ACTION_VARIANTS[c.nextAction]}>
                              {c.nextAction}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-right text-muted-foreground">
                            {duration} ms
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                No cycles yet. Run a cycle or start the loop.
              </p>
            )}
          </CardContent>
        </Card>

        {/* D. Self-check health panel */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0">
            <CardTitle className="text-base">Self-Check Health</CardTitle>
            <Button
              size="sm"
              variant="outline"
              onClick={() => healthCheckMutation.mutate()}
              disabled={healthCheckMutation.isPending}
              data-testid="button-health-check"
            >
              <HeartPulse className="mr-2 h-4 w-4" />
              {healthCheckMutation.isPending ? "Checking…" : "Run Health Check"}
            </Button>
          </CardHeader>
          <CardContent>
            {health ? (
              <div className="space-y-4">
                <div className="flex flex-wrap items-center gap-4">
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">
                      Overall
                    </span>
                    <Badge variant={HEALTH_VARIANTS[health.overallHealth]}>
                      <span className={HEALTH_COLOR[health.overallHealth]}>
                        {health.overallHealth}
                      </span>
                    </Badge>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">
                      Trajectory
                    </span>
                    {health.scoreTrajectory === "improving" ? (
                      <span className="flex items-center gap-1 text-green-600 dark:text-green-400">
                        <ArrowUp className="h-4 w-4" /> improving
                      </span>
                    ) : health.scoreTrajectory === "declining" ? (
                      <span className="flex items-center gap-1 text-destructive">
                        <ArrowDown className="h-4 w-4" /> declining
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-muted-foreground">
                        <ArrowRight className="h-4 w-4" /> stable
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">
                      Patterns
                    </span>
                    <Badge variant="outline">{health.patternQuality}</Badge>
                  </div>
                </div>

                {health.agentPerformance.length > 0 && (
                  <div>
                    <h3 className="mb-2 text-sm font-medium">
                      Agent Performance
                    </h3>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Agent</TableHead>
                          <TableHead>Score</TableHead>
                          <TableHead className="text-right">Success</TableHead>
                          <TableHead>Health</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {health.agentPerformance.map((a) => (
                          <TableRow key={a.agentName}>
                            <TableCell>{a.agentName}</TableCell>
                            <TableCell className="w-[200px]">
                              <div className="flex items-center gap-2">
                                <Progress
                                  value={Math.max(
                                    0,
                                    Math.min(100, a.avgScore),
                                  )}
                                  className="w-28"
                                />
                                <span
                                  className={`text-xs ${scoreColor(a.avgScore)}`}
                                >
                                  {a.avgScore.toFixed(0)}
                                </span>
                              </div>
                            </TableCell>
                            <TableCell className="text-right">
                              {Math.round(a.successRate * 100)}%
                            </TableCell>
                            <TableCell>
                              <Badge
                                variant={AGENT_HEALTH_VARIANTS[a.health]}
                              >
                                {a.health}
                              </Badge>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}

                <div>
                  <h3 className="mb-2 text-sm font-medium">
                    Recommended Interventions
                  </h3>
                  <ul className="space-y-1">
                    {health.recommendedInterventions.map((it, i) => (
                      <li
                        key={i}
                        className="flex items-start gap-2 text-sm text-muted-foreground"
                      >
                        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
                        <span>{it}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                {health.aiAnalysis && (
                  <p className="border-l-2 border-muted pl-3 text-sm italic text-muted-foreground">
                    {health.aiAnalysis}
                  </p>
                )}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                Run a health check to assess simulation health.
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
