import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/hooks/use-toast";
import { apiRequest } from "@/lib/queryClient";
import {
  Activity, Plus, Save, Loader2, User, ChevronRight, FileText,
  CheckCircle, AlertTriangle, Clock, Zap,
} from "lucide-react";

// ─── Types ─────────────────────────────────────────────────────────────────
interface EndoCase {
  id: number;
  patientId: number;
  toothNumber: number;
  toothName: string | null;
  diagnosis: string;
  diagnosisIcd10: string | null;
  procedure: string;
  procedureCdt: string | null;
  status: string;
  startDate: string;
  completionDate: string | null;
  referredBy: string | null;
  referredTo: string | null;
  providerName: string | null;
  canalData: Record<string, CanalInfo>;
  visitLog: VisitEntry[];
  workingLength: string | null;
  masterApicalFile: string | null;
  obturationMethod: string | null;
  irrigant: string | null;
  sealer: string | null;
  restorationPlan: string | null;
  prognosis: string | null;
  notes: string | null;
  totalFee: string | null;
  insuranceFiled: boolean;
}

interface CanalInfo {
  length?: string;
  file?: string;
  obturation?: string;
  notes?: string;
}

interface VisitEntry {
  id: string;
  date: string;
  visit: string;
  notes: string;
}

const DIAGNOSES = [
  { value: "irreversible_pulpitis", label: "Irreversible Pulpitis", icd10: "K04.0" },
  { value: "pulp_necrosis", label: "Pulp Necrosis", icd10: "K04.1" },
  { value: "previously_treated", label: "Previously Treated", icd10: "K04.5" },
  { value: "symptomatic_apical_periodontitis", label: "Symptomatic Apical Periodontitis", icd10: "K04.4" },
  { value: "asymptomatic_apical_periodontitis", label: "Asymptomatic Apical Periodontitis", icd10: "K04.5" },
  { value: "chronic_apical_abscess", label: "Chronic Apical Abscess", icd10: "K04.6" },
  { value: "acute_apical_abscess", label: "Acute Apical Abscess", icd10: "K04.7" },
  { value: "reversible_pulpitis", label: "Reversible Pulpitis", icd10: "K04.0" },
];

const PROCEDURES = [
  { value: "rct_anterior", label: "RCT — Anterior (1 canal)", cdt: "D3310" },
  { value: "rct_premolar", label: "RCT — Premolar (2 canals)", cdt: "D3320" },
  { value: "rct_molar", label: "RCT — Molar (3+ canals)", cdt: "D3330" },
  { value: "retreatment_anterior", label: "Retreatment — Anterior", cdt: "D3346" },
  { value: "retreatment_premolar", label: "Retreatment — Premolar", cdt: "D3347" },
  { value: "retreatment_molar", label: "Retreatment — Molar", cdt: "D3348" },
  { value: "pulpotomy", label: "Pulpotomy", cdt: "D3220" },
  { value: "pulpectomy", label: "Pulpectomy", cdt: "D3221" },
  { value: "apicoectomy", label: "Apicoectomy", cdt: "D3410" },
];

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string; icon: any }> = {
  in_progress:  { label: "In Progress", color: "text-blue-600 dark:text-blue-400",    bg: "bg-blue-500/10 border-blue-400/40",    icon: Clock },
  completed:    { label: "Completed",   color: "text-emerald-600 dark:text-emerald-400", bg: "bg-emerald-500/10 border-emerald-400/40", icon: CheckCircle },
  referred_out: { label: "Referred Out", color: "text-amber-600 dark:text-amber-400",  bg: "bg-amber-500/10 border-amber-400/40",  icon: ChevronRight },
  failed:       { label: "Failed",      color: "text-red-600 dark:text-red-400",       bg: "bg-red-500/10 border-red-400/40",       icon: AlertTriangle },
};

// Canal names by typical tooth type
function getCanals(toothNumber: number): string[] {
  if ([1,2,3,6,7,8,9,10,11,14,22,23,24,25,26,27,30].includes(toothNumber)) return ["Canal 1"];
  if ([4,5,12,13,20,21,28,29].includes(toothNumber)) return ["MB", "DB"];
  return ["MB", "DB", "ML"]; // molars
}

