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
  Baby, Plus, Save, Loader2, CheckCircle, AlertTriangle,
  Smile, Star, Heart, ChevronRight,
} from "lucide-react";

// Primary tooth chart — 20 teeth labeled A-T (Universal/Numbering System)
const PRIMARY_TEETH: { id: string; name: string; arch: "upper" | "lower" }[] = [
  { id: "A", name: "Upper Right 2nd Molar", arch: "upper" },
  { id: "B", name: "Upper Right 1st Molar", arch: "upper" },
  { id: "C", name: "Upper Right Canine", arch: "upper" },
  { id: "D", name: "Upper Right Lateral", arch: "upper" },
  { id: "E", name: "Upper Right Central", arch: "upper" },
  { id: "F", name: "Upper Left Central", arch: "upper" },
  { id: "G", name: "Upper Left Lateral", arch: "upper" },
  { id: "H", name: "Upper Left Canine", arch: "upper" },
  { id: "I", name: "Upper Left 1st Molar", arch: "upper" },
  { id: "J", name: "Upper Left 2nd Molar", arch: "upper" },
  { id: "K", name: "Lower Left 2nd Molar", arch: "lower" },
  { id: "L", name: "Lower Left 1st Molar", arch: "lower" },
  { id: "M", name: "Lower Left Canine", arch: "lower" },
  { id: "N", name: "Lower Left Lateral", arch: "lower" },
  { id: "O", name: "Lower Left Central", arch: "lower" },
  { id: "P", name: "Lower Right Central", arch: "lower" },
  { id: "Q", name: "Lower Right Lateral", arch: "lower" },
  { id: "R", name: "Lower Right Canine", arch: "lower" },
  { id: "S", name: "Lower Right 1st Molar", arch: "lower" },
  { id: "T", name: "Lower Right 2nd Molar", arch: "lower" },
];

interface ToothStatus { present: boolean; caries: boolean; filling: boolean; extracted: boolean; sealant: boolean; }
type PrimaryTeethMap = Record<string, ToothStatus>;

interface PediatricExam {
  id: number; patientId: number; examDate: string; providerName: string | null;
  primaryTeeth: PrimaryTeethMap;
  thumbSucking: boolean; pacifierUse: boolean; bruxism: boolean; tongueThrustting: boolean;
  dmft: number | null; fluorideTreatment: boolean; fluorideType: string | null;
  bitewingsTaken: boolean; behaviorRating: string | null; nextRecallMonths: number | null;
  clinicalNotes: string | null; treatmentPlan: string | null; parentEducation: string | null;
}

function getToothColor(status: ToothStatus): string {
  if (!status.present) return "bg-gray-200 dark:bg-gray-700 opacity-50";
  if (status.extracted) return "bg-red-200 dark:bg-red-900/50 border-red-400";
  if (status.caries) return "bg-amber-200 dark:bg-amber-900/50 border-amber-400";
  if (status.filling) return "bg-blue-200 dark:bg-blue-900/50 border-blue-400";
  if (status.sealant) return "bg-teal-200 dark:bg-teal-900/50 border-teal-400";
  return "bg-emerald-100 dark:bg-emerald-900/30 border-emerald-300";
}

