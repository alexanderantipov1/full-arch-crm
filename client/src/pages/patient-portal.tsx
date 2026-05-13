import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  User, Calendar, FileText, DollarSign, ClipboardList,
  CheckCircle, Clock, AlertCircle, Search,
  Shield, Phone, Mail, Eye, Send, CreditCard,
  MessageSquare, Stethoscope, CalendarPlus, Heart,
  Edit, Receipt, Download, MapPin,
} from "lucide-react";
import { apiRequest, queryClient } from "@/lib/queryClient";
import { useToast } from "@/hooks/use-toast";

// ─── Types ─────────────────────────────────────────────────────────────────
interface Patient {
  id: number; firstName: string; lastName: string;
  dateOfBirth: string | null; phone: string | null; email: string | null;
  address: string | null; city: string | null; state: string | null; zipCode: string | null;
}
interface Appointment {
  id: number; patientId: number; title: string; appointmentType: string;
  startTime: string; endTime: string; status: string; providerName: string | null;
}
interface TreatmentPlan {
  id: number; patientId: number; planName: string; status: string;
  totalCost: string | null; insuranceCoverage: string | null; patientResponsibility: string | null;
}
interface BillingClaim {
  id: number; patientId: number; claimNumber: string | null; claimStatus: string;
  serviceDate: string; procedureCode: string; description: string | null;
  chargedAmount: string; allowedAmount: string | null; paidAmount: string | null;
  patientPortion: string | null; denialReason: string | null; paidDate: string | null;
}
interface ConsentForm {
  id: number; patientId: number; formType: string; status: string; createdAt: string;
}
interface Document {
  id: number; patientId: number; documentType: string; fileName: string;
  fileUrl: string; createdAt: string;
}
interface SurgeryReport {
  id: number; patientId: number; surgeryDate: string; surgeryType: string;
  surgeon: string | null; postOpInstructions: string | null; followUpPlan: string | null;
  createdAt: string;
}
interface PortalAppointmentRequest {
  id: number; patientId: number; preferredDate: string | null; preferredTime: string | null;
  reason: string; appointmentType: string | null; status: string; createdAt: string;
}
interface PaymentPosting {
  id: number; patientId: number | null; claimId: number | null;
  paymentDate: string; payerName: string; checkNumber: string | null;
  paymentAmount: string; adjustmentAmount: string | null;
  patientResponsibility: string | null; postingStatus: string; createdAt: string;
}

const APPT_STATUS_CFG: Record<string, { label: string; color: string; icon: typeof Clock }> = {
  scheduled:   { label: "Scheduled",  color: "text-blue-600 dark:text-blue-400",       icon: Clock },
  confirmed:   { label: "Confirmed",  color: "text-teal-600 dark:text-teal-400",       icon: CheckCircle },
  completed:   { label: "Completed",  color: "text-emerald-600 dark:text-emerald-400", icon: CheckCircle },
  no_show:     { label: "No Show",    color: "text-red-600 dark:text-red-400",         icon: AlertCircle },
  cancelled:   { label: "Cancelled",  color: "text-orange-600 dark:text-orange-400",   icon: AlertCircle },
};