// ─── Canal Table ────────────────────────────────────────────────────────────
function CanalTable({ toothNumber, canalData, onChange }: {
  toothNumber: number;
  canalData: Record<string, CanalInfo>;
  onChange: (data: Record<string, CanalInfo>) => void;
}) {
  const canals = getCanals(toothNumber);
  return (
    <div className="rounded-lg border overflow-hidden">
      <table className="w-full text-xs">
        <thead className="bg-muted/50">
          <tr>
            <th className="text-left p-2 font-semibold">Canal</th>
            <th className="text-left p-2 font-semibold">Working Length</th>
            <th className="text-left p-2 font-semibold">MAF</th>
            <th className="text-left p-2 font-semibold">Obturation</th>
          </tr>
        </thead>
        <tbody>
          {canals.map(canal => {
            const info = canalData[canal] || {};
            return (
              <tr key={canal} className="border-t">
                <td className="p-2 font-bold text-primary">{canal}</td>
                <td className="p-2">
                  <Input
                    className="h-7 text-xs"
                    value={info.length || ""}
                    onChange={e => onChange({ ...canalData, [canal]: { ...info, length: e.target.value } })}
                    placeholder="mm"
                    data-testid={`canal-length-${canal}`}
                  />
                </td>
                <td className="p-2">
                  <Input
                    className="h-7 text-xs"
                    value={info.file || ""}
                    onChange={e => onChange({ ...canalData, [canal]: { ...info, file: e.target.value } })}
                    placeholder="#"
                    data-testid={`canal-file-${canal}`}
                  />
                </td>
                <td className="p-2">
                  <Select value={info.obturation || ""} onValueChange={v => onChange({ ...canalData, [canal]: { ...info, obturation: v } })}>
                    <SelectTrigger className="h-7 text-xs"><SelectValue placeholder="Method" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="lateral_condensation">Lateral Condensation</SelectItem>
                      <SelectItem value="warm_vertical">Warm Vertical</SelectItem>
                      <SelectItem value="single_cone">Single Cone</SelectItem>
                      <SelectItem value="carrier_based">Carrier-Based</SelectItem>
                    </SelectContent>
                  </Select>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ─── New Case Dialog ─────────────────────────────────────────────────────
function NewCaseDialog({ patients, open, onClose, onSaved }: {
  patients: any[]; open: boolean; onClose: () => void; onSaved: () => void;
}) {
  const { toast } = useToast();
  const [form, setForm] = useState({
    patientId: "", toothNumber: "", toothName: "",
    diagnosis: "irreversible_pulpitis", procedure: "rct_molar",
    status: "in_progress", startDate: new Date().toISOString().split("T")[0],
    providerName: "", referredBy: "", referredTo: "",
    restorationPlan: "crown", prognosis: "good",
    irrigant: "NaOCl + EDTA", sealer: "AH Plus",
    totalFee: "", notes: "",
  });

  const diagInfo = DIAGNOSES.find(d => d.value === form.diagnosis);
  const procInfo = PROCEDURES.find(p => p.value === form.procedure);

  const mut = useMutation({
    mutationFn: () => apiRequest("POST", "/api/endo", {
      ...form,
      patientId: parseInt(form.patientId),
      toothNumber: parseInt(form.toothNumber),
      diagnosisIcd10: diagInfo?.icd10 || "",
      procedureCdt: procInfo?.cdt || "",
      canalData: {}, visitLog: [],
    }),
    onSuccess: () => { toast({ title: "Endo case created" }); onSaved(); onClose(); },
    onError: () => toast({ title: "Error", variant: "destructive" }),
  });

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><Zap className="h-4 w-4" /> New Endo / RCT Case</DialogTitle>
        </DialogHeader>
        <div className="grid grid-cols-2 gap-4 py-2">
          <div className="col-span-2">
            <Label>Patient *</Label>
            <Select value={form.patientId} onValueChange={v => setForm(f => ({ ...f, patientId: v }))}>
              <SelectTrigger data-testid="select-patient-endo"><SelectValue placeholder="Select patient…" /></SelectTrigger>
              <SelectContent>{patients.map((p: any) => <SelectItem key={p.id} value={p.id.toString()}>{p.firstName} {p.lastName}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div>
            <Label>Tooth # *</Label>
            <Input type="number" min="1" max="32" value={form.toothNumber} onChange={e => setForm(f => ({ ...f, toothNumber: e.target.value }))} placeholder="e.g. 19" data-testid="input-tooth-number" />
          </div>
          <div>
            <Label>Tooth Name</Label>
            <Input value={form.toothName} onChange={e => setForm(f => ({ ...f, toothName: e.target.value }))} placeholder="e.g. Mandibular Left First Molar" />
          </div>
          <div>
            <Label>Diagnosis *</Label>
            <Select value={form.diagnosis} onValueChange={v => setForm(f => ({ ...f, diagnosis: v }))}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>{DIAGNOSES.map(d => <SelectItem key={d.value} value={d.value}>{d.label}</SelectItem>)}</SelectContent>
            </Select>
            {diagInfo && <p className="text-[10px] text-muted-foreground mt-0.5">ICD-10: {diagInfo.icd10}</p>}
          </div>
          <div>
            <Label>Procedure *</Label>
            <Select value={form.procedure} onValueChange={v => setForm(f => ({ ...f, procedure: v }))}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>{PROCEDURES.map(p => <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>)}</SelectContent>
            </Select>
            {procInfo && <p className="text-[10px] text-muted-foreground mt-0.5">CDT: {procInfo.cdt}</p>}
          </div>
          <div>
            <Label>Start Date</Label>
            <Input type="date" value={form.startDate} onChange={e => setForm(f => ({ ...f, startDate: e.target.value }))} />
          </div>
          <div>
            <Label>Status</Label>
            <Select value={form.status} onValueChange={v => setForm(f => ({ ...f, status: v }))}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="in_progress">In Progress</SelectItem>
                <SelectItem value="completed">Completed</SelectItem>
                <SelectItem value="referred_out">Referred Out</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Provider</Label>
            <Input value={form.providerName} onChange={e => setForm(f => ({ ...f, providerName: e.target.value }))} placeholder="Dr. Smith" />
          </div>
          <div>
            <Label>Referred By</Label>
            <Input value={form.referredBy} onChange={e => setForm(f => ({ ...f, referredBy: e.target.value }))} placeholder="Referring provider" />
          </div>
          <div>
            <Label>Restoration Plan</Label>
            <Select value={form.restorationPlan} onValueChange={v => setForm(f => ({ ...f, restorationPlan: v }))}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="crown">PFM/Zirconia Crown</SelectItem>
                <SelectItem value="buildup_crown">Buildup + Crown</SelectItem>
                <SelectItem value="composite">Composite Restoration</SelectItem>
                <SelectItem value="onlay">Onlay</SelectItem>
                <SelectItem value="observation">Observation Only</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Prognosis</Label>
            <Select value={form.prognosis} onValueChange={v => setForm(f => ({ ...f, prognosis: v }))}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="excellent">Excellent</SelectItem>
                <SelectItem value="good">Good</SelectItem>
                <SelectItem value="fair">Fair</SelectItem>
                <SelectItem value="poor">Poor</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Total Fee ($)</Label>
            <Input type="number" value={form.totalFee} onChange={e => setForm(f => ({ ...f, totalFee: e.target.value }))} />
          </div>
          <div className="col-span-2">
            <Label>Notes</Label>
            <Textarea value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} rows={2} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={() => mut.mutate()} disabled={mut.isPending || !form.patientId || !form.toothNumber} data-testid="button-save-endo">
            {mut.isPending ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Save className="h-4 w-4 mr-1" />}
            Create Case
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ─── Case Detail ──────────────────────────────────────────────────────────
function CaseDetail({ endoCase, patients, onClose }: {
  endoCase: EndoCase; patients: any[]; onClose: () => void;
}) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const patient = patients.find((p: any) => p.id === endoCase.patientId);
  const [canalData, setCanalData] = useState<Record<string, CanalInfo>>(endoCase.canalData || {});
  const [visitNote, setVisitNote] = useState({ date: new Date().toISOString().split("T")[0], visit: "Initial", notes: "" });
  const [addingVisit, setAddingVisit] = useState(false);
  const cfg = STATUS_CONFIG[endoCase.status] || STATUS_CONFIG.in_progress;

  const saveCanalsMut = useMutation({
    mutationFn: () => apiRequest("PUT", `/api/endo/${endoCase.id}`, { canalData }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["/api/endo"] }); toast({ title: "Canal data saved" }); },
    onError: () => toast({ title: "Error", variant: "destructive" }),
  });

  const addVisitMut = useMutation({
    mutationFn: () => {
      const entry: VisitEntry = { id: Date.now().toString(), ...visitNote };
      return apiRequest("PUT", `/api/endo/${endoCase.id}`, {
        visitLog: [...(endoCase.visitLog || []), entry],
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/endo"] });
      toast({ title: "Visit logged" });
      setAddingVisit(false);
      setVisitNote({ date: new Date().toISOString().split("T")[0], visit: "Progress", notes: "" });
    },
  });

  const statusMut = useMutation({
    mutationFn: (status: string) => apiRequest("PUT", `/api/endo/${endoCase.id}`, { status }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["/api/endo"] }); toast({ title: "Status updated" }); },
  });

  const diagInfo = DIAGNOSES.find(d => d.value === endoCase.diagnosis);
  const procInfo = PROCEDURES.find(p => p.value === endoCase.procedure);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold">
            Tooth #{endoCase.toothNumber} — {patient?.firstName} {patient?.lastName}
          </h2>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-sm text-muted-foreground">{procInfo?.label || endoCase.procedure}</span>
            <Badge className={`text-[10px] px-1.5 border ${cfg.bg} ${cfg.color}`}>{cfg.label}</Badge>
          </div>
        </div>
        <div className="flex gap-2">
          <div className="flex gap-1">
            {Object.entries(STATUS_CONFIG).filter(([k]) => k !== endoCase.status).map(([key, val]) => (
              <button
                key={key}
                onClick={() => statusMut.mutate(key)}
                className={`text-[10px] px-2 py-1 rounded border ${val.bg} ${val.color} hover:opacity-80`}
                data-testid={`button-status-${key}`}
              >
                → {val.label}
              </button>
            ))}
          </div>
          <Button variant="outline" size="sm" onClick={onClose}>← Back</Button>
        </div>
      </div>

      {/* Summary row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Diagnosis", value: diagInfo?.label || endoCase.diagnosis },
          { label: "ICD-10", value: endoCase.diagnosisIcd10 || diagInfo?.icd10 || "—" },
          { label: "CDT Code", value: endoCase.procedureCdt || procInfo?.cdt || "—" },
          { label: "Prognosis", value: endoCase.prognosis ? endoCase.prognosis.charAt(0).toUpperCase() + endoCase.prognosis.slice(1) : "—" },
        ].map(item => (
          <Card key={item.label}>
            <CardContent className="pt-3 pb-3">
              <div className="text-[10px] text-muted-foreground uppercase tracking-wider">{item.label}</div>
              <div className="text-sm font-semibold mt-0.5">{item.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Tabs defaultValue="canals">
        <TabsList>
          <TabsTrigger value="canals">Canal Data</TabsTrigger>
          <TabsTrigger value="visits">Visit Log ({(endoCase.visitLog || []).length})</TabsTrigger>
          <TabsTrigger value="details">Details</TabsTrigger>
        </TabsList>

        <TabsContent value="canals" className="mt-3 space-y-4">
          <CanalTable
            toothNumber={endoCase.toothNumber}
            canalData={canalData}
            onChange={setCanalData}
          />
          <div className="grid grid-cols-3 gap-4">
            <div>
              <Label className="text-xs">Irrigant</Label>
              <Input defaultValue={endoCase.irrigant || "NaOCl + EDTA"} className="h-8 text-xs mt-1" />
            </div>
            <div>
              <Label className="text-xs">Sealer</Label>
              <Input defaultValue={endoCase.sealer || ""} placeholder="AH Plus" className="h-8 text-xs mt-1" />
            </div>
            <div>
              <Label className="text-xs">Restoration Plan</Label>
              <Input defaultValue={endoCase.restorationPlan || ""} className="h-8 text-xs mt-1" />
            </div>
          </div>
          <Button size="sm" onClick={() => saveCanalsMut.mutate()} disabled={saveCanalsMut.isPending} data-testid="button-save-canals">
            {saveCanalsMut.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" /> : <Save className="h-3.5 w-3.5 mr-1" />}
            Save Canal Data
          </Button>
        </TabsContent>

        <TabsContent value="visits" className="mt-3 space-y-3">
          <Button size="sm" onClick={() => setAddingVisit(v => !v)} data-testid="button-add-visit">
            <Plus className="h-3.5 w-3.5 mr-1" /> Add Visit
          </Button>

          {addingVisit && (
            <Card className="border-primary/30">
              <CardContent className="pt-4 space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label className="text-xs">Date</Label>
                    <Input type="date" value={visitNote.date} onChange={e => setVisitNote(v => ({ ...v, date: e.target.value }))} className="h-8 text-xs mt-1" />
                  </div>
                  <div>
                    <Label className="text-xs">Visit Type</Label>
                    <Select value={visitNote.visit} onValueChange={v => setVisitNote(vn => ({ ...vn, visit: v }))}>
                      <SelectTrigger className="h-8 text-xs mt-1"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {["Initial", "Cleaning & Shaping", "Obturation", "Follow-Up 3mo", "Follow-Up 6mo", "Follow-Up 12mo", "Retreatment", "Apicoectomy"].map(v => (
                          <SelectItem key={v} value={v}>{v}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div>
                  <Label className="text-xs">Notes</Label>
                  <Textarea value={visitNote.notes} onChange={e => setVisitNote(v => ({ ...v, notes: e.target.value }))} rows={2} className="text-xs mt-1" data-testid="textarea-visit-notes" />
                </div>
                <div className="flex gap-2">
                  <Button size="sm" onClick={() => addVisitMut.mutate()} disabled={addVisitMut.isPending} data-testid="button-save-visit">
                    {addVisitMut.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Save Visit"}
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => setAddingVisit(false)}>Cancel</Button>
                </div>
              </CardContent>
            </Card>
          )}

          {(endoCase.visitLog || []).length === 0 ? (
            <p className="text-sm text-muted-foreground italic">No visits logged yet.</p>
          ) : (
            <div className="relative pl-5 border-l-2 border-primary/20 space-y-3">
              {[...(endoCase.visitLog || [])].reverse().map((v, i) => (
                <div key={v.id || i} className="relative">
                  <div className="absolute -left-[22px] top-1 w-4 h-4 rounded-full bg-primary/20 border-2 border-primary" />
                  <div className="bg-muted/30 rounded-lg p-3">
                    <div className="flex justify-between mb-1">
                      <span className="text-xs font-bold text-primary">{v.visit}</span>
                      <span className="text-[10px] text-muted-foreground">{v.date}</span>
                    </div>
                    <p className="text-sm text-muted-foreground">{v.notes}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="details" className="mt-3">
          <Card>
            <CardContent className="pt-4 space-y-2 text-sm">
              {[
                { label: "Tooth", value: `#${endoCase.toothNumber} — ${endoCase.toothName || ""}` },
                { label: "Provider", value: endoCase.providerName || "—" },
                { label: "Referred By", value: endoCase.referredBy || "—" },
                { label: "Start Date", value: endoCase.startDate },
                { label: "Completion", value: endoCase.completionDate || "Pending" },
                { label: "Total Fee", value: endoCase.totalFee ? `$${parseFloat(endoCase.totalFee).toLocaleString()}` : "—" },
                { label: "Insurance Filed", value: endoCase.insuranceFiled ? "Yes" : "No" },
              ].map(item => (
                <div key={item.label} className="flex justify-between py-1 border-b border-border/50 last:border-0">
                  <span className="text-muted-foreground">{item.label}</span>
                  <span className="font-medium">{item.value}</span>
                </div>
              ))}
              {endoCase.notes && (
                <div className="pt-2">
                  <span className="text-xs text-muted-foreground uppercase tracking-wider">Notes</span>
                  <p className="text-sm mt-1">{endoCase.notes}</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

// ─── Main Page ─────────────────────────────────────────────────────────────
export default function EndoTrackerPage() {
  const queryClient = useQueryClient();
  const [newOpen, setNewOpen] = useState(false);
  const [selectedCase, setSelectedCase] = useState<EndoCase | null>(null);
  const [filterStatus, setFilterStatus] = useState("all");

  const { data: patients = [] } = useQuery<any[]>({ queryKey: ["/api/patients"] });
  const { data: allCases = [], isLoading } = useQuery<EndoCase[]>({
    queryKey: ["/api/endo"],
    queryFn: () => fetch("/api/endo", { credentials: "include" }).then(r => r.json()),
  });

  const filtered = filterStatus === "all" ? allCases : allCases.filter(c => c.status === filterStatus);
  const inProgress = allCases.filter(c => c.status === "in_progress").length;
  const completed = allCases.filter(c => c.status === "completed").length;
  const totalRevenue = allCases.reduce((a, c) => a + parseFloat(c.totalFee || "0"), 0);

  // Refresh selected case when data changes
  if (selectedCase) {
    const fresh = allCases.find(c => c.id === selectedCase.id);
    if (fresh && JSON.stringify(fresh) !== JSON.stringify(selectedCase)) {
      setSelectedCase(fresh);
    }
  }

  if (selectedCase) {
    return (
      <div className="space-y-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">Endo Case Detail</h1>
          <p className="text-sm text-muted-foreground">Canal data, visit log, clinical details</p>
        </div>
        <CaseDetail endoCase={selectedCase} patients={patients} onClose={() => setSelectedCase(null)} />
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">Endodontics / RCT Tracker</h1>
          <p className="text-sm text-muted-foreground">Root canal treatments, retreatments, apicoectomies — canal data, visit log, billing codes</p>
        </div>
        <Button onClick={() => setNewOpen(true)} data-testid="button-new-endo">
          <Plus className="h-4 w-4 mr-1.5" /> New Case
        </Button>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "In Progress", value: inProgress, color: "text-blue-600 dark:text-blue-400" },
          { label: "Completed", value: completed, color: "text-emerald-600 dark:text-emerald-400" },
          { label: "Total Cases", value: allCases.length, color: "" },
          { label: "Case Revenue", value: `$${(totalRevenue / 1000).toFixed(0)}k`, color: "" },
        ].map(k => (
          <Card key={k.label}>
            <CardContent className="pt-4 pb-4">
              <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">{k.label}</div>
              <div className={`text-2xl font-bold font-mono ${k.color}`} data-testid={`kpi-${k.label.toLowerCase().replace(/ /g, "-")}`}>{k.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Filters */}
      <div className="flex gap-2 flex-wrap">
        {["all", "in_progress", "completed", "referred_out", "failed"].map(s => (
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
              : `${STATUS_CONFIG[s]?.label || s} (${allCases.filter(c => c.status === s).length})`}
          </button>
        ))}
      </div>

      {/* Cases */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12"><Loader2 className="h-6 w-6 animate-spin" /></div>
      ) : filtered.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="pt-12 pb-12 flex flex-col items-center gap-3 text-muted-foreground">
            <Zap className="h-10 w-10 opacity-30" />
            <p className="text-sm">No endo cases — create one to get started</p>
            <Button onClick={() => setNewOpen(true)} variant="outline" size="sm"><Plus className="h-4 w-4 mr-1" /> New Case</Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map(c => {
            const patient = patients.find((p: any) => p.id === c.patientId);
            const cfg = STATUS_CONFIG[c.status] || STATUS_CONFIG.in_progress;
            const procInfo = PROCEDURES.find(p => p.value === c.procedure);
            const diagInfo = DIAGNOSES.find(d => d.value === c.diagnosis);
            return (
              <Card
                key={c.id}
                className="hover:border-primary/40 transition-colors cursor-pointer"
                onClick={() => setSelectedCase(c)}
                data-testid={`card-endo-${c.id}`}
              >
                <CardContent className="pt-4 pb-4">
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <div className="font-semibold">
                        {patient ? `${patient.firstName} ${patient.lastName}` : `Patient #${c.patientId}`}
                      </div>
                      <div className="text-xs text-muted-foreground flex items-center gap-2 mt-0.5">
                        <span className="font-mono text-primary font-bold">Tooth #{c.toothNumber}</span>
                        {c.toothName && <span>{c.toothName}</span>}
                      </div>
                    </div>
                    <Badge className={`text-[10px] px-1.5 border ${cfg.bg} ${cfg.color}`}>{cfg.label}</Badge>
                  </div>
                  <div className="space-y-1 text-xs text-muted-foreground">
                    <div className="flex justify-between">
                      <span>Diagnosis:</span>
                      <span className="font-medium text-foreground">{diagInfo?.label || c.diagnosis}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Procedure:</span>
                      <span className="font-medium text-foreground">{procInfo?.label || c.procedure}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>CDT:</span>
                      <span className="font-mono font-medium text-primary">{c.procedureCdt || procInfo?.cdt || "—"}</span>
                    </div>
                    {c.prognosis && (
                      <div className="flex justify-between">
                        <span>Prognosis:</span>
                        <span className={`font-medium capitalize ${c.prognosis === "excellent" || c.prognosis === "good" ? "text-emerald-600 dark:text-emerald-400" : "text-amber-600 dark:text-amber-400"}`}>
                          {c.prognosis}
                        </span>
                      </div>
                    )}
                  </div>
                  <div className="flex justify-between items-center mt-3 pt-3 border-t text-xs text-muted-foreground">
                    <span>{c.startDate}</span>
                    <span className="flex items-center gap-1 text-primary hover:underline">
                      View Details <ChevronRight className="h-3 w-3" />
                    </span>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      <NewCaseDialog patients={patients} open={newOpen} onClose={() => setNewOpen(false)} onSaved={() => queryClient.invalidateQueries({ queryKey: ["/api/endo"] })} />
    </div>
  );
}
