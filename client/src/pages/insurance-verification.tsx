import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useLocation } from "wouter";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { useToast } from "@/hooks/use-toast";
import { apiRequest } from "@/lib/queryClient";
import {
  Shield, Search, CheckCircle2, XCircle, AlertTriangle, Clock,
  Loader2, User, Calendar, DollarSign, RefreshCw, FileCheck,
  ChevronDown, ChevronUp, Zap, History,
} from "lucide-react";

interface Patient { id: number; firstName: string; lastName: string; dateOfBirth: string; }

interface InsuranceRecord {
  id: number; patientId: number; providerName: string | null; insuranceType: string | null;
  policyNumber: string | null; groupNumber: string | null; subscriberName: string | null;
  effectiveDate: string | null; terminationDate: string | null;
  annualMaximum: string | null; deductible: string | null; remainingBenefit: string | null;
}

interface CoverageDetails {
  planName?: string; planType?: string; groupNumber?: string; subscriberId?: string;
  subscriberName?: string; effectiveDate?: string; terminationDate?: string | null;
  networkStatus?: string; deductibleIndividual?: number; deductibleMet?: number;
  deductibleRemaining?: number; deductibleFamily?: number; outOfPocketMax?: number;
  oopMet?: number; oopRemaining?: number; annualMaximum?: number; benefitsRemaining?: number;
  copayPreventive?: number; copayBasic?: number; copayMajor?: number; copayOrtho?: number;
  coveredServices?: string[]; waitingPeriods?: { major?: string | null; orthodontics?: string | null };
  priorAuthRequired?: string[]; notes?: string;
}

interface EligibilityCheck {
  id: number; patientId: number; checkDate: string; status: string;
  eligibilityStatus: string | null; coverageDetails: CoverageDetails | null;
  benefitsRemaining: string | null; deductibleMet: string | null;
  effectiveDate: string | null; terminationDate: string | null;
  cached?: boolean; patientName?: string;
}

interface VerificationStats {
  checksToday: number; activeVerifications: number; eligibleRate: number; avgResponseTime: string;
}

const fmt$ = (v: number | string | null | undefined) => {
  if (v == null || v === "") return "$0";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 0 }).format(Number(v));
};

const fmtDate = (d: string | null | undefined) =>
  d ? new Date(d).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : "N/A";

function StatusBadge({ status }: { status: string | null }) {
  if (status === "active") return <Badge className="bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300"><CheckCircle2 className="h-3 w-3 mr-1" />Active</Badge>;
  if (status === "inactive" || status === "terminated") return <Badge variant="destructive"><XCircle className="h-3 w-3 mr-1" />Inactive</Badge>;
  return <Badge variant="outline"><AlertTriangle className="h-3 w-3 mr-1" />{status || "Unknown"}</Badge>;
}

function DeductibleBar({ label, met = 0, total = 0 }: { label: string; met?: number; total?: number }) {
  const pct = total > 0 ? Math.min(100, Math.round((met / total) * 100)) : 0;
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-medium">{fmt$(met)} / {fmt$(total)}</span>
      </div>
      <Progress value={pct} className="h-1.5" />
      <p className="text-[10px] text-muted-foreground text-right">{fmt$(total - met)} remaining</p>
    </div>
  );
}

