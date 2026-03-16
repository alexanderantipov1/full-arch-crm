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
  Plus, Save, Loader2, ChevronRight, Bell, Phone, Mail,
  CheckCircle, Clock, AlertTriangle, CalendarDays, X,
  MessageSquare, TrendingUp, Users,
} from "lucide-react";

// ─── Types ─────────────────────────────────────────────────────────────────
interface RecallEntry {
  id: number;
  patientId: number;
  recallType: string;
  intervalMonths: number;
  lastVisitDate: string | null;
  nextDueDate: string;
  status: string;
  priority: string;
  notes: string | null;
  assignedTo: string | null;
  contactPreference: string | null;
  patient?: { id: number; firstName: string; lastName: string; phone?: string; email?: string };
}

interface ContactEntry {
  id: number;
  recallPatientId: number;
  contactDate: string;
  method: string;
  outcome: string;
  scheduledDate: string | null;
  notes: string | null;
  contactedBy: string | null;
}

const RECALL_TYPES = [
  { value: "hygiene", label: "Hygiene / Cleaning", defaultMonths: 6 },
  { value: "perio_maintenance", label: "Perio Maintenance", defaultMonths: 3 },
  { value: "post_op", label: "Post-Op Follow-Up", defaultMonths: 1 },
  { value: "implant_check", label: "Implant Check", defaultMonths: 12 },
  { value: "ortho_check", label: "Ortho Check", defaultMonths: 2 },
  { value: "endo_check", label: "Endo Follow-Up", defaultMonths: 6 },
  { value: "new_patient_followup", label: "New Patient Follow-Up", defaultMonths: 3 },
  { value: "annual_exam", label: "Annual Exam", defaultMonths: 12 },
];

const STATUS_CFG: Record<string, { label: string; color: string; bg: string; icon: any }> = {
  due:       { label: "Due",        color: "text-amber-600 dark:text-amber-400",   bg: "bg-amber-500/10 border-amber-400/40",   icon: Bell },
  scheduled: { label: "Scheduled",  color: "text-blue-600 dark:text-blue-400",    bg: "bg-blue-500/10 border-blue-400/40",    icon: CalendarDays },
  completed: { label: "Completed",  color: "text-emerald-600 dark:text-emerald-400", bg: "bg-emerald-500/10 border-emerald-400/40", icon: CheckCircle },
  overdue:   { label: "Overdue",    color: "text-red-600 dark:text-red-400",      bg: "bg-red-500/10 border-red-400/40",      icon: AlertTriangle },
  declined:  { label: "Declined",   color: "text-gray-500 dark:text-gray-400",    bg: "bg-gray-500/10 border-gray-400/30",    icon: X },
};

const OUTCOME_CFG: Record<string, string> = {
  scheduled: "text-emerald-600 dark:text-emerald-400",
  no_answer: "text-amber-600 dark:text-amber-400",
  left_vm:   "text-blue-600 dark:text-blue-400",
  patient_declined: "text-red-500 dark:text-red-400",
  wrong_number: "text-gray-500",
};

// ─── Days Until ─────────────────────────────────────────────────────────────
function daysUntil(dateStr: string) {
  const due = new Date(dateStr);
  const today = new Date();
  return Math.round((due.getTime() - today.getTime()) / 86400000);
}

