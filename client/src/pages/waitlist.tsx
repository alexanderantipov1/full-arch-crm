import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { apiRequest } from "@/lib/queryClient";
import {
  Clock, Users, PhoneCall, CheckCircle, CalendarX, Timer, Plus,
  Loader2, UserCheck, Trash2, Sparkles, Phone,
} from "lucide-react";

interface WaitlistEntry {
  id: string;
  patientName: string; patientPhone: string; patientEmail: string;
  appointmentType: string;
  providerId?: string; providerName?: string;
  minNoticeHours: number;
  preferredDays: string[];
  preferredTimeBlocks: string[];
  notes: string;
  status: "active" | "contacted" | "booked" | "removed";
  contactAttempts: number;
  lastContactedAt: string | null;
  addedAt: string;
  bookedAt: string | null;
  priority: number;
}
interface CancellationSlot {
  id: string; date: string; time: string;
  providerId: string; providerName: string;
  durationMinutes: number; appointmentType: string;
  openedAt: string; filledAt: string | null; filledByPatientId: string | null;
}
interface Stats {
  total: number; active: number; contacted: number; booked: number;
  openSlots: number; avgWaitDays: number;
}

const APPT_TYPES = [
  { value: "full_arch_consult", label: "Full Arch Consult" },
  { value: "implant_consult", label: "Implant Consult" },
  { value: "implant_placement", label: "Implant Placement" },
  { value: "new_patient_exam", label: "New Patient Exam" },
  { value: "recall_hygiene", label: "Hygiene Recall" },
  { value: "emergency", label: "Emergency" },
  { value: "post_op", label: "Post-Op" },
  { value: "treatment_consult", label: "Treatment Consult" },
];
const TYPE_LABEL: Record<string, string> = Object.fromEntries(APPT_TYPES.map(t => [t.value, t.label]));

const DAYS = [
  { value: "monday", label: "Mon" }, { value: "tuesday", label: "Tue" },
  { value: "wednesday", label: "Wed" }, { value: "thursday", label: "Thu" },
  { value: "friday", label: "Fri" },
];
const TIME_BLOCKS = [
  { value: "morning", label: "Morning" }, { value: "afternoon", label: "Afternoon" }, { value: "evening", label: "Evening" },
];
const NOTICE_OPTS = [
  { value: 2, label: "Same day (2hr notice)" },
  { value: 24, label: "1 day notice" },
  { value: 72, label: "3+ days notice" },
];
const PROVIDERS = [
  { id: "prov-1", name: "Dr. Antipov" },
  { id: "prov-2", name: "Dr. Johnson" },
];

const STATUS_CFG: Record<string, { label: string; cls: string }> = {
  active: { label: "Active", cls: "bg-blue-500/10 text-blue-600 border-blue-400/40" },
  contacted: { label: "Contacted", cls: "bg-amber-500/10 text-amber-600 border-amber-400/40" },
  booked: { label: "Booked", cls: "bg-emerald-500/10 text-emerald-600 border-emerald-400/40" },
  removed: { label: "Removed", cls: "bg-gray-500/10 text-gray-500 border-gray-400/30" },
};

function daysOnList(addedAt: string) {
  return Math.max(0, Math.floor((Date.now() - new Date(addedAt).getTime()) / 86400000));
}
function prettyDate(s: string) {
  if (!s) return "—";
  return new Date(s + "T00:00:00").toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
}
function prettyTime(t: string) {
  if (!t) return "";
  const [h, m] = t.split(":").map(Number);
  const period = h >= 12 ? "PM" : "AM";
  const hr = h % 12 === 0 ? 12 : h % 12;
  return `${hr}:${m.toString().padStart(2, "0")} ${period}`;
}

