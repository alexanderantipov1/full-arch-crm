import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Stethoscope, Smile, UserPlus, AlertTriangle, Activity, RefreshCcw,
  ClipboardCheck, MessageSquare, Clock, CheckCircle2, CalendarDays,
  ChevronLeft, Loader2, Phone, Mail, MapPin,
} from "lucide-react";

// ─── Types ───────────────────────────────────────────────────────────────
type AppointmentType =
  | "full_arch_consult" | "implant_consult" | "implant_placement"
  | "new_patient_exam" | "recall_hygiene" | "emergency"
  | "post_op" | "treatment_consult";

interface TimeSlot {
  date: string;
  time: string;
  providerId: string;
  providerName: string;
  durationMinutes: number;
  available: boolean;
}

interface BookingResult {
  confirmationNumber: string;
  firstName: string;
  lastName: string;
  appointmentType: AppointmentType;
  preferredDate: string;
  preferredTime: string;
  providerId?: string;
}

const APPT_TYPES: {
  value: AppointmentType; title: string; description: string; duration: number; icon: any;
}[] = [
  { value: "full_arch_consult", title: "Full Arch Consultation", description: "Free consultation for All-on-4 / All-on-6 implant solutions", duration: 90, icon: Smile },
  { value: "implant_consult", title: "Implant Consultation", description: "Evaluate a single tooth implant or replacement options", duration: 60, icon: Stethoscope },
  { value: "new_patient_exam", title: "New Patient Exam", description: "Comprehensive exam, x-rays and treatment overview", duration: 60, icon: UserPlus },
  { value: "treatment_consult", title: "Treatment Consultation", description: "Discuss a recommended treatment plan and next steps", duration: 45, icon: ClipboardCheck },
  { value: "recall_hygiene", title: "Hygiene / Cleaning", description: "Routine cleaning and recall visit", duration: 60, icon: RefreshCcw },
  { value: "emergency", title: "Emergency / Pain", description: "Same-day care for pain, swelling or a dental emergency", duration: 30, icon: AlertTriangle },
  { value: "post_op", title: "Post-Op Follow-Up", description: "Follow-up visit after a surgical procedure", duration: 30, icon: Activity },
];

const INSURANCE_CARRIERS = [
  "Delta Dental", "Cigna", "MetLife", "Aetna", "Guardian", "United Healthcare",
  "Humana", "Blue Cross Blue Shield", "Medicare", "Self-Pay / No Insurance", "Other",
];

const SOURCES: { value: string; label: string }[] = [
  { value: "website", label: "Practice Website" },
  { value: "google", label: "Google Search" },
  { value: "facebook", label: "Facebook / Instagram" },
  { value: "referral", label: "Friend / Family Referral" },
  { value: "direct", label: "Other" },
];

function fmtDate(d: Date) { return d.toISOString().split("T")[0]; }
function prettyDate(s: string) {
  return new Date(s + "T00:00:00").toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
}
function prettyTime(t: string) {
  const [h, m] = t.split(":").map(Number);
  const period = h >= 12 ? "PM" : "AM";
  const hr = h % 12 === 0 ? 12 : h % 12;
  return `${hr}:${m.toString().padStart(2, "0")} ${period}`;
}

