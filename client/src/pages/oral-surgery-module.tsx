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
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/hooks/use-toast";
import { apiRequest } from "@/lib/queryClient";
import {
  Syringe, Plus, Save, Loader2, CheckCircle, AlertTriangle,
  Clock, ChevronRight, FileText, Shield, CalendarDays,
} from "lucide-react";

interface OralSurgeryCase {
  id: number; patientId: number;
  procedureType: string; teeth: string | null; surgeryDate: string;
  surgeon: string | null; anesthesia: string; status: string;
  preOpNotes: string | null; medicalClearance: boolean; consentSigned: boolean;
  operativeFindings: string | null; complications: string | null;
  surgeryDuration: number | null; postOpInstructions: string | null;
  medicationsPrescribed: string | null; followUpDate: string | null;
  healingStatus: string | null; cdtCode: string | null; fee: string | null; notes: string | null;
}

const PROCEDURE_TYPES = [
  { value: "simple_extraction", label: "Simple Extraction", cdt: "D7140" },
  { value: "surgical_extraction", label: "Surgical Extraction", cdt: "D7210" },
  { value: "wisdom_tooth_soft", label: "Wisdom Tooth - Soft Tissue", cdt: "D7240" },
  { value: "wisdom_tooth_partial", label: "Wisdom Tooth - Partial Bony", cdt: "D7241" },
  { value: "wisdom_tooth_complete", label: "Wisdom Tooth - Complete Bony", cdt: "D7240" },
  { value: "implant_placement", label: "Implant Placement", cdt: "D6010" },
  { value: "bone_graft", label: "Bone Graft / Augmentation", cdt: "D7953" },
  { value: "sinus_lift_lateral", label: "Sinus Lift - Lateral Window", cdt: "D7310" },
  { value: "sinus_lift_crestal", label: "Sinus Lift - Crestal", cdt: "D7320" },
  { value: "all_on_4", label: "All-on-4 Full Arch", cdt: "D6114" },
  { value: "all_on_6", label: "All-on-6 Full Arch", cdt: "D6114" },
  { value: "biopsy", label: "Soft Tissue Biopsy", cdt: "D7286" },
  { value: "frenectomy", label: "Frenectomy", cdt: "D7960" },
  { value: "alveoloplasty", label: "Alveoloplasty", cdt: "D7310" },
  { value: "tori_removal", label: "Torus Removal", cdt: "D7472" },
  { value: "apicoectomy", label: "Apicoectomy", cdt: "D3410" },
];

const STATUS_CFG: Record<string, { label: string; color: string; bg: string; icon: any }> = {
  planned:          { label: "Planned",          color: "text-blue-600 dark:text-blue-400",    bg: "bg-blue-500/10 border-blue-400/40",    icon: Clock },
  completed:        { label: "Completed",         color: "text-emerald-600 dark:text-emerald-400", bg: "bg-emerald-500/10 border-emerald-400/40", icon: CheckCircle },
  follow_up_needed: { label: "Follow-Up Needed",  color: "text-amber-600 dark:text-amber-400",  bg: "bg-amber-500/10 border-amber-400/40",  icon: AlertTriangle },
  cancelled:        { label: "Cancelled",         color: "text-gray-500",                       bg: "bg-gray-500/10 border-gray-400/30",    icon: AlertTriangle },
};

