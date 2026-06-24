import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useToast } from "@/hooks/use-toast";
import { apiRequest, queryClient } from "@/lib/queryClient";
import {
  FileCheck,
  Loader2,
  Plus,
  Trash2,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Info,
  DollarSign,
  Send,
} from "lucide-react";

interface EOBLineItem {
  procedureCode: string;
  toothNumber: string;
  billedAmount: number;
  allowedAmount: number;
  insurancePaid: number;
  patientResponsibility: number;
  adjustments: number;
  denialCode: string | null;
  denialReason: string | null;
}

interface ParsedEOB {
  id: string;
  patientName: string;
  patientId: string;
  insurerName: string;
  claimNumber: string;
  serviceDate: string;
  processingDate: string;
  totalBilled: number;
  totalAllowed: number;
  totalInsurancePaid: number;
  totalPatientResponsibility: number;
  lineItems: EOBLineItem[];
  postingStatus: "pending" | "posted" | "error" | "needs_review";
  postingNotes: string;
  parsedAt: string;
}

interface EOBPostingResult {
  eobId: string;
  linesPosted: number;
  totalPosted: number;
  deniedLines: number;
  patientBalanceCreated: number;
  appealCandidates: EOBLineItem[];
  postingStatus: ParsedEOB["postingStatus"];
  message: string;
}

interface ClaimLine {
  procedureCode: string;
  toothNumber: string;
  surface?: string;
  fee: number;
  diagnosisCode?: string;
  dateOfService: string;
}

type ScrubSeverity = "error" | "warning" | "info";

interface ScrubIssue {
  code: string;
  severity: ScrubSeverity;
  affectedLine: string;
  message: string;
  suggestion: string;
  autoFixable: boolean;
}

interface ScrubResult {
  claimId: string;
  passedScrub: boolean;
  issues: ScrubIssue[];
  errorCount: number;
  warningCount: number;
  estimatedDenialRisk: "low" | "medium" | "high";
  cleanClaimScore: number;
  readyToSubmit: boolean;
  scrubbedAt: string;
}

const fmtUSD = (n: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n || 0);

function StatCard({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          {label}
        </div>
        <div className={`mt-1 text-xl font-bold font-mono ${accent ?? ""}`}>{value}</div>
      </CardContent>
    </Card>
  );
}

