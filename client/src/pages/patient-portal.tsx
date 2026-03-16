import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  User, Calendar, FileText, DollarSign, ClipboardList,
  ChevronRight, CheckCircle, Clock, AlertCircle, Search,
  Shield, Phone, Mail, Download, Eye,
} from "lucide-react";

// ─── Types ─────────────────────────────────────────────────────────────────
interface Patient {
  id: number; firstName: string; lastName: string;
  dateOfBirth: string | null; phone: string | null; email: string | null;
  address: string | null; city: string | null; state: string | null;
}
interface Appointment {
  id: number; patientId: number; title: string; appointmentType: string;
  startTime: string; endTime: string; status: string; providerName: string | null;
}
interface TreatmentPlan {
  id: number; patientId: number; title: string; status: string;
  totalCost: string | null; insuranceCoverage: string | null; patientResponsibility: string | null;
}
interface ConsentForm {
  id: number; patientId: number; formType: string; status: string; createdAt: string;
}
interface Document {
  id: number; patientId: number; documentType: string; fileName: string; createdAt: string;
}

const APPT_STATUS_CFG: Record<string, { label: string; color: string; icon: any }> = {
  scheduled:   { label: "Scheduled",  color: "text-blue-600 dark:text-blue-400",    icon: Clock },
  confirmed:   { label: "Confirmed",  color: "text-teal-600 dark:text-teal-400",    icon: CheckCircle },
  completed:   { label: "Completed",  color: "text-emerald-600 dark:text-emerald-400", icon: CheckCircle },
  no_show:     { label: "No Show",    color: "text-red-600 dark:text-red-400",       icon: AlertCircle },
  cancelled:   { label: "Cancelled",  color: "text-orange-600 dark:text-orange-400", icon: AlertCircle },
};

// ─── Patient Selector ─────────────────────────────────────────────────────
function PatientSelector({ patients, selected, onSelect }: {
  patients: Patient[]; selected: Patient | null; onSelect: (p: Patient) => void;
}) {
  const [search, setSearch] = useState("");
  const filtered = patients.filter(p =>
    `${p.firstName} ${p.lastName}`.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-3">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          className="pl-9"
          placeholder="Search patient name…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          data-testid="input-patient-search"
        />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 max-h-[400px] overflow-y-auto">
        {filtered.map(p => (
          <button
            key={p.id}
            onClick={() => onSelect(p)}
            className={`text-left px-4 py-3 rounded-lg border transition-colors ${
              selected?.id === p.id
                ? "border-primary bg-primary/5 text-primary"
                : "border-border hover:border-primary/40"
            }`}
            data-testid={`patient-card-${p.id}`}
          >
            <div className="font-semibold text-sm">{p.firstName} {p.lastName}</div>
            <div className="text-xs text-muted-foreground mt-0.5">{p.phone || p.email || "—"}</div>
          </button>
        ))}
      </div>
    </div>
  );
}