function PrimaryToothChart({ teeth, onChange }: {
  teeth: PrimaryTeethMap; onChange: (updated: PrimaryTeethMap) => void;
}) {
  const [selected, setSelected] = useState<string | null>(null);
  const upper = PRIMARY_TEETH.filter(t => t.arch === "upper");
  const lower = PRIMARY_TEETH.filter(t => t.arch === "lower");

  const defaultStatus = (): ToothStatus => ({ present: true, caries: false, filling: false, extracted: false, sealant: false });
  const getStatus = (id: string) => teeth[id] || defaultStatus();

  const toggle = (id: string, key: keyof ToothStatus) => {
    const curr = getStatus(id);
    onChange({ ...teeth, [id]: { ...curr, [key]: !curr[key] } });
  };

  return (
    <div className="space-y-2">
      {/* Legend */}
      <div className="flex gap-3 text-[10px] text-muted-foreground flex-wrap mb-2">
        {[
          { color: "bg-emerald-200", label: "Healthy" },
          { color: "bg-amber-200", label: "Caries" },
          { color: "bg-blue-200", label: "Filling" },
          { color: "bg-teal-200", label: "Sealant" },
          { color: "bg-red-200", label: "Extracted" },
          { color: "bg-gray-200 opacity-50", label: "Missing/Absent" },
        ].map(l => (
          <span key={l.label} className="flex items-center gap-1">
            <span className={`w-3 h-3 rounded border ${l.color}`} /> {l.label}
          </span>
        ))}
      </div>

      {/* Upper arch */}
      <div className="text-[10px] text-muted-foreground text-center mb-1">UPPER</div>
      <div className="flex justify-center gap-1 flex-wrap">
        {upper.map(t => {
          const st = getStatus(t.id);
          return (
            <button
              key={t.id}
              onClick={() => setSelected(selected === t.id ? null : t.id)}
              title={t.name}
              className={`w-8 h-8 rounded border-2 text-xs font-bold transition-all ${getToothColor(st)} ${selected === t.id ? "ring-2 ring-primary ring-offset-1 scale-110" : "hover:scale-105"}`}
              data-testid={`tooth-${t.id}`}
            >
              {t.id}
            </button>
          );
        })}
      </div>
      <div className="flex justify-center gap-1 flex-wrap">
        {lower.map(t => {
          const st = getStatus(t.id);
          return (
            <button
              key={t.id}
              onClick={() => setSelected(selected === t.id ? null : t.id)}
              title={t.name}
              className={`w-8 h-8 rounded border-2 text-xs font-bold transition-all ${getToothColor(st)} ${selected === t.id ? "ring-2 ring-primary ring-offset-1 scale-110" : "hover:scale-105"}`}
              data-testid={`tooth-${t.id}`}
            >
              {t.id}
            </button>
          );
        })}
      </div>
      <div className="text-[10px] text-muted-foreground text-center mt-1">LOWER</div>

      {/* Selected tooth actions */}
      {selected && (
        <div className="border rounded-lg p-3 mt-2">
          <div className="text-xs font-semibold mb-2">Tooth {selected} — {PRIMARY_TEETH.find(t => t.id === selected)?.name}</div>
          <div className="grid grid-cols-2 gap-2">
            {[
              { key: "present" as keyof ToothStatus, label: "Present" },
              { key: "caries" as keyof ToothStatus, label: "Caries (D)" },
              { key: "filling" as keyof ToothStatus, label: "Filling (F)" },
              { key: "sealant" as keyof ToothStatus, label: "Sealant" },
              { key: "extracted" as keyof ToothStatus, label: "Extracted" },
            ].map(item => {
              const st = getStatus(selected);
              return (
                <div key={item.key} className="flex items-center justify-between px-2 py-1 rounded bg-muted/30">
                  <span className="text-xs">{item.label}</span>
                  <Switch checked={st[item.key]} onCheckedChange={() => toggle(selected, item.key)} />
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

function NewExamDialog({ patients, open, onClose, onSaved }: {
  patients: any[]; open: boolean; onClose: () => void; onSaved: () => void;
}) {
  const { toast } = useToast();
  const [form, setForm] = useState({
    patientId: "", examDate: new Date().toISOString().split("T")[0],
    providerName: "", thumbSucking: false, pacifierUse: false, bruxism: false, tongueThrustting: false,
    fluorideTreatment: false, fluorideType: "varnish", bitewingsTaken: false,
    behaviorRating: "positive", nextRecallMonths: 6,
    dmft: "", clinicalNotes: "", treatmentPlan: "", parentEducation: "",
  });
  const [primaryTeeth, setPrimaryTeeth] = useState<PrimaryTeethMap>({});

  const mut = useMutation({
    mutationFn: () => apiRequest("POST", "/api/pediatric", {
      ...form,
      patientId: parseInt(form.patientId),
      nextRecallMonths: parseInt(form.nextRecallMonths.toString()) || 6,
      dmft: form.dmft ? parseInt(form.dmft) : null,
      primaryTeeth,
    }),
    onSuccess: () => { toast({ title: "Exam saved" }); onSaved(); onClose(); },
    onError: () => toast({ title: "Error saving exam", variant: "destructive" }),
  });

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><Baby className="h-4 w-4" /> New Pediatric Exam</DialogTitle>
        </DialogHeader>
        <Tabs defaultValue="info">
          <TabsList><TabsTrigger value="info">Patient Info</TabsTrigger><TabsTrigger value="chart">Tooth Chart</TabsTrigger><TabsTrigger value="clinical">Clinical</TabsTrigger></TabsList>

          <TabsContent value="info" className="space-y-3 pt-3">
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2">
                <Label>Patient *</Label>
                <Select value={form.patientId} onValueChange={v => setForm(f => ({ ...f, patientId: v }))}>
                  <SelectTrigger data-testid="select-patient"><SelectValue placeholder="Select patient…" /></SelectTrigger>
                  <SelectContent>{patients.map((p: any) => <SelectItem key={p.id} value={p.id.toString()}>{p.firstName} {p.lastName}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div><Label>Exam Date</Label><Input type="date" value={form.examDate} onChange={e => setForm(f => ({ ...f, examDate: e.target.value }))} /></div>
              <div><Label>Provider</Label><Input value={form.providerName} onChange={e => setForm(f => ({ ...f, providerName: e.target.value }))} placeholder="Dr. Smith" /></div>
            </div>
            <div className="space-y-2">
              <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Oral Habits</div>
              {[
                { key: "thumbSucking", label: "Thumb Sucking" },
                { key: "pacifierUse", label: "Pacifier Use" },
                { key: "bruxism", label: "Bruxism / Teeth Grinding" },
                { key: "tongueThrustting", label: "Tongue Thrusting" },
              ].map(item => (
                <div key={item.key} className="flex items-center justify-between px-3 py-2 rounded border">
                  <span className="text-sm">{item.label}</span>
                  <Switch checked={(form as any)[item.key]} onCheckedChange={v => setForm(f => ({ ...f, [item.key]: v }))} />
                </div>
              ))}
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <Label>DMFT (primary)</Label>
                <Input type="number" min="0" max="20" value={form.dmft} onChange={e => setForm(f => ({ ...f, dmft: e.target.value }))} placeholder="0" />
              </div>
              <div>
                <Label>Next Recall (mo)</Label>
                <Select value={form.nextRecallMonths.toString()} onValueChange={v => setForm(f => ({ ...f, nextRecallMonths: parseInt(v) }))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>{[3,4,6,12].map(n => <SelectItem key={n} value={n.toString()}>{n} months</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div>
                <Label>Behavior</Label>
                <Select value={form.behaviorRating} onValueChange={v => setForm(f => ({ ...f, behaviorRating: v }))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="definitely_positive">Definitely Positive</SelectItem>
                    <SelectItem value="positive">Positive</SelectItem>
                    <SelectItem value="negative">Negative</SelectItem>
                    <SelectItem value="definitely_negative">Definitely Negative</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="flex items-center justify-between px-3 py-2 rounded border">
              <span className="text-sm">Fluoride Treatment</span>
              <Switch checked={form.fluorideTreatment} onCheckedChange={v => setForm(f => ({ ...f, fluorideTreatment: v }))} />
            </div>
            <div className="flex items-center justify-between px-3 py-2 rounded border">
              <span className="text-sm">Bitewings Taken</span>
              <Switch checked={form.bitewingsTaken} onCheckedChange={v => setForm(f => ({ ...f, bitewingsTaken: v }))} />
            </div>
          </TabsContent>

          <TabsContent value="chart" className="pt-3">
            <PrimaryToothChart teeth={primaryTeeth} onChange={setPrimaryTeeth} />
          </TabsContent>

          <TabsContent value="clinical" className="space-y-3 pt-3">
            <div><Label>Clinical Notes</Label><Textarea value={form.clinicalNotes} onChange={e => setForm(f => ({ ...f, clinicalNotes: e.target.value }))} rows={3} data-testid="textarea-notes" /></div>
            <div><Label>Treatment Plan</Label><Textarea value={form.treatmentPlan} onChange={e => setForm(f => ({ ...f, treatmentPlan: e.target.value }))} rows={3} /></div>
            <div><Label>Parent Education</Label><Textarea value={form.parentEducation} onChange={e => setForm(f => ({ ...f, parentEducation: e.target.value }))} rows={2} /></div>
          </TabsContent>
        </Tabs>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={() => mut.mutate()} disabled={mut.isPending || !form.patientId} data-testid="button-save-exam">
            {mut.isPending ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Save className="h-4 w-4 mr-1" />}
            Save Exam
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function PediatricModulePage() {
  const queryClient = useQueryClient();
  const [newOpen, setNewOpen] = useState(false);

  const { data: patients = [] } = useQuery<any[]>({ queryKey: ["/api/patients"] });
  const { data: exams = [], isLoading } = useQuery<PediatricExam[]>({
    queryKey: ["/api/pediatric"],
    queryFn: () => fetch("/api/pediatric", { credentials: "include" }).then(r => r.json()),
  });

  const totalDmft = exams.reduce((a, e) => a + (e.dmft || 0), 0);
  const fluorideToday = exams.filter(e => e.fluorideTreatment).length;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">Pediatric Module</h1>
          <p className="text-sm text-muted-foreground">Primary tooth charting, DMFT tracking, behavior management, fluoride treatments</p>
        </div>
        <Button onClick={() => setNewOpen(true)} data-testid="button-new-exam">
          <Plus className="h-4 w-4 mr-1.5" /> New Exam
        </Button>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Total Exams", value: exams.length },
          { label: "Avg DMFT", value: exams.length ? (totalDmft / exams.length).toFixed(1) : "0" },
          { label: "Fluoride Tx", value: fluorideToday },
          { label: "Patients", value: new Set(exams.map(e => e.patientId)).size },
        ].map(k => (
          <Card key={k.label}>
            <CardContent className="pt-4 pb-4">
              <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">{k.label}</div>
              <div className="text-2xl font-bold font-mono" data-testid={`kpi-${k.label.toLowerCase().replace(/ /g, "-")}`}>{k.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-12"><Loader2 className="h-6 w-6 animate-spin" /></div>
      ) : exams.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="pt-12 pb-12 flex flex-col items-center gap-3 text-muted-foreground">
            <Baby className="h-10 w-10 opacity-30" />
            <p className="text-sm">No pediatric exams recorded — start by creating an exam</p>
            <Button onClick={() => setNewOpen(true)} variant="outline" size="sm"><Plus className="h-4 w-4 mr-1" /> New Exam</Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
          {exams.map(e => {
            const patient = patients.find((p: any) => p.id === e.patientId);
            const teethArr = Object.entries(e.primaryTeeth || {});
            const cariesCount = teethArr.filter(([, v]) => (v as ToothStatus).caries).length;
            return (
              <Card key={e.id} className="hover:border-primary/30 transition-colors" data-testid={`exam-card-${e.id}`}>
                <CardContent className="pt-4 pb-4">
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <div className="font-semibold">{patient ? `${patient.firstName} ${patient.lastName}` : `Patient #${e.patientId}`}</div>
                      <div className="text-xs text-muted-foreground">{e.examDate} · {e.providerName || "Unknown provider"}</div>
                    </div>
                    <Baby className="h-4 w-4 text-primary opacity-60" />
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-xs mt-3">
                    <div className="text-center"><div className="text-muted-foreground">DMFT</div><div className={`font-bold text-lg ${(e.dmft || 0) > 3 ? "text-red-500" : "text-emerald-500"}`}>{e.dmft ?? "—"}</div></div>
                    <div className="text-center"><div className="text-muted-foreground">Caries</div><div className={`font-bold text-lg ${cariesCount > 0 ? "text-amber-500" : "text-emerald-500"}`}>{cariesCount}</div></div>
                    <div className="text-center"><div className="text-muted-foreground">Fluoride</div><div className={`font-bold text-lg ${e.fluorideTreatment ? "text-teal-500" : "text-muted-foreground"}`}>{e.fluorideTreatment ? "✓" : "—"}</div></div>
                  </div>
                  {e.behaviorRating && (
                    <div className="mt-2 text-[10px] text-muted-foreground capitalize">Behavior: {e.behaviorRating.replace(/_/g, " ")}</div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      <NewExamDialog patients={patients} open={newOpen} onClose={() => setNewOpen(false)} onSaved={() => queryClient.invalidateQueries({ queryKey: ["/api/pediatric"] })} />
    </div>
  );
}
