import { useState } from "react";
import {
  BarChart3, Users, Calendar, Activity, DollarSign, Clock, Phone, Mail,
  MessageSquare, AlertCircle, CheckCircle, Search, ChevronRight, Star,
  FileText, Bot, TrendingUp, AlertTriangle, ArrowRight,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table, TableHeader, TableRow, TableHead, TableBody, TableCell,
} from "@/components/ui/table";
import { ScrollArea } from "@/components/ui/scroll-area";

type ToothCondition = "crown" | "filling" | "implant" | "decay" | "missing" | "root_canal" | "bridge";

interface Treatment {
  date: string;
  cdt: string;
  desc: string;
  fee: number;
  ins: number;
  pat: number;
  status: string;
  provider: string;
}

interface LedgerEntry {
  date: string;
  desc: string;
  charge: number;
  payment: number;
  adj: number;
  ins: number;
  bal: number;
}

interface Communication {
  date: string;
  type: string;
  dir: string;
  msg: string;
  status: string;
  duration?: string;
}

interface TxPlanItem {
  tooth: number | null;
  cdt: string;
  desc: string;
  fee: number;
  ins_est: number;
}

interface TxPlan {
  id: string;
  name: string;
  status: string;
  presented: string;
  items: TxPlanItem[];
}

interface Patient {
  id: number;
  fn: string;
  ln: string;
  dob: string;
  gender: string;
  phone: string;
  email: string;
  insurance: { primary: string; memberId: string; group: string; employer: string; copay: number; deductible: number; used: number; annual_max: number };
  provider: string;
  status: string;
  lastVisit: string;
  nextAppt: string;
  balance: number;
  alert: string;
  medHx: string[];
  chart: Record<number, ToothCondition>;
  treatments: Treatment[];
  ledger: LedgerEntry[];
  comms: Communication[];
  txPlans: TxPlan[];
}

interface ScheduleEntry {
  time: string;
  duration: number;
  patient: string;
  procedure: string;
  provider: string;
  type: string;
  status: string;
}

interface AIInsight {
  type: string;
  icon: typeof DollarSign;
  title: string;
  desc: string;
  priority: "high" | "medium" | "low";
  action: string;
}