// ─── Portal View ───────────────────────────────────────────────────────────
function PortalView({ patient }: { patient: Patient }) {
  const { data: allAppts = [] } = useQuery<Appointment[]>({ queryKey: ["/api/appointments"] });
  const { data: allPlans = [] } = useQuery<TreatmentPlan[]>({ queryKey: ["/api/treatment-plans"] });
  const { data: allConsent = [] } = useQuery<ConsentForm[]>({ queryKey: ["/api/consent-forms"] });
  const { data: allDocs = [] } = useQuery<Document[]>({ queryKey: ["/api/documents"] });

  const appts = allAppts.filter(a => a.patientId === patient.id).sort((a, b) => new Date(b.startTime).getTime() - new Date(a.startTime).getTime());
  const plans = allPlans.filter(p => p.patientId === patient.id);
  const consent = allConsent.filter(c => c.patientId === patient.id);
  const docs = allDocs.filter(d => d.patientId === patient.id);

  const upcoming = appts.filter(a => new Date(a.startTime) >= new Date() && a.status !== "cancelled");
  const past = appts.filter(a => new Date(a.startTime) < new Date() || a.status === "completed");

  const totalResponsibility = plans.reduce((acc, p) => acc + parseFloat(p.patientResponsibility || "0"), 0);
  const activePlan = plans.find(p => p.status === "active" || p.status === "approved");

  return (
    <div className="space-y-4">
      {/* Patient Header */}
      <Card className="border-primary/20 bg-primary/5">
        <CardContent className="pt-4 pb-4">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-full bg-primary/20 flex items-center justify-center">
              <span className="text-xl font-bold text-primary">
                {patient.firstName[0]}{patient.lastName[0]}
              </span>
            </div>
            <div>
              <h2 className="text-xl font-bold">{patient.firstName} {patient.lastName}</h2>
              <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1 text-sm text-muted-foreground">
                {patient.phone && <span className="flex items-center gap-1"><Phone className="h-3.5 w-3.5" />{patient.phone}</span>}
                {patient.email && <span className="flex items-center gap-1"><Mail className="h-3.5 w-3.5" />{patient.email}</span>}
                {patient.dateOfBirth && <span>DOB: {patient.dateOfBirth}</span>}
              </div>
            </div>
            <div className="ml-auto">
              <Badge variant="outline" className="text-xs border-primary/30 text-primary gap-1">
                <Shield className="h-3 w-3" /> HIPAA Protected
              </Badge>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Summary KPIs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Upcoming Visits", value: upcoming.length, icon: Calendar, color: "text-blue-600 dark:text-blue-400" },
          { label: "Active Treatment", value: activePlan ? "Yes" : "No", icon: ClipboardList, color: activePlan ? "text-emerald-600 dark:text-emerald-400" : "text-muted-foreground" },
          { label: "Est. Balance", value: `$${totalResponsibility.toLocaleString()}`, icon: DollarSign, color: totalResponsibility > 0 ? "text-amber-600 dark:text-amber-400" : "text-emerald-600 dark:text-emerald-400" },
          { label: "Documents", value: docs.length, icon: FileText, color: "" },
        ].map(k => (
          <Card key={k.label}>
            <CardContent className="pt-3 pb-3 flex items-center gap-3">
              <k.icon className={`h-5 w-5 ${k.color}`} />
              <div>
                <div className="text-[10px] text-muted-foreground uppercase tracking-wider">{k.label}</div>
                <div className={`text-lg font-bold font-mono ${k.color}`}>{k.value}</div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Tabs */}
      <Tabs defaultValue="appointments">
        <TabsList>
          <TabsTrigger value="appointments">Appointments ({appts.length})</TabsTrigger>
          <TabsTrigger value="treatment">Treatment Plans ({plans.length})</TabsTrigger>
          <TabsTrigger value="documents">Documents ({docs.length})</TabsTrigger>
          <TabsTrigger value="consent">Consent Forms ({consent.length})</TabsTrigger>
        </TabsList>

        {/* Appointments */}
        <TabsContent value="appointments" className="mt-3 space-y-3">
          {upcoming.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Upcoming</div>
              <div className="space-y-2">
                {upcoming.map(a => {
                  const cfg = APPT_STATUS_CFG[a.status] || APPT_STATUS_CFG.scheduled;
                  return (
                    <div key={a.id} className="flex items-center gap-3 px-4 py-3 rounded-lg border border-border bg-card" data-testid={`appt-${a.id}`}>
                      <Calendar className="h-5 w-5 text-primary shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="font-medium text-sm">{a.title}</div>
                        <div className="text-xs text-muted-foreground">
                          {new Date(a.startTime).toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })} at{" "}
                          {new Date(a.startTime).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}
                          {a.providerName && ` · ${a.providerName}`}
                        </div>
                      </div>
                      <Badge className={`text-[10px] border-0 bg-blue-500/10 ${cfg.color}`}>{cfg.label}</Badge>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
          {past.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Past Visits</div>
              <div className="space-y-2">
                {past.slice(0, 5).map(a => {
                  const cfg = APPT_STATUS_CFG[a.status] || APPT_STATUS_CFG.completed;
                  return (
                    <div key={a.id} className="flex items-center gap-3 px-4 py-2.5 rounded-lg border border-border/50 bg-muted/20" data-testid={`past-appt-${a.id}`}>
                      <CheckCircle className="h-4 w-4 text-muted-foreground shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="font-medium text-sm text-muted-foreground">{a.title}</div>
                        <div className="text-xs text-muted-foreground">
                          {new Date(a.startTime).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
                          {a.providerName && ` · ${a.providerName}`}
                        </div>
                      </div>
                      <span className={`text-[10px] ${cfg.color}`}>{cfg.label}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
          {appts.length === 0 && (
            <p className="text-sm text-muted-foreground italic py-4 text-center">No appointments on record.</p>
          )}
        </TabsContent>

        {/* Treatment Plans */}
        <TabsContent value="treatment" className="mt-3 space-y-3">
          {plans.length === 0 ? (
            <p className="text-sm text-muted-foreground italic py-4 text-center">No treatment plans on file.</p>
          ) : plans.map(p => (
            <Card key={p.id} data-testid={`plan-${p.id}`}>
              <CardContent className="pt-4 pb-4">
                <div className="flex items-start justify-between mb-2">
                  <div className="font-semibold">{p.title}</div>
                  <Badge variant="outline" className="text-xs capitalize">{p.status}</Badge>
                </div>
                <div className="grid grid-cols-3 gap-3 text-xs">
                  {[
                    { label: "Total Cost", value: p.totalCost ? `$${parseFloat(p.totalCost).toLocaleString()}` : "—" },
                    { label: "Insurance Est.", value: p.insuranceCoverage ? `$${parseFloat(p.insuranceCoverage).toLocaleString()}` : "—" },
                    { label: "Patient Est.", value: p.patientResponsibility ? `$${parseFloat(p.patientResponsibility).toLocaleString()}` : "—" },
                  ].map(item => (
                    <div key={item.label}>
                      <div className="text-muted-foreground">{item.label}</div>
                      <div className="font-bold">{item.value}</div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </TabsContent>

        {/* Documents */}
        <TabsContent value="documents" className="mt-3 space-y-2">
          {docs.length === 0 ? (
            <p className="text-sm text-muted-foreground italic py-4 text-center">No documents on file.</p>
          ) : docs.map(d => (
            <div key={d.id} className="flex items-center gap-3 px-4 py-3 rounded-lg border border-border" data-testid={`doc-${d.id}`}>
              <FileText className="h-5 w-5 text-muted-foreground shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="font-medium text-sm truncate">{d.fileName}</div>
                <div className="text-xs text-muted-foreground capitalize">{d.documentType.replace(/_/g, " ")} · {new Date(d.createdAt).toLocaleDateString()}</div>
              </div>
              <button className="text-muted-foreground hover:text-primary" data-testid={`btn-view-doc-${d.id}`}>
                <Eye className="h-4 w-4" />
              </button>
            </div>
          ))}
        </TabsContent>

        {/* Consent Forms */}
        <TabsContent value="consent" className="mt-3 space-y-2">
          {consent.length === 0 ? (
            <p className="text-sm text-muted-foreground italic py-4 text-center">No consent forms on file.</p>
          ) : consent.map(c => (
            <div key={c.id} className="flex items-center gap-3 px-4 py-3 rounded-lg border border-border" data-testid={`consent-${c.id}`}>
              <Shield className={`h-5 w-5 shrink-0 ${c.status === "signed" ? "text-emerald-500" : "text-amber-500"}`} />
              <div className="flex-1 min-w-0">
                <div className="font-medium text-sm capitalize">{c.formType.replace(/_/g, " ")} Consent</div>
                <div className="text-xs text-muted-foreground">{new Date(c.createdAt).toLocaleDateString()}</div>
              </div>
              <Badge className={`text-[10px] capitalize border ${c.status === "signed" ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-400/30" : "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-400/30"}`}>
                {c.status}
              </Badge>
            </div>
          ))}
        </TabsContent>
      </Tabs>
    </div>
  );
}

// ─── Main Page ─────────────────────────────────────────────────────────────
export default function PatientPortalPage() {
  const [selectedPatient, setSelectedPatient] = useState<Patient | null>(null);

  const { data: patients = [], isLoading } = useQuery<Patient[]>({ queryKey: ["/api/patients"] });

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">Patient Portal</h1>
        <p className="text-sm text-muted-foreground">Full patient view — appointments, treatment plans, documents, consent forms, and billing summary</p>
      </div>

      {!selectedPatient ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <User className="h-4 w-4" /> Select a Patient
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="text-center py-6 text-muted-foreground text-sm">Loading patients…</div>
            ) : (
              <PatientSelector patients={patients} selected={selectedPatient} onSelect={setSelectedPatient} />
            )}
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          <Button variant="outline" size="sm" onClick={() => setSelectedPatient(null)} data-testid="button-back">
            ← All Patients
          </Button>
          <PortalView patient={selectedPatient} />
        </div>
      )}
    </div>
  );
}
