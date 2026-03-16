import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/hooks/use-toast";
import { apiRequest } from "@/lib/queryClient";
import {
  Smile, Calendar, DollarSign, CheckCircle, AlertTriangle, User,
  Plus, Save, Loader2, Activity, ChevronRight, RotateCcw, Star,
  Scissors, TrendingUp, FileText,
} from "lucide-react";

interface OrthoCase {
  id: number;
  patientId: number;
  treatmentType: string;
  status: string;
  startDate: string;
  estimatedEndDate: string | null;
  actualEndDate: string | null;
  currentStep: number;
  totalSteps: number | null;
  compliance: number;
  totalFee: string | null;
  amountPaid: string | null;
  insuranceCoverage: string | null;
  archesType: string;
  extractionsRequired: boolean;
  providerName: string | null;
  notes: string | null;
  progressLog: ProgressEntry[];
}

interface ProgressEntry {
  id: string;
  date: string;
  phase: string;
  step?: number;
  notes: string;
}

const TREATMENT_TYPES = [
  "Invisalign Full", "Invisalign Lite", "Invisalign Teen",
  "Metal Braces", "Clear Ceramic Braces", "Lingual Braces",
  "Retainer Only", "Phase I (Interceptive)", "Phase II (Comprehensive)",
];

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  active:       { label: "Active",        color: "text-blue-600 dark:text-blue-400",    bg: "bg-blue-500/10 border-blue-400/40" },
  retention:    { label: "Retention",     color: "text-purple-600 dark:text-purple-400", bg: "bg-purple-500/10 border-purple-400/40" },
  completed:    { label: "Completed",     color: "text-emerald-600 dark:text-emerald-400", bg: "bg-emerald-500/10 border-emerald-400/40" },
  discontinued: { label: "Discontinued",  color: "text-red-600 dark:text-red-400",      bg: "bg-red-500/10 border-red-400/40" },
};

function complianceColor(c: number) {
  if (c >= 85) return "text-emerald-600 dark:text-emerald-400";
  if (c >= 70) return "text-amber-600 dark:text-amber-400";
  return "text-red-600 dark:text-red-400";
}

function monthsRemaining(end: string | null) {
  if (!end) return null;
  return Math.round((new Date(end).getTime() - Date.now()) / (1000 * 60 * 60 * 24 * 30));
}