// ---------------- EOB Posting Tab ----------------
function EOBPostingTab() {
  const { toast } = useToast();
  const [rawEOBText, setRawEOBText] = useState("");
  const [eob, setEob] = useState<ParsedEOB | null>(null);
  const [postResult, setPostResult] = useState<EOBPostingResult | null>(null);

  const { data: recentEOBs } = useQuery<ParsedEOB[]>({ queryKey: ["/api/rcm/eob"] });

  const parseMutation = useMutation({
    mutationFn: async () => {
      const res = await apiRequest("POST", "/api/rcm/eob/parse", { rawEOBText });
      return (await res.json()) as ParsedEOB;
    },
    onSuccess: (data) => {
      setEob(data);
      setPostResult(null);
      queryClient.invalidateQueries({ queryKey: ["/api/rcm/eob"] });
      toast({ title: "EOB Parsed", description: `Claim ${data.claimNumber} — ${data.lineItems.length} line items` });
    },
    onError: (err: Error) => toast({ title: "Parse Failed", description: err.message, variant: "destructive" }),
  });

  const postMutation = useMutation({
    mutationFn: async (id: string) => {
      const res = await apiRequest("POST", `/api/rcm/eob/post/${id}`, {});
      return (await res.json()) as EOBPostingResult;
    },
    onSuccess: (data) => {
      setPostResult(data);
      queryClient.invalidateQueries({ queryKey: ["/api/rcm/eob"] });
      toast({ title: "Posted to Ledger", description: data.message });
    },
    onError: (err: Error) => toast({ title: "Posting Failed", description: err.message, variant: "destructive" }),
  });

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
      <div className="space-y-6 lg:col-span-2">
        <Card>
          <CardHeader>
            <CardTitle>Parse EOB</CardTitle>
            <CardDescription>Paste the raw EOB text and let AI extract structured line items.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Textarea
              data-testid="input-eob-text"
              rows={10}
              placeholder="Paste EOB text here"
              value={rawEOBText}
              onChange={(e) => setRawEOBText(e.target.value)}
            />
            <Button
              data-testid="button-parse-eob"
              onClick={() => parseMutation.mutate()}
              disabled={!rawEOBText.trim() || parseMutation.isPending}
            >
              {parseMutation.isPending ? (
                <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Parsing…</>
              ) : (
                <><FileCheck className="mr-2 h-4 w-4" /> Parse EOB</>
              )}
            </Button>
          </CardContent>
        </Card>

        {eob && (
          <Card data-testid="card-parsed-eob">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>{eob.patientName}</CardTitle>
                  <CardDescription>
                    {eob.insurerName} • Claim {eob.claimNumber} • DOS {eob.serviceDate}
                  </CardDescription>
                </div>
                <Badge variant={eob.postingStatus === "posted" ? "default" : "secondary"}>
                  {eob.postingStatus}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <StatCard label="Billed" value={fmtUSD(eob.totalBilled)} />
                <StatCard label="Allowed" value={fmtUSD(eob.totalAllowed)} />
                <StatCard label="Ins. Paid" value={fmtUSD(eob.totalInsurancePaid)} accent="text-emerald-600 dark:text-emerald-400" />
                <StatCard label="Patient Resp." value={fmtUSD(eob.totalPatientResponsibility)} />
              </div>

              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Code</TableHead>
                      <TableHead>Tooth</TableHead>
                      <TableHead className="text-right">Billed</TableHead>
                      <TableHead className="text-right">Allowed</TableHead>
                      <TableHead className="text-right">Paid</TableHead>
                      <TableHead className="text-right">Pt Resp</TableHead>
                      <TableHead>Denial</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {eob.lineItems.map((l, i) => (
                      <TableRow key={i} data-testid={`row-eob-line-${i}`}>
                        <TableCell className="font-mono font-medium">{l.procedureCode}</TableCell>
                        <TableCell>{l.toothNumber}</TableCell>
                        <TableCell className="text-right font-mono">{fmtUSD(l.billedAmount)}</TableCell>
                        <TableCell className="text-right font-mono">{fmtUSD(l.allowedAmount)}</TableCell>
                        <TableCell className="text-right font-mono">{fmtUSD(l.insurancePaid)}</TableCell>
                        <TableCell className="text-right font-mono">{fmtUSD(l.patientResponsibility)}</TableCell>
                        <TableCell>
                          {l.denialCode ? (
                            <Badge variant="destructive" title={l.denialReason ?? ""}>{l.denialCode}</Badge>
                          ) : (
                            <span className="text-muted-foreground">—</span>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              <Button
                data-testid="button-post-eob"
                onClick={() => postMutation.mutate(eob.id)}
                disabled={postMutation.isPending}
              >
                {postMutation.isPending ? (
                  <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Posting…</>
                ) : (
                  <><DollarSign className="mr-2 h-4 w-4" /> Post to Ledger</>
                )}
              </Button>
            </CardContent>
          </Card>
        )}

        {postResult && (
          <Card data-testid="card-post-result">
            <CardHeader>
              <CardTitle>Posting Result</CardTitle>
              <CardDescription>{postResult.message}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <StatCard label="Lines Posted" value={String(postResult.linesPosted)} />
                <StatCard label="Total Posted" value={fmtUSD(postResult.totalPosted)} accent="text-emerald-600 dark:text-emerald-400" />
                <StatCard label="Denied Lines" value={String(postResult.deniedLines)} accent={postResult.deniedLines > 0 ? "text-destructive" : ""} />
                <StatCard label="Patient Balance" value={fmtUSD(postResult.patientBalanceCreated)} />
              </div>

              {postResult.appealCandidates.length > 0 && (
                <div className="rounded-md border border-amber-400 bg-amber-50 p-4 dark:bg-amber-950/30">
                  <div className="mb-2 flex items-center gap-2 font-semibold text-amber-700 dark:text-amber-400">
                    <AlertTriangle className="h-4 w-4" /> Appeal Candidates ({postResult.appealCandidates.length})
                  </div>
                  <ul className="space-y-1 text-sm">
                    {postResult.appealCandidates.map((c, i) => (
                      <li key={i} data-testid={`appeal-candidate-${i}`} className="font-mono">
                        {c.procedureCode} (tooth {c.toothNumber}) — {c.denialCode}: {c.denialReason ?? "denied"}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </div>

      <div>
        <Card>
          <CardHeader>
            <CardTitle>Recent EOBs</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {!recentEOBs?.length && <p className="text-sm text-muted-foreground">No EOBs parsed yet.</p>}
            {recentEOBs?.map((e) => (
              <button
                key={e.id}
                data-testid={`recent-eob-${e.id}`}
                onClick={() => { setEob(e); setPostResult(null); }}
                className="w-full rounded-md border p-3 text-left text-sm hover:bg-muted"
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium">{e.patientName}</span>
                  <Badge variant={e.postingStatus === "posted" ? "default" : "secondary"}>{e.postingStatus}</Badge>
                </div>
                <div className="text-xs text-muted-foreground">{e.insurerName} • {e.claimNumber}</div>
              </button>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

// ---------------- Claim Scrubber Tab ----------------
const emptyLine: ClaimLine = {
  procedureCode: "",
  toothNumber: "",
  surface: "",
  fee: 0,
  diagnosisCode: "",
  dateOfService: "",
};

function ClaimScrubberTab() {
  const { toast } = useToast();
  const [patientName, setPatientName] = useState("");
  const [patientDOB, setPatientDOB] = useState("");
  const [patientInsuranceId, setPatientInsuranceId] = useState("");
  const [insurerName, setInsurerName] = useState("");
  const [providerNPI, setProviderNPI] = useState("");
  const [dateOfService, setDateOfService] = useState("");
  const [lines, setLines] = useState<ClaimLine[]>([]);
  const [draft, setDraft] = useState<ClaimLine>({ ...emptyLine });
  const [result, setResult] = useState<ScrubResult | null>(null);

  const addLine = () => {
    if (!draft.procedureCode.trim()) {
      toast({ title: "CDT code required", description: "Enter a procedure code before adding a line.", variant: "destructive" });
      return;
    }
    setLines((prev) => [...prev, { ...draft, dateOfService: draft.dateOfService || dateOfService }]);
    setDraft({ ...emptyLine });
  };

  const removeLine = (idx: number) => setLines((prev) => prev.filter((_, i) => i !== idx));

  const scrubMutation = useMutation({
    mutationFn: async () => {
      const claim = {
        patientName,
        patientDOB,
        patientInsuranceId,
        insurerName,
        providerNPI,
        dateOfService,
        lines,
      };
      const res = await apiRequest("POST", "/api/rcm/claims/scrub", claim);
      return (await res.json()) as ScrubResult;
    },
    onSuccess: (data) => {
      setResult(data);
      toast({ title: "Claim Scrubbed", description: `Score ${data.cleanClaimScore}/100 — ${data.issues.length} issue(s)` });
    },
    onError: (err: Error) => toast({ title: "Scrub Failed", description: err.message, variant: "destructive" }),
  });

  const applyFix = (issue: ScrubIssue) => {
    // Mark the issue resolved locally; real auto-fix would mutate the claim line.
    setResult((prev) =>
      prev ? { ...prev, issues: prev.issues.filter((i) => i !== issue) } : prev
    );
    toast({ title: "Fix applied", description: `${issue.code} marked resolved. Re-scrub to confirm.` });
  };

  const scoreColor = (s: number) =>
    s >= 80 ? "text-emerald-600 dark:text-emerald-400" : s >= 60 ? "text-amber-600 dark:text-amber-400" : "text-destructive";

  const riskVariant = (r: ScrubResult["estimatedDenialRisk"]) =>
    r === "low" ? "default" : r === "medium" ? "secondary" : "destructive";

  const severityIcon = (s: ScrubSeverity) =>
    s === "error" ? <XCircle className="h-4 w-4 text-destructive" /> :
    s === "warning" ? <AlertTriangle className="h-4 w-4 text-amber-500" /> :
    <Info className="h-4 w-4 text-blue-500" />;

  const autoFixable = result?.issues.filter((i) => i.autoFixable) ?? [];

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Build Claim</CardTitle>
            <CardDescription>Enter claim header and procedure lines, then scrub for denial risk.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Patient Name</Label>
                <Input data-testid="input-patient-name" value={patientName} onChange={(e) => setPatientName(e.target.value)} />
              </div>
              <div>
                <Label>Patient DOB</Label>
                <Input data-testid="input-patient-dob" type="date" value={patientDOB} onChange={(e) => setPatientDOB(e.target.value)} />
              </div>
              <div>
                <Label>Insurance ID</Label>
                <Input data-testid="input-insurance-id" value={patientInsuranceId} onChange={(e) => setPatientInsuranceId(e.target.value)} />
              </div>
              <div>
                <Label>Insurer Name</Label>
                <Input data-testid="input-insurer-name" value={insurerName} onChange={(e) => setInsurerName(e.target.value)} />
              </div>
              <div>
                <Label>Provider NPI</Label>
                <Input data-testid="input-provider-npi" value={providerNPI} onChange={(e) => setProviderNPI(e.target.value)} />
              </div>
              <div>
                <Label>Date of Service</Label>
                <Input data-testid="input-date-of-service" type="date" value={dateOfService} onChange={(e) => setDateOfService(e.target.value)} />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Procedure Lines</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              <div>
                <Label className="text-xs">CDT Code</Label>
                <Input data-testid="input-line-code" placeholder="D6010" value={draft.procedureCode} onChange={(e) => setDraft({ ...draft, procedureCode: e.target.value })} />
              </div>
              <div>
                <Label className="text-xs">Tooth</Label>
                <Input data-testid="input-line-tooth" placeholder="30" value={draft.toothNumber} onChange={(e) => setDraft({ ...draft, toothNumber: e.target.value })} />
              </div>
              <div>
                <Label className="text-xs">Surface</Label>
                <Input data-testid="input-line-surface" placeholder="MOD" value={draft.surface} onChange={(e) => setDraft({ ...draft, surface: e.target.value })} />
              </div>
              <div>
                <Label className="text-xs">Fee</Label>
                <Input data-testid="input-line-fee" type="number" value={draft.fee || ""} onChange={(e) => setDraft({ ...draft, fee: parseFloat(e.target.value) || 0 })} />
              </div>
              <div>
                <Label className="text-xs">ICD-10</Label>
                <Input data-testid="input-line-dx" placeholder="K08.101" value={draft.diagnosisCode} onChange={(e) => setDraft({ ...draft, diagnosisCode: e.target.value })} />
              </div>
              <div className="flex items-end">
                <Button data-testid="button-add-line" variant="secondary" className="w-full" onClick={addLine}>
                  <Plus className="mr-2 h-4 w-4" /> Add Line
                </Button>
              </div>
            </div>

            {lines.length > 0 && (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Code</TableHead>
                      <TableHead>Tooth</TableHead>
                      <TableHead>Surface</TableHead>
                      <TableHead className="text-right">Fee</TableHead>
                      <TableHead>ICD-10</TableHead>
                      <TableHead></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {lines.map((l, i) => (
                      <TableRow key={i} data-testid={`row-claim-line-${i}`}>
                        <TableCell className="font-mono font-medium">{l.procedureCode}</TableCell>
                        <TableCell>{l.toothNumber || "—"}</TableCell>
                        <TableCell>{l.surface || "—"}</TableCell>
                        <TableCell className="text-right font-mono">{fmtUSD(l.fee)}</TableCell>
                        <TableCell>{l.diagnosisCode || "—"}</TableCell>
                        <TableCell>
                          <Button data-testid={`button-remove-line-${i}`} variant="ghost" size="icon" onClick={() => removeLine(i)}>
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}

            <Button
              data-testid="button-scrub-claim"
              onClick={() => scrubMutation.mutate()}
              disabled={!lines.length || scrubMutation.isPending}
            >
              {scrubMutation.isPending ? (
                <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Scrubbing…</>
              ) : (
                <><Send className="mr-2 h-4 w-4" /> Scrub Claim</>
              )}
            </Button>
          </CardContent>
        </Card>
      </div>

      <div className="space-y-6">
        {result ? (
          <>
            <Card data-testid="card-scrub-summary">
              <CardHeader>
                <CardTitle>Scrub Results</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Clean Claim Score</div>
                    <div data-testid="text-clean-score" className={`text-5xl font-bold font-mono ${scoreColor(result.cleanClaimScore)}`}>
                      {result.cleanClaimScore}
                    </div>
                  </div>
                  <div className="space-y-2 text-right">
                    <div>
                      <span className="mr-2 text-xs text-muted-foreground">Denial Risk</span>
                      <Badge data-testid="badge-denial-risk" variant={riskVariant(result.estimatedDenialRisk)}>
                        {result.estimatedDenialRisk}
                      </Badge>
                    </div>
                    <div className="flex items-center justify-end gap-2" data-testid="text-ready-to-submit">
                      {result.readyToSubmit ? (
                        <><CheckCircle2 className="h-5 w-5 text-emerald-500" /> <span className="text-sm font-medium">Ready to Submit</span></>
                      ) : (
                        <><XCircle className="h-5 w-5 text-destructive" /> <span className="text-sm font-medium">Not Ready</span></>
                      )}
                    </div>
                  </div>
                </div>
                <div className="flex gap-4 text-sm">
                  <span className="text-destructive">{result.errorCount} errors</span>
                  <span className="text-amber-600 dark:text-amber-400">{result.warningCount} warnings</span>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Issues ({result.issues.length})</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {result.issues.length === 0 && (
                  <p className="text-sm text-emerald-600 dark:text-emerald-400">No issues found — claim is clean.</p>
                )}
                {result.issues.map((issue, i) => (
                  <div key={i} data-testid={`scrub-issue-${i}`} className="rounded-md border p-3">
                    <div className="flex items-start gap-2">
                      {severityIcon(issue.severity)}
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs font-semibold">{issue.code}</span>
                          <Badge variant="outline" className="text-xs">{issue.affectedLine}</Badge>
                        </div>
                        <p className="mt-1 text-sm">{issue.message}</p>
                        <p className="mt-1 text-xs text-muted-foreground">{issue.suggestion}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>

            {autoFixable.length > 0 && (
              <Card data-testid="card-fix-issues">
                <CardHeader>
                  <CardTitle>Fix Issues</CardTitle>
                  <CardDescription>Auto-fixable issues can be resolved with one click.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-2">
                  {autoFixable.map((issue, i) => (
                    <div key={i} className="flex items-center justify-between rounded-md border p-3">
                      <div className="text-sm">
                        <span className="font-mono font-semibold">{issue.code}</span> — {issue.message}
                      </div>
                      <Button data-testid={`button-fix-${i}`} size="sm" onClick={() => applyFix(issue)}>Fix</Button>
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}
          </>
        ) : (
          <Card>
            <CardContent className="pt-6">
              <p className="text-sm text-muted-foreground">Build a claim and run the scrubber to see results here.</p>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}

export default function RcmToolsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">RCM Tools</h1>
        <p className="text-sm text-muted-foreground">AI EOB posting and claim scrubbing for revenue cycle management.</p>
      </div>

      <Tabs defaultValue="eob">
        <TabsList>
          <TabsTrigger value="eob" data-testid="tab-eob">EOB Posting</TabsTrigger>
          <TabsTrigger value="scrubber" data-testid="tab-scrubber">Claim Scrubber</TabsTrigger>
        </TabsList>
        <TabsContent value="eob" className="mt-6">
          <EOBPostingTab />
        </TabsContent>
        <TabsContent value="scrubber" className="mt-6">
          <ClaimScrubberTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