export default function WaitlistPage() {
  const { toast } = useToast();
  const qc = useQueryClient();
  const [statusFilter, setStatusFilter] = useState("active");
  const [typeFilter, setTypeFilter] = useState("all");
  const [matches, setMatches] = useState<Record<string, WaitlistEntry[]>>({});

  const { data: stats } = useQuery<Stats>({ queryKey: ["/api/waitlist/stats"], refetchInterval: 30000 });
  const { data: entries = [], isLoading } = useQuery<WaitlistEntry[]>({
    queryKey: [statusFilter === "all" ? "/api/waitlist" : `/api/waitlist?status=${statusFilter}`],
    refetchInterval: 30000,
  });
  const { data: openSlots = [] } = useQuery<CancellationSlot[]>({
    queryKey: ["/api/waitlist/slots/open"], refetchInterval: 30000,
  });

  const invalidateAll = () => {
    qc.invalidateQueries({ queryKey: ["/api/waitlist/stats"] });
    qc.invalidateQueries({ predicate: q => String(q.queryKey[0]).startsWith("/api/waitlist") });
  };

  const contactMut = useMutation({
    mutationFn: (id: string) => apiRequest("POST", `/api/waitlist/${id}/contact`),
    onSuccess: () => { invalidateAll(); toast({ title: "Contact attempt recorded" }); },
    onError: () => toast({ title: "Failed", variant: "destructive" }),
  });
  const statusMut = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => apiRequest("PATCH", `/api/waitlist/${id}/status`, { status }),
    onSuccess: () => { invalidateAll(); toast({ title: "Updated" }); },
    onError: () => toast({ title: "Failed", variant: "destructive" }),
  });
  const removeMut = useMutation({
    mutationFn: (id: string) => apiRequest("DELETE", `/api/waitlist/${id}`),
    onSuccess: () => { invalidateAll(); toast({ title: "Removed from waitlist" }); },
    onError: () => toast({ title: "Failed", variant: "destructive" }),
  });
  const findMatchesMut = useMutation({
    mutationFn: (slot: CancellationSlot) => apiRequest("POST", "/api/waitlist/slots/open", {
      date: slot.date, time: slot.time, providerId: slot.providerId,
      providerName: slot.providerName, durationMinutes: slot.durationMinutes,
      appointmentType: slot.appointmentType,
    }).then(r => r.json()),
    onSuccess: (data: { slot: CancellationSlot; matches: WaitlistEntry[] }, slot) => {
      setMatches(m => ({ ...m, [slot.id]: data.matches }));
      qc.invalidateQueries({ queryKey: ["/api/waitlist/slots/open"] });
      toast({ title: `${data.matches.length} match${data.matches.length === 1 ? "" : "es"} found` });
    },
    onError: () => toast({ title: "Match failed", variant: "destructive" }),
  });
  const fillMut = useMutation({
    mutationFn: ({ slotId, patientId }: { slotId: string; patientId: string }) =>
      apiRequest("POST", `/api/waitlist/slots/${slotId}/fill`, { patientId }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["/api/waitlist/slots/open"] });
      toast({ title: "Slot marked filled" });
    },
    onError: () => toast({ title: "Failed", variant: "destructive" }),
  });

  const filtered = entries.filter(e => typeFilter === "all" || e.appointmentType === typeFilter);
  const maxPriority = 6;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary"><Clock className="h-5 w-5" /></div>
        <div>
          <h1 className="text-2xl font-semibold">Waitlist Manager</h1>
          <p className="text-sm text-muted-foreground">Fill cancellations fast — match waitlisted patients to open slots by priority</p>
        </div>
      </div>

      {/* Stats */}
      <div className="grid gap-4 grid-cols-2 lg:grid-cols-6">
        <StatCard icon={Users} label="Total" value={stats?.total ?? 0} tone="text-slate-600" />
        <StatCard icon={Clock} label="Active" value={stats?.active ?? 0} tone="text-blue-600" />
        <StatCard icon={PhoneCall} label="Contacted" value={stats?.contacted ?? 0} tone="text-amber-600" />
        <StatCard icon={CheckCircle} label="Booked" value={stats?.booked ?? 0} tone="text-emerald-600" />
        <StatCard icon={CalendarX} label="Open Slots" value={stats?.openSlots ?? 0} tone="text-red-600" />
        <StatCard icon={Timer} label="Avg Wait (days)" value={stats ? stats.avgWaitDays.toFixed(1) : "0"} tone="text-purple-600" />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Add to waitlist form */}
        <AddToWaitlistForm onSaved={invalidateAll} />

        {/* Open cancellation slots */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base"><CalendarX className="h-4 w-4 text-red-500" /> Open Cancellation Slots</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {openSlots.length === 0 ? (
              <p className="text-sm text-muted-foreground">No open slots. When an appointment cancels, open it here to find waitlist matches.</p>
            ) : openSlots.map(slot => (
              <div key={slot.id} className="rounded-lg border p-3" data-testid={`open-slot-${slot.id}`}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <div className="font-medium">{prettyDate(slot.date)} · {prettyTime(slot.time)}</div>
                    <div className="text-xs text-muted-foreground">{slot.providerName} · {TYPE_LABEL[slot.appointmentType] ?? slot.appointmentType}</div>
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" disabled={findMatchesMut.isPending} onClick={() => findMatchesMut.mutate(slot)} data-testid={`button-find-matches-${slot.id}`}>
                      <Sparkles className="mr-1 h-3.5 w-3.5" /> Find Matches
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => fillMut.mutate({ slotId: slot.id, patientId: "manual" })} data-testid={`button-fill-${slot.id}`}>
                      <CheckCircle className="mr-1 h-3.5 w-3.5" /> Mark Filled
                    </Button>
                  </div>
                </div>
                {matches[slot.id] && (
                  <div className="mt-3 space-y-2 border-t pt-3">
                    {matches[slot.id].length === 0 ? (
                      <p className="text-xs text-muted-foreground">No matching waitlist patients.</p>
                    ) : matches[slot.id].map((m, i) => (
                      <div key={m.id} className="flex items-center justify-between gap-2 rounded-md bg-muted/40 px-3 py-2" data-testid={`match-${slot.id}-${m.id}`}>
                        <div className="flex items-center gap-2">
                          <span className="flex h-5 w-5 items-center justify-center rounded-full bg-primary text-[10px] font-semibold text-primary-foreground">{i + 1}</span>
                          <div>
                            <div className="text-sm font-medium">{m.patientName}</div>
                            <div className="text-xs text-muted-foreground">{m.patientPhone} · priority {m.priority}</div>
                          </div>
                        </div>
                        <Button size="sm" variant="outline" disabled={contactMut.isPending} onClick={() => contactMut.mutate(m.id)} data-testid={`button-contact-match-${m.id}`}>
                          <PhoneCall className="mr-1 h-3.5 w-3.5" /> Contact
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-40" data-testid="filter-wl-status"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="contacted">Contacted</SelectItem>
            <SelectItem value="booked">Booked</SelectItem>
            <SelectItem value="removed">Removed</SelectItem>
          </SelectContent>
        </Select>
        <Select value={typeFilter} onValueChange={setTypeFilter}>
          <SelectTrigger className="w-48" data-testid="filter-wl-type"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All types</SelectItem>
            {APPT_TYPES.map(t => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      {/* Waitlist table */}
      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="flex items-center justify-center py-16 text-muted-foreground"><Loader2 className="mr-2 h-5 w-5 animate-spin" /> Loading…</div>
          ) : filtered.length === 0 ? (
            <div className="py-16 text-center text-sm text-muted-foreground">No patients on the waitlist for this filter.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th className="px-4 py-3">Patient</th>
                    <th className="px-4 py-3">Type</th>
                    <th className="px-4 py-3">Provider</th>
                    <th className="px-4 py-3">Notice</th>
                    <th className="px-4 py-3">Days</th>
                    <th className="px-4 py-3">Priority</th>
                    <th className="px-4 py-3">Contacts</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(e => {
                    const cfg = STATUS_CFG[e.status];
                    return (
                      <tr key={e.id} className="border-b last:border-0 hover:bg-muted/20" data-testid={`waitlist-row-${e.id}`}>
                        <td className="px-4 py-3">
                          <div className="font-medium">{e.patientName}</div>
                          <div className="flex gap-2 text-xs text-muted-foreground">
                            <a href={`tel:${e.patientPhone}`} className="inline-flex items-center gap-1 hover:text-foreground"><Phone className="h-3 w-3" />{e.patientPhone}</a>
                          </div>
                        </td>
                        <td className="px-4 py-3">{TYPE_LABEL[e.appointmentType] ?? e.appointmentType}</td>
                        <td className="px-4 py-3 text-muted-foreground">{e.providerName || "Any"}</td>
                        <td className="px-4 py-3 whitespace-nowrap">{e.minNoticeHours <= 2 ? "Same day" : e.minNoticeHours <= 24 ? "1 day" : "3+ days"}</td>
                        <td className="px-4 py-3">{daysOnList(e.addedAt)}</td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <div className="h-2 w-16 overflow-hidden rounded-full bg-muted">
                              <div className="h-full rounded-full bg-primary" style={{ width: `${(e.priority / maxPriority) * 100}%` }} />
                            </div>
                            <span className="text-xs font-medium">{e.priority}</span>
                          </div>
                        </td>
                        <td className="px-4 py-3">{e.contactAttempts}</td>
                        <td className="px-4 py-3"><Badge variant="outline" className={cfg.cls}>{cfg.label}</Badge></td>
                        <td className="px-4 py-3">
                          <div className="flex justify-end gap-1.5">
                            {e.status !== "booked" && e.status !== "removed" && (
                              <>
                                <Button size="sm" variant="outline" disabled={contactMut.isPending} onClick={() => contactMut.mutate(e.id)} data-testid={`button-contact-${e.id}`}>
                                  <PhoneCall className="h-3.5 w-3.5" />
                                </Button>
                                <Button size="sm" variant="default" onClick={() => statusMut.mutate({ id: e.id, status: "booked" })} data-testid={`button-book-${e.id}`}>
                                  <UserCheck className="mr-1 h-3.5 w-3.5" /> Book
                                </Button>
                              </>
                            )}
                            {e.status !== "removed" && (
                              <Button size="sm" variant="ghost" className="text-red-600 hover:text-red-700" onClick={() => removeMut.mutate(e.id)} data-testid={`button-remove-${e.id}`}>
                                <Trash2 className="h-3.5 w-3.5" />
                              </Button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function AddToWaitlistForm({ onSaved }: { onSaved: () => void }) {
  const { toast } = useToast();
  const [form, setForm] = useState({
    patientName: "", patientPhone: "", patientEmail: "",
    appointmentType: "full_arch_consult", providerId: "", minNoticeHours: 2,
    notes: "",
  });
  const [days, setDays] = useState<string[]>([]);
  const [blocks, setBlocks] = useState<string[]>([]);

  const toggle = (arr: string[], set: (v: string[]) => void, val: string) =>
    set(arr.includes(val) ? arr.filter(d => d !== val) : [...arr, val]);

  const mut = useMutation({
    mutationFn: () => apiRequest("POST", "/api/waitlist", {
      ...form,
      providerName: PROVIDERS.find(p => p.id === form.providerId)?.name,
      providerId: form.providerId || undefined,
      minNoticeHours: Number(form.minNoticeHours),
      preferredDays: days,
      preferredTimeBlocks: blocks,
    }),
    onSuccess: () => {
      toast({ title: "Added to waitlist" });
      setForm({ patientName: "", patientPhone: "", patientEmail: "", appointmentType: "full_arch_consult", providerId: "", minNoticeHours: 2, notes: "" });
      setDays([]); setBlocks([]);
      onSaved();
    },
    onError: () => toast({ title: "Failed to add", variant: "destructive" }),
  });

  const canSubmit = form.patientName && form.patientPhone;

  return (
    <Card>
      <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Plus className="h-4 w-4 text-primary" /> Add to Waitlist</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        <div><Label>Patient name *</Label><Input value={form.patientName} onChange={e => setForm(f => ({ ...f, patientName: e.target.value }))} data-testid="input-wl-name" /></div>
        <div className="grid grid-cols-2 gap-3">
          <div><Label>Phone *</Label><Input value={form.patientPhone} onChange={e => setForm(f => ({ ...f, patientPhone: e.target.value }))} data-testid="input-wl-phone" /></div>
          <div><Label>Email</Label><Input value={form.patientEmail} onChange={e => setForm(f => ({ ...f, patientEmail: e.target.value }))} data-testid="input-wl-email" /></div>
        </div>
        <div>
          <Label>Appointment type</Label>
          <Select value={form.appointmentType} onValueChange={v => setForm(f => ({ ...f, appointmentType: v }))}>
            <SelectTrigger data-testid="select-wl-type"><SelectValue /></SelectTrigger>
            <SelectContent>{APPT_TYPES.map(t => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div>
          <Label>Provider preference</Label>
          <Select value={form.providerId || "any"} onValueChange={v => setForm(f => ({ ...f, providerId: v === "any" ? "" : v }))}>
            <SelectTrigger data-testid="select-wl-provider"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="any">Any provider</SelectItem>
              {PROVIDERS.map(p => <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label>Minimum notice needed</Label>
          <Select value={String(form.minNoticeHours)} onValueChange={v => setForm(f => ({ ...f, minNoticeHours: Number(v) }))}>
            <SelectTrigger data-testid="select-wl-notice"><SelectValue /></SelectTrigger>
            <SelectContent>{NOTICE_OPTS.map(o => <SelectItem key={o.value} value={String(o.value)}>{o.label}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div>
          <Label>Preferred days</Label>
          <div className="mt-1 flex flex-wrap gap-1.5">
            {DAYS.map(d => (
              <button key={d.value} type="button" onClick={() => toggle(days, setDays, d.value)}
                className={`rounded-md border px-2.5 py-1 text-xs transition ${days.includes(d.value) ? "border-primary bg-primary text-primary-foreground" : "border-input hover:bg-muted"}`}
                data-testid={`day-${d.value}`}>{d.label}</button>
            ))}
          </div>
        </div>
        <div>
          <Label>Preferred time</Label>
          <div className="mt-1 flex flex-wrap gap-1.5">
            {TIME_BLOCKS.map(b => (
              <button key={b.value} type="button" onClick={() => toggle(blocks, setBlocks, b.value)}
                className={`rounded-md border px-2.5 py-1 text-xs transition ${blocks.includes(b.value) ? "border-primary bg-primary text-primary-foreground" : "border-input hover:bg-muted"}`}
                data-testid={`block-${b.value}`}>{b.label}</button>
            ))}
          </div>
        </div>
        <div><Label>Notes</Label><Textarea rows={2} value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} data-testid="input-wl-notes" /></div>
        <Button className="w-full" disabled={!canSubmit || mut.isPending} onClick={() => mut.mutate()} data-testid="button-add-waitlist">
          {mut.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}
          Add to Waitlist
        </Button>
      </CardContent>
    </Card>
  );
}

function StatCard({ icon: Icon, label, value, tone }: { icon: any; label: string; value: number | string; tone: string }) {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 p-4">
        <div className={`flex h-9 w-9 items-center justify-center rounded-lg bg-muted ${tone}`}><Icon className="h-4 w-4" /></div>
        <div>
          <div className="text-xl font-semibold" data-testid={`wl-stat-${label.toLowerCase().replace(/[^a-z]+/g, "-")}`}>{value}</div>
          <div className="text-xs text-muted-foreground">{label}</div>
        </div>
      </CardContent>
    </Card>
  );
}
