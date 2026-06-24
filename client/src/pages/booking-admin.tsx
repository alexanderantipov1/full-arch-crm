import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { apiRequest } from "@/lib/queryClient";
import {
  Globe, Clock, CheckCircle, CalendarDays, Phone, Mail, Loader2,
  XCircle, RefreshCcw, TrendingUp, Search,
} from "lucide-react";

interface TimeSlot {
  date: string; time: string; providerId: string; providerName: string;
  durationMinutes: number; available: boolean;
}
interface Booking {
  id: string;
  firstName: string; lastName: string; email: string; phone: string;
  appointmentType: string;
  preferredDate: string; preferredTime: string;
  providerId?: string;
  insuranceCarrier?: string;
  notes?: string;
  source: string;
  status: "pending" | "confirmed" | "cancelled" | "rescheduled";
  confirmedSlot?: TimeSlot;
  confirmationNumber: string;
  createdAt: string;
}

const TYPE_LABELS: Record<string, string> = {
  full_arch_consult: "Full Arch Consult", implant_consult: "Implant Consult",
  implant_placement: "Implant Placement", new_patient_exam: "New Patient Exam",
  recall_hygiene: "Hygiene Recall", emergency: "Emergency", post_op: "Post-Op",
  treatment_consult: "Treatment Consult",
};

const SOURCE_LABELS: Record<string, string> = {
  website: "Website", google: "Google", facebook: "Facebook", referral: "Referral", direct: "Direct",
};

const STATUS_CFG: Record<string, { label: string; cls: string }> = {
  pending: { label: "Pending", cls: "bg-amber-500/10 text-amber-600 border-amber-400/40" },
  confirmed: { label: "Confirmed", cls: "bg-emerald-500/10 text-emerald-600 border-emerald-400/40" },
  cancelled: { label: "Cancelled", cls: "bg-red-500/10 text-red-600 border-red-400/40" },
  rescheduled: { label: "Rescheduled", cls: "bg-blue-500/10 text-blue-600 border-blue-400/40" },
};

function prettyDate(s: string) {
  if (!s) return "—";
  return new Date(s + (s.includes("T") ? "" : "T00:00:00")).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}
function prettyTime(t: string) {
  if (!t) return "";
  const [h, m] = t.split(":").map(Number);
  const period = h >= 12 ? "PM" : "AM";
  const hr = h % 12 === 0 ? 12 : h % 12;
  return `${hr}:${m.toString().padStart(2, "0")} ${period}`;
}
function isToday(s: string) {
  if (!s) return false;
  return s.split("T")[0] === new Date().toISOString().split("T")[0];
}