const PATIENTS: Patient[] = [
  { id: 1, fn: "Margaret", ln: "Sullivan", dob: "1965-03-14", gender: "F", phone: "(555) 234-8901", email: "msullivan@email.com", insurance: { primary: "Delta Dental PPO", memberId: "DDN-849201", group: "GRP-7742", employer: "State Farm Insurance", copay: 25, deductible: 1500, used: 420, annual_max: 2000 }, provider: "Dr. Chen", status: "active", lastVisit: "2026-01-28", nextAppt: "2026-02-18", balance: 1250.00, alert: "Penicillin allergy", medHx: ["Hypertension", "Penicillin allergy", "Bisphosphonate use"], chart: { 3: "crown", 14: "implant", 19: "filling", 30: "missing" }, treatments: [
    { date: "2026-01-28", cdt: "D6010", desc: "Implant body - #14", fee: 2200, ins: 1100, pat: 1100, status: "completed", provider: "Dr. Chen" },
    { date: "2026-01-28", cdt: "D0367", desc: "CBCT - limited FOV", fee: 250, ins: 175, pat: 75, status: "completed", provider: "Dr. Chen" },
    { date: "2025-11-15", cdt: "D2740", desc: "Crown porcelain - #3", fee: 1450, ins: 870, pat: 580, status: "completed", provider: "Dr. Chen" },
    { date: "2025-09-20", cdt: "D1110", desc: "Prophylaxis - adult", fee: 175, ins: 175, pat: 0, status: "completed", provider: "Sarah M." },
  ], ledger: [
    { date: "2026-01-28", desc: "Implant body #14 + CBCT", charge: 2450, payment: 0, adj: 0, ins: 1275, bal: 1175 },
    { date: "2026-01-30", desc: "Insurance payment - Delta", charge: 0, payment: 1275, adj: 0, ins: 0, bal: -100 },
    { date: "2025-11-15", desc: "Crown #3", charge: 1450, payment: 580, adj: 0, ins: 870, bal: 0 },
  ], comms: [
    { date: "2026-02-10", type: "sms", dir: "out", msg: "Hi Margaret! Reminder: your appointment is Feb 18 at 9:00 AM with Dr. Chen. Reply C to confirm.", status: "delivered" },
    { date: "2026-02-10", type: "sms", dir: "in", msg: "C", status: "received" },
    { date: "2026-01-29", type: "call", dir: "out", msg: "Post-op follow-up call. Patient reports mild soreness, no complications.", status: "completed", duration: "3:42" },
    { date: "2026-01-28", type: "email", dir: "out", msg: "Post-procedure care instructions sent for implant #14", status: "delivered" },
    { date: "2026-01-20", type: "sms", dir: "out", msg: "Balance reminder: $1,250.00 due.", status: "delivered" },
  ], txPlans: [
    { id: "TP-001", name: "Implant Restoration Phase 2", status: "pending", presented: "2026-01-28", items: [
      { tooth: 14, cdt: "D6058", desc: "Abutment - implant supported", fee: 950, ins_est: 475 },
      { tooth: 14, cdt: "D6065", desc: "Crown - implant supported porcelain", fee: 1650, ins_est: 825 },
    ]},
    { id: "TP-002", name: "Perio Maintenance", status: "accepted", presented: "2025-09-20", items: [
      { tooth: null, cdt: "D4910", desc: "Periodontal maintenance", fee: 195, ins_est: 175 },
    ]},
  ]},
  { id: 2, fn: "Robert", ln: "Kim", dob: "1978-07-22", gender: "M", phone: "(555) 345-6789", email: "rkim@email.com", insurance: { primary: "MetLife DPPO", memberId: "MLF-332847", group: "GRP-5501", employer: "Wells Fargo", copay: 30, deductible: 1000, used: 280, annual_max: 1500 }, provider: "Dr. Chen", status: "active", lastVisit: "2026-02-05", nextAppt: "2026-02-22", balance: 0, alert: "", medHx: ["None reported"], chart: { 14: "decay", 19: "filling", 31: "filling" }, treatments: [
    { date: "2026-02-05", cdt: "D0150", desc: "Comprehensive oral evaluation", fee: 125, ins: 100, pat: 25, status: "completed", provider: "Dr. Chen" },
    { date: "2026-02-05", cdt: "D0210", desc: "Full mouth X-rays", fee: 195, ins: 156, pat: 39, status: "completed", provider: "Dr. Chen" },
  ], ledger: [
    { date: "2026-02-05", desc: "New patient exam + FMX", charge: 320, payment: 64, adj: 0, ins: 256, bal: 0 },
  ], comms: [
    { date: "2026-02-09", type: "sms", dir: "out", msg: "Hi Robert! Your treatment plan is ready.", status: "delivered" },
  ], txPlans: [
    { id: "TP-003", name: "Single Implant #14", status: "presented", presented: "2026-02-05", items: [
      { tooth: 14, cdt: "D6010", desc: "Implant body - endosteal", fee: 2200, ins_est: 880 },
      { tooth: 14, cdt: "D6058", desc: "Abutment - implant supported", fee: 950, ins_est: 380 },
      { tooth: 14, cdt: "D6065", desc: "Crown - implant supported", fee: 1650, ins_est: 660 },
    ]},
  ]},
  { id: 3, fn: "Diana", ln: "Patel", dob: "1992-11-03", gender: "F", phone: "(555) 456-7890", email: "dpatel@email.com", insurance: { primary: "Cigna DHMO", memberId: "CIG-119374", group: "GRP-8823", employer: "Google", copay: 20, deductible: 0, used: 0, annual_max: 2500 }, provider: "Dr. Park", status: "active", lastVisit: "2026-01-15", nextAppt: "2026-02-20", balance: 350.00, alert: "Latex allergy", medHx: ["Latex allergy", "Asthma"], chart: {}, treatments: [
    { date: "2026-01-15", cdt: "D0150", desc: "Comprehensive oral evaluation", fee: 125, ins: 100, pat: 25, status: "completed", provider: "Dr. Park" },
    { date: "2026-01-15", cdt: "D8090", desc: "Comprehensive orthodontic - adult", fee: 5800, ins: 2500, pat: 3300, status: "in_progress", provider: "Dr. Park" },
  ], ledger: [
    { date: "2026-01-15", desc: "Ortho consult + Invisalign start", charge: 5925, payment: 2950, adj: 0, ins: 2625, bal: 350 },
  ], comms: [], txPlans: [] },
  { id: 4, fn: "James", ln: "Okafor", dob: "1985-05-30", gender: "M", phone: "(555) 567-8901", email: "jokafor@email.com", insurance: { primary: "Aetna PPO", memberId: "AET-556201", group: "GRP-3317", employer: "Kaiser Permanente", copay: 25, deductible: 1500, used: 1200, annual_max: 2000 }, provider: "Dr. Park", status: "active", lastVisit: "2026-02-03", nextAppt: "2026-03-05", balance: 0, alert: "", medHx: ["Type 2 Diabetes"], chart: { 2: "filling", 15: "filling", 18: "crown", 31: "root_canal" }, treatments: [
    { date: "2026-02-03", cdt: "D4341", desc: "Scaling & root planing", fee: 285, ins: 228, pat: 57, status: "completed", provider: "Dr. Park" },
  ], ledger: [], comms: [], txPlans: [] },
  { id: 5, fn: "Sarah", ln: "Chen", dob: "2000-09-17", gender: "F", phone: "(555) 678-9012", email: "schen@email.com", insurance: { primary: "United Healthcare", memberId: "UHC-884502", group: "GRP-2209", employer: "Self", copay: 35, deductible: 2000, used: 0, annual_max: 1500 }, provider: "Unassigned", status: "lead", lastVisit: "-", nextAppt: "Pending", balance: 0, alert: "", medHx: [], chart: {}, treatments: [], ledger: [], comms: [
    { date: "2026-02-11", type: "webform", dir: "in", msg: "New patient inquiry via website: interested in dental implants.", status: "new_lead" },
  ], txPlans: [] },
  { id: 6, fn: "Michael", ln: "Torres", dob: "1970-01-08", gender: "M", phone: "(555) 789-0123", email: "mtorres@email.com", insurance: { primary: "Guardian DentalGuard", memberId: "GDN-770318", group: "GRP-1145", employer: "Retired - COBRA", copay: 20, deductible: 1000, used: 950, annual_max: 1500 }, provider: "Dr. Okafor", status: "active", lastVisit: "2026-01-10", nextAppt: "2026-07-15", balance: 475.00, alert: "Blood thinner - Warfarin", medHx: ["Warfarin use", "Heart murmur", "Hip replacement 2023"], chart: { 1: "missing", 16: "missing", 17: "bridge", 32: "missing" }, treatments: [
    { date: "2026-01-10", cdt: "D7210", desc: "Extraction - surgical (#17 remnant)", fee: 385, ins: 308, pat: 77, status: "completed", provider: "Dr. Okafor" },
    { date: "2026-01-10", cdt: "D7953", desc: "Bone graft - socket preservation", fee: 650, ins: 325, pat: 325, status: "completed", provider: "Dr. Okafor" },
  ], ledger: [
    { date: "2026-01-10", desc: "Surgical extraction + bone graft", charge: 1035, payment: 560, adj: 0, ins: 0, bal: 475 },
  ], comms: [
    { date: "2026-02-08", type: "sms", dir: "out", msg: "Hi Michael, you have a balance of $475.00.", status: "delivered" },
    { date: "2026-02-08", type: "sms", dir: "in", msg: "PLAN", status: "received" },
    { date: "2026-02-08", type: "sms", dir: "out", msg: "Great! We've set you up on 3 payments of $158.33/mo.", status: "delivered" },
  ], txPlans: [] },
];