const REQUEST_STATUS_CFG: Record<string, { label: string; cls: string }> = {
  pending:   { label: "Pending",   cls: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-400/30" },
  confirmed: { label: "Confirmed", cls: "bg-teal-500/10 text-teal-600 dark:text-teal-400 border-teal-400/30" },
  completed: { label: "Completed", cls: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-400/30" },
  cancelled: { label: "Cancelled", cls: "bg-red-500/10 text-red-600 dark:text-red-400 border-red-400/30" },
};

const fmt$ = (v: string | null | undefined) =>
  v ? `$${parseFloat(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : "—";

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
        {filtered.length === 0 && (
          <p className="col-span-3 text-center py-6 text-sm text-muted-foreground">No patients found.</p>
        )}
      </div>
    </div>
  );
}

// ─── My Info Tab (Contact Update) ─────────────────────────────────────────
function MyInfoTab({ patient, onAuditLog }: { patient: Patient; onAuditLog: (tab: string) => void }) {
  const { toast } = useToast();
  const [form, setForm] = useState({
    phone: patient.phone || "",
    email: patient.email || "",
    address: patient.address || "",
    city: patient.city || "",
    state: patient.state || "",
    zipCode: patient.zipCode || "",
  });

  const updateMutation = useMutation({
    mutationFn: () => apiRequest("PATCH", `/api/patients/${patient.id}`, form),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/patients"] });
      onAuditLog("my_info_update");
      toast({ title: "Contact info updated", description: "Your information has been saved." });
    },
    onError: () => toast({ title: "Update failed", variant: "destructive" }),
  });

  const field = (label: string, key: keyof typeof form, type = "text", testId = "") => (
    <div className="space-y-1.5">
      <Label htmlFor={key}>{label}</Label>
      <Input
        id={key}
        type={type}
        value={form[key]}
        onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
        data-testid={testId || `input-${key}`}
      />
    </div>
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          <Edit className="h-4 w-4 text-primary" /> My Contact Information
        </CardTitle>
        <CardDescription>Keep your contact details up to date for appointment reminders and billing</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          {field("Phone Number", "phone", "tel", "input-portal-phone")}
          {field("Email Address", "email", "email", "input-portal-email")}
        </div>
        {field("Street Address", "address", "text", "input-portal-address")}
        <div className="grid gap-4 sm:grid-cols-3">
          {field("City", "city")}
          {field("State", "state")}
          {field("ZIP Code", "zipCode")}
        </div>
        <div className="pt-1">
          <Button
            onClick={() => updateMutation.mutate()}
            disabled={updateMutation.isPending}
            data-testid="button-save-contact"
          >
            {updateMutation.isPending ? "Saving…" : "Save Changes"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// ─── EOB / Explanation of Benefits Tab ────────────────────────────────────
function EobTab({ patient, onAuditLog }: { patient: Patient; onAuditLog: (tab: string) => void }) {
  const { data: claims = [], isLoading: claimsLoading } = useQuery<BillingClaim[]>({
    queryKey: ["/api/billing/claims", { patientId: patient.id }],
    queryFn: () => fetch(`/api/billing/claims?patientId=${patient.id}`, { credentials: "include" }).then(r => r.json()),
  });
  const { data: postings = [], isLoading: postingsLoading } = useQuery<PaymentPosting[]>({
    queryKey: ["/api/payment-postings/patient", patient.id],
    queryFn: () => fetch(`/api/payment-postings/patient/${patient.id}`, { credentials: "include" }).then(r => r.json()),
  });

  const isLoading = claimsLoading || postingsLoading;
  const paidClaims = claims.filter(c => c.claimStatus === "paid" || c.paidAmount);

  return (
    <div className="space-y-4">
      {/* Summary */}
      {postings.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Receipt className="h-4 w-4 text-primary" /> Insurance Payment Explanations (EOB)
            </CardTitle>
            <CardDescription>Payments received from your insurance carrier</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {postings.map(p => (
              <div key={p.id} className="rounded-lg border p-4" data-testid={`eob-posting-${p.id}`}>
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <div className="font-semibold">{p.payerName}</div>
                    <div className="text-xs text-muted-foreground">
                      Payment Date: {new Date(p.paymentDate).toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" })}
                      {p.checkNumber && ` · Check #${p.checkNumber}`}
                    </div>
                  </div>
                  <Badge
                    variant="outline"
                    className={`capitalize text-xs ${
                      p.postingStatus === "posted" ? "border-emerald-400/40 text-emerald-600" : "border-amber-400/40 text-amber-600"
                    }`}
                  >
                    {p.postingStatus}
                  </Badge>
                </div>
                <div className="grid grid-cols-3 gap-3 text-sm">
                  <div>
                    <div className="text-xs text-muted-foreground mb-0.5">Insurance Paid</div>
                    <div className="font-bold text-emerald-600 dark:text-emerald-400">{fmt$(p.paymentAmount)}</div>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground mb-0.5">Adjustment</div>
                    <div className="font-medium">{fmt$(p.adjustmentAmount)}</div>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground mb-0.5">Patient Portion</div>
                    <div className={`font-bold ${p.patientResponsibility && parseFloat(p.patientResponsibility) > 0 ? "text-amber-600 dark:text-amber-400" : ""}`}>
                      {fmt$(p.patientResponsibility)}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Claim-level EOB data */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <ClipboardList className="h-4 w-4 text-primary" /> Claim Detail
          </CardTitle>
          <CardDescription>Breakdown of each service claim and insurance response</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-sm text-muted-foreground py-4 text-center">Loading claims…</p>
          ) : claims.length === 0 ? (
            <div className="text-center py-8">
              <Receipt className="mx-auto h-9 w-9 text-muted-foreground/40 mb-3" />
              <p className="text-sm text-muted-foreground">No claims on file yet.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {claims.map(c => (
                <div
                  key={c.id}
                  className="rounded-lg border p-3"
                  data-testid={`eob-claim-${c.id}`}
                >
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <div className="font-medium text-sm">
                        {c.procedureCode}{c.description ? ` — ${c.description}` : ""}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        Service: {new Date(c.serviceDate).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
                        {c.claimNumber && ` · Claim #${c.claimNumber}`}
                      </div>
                    </div>
                    <Badge
                      className={`capitalize text-[10px] border ${
                        c.claimStatus === "paid" ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-400/30" :
                        c.claimStatus === "denied" ? "bg-red-500/10 text-red-600 dark:text-red-400 border-red-400/30" :
                        c.claimStatus === "submitted" ? "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-400/30" :
                        "bg-muted text-muted-foreground border-border"
                      }`}
                    >
                      {c.claimStatus}
                    </Badge>
                  </div>
                  <div className="grid grid-cols-4 gap-2 text-xs">
                    <div>
                      <div className="text-muted-foreground">Charged</div>
                      <div className="font-semibold">{fmt$(c.chargedAmount)}</div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">Allowed</div>
                      <div className="font-semibold">{fmt$(c.allowedAmount)}</div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">Insurance Paid</div>
                      <div className="font-semibold text-emerald-600 dark:text-emerald-400">{fmt$(c.paidAmount)}</div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">Patient Owes</div>
                      <div className={`font-semibold ${c.patientPortion && parseFloat(c.patientPortion) > 0 ? "text-amber-600 dark:text-amber-400" : ""}`}>
                        {fmt$(c.patientPortion)}
                      </div>
                    </div>
                  </div>
                  {c.denialReason && (
                    <div className="mt-2 flex items-start gap-1.5 text-xs text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/20 rounded p-2">
                      <AlertCircle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
                      <span><strong>Denial reason:</strong> {c.denialReason}</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// ─── Appointment Request Form ──────────────────────────────────────────────
function AppointmentRequestTab({ patient }: { patient: Patient }) {
  const { toast } = useToast();
  const [form, setForm] = useState({
    reason: "",
    preferredDate: "",
    preferredTime: "",
    appointmentType: "consultation",
  });

  const { data: existingRequests = [], isLoading: reqLoading } = useQuery<PortalAppointmentRequest[]>({
    queryKey: ["/api/portal/appointment-requests", patient.id],
    queryFn: () => fetch(`/api/portal/appointment-requests?patientId=${patient.id}`, { credentials: "include" }).then(r => r.json()),
  });

  const createMutation = useMutation({
    mutationFn: (data: typeof form) =>
      apiRequest("POST", "/api/portal/appointment-requests", { ...data, patientId: patient.id }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/portal/appointment-requests", patient.id] });
      setForm({ reason: "", preferredDate: "", preferredTime: "", appointmentType: "consultation" });
      toast({ title: "Request submitted", description: "Your appointment request has been sent to the practice." });
    },
    onError: () => toast({ title: "Failed to submit request", variant: "destructive" }),
  });

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <CalendarPlus className="h-4 w-4 text-primary" /> New Appointment Request
          </CardTitle>
          <CardDescription>Tell us when you'd like to come in and why</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="appt-type">Appointment Type</Label>
              <Select
                value={form.appointmentType}
                onValueChange={v => setForm(f => ({ ...f, appointmentType: v }))}
              >
                <SelectTrigger id="appt-type" data-testid="select-appt-type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="consultation">Consultation</SelectItem>
                  <SelectItem value="follow_up">Follow-up Visit</SelectItem>
                  <SelectItem value="post_op">Post-Op Check</SelectItem>
                  <SelectItem value="emergency">Urgent / Emergency</SelectItem>
                  <SelectItem value="maintenance">Maintenance Cleaning</SelectItem>
                  <SelectItem value="imaging">X-Ray / Imaging</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="preferred-date">Preferred Date</Label>
              <Input
                id="preferred-date"
                type="date"
                value={form.preferredDate}
                onChange={e => setForm(f => ({ ...f, preferredDate: e.target.value }))}
                data-testid="input-preferred-date"
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="preferred-time">Preferred Time</Label>
            <Select
              value={form.preferredTime}
              onValueChange={v => setForm(f => ({ ...f, preferredTime: v }))}
            >
              <SelectTrigger id="preferred-time" data-testid="select-preferred-time">
                <SelectValue placeholder="Any time" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="morning">Morning (8am – 12pm)</SelectItem>
                <SelectItem value="afternoon">Afternoon (12pm – 4pm)</SelectItem>
                <SelectItem value="late_afternoon">Late Afternoon (4pm – 6pm)</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="reason">Reason for Visit <span className="text-destructive">*</span></Label>
            <Textarea
              id="reason"
              placeholder="Describe your concern or the reason for your visit…"
              value={form.reason}
              onChange={e => setForm(f => ({ ...f, reason: e.target.value }))}
              rows={3}
              data-testid="textarea-reason"
            />
          </div>
          <Button
            onClick={() => createMutation.mutate(form)}
            disabled={!form.reason.trim() || createMutation.isPending}
            data-testid="button-submit-appt-request"
          >
            <Send className="mr-2 h-4 w-4" />
            {createMutation.isPending ? "Submitting…" : "Submit Request"}
          </Button>
        </CardContent>
      </Card>

      {(reqLoading || existingRequests.length > 0) && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm text-muted-foreground uppercase tracking-wider">Previous Requests</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {reqLoading ? (
              <p className="text-sm text-muted-foreground">Loading…</p>
            ) : existingRequests.map(r => {
              const cfg = REQUEST_STATUS_CFG[r.status] || REQUEST_STATUS_CFG.pending;
              return (
                <div key={r.id} className="flex items-start justify-between gap-3 px-4 py-3 rounded-lg border border-border" data-testid={`req-${r.id}`}>
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-sm capitalize">{(r.appointmentType || "consultation").replace(/_/g, " ")}</div>
                    <div className="text-xs text-muted-foreground mt-0.5">{r.reason}</div>
                    {r.preferredDate && (
                      <div className="text-xs text-muted-foreground mt-0.5">
                        Preferred: {r.preferredDate}{r.preferredTime ? ` · ${r.preferredTime.replace(/_/g, " ")}` : ""}
                      </div>
                    )}
                  </div>
                  <Badge className={`text-[10px] capitalize border shrink-0 ${cfg.cls}`}>{cfg.label}</Badge>
                </div>
              );
            })}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ─── Message Compose ──────────────────────────────────────────────────────
function MessageTab({ patient }: { patient: Patient }) {
  const { toast } = useToast();
  const [message, setMessage] = useState("");

  const { data: messages = [] } = useQuery<Array<{ id: number; body: string; direction: string; createdAt: string; isRead: boolean }>>({
    queryKey: ["/api/patient-messages", patient.id],
    queryFn: () => fetch(`/api/patient-messages?patientId=${patient.id}`, { credentials: "include" }).then(r => r.json()),
  });

  const sendMutation = useMutation({
    mutationFn: () =>
      apiRequest("POST", "/api/patient-messages", {
        patientId: patient.id,
        body: message,
        direction: "inbound",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/patient-messages", patient.id] });
      queryClient.invalidateQueries({ queryKey: ["/api/patient-messages/threads"] });
      setMessage("");
      toast({ title: "Message sent", description: "Your message has been sent to the care team." });
    },
    onError: () => toast({ title: "Failed to send message", variant: "destructive" }),
  });

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <MessageSquare className="h-4 w-4 text-primary" /> Message the Care Team
          </CardTitle>
          <CardDescription>Questions about your treatment, appointment, or billing? Send us a message.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Textarea
            placeholder="Type your message here…"
            value={message}
            onChange={e => setMessage(e.target.value)}
            rows={4}
            data-testid="textarea-message"
          />
          <Button
            onClick={() => sendMutation.mutate()}
            disabled={!message.trim() || sendMutation.isPending}
            data-testid="button-send-message"
          >
            <Send className="mr-2 h-4 w-4" />
            {sendMutation.isPending ? "Sending…" : "Send Message"}
          </Button>
        </CardContent>
      </Card>

      {messages.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm text-muted-foreground uppercase tracking-wider">Message History</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 max-h-[300px] overflow-y-auto">
            {[...messages].reverse().map(m => (
              <div
                key={m.id}
                className={`px-3 py-2.5 rounded-lg text-sm max-w-[80%] ${
                  m.direction === "inbound"
                    ? "ml-auto bg-primary/10 text-primary"
                    : "bg-muted text-foreground"
                }`}
                data-testid={`message-${m.id}`}
              >
                <div>{m.body}</div>
                <div className="text-[10px] mt-1 opacity-60 text-right">
                  {new Date(m.createdAt).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ─── Post-Op Instructions ─────────────────────────────────────────────────
function PostOpTab({ patient }: { patient: Patient }) {
  const { data: reports = [], isLoading } = useQuery<SurgeryReport[]>({
    queryKey: ["/api/surgery-reports/patient", patient.id],
    queryFn: () => fetch(`/api/surgery-reports/patient/${patient.id}`, { credentials: "include" }).then(r => r.json()),
  });
  const withInstructions = reports.filter(r => r.postOpInstructions || r.followUpPlan);

  return (
    <div className="space-y-4">
      {isLoading ? (
        <p className="text-sm text-muted-foreground text-center py-6">Loading post-op instructions…</p>
      ) : withInstructions.length === 0 ? (
        <div className="text-center py-10">
          <Heart className="mx-auto h-10 w-10 text-muted-foreground/40 mb-3" />
          <p className="text-sm text-muted-foreground">No post-operative instructions on file yet.</p>
          <p className="text-xs text-muted-foreground mt-1">Your care team will add these after your procedure.</p>
        </div>
      ) : withInstructions.map(r => (
        <Card key={r.id} data-testid={`post-op-${r.id}`}>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-base flex items-center gap-2">
                  <Stethoscope className="h-4 w-4 text-primary" />{r.surgeryType}
                </CardTitle>
                <CardDescription>
                  {new Date(r.surgeryDate).toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" })}
                  {r.surgeon && ` · Dr. ${r.surgeon}`}
                </CardDescription>
              </div>
              <Badge variant="outline" className="text-xs">Post-Op Care</Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {r.postOpInstructions && (
              <div>
                <h4 className="text-sm font-semibold mb-2 flex items-center gap-1.5">
                  <CheckCircle className="h-4 w-4 text-emerald-500" /> Care Instructions
                </h4>
                <div className="rounded-lg bg-muted/50 p-3 text-sm whitespace-pre-wrap leading-relaxed">
                  {r.postOpInstructions}
                </div>
              </div>
            )}
            {r.followUpPlan && (
              <div>
                <h4 className="text-sm font-semibold mb-2 flex items-center gap-1.5">
                  <Calendar className="h-4 w-4 text-blue-500" /> Follow-Up Plan
                </h4>
                <div className="rounded-lg bg-blue-50/50 dark:bg-blue-950/20 border border-blue-200/40 dark:border-blue-800/30 p-3 text-sm whitespace-pre-wrap leading-relaxed">
                  {r.followUpPlan}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

// ─── Billing Tab ──────────────────────────────────────────────────────────
function BillingTab({ plans }: { plans: TreatmentPlan[] }) {
  const { toast } = useToast();
  const totalResponsibility = plans.reduce((acc, p) => acc + parseFloat(p.patientResponsibility || "0"), 0);

  return (
    <div className="space-y-4">
      <Card className={totalResponsibility > 0 ? "border-amber-400/30 bg-amber-50/30 dark:bg-amber-950/20" : "border-emerald-400/30 bg-emerald-50/30 dark:bg-emerald-950/20"}>
        <CardContent className="pt-5 pb-5">
          <div className="flex items-center justify-between gap-4">
            <div>
              <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Estimated Patient Balance</div>
              <div className={`text-3xl font-bold font-mono ${totalResponsibility > 0 ? "text-amber-600 dark:text-amber-400" : "text-emerald-600 dark:text-emerald-400"}`}>
                ${totalResponsibility.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </div>
              <div className="text-xs text-muted-foreground mt-1">Across {plans.length} treatment plan{plans.length !== 1 ? "s" : ""}</div>
            </div>
            {totalResponsibility > 0 && (
              <Button
                className="gap-2 shrink-0"
                onClick={() => toast({ title: "Payment portal coming soon", description: "Online payments will be available in an upcoming update." })}
                data-testid="button-pay-now"
              >
                <CreditCard className="h-4 w-4" /> Pay Now
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {plans.map(p => (
        <Card key={p.id} data-testid={`plan-billing-${p.id}`}>
          <CardContent className="pt-4 pb-4">
            <div className="flex items-start justify-between mb-3">
              <div className="font-semibold">{p.planName}</div>
              <Badge variant="outline" className="text-xs capitalize">{p.status}</Badge>
            </div>
            <div className="grid grid-cols-3 gap-3 text-sm">
              <div>
                <div className="text-xs text-muted-foreground mb-0.5">Total Cost</div>
                <div className="font-bold">{p.totalCost ? `$${parseFloat(p.totalCost).toLocaleString()}` : "—"}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground mb-0.5">Insurance Est.</div>
                <div className="font-bold text-emerald-600 dark:text-emerald-400">
                  {p.insuranceCoverage ? `$${parseFloat(p.insuranceCoverage).toLocaleString()}` : "—"}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground mb-0.5">Patient Est.</div>
                <div className={`font-bold ${p.patientResponsibility && parseFloat(p.patientResponsibility) > 0 ? "text-amber-600 dark:text-amber-400" : ""}`}>
                  {p.patientResponsibility ? `$${parseFloat(p.patientResponsibility).toLocaleString()}` : "—"}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      ))}

      {plans.length === 0 && (
        <p className="text-sm text-muted-foreground italic py-4 text-center">No treatment plans with billing information.</p>
      )}
    </div>
  );
}

// ─── Portal View ───────────────────────────────────────────────────────────
function PortalView({ patient, onAuditLog }: {
  patient: Patient;
  onAuditLog: (tab: string) => void;
}) {
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
            <div className="w-14 h-14 rounded-full bg-primary/20 flex items-center justify-center shrink-0">
              <span className="text-xl font-bold text-primary">
                {patient.firstName[0]}{patient.lastName[0]}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <h2 className="text-xl font-bold">{patient.firstName} {patient.lastName}</h2>
              <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1 text-sm text-muted-foreground">
                {patient.phone && <span className="flex items-center gap-1"><Phone className="h-3.5 w-3.5" />{patient.phone}</span>}
                {patient.email && <span className="flex items-center gap-1"><Mail className="h-3.5 w-3.5" />{patient.email}</span>}
                {(patient.city || patient.state) && (
                  <span className="flex items-center gap-1">
                    <MapPin className="h-3.5 w-3.5" />{[patient.city, patient.state].filter(Boolean).join(", ")}
                  </span>
                )}
              </div>
            </div>
            <Badge variant="outline" className="text-xs border-primary/30 text-primary gap-1 shrink-0">
              <Shield className="h-3 w-3" /> HIPAA Protected
            </Badge>
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
      <Tabs defaultValue="appointments" onValueChange={tab => onAuditLog(tab)}>
        <TabsList className="flex-wrap h-auto gap-1">
          <TabsTrigger value="appointments">Appointments ({appts.length})</TabsTrigger>
          <TabsTrigger value="request">Request Appt.</TabsTrigger>
          <TabsTrigger value="billing">Billing</TabsTrigger>
          <TabsTrigger value="eob">EOB / Payments</TabsTrigger>
          <TabsTrigger value="post-op">Post-Op Care</TabsTrigger>
          <TabsTrigger value="messages">Messages</TabsTrigger>
          <TabsTrigger value="documents">Documents ({docs.length})</TabsTrigger>
          <TabsTrigger value="consent">Consent Forms ({consent.length})</TabsTrigger>
          <TabsTrigger value="my-info">My Info</TabsTrigger>
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

        <TabsContent value="request" className="mt-3">
          <AppointmentRequestTab patient={patient} />
        </TabsContent>

        <TabsContent value="billing" className="mt-3">
          <BillingTab plans={plans} />
        </TabsContent>

        <TabsContent value="eob" className="mt-3">
          <EobTab patient={patient} onAuditLog={onAuditLog} />
        </TabsContent>

        <TabsContent value="post-op" className="mt-3">
          <PostOpTab patient={patient} />
        </TabsContent>

        <TabsContent value="messages" className="mt-3">
          <MessageTab patient={patient} />
        </TabsContent>

        {/* Documents — with download/open action */}
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
              <div className="flex items-center gap-1 shrink-0">
                <button
                  className="text-muted-foreground hover:text-primary p-1 rounded"
                  title="View document"
                  onClick={() => window.open(d.fileUrl, "_blank", "noopener,noreferrer")}
                  data-testid={`btn-view-doc-${d.id}`}
                >
                  <Eye className="h-4 w-4" />
                </button>
                <a
                  href={d.fileUrl}
                  download={d.fileName}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-muted-foreground hover:text-primary p-1 rounded"
                  title="Download document"
                  data-testid={`btn-download-doc-${d.id}`}
                >
                  <Download className="h-4 w-4" />
                </a>
              </div>
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

        {/* My Info */}
        <TabsContent value="my-info" className="mt-3">
          <MyInfoTab patient={patient} onAuditLog={onAuditLog} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

interface PortalAccess {
  id: number; patientId: number; enabled: boolean;
  lastAccessedAt: string | null; linkSentAt: string | null;
}

// ─── Main Page ─────────────────────────────────────────────────────────────
export default function PatientPortalPage() {
  const [selectedPatient, setSelectedPatient] = useState<Patient | null>(null);

  const { data: patients = [], isLoading } = useQuery<Patient[]>({ queryKey: ["/api/patients"] });

  // Always fetch portal access status for the selected patient
  const { data: portalAccess } = useQuery<PortalAccess | null>({
    queryKey: ["/api/patients", selectedPatient?.id, "portal-access"],
    queryFn: () =>
      selectedPatient
        ? fetch(`/api/patients/${selectedPatient.id}/portal-access`, { credentials: "include" })
            .then(r => r.ok ? r.json() : null)
        : Promise.resolve(null),
    enabled: !!selectedPatient,
  });

  const logAccessMutation = useMutation({
    mutationFn: ({ patientId, tab }: { patientId: number; tab: string }) =>
      apiRequest("POST", `/api/patients/${patientId}/portal-access-log`, { tab }),
  });

  function handleSelectPatient(p: Patient) {
    setSelectedPatient(p);
    // Access log fires only after portal-access check confirms enabled
  }

  function handleAuditLog(tab: string) {
    if (!selectedPatient || !portalAccess?.enabled) return;
    logAccessMutation.mutate({ patientId: selectedPatient.id, tab });
  }

  const portalEnabled = portalAccess?.enabled === true;
  const portalChecked = selectedPatient && portalAccess !== undefined;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">Patient Portal</h1>
        <p className="text-sm text-muted-foreground">
          Full patient view — appointments, EOBs, post-op care, messaging, document download, and contact management
        </p>
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
              <PatientSelector patients={patients} selected={selectedPatient} onSelect={handleSelectPatient} />
            )}
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          <Button variant="outline" size="sm" onClick={() => setSelectedPatient(null)} data-testid="button-back">
            ← All Patients
          </Button>
          {!portalChecked ? (
            <p className="text-sm text-muted-foreground py-4">Checking portal access…</p>
          ) : !portalEnabled ? (
            <Card className="border-amber-400/30 bg-amber-50/30 dark:bg-amber-950/20" data-testid="portal-disabled-notice">
              <CardContent className="pt-6 pb-6 text-center">
                <Shield className="mx-auto h-10 w-10 text-amber-500 mb-3" />
                <h3 className="font-semibold text-lg mb-1">Portal Access Disabled</h3>
                <p className="text-sm text-muted-foreground max-w-sm mx-auto">
                  The patient portal is not currently enabled for{" "}
                  <strong>{selectedPatient.firstName} {selectedPatient.lastName}</strong>.
                  Enable access from the patient record and send an invitation link first.
                </p>
              </CardContent>
            </Card>
          ) : (
            <PortalView patient={selectedPatient} onAuditLog={handleAuditLog} />
          )}
        </div>
      )}
    </div>
  );
}