export default function BookingAdminPage() {
  const { toast } = useToast();
  const qc = useQueryClient();
  const [statusFilter, setStatusFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");

  const { data: bookings = [], isLoading } = useQuery<Booking[]>({
    queryKey: ["/api/booking/all"],
    refetchInterval: 30000,
  });

  const statusMut = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      apiRequest("PATCH", `/api/booking/${id}/status`, { status }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["/api/booking/all"] });
      toast({ title: "Booking updated" });
    },
    onError: () => toast({ title: "Update failed", variant: "destructive" }),
  });

  const confirmMut = useMutation({
    mutationFn: (b: Booking) => apiRequest("POST", `/api/booking/confirm/${b.id}`, {
      slot: {
        date: b.preferredDate, time: b.preferredTime,
        providerId: b.providerId ?? "prov-1",
        providerName: b.providerId === "prov-2" ? "Dr. Johnson" : "Dr. Antipov",
        durationMinutes: 60, available: false,
      },
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["/api/booking/all"] });
      toast({ title: "Appointment confirmed" });
    },
    onError: () => toast({ title: "Confirm failed", variant: "destructive" }),
  });

  const stats = useMemo(() => {
    const pending = bookings.filter(b => b.status === "pending").length;
    const confirmedToday = bookings.filter(b => b.status === "confirmed" && (isToday(b.confirmedSlot?.date ?? b.preferredDate))).length;
    const bySource: Record<string, number> = {};
    bookings.forEach(b => { bySource[b.source] = (bySource[b.source] ?? 0) + 1; });
    return { pending, confirmedToday, total: bookings.length, bySource };
  }, [bookings]);

  const maxSource = Math.max(1, ...Object.values(stats.bySource));

  const filtered = bookings.filter(b =>
    (statusFilter === "all" || b.status === statusFilter) &&
    (typeFilter === "all" || b.appointmentType === typeFilter)
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <Globe className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-2xl font-semibold">Online Booking</h1>
          <p className="text-sm text-muted-foreground">Patient-submitted appointment requests from your website & Google profile</p>
        </div>
      </div>

      {/* Stats */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={Clock} label="Pending" value={stats.pending} tone="text-amber-600" />
        <StatCard icon={CheckCircle} label="Confirmed Today" value={stats.confirmedToday} tone="text-emerald-600" />
        <StatCard icon={CalendarDays} label="Total Requests" value={stats.total} tone="text-blue-600" />
        <StatCard icon={TrendingUp} label="Top Source" value={
          Object.entries(stats.bySource).sort((a, b) => b[1] - a[1])[0]?.[0]
            ? SOURCE_LABELS[Object.entries(stats.bySource).sort((a, b) => b[1] - a[1])[0][0]] ?? "—"
            : "—"
        } tone="text-purple-600" />
      </div>

      {/* Source analytics */}
      <Card>
        <CardHeader><CardTitle className="text-base">Bookings by Source</CardTitle></CardHeader>
        <CardContent>
          {Object.keys(stats.bySource).length === 0 ? (
            <p className="text-sm text-muted-foreground">No bookings yet.</p>
          ) : (
            <div className="space-y-3">
              {Object.entries(stats.bySource).sort((a, b) => b[1] - a[1]).map(([src, count]) => (
                <div key={src} className="flex items-center gap-3" data-testid={`source-bar-${src}`}>
                  <span className="w-24 shrink-0 text-sm text-muted-foreground">{SOURCE_LABELS[src] ?? src}</span>
                  <div className="h-6 flex-1 overflow-hidden rounded-md bg-muted">
                    <div className="flex h-full items-center justify-end rounded-md bg-primary px-2 text-xs font-medium text-primary-foreground" style={{ width: `${(count / maxSource) * 100}%` }}>
                      {count}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-40" data-testid="filter-status"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
            <SelectItem value="confirmed">Confirmed</SelectItem>
            <SelectItem value="cancelled">Cancelled</SelectItem>
            <SelectItem value="rescheduled">Rescheduled</SelectItem>
          </SelectContent>
        </Select>
        <Select value={typeFilter} onValueChange={setTypeFilter}>
          <SelectTrigger className="w-48" data-testid="filter-type"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All types</SelectItem>
            {Object.entries(TYPE_LABELS).map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="flex items-center justify-center py-16 text-muted-foreground"><Loader2 className="mr-2 h-5 w-5 animate-spin" /> Loading…</div>
          ) : filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-2 py-16 text-muted-foreground">
              <Search className="h-8 w-8 opacity-40" />
              <p className="text-sm">No booking requests match your filters.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th className="px-4 py-3">Patient</th>
                    <th className="px-4 py-3">Type</th>
                    <th className="px-4 py-3">Preferred</th>
                    <th className="px-4 py-3">Source</th>
                    <th className="px-4 py-3">Contact</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(b => {
                    const cfg = STATUS_CFG[b.status];
                    return (
                      <tr key={b.id} className="border-b last:border-0 hover:bg-muted/20" data-testid={`booking-row-${b.id}`}>
                        <td className="px-4 py-3">
                          <div className="font-medium">{b.firstName} {b.lastName}</div>
                          <div className="font-mono text-xs text-muted-foreground">{b.confirmationNumber}</div>
                        </td>
                        <td className="px-4 py-3">{TYPE_LABELS[b.appointmentType] ?? b.appointmentType}</td>
                        <td className="px-4 py-3 whitespace-nowrap">{prettyDate(b.preferredDate)} · {prettyTime(b.preferredTime)}</td>
                        <td className="px-4 py-3"><Badge variant="outline">{SOURCE_LABELS[b.source] ?? b.source}</Badge></td>
                        <td className="px-4 py-3">
                          <div className="flex flex-col gap-0.5 text-xs text-muted-foreground">
                            <a href={`tel:${b.phone}`} className="inline-flex items-center gap-1 hover:text-foreground"><Phone className="h-3 w-3" /> {b.phone}</a>
                            <a href={`mailto:${b.email}`} className="inline-flex items-center gap-1 hover:text-foreground"><Mail className="h-3 w-3" /> {b.email}</a>
                          </div>
                        </td>
                        <td className="px-4 py-3"><Badge variant="outline" className={cfg.cls}>{cfg.label}</Badge></td>
                        <td className="px-4 py-3">
                          <div className="flex justify-end gap-1.5">
                            {b.status === "pending" && (
                              <Button size="sm" variant="default" disabled={confirmMut.isPending} onClick={() => confirmMut.mutate(b)} data-testid={`button-confirm-${b.id}`}>
                                <CheckCircle className="mr-1 h-3.5 w-3.5" /> Confirm
                              </Button>
                            )}
                            {b.status !== "rescheduled" && b.status !== "cancelled" && (
                              <Button size="sm" variant="outline" onClick={() => statusMut.mutate({ id: b.id, status: "rescheduled" })} data-testid={`button-reschedule-${b.id}`}>
                                <RefreshCcw className="h-3.5 w-3.5" />
                              </Button>
                            )}
                            {b.status !== "cancelled" && (
                              <Button size="sm" variant="ghost" className="text-red-600 hover:text-red-700" onClick={() => statusMut.mutate({ id: b.id, status: "cancelled" })} data-testid={`button-cancel-${b.id}`}>
                                <XCircle className="h-3.5 w-3.5" />
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

function StatCard({ icon: Icon, label, value, tone }: { icon: any; label: string; value: number | string; tone: string }) {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 p-4">
        <div className={`flex h-10 w-10 items-center justify-center rounded-lg bg-muted ${tone}`}><Icon className="h-5 w-5" /></div>
        <div>
          <div className="text-2xl font-semibold" data-testid={`stat-${label.toLowerCase().replace(/\s+/g, "-")}`}>{value}</div>
          <div className="text-xs text-muted-foreground">{label}</div>
        </div>
      </CardContent>
    </Card>
  );
}
