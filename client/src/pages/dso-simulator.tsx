import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { apiRequest } from "@/lib/queryClient";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Network, Play, DollarSign, TrendingUp, Building2, Lightbulb } from "lucide-react";

type PracticeArchetype =
  | "solo_gp"
  | "implant_specialist"
  | "dso_satellite"
  | "multi_specialty"
  | "startup_location";

interface PracticeProfile {
  archetype: PracticeArchetype;
  name: string;
  chairCount: number;
  annualProductionTarget: number;
  insuranceMix: Record<string, number>;
  scenarioBias: Record<string, number>;
  staffing: { doctors: number; hygienists: number; frontDesk: number };
  dsoGroup: string | null;
}

interface LocationKPIs {
  newPatientConversionRate: number;
  treatmentAcceptanceRate: number;
  recallComplianceRate: number;
  revenuePerChair: number;
  avgTreatmentValue: number;
  insuranceDenialRate: number;
  dsoReadinessScore: number;
}

interface LocationSimResult {
  locationId: string;
  profile: PracticeProfile;
  episodeCount: number;
  avgScore: number;
  conversionRate: number;
  projectedAnnualRevenue: number;
  patientAcquisitionCost: number;
  topPerformingAgent: string;
  weakestAgent: string;
  kpis: LocationKPIs;
}

interface DSONetworkResult {
  runId: string;
  runAt: string;
  locations: LocationSimResult[];
  networkSummary: {
    totalProjectedRevenue: number;
    bestPerformingArchetype: PracticeArchetype;
    worstPerformingArchetype: PracticeArchetype;
    avgNetworkScore: number;
    dsoExpansionRecommendation: string;
    optimalExpansionArchetype: PracticeArchetype;
  };
}

const ARCHETYPES: { value: PracticeArchetype; label: string }[] = [
  { value: "solo_gp", label: "Solo GP Practice" },
  { value: "implant_specialist", label: "Implant Specialist" },
  { value: "dso_satellite", label: "DSO Satellite Location" },
  { value: "multi_specialty", label: "Multi-Specialty Group" },
  { value: "startup_location", label: "New DSO Expansion Site" },
];

function scoreColor(score: number): string {
  if (score > 70) return "text-green-600 dark:text-green-400";
  if (score >= 50) return "text-yellow-600 dark:text-yellow-400";
  return "text-destructive";
}

function currency(n: number): string {
  return `$${Math.round(n).toLocaleString()}`;
}

function pct(n: number): string {
  return `${Math.round(n * 100)}%`;
}