// ─── New Recall Dialog ───────────────────────────────────────────────────
function NewRecallDialog({ patients, open, onClose, onSaved }: {
  patients: any[]; open: boolean; onClose: () => void; onSaved: () => void;
}) {
  const { toast } = useToast();
  const [form, setForm] = useState({
    patientId: "", recallType: "hygiene", intervalMonths: 6,
    lastVisitDate: "", nextDueDate: "", status: "due", priority: "normal",
    assignedTo: "", contactPreference: "any", notes: "",
  });

  const recallInfo = RECALL_TYPES.find(r => r.value === form.recallType);

  const updateType = (type: string) => {
    const info = RECALL_TYPES.find(r => r.value === type);
    const months = info?.defaultMonths || 6;
    const due = new Date();
    due.setMonth(due.getMonth() + months);
    setForm(f => ({
      ...f, recallType: type, intervalMonths: months,
      nextDueDate: due.toISOString().split("T")[0],
    }));
  };

  const mut = useMutation({
    mutationFn: () => apiRequest("POST", "/api/recall", {
      ...form,
      patientId: parseInt(form.patientId),
      intervalMonths: parseInt(form.intervalMonths.toString()),
      lastVisitDate: form.lastVisitDate || null,
    }),
    onSuccess: () => { toast({ title: "Recall created" }); onSaved(); onClose(); },
    onError: () => toast({ title: "Error creating recall", variant: "destructive" }),
  });

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><Bell className="h-4 w-4" /> Add Patient to Recall</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 py-2">
          <div>
            <Label>Patient *</Label>
            <Select value={form.patientId} onValueChange={v => setForm(f => ({ ...f, patientId: v }))}>
              <SelectTrigger data-testid="select-patient-recall"><SelectValue placeholder="Select patient…" /></SelectTrigger>
              <SelectContent>{patients.map((p: any) => <SelectItem key={p.id} value={p.id.toString()}>{p.firstName} {p.lastName}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Recall Type *</Label>
              <Select value={form.recallType} onValueChange={updateType}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{RECALL_TYPES.map(r => <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div>
              <Label>Interval (months)</Label>
              <Input type="number" min="1" max="24" value={form.intervalMonths}
                onChange={e => setForm(f => ({ ...f, intervalMonths: parseInt(e.target.value) || 6 }))} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Last Visit Date</Label>
              <Input type="date" value={form.lastVisitDate} onChange={e => setForm(f => ({ ...f, lastVisitDate: e.target.value }))} />
            </div>
            <div>
              <Label>Next Due Date *</Label>
              <Input type="date" value={form.nextDueDate} onChange={e => setForm(f => ({ ...f, nextDueDate: e.target.value }))} data-testid="input-due-date" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Priority</Label>
              <Select value={form.priority} onValueChange={v => setForm(f => ({ ...f, priority: v }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="high">High</SelectItem>
                  <SelectItem value="normal">Normal</SelectItem>
                  <SelectItem value="low">Low</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Contact Preference</Label>
              <Select value={form.contactPreference} onValueChange={v => setForm(f => ({ ...f, contactPreference: v }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="any">Any</SelectItem>
                  <SelectItem value="phone">Phone</SelectItem>
                  <SelectItem value="email">Email</SelectItem>
                  <SelectItem value="sms">SMS</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div>
            <Label>Notes</Label>
            <Textarea value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} rows={2} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={() => mut.mutate()} disabled={mut.isPending || !form.patientId || !form.nextDueDate} data-testid="button-save-recall">
            {mut.isPending ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Save className="h-4 w-4 mr-1" />}
            Add to Recall
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ─── Contact Log Dialog ───────────────────────────────────────────────────
function ContactLogDialog({ recall, open, onClose }: { recall: RecallEntry; open: boolean; onClose: () => void }) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    contactDate: new Date().toISOString().split("T")[0],
    method: "phone", outcome: "no_answer", scheduledDate: "", notes: "", contactedBy: "",
  });

  const { data: logs = [] } = useQuery<ContactEntry[]>({
    queryKey: ["/api/recall", recall.id, "contacts"],
    queryFn: () => fetch(`/api/recall/${recall.id}/contacts`, { credentials: "include" }).then(r => r.json()),
    enabled: open,
  });

  const logMut = useMutation({
    mutationFn: () => apiRequest("POST", `/api/recall/${recall.id}/contacts`, {
      ...form,
      scheduledDate: form.scheduledDate || null,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/recall", recall.id, "contacts"] });
      queryClient.invalidateQueries({ queryKey: ["/api/recall"] });
      toast({ title: "Contact logged" });
      setForm({ contactDate: new Date().toISOString().split("T")[0], method: "phone", outcome: "no_answer", scheduledDate: "", notes: "", contactedBy: "" });
    },
  });

  const outcomeLabel: Record<string, string> = {
    scheduled: "Scheduled", no_answer: "No Answer",
    left_vm: "Left Voicemail", patient_declined: "Declined",
    wrong_number: "Wrong Number",
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Contact Log — {recall.patient?.firstName} {recall.patient?.lastName}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 py-2">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-xs">Date</Label>
              <Input type="date" value={form.contactDate} onChange={e => setForm(f => ({ ...f, contactDate: e.target.value }))} className="h-8 text-xs mt-1" />
            </div>
            <div>
              <Label className="text-xs">Method</Label>
              <Select value={form.method} onValueChange={v => setForm(f => ({ ...f, method: v }))}>
                <SelectTrigger className="h-8 text-xs mt-1"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="phone">Phone</SelectItem>
                  <SelectItem value="email">Email</SelectItem>
                  <SelectItem value="sms">SMS</SelectItem>
                  <SelectItem value="mail">Mail</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-xs">Outcome</Label>
              <Select value={form.outcome} onValueChange={v => setForm(f => ({ ...f, outcome: v }))}>
                <SelectTrigger className="h-8 text-xs mt-1"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="scheduled">Appointment Scheduled</SelectItem>
                  <SelectItem value="no_answer">No Answer</SelectItem>
                  <SelectItem value="left_vm">Left Voicemail</SelectItem>
                  <SelectItem value="patient_declined">Patient Declined</SelectItem>
                  <SelectItem value="wrong_number">Wrong Number</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs">Scheduled Date</Label>
              <Input type="date" value={form.scheduledDate} onChange={e => setForm(f => ({ ...f, scheduledDate: e.target.value }))} className="h-8 text-xs mt-1" />
            </div>
          </div>
          <div>
            <Label className="text-xs">Notes</Label>
            <Textarea value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} rows={2} className="text-xs mt-1" data-testid="textarea-contact-notes" />
          </div>
          <Button size="sm" onClick={() => logMut.mutate()} disabled={logMut.isPending} data-testid="button-log-contact">
            {logMut.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Log Contact"}
          </Button>

          {logs.length > 0 && (
            <div className="mt-3 space-y-2">
              <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Previous Contacts</div>
              {logs.map(l => (
                <div key={l.id} className="text-xs bg-muted/30 rounded p-2.5 flex justify-between gap-2">
                  <div>
                    <span className="font-medium capitalize">{l.method}</span>
                    {" • "}
                    <span className={outcomeLabel[l.outcome] ? OUTCOME_CFG[l.outcome] : ""}>{outcomeLabel[l.outcome] || l.outcome}</span>
                    {l.notes && <p className="text-muted-foreground mt-0.5">{l.notes}</p>}
                  </div>
                  <span className="text-muted-foreground shrink-0">{l.contactDate}</span>
                </div>
              ))}
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Close</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ─── Recall Row ────────────────────────────────────────────────────────────
function RecallRow({ entry, onContact, onStatusChange }: {
  entry: RecallEntry;
  onContact: (e: RecallEntry) => void;
  onStatusChange: (id: number, status: string) => void;
}) {
  const cfg = STATUS_CFG[entry.status] || STATUS_CFG.due;
  const days = daysUntil(entry.nextDueDate);
  const type = RECALL_TYPES.find(r => r.value === entry.recallType);
  const Icon = cfg.icon;

  return (
    <div className={`flex items-center gap-3 px-4 py-3 border rounded-lg ${entry.status === "overdue" ? "border-red-400/40 bg-red-500/5" : "border-border"} hover:border-primary/30 transition-colors`} data-testid={`recall-row-${entry.id}`}>
      <div className="shrink-0">
        <Icon className={`h-4 w-4 ${cfg.color}`} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="font-medium text-sm truncate">
          {entry.patient ? `${entry.patient.firstName} ${entry.patient.lastName}` : `Patient #${entry.patientId}`}
        </div>
        <div className="text-xs text-muted-foreground">{type?.label || entry.recallType} · every {entry.intervalMonths}mo</div>
      </div>
      <div className="text-xs text-center shrink-0">
        <div className={`font-bold ${days < 0 ? "text-red-500" : days <= 7 ? "text-amber-500" : "text-muted-foreground"}`}>
          {days < 0 ? `${Math.abs(days)}d overdue` : days === 0 ? "Today" : `in ${days}d`}
        </div>
        <div className="text-muted-foreground">{entry.nextDueDate}</div>
      </div>
      <div className="shrink-0">
        <Badge className={`text-[10px] px-1.5 border ${cfg.bg} ${cfg.color}`}>{cfg.label}</Badge>
      </div>
      <div className="flex gap-1.5 shrink-0">
        <button
          onClick={() => onContact(entry)}
          className="text-xs px-2 py-1 rounded border border-primary/30 text-primary hover:bg-primary/10 flex items-center gap-1"
          data-testid={`button-contact-${entry.id}`}
        >
          <Phone className="h-3 w-3" /> Contact
        </button>
        {entry.status !== "completed" && (
          <button
            onClick={() => onStatusChange(entry.id, "completed")}
            className="text-xs px-2 py-1 rounded border border-emerald-400/40 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-500/10"
            data-testid={`button-complete-${entry.id}`}
          >
            Done
          </button>
        )}
        {entry.status !== "scheduled" && entry.status !== "completed" && (
          <button
            onClick={() => onStatusChange(entry.id, "scheduled")}
            className="text-xs px-2 py-1 rounded border border-blue-400/40 text-blue-600 dark:text-blue-400 hover:bg-blue-500/10"
            data-testid={`button-scheduled-${entry.id}`}
          >
            Scheduled
          </button>
        )}
      </div>
    </div>
  );
}

// ─── Main Page ─────────────────────────────────────────────────────────────
export default function RecallSystemPage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [newOpen, setNewOpen] = useState(false);
  const [contactEntry, setContactEntry] = useState<RecallEntry | null>(null);
  const [filterStatus, setFilterStatus] = useState("all");
  const [filterType, setFilterType] = useState("all");
  const [search, setSearch] = useState("");

  const { data: patients = [] } = useQuery<any[]>({ queryKey: ["/api/patients"] });
  const { data: allRecalls = [], isLoading } = useQuery<RecallEntry[]>({
    queryKey: ["/api/recall"],
    queryFn: () => fetch("/api/recall", { credentials: "include" }).then(r => r.json()),
  });

  const statusMut = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) => apiRequest("PUT", `/api/recall/${id}`, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/recall"] });
      toast({ title: "Status updated" });
    },
  });

  const filtered = allRecalls.filter(r => {
    if (filterStatus !== "all" && r.status !== filterStatus) return false;
    if (filterType !== "all" && r.recallType !== filterType) return false;
    if (search) {
      const name = r.patient ? `${r.patient.firstName} ${r.patient.lastName}`.toLowerCase() : "";
      if (!name.includes(search.toLowerCase())) return false;
    }
    return true;
  });

  const overdue = allRecalls.filter(r => r.status === "overdue" || (r.status === "due" && daysUntil(r.nextDueDate) < 0)).length;
  const dueThisMonth = allRecalls.filter(r => daysUntil(r.nextDueDate) >= 0 && daysUntil(r.nextDueDate) <= 30).length;
  const scheduled = allRecalls.filter(r => r.status === "scheduled").length;
  const completed = allRecalls.filter(r => r.status === "completed").length;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">Recall System</h1>
          <p className="text-sm text-muted-foreground">Patient recall management — hygiene, post-op, implant checks, and follow-ups</p>
        </div>
        <Button onClick={() => setNewOpen(true)} data-testid="button-new-recall">
          <Plus className="h-4 w-4 mr-1.5" /> Add Recall
        </Button>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Overdue", value: overdue, color: "text-red-600 dark:text-red-400" },
          { label: "Due This Month", value: dueThisMonth, color: "text-amber-600 dark:text-amber-400" },
          { label: "Scheduled", value: scheduled, color: "text-blue-600 dark:text-blue-400" },
          { label: "Completed (total)", value: completed, color: "text-emerald-600 dark:text-emerald-400" },
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
      <div className="flex flex-wrap gap-2 items-center">
        <Input
          placeholder="Search patient…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="h-8 w-48 text-sm"
          data-testid="input-search-recall"
        />
        <div className="flex gap-1.5 flex-wrap">
          {["all", "overdue", "due", "scheduled", "completed", "declined"].map(s => (
            <button
              key={s}
              onClick={() => setFilterStatus(s)}
              className={`px-2.5 py-1 rounded-full text-xs font-medium border transition-colors ${
                filterStatus === s
                  ? "bg-primary text-primary-foreground border-primary"
                  : "border-border text-muted-foreground hover:border-primary/50"
              }`}
              data-testid={`filter-status-${s}`}
            >
              {s === "all" ? `All (${allRecalls.length})` : (STATUS_CFG[s]?.label || s)}
            </button>
          ))}
        </div>
        <Select value={filterType} onValueChange={setFilterType}>
          <SelectTrigger className="h-8 text-xs w-44">
            <SelectValue placeholder="All types" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Types</SelectItem>
            {RECALL_TYPES.map(r => <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      {/* List */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12"><Loader2 className="h-6 w-6 animate-spin" /></div>
      ) : filtered.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="pt-12 pb-12 flex flex-col items-center gap-3 text-muted-foreground">
            <Bell className="h-10 w-10 opacity-30" />
            <p className="text-sm">No recall entries — add patients to the recall system</p>
            <Button onClick={() => setNewOpen(true)} variant="outline" size="sm"><Plus className="h-4 w-4 mr-1" /> Add Recall</Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {filtered.map(r => (
            <RecallRow
              key={r.id}
              entry={r}
              onContact={setContactEntry}
              onStatusChange={(id, status) => statusMut.mutate({ id, status })}
            />
          ))}
        </div>
      )}

      <NewRecallDialog patients={patients} open={newOpen} onClose={() => setNewOpen(false)} onSaved={() => queryClient.invalidateQueries({ queryKey: ["/api/recall"] })} />

      {contactEntry && (
        <ContactLogDialog recall={contactEntry} open={!!contactEntry} onClose={() => setContactEntry(null)} />
      )}
    </div>
  );
}