function NewCaseDialog({ patients, open, onClose, onSaved }: {
  patients: any[]; open: boolean; onClose: () => void; onSaved: () => void;
}) {
  const { toast } = useToast();
  const [form, setForm] = useState({
    patientId: "", procedureType: "simple_extraction", teeth: "", surgeryDate: new Date().toISOString().split("T")[0],
    surgeon: "", anesthesia: "local", status: "planned",
    preOpNotes: "", medicalClearance: false, consentSigned: false,
    operativeFindings: "", complications: "", surgeryDuration: "",
    postOpInstructions: "", medicationsPrescribed: "", followUpDate: "",
    healingStatus: "normal", notes: "", fee: "",
  });

  const procInfo = PROCEDURE_TYPES.find(p => p.value === form.procedureType);

  const mut = useMutation({
    mutationFn: () => apiRequest("POST", "/api/oral-surgery", {
      ...form,
      patientId: parseInt(form.patientId),
      cdtCode: procInfo?.cdt || null,
      surgeryDuration: form.surgeryDuration ? parseInt(form.surgeryDuration) : null,
      fee: form.fee || null,
      followUpDate: form.followUpDate || null,
      teeth: form.teeth || null,
    }),
    onSuccess: () => { toast({ title: "Surgery case created" }); onSaved(); onClose(); },
    onError: () => toast({ title: "Error", variant: "destructive" }),
  });

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><Syringe className="h-4 w-4" /> New Oral Surgery Case</DialogTitle>
        </DialogHeader>
        <Tabs defaultValue="preop">
          <TabsList>
            <TabsTrigger value="preop">Pre-Op</TabsTrigger>
            <TabsTrigger value="intraop">Intra-Op</TabsTrigger>
            <TabsTrigger value="postop">Post-Op</TabsTrigger>
          </TabsList>

          <TabsContent value="preop" className="space-y-3 pt-3">
            <div>
              <Label>Patient *</Label>
              <Select value={form.patientId} onValueChange={v => setForm(f => ({ ...f, patientId: v }))}>
                <SelectTrigger data-testid="select-patient-surgery"><SelectValue placeholder="Select patient…" /></SelectTrigger>
                <SelectContent>{patients.map((p: any) => <SelectItem key={p.id} value={p.id.toString()}>{p.firstName} {p.lastName}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Procedure *</Label>
                <Select value={form.procedureType} onValueChange={v => setForm(f => ({ ...f, procedureType: v }))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>{PROCEDURE_TYPES.map(p => <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>)}</SelectContent>
                </Select>
                {procInfo && <p className="text-[10px] text-muted-foreground mt-0.5">CDT: {procInfo.cdt}</p>}
              </div>
              <div>
                <Label>Surgery Date</Label>
                <Input type="date" value={form.surgeryDate} onChange={e => setForm(f => ({ ...f, surgeryDate: e.target.value }))} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Teeth Involved</Label>
                <Input value={form.teeth} onChange={e => setForm(f => ({ ...f, teeth: e.target.value }))} placeholder="#1, 16, 17, 32" />
              </div>
              <div>
                <Label>Surgeon</Label>
                <Input value={form.surgeon} onChange={e => setForm(f => ({ ...f, surgeon: e.target.value }))} placeholder="Dr. Smith, DDS" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Anesthesia</Label>
                <Select value={form.anesthesia} onValueChange={v => setForm(f => ({ ...f, anesthesia: v }))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="local">Local Only</SelectItem>
                    <SelectItem value="local_sedation">Local + Oral Sedation</SelectItem>
                    <SelectItem value="iv_sedation">IV Sedation</SelectItem>
                    <SelectItem value="ga">General Anesthesia</SelectItem>
                    <SelectItem value="nitrous">Local + Nitrous</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Fee ($)</Label>
                <Input type="number" value={form.fee} onChange={e => setForm(f => ({ ...f, fee: e.target.value }))} />
              </div>
            </div>
            <div className="space-y-2">
              {[
                { key: "medicalClearance", label: "Medical Clearance Obtained" },
                { key: "consentSigned", label: "Informed Consent Signed" },
              ].map(item => (
                <div key={item.key} className="flex items-center justify-between px-3 py-2 rounded border">
                  <span className="text-sm flex items-center gap-2"><Shield className="h-3.5 w-3.5 text-primary" />{item.label}</span>
                  <Switch checked={(form as any)[item.key]} onCheckedChange={v => setForm(f => ({ ...f, [item.key]: v }))} />
                </div>
              ))}
            </div>
            <div>
              <Label>Pre-Op Notes</Label>
              <Textarea value={form.preOpNotes} onChange={e => setForm(f => ({ ...f, preOpNotes: e.target.value }))} rows={2} />
            </div>
          </TabsContent>

          <TabsContent value="intraop" className="space-y-3 pt-3">
            <div>
              <Label>Operative Findings</Label>
              <Textarea value={form.operativeFindings} onChange={e => setForm(f => ({ ...f, operativeFindings: e.target.value }))} rows={3} data-testid="textarea-operative-findings" />
            </div>
            <div>
              <Label>Complications</Label>
              <Textarea value={form.complications} onChange={e => setForm(f => ({ ...f, complications: e.target.value }))} rows={2} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Surgery Duration (min)</Label>
                <Input type="number" value={form.surgeryDuration} onChange={e => setForm(f => ({ ...f, surgeryDuration: e.target.value }))} placeholder="90" />
              </div>
              <div>
                <Label>Status</Label>
                <Select value={form.status} onValueChange={v => setForm(f => ({ ...f, status: v }))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="planned">Planned</SelectItem>
                    <SelectItem value="completed">Completed</SelectItem>
                    <SelectItem value="follow_up_needed">Follow-Up Needed</SelectItem>
                    <SelectItem value="cancelled">Cancelled</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </TabsContent>

          <TabsContent value="postop" className="space-y-3 pt-3">
            <div>
              <Label>Post-Op Instructions</Label>
              <Textarea value={form.postOpInstructions} onChange={e => setForm(f => ({ ...f, postOpInstructions: e.target.value }))} rows={3} />
            </div>
            <div>
              <Label>Medications Prescribed</Label>
              <Textarea value={form.medicationsPrescribed} onChange={e => setForm(f => ({ ...f, medicationsPrescribed: e.target.value }))} rows={2} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Follow-Up Date</Label>
                <Input type="date" value={form.followUpDate} onChange={e => setForm(f => ({ ...f, followUpDate: e.target.value }))} />
              </div>
              <div>
                <Label>Healing Status</Label>
                <Select value={form.healingStatus} onValueChange={v => setForm(f => ({ ...f, healingStatus: v }))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="normal">Normal</SelectItem>
                    <SelectItem value="delayed">Delayed</SelectItem>
                    <SelectItem value="complications">Complications</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </TabsContent>
        </Tabs>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={() => mut.mutate()} disabled={mut.isPending || !form.patientId} data-testid="button-save-surgery">
            {mut.isPending ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Save className="h-4 w-4 mr-1" />}
            Save Case
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function OralSurgeryModulePage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [newOpen, setNewOpen] = useState(false);
  const [filterStatus, setFilterStatus] = useState("all");

  const { data: patients = [] } = useQuery<any[]>({ queryKey: ["/api/patients"] });
  const { data: allCases = [], isLoading } = useQuery<OralSurgeryCase[]>({
    queryKey: ["/api/oral-surgery"],
    queryFn: () => fetch("/api/oral-surgery", { credentials: "include" }).then(r => r.json()),
  });

  const statusMut = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) => apiRequest("PUT", `/api/oral-surgery/${id}`, { status }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["/api/oral-surgery"] }); toast({ title: "Updated" }); },
  });

  const filtered = filterStatus === "all" ? allCases : allCases.filter(c => c.status === filterStatus);
  const completed = allCases.filter(c => c.status === "completed").length;
  const followUp = allCases.filter(c => c.status === "follow_up_needed").length;
  const totalFee = allCases.reduce((a, c) => a + parseFloat(c.fee || "0"), 0);

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">Oral Surgery Module</h1>
          <p className="text-sm text-muted-foreground">Extractions, implants, grafts, wisdom teeth, All-on-4/6 surgical cases with full pre/intra/post-op tracking</p>
        </div>
        <Button onClick={() => setNewOpen(true)} data-testid="button-new-surgery">
          <Plus className="h-4 w-4 mr-1.5" /> New Case
        </Button>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Total Cases", value: allCases.length },
          { label: "Completed", value: completed, color: "text-emerald-600 dark:text-emerald-400" },
          { label: "Need Follow-Up", value: followUp, color: followUp > 0 ? "text-amber-600 dark:text-amber-400" : "" },
          { label: "Case Revenue", value: `$${(totalFee / 1000).toFixed(0)}k` },
        ].map(k => (
          <Card key={k.label}>
            <CardContent className="pt-4 pb-4">
              <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">{k.label}</div>
              <div className={`text-2xl font-bold font-mono ${k.color || ""}`} data-testid={`kpi-${k.label.toLowerCase().replace(/ /g, "-")}`}>{k.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="flex gap-2 flex-wrap">
        {["all", "planned", "completed", "follow_up_needed", "cancelled"].map(s => (
          <button
            key={s}
            onClick={() => setFilterStatus(s)}
            className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
              filterStatus === s ? "bg-primary text-primary-foreground border-primary" : "border-border text-muted-foreground hover:border-primary/50"
            }`}
            data-testid={`filter-${s}`}
          >
            {s === "all" ? `All (${allCases.length})` : `${STATUS_CFG[s]?.label || s} (${allCases.filter(c => c.status === s).length})`}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-12"><Loader2 className="h-6 w-6 animate-spin" /></div>
      ) : filtered.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="pt-12 pb-12 flex flex-col items-center gap-3 text-muted-foreground">
            <Syringe className="h-10 w-10 opacity-30" />
            <p className="text-sm">No oral surgery cases — create the first case</p>
            <Button onClick={() => setNewOpen(true)} variant="outline" size="sm"><Plus className="h-4 w-4 mr-1" /> New Case</Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map(c => {
            const patient = patients.find((p: any) => p.id === c.patientId);
            const proc = PROCEDURE_TYPES.find(p => p.value === c.procedureType);
            const cfg = STATUS_CFG[c.status] || STATUS_CFG.planned;
            const Icon = cfg.icon;
            return (
              <Card key={c.id} className="hover:border-primary/30 transition-colors" data-testid={`card-surgery-${c.id}`}>
                <CardContent className="pt-4 pb-4">
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <div className="font-semibold">{patient ? `${patient.firstName} ${patient.lastName}` : `Patient #${c.patientId}`}</div>
                      <div className="text-xs text-muted-foreground mt-0.5">{c.surgeryDate} · {c.surgeon || "—"}</div>
                    </div>
                    <Badge className={`text-[10px] px-1.5 border ${cfg.bg} ${cfg.color}`}>{cfg.label}</Badge>
                  </div>
                  <div className="space-y-1 text-xs text-muted-foreground">
                    <div className="flex justify-between">
                      <span>Procedure:</span>
                      <span className="font-medium text-foreground">{proc?.label || c.procedureType}</span>
                    </div>
                    {c.teeth && <div className="flex justify-between"><span>Teeth:</span><span className="font-mono font-medium text-primary">{c.teeth}</span></div>}
                    <div className="flex justify-between">
                      <span>CDT:</span>
                      <span className="font-mono text-primary">{c.cdtCode || proc?.cdt || "—"}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Anesthesia:</span>
                      <span className="capitalize font-medium text-foreground">{c.anesthesia.replace(/_/g, " ")}</span>
                    </div>
                    {c.fee && (
                      <div className="flex justify-between">
                        <span>Fee:</span>
                        <span className="font-bold text-foreground">${parseFloat(c.fee).toLocaleString()}</span>
                      </div>
                    )}
                  </div>
                  <div className="flex gap-1 mt-3 flex-wrap">
                    {c.medicalClearance && <Badge variant="outline" className="text-[10px] text-emerald-600 border-emerald-400/30">Med Clearance ✓</Badge>}
                    {c.consentSigned && <Badge variant="outline" className="text-[10px] text-blue-600 border-blue-400/30">Consent ✓</Badge>}
                    {c.complications && <Badge variant="outline" className="text-[10px] text-amber-600 border-amber-400/30">Complications</Badge>}
                  </div>
                  <div className="flex gap-1.5 mt-3 pt-3 border-t flex-wrap">
                    {c.status === "planned" && (
                      <button onClick={() => statusMut.mutate({ id: c.id, status: "completed" })}
                        className="text-[10px] px-2 py-1 rounded border border-emerald-400/40 text-emerald-600 hover:bg-emerald-500/10"
                        data-testid={`complete-${c.id}`}>
                        Mark Complete
                      </button>
                    )}
                    {c.status === "completed" && !c.followUpDate && (
                      <button onClick={() => statusMut.mutate({ id: c.id, status: "follow_up_needed" })}
                        className="text-[10px] px-2 py-1 rounded border border-amber-400/40 text-amber-600 hover:bg-amber-500/10"
                        data-testid={`followup-${c.id}`}>
                        Flag Follow-Up
                      </button>
                    )}
                    {c.followUpDate && (
                      <span className="text-[10px] text-muted-foreground flex items-center gap-1">
                        <CalendarDays className="h-3 w-3" /> F/U: {c.followUpDate}
                      </span>
                    )}
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      <NewCaseDialog patients={patients} open={newOpen} onClose={() => setNewOpen(false)} onSaved={() => queryClient.invalidateQueries({ queryKey: ["/api/oral-surgery"] })} />
    </div>
  );
}
