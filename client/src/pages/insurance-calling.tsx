import { Fragment, useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/hooks/use-toast";
import { apiRequest, queryClient } from "@/lib/queryClient";
import {
  Phone,
  PhoneCall,
  Clock,
  CheckCircle2,
  DollarSign,
  Loader2,
  AlertTriangle,
  FileText,
  ChevronDown,
  ChevronRight,
} from "lucide-react";

type CallStatus = "queued" | "initiated" | "in_progress" | "completed" | "failed" | "mock_completed";
type CallPurpose = "claim_status" | "denial_appeal" | "prior_auth" | "eligibility_verify" | "payment_status";

interface CallOutcome {
  resolved: boolean;
  summary: string;
  nextAction: string;
  referenceNumber: string;
  followUpDate: string | null;
}

interface InsuranceCallTask {
  id: string;
  patientName: string;
  patientDOB: string;
  patientInsuranceId: string;
  insurerName: string;
  insurerPhone: string;
  claimNumber: string;
  procedureCodes: string[];
  purpose: CallPurpose;
  priority: "urgent" | "standard" | "low";
  callScript: string;
  status: CallStatus;
  callSid: string | null;
  callDuration: number | null;
  transcript: string | null;
  outcome: CallOutcome | null;
  notes: string;
  createdAt: string;
  completedAt: string | null;
}

interface CallQueueStats {
  queued: number;
  inProgress: number;
  completedToday: number;
  resolvedToday: number;
  estimatedRevenuePending: number;
}

const purposeLabels: Record<CallPurpose, string> = {
  claim_status: "Claim Status",
  denial_appeal: "Denial Appeal",
  prior_auth: "Prior Auth",
  eligibility_verify: "Eligibility Verify",
  payment_status: "Payment Status",
};

const emptyForm = {
  patientName: "",
  patientDOB: "",
  patientInsuranceId: "",
  insurerName: "",
  insurerPhone: "",
  claimNumber: "",
  procedureCodes: "",
  purpose: "claim_status" as CallPurpose,
  priority: "standard" as InsuranceCallTask["priority"],
};

function statusBadge(status: CallStatus) {
  const map: Record<CallStatus, string> = {
    queued: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300",
    initiated: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
    in_progress: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400",
    completed: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
    failed: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
    mock_completed: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400",
  };
  return <Badge className={map[status]} data-testid={`badge-status-${status}`}>{status.replace("_", " ")}</Badge>;
}

function priorityBadge(priority: InsuranceCallTask["priority"]) {
  const map: Record<InsuranceCallTask["priority"], string> = {
    urgent: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
    standard: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
    low: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300",
  };
  return <Badge className={map[priority]}>{priority}</Badge>;
}

export default function InsuranceCallingPage() {
  const { toast } = useToast();
  const [form, setForm] = useState({ ...emptyForm });
  const [lastScript, setLastScript] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [showMockNotice, setShowMockNotice] = useState(false);

  const { data: stats, isLoading: statsLoading } = useQuery<CallQueueStats>({
    queryKey: ["/api/insurance-calls/stats"],
  });

  const { data: tasks, isLoading: tasksLoading } = useQuery<InsuranceCallTask[]>({
    queryKey: ["/api/insurance-calls"],
  });

  const createMutation = useMutation({
    mutationFn: async () => {
      const res = await apiRequest("POST", "/api/insurance-calls/create", {
        ...form,
        procedureCodes: form.procedureCodes
          .split(",")
          .map((c) => c.trim())
          .filter(Boolean),
      });
      return (await res.json()) as InsuranceCallTask;
    },
    onSuccess: (task) => {
      setLastScript(task.callScript);
      setForm({ ...emptyForm });
      queryClient.invalidateQueries({ queryKey: ["/api/insurance-calls"] });
      queryClient.invalidateQueries({ queryKey: ["/api/insurance-calls/stats"] });
      toast({ title: "Call Task Created", description: "AI generated a call script for this task" });
    },
    onError: (err: Error) => {
      toast({ title: "Creation Failed", description: err.message, variant: "destructive" });
    },
  });

  const initiateMutation = useMutation({
    mutationFn: async (id: string) => {
      const res = await apiRequest("POST", `/api/insurance-calls/initiate/${id}`, {});
      return (await res.json()) as InsuranceCallTask;
    },
    onSuccess: (task) => {
      if (task.status === "mock_completed") setShowMockNotice(true);
      queryClient.invalidateQueries({ queryKey: ["/api/insurance-calls"] });
      queryClient.invalidateQueries({ queryKey: ["/api/insurance-calls/stats"] });
      toast({ title: "Call Initiated", description: `Status: ${task.status.replace("_", " ")}` });
    },
    onError: (err: Error) => {
      toast({ title: "Initiate Failed", description: err.message, variant: "destructive" });
    },
  });

  const canSubmit =
    form.patientName && form.insurerName && form.insurerPhone && form.claimNumber && !createMutation.isPending;

  return (
    <div className="p-6 space-y-6 overflow-y-auto max-h-[calc(100vh-80px)]">
      <div>
        <h1 className="text-3xl font-bold" data-testid="text-page-title">AI Insurance Calling</h1>
        <p className="text-muted-foreground">
          Outbound follow-up calls to insurers for denied and pending claims
        </p>
      </div>

      {showMockNotice && (
        <div className="p-4 rounded-lg border border-yellow-300 bg-yellow-50 dark:bg-yellow-900/20 dark:border-yellow-800 flex items-start gap-2" data-testid="banner-mock-mode">
          <AlertTriangle className="h-5 w-5 text-yellow-600 mt-0.5 shrink-0" />
          <p className="text-sm text-yellow-800 dark:text-yellow-200">
            Running in mock mode — add <code className="font-mono">TWILIO_ACCOUNT_SID</code>,{" "}
            <code className="font-mono">TWILIO_AUTH_TOKEN</code>, <code className="font-mono">TWILIO_FROM_NUMBER</code>{" "}
            to enable live calls.
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {statsLoading ? (
          [...Array(4)].map((_, i) => <Skeleton key={i} className="h-28" />)
        ) : (
          <>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Queued Calls</p>
                    <p className="text-2xl font-bold" data-testid="stat-queued">{stats?.queued ?? 0}</p>
                  </div>
                  <div className="p-2 bg-muted rounded-full"><Phone className="h-5 w-5 text-muted-foreground" /></div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">In Progress</p>
                    <p className="text-2xl font-bold text-amber-600" data-testid="stat-in-progress">{stats?.inProgress ?? 0}</p>
                  </div>
                  <div className="p-2 bg-amber-100 dark:bg-amber-900/30 rounded-full"><Clock className="h-5 w-5 text-amber-600" /></div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Completed Today</p>
                    <p className="text-2xl font-bold text-green-600" data-testid="stat-completed">{stats?.completedToday ?? 0}</p>
                    <p className="text-xs text-muted-foreground mt-1">{stats?.resolvedToday ?? 0} resolved</p>
                  </div>
                  <div className="p-2 bg-green-100 dark:bg-green-900/30 rounded-full"><CheckCircle2 className="h-5 w-5 text-green-600" /></div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Est. Revenue Pending</p>
                    <p className="text-2xl font-bold" data-testid="stat-revenue">
                      ${((stats?.estimatedRevenuePending ?? 0) / 1000).toFixed(1)}K
                    </p>
                  </div>
                  <div className="p-2 bg-primary/10 rounded-full"><DollarSign className="h-5 w-5 text-primary" /></div>
                </div>
              </CardContent>
            </Card>
          </>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><PhoneCall className="h-5 w-5 text-primary" />New Call Task</CardTitle>
          <CardDescription>Create a follow-up call task — an AI call script is generated automatically</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label>Patient Name</Label>
              <Input value={form.patientName} onChange={(e) => setForm({ ...form, patientName: e.target.value })} data-testid="input-patient-name" />
            </div>
            <div className="space-y-2">
              <Label>Date of Birth</Label>
              <Input type="date" value={form.patientDOB} onChange={(e) => setForm({ ...form, patientDOB: e.target.value })} data-testid="input-dob" />
            </div>
            <div className="space-y-2">
              <Label>Insurance ID</Label>
              <Input value={form.patientInsuranceId} onChange={(e) => setForm({ ...form, patientInsuranceId: e.target.value })} data-testid="input-insurance-id" />
            </div>
            <div className="space-y-2">
              <Label>Insurer Name</Label>
              <Input value={form.insurerName} onChange={(e) => setForm({ ...form, insurerName: e.target.value })} data-testid="input-insurer-name" />
            </div>
            <div className="space-y-2">
              <Label>Insurer Phone</Label>
              <Input value={form.insurerPhone} onChange={(e) => setForm({ ...form, insurerPhone: e.target.value })} data-testid="input-insurer-phone" />
            </div>
            <div className="space-y-2">
              <Label>Claim Number</Label>
              <Input value={form.claimNumber} onChange={(e) => setForm({ ...form, claimNumber: e.target.value })} data-testid="input-claim-number" />
            </div>
            <div className="space-y-2 md:col-span-3">
              <Label>Procedure Codes (comma-separated CDT, e.g. D6010, D6056)</Label>
              <Input value={form.procedureCodes} onChange={(e) => setForm({ ...form, procedureCodes: e.target.value })} placeholder="D6010, D6056" data-testid="input-procedure-codes" />
            </div>
            <div className="space-y-2">
              <Label>Purpose</Label>
              <Select value={form.purpose} onValueChange={(v) => setForm({ ...form, purpose: v as CallPurpose })}>
                <SelectTrigger data-testid="select-purpose"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {(Object.keys(purposeLabels) as CallPurpose[]).map((p) => (
                    <SelectItem key={p} value={p}>{purposeLabels[p]}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Priority</Label>
              <Select value={form.priority} onValueChange={(v) => setForm({ ...form, priority: v as InsuranceCallTask["priority"] })}>
                <SelectTrigger data-testid="select-priority"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="urgent">Urgent</SelectItem>
                  <SelectItem value="standard">Standard</SelectItem>
                  <SelectItem value="low">Low</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <Button onClick={() => createMutation.mutate()} disabled={!canSubmit} data-testid="button-create-task">
            {createMutation.isPending ? (
              <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Generating Script...</>
            ) : (
              <><PhoneCall className="mr-2 h-4 w-4" />Create Call Task</>
            )}
          </Button>

          {lastScript && (
            <div className="space-y-2">
              <Label className="flex items-center gap-2"><FileText className="h-4 w-4" />Generated Call Script</Label>
              <pre className="p-3 bg-muted rounded-lg text-sm whitespace-pre-wrap font-mono overflow-x-auto" data-testid="text-generated-script">{lastScript}</pre>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Call Queue</CardTitle>
          <CardDescription>All insurance call tasks</CardDescription>
        </CardHeader>
        <CardContent>
          {tasksLoading ? (
            <div className="space-y-2">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-16" />)}</div>
          ) : tasks && tasks.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="py-2 pr-4 font-medium"></th>
                    <th className="py-2 pr-4 font-medium">Patient</th>
                    <th className="py-2 pr-4 font-medium">Insurer</th>
                    <th className="py-2 pr-4 font-medium">Purpose</th>
                    <th className="py-2 pr-4 font-medium">Procedures</th>
                    <th className="py-2 pr-4 font-medium">Priority</th>
                    <th className="py-2 pr-4 font-medium">Status</th>
                    <th className="py-2 pr-4 font-medium">Created</th>
                    <th className="py-2 pr-4 font-medium">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {tasks.map((t) => (
                    <Fragment key={t.id}>
                      <tr className="border-b" data-testid={`row-task-${t.id}`}>
                        <td className="py-2 pr-4">
                          <button onClick={() => setExpanded(expanded === t.id ? null : t.id)} data-testid={`button-expand-${t.id}`}>
                            {expanded === t.id ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                          </button>
                        </td>
                        <td className="py-2 pr-4 font-medium">{t.patientName}</td>
                        <td className="py-2 pr-4">{t.insurerName}</td>
                        <td className="py-2 pr-4">{purposeLabels[t.purpose]}</td>
                        <td className="py-2 pr-4">{t.procedureCodes.join(", ")}</td>
                        <td className="py-2 pr-4">{priorityBadge(t.priority)}</td>
                        <td className="py-2 pr-4">{statusBadge(t.status)}</td>
                        <td className="py-2 pr-4 text-muted-foreground">{new Date(t.createdAt).toLocaleDateString()}</td>
                        <td className="py-2 pr-4">
                          {t.status === "queued" && (
                            <Button
                              size="sm"
                              onClick={() => initiateMutation.mutate(t.id)}
                              disabled={initiateMutation.isPending}
                              data-testid={`button-initiate-${t.id}`}
                            >
                              {initiateMutation.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : <><PhoneCall className="h-3 w-3 mr-1" />Initiate</>}
                            </Button>
                          )}
                        </td>
                      </tr>
                      {expanded === t.id && (
                        <tr className="border-b bg-muted/30" data-testid={`row-detail-${t.id}`}>
                          <td colSpan={9} className="p-4 space-y-3">
                            <div>
                              <p className="font-medium mb-1">Call Script</p>
                              <pre className="p-3 bg-background rounded text-xs whitespace-pre-wrap font-mono overflow-x-auto">{t.callScript}</pre>
                            </div>
                            {t.transcript && (
                              <div>
                                <p className="font-medium mb-1">Transcript</p>
                                <pre className="p-3 bg-background rounded text-xs whitespace-pre-wrap font-mono overflow-x-auto">{t.transcript}</pre>
                              </div>
                            )}
                            {t.outcome && (
                              <div>
                                <p className="font-medium mb-1">Outcome</p>
                                <div className="p-3 bg-background rounded text-xs space-y-1">
                                  <p><span className="text-muted-foreground">Resolved:</span> {t.outcome.resolved ? "Yes" : "No"}</p>
                                  <p><span className="text-muted-foreground">Summary:</span> {t.outcome.summary}</p>
                                  <p><span className="text-muted-foreground">Next Action:</span> {t.outcome.nextAction}</p>
                                  <p><span className="text-muted-foreground">Reference #:</span> {t.outcome.referenceNumber}</p>
                                  {t.outcome.followUpDate && <p><span className="text-muted-foreground">Follow-up:</span> {t.outcome.followUpDate}</p>}
                                </div>
                              </div>
                            )}
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              <Phone className="h-12 w-12 mx-auto mb-2" />
              <p>No call tasks yet — create one above</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
