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
  ChevronLeft, ChevronRight, Plus, Save, Loader2,
  Users, Clock, Calendar, Settings, TrendingUp,
  CheckCircle, AlertTriangle, X,
} from "lucide-react";

// ─── Types ─────────────────────────────────────────────────────────────────
interface Provider {
  id: number;
  name: string;
  title: string;
  specialty: string;
  color: string;
  operatory: string | null;
  dailyProductionTarget: string | null;
  isActive: boolean;
}

interface Appointment {
  id: number;
  patientId: number;
  appointmentType: string;
  title: string;
  description: string | null;
  startTime: string;
  endTime: string;
  status: string;
  providerName: string | null;
  notes: string | null;
}

const APPT_TYPES = [
  "New Patient Exam", "Recall / Cleaning", "Full Arch Consultation", "Surgery",
  "Implant Placement", "Implant Restoration", "Crown Prep", "Crown Delivery",
  "Extraction", "RCT", "Emergency", "Follow-Up", "Ortho Check", "Endo Check",
];

const PROVIDER_COLORS = [
  "#0EA5E9", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6",
  "#EC4899", "#06B6D4", "#F97316", "#84CC16", "#6366F1",
];

const STATUS_CFG: Record<string, { label: string; dot: string }> = {
  scheduled:   { label: "Scheduled",  dot: "bg-blue-500"   },
  confirmed:   { label: "Confirmed",  dot: "bg-emerald-500" },
  checked_in:  { label: "Checked In", dot: "bg-teal-500"   },
  in_progress: { label: "In Progress", dot: "bg-purple-500" },
  completed:   { label: "Completed",  dot: "bg-gray-400"   },
  no_show:     { label: "No Show",    dot: "bg-red-500"    },
  cancelled:   { label: "Cancelled",  dot: "bg-orange-400" },
};

// ─── Utilities ──────────────────────────────────────────────────────────────
function formatDate(d: Date) {
  return d.toISOString().split("T")[0];
}

function addDays(d: Date, n: number) {
  const r = new Date(d);
  r.setDate(r.getDate() + n);
  return r;
}

function isSameDay(a: Date, b: Date) {
  return a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate();
}

function parseTime(ts: string) {
  const d = new Date(ts);
  return { hours: d.getHours(), minutes: d.getMinutes() };
}

function timeLabel(ts: string) {
  const d = new Date(ts);
  let h = d.getHours();
  const m = d.getMinutes().toString().padStart(2, "0");
  const am = h < 12 ? "am" : "pm";
  if (h > 12) h -= 12;
  if (h === 0) h = 12;
  return `${h}:${m}${am}`;
}