const SCHEDULE: ScheduleEntry[] = [
  { time: "08:00", duration: 60, patient: "Margaret Sullivan", procedure: "Implant Follow-up", provider: "Dr. Chen", type: "implant", status: "confirmed" },
  { time: "09:00", duration: 90, patient: "Robert Kim", procedure: "Implant Consult + CBCT", provider: "Dr. Chen", type: "implant", status: "confirmed" },
  { time: "08:00", duration: 60, patient: "James Okafor", procedure: "Perio Maintenance", provider: "Dr. Park", type: "perio", status: "confirmed" },
  { time: "09:00", duration: 30, patient: "Diana Patel", procedure: "Invisalign Check", provider: "Dr. Park", type: "ortho", status: "unconfirmed" },
  { time: "10:00", duration: 60, patient: "New Patient Web Lead", procedure: "Comprehensive Exam", provider: "Dr. Chen", type: "exam", status: "unconfirmed" },
  { time: "10:30", duration: 90, patient: "Michael Torres", procedure: "Implant Surgery #17", provider: "Dr. Okafor", type: "implant", status: "confirmed" },
  { time: "11:00", duration: 60, patient: "Emily Watson", procedure: "Crown Prep #12", provider: "Dr. Park", type: "restorative", status: "confirmed" },
  { time: "13:00", duration: 60, patient: "Hygiene", procedure: "Prophy + Exam", provider: "Hygiene 1", type: "hygiene", status: "confirmed" },
  { time: "13:00", duration: 90, patient: "OPEN", procedure: "Available", provider: "Dr. Chen", type: "open", status: "open" },
  { time: "14:00", duration: 60, patient: "Hygiene", procedure: "SRP Quad 1", provider: "Hygiene 2", type: "perio", status: "confirmed" },
  { time: "14:00", duration: 60, patient: "Walk-In Emergency", procedure: "Emergency Exam", provider: "Dr. Okafor", type: "emergency", status: "pending" },
];

const AI_INSIGHTS: AIInsight[] = [
  { type: "revenue", icon: DollarSign, title: "Unscheduled treatment: $847K", desc: "234 patients have accepted but unscheduled treatment plans totaling $847,200. AI recommends automated 3-touch SMS sequence.", priority: "high", action: "Activate Sequence" },
  { type: "recall", icon: Calendar, title: "187 patients overdue for recall", desc: "These patients are 6+ months past their recall date. Reactivation campaign could recover $112K in hygiene production.", priority: "high", action: "Launch Campaign" },
  { type: "billing", icon: FileText, title: "A/R over 90 days: $23,400", desc: "14 accounts are 90+ days past due. AI recommends escalating to payment plan offers via SMS before collections.", priority: "medium", action: "Send SMS Offers" },
  { type: "insurance", icon: AlertCircle, title: "12 claims pending >30 days", desc: "Claims worth $18,600 have been pending with insurers for 30+ days. Auto-follow-up can recover 85% within 2 weeks.", priority: "medium", action: "Auto Follow-Up" },
  { type: "schedule", icon: Clock, title: "Tomorrow: 3 unconfirmed appointments", desc: "3 patients haven't confirmed for tomorrow. AI will send final confirmation SMS at 6 PM tonight + auto-fill from waitlist if no response.", priority: "low", action: "Auto-Confirm" },
  { type: "lead", icon: Star, title: "New web lead: Sarah Chen", desc: "Submitted form 2 hours ago. AI recommends immediate phone call (85% conversion within 5 minutes) followed by consult booking.", priority: "high", action: "Call Now" },
];

const UPPER_TEETH = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16];
const LOWER_TEETH = [32,31,30,29,28,27,26,25,24,23,22,21,20,19,18,17];

const TYPE_COLORS: Record<string, string> = {
  implant: "bg-blue-500",
  perio: "bg-teal-500",
  ortho: "bg-purple-500",
  restorative: "bg-orange-500",
  hygiene: "bg-green-500",
  exam: "bg-cyan-500",
  emergency: "bg-red-500",
  open: "bg-gray-400",
};