export default function PatientBookingPage() {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [apptType, setApptType] = useState<AppointmentType | null>(null);
  const [providerId, setProviderId] = useState<string>("");
  const [selectedSlot, setSelectedSlot] = useState<TimeSlot | null>(null);
  const [form, setForm] = useState({
    firstName: "", lastName: "", email: "", phone: "",
    dateOfBirth: "", insuranceCarrier: "", source: "website", notes: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<BookingResult | null>(null);

  const today = new Date();
  const endDate = new Date(); endDate.setDate(endDate.getDate() + 14);

  const { data: slots = [], isLoading: slotsLoading } = useQuery<TimeSlot[]>({
    queryKey: [`/api/booking/slots?appointmentType=${apptType}&startDate=${fmtDate(today)}&endDate=${fmtDate(endDate)}${providerId ? `&providerId=${providerId}` : ""}`],
    enabled: step === 2 && !!apptType,
  });

  // Group slots by date
  const slotsByDate = slots.reduce<Record<string, TimeSlot[]>>((acc, s) => {
    (acc[s.date] ||= []).push(s);
    return acc;
  }, {});
  const sortedDates = Object.keys(slotsByDate).sort();

  const selectedTypeInfo = APPT_TYPES.find(t => t.value === apptType);

  async function submitBooking() {
    if (!apptType || !selectedSlot) return;
    if (!form.firstName || !form.lastName || !form.email || !form.phone) {
      setError("Please fill in your name, email and phone.");
      return;
    }
    setSubmitting(true); setError("");
    try {
      const res = await fetch("/api/booking/request", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...form,
          dateOfBirth: form.dateOfBirth || undefined,
          insuranceCarrier: form.insuranceCarrier || undefined,
          appointmentType: apptType,
          preferredDate: selectedSlot.date,
          preferredTime: selectedSlot.time,
          providerId: selectedSlot.providerId,
        }),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      const data = await res.json();
      setResult(data);
    } catch {
      setError("Something went wrong submitting your request. Please call our office.");
    } finally {
      setSubmitting(false);
    }
  }

  function buildCalendarLink(r: BookingResult) {
    const start = new Date(`${r.preferredDate}T${r.preferredTime}:00`);
    const end = new Date(start.getTime() + (selectedTypeInfo?.duration ?? 60) * 60000);
    const fmt = (d: Date) => d.toISOString().replace(/[-:]/g, "").split(".")[0] + "Z";
    const title = encodeURIComponent(`Fusion Dental — ${selectedTypeInfo?.title ?? "Appointment"}`);
    const details = encodeURIComponent(`Confirmation #${r.confirmationNumber}`);
    return `https://calendar.google.com/calendar/render?action=TEMPLATE&text=${title}&dates=${fmt(start)}/${fmt(end)}&details=${details}`;
  }

  // ─── Confirmation screen ──────────────────────────────────────────────
  if (result) {
    return (
      <div className="min-h-screen bg-slate-50">
        <Header />
        <div className="mx-auto max-w-xl px-4 py-10">
          <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
            <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100">
              <CheckCircle2 className="h-9 w-9 text-emerald-600" />
            </div>
            <h2 className="text-2xl font-semibold text-slate-900">Appointment Requested!</h2>
            <p className="mt-2 text-slate-600">
              Thank you, {result.firstName}. Our team will call you shortly to confirm your visit.
            </p>
            <div className="mt-6 rounded-xl bg-slate-50 p-5 text-left">
              <div className="flex items-center justify-between border-b border-slate-200 pb-3">
                <span className="text-sm text-slate-500">Confirmation #</span>
                <span className="font-mono text-sm font-semibold text-blue-700" data-testid="text-confirmation-number">{result.confirmationNumber}</span>
              </div>
              <dl className="mt-3 space-y-2 text-sm">
                <div className="flex justify-between"><dt className="text-slate-500">Type</dt><dd className="font-medium text-slate-900">{selectedTypeInfo?.title}</dd></div>
                <div className="flex justify-between"><dt className="text-slate-500">Date</dt><dd className="font-medium text-slate-900">{prettyDate(result.preferredDate)}</dd></div>
                <div className="flex justify-between"><dt className="text-slate-500">Time</dt><dd className="font-medium text-slate-900">{prettyTime(result.preferredTime)}</dd></div>
                {selectedSlot && <div className="flex justify-between"><dt className="text-slate-500">Provider</dt><dd className="font-medium text-slate-900">{selectedSlot.providerName}</dd></div>}
              </dl>
            </div>
            <a
              href={buildCalendarLink(result)} target="_blank" rel="noopener noreferrer"
              className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-3 font-medium text-white transition hover:bg-blue-700"
              data-testid="link-add-to-calendar"
            >
              <CalendarDays className="h-4 w-4" /> Add to Calendar
            </a>
            <p className="mt-4 text-xs text-slate-400">A confirmation has also been sent to {result.firstName}'s phone.</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <Header />
      <div className="mx-auto max-w-3xl px-4 py-8">
        <Stepper step={step} />

        {/* ─── Step 1: Appointment Type ─────────────────────────────── */}
        {step === 1 && (
          <div data-testid="step-appointment-type">
            <h2 className="mb-1 text-xl font-semibold text-slate-900">What can we help you with?</h2>
            <p className="mb-5 text-sm text-slate-500">Select the type of visit you'd like to book.</p>
            <div className="grid gap-3 sm:grid-cols-2">
              {APPT_TYPES.map(t => {
                const Icon = t.icon;
                const active = apptType === t.value;
                return (
                  <button
                    key={t.value}
                    onClick={() => { setApptType(t.value); setSelectedSlot(null); }}
                    className={`flex items-start gap-3 rounded-xl border p-4 text-left transition ${active ? "border-blue-600 bg-blue-50 ring-1 ring-blue-600" : "border-slate-200 bg-white hover:border-blue-300 hover:shadow-sm"}`}
                    data-testid={`card-appttype-${t.value}`}
                  >
                    <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${active ? "bg-blue-600 text-white" : "bg-blue-100 text-blue-700"}`}>
                      <Icon className="h-5 w-5" />
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-slate-900">{t.title}</span>
                      </div>
                      <p className="mt-0.5 text-xs text-slate-500">{t.description}</p>
                      <span className="mt-2 inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">
                        <Clock className="h-3 w-3" /> {t.duration} min
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
            <div className="mt-6 flex justify-end">
              <button
                disabled={!apptType}
                onClick={() => setStep(2)}
                className="rounded-lg bg-blue-600 px-6 py-2.5 font-medium text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                data-testid="button-next-step1"
              >Continue</button>
            </div>
          </div>
        )}

        {/* ─── Step 2: Date & Time ──────────────────────────────────── */}
        {step === 2 && (
          <div data-testid="step-date-time">
            <h2 className="mb-1 text-xl font-semibold text-slate-900">Choose a date & time</h2>
            <p className="mb-4 text-sm text-slate-500">Available appointments over the next 2 weeks.</p>

            <div className="mb-5">
              <label className="mb-1 block text-sm font-medium text-slate-700">Provider</label>
              <select
                value={providerId}
                onChange={e => { setProviderId(e.target.value); setSelectedSlot(null); }}
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 sm:w-72"
                data-testid="select-provider"
              >
                <option value="">No preference</option>
                <option value="prov-1">Dr. Antipov</option>
                <option value="prov-2">Dr. Johnson</option>
              </select>
            </div>

            {slotsLoading ? (
              <div className="flex items-center justify-center py-16 text-slate-400"><Loader2 className="mr-2 h-5 w-5 animate-spin" /> Loading availability…</div>
            ) : sortedDates.length === 0 ? (
              <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
                No openings found for this selection. Try a different provider or call our office.
              </div>
            ) : (
              <div className="space-y-5">
                {sortedDates.map(date => {
                  const daySlots = slotsByDate[date].sort((a, b) => a.time.localeCompare(b.time));
                  const morning = daySlots.filter(s => parseInt(s.time) < 12);
                  const afternoon = daySlots.filter(s => parseInt(s.time) >= 12);
                  return (
                    <div key={date} className="rounded-xl border border-slate-200 bg-white p-4">
                      <div className="mb-3 flex items-center gap-2 font-medium text-slate-800">
                        <CalendarDays className="h-4 w-4 text-blue-600" /> {prettyDate(date)}
                      </div>
                      {[{ label: "Morning", list: morning }, { label: "Afternoon", list: afternoon }].map(grp => grp.list.length > 0 && (
                        <div key={grp.label} className="mb-3 last:mb-0">
                          <div className="mb-1.5 text-xs font-medium uppercase tracking-wide text-slate-400">{grp.label}</div>
                          <div className="flex flex-wrap gap-2">
                            {grp.list.map(s => {
                              const sel = selectedSlot?.date === s.date && selectedSlot?.time === s.time && selectedSlot?.providerId === s.providerId;
                              return (
                                <button
                                  key={`${s.time}-${s.providerId}`}
                                  onClick={() => setSelectedSlot(s)}
                                  className={`rounded-lg border px-3 py-1.5 text-sm transition ${sel ? "border-blue-600 bg-blue-600 text-white" : "border-slate-200 bg-white text-slate-700 hover:border-blue-400"}`}
                                  data-testid={`slot-${s.date}-${s.time}-${s.providerId}`}
                                >
                                  {prettyTime(s.time)}
                                  {!providerId && <span className="ml-1 text-[10px] opacity-70">{s.providerName.replace("Dr. ", "")}</span>}
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      ))}
                    </div>
                  );
                })}
              </div>
            )}

            <div className="mt-6 flex items-center justify-between">
              <button onClick={() => setStep(1)} className="inline-flex items-center gap-1 text-sm font-medium text-slate-600 hover:text-slate-900" data-testid="button-back-step2">
                <ChevronLeft className="h-4 w-4" /> Back
              </button>
              <button
                disabled={!selectedSlot}
                onClick={() => setStep(3)}
                className="rounded-lg bg-blue-600 px-6 py-2.5 font-medium text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                data-testid="button-next-step2"
              >Continue</button>
            </div>
          </div>
        )}

        {/* ─── Step 3: Your Information ─────────────────────────────── */}
        {step === 3 && (
          <div data-testid="step-your-info">
            <h2 className="mb-1 text-xl font-semibold text-slate-900">Your information</h2>
            <p className="mb-4 text-sm text-slate-500">
              {selectedTypeInfo?.title} · {selectedSlot && `${prettyDate(selectedSlot.date)} at ${prettyTime(selectedSlot.time)} with ${selectedSlot.providerName}`}
            </p>

            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="First name *"><input value={form.firstName} onChange={e => setForm(f => ({ ...f, firstName: e.target.value }))} className={inputCls} data-testid="input-firstName" /></Field>
                <Field label="Last name *"><input value={form.lastName} onChange={e => setForm(f => ({ ...f, lastName: e.target.value }))} className={inputCls} data-testid="input-lastName" /></Field>
                <Field label="Email *"><input type="email" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} className={inputCls} data-testid="input-email" /></Field>
                <Field label="Phone *"><input type="tel" value={form.phone} onChange={e => setForm(f => ({ ...f, phone: e.target.value }))} className={inputCls} data-testid="input-phone" /></Field>
                <Field label="Date of birth"><input type="date" value={form.dateOfBirth} onChange={e => setForm(f => ({ ...f, dateOfBirth: e.target.value }))} className={inputCls} data-testid="input-dob" /></Field>
                <Field label="Insurance carrier">
                  <select value={form.insuranceCarrier} onChange={e => setForm(f => ({ ...f, insuranceCarrier: e.target.value }))} className={inputCls} data-testid="select-insurance">
                    <option value="">Select…</option>
                    {INSURANCE_CARRIERS.map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                </Field>
                <Field label="How did you hear about us?">
                  <select value={form.source} onChange={e => setForm(f => ({ ...f, source: e.target.value }))} className={inputCls} data-testid="select-source">
                    {SOURCES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
                  </select>
                </Field>
                <Field label="Notes" full>
                  <textarea rows={3} value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} className={inputCls} placeholder="Anything we should know before your visit?" data-testid="input-notes" />
                </Field>
              </div>

              {error && <p className="mt-3 text-sm text-red-600" data-testid="text-error">{error}</p>}
            </div>

            <div className="mt-6 flex items-center justify-between">
              <button onClick={() => setStep(2)} className="inline-flex items-center gap-1 text-sm font-medium text-slate-600 hover:text-slate-900" data-testid="button-back-step3">
                <ChevronLeft className="h-4 w-4" /> Back
              </button>
              <button
                disabled={submitting}
                onClick={submitBooking}
                className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-6 py-2.5 font-medium text-white transition hover:bg-blue-700 disabled:opacity-60"
                data-testid="button-submit-booking"
              >
                {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
                Request Appointment
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

const inputCls = "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500";

function Field({ label, children, full }: { label: string; children: React.ReactNode; full?: boolean }) {
  return (
    <div className={full ? "sm:col-span-2" : ""}>
      <label className="mb-1 block text-sm font-medium text-slate-700">{label}</label>
      {children}
    </div>
  );
}

function Header() {
  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-3xl flex-col gap-2 px-4 py-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-blue-600 text-white">
            <Stethoscope className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-slate-900">Fusion Dental Implant Center</h1>
            <p className="text-xs text-slate-500">Schedule your visit online</p>
          </div>
        </div>
        <div className="flex flex-col gap-1 text-xs text-slate-500 sm:items-end">
          <span className="inline-flex items-center gap-1"><Phone className="h-3 w-3" /> (555) 012-3456</span>
          <span className="inline-flex items-center gap-1"><MapPin className="h-3 w-3" /> 123 Smile Ave, Suite 100</span>
        </div>
      </div>
    </header>
  );
}

function Stepper({ step }: { step: number }) {
  const steps = ["Appointment", "Date & Time", "Your Info"];
  return (
    <div className="mb-8 flex items-center justify-center gap-2">
      {steps.map((label, i) => {
        const n = i + 1;
        const active = step === n;
        const done = step > n;
        return (
          <div key={label} className="flex items-center gap-2">
            <div className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold ${done ? "bg-emerald-500 text-white" : active ? "bg-blue-600 text-white" : "bg-slate-200 text-slate-500"}`}>
              {done ? <CheckCircle2 className="h-4 w-4" /> : n}
            </div>
            <span className={`hidden text-sm sm:inline ${active ? "font-medium text-slate-900" : "text-slate-400"}`}>{label}</span>
            {n < steps.length && <div className="h-px w-6 bg-slate-200 sm:w-10" />}
          </div>
        );
      })}
    </div>
  );
}