export default function DSOSimulatorPage() {
  const [selected, setSelected] = useState<PracticeArchetype[]>(
    ARCHETYPES.map((a) => a.value),
  );
  const [patientCount, setPatientCount] = useState(15);

  const runMutation = useMutation({
    mutationFn: async (): Promise<DSONetworkResult> => {
      const res = await apiRequest("POST", "/api/simulation/dso/run-network", {
        archetypes: selected,
        patientCount,
      });
      return res.json();
    },
  });

  const result = runMutation.data;
  const toggle = (a: PracticeArchetype) =>
    setSelected((prev) =>
      prev.includes(a) ? prev.filter((x) => x !== a) : [...prev, a],
    );

  return (
    <div className="p-6 space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Network className="h-8 w-8 text-primary" />
          <div>
            <h1 className="text-2xl font-bold">DSO Network Simulator</h1>
            <p className="text-sm text-muted-foreground">
              Run all practice archetypes simultaneously — synthetic data, no
              real PHI.
              {result
                ? ` Last run ${new Date(result.runAt).toLocaleString()}.`
                : ""}
            </p>
          </div>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Network Configuration</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {ARCHETYPES.map((a) => (
              <label
                key={a.value}
                className="flex items-center gap-2 text-sm"
                data-testid={`checkbox-archetype-${a.value}`}
              >
                <Checkbox
                  checked={selected.includes(a.value)}
                  onCheckedChange={() => toggle(a.value)}
                />
                {a.label}
              </label>
            ))}
          </div>
          <div className="flex flex-wrap items-end gap-4">
            <div className="space-y-1">
              <label className="text-sm font-medium" htmlFor="patient-count">
                Patients per location
              </label>
              <Input
                id="patient-count"
                type="number"
                min={5}
                max={50}
                value={patientCount}
                onChange={(e) =>
                  setPatientCount(
                    Math.max(5, Math.min(50, Number(e.target.value) || 5)),
                  )
                }
                className="w-32"
                data-testid="input-patient-count"
              />
            </div>
            <Button
              onClick={() => runMutation.mutate()}
              disabled={runMutation.isPending || selected.length === 0}
              data-testid="button-run-network"
            >
              <Play className="mr-2 h-4 w-4" />
              {runMutation.isPending ? "Running…" : "Run Network Simulation"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {runMutation.isError && (
        <p className="text-sm text-destructive">
          Simulation failed. Please try again.
        </p>
      )}

      {result && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Network Summary</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <div>
                  <p className="text-sm text-muted-foreground">
                    Total Projected Revenue
                  </p>
                  <p
                    className="text-3xl font-bold"
                    data-testid="text-total-revenue"
                  >
                    {currency(result.networkSummary.totalProjectedRevenue)}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">
                    Avg Network Score
                  </p>
                  <p
                    className={`text-3xl font-bold ${scoreColor(result.networkSummary.avgNetworkScore)}`}
                  >
                    {result.networkSummary.avgNetworkScore.toFixed(1)}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">
                    Best Archetype
                  </p>
                  <Badge className="mt-2 text-sm">
                    {
                      ARCHETYPES.find(
                        (a) =>
                          a.value ===
                          result.networkSummary.bestPerformingArchetype,
                      )?.label
                    }
                  </Badge>
                </div>
              </div>
              <div className="flex items-start gap-3 rounded-md border border-primary/30 bg-primary/5 p-4">
                <Lightbulb className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
                <div>
                  <p className="text-sm font-medium">Expansion Recommendation</p>
                  <p className="text-sm text-muted-foreground">
                    {result.networkSummary.dsoExpansionRecommendation}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Location Comparison</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Practice Type</TableHead>
                      <TableHead className="text-right">Score</TableHead>
                      <TableHead className="text-right">Conv Rate</TableHead>
                      <TableHead className="text-right">Revenue/Chair</TableHead>
                      <TableHead className="text-right">DSO Readiness</TableHead>
                      <TableHead>Top Agent</TableHead>
                      <TableHead>Weakest Agent</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {result.locations.map((loc) => (
                      <TableRow key={loc.locationId}>
                        <TableCell className="font-medium">
                          {loc.profile.name}
                        </TableCell>
                        <TableCell
                          className={`text-right font-medium ${scoreColor(loc.avgScore)}`}
                        >
                          {loc.avgScore.toFixed(1)}
                        </TableCell>
                        <TableCell className="text-right">
                          {pct(loc.conversionRate)}
                        </TableCell>
                        <TableCell className="text-right">
                          {currency(loc.kpis.revenuePerChair)}
                        </TableCell>
                        <TableCell
                          className={`text-right font-medium ${scoreColor(loc.kpis.dsoReadinessScore)}`}
                        >
                          {loc.kpis.dsoReadinessScore}
                        </TableCell>
                        <TableCell>{loc.topPerformingAgent}</TableCell>
                        <TableCell className="text-muted-foreground">
                          {loc.weakestAgent}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>

          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {result.locations.map((loc) => (
              <Card key={loc.locationId}>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between gap-2">
                    <CardTitle className="text-base">
                      {loc.profile.name}
                    </CardTitle>
                    <Building2 className="h-4 w-4 text-muted-foreground" />
                  </div>
                  {loc.profile.dsoGroup && (
                    <Badge variant="outline" className="w-fit">
                      {loc.profile.dsoGroup}
                    </Badge>
                  )}
                </CardHeader>
                <CardContent className="space-y-2 text-sm">
                  <KpiRow
                    label="Projected Revenue"
                    value={currency(loc.projectedAnnualRevenue)}
                    icon={DollarSign}
                  />
                  <KpiRow
                    label="New Patient Conv."
                    value={pct(loc.kpis.newPatientConversionRate)}
                  />
                  <KpiRow
                    label="Treatment Accept."
                    value={pct(loc.kpis.treatmentAcceptanceRate)}
                  />
                  <KpiRow
                    label="Recall Compliance"
                    value={pct(loc.kpis.recallComplianceRate)}
                  />
                  <KpiRow
                    label="Insurance Denial"
                    value={pct(loc.kpis.insuranceDenialRate)}
                  />
                  <KpiRow
                    label="Avg Treatment Value"
                    value={currency(loc.kpis.avgTreatmentValue)}
                  />
                  <KpiRow
                    label="Patient Acq. Cost"
                    value={currency(loc.patientAcquisitionCost)}
                  />
                  <KpiRow
                    label="DSO Readiness"
                    value={`${loc.kpis.dsoReadinessScore}/100`}
                  />
                  <KpiRow
                    label="Chairs / Episodes"
                    value={`${loc.profile.chairCount} / ${loc.episodeCount}`}
                  />
                </CardContent>
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function KpiRow({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: string;
  icon?: typeof TrendingUp;
}) {
  return (
    <div className="flex items-center justify-between">
      <span className="flex items-center gap-1.5 text-muted-foreground">
        {Icon && <Icon className="h-3.5 w-3.5" />}
        {label}
      </span>
      <span className="font-medium">{value}</span>
    </div>
  );
}