function EligibilityResultCard({ result, onRefresh, refreshing }: {
  result: EligibilityCheck; onRefresh?: () => void; refreshing?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const cd = result.coverageDetails || {} as CoverageDetails;

  return (
    <Card className={`border-2 ${result.eligibilityStatus === "active" ? "border-green-200 dark:border-green-800" : "border-red-200 dark:border-red-800"}`}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <StatusBadge status={result.eligibilityStatus} />
              {result.cached && (
                <Badge variant="secondary" className="text-[10px]">
                  <Clock className="h-2.5 w-2.5 mr-1" />Cached
                </Badge>
              )}
            </div>
            <p className="text-sm font-semibold">{cd.planName || "Plan"}</p>
            <p className="text-xs text-muted-foreground">
              {cd.planType} · {cd.networkStatus || "In-Network"} · Checked {fmtDate(result.checkDate)}
            </p>
          </div>
          {onRefresh && (
            <Button variant="ghost" size="sm" onClick={onRefresh} disabled={refreshing} data-testid="button-force-refresh">
              <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`} />
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
          <div><span className="text-muted-foreground text-xs">Subscriber ID</span><p className="font-medium">{cd.subscriberId || "N/A"}</p></div>
          <div><span className="text-muted-foreground text-xs">Group Number</span><p className="font-medium">{cd.groupNumber || "N/A"}</p></div>
          <div><span className="text-muted-foreground text-xs">Effective Date</span><p className="font-medium">{fmtDate(result.effectiveDate || cd.effectiveDate)}</p></div>
          <div><span className="text-muted-foreground text-xs">Term Date</span><p className="font-medium">{result.terminationDate ? fmtDate(result.terminationDate) : "None"}</p></div>
        </div>

        <Separator />

        <div className="space-y-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Benefits</p>
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-lg bg-green-50 dark:bg-green-950/30 p-3 text-center">
              <p className="text-xs text-muted-foreground">Annual Maximum</p>
              <p className="text-lg font-bold text-green-700 dark:text-green-300" data-testid="text-annual-max">{fmt$(cd.annualMaximum)}</p>
            </div>
            <div className="rounded-lg bg-blue-50 dark:bg-blue-950/30 p-3 text-center">
              <p className="text-xs text-muted-foreground">Benefits Remaining</p>
              <p className="text-lg font-bold text-blue-700 dark:text-blue-300" data-testid="text-benefits-remaining">{fmt$(cd.benefitsRemaining ?? result.benefitsRemaining)}</p>
            </div>
          </div>

          <DeductibleBar label="Individual Deductible" met={cd.deductibleMet ?? 0} total={cd.deductibleIndividual ?? 0} />
          <DeductibleBar label="Out-of-Pocket Max" met={cd.oopMet ?? 0} total={cd.outOfPocketMax ?? 0} />
        </div>

        <button
          onClick={() => setExpanded(e => !e)}
          className="flex items-center gap-1 text-xs text-primary hover:underline"
          data-testid="button-toggle-details"
        >
          {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          {expanded ? "Hide" : "Show"} co-pays & covered services
        </button>

        {expanded && (
          <div className="space-y-4 pt-1">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {[
                { label: "Preventive", value: cd.copayPreventive },
                { label: "Basic", value: cd.copayBasic },
                { label: "Major", value: cd.copayMajor },
                { label: "Ortho", value: cd.copayOrtho },
              ].map(({ label, value }) => (
                <div key={label} className="rounded-lg border p-2 text-center">
                  <p className="text-[10px] text-muted-foreground">{label}</p>
                  <p className="font-semibold text-sm">{value != null ? `${value}%` : "N/A"}</p>
                  <p className="text-[10px] text-muted-foreground">co-ins</p>
                </div>
              ))}
            </div>

            {cd.coveredServices && cd.coveredServices.length > 0 && (
              <div className="space-y-1">
                <p className="text-xs font-medium text-muted-foreground">Covered Services</p>
                <div className="flex flex-wrap gap-1">
                  {cd.coveredServices.map(s => (
                    <Badge key={s} variant="secondary" className="text-[10px] capitalize">{s.replace(/_/g, " ")}</Badge>
                  ))}
                </div>
              </div>
            )}

            {cd.priorAuthRequired && cd.priorAuthRequired.length > 0 && (
              <div className="rounded-md border border-yellow-200 dark:border-yellow-800 bg-yellow-50 dark:bg-yellow-950/20 p-2">
                <p className="text-xs font-medium text-yellow-800 dark:text-yellow-300">Prior Auth Required: {cd.priorAuthRequired.map(s => s.replace(/_/g, " ")).join(", ")}</p>
              </div>
            )}

            {cd.notes && <p className="text-xs text-muted-foreground italic">{cd.notes}</p>}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function InsuranceVerificationPage() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [location] = useLocation();
  const [selectedPatient, setSelectedPatient] = useState<string>("");
  const [batchProgress, setBatchProgress] = useState<{ done: number; total: number; results: any[] } | null>(null);
  const [batchRunning, setBatchRunning] = useState(false);

  // Pre-select patient from URL query param (e.g. clicking eligibility badge on patient profile)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const pid = params.get("patientId");
    if (pid) setSelectedPatient(pid);
  }, [location]);

  const { data: patients } = useQuery<Patient[]>({ queryKey: ["/api/patients"] });

  const { data: stats } = useQuery<VerificationStats>({
    queryKey: ["/api/eligibility/stats"],
  });

  const { data: recentChecks, isLoading: checksLoading } = useQuery<EligibilityCheck[]>({
    queryKey: ["/api/eligibility/recent"],
  });

  const { data: patientHistory, isLoading: historyLoading } = useQuery<EligibilityCheck[]>({
    queryKey: ["/api/eligibility/patient", selectedPatient],
    queryFn: () => fetch(`/api/eligibility/patient/${selectedPatient}`, { credentials: "include" }).then(r => r.json()),
    enabled: !!selectedPatient,
  });

  const { data: patientInsurance } = useQuery<InsuranceRecord[]>({
    queryKey: ["/api/patients", selectedPatient, "insurance"],
    queryFn: () => fetch(`/api/patients/${selectedPatient}/insurance`, { credentials: "include" }).then(r => r.json()),
    enabled: !!selectedPatient,
  });
  const primaryInsurance = patientInsurance?.[0];

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ["/api/eligibility/stats"] });
    queryClient.invalidateQueries({ queryKey: ["/api/eligibility/recent"] });
    if (selectedPatient) {
      queryClient.invalidateQueries({ queryKey: ["/api/eligibility/patient", selectedPatient] });
    }
  };

  const verifyMut = useMutation({
    mutationFn: ({ patientId, forceRefresh }: { patientId: number; forceRefresh?: boolean }) =>
      apiRequest("POST", "/api/eligibility/check", { patientId, forceRefresh }).then(r => r.json()),
    onSuccess: () => {
      invalidateAll();
      queryClient.invalidateQueries({ queryKey: ["/api/eligibility/patient", selectedPatient] });
      toast({ title: "Eligibility Check Complete" });
    },
    onError: () => toast({ title: "Verification failed", variant: "destructive" }),
  });

  const runBatchVerify = async () => {
    setBatchRunning(true);
    setBatchProgress({ done: 0, total: 0, results: [] });
    try {
      const data = await apiRequest("POST", "/api/eligibility/batch-tomorrow", {}).then(r => r.json());
      setBatchProgress({ done: data.checked, total: data.checked, results: data.results ?? [] });
      invalidateAll();
      const active = (data.results ?? []).filter((r: any) => r.eligibilityStatus === "active").length;
      const issues = data.checked - active;
      toast({ title: `Batch Verify Complete — ${active} active, ${issues} need review` });
    } catch {
      toast({ title: "Batch verify failed", variant: "destructive" });
    } finally {
      setBatchRunning(false);
    }
  };

  const latestResult = patientHistory?.[0];
  const selectedPatientName = patients?.find(p => p.id.toString() === selectedPatient);

  return (
    <div className="p-6 space-y-6 overflow-y-auto max-h-[calc(100vh-80px)]">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold" data-testid="text-page-title">Insurance Eligibility</h1>
          <p className="text-muted-foreground">AI-powered real-time coverage verification</p>
        </div>
        <Button
          variant="outline"
          onClick={runBatchVerify}
          disabled={batchRunning}
          data-testid="button-batch-verify"
        >
          {batchRunning ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Zap className="mr-2 h-4 w-4" />}
          Verify Tomorrow's Patients
        </Button>
      </div>

      {/* Batch progress + results */}
      {(batchRunning || batchProgress) && (
        <Card className="border-blue-200 dark:border-blue-800" data-testid="card-batch-results">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Zap className="h-4 w-4 text-blue-500" />
              {batchRunning
                ? "Running Batch Verification…"
                : `Batch Complete — ${batchProgress?.done ?? 0} patients checked`}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {batchRunning && (
              <div className="space-y-1" data-testid="batch-progress-bar">
                <Progress value={undefined} className="h-2 animate-pulse" />
                <p className="text-xs text-muted-foreground">Checking eligibility for tomorrow's appointments…</p>
              </div>
            )}
            {!batchRunning && batchProgress && batchProgress.results.length > 0 && (
              <>
                <div className="space-y-1">
                  <div className="flex justify-between text-xs text-muted-foreground">
                    <span>Completed</span>
                    <span>{batchProgress.done} patients</span>
                  </div>
                  <Progress value={100} className="h-2" data-testid="batch-progress-complete" />
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {batchProgress.results.map((r, i) => (
                    <Badge
                      key={i}
                      variant={r.eligibilityStatus === "active" ? "secondary" : "destructive"}
                      className="text-[10px]"
                      data-testid={`batch-result-${i}`}
                    >
                      {r.eligibilityStatus === "active"
                        ? <CheckCircle2 className="h-2.5 w-2.5 mr-1" />
                        : <AlertTriangle className="h-2.5 w-2.5 mr-1" />}
                      Pt {r.patientId}: {r.eligibilityStatus ?? r.status}
                      {r.cached ? " (cached)" : ""}
                    </Badge>
                  ))}
                </div>
              </>
            )}
            {!batchRunning && batchProgress && batchProgress.results.length === 0 && (
              <p className="text-xs text-muted-foreground">No appointments scheduled for tomorrow.</p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: "Checks Today", value: stats?.checksToday ?? 0, sub: "Verifications run", icon: Search, color: "text-primary", bg: "bg-primary/10" },
          { label: "Eligible Rate", value: `${stats?.eligibleRate ?? 92}%`, sub: "Active coverage", icon: CheckCircle2, color: "text-green-600", bg: "bg-green-100 dark:bg-green-900/30" },
          { label: "Avg Response", value: stats?.avgResponseTime ?? "3.2s", sub: "AI-simulated", icon: Clock, color: "text-muted-foreground", bg: "bg-muted" },
          { label: "Total Verified", value: stats?.activeVerifications ?? 0, sub: "All time", icon: Shield, color: "text-primary", bg: "bg-primary/10" },
        ].map(({ label, value, sub, icon: Icon, color, bg }) => (
          <Card key={label}>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">{label}</p>
                  <p className={`text-2xl font-bold ${color}`} data-testid={`stat-${label.toLowerCase().replace(/\s/g, "-")}`}>{value}</p>
                  <p className="text-xs text-muted-foreground mt-1">{sub}</p>
                </div>
                <div className={`p-2 ${bg} rounded-full`}><Icon className={`h-5 w-5 ${color}`} /></div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Left — verify panel */}
        <div className="lg:col-span-2 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Search className="h-4 w-4" />Verify Eligibility
              </CardTitle>
              <CardDescription>Select a patient to check their coverage. Results are cached for 24 hours.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Patient</Label>
                <Select value={selectedPatient} onValueChange={setSelectedPatient}>
                  <SelectTrigger data-testid="select-patient">
                    <SelectValue placeholder="Choose a patient…" />
                  </SelectTrigger>
                  <SelectContent>
                    {patients?.map(p => (
                      <SelectItem key={p.id} value={p.id.toString()}>
                        <div className="flex items-center gap-2">
                          <User className="h-3.5 w-3.5" />{p.firstName} {p.lastName}
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <Button
                className="w-full"
                onClick={() => verifyMut.mutate({ patientId: parseInt(selectedPatient) })}
                disabled={verifyMut.isPending || !selectedPatient}
                data-testid="button-verify"
              >
                {verifyMut.isPending ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Verifying…</> : <><Shield className="mr-2 h-4 w-4" />Verify Eligibility Now</>}
              </Button>

              {latestResult && !verifyMut.isPending && (
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full"
                  onClick={() => verifyMut.mutate({ patientId: parseInt(selectedPatient), forceRefresh: true })}
                  disabled={verifyMut.isPending}
                  data-testid="button-force-refresh-main"
                >
                  <RefreshCw className="mr-2 h-3.5 w-3.5" />Force Refresh (bypass cache)
                </Button>
              )}
            </CardContent>
          </Card>

          {/* On-file insurance summary — shown before/independent of running a check */}
          {selectedPatient && primaryInsurance && (
            <Card data-testid="card-insurance-on-file">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Shield className="h-4 w-4 text-primary" />Insurance On File
                </CardTitle>
                <CardDescription className="text-xs">
                  Current coverage record — verify to get real-time status
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Provider</span>
                  <span className="font-medium">{primaryInsurance.providerName ?? "—"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Type</span>
                  <span className="font-medium uppercase">{primaryInsurance.insuranceType ?? "—"}</span>
                </div>
                {primaryInsurance.subscriberName && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Subscriber</span>
                    <span className="font-medium">{primaryInsurance.subscriberName}</span>
                  </div>
                )}
                {primaryInsurance.policyNumber && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Policy #</span>
                    <span className="font-medium font-mono">{primaryInsurance.policyNumber}</span>
                  </div>
                )}
                {primaryInsurance.groupNumber && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Group #</span>
                    <span className="font-medium font-mono">{primaryInsurance.groupNumber}</span>
                  </div>
                )}
                <Separator />
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Effective</span>
                  <span className="font-medium">{fmtDate(primaryInsurance.effectiveDate)}</span>
                </div>
                {primaryInsurance.terminationDate && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Terminates</span>
                    <span className="font-medium text-red-600">{fmtDate(primaryInsurance.terminationDate)}</span>
                  </div>
                )}
                <Separator />
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Annual Max</span>
                  <span className="font-medium">{fmt$(primaryInsurance.annualMaximum)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Deductible</span>
                  <span className="font-medium">{fmt$(primaryInsurance.deductible)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Benefits Remaining</span>
                  <span className="font-medium text-green-600">{fmt$(primaryInsurance.remainingBenefit)}</span>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Patient eligibility history */}
          {selectedPatient && (
            <Card data-testid="card-patient-history">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm flex items-center gap-2">
                  <History className="h-4 w-4" />
                  History — {selectedPatientName ? `${selectedPatientName.firstName} ${selectedPatientName.lastName}` : "Patient"}
                </CardTitle>
              </CardHeader>
              <CardContent>
                {historyLoading ? (
                  <div className="space-y-2">{[1,2].map(i => <Skeleton key={i} className="h-12" />)}</div>
                ) : patientHistory && patientHistory.length > 0 ? (
                  <div className="space-y-2">
                    {patientHistory.map((c, i) => (
                      <div key={c.id} className="flex items-center justify-between text-xs p-2 rounded border" data-testid={`history-row-${i}`}>
                        <div className="flex items-center gap-2">
                          <Calendar className="h-3 w-3 text-muted-foreground" />
                          <span>{fmtDate(c.checkDate)}</span>
                        </div>
                        <StatusBadge status={c.eligibilityStatus} />
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground text-center py-4">No checks yet</p>
                )}
              </CardContent>
            </Card>
          )}
        </div>

        {/* Right — results + recent */}
        <div className="lg:col-span-3 space-y-4">
          {/* Latest result for selected patient */}
          {verifyMut.data ? (
            <div data-testid="card-verify-result">
              <EligibilityResultCard
                result={verifyMut.data}
                onRefresh={() => verifyMut.mutate({ patientId: parseInt(selectedPatient), forceRefresh: true })}
                refreshing={verifyMut.isPending}
              />
            </div>
          ) : verifyMut.isPending ? (
            <Card><CardContent className="pt-6 space-y-3">
              <Skeleton className="h-8 w-48" />
              <Skeleton className="h-20 w-full" />
              <Skeleton className="h-16 w-full" />
            </CardContent></Card>
          ) : null}

          {/* Recent verifications */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <FileCheck className="h-4 w-4" />Recent Verifications
              </CardTitle>
            </CardHeader>
            <CardContent>
              {checksLoading ? (
                <div className="space-y-2">{[1,2,3].map(i => <Skeleton key={i} className="h-16" />)}</div>
              ) : recentChecks && recentChecks.length > 0 ? (
                <div className="space-y-2">
                  {recentChecks.map(check => (
                    <div
                      key={check.id}
                      className="flex items-center justify-between p-3 border rounded-lg hover:bg-muted/40 transition-colors cursor-pointer"
                      onClick={() => setSelectedPatient(check.patientId.toString())}
                      data-testid={`check-${check.id}`}
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                          <User className="h-3.5 w-3.5 text-primary" />
                        </div>
                        <div>
                          <p className="text-sm font-medium">{check.patientName}</p>
                          <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <Calendar className="h-3 w-3" />
                            <span>{fmtDate(check.checkDate)}</span>
                            {check.benefitsRemaining && (
                              <><DollarSign className="h-3 w-3" /><span>{fmt$(check.benefitsRemaining)} remaining</span></>
                            )}
                          </div>
                        </div>
                      </div>
                      <StatusBadge status={check.eligibilityStatus} />
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  <Shield className="h-10 w-10 mx-auto mb-2 opacity-30" />
                  <p className="text-sm">No verifications yet</p>
                  <p className="text-xs mt-1">Select a patient and click Verify Eligibility Now</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