const TYPE_BADGE_VARIANTS: Record<string, string> = {
  implant: "bg-blue-500/15 text-blue-700 dark:text-blue-400",
  perio: "bg-teal-500/15 text-teal-700 dark:text-teal-400",
  ortho: "bg-purple-500/15 text-purple-700 dark:text-purple-400",
  restorative: "bg-orange-500/15 text-orange-700 dark:text-orange-400",
  hygiene: "bg-green-500/15 text-green-700 dark:text-green-400",
  exam: "bg-cyan-500/15 text-cyan-700 dark:text-cyan-400",
  emergency: "bg-red-500/15 text-red-700 dark:text-red-400",
  open: "bg-gray-500/15 text-gray-700 dark:text-gray-400",
};

const TOOTH_COLORS: Record<string, string> = {
  healthy: "bg-muted text-muted-foreground",
  crown: "bg-blue-500 text-white",
  filling: "bg-amber-500 text-white",
  implant: "bg-purple-500 text-white",
  decay: "bg-red-500 text-white",
  missing: "bg-gray-800 text-gray-300 dark:bg-gray-900 dark:text-gray-500",
  root_canal: "bg-orange-500 text-white",
  bridge: "bg-teal-500 text-white",
};

const PRIORITY_COLORS: Record<string, string> = {
  high: "destructive",
  medium: "secondary",
  low: "outline",
};

function getCommIcon(type: string) {
  if (type === "sms") return MessageSquare;
  if (type === "call") return Phone;
  if (type === "email") return Mail;
  return FileText;
}