// ─── New Case Dialog ────────────────────────────────────────────────────────
function NewCaseDialog({ patients, open, onClose, onSaved }: {
  patients: any[]; open: boolean; onClose: () => void; onSaved: () => void;
}) {
  const { toast } = useToast();
  const [form, setForm] = useState({
    patientId: "", treatmentType: "Invisalign Full", status: "active",
    startDate: new Date().toISOString().split("T")[0], estimatedEndDate: "",
    currentStep: 1, totalSteps: 24, compliance: 100,
    totalFee: "", amountPaid: "0", insuranceCoverage: "0",
    archesType: "both", extractionsRequired: false, providerName: "", notes: "",
  });

  const mut = useMutation({
    mutationFn: () => apiRequest("POST", "/api/ortho", {
      ...form,
      patientId: parseInt(form.patientId),
      currentStep: Number(form.currentStep),
      totalSteps: Number(form.totalSteps),
      compliance: Number(form.compliance),
      progressLog: [],
    }),
    onSuccess: () => { toast({ title: "Case created" }); onSaved(); onClose(); },
    onError: () => toast({ title: "Error creating case", variant: "destructive" }),
  });

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><Smile className="h-4 w-4" /> New Ortho Case</DialogTitle>
        </DialogHeader>
        <div className="grid grid-cols-2 gap-4 py-2">
          <div className="col-span-2">
            <Label>Patient *</Label>
            <Select value={form.patientId} onValueChange={v => setForm(f => ({ ...f, patientId: v }))}>
              <SelectTrigger data-testid="select-patient-ortho"><SelectValue placeholder="Select patient…" /></SelectTrigger>
              <SelectContent>{patients.map((p: any) => <SelectItem key={p.id} value={p.id.toString()}>{p.firstName} {p.lastName}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div>
            <Label>Treatment Type *</Label>
            <Select value={form.treatmentType} onValueChange={v => setForm(f => ({ ...f, treatmentType: v }))}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>{TREATMENT_TYPES.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div>
            <Label>Arches</Label>
            <Select value={form.archesType} onValueChange={v => setForm(f => ({ ...f, archesType: v }))}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="both">Both Arches</SelectItem>
                <SelectItem value="upper">Upper Only</SelectItem>
                <SelectItem value="lower">Lower Only</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Start Date *</Label>
            <Input type="date" value={form.startDate} onChange={e => setForm(f => ({ ...f, startDate: e.target.value }))} data-testid="input-start-date" />
          </div>
          <div>
            <Label>Est. End Date</Label>
            <Input type="date" value={form.estimatedEndDate} onChange={e => setForm(f => ({ ...f, estimatedEndDate: e.target.value }))} />
          </div>
          <div>
            <Label>Current Step / Aligner</Label>
            <Input type="number" min="1" value={form.currentStep} onChange={e => setForm(f => ({ ...f, currentStep: parseInt(e.target.value) }))} />
          </div>
          <div>
            <Label>Total Steps / Aligners</Label>
            <Input type="number" min="1" value={form.totalSteps} onChange={e => setForm(f => ({ ...f, totalSteps: parseInt(e.target.value) }))} />
          </div>
          <div>
            <Label>Total Fee ($)</Label>
            <Input type="number" value={form.totalFee} onChange={e => setForm(f => ({ ...f, totalFee: e.target.value }))} data-testid="input-total-fee" />
          </div>
          <div>
            <Label>Amount Paid ($)</Label>
            <Input type="number" value={form.amountPaid} onChange={e => setForm(f => ({ ...f, amountPaid: e.target.value }))} />
          </div>
          <div>
            <Label>Insurance Coverage ($)</Label>
            <Input type="number" value={form.insuranceCoverage} onChange={e => setForm(f => ({ ...f, insuranceCoverage: e.target.value }))} />
          </div>
          <div>
            <Label>Provider</Label>
            <Input value={form.providerName} onChange={e => setForm(f => ({ ...f, providerName: e.target.value }))} placeholder="Dr. Smith" />
          </div>
          <div className="col-span-2">
            <Label>Notes</Label>
            <Textarea value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} rows={2} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={() => mut.mutate()} disabled={mut.isPending || !form.patientId} data-testid="button-save-case">
            {mut.isPending ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Save className="h-4 w-4 mr-1" />}
            Create Case
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ─── Progress Dialog ─────────────────────────────────────────────────────
function AddProgressDialog({ caseId, currentLog, open, onClose, onSaved }: {
  caseId: number; currentLog: ProgressEntry[]; open: boolean; onClose: () => void; onSaved: () => void;
}) {
  const { toast } = useToast();
  const [form, setForm] = useState({
    date: new Date().toISOString().split("T")[0],
    phase: "Progress Check", step: "", notes: "",
  });

  const mut = useMutation({
    mutationFn: () => {
      const entry: ProgressEntry = {
        id: Date.now().toString(), date: form.date,
        phase: form.phase, notes: form.notes,
        ...(form.step ? { step: parseInt(form.step) } : {}),
      };
      return apiRequest("PUT", `/api/ortho/${caseId}`, {
        progressLog: [...currentLog, entry],
        ...(form.step ? { currentStep: parseInt(form.step) } : {}),
      });
    },
    onSuccess: () => { toast({ title: "Progress recorded" }); onSaved(); onClose(); },
    onError: () => toast({ title: "Error", variant: "destructive" }),
  });

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader><DialogTitle>Add Progress Note</DialogTitle></DialogHeader>
        <div className="space-y-4 py-2">
          <div>
            <Label>Date</Label>
            <Input type="date" value={form.date} onChange={e => setForm(f => ({ ...f, date: e.target.value }))} />
          </div>
          <div>
            <Label>Visit Type</Label>
            <Select value={form.phase} onValueChange={v => setForm(f => ({ ...f, phase: v }))}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {["Bond / Start", "Progress Check", "Aligner Change", "Adjustment",
                  "Refinement", "Retention Start", "Retainer Check", "Completion / Deband"].map(p => (
                  <SelectItem key={p} value={p}>{p}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Step / Aligner # (optional)</Label>
            <Input type="number" value={form.step} onChange={e => setForm(f => ({ ...f, step: e.target.value }))} placeholder="e.g. 12" />
          </div>
          <div>
            <Label>Clinical Notes</Label>
            <Textarea value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} rows={3}
              placeholder="Tooth movement, patient feedback, next steps…" data-testid="textarea-progress-notes" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={() => mut.mutate()} disabled={mut.isPending} data-testid="button-save-progress">
            {mut.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4 mr-1" />}
            Save Progress
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ─── Case Detail ──────────────────────────────────────────────────────────
function CaseDetail({ orthoCase, patients, onClose, onAddProgress }: {
  orthoCase: OrthoCase; patients: any[]; onClose: () => void; onAddProgress: () => void;
}) {
  const patient = patients.find((p: any) => p.id === orthoCase.patientId);
  const log = [...(orthoCase.progressLog || [])].reverse();
  const pct = orthoCase.totalSteps ? Math.round((orthoCase.currentStep / orthoCase.totalSteps) * 100) : 0;
  const totalFee = parseFloat(orthoCase.totalFee || "0");
  const paid = parseFloat(orthoCase.amountPaid || "0");
  const insurance = parseFloat(orthoCase.insuranceCoverage || "0");
  const balance = totalFee - paid - insurance;
  const cfg = STATUS_CONFIG[orthoCase.status] || STATUS_CONFIG.active;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold">{patient?.firstName} {patient?.lastName}</h2>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-sm text-muted-foreground">{orthoCase.treatmentType}</span>
            <Badge className={`text-[10px] px-1.5 border ${cfg.bg} ${cfg.color}`}>{cfg.label}</Badge>
          </div>
        </div>
        <div className="flex gap-2">
          <Button size="sm" onClick={onAddProgress} data-testid="button-add-progress-detail">
            <Plus className="h-3.5 w-3.5 mr-1" /> Add Progress
          </Button>
          <Button variant="outline" size="sm" onClick={onClose}>← Back</Button>
        </div>
      </div>

      {/* Progress bar */}
      {orthoCase.totalSteps && (
        <Card>
          <CardContent className="pt-4 pb-4">
            <div className="flex justify-between mb-2">
              <span className="text-sm font-medium">Treatment Progress</span>
              <span className="text-sm font-bold text-primary">Step {orthoCase.currentStep} / {orthoCase.totalSteps} ({pct}%)</span>
            </div>
            <Progress value={pct} className="h-3" />
            <div className="flex justify-between mt-2 text-xs text-muted-foreground">
              <span>Started: {orthoCase.startDate}</span>
              {orthoCase.estimatedEndDate && <span>Est. completion: {orthoCase.estimatedEndDate}</span>}
            </div>
          </CardContent>
        </Card>
      )}

      <Tabs defaultValue="timeline">
        <TabsList>
          <TabsTrigger value="timeline">Timeline ({(orthoCase.progressLog || []).length})</TabsTrigger>
          <TabsTrigger value="financial">Financial</TabsTrigger>
          <TabsTrigger value="notes">Notes</TabsTrigger>
        </TabsList>

        <TabsContent value="timeline" className="mt-3">
          {log.length === 0 ? (
            <Card className="border-dashed">
              <CardContent className="py-8 text-center">
                <FileText className="h-8 w-8 mx-auto opacity-30 mb-2" />
                <p className="text-sm text-muted-foreground">No progress notes yet. Add the first progress entry.</p>
              </CardContent>
            </Card>
          ) : (
            <div className="relative pl-5 border-l-2 border-primary/20 space-y-4">
              {log.map((entry, i) => (
                <div key={entry.id || i} className="relative" data-testid={`progress-entry-${i}`}>
                  <div className="absolute -left-[22px] top-1 w-4 h-4 rounded-full bg-primary/20 border-2 border-primary" />
                  <div className="bg-muted/30 rounded-lg p-3">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-bold text-primary">{entry.phase}</span>
                      <span className="text-[10px] text-muted-foreground">{entry.date}</span>
                    </div>
                    {entry.step && (
                      <span className="text-[10px] bg-primary/10 text-primary px-1.5 py-0.5 rounded font-mono mr-2">Step {entry.step}</span>
                    )}
                    <p className="text-sm mt-1 text-muted-foreground">{entry.notes}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="financial" className="mt-3 space-y-4">
          <div className="grid grid-cols-3 gap-4">
            {[
              { label: "Total Fee", value: `$${totalFee.toLocaleString()}`, color: "" },
              { label: "Paid (+ Insurance)", value: `$${(paid + insurance).toLocaleString()}`, color: "text-emerald-600 dark:text-emerald-400" },
              { label: "Balance", value: `$${balance.toLocaleString()}`, color: balance > 0 ? "text-amber-600 dark:text-amber-400" : "text-emerald-600 dark:text-emerald-400" },
            ].map(item => (
              <Card key={item.label}>
                <CardContent className="pt-4 pb-4">
                  <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">{item.label}</div>
                  <div className={`text-xl font-bold font-mono ${item.color}`}>{item.value}</div>
                </CardContent>
              </Card>
            ))}
          </div>
          <Card>
            <CardContent className="pt-4 pb-4">
              <div className="flex justify-between text-sm mb-2">
                <span className="text-muted-foreground">Payment Progress</span>
                <span className="font-medium">{Math.round(((paid + insurance) / Math.max(totalFee, 1)) * 100)}%</span>
              </div>
              <Progress value={Math.round(((paid + insurance) / Math.max(totalFee, 1)) * 100)} className="h-3" />
              <div className="flex justify-between mt-2 text-xs text-muted-foreground">
                <span>Patient: ${paid.toLocaleString()}</span>
                <span>Insurance: ${insurance.toLocaleString()}</span>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="notes" className="mt-3">
          <Card>
            <CardContent className="pt-4">
              <p className="text-sm text-muted-foreground whitespace-pre-wrap">{orthoCase.notes || "No additional notes recorded."}</p>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

// ─── Case Card ────────────────────────────────────────────────────────────
function CaseCard({ orthoCase, patients, onSelect, onAddProgress, onStatusChange }: {
  orthoCase: OrthoCase; patients: any[];
  onSelect: () => void; onAddProgress: () => void; onStatusChange: (s: string) => void;
}) {
  const patient = patients.find((p: any) => p.id === orthoCase.patientId);
  const pct = orthoCase.totalSteps ? Math.round((orthoCase.currentStep / orthoCase.totalSteps) * 100) : 0;
  const remaining = monthsRemaining(orthoCase.estimatedEndDate);
  const cfg = STATUS_CONFIG[orthoCase.status] || STATUS_CONFIG.active;
  const totalFee = parseFloat(orthoCase.totalFee || "0");
  const paid = parseFloat(orthoCase.amountPaid || "0");
  const insurance = parseFloat(orthoCase.insuranceCoverage || "0");
  const balance = totalFee - paid - insurance;

  return (
    <Card className="hover:border-primary/40 transition-colors" data-testid={`card-ortho-${orthoCase.id}`}>
      <CardContent className="pt-4 pb-4">
        <div className="flex items-start justify-between mb-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold">{patient ? `${patient.firstName} ${patient.lastName}` : `Patient #${orthoCase.patientId}`}</span>
              <Badge className={`text-[10px] px-1.5 border ${cfg.bg} ${cfg.color}`}>{cfg.label}</Badge>
            </div>
            <div className="text-xs text-muted-foreground mt-0.5 flex items-center gap-2">
              <Smile className="h-3 w-3" />
              {orthoCase.treatmentType}
              {orthoCase.archesType !== "both" && <span className="capitalize">· {orthoCase.archesType} arch</span>}
              {orthoCase.extractionsRequired && (
                <span className="flex items-center gap-0.5 text-amber-600 dark:text-amber-400"><Scissors className="h-3 w-3" />Extractions</span>
              )}
            </div>
          </div>
          <div className="flex gap-1.5">
            <Button size="sm" variant="outline" onClick={onAddProgress} data-testid={`button-add-progress-${orthoCase.id}`}>
              <Plus className="h-3.5 w-3.5 mr-1" />Progress
            </Button>
            <Button size="sm" variant="ghost" onClick={onSelect} data-testid={`button-view-${orthoCase.id}`}>
              <ChevronRight className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>

        {orthoCase.totalSteps && (
          <div className="mb-3">
            <div className="flex justify-between items-center mb-1">
              <span className="text-xs text-muted-foreground">
                Step {orthoCase.currentStep} / {orthoCase.totalSteps}
              </span>
              <span className="text-xs font-bold text-primary">{pct}%</span>
            </div>
            <Progress value={pct} className="h-2" />
          </div>
        )}

        <div className="grid grid-cols-3 gap-3 text-xs">
          <div>
            <span className="text-[10px] text-muted-foreground uppercase tracking-wider block">Compliance</span>
            <span className={`font-bold text-base font-mono ${complianceColor(orthoCase.compliance)}`}>{orthoCase.compliance}%</span>
          </div>
          <div>
            <span className="text-[10px] text-muted-foreground uppercase tracking-wider block">Est. End</span>
            <span className="font-semibold">{orthoCase.estimatedEndDate || "TBD"}</span>
            {remaining !== null && (
              <span className="block text-[10px] text-muted-foreground">{remaining > 0 ? `${remaining}mo left` : "Overdue"}</span>
            )}
          </div>
          <div>
            <span className="text-[10px] text-muted-foreground uppercase tracking-wider block">Balance</span>
            <span className={`font-bold text-base font-mono ${balance > 0 ? "text-amber-600 dark:text-amber-400" : "text-emerald-600 dark:text-emerald-400"}`}>
              ${balance.toLocaleString()}
            </span>
          </div>
        </div>

        <div className="mt-3 pt-3 border-t flex items-center gap-2 flex-wrap">
          <span className="text-[10px] text-muted-foreground">Move to:</span>
          {Object.entries(STATUS_CONFIG).filter(([k]) => k !== orthoCase.status).map(([key, val]) => (
            <button
              key={key}
              onClick={() => onStatusChange(key)}
              className={`text-[10px] px-2 py-0.5 rounded border ${val.bg} ${val.color} hover:opacity-80`}
              data-testid={`button-status-${key}-${orthoCase.id}`}
            >
              → {val.label}
            </button>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

// ─── Main Page ─────────────────────────────────────────────────────────────
export default function OrthoTrackerPage() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [newCaseOpen, setNewCaseOpen] = useState(false);
  const [progressCaseId, setProgressCaseId] = useState<number | null>(null);
  const [selectedCase, setSelectedCase] = useState<OrthoCase | null>(null);
  const [filterStatus, setFilterStatus] = useState("all");

  const { data: patients = [] } = useQuery<any[]>({ queryKey: ["/api/patients"] });
  const { data: allCases = [], isLoading } = useQuery<OrthoCase[]>({
    queryKey: ["/api/ortho"],
    queryFn: () => fetch("/api/ortho", { credentials: "include" }).then(r => r.json()),
  });

  const statusMut = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      apiRequest("PUT", `/api/ortho/${id}`, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/ortho"] });
      toast({ title: "Status updated" });
    },
  });

  const refreshCase = () => {
    queryClient.invalidateQueries({ queryKey: ["/api/ortho"] });
    if (selectedCase) {
      fetch(`/api/ortho/${selectedCase.id}`, { credentials: "include" })
        .then(r => r.json())
        .then(setSelectedCase);
    }
  };

  const filtered = filterStatus === "all" ? allCases : allCases.filter(c => c.status === filterStatus);
  const active = allCases.filter(c => c.status === "active").length;
  const retention = allCases.filter(c => c.status === "retention").length;
  const avgCompliance = allCases.length
    ? Math.round(allCases.reduce((a, c) => a + (c.compliance || 0), 0) / allCases.length)
    : 0;
  const totalValue = allCases.reduce((a, c) => a + parseFloat(c.totalFee || "0"), 0);

  const progressCase = progressCaseId ? allCases.find(c => c.id === progressCaseId) : null;

  if (selectedCase) {
    return (
      <div className="space-y-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">Ortho Case Detail</h1>
          <p className="text-sm text-muted-foreground">Treatment timeline, financial summary, and progress log</p>
        </div>
        <CaseDetail
          orthoCase={selectedCase}
          patients={patients}
          onClose={() => setSelectedCase(null)}
          onAddProgress={() => setProgressCaseId(selectedCase.id)}
        />
        {progressCase && (
          <AddProgressDialog
            caseId={progressCase.id}
            currentLog={progressCase.progressLog || []}
            open={!!progressCaseId}
            onClose={() => setProgressCaseId(null)}
            onSaved={refreshCase}
          />
        )}
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">Ortho Case Tracker</h1>
          <p className="text-sm text-muted-foreground">Invisalign · Braces · Retention · Progress tracking · Financial management</p>
        </div>
        <Button onClick={() => setNewCaseOpen(true)} data-testid="button-new-case">
          <Plus className="h-4 w-4 mr-1.5" /> New Case
        </Button>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Active Cases", value: active, icon: Activity, color: "text-blue-600 dark:text-blue-400" },
          { label: "In Retention", value: retention, icon: RotateCcw, color: "text-purple-600 dark:text-purple-400" },
          { label: "Avg Compliance", value: `${avgCompliance}%`, icon: Star, color: complianceColor(avgCompliance) },
          { label: "Total Case Value", value: `$${(totalValue / 1000).toFixed(0)}k`, icon: DollarSign, color: "" },
        ].map(k => (
          <Card key={k.label}>
            <CardContent className="pt-4 pb-4">
              <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground uppercase tracking-wider mb-1">
                <k.icon className="h-3 w-3" />{k.label}
              </div>
              <div className={`text-2xl font-bold font-mono ${k.color}`} data-testid={`kpi-${k.label.toLowerCase().replace(/ /g, "-")}`}>
                {k.value}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Status Filters */}
      <div className="flex items-center gap-2 flex-wrap">
        {["all", "active", "retention", "completed", "discontinued"].map(s => (
          <button
            key={s}
            onClick={() => setFilterStatus(s)}
            className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
              filterStatus === s
                ? "bg-primary text-primary-foreground border-primary"
                : "border-border text-muted-foreground hover:border-primary/50"
            }`}
            data-testid={`filter-${s}`}
          >
            {s === "all"
              ? `All (${allCases.length})`
              : `${STATUS_CONFIG[s]?.label} (${allCases.filter(c => c.status === s).length})`}
          </button>
        ))}
      </div>

      {/* Case List */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12"><Loader2 className="h-6 w-6 animate-spin" /></div>
      ) : filtered.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="pt-12 pb-12 flex flex-col items-center gap-3 text-muted-foreground">
            <Smile className="h-10 w-10 opacity-30" />
            <p className="text-sm">No orthodontic cases{filterStatus !== "all" ? ` with status "${filterStatus}"` : ""} — create one to get started</p>
            <Button onClick={() => setNewCaseOpen(true)} variant="outline" size="sm">
              <Plus className="h-4 w-4 mr-1" /> New Case
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {filtered.map(c => (
            <CaseCard
              key={c.id}
              orthoCase={c}
              patients={patients}
              onSelect={() => setSelectedCase(c)}
              onAddProgress={() => setProgressCaseId(c.id)}
              onStatusChange={status => statusMut.mutate({ id: c.id, status })}
            />
          ))}
        </div>
      )}

      <NewCaseDialog
        patients={patients}
        open={newCaseOpen}
        onClose={() => setNewCaseOpen(false)}
        onSaved={() => queryClient.invalidateQueries({ queryKey: ["/api/ortho"] })}
      />

      {progressCase && (
        <AddProgressDialog
          caseId={progressCase.id}
          currentLog={progressCase.progressLog || []}
          open={!!progressCaseId}
          onClose={() => setProgressCaseId(null)}
          onSaved={() => queryClient.invalidateQueries({ queryKey: ["/api/ortho"] })}
        />
      )}
    </div>
  );
}