// ─── Provider Dialog ─────────────────────────────────────────────────────
function ProviderDialog({ open, onClose, onSaved, editProvider }: {
  open: boolean; onClose: () => void; onSaved: () => void;
  editProvider?: Provider | null;
}) {
  const { toast } = useToast();
  const [form, setForm] = useState({
    name: editProvider?.name || "",
    title: editProvider?.title || "DMD",
    specialty: editProvider?.specialty || "General Dentistry",
    color: editProvider?.color || PROVIDER_COLORS[0],
    operatory: editProvider?.operatory || "",
    dailyProductionTarget: editProvider?.dailyProductionTarget || "",
    npi: "", licenseNumber: "", email: "", phone: "", notes: "",
  });

  const mut = useMutation({
    mutationFn: () => {
      const payload = { ...form, dailyProductionTarget: form.dailyProductionTarget || null, isActive: true };
      if (editProvider) return apiRequest("PUT", `/api/practice-providers/${editProvider.id}`, payload);
      return apiRequest("POST", "/api/practice-providers", payload);
    },
    onSuccess: () => { toast({ title: editProvider ? "Provider updated" : "Provider added" }); onSaved(); onClose(); },
    onError: () => toast({ title: "Error saving provider", variant: "destructive" }),
  });

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Users className="h-4 w-4" /> {editProvider ? "Edit Provider" : "Add Provider"}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-3 py-2">
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2">
              <Label>Full Name *</Label>
              <Input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="Dr. Jane Smith" data-testid="input-provider-name" />
            </div>
            <div>
              <Label>Title</Label>
              <Select value={form.title} onValueChange={v => setForm(f => ({ ...f, title: v }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {["DMD", "DDS", "MD", "RDH", "DA", "Office Manager"].map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div>
            <Label>Specialty</Label>
            <Select value={form.specialty} onValueChange={v => setForm(f => ({ ...f, specialty: v }))}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {["General Dentistry", "Oral Surgery", "Implantology", "Endodontics", "Periodontics", "Orthodontics", "Prosthodontics", "Pediatric Dentistry", "Dental Hygienist"].map(s => (
                  <SelectItem key={s} value={s}>{s}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Operatory / Chair</Label>
              <Input value={form.operatory} onChange={e => setForm(f => ({ ...f, operatory: e.target.value }))} placeholder="Op 1" />
            </div>
            <div>
              <Label>Daily Target ($)</Label>
              <Input type="number" value={form.dailyProductionTarget} onChange={e => setForm(f => ({ ...f, dailyProductionTarget: e.target.value }))} placeholder="5000" />
            </div>
          </div>
          <div>
            <Label>Calendar Color</Label>
            <div className="flex gap-2 mt-1 flex-wrap">
              {PROVIDER_COLORS.map(c => (
                <button key={c} onClick={() => setForm(f => ({ ...f, color: c }))}
                  className={`w-6 h-6 rounded-full border-2 ${form.color === c ? "border-foreground scale-110" : "border-transparent"}`}
                  style={{ backgroundColor: c }} data-testid={`color-${c}`}
                />
              ))}
            </div>
          </div>
          <div>
            <Label>Notes</Label>
            <Textarea value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} rows={2} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={() => mut.mutate()} disabled={mut.isPending || !form.name} data-testid="button-save-provider">
            {mut.isPending ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Save className="h-4 w-4 mr-1" />}
            Save Provider
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ─── New Appointment Dialog ───────────────────────────────────────────────
function NewApptDialog({ patients, providers, defaultDate, defaultProvider, open, onClose, onSaved }: {
  patients: any[]; providers: Provider[]; defaultDate: Date; defaultProvider?: string;
  open: boolean; onClose: () => void; onSaved: () => void;
}) {
  const { toast } = useToast();
  const [form, setForm] = useState({
    patientId: "", providerName: defaultProvider || (providers[0]?.name || ""),
    appointmentType: "New Patient Exam", title: "New Patient Exam",
    startDate: formatDate(defaultDate), startTime: "09:00", endTime: "10:00",
    status: "scheduled", notes: "", description: "",
  });

  const mut = useMutation({
    mutationFn: () => {
      const start = new Date(`${form.startDate}T${form.startTime}`);
      const end = new Date(`${form.startDate}T${form.endTime}`);
      return apiRequest("POST", "/api/appointments", {
        patientId: parseInt(form.patientId),
        appointmentType: form.appointmentType,
        title: form.title,
        description: form.description,
        startTime: start.toISOString(),
        endTime: end.toISOString(),
        status: form.status,
        providerName: form.providerName,
        notes: form.notes,
      });
    },
    onSuccess: () => { toast({ title: "Appointment booked" }); onSaved(); onClose(); },
    onError: () => toast({ title: "Error booking appointment", variant: "destructive" }),
  });

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><Calendar className="h-4 w-4" /> Book Appointment</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 py-2">
          <div>
            <Label>Patient *</Label>
            <Select value={form.patientId} onValueChange={v => setForm(f => ({ ...f, patientId: v }))}>
              <SelectTrigger data-testid="select-patient-appt"><SelectValue placeholder="Select patient…" /></SelectTrigger>
              <SelectContent>{patients.map((p: any) => <SelectItem key={p.id} value={p.id.toString()}>{p.firstName} {p.lastName}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div>
            <Label>Provider *</Label>
            <Select value={form.providerName} onValueChange={v => setForm(f => ({ ...f, providerName: v }))}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>{providers.map(p => <SelectItem key={p.id} value={p.name}>{p.name}, {p.title}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div>
            <Label>Appointment Type</Label>
            <Select value={form.appointmentType} onValueChange={v => setForm(f => ({ ...f, appointmentType: v, title: v }))}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>{APPT_TYPES.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div>
            <Label>Date</Label>
            <Input type="date" value={form.startDate} onChange={e => setForm(f => ({ ...f, startDate: e.target.value }))} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Start Time</Label>
              <Input type="time" value={form.startTime} onChange={e => setForm(f => ({ ...f, startTime: e.target.value }))} data-testid="input-start-time" />
            </div>
            <div>
              <Label>End Time</Label>
              <Input type="time" value={form.endTime} onChange={e => setForm(f => ({ ...f, endTime: e.target.value }))} data-testid="input-end-time" />
            </div>
          </div>
          <div>
            <Label>Notes</Label>
            <Textarea value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} rows={2} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={() => mut.mutate()} disabled={mut.isPending || !form.patientId} data-testid="button-save-appt">
            {mut.isPending ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : "Book Appointment"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ─── Day View Grid ─────────────────────────────────────────────────────────
const HOURS = Array.from({ length: 11 }, (_, i) => i + 7); // 7am to 5pm
const CELL_HEIGHT = 60; // px per hour

function DayGrid({ date, providers, appointments, patients, onBook }: {
  date: Date;
  providers: Provider[];
  appointments: Appointment[];
  patients: any[];
  onBook: (providerName: string) => void;
}) {
  const dayAppts = appointments.filter(a => {
    const d = new Date(a.startTime);
    return isSameDay(d, date);
  });

  return (
    <div className="overflow-x-auto">
      <div className="min-w-[600px]">
        {/* Header */}
        <div className="flex border-b sticky top-0 bg-background z-10">
          <div className="w-16 shrink-0" />
          {providers.map(p => (
            <div key={p.id} className="flex-1 text-center py-2 border-l">
              <div className="font-semibold text-sm truncate px-1">{p.name}</div>
              <div className="text-[10px] text-muted-foreground">{p.title} · {p.operatory || "Op"}</div>
              <div className="mt-1 h-1.5 rounded-full mx-2" style={{ backgroundColor: p.color }} />
            </div>
          ))}
        </div>

        {/* Time slots */}
        <div className="relative">
          {HOURS.map(hour => (
            <div key={hour} className="flex" style={{ height: CELL_HEIGHT }}>
              <div className="w-16 shrink-0 text-[10px] text-muted-foreground text-right pr-2 pt-1 border-r">
                {hour < 12 ? `${hour}am` : hour === 12 ? "12pm" : `${hour - 12}pm`}
              </div>
              {providers.map(p => {
                const slotAppts = dayAppts.filter(a => {
                  const { hours } = parseTime(a.startTime);
                  return a.providerName === p.name && hours === hour;
                });
                return (
                  <div
                    key={p.id}
                    className="flex-1 border-l border-b border-dashed border-border/40 relative cursor-pointer hover:bg-muted/20 transition-colors"
                    onClick={() => onBook(p.name)}
                  >
                    {slotAppts.map(a => {
                      const patient = patients.find((pt: any) => pt.id === a.patientId);
                      const cfg = STATUS_CFG[a.status] || STATUS_CFG.scheduled;
                      const { minutes } = parseTime(a.startTime);
                      const endH = parseTime(a.endTime).hours;
                      const endM = parseTime(a.endTime).minutes;
                      const durationMins = (endH - hour) * 60 + (endM - minutes);
                      const heightPx = Math.max(20, (durationMins / 60) * CELL_HEIGHT);
                      const topPx = (minutes / 60) * CELL_HEIGHT;
                      return (
                        <div
                          key={a.id}
                          className="absolute left-0.5 right-0.5 rounded text-[10px] px-1 py-0.5 overflow-hidden cursor-pointer hover:opacity-90"
                          style={{
                            top: topPx,
                            height: heightPx,
                            backgroundColor: p.color + "33",
                            borderLeft: `3px solid ${p.color}`,
                          }}
                          onClick={ev => ev.stopPropagation()}
                          data-testid={`appt-block-${a.id}`}
                        >
                          <div className="font-bold truncate" style={{ color: p.color }}>{a.title}</div>
                          {patient && <div className="text-muted-foreground truncate">{patient.firstName} {patient.lastName}</div>}
                          <div className="text-muted-foreground">{timeLabel(a.startTime)}–{timeLabel(a.endTime)}</div>
                        </div>
                      );
                    })}
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Week View ─────────────────────────────────────────────────────────────
function WeekView({ weekStart, providers, appointments, patients, onBook }: {
  weekStart: Date;
  providers: Provider[];
  appointments: Appointment[];
  patients: any[];
  onBook: (date: Date) => void;
}) {
  const days = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));
  const today = new Date();

  return (
    <div className="overflow-x-auto">
      <div className="min-w-[700px]">
        <div className="grid grid-cols-8 border-b">
          <div className="border-r p-2" />
          {days.map((d, i) => {
            const isToday = isSameDay(d, today);
            const dayAppts = appointments.filter(a => isSameDay(new Date(a.startTime), d));
            return (
              <div key={i} className={`text-center p-2 border-r ${isToday ? "bg-primary/5" : ""}`}>
                <div className={`text-xs font-semibold ${isToday ? "text-primary" : "text-muted-foreground"}`}>
                  {d.toLocaleDateString("en-US", { weekday: "short" })}
                </div>
                <div className={`text-lg font-bold font-mono ${isToday ? "text-primary" : ""}`}>{d.getDate()}</div>
                <div className="text-[10px] text-muted-foreground">{dayAppts.length} appts</div>
              </div>
            );
          })}
        </div>
        {providers.map(p => {
          const dayCounts = days.map(d => appointments.filter(a => a.providerName === p.name && isSameDay(new Date(a.startTime), d)));
          return (
            <div key={p.id} className="grid grid-cols-8 border-b">
              <div className="border-r p-2 flex flex-col justify-center">
                <div className="w-3 h-3 rounded-full mb-1" style={{ backgroundColor: p.color }} />
                <div className="text-xs font-semibold truncate">{p.name.split(" ").pop()}</div>
                <div className="text-[10px] text-muted-foreground">{p.title}</div>
              </div>
              {days.map((d, i) => (
                <div
                  key={i}
                  className="border-r p-1.5 min-h-[80px] cursor-pointer hover:bg-muted/20"
                  onClick={() => onBook(d)}
                >
                  {dayCounts[i].map(a => {
                    const patient = patients.find((pt: any) => pt.id === a.patientId);
                    return (
                      <div
                        key={a.id}
                        className="text-[10px] rounded px-1 py-0.5 mb-0.5 truncate"
                        style={{ backgroundColor: p.color + "25", borderLeft: `2px solid ${p.color}` }}
                        data-testid={`week-appt-${a.id}`}
                      >
                        {timeLabel(a.startTime)} {patient ? patient.firstName : a.title}
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Main Page ─────────────────────────────────────────────────────────────
export default function MultiProviderSchedulingPage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [view, setView] = useState<"week" | "day">("week");
  const [currentDate, setCurrentDate] = useState(() => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return d;
  });
  const [newApptOpen, setNewApptOpen] = useState(false);
  const [newApptProvider, setNewApptProvider] = useState<string>("");
  const [newApptDate, setNewApptDate] = useState(new Date());
  const [providerDialogOpen, setProviderDialogOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("schedule");

  const { data: patients = [] } = useQuery<any[]>({ queryKey: ["/api/patients"] });
  const { data: providers = [] } = useQuery<Provider[]>({
    queryKey: ["/api/practice-providers"],
    queryFn: () => fetch("/api/practice-providers", { credentials: "include" }).then(r => r.json()),
  });
  const { data: allAppts = [] } = useQuery<Appointment[]>({ queryKey: ["/api/appointments"] });

  // Week navigation
  const weekStart = (() => {
    const d = new Date(currentDate);
    const day = d.getDay();
    d.setDate(d.getDate() - day);
    return d;
  })();

  const goBack = () => {
    if (view === "week") setCurrentDate(d => addDays(d, -7));
    else setCurrentDate(d => addDays(d, -1));
  };
  const goForward = () => {
    if (view === "week") setCurrentDate(d => addDays(d, 7));
    else setCurrentDate(d => addDays(d, 1));
  };

  const openBook = (date: Date, providerName?: string) => {
    setNewApptDate(date);
    setNewApptProvider(providerName || providers[0]?.name || "");
    setNewApptOpen(true);
  };

  const totalToday = allAppts.filter(a => isSameDay(new Date(a.startTime), new Date())).length;
  const noShows = allAppts.filter(a => a.status === "no_show").length;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">Multi-Provider Scheduling</h1>
          <p className="text-sm text-muted-foreground">Provider schedules, production tracking, appointment management</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => setProviderDialogOpen(true)} data-testid="button-manage-providers">
            <Settings className="h-4 w-4 mr-1.5" /> Providers
          </Button>
          <Button size="sm" onClick={() => openBook(currentDate)} data-testid="button-new-appointment">
            <Plus className="h-4 w-4 mr-1.5" /> Book Appointment
          </Button>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Providers Active", value: providers.length },
          { label: "Today's Appointments", value: totalToday },
          { label: "This Week", value: allAppts.filter(a => isSameDay(new Date(a.startTime), weekStart) || (new Date(a.startTime) >= weekStart && new Date(a.startTime) < addDays(weekStart, 7))).length },
          { label: "No Shows (Total)", value: noShows, color: noShows > 0 ? "text-red-500" : "" },
        ].map(k => (
          <Card key={k.label}>
            <CardContent className="pt-4 pb-4">
              <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">{k.label}</div>
              <div className={`text-2xl font-bold font-mono ${k.color || ""}`} data-testid={`kpi-${k.label.toLowerCase().replace(/ /g, "-")}`}>{k.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="schedule">Schedule</TabsTrigger>
          <TabsTrigger value="providers">Provider Roster</TabsTrigger>
        </TabsList>

        <TabsContent value="schedule" className="mt-3">
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Button variant="ghost" size="icon" className="h-7 w-7" onClick={goBack} data-testid="button-prev-period">
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  <Button variant="ghost" size="icon" className="h-7 w-7" onClick={goForward} data-testid="button-next-period">
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                  <span className="font-semibold text-sm">
                    {view === "week"
                      ? `Week of ${weekStart.toLocaleDateString("en-US", { month: "short", day: "numeric" })} – ${addDays(weekStart, 6).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}`
                      : currentDate.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" })}
                  </span>
                </div>
                <div className="flex gap-1">
                  <Button size="sm" variant={view === "week" ? "default" : "outline"} className="h-7 text-xs" onClick={() => setView("week")}>Week</Button>
                  <Button size="sm" variant={view === "day" ? "default" : "outline"} className="h-7 text-xs" onClick={() => setView("day")}>Day</Button>
                </div>
              </div>
            </CardHeader>
            <CardContent className="pt-0">
              {providers.length === 0 ? (
                <div className="py-12 text-center text-muted-foreground">
                  <Users className="h-8 w-8 mx-auto mb-3 opacity-30" />
                  <p className="text-sm">No providers configured. Add providers to start scheduling.</p>
                  <Button className="mt-3" variant="outline" size="sm" onClick={() => setProviderDialogOpen(true)}>
                    <Plus className="h-4 w-4 mr-1" /> Add Provider
                  </Button>
                </div>
              ) : view === "week" ? (
                <WeekView
                  weekStart={weekStart}
                  providers={providers}
                  appointments={allAppts}
                  patients={patients}
                  onBook={openBook}
                />
              ) : (
                <DayGrid
                  date={currentDate}
                  providers={providers}
                  appointments={allAppts}
                  patients={patients}
                  onBook={(providerName) => openBook(currentDate, providerName)}
                />
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="providers" className="mt-3">
          <div className="flex justify-end mb-3">
            <Button size="sm" onClick={() => setProviderDialogOpen(true)} data-testid="button-add-provider">
              <Plus className="h-4 w-4 mr-1" /> Add Provider
            </Button>
          </div>
          {providers.length === 0 ? (
            <Card className="border-dashed">
              <CardContent className="py-10 text-center text-muted-foreground">
                <Users className="h-8 w-8 mx-auto mb-2 opacity-30" />
                <p className="text-sm">No providers yet.</p>
              </CardContent>
            </Card>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {providers.map(p => {
                const appts = allAppts.filter(a => a.providerName === p.name);
                const todayAppts = appts.filter(a => isSameDay(new Date(a.startTime), new Date()));
                return (
                  <Card key={p.id} className="hover:border-primary/30 transition-colors" data-testid={`card-provider-${p.id}`}>
                    <CardContent className="pt-4 pb-4">
                      <div className="flex items-center gap-3 mb-3">
                        <div className="w-10 h-10 rounded-full flex items-center justify-center text-white font-bold text-sm"
                          style={{ backgroundColor: p.color }}>
                          {p.name.split(" ").map(n => n[0]).join("").slice(0, 2)}
                        </div>
                        <div>
                          <div className="font-semibold">{p.name}, {p.title}</div>
                          <div className="text-xs text-muted-foreground">{p.specialty}</div>
                        </div>
                      </div>
                      <div className="space-y-1 text-xs text-muted-foreground">
                        {p.operatory && <div>Operatory: <span className="font-medium text-foreground">{p.operatory}</span></div>}
                        <div>Today: <span className="font-medium text-foreground">{todayAppts.length} appointments</span></div>
                        {p.dailyProductionTarget && (
                          <div>Target: <span className="font-medium text-foreground">${parseFloat(p.dailyProductionTarget).toLocaleString()}/day</span></div>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </TabsContent>
      </Tabs>

      <ProviderDialog open={providerDialogOpen} onClose={() => setProviderDialogOpen(false)} onSaved={() => queryClient.invalidateQueries({ queryKey: ["/api/practice-providers"] })} />

      {newApptOpen && (
        <NewApptDialog
          patients={patients}
          providers={providers}
          defaultDate={newApptDate}
          defaultProvider={newApptProvider}
          open={newApptOpen}
          onClose={() => setNewApptOpen(false)}
          onSaved={() => queryClient.invalidateQueries({ queryKey: ["/api/appointments"] })}
        />
      )}
    </div>
  );
}