export default function PracticeCRM() {
  const [mainTab, setMainTab] = useState("dashboard");
  const [selectedPatient, setSelectedPatient] = useState<Patient | null>(null);
  const [patSearch, setPatSearch] = useState("");
  const [patientSubTab, setPatientSubTab] = useState("overview");
  const [selectedTooth, setSelectedTooth] = useState<number | null>(null);

  const filteredPatients = PATIENTS.filter((p) => {
    const q = patSearch.toLowerCase();
    return !q || `${p.fn} ${p.ln}`.toLowerCase().includes(q) || p.phone.includes(q) || p.email.toLowerCase().includes(q);
  });

  return (
    <div className="space-y-4 p-4" data-testid="practice-crm">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground" data-testid="text-page-title">Practice CRM</h1>
          <p className="text-sm text-muted-foreground">Dental practice management dashboard</p>
        </div>
      </div>

      <Tabs value={mainTab} onValueChange={(v) => { setMainTab(v); if (v !== "patients" && v !== "charting") { setSelectedTooth(null); } }} data-testid="main-tabs">
        <TabsList data-testid="main-tabs-list">
          <TabsTrigger value="dashboard" data-testid="tab-dashboard"><BarChart3 className="h-3.5 w-3.5 mr-1.5" />Dashboard</TabsTrigger>
          <TabsTrigger value="patients" data-testid="tab-patients"><Users className="h-3.5 w-3.5 mr-1.5" />Patients</TabsTrigger>
          <TabsTrigger value="schedule" data-testid="tab-schedule"><Calendar className="h-3.5 w-3.5 mr-1.5" />Schedule</TabsTrigger>
          {selectedPatient && (
            <TabsTrigger value="charting" data-testid="tab-charting"><Activity className="h-3.5 w-3.5 mr-1.5" />Charting</TabsTrigger>
          )}
          <TabsTrigger value="ai" data-testid="tab-ai"><Bot className="h-3.5 w-3.5 mr-1.5" />AI Engine</TabsTrigger>
        </TabsList>

        {/* DASHBOARD TAB */}
        <TabsContent value="dashboard" className="space-y-4 mt-4" data-testid="dashboard-content">
          <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
            <Card data-testid="kpi-todays-production">
              <CardContent className="p-4">
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Today's Production</p>
                  <DollarSign className="h-4 w-4 text-muted-foreground" />
                </div>
                <p className="text-2xl font-bold text-foreground mt-1" data-testid="value-todays-production">$4,280</p>
              </CardContent>
            </Card>
            <Card data-testid="kpi-collections-rate">
              <CardContent className="p-4">
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Collections Rate</p>
                  <TrendingUp className="h-4 w-4 text-muted-foreground" />
                </div>
                <p className="text-2xl font-bold text-foreground mt-1" data-testid="value-collections-rate">98.2%</p>
              </CardContent>
            </Card>
            <Card data-testid="kpi-new-patients">
              <CardContent className="p-4">
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">New Patients</p>
                  <Users className="h-4 w-4 text-muted-foreground" />
                </div>
                <p className="text-2xl font-bold text-foreground mt-1" data-testid="value-new-patients">7 <span className="text-sm font-normal text-muted-foreground">this week</span></p>
              </CardContent>
            </Card>
            <Card data-testid="kpi-chair-utilization">
              <CardContent className="p-4">
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Chair Utilization</p>
                  <Activity className="h-4 w-4 text-muted-foreground" />
                </div>
                <p className="text-2xl font-bold text-foreground mt-1" data-testid="value-chair-utilization">87%</p>
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <Card className="lg:col-span-2" data-testid="todays-schedule-card">
              <CardHeader className="flex flex-row items-center justify-between gap-2 space-y-0 pb-2">
                <CardTitle className="text-sm font-semibold">Today's Schedule</CardTitle>
                <Calendar className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[420px]">
                  <div className="space-y-1">
                    {SCHEDULE.map((s, i) => (
                      <div key={i} className="flex items-center gap-3 py-2 border-b last:border-0" data-testid={`schedule-entry-${i}`}>
                        <div className="w-12 text-xs font-mono font-semibold text-foreground">{s.time}</div>
                        <div className={`w-2 h-2 rounded-full flex-shrink-0 ${TYPE_COLORS[s.type]}`} />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-foreground truncate">{s.patient}</p>
                          <p className="text-xs text-muted-foreground truncate">{s.procedure}</p>
                        </div>
                        <div className="text-xs text-muted-foreground hidden sm:block">{s.provider}</div>
                        <Badge variant="secondary" className={`text-[10px] no-default-hover-elevate no-default-active-elevate ${TYPE_BADGE_VARIANTS[s.type]}`} data-testid={`badge-type-${i}`}>{s.type}</Badge>
                        <Badge variant={s.status === "confirmed" ? "default" : s.status === "pending" ? "secondary" : "outline"} className="text-[10px]" data-testid={`badge-status-${i}`}>{s.status}</Badge>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>

            <Card data-testid="ai-insights-card">
              <CardHeader className="flex flex-row items-center justify-between gap-2 space-y-0 pb-2">
                <CardTitle className="text-sm font-semibold">AI Insights</CardTitle>
                <Bot className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[420px]">
                  <div className="space-y-3">
                    {AI_INSIGHTS.map((ins, i) => {
                      const Icon = ins.icon;
                      return (
                        <Card key={i} data-testid={`insight-card-${i}`}>
                          <CardContent className="p-3">
                            <div className="flex items-start gap-2">
                              <Icon className="h-4 w-4 mt-0.5 flex-shrink-0 text-muted-foreground" />
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 flex-wrap mb-1">
                                  <Badge variant={PRIORITY_COLORS[ins.priority] as any} className="text-[10px]" data-testid={`badge-priority-${i}`}>{ins.priority}</Badge>
                                  <span className="text-xs font-semibold text-foreground">{ins.title}</span>
                                </div>
                                <p className="text-xs text-muted-foreground leading-relaxed mb-2">{ins.desc}</p>
                                <Button size="sm" variant="outline" data-testid={`button-insight-action-${i}`}>
                                  {ins.action} <ArrowRight className="ml-1 h-3 w-3" />
                                </Button>
                              </div>
                            </div>
                          </CardContent>
                        </Card>
                      );
                    })}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* PATIENTS TAB */}
        <TabsContent value="patients" className="mt-4" data-testid="patients-content">
          <div className="flex gap-4">
            <div className={selectedPatient ? "w-1/3 min-w-[280px]" : "w-full"}>
              <div className="mb-3 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  value={patSearch}
                  onChange={(e) => setPatSearch(e.target.value)}
                  placeholder="Search patients..."
                  className="pl-9"
                  data-testid="input-patient-search"
                />
              </div>
              <Card>
                <ScrollArea className="h-[600px]">
                  <div className="divide-y">
                    {filteredPatients.map((p) => (
                      <button
                        key={p.id}
                        onClick={() => { setSelectedPatient(p); setPatientSubTab("overview"); setSelectedTooth(null); }}
                        className={`w-full text-left p-3 flex items-center gap-3 hover-elevate transition-colors ${selectedPatient?.id === p.id ? "bg-accent/50" : ""}`}
                        data-testid={`patient-row-${p.id}`}
                      >
                        <div className="w-9 h-9 rounded-full bg-muted flex items-center justify-center text-xs font-bold text-muted-foreground flex-shrink-0">
                          {p.fn[0]}{p.ln[0]}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-foreground truncate">{p.fn} {p.ln}</p>
                          <p className="text-xs text-muted-foreground">{p.provider} {p.balance > 0 ? `- $${p.balance.toFixed(2)}` : ""}</p>
                        </div>
                        <Badge variant={p.status === "active" ? "default" : "secondary"} className="text-[10px]" data-testid={`badge-patient-status-${p.id}`}>{p.status}</Badge>
                        <ChevronRight className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                      </button>
                    ))}
                  </div>
                </ScrollArea>
              </Card>
            </div>

            {selectedPatient && (
              <div className="flex-1 min-w-0" data-testid="patient-detail-panel">
                <Card>
                  <CardHeader className="flex flex-row items-center justify-between gap-2 space-y-0 pb-2">
                    <div>
                      <CardTitle data-testid="text-patient-name">{selectedPatient.fn} {selectedPatient.ln}</CardTitle>
                      <p className="text-xs text-muted-foreground mt-0.5">{selectedPatient.gender === "F" ? "Female" : "Male"} - DOB: {selectedPatient.dob} - {selectedPatient.provider}</p>
                    </div>
                    {selectedPatient.alert && (
                      <Badge variant="destructive" className="text-[10px]" data-testid="badge-patient-alert">
                        <AlertTriangle className="h-3 w-3 mr-1" />{selectedPatient.alert}
                      </Badge>
                    )}
                  </CardHeader>
                  <CardContent>
                    <Tabs value={patientSubTab} onValueChange={setPatientSubTab} data-testid="patient-sub-tabs">
                      <TabsList className="mb-3" data-testid="patient-sub-tabs-list">
                        <TabsTrigger value="overview" data-testid="subtab-overview">Overview</TabsTrigger>
                        <TabsTrigger value="charting" data-testid="subtab-charting">Charting</TabsTrigger>
                        <TabsTrigger value="treatment" data-testid="subtab-treatment">Treatment Plans</TabsTrigger>
                        <TabsTrigger value="ledger" data-testid="subtab-ledger">Ledger</TabsTrigger>
                        <TabsTrigger value="comms" data-testid="subtab-comms">Communications</TabsTrigger>
                      </TabsList>

                      <TabsContent value="overview" data-testid="patient-overview">
                        <div className="grid gap-4 md:grid-cols-2">
                          <div className="space-y-3">
                            <div>
                              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">Demographics</p>
                              <div className="space-y-1 text-sm">
                                <p className="text-foreground"><span className="text-muted-foreground">Phone:</span> {selectedPatient.phone}</p>
                                <p className="text-foreground"><span className="text-muted-foreground">Email:</span> {selectedPatient.email}</p>
                                <p className="text-foreground"><span className="text-muted-foreground">DOB:</span> {selectedPatient.dob}</p>
                                <p className="text-foreground"><span className="text-muted-foreground">Gender:</span> {selectedPatient.gender === "F" ? "Female" : "Male"}</p>
                                <p className="text-foreground"><span className="text-muted-foreground">Last Visit:</span> {selectedPatient.lastVisit}</p>
                                <p className="text-foreground"><span className="text-muted-foreground">Next Appt:</span> {selectedPatient.nextAppt}</p>
                              </div>
                            </div>
                            {selectedPatient.medHx.length > 0 && (
                              <div>
                                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">Medical History</p>
                                <div className="flex flex-wrap gap-1">
                                  {selectedPatient.medHx.map((m, i) => (
                                    <Badge key={i} variant="secondary" className="text-[10px]" data-testid={`badge-medhx-${i}`}>{m}</Badge>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                          <div className="space-y-3">
                            <div>
                              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">Insurance</p>
                              <div className="space-y-1 text-sm">
                                <p className="text-foreground"><span className="text-muted-foreground">Plan:</span> {selectedPatient.insurance.primary}</p>
                                <p className="text-foreground"><span className="text-muted-foreground">Member ID:</span> {selectedPatient.insurance.memberId}</p>
                                <p className="text-foreground"><span className="text-muted-foreground">Group:</span> {selectedPatient.insurance.group}</p>
                                <p className="text-foreground"><span className="text-muted-foreground">Employer:</span> {selectedPatient.insurance.employer}</p>
                                <p className="text-foreground"><span className="text-muted-foreground">Deductible:</span> ${selectedPatient.insurance.deductible} (Used: ${selectedPatient.insurance.used})</p>
                                <p className="text-foreground"><span className="text-muted-foreground">Annual Max:</span> ${selectedPatient.insurance.annual_max}</p>
                              </div>
                            </div>
                            <div>
                              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">Balance</p>
                              <p className={`text-lg font-bold ${selectedPatient.balance > 0 ? "text-red-500" : "text-foreground"}`} data-testid="text-patient-balance">${selectedPatient.balance.toFixed(2)}</p>
                            </div>
                            {selectedPatient.alert && (
                              <div>
                                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">Medical Alerts</p>
                                <Badge variant="destructive" data-testid="badge-medical-alert">
                                  <AlertTriangle className="h-3 w-3 mr-1" />{selectedPatient.alert}
                                </Badge>
                              </div>
                            )}
                          </div>
                        </div>
                      </TabsContent>

                      <TabsContent value="charting" data-testid="patient-charting">
                        <ToothChart chart={selectedPatient.chart} selectedTooth={selectedTooth} onSelectTooth={setSelectedTooth} />
                      </TabsContent>

                      <TabsContent value="treatment" data-testid="patient-treatment-plans">
                        {selectedPatient.txPlans.length === 0 ? (
                          <p className="text-sm text-muted-foreground py-4">No treatment plans on file.</p>
                        ) : (
                          <div className="space-y-4">
                            {selectedPatient.txPlans.map((plan) => (
                              <Card key={plan.id} data-testid={`tx-plan-${plan.id}`}>
                                <CardContent className="p-4">
                                  <div className="flex items-center justify-between gap-2 flex-wrap mb-3">
                                    <div>
                                      <p className="text-sm font-semibold text-foreground">{plan.name}</p>
                                      <p className="text-xs text-muted-foreground">Presented: {plan.presented}</p>
                                    </div>
                                    <Badge variant={plan.status === "accepted" ? "default" : "secondary"} data-testid={`badge-plan-status-${plan.id}`}>{plan.status}</Badge>
                                  </div>
                                  <Table>
                                    <TableHeader>
                                      <TableRow>
                                        <TableHead className="text-xs">Tooth</TableHead>
                                        <TableHead className="text-xs">CDT</TableHead>
                                        <TableHead className="text-xs">Description</TableHead>
                                        <TableHead className="text-xs text-right">Fee</TableHead>
                                        <TableHead className="text-xs text-right">Ins Est.</TableHead>
                                      </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                      {plan.items.map((item, j) => (
                                        <TableRow key={j} data-testid={`tx-item-${plan.id}-${j}`}>
                                          <TableCell className="text-xs">{item.tooth ?? "-"}</TableCell>
                                          <TableCell className="text-xs font-mono">{item.cdt}</TableCell>
                                          <TableCell className="text-xs">{item.desc}</TableCell>
                                          <TableCell className="text-xs text-right">${item.fee.toFixed(2)}</TableCell>
                                          <TableCell className="text-xs text-right">${item.ins_est.toFixed(2)}</TableCell>
                                        </TableRow>
                                      ))}
                                    </TableBody>
                                  </Table>
                                  <div className="flex justify-end gap-4 mt-2 text-xs text-muted-foreground">
                                    <span>Total: ${plan.items.reduce((s, it) => s + it.fee, 0).toFixed(2)}</span>
                                    <span>Ins Est: ${plan.items.reduce((s, it) => s + it.ins_est, 0).toFixed(2)}</span>
                                    <span className="font-semibold text-foreground">Patient Est: ${plan.items.reduce((s, it) => s + (it.fee - it.ins_est), 0).toFixed(2)}</span>
                                  </div>
                                </CardContent>
                              </Card>
                            ))}
                          </div>
                        )}
                      </TabsContent>

                      <TabsContent value="ledger" data-testid="patient-ledger">
                        {selectedPatient.ledger.length === 0 ? (
                          <p className="text-sm text-muted-foreground py-4">No ledger entries.</p>
                        ) : (
                          <Table>
                            <TableHeader>
                              <TableRow>
                                <TableHead className="text-xs">Date</TableHead>
                                <TableHead className="text-xs">Description</TableHead>
                                <TableHead className="text-xs text-right">Charge</TableHead>
                                <TableHead className="text-xs text-right">Payment</TableHead>
                                <TableHead className="text-xs text-right">Insurance</TableHead>
                                <TableHead className="text-xs text-right">Balance</TableHead>
                              </TableRow>
                            </TableHeader>
                            <TableBody>
                              {selectedPatient.ledger.map((entry, i) => (
                                <TableRow key={i} data-testid={`ledger-row-${i}`}>
                                  <TableCell className="text-xs">{entry.date}</TableCell>
                                  <TableCell className="text-xs">{entry.desc}</TableCell>
                                  <TableCell className="text-xs text-right">{entry.charge > 0 ? `$${entry.charge.toFixed(2)}` : "-"}</TableCell>
                                  <TableCell className="text-xs text-right">{entry.payment > 0 ? `$${entry.payment.toFixed(2)}` : "-"}</TableCell>
                                  <TableCell className="text-xs text-right">{entry.ins > 0 ? `$${entry.ins.toFixed(2)}` : "-"}</TableCell>
                                  <TableCell className="text-xs text-right font-medium">${entry.bal.toFixed(2)}</TableCell>
                                </TableRow>
                              ))}
                            </TableBody>
                          </Table>
                        )}
                      </TabsContent>

                      <TabsContent value="comms" data-testid="patient-comms">
                        {selectedPatient.comms.length === 0 ? (
                          <p className="text-sm text-muted-foreground py-4">No communications on file.</p>
                        ) : (
                          <div className="space-y-2">
                            {selectedPatient.comms.map((c, i) => {
                              const CommIcon = getCommIcon(c.type);
                              return (
                                <div key={i} className="flex gap-3 py-2 border-b last:border-0" data-testid={`comm-entry-${i}`}>
                                  <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${c.dir === "in" ? "bg-blue-500/10" : "bg-muted"}`}>
                                    <CommIcon className={`h-3.5 w-3.5 ${c.dir === "in" ? "text-blue-500" : "text-muted-foreground"}`} />
                                  </div>
                                  <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                                      <Badge variant="secondary" className="text-[10px]">{c.type}</Badge>
                                      <span className="text-[10px] text-muted-foreground">{c.dir === "in" ? "Inbound" : "Outbound"}</span>
                                      <span className="text-[10px] text-muted-foreground">{c.date}</span>
                                      {c.duration && <span className="text-[10px] text-muted-foreground">{c.duration}</span>}
                                    </div>
                                    <p className="text-xs text-foreground">{c.msg}</p>
                                  </div>
                                  <Badge variant="outline" className="text-[10px] self-start">{c.status}</Badge>
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </TabsContent>
                    </Tabs>
                  </CardContent>
                </Card>
              </div>
            )}
          </div>
        </TabsContent>

        {/* SCHEDULE TAB */}
        <TabsContent value="schedule" className="mt-4" data-testid="schedule-content">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between gap-2 space-y-0 pb-2">
              <CardTitle className="text-sm font-semibold">Full Day Schedule</CardTitle>
              <Calendar className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs">Time</TableHead>
                    <TableHead className="text-xs">Duration</TableHead>
                    <TableHead className="text-xs">Patient</TableHead>
                    <TableHead className="text-xs">Procedure</TableHead>
                    <TableHead className="text-xs">Provider</TableHead>
                    <TableHead className="text-xs">Type</TableHead>
                    <TableHead className="text-xs">Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {SCHEDULE.map((s, i) => (
                    <TableRow key={i} data-testid={`schedule-row-${i}`}>
                      <TableCell className="text-sm font-mono font-semibold">{s.time}</TableCell>
                      <TableCell className="text-xs text-muted-foreground">{s.duration} min</TableCell>
                      <TableCell className="text-sm font-medium">
                        <div className="flex items-center gap-2">
                          <div className={`w-2 h-2 rounded-full flex-shrink-0 ${TYPE_COLORS[s.type]}`} />
                          {s.patient}
                        </div>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">{s.procedure}</TableCell>
                      <TableCell className="text-xs text-muted-foreground">{s.provider}</TableCell>
                      <TableCell>
                        <Badge variant="secondary" className={`text-[10px] no-default-hover-elevate no-default-active-elevate ${TYPE_BADGE_VARIANTS[s.type]}`} data-testid={`schedule-type-badge-${i}`}>{s.type}</Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant={s.status === "confirmed" ? "default" : s.status === "pending" ? "secondary" : "outline"} className="text-[10px]" data-testid={`schedule-status-badge-${i}`}>{s.status}</Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* CHARTING TAB */}
        {selectedPatient && (
          <TabsContent value="charting" className="mt-4" data-testid="charting-content">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between gap-2 space-y-0 pb-2">
                <CardTitle className="text-sm font-semibold">{selectedPatient.fn} {selectedPatient.ln} - Tooth Chart</CardTitle>
                <Activity className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <ToothChart chart={selectedPatient.chart} selectedTooth={selectedTooth} onSelectTooth={setSelectedTooth} />
              </CardContent>
            </Card>
          </TabsContent>
        )}

        {/* AI ENGINE TAB */}
        <TabsContent value="ai" className="mt-4" data-testid="ai-content">
          <div className="space-y-4">
            <div className="flex items-center gap-2 mb-2">
              <Bot className="h-5 w-5 text-muted-foreground" />
              <h2 className="text-lg font-bold text-foreground">AI-Powered Insights</h2>
              <Badge variant="destructive" className="text-[10px]" data-testid="badge-urgent-count">{AI_INSIGHTS.filter(i => i.priority === "high").length} urgent</Badge>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              {AI_INSIGHTS.map((ins, i) => {
                const Icon = ins.icon;
                return (
                  <Card key={i} data-testid={`ai-insight-full-${i}`}>
                    <CardContent className="p-4">
                      <div className="flex items-start gap-3">
                        <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center flex-shrink-0">
                          <Icon className="h-5 w-5 text-muted-foreground" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap mb-1">
                            <Badge variant={PRIORITY_COLORS[ins.priority] as any} className="text-[10px]" data-testid={`ai-badge-priority-${i}`}>{ins.priority}</Badge>
                            <span className="text-sm font-semibold text-foreground">{ins.title}</span>
                          </div>
                          <p className="text-sm text-muted-foreground leading-relaxed mb-3">{ins.desc}</p>
                          <Button size="sm" data-testid={`button-ai-action-${i}`}>
                            {ins.action} <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
                          </Button>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function ToothChart({ chart, selectedTooth, onSelectTooth }: { chart: Record<number, ToothCondition>; selectedTooth: number | null; onSelectTooth: (t: number | null) => void }) {
  const getCondition = (tooth: number): string => chart[tooth] || "healthy";
  const getColorClass = (tooth: number): string => TOOTH_COLORS[getCondition(tooth)] || TOOTH_COLORS.healthy;

  return (
    <div className="space-y-4" data-testid="tooth-chart">
      <div className="flex items-center gap-2 flex-wrap mb-2">
        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Legend:</p>
        {Object.entries(TOOTH_COLORS).map(([cond, cls]) => (
          <div key={cond} className="flex items-center gap-1">
            <div className={`w-3 h-3 rounded-sm ${cls.split(" ")[0]}`} />
            <span className="text-[10px] text-muted-foreground capitalize">{cond.replace("_", " ")}</span>
          </div>
        ))}
      </div>

      <div>
        <p className="text-xs font-semibold text-muted-foreground mb-2">Upper (1-16)</p>
        <div className="grid grid-cols-16 gap-1">
          {UPPER_TEETH.map((t) => (
            <Button
              key={t}
              size="sm"
              variant="ghost"
              onClick={() => onSelectTooth(selectedTooth === t ? null : t)}
              className={`h-10 text-xs font-bold p-0 ${getColorClass(t)} ${selectedTooth === t ? "ring-2 ring-foreground ring-offset-2" : ""}`}
              data-testid={`tooth-${t}`}
            >
              {t}
            </Button>
          ))}
        </div>
      </div>

      <div>
        <p className="text-xs font-semibold text-muted-foreground mb-2">Lower (32-17)</p>
        <div className="grid grid-cols-16 gap-1">
          {LOWER_TEETH.map((t) => (
            <Button
              key={t}
              size="sm"
              variant="ghost"
              onClick={() => onSelectTooth(selectedTooth === t ? null : t)}
              className={`h-10 text-xs font-bold p-0 ${getColorClass(t)} ${selectedTooth === t ? "ring-2 ring-foreground ring-offset-2" : ""}`}
              data-testid={`tooth-${t}`}
            >
              {t}
            </Button>
          ))}
        </div>
      </div>

      {selectedTooth && (
        <Card data-testid="tooth-detail">
          <CardContent className="p-3">
            <div className="flex items-center gap-2">
              <div className={`w-8 h-8 rounded-md flex items-center justify-center text-sm font-bold ${getColorClass(selectedTooth)}`}>
                {selectedTooth}
              </div>
              <div>
                <p className="text-sm font-semibold text-foreground">Tooth #{selectedTooth}</p>
                <p className="text-xs text-muted-foreground capitalize">Condition: {getCondition(selectedTooth).replace("_", " ")}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}