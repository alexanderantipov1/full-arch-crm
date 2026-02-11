import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "wouter";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import {
  AreaChart, Area, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, RadarChart, Radar, PolarGrid, PolarAngleAxis,
  PolarRadiusAxis, Legend, ComposedChart, BarChart, Bar, Line,
} from "recharts";
import {
  Zap, Users, BarChart3, GitBranch, Rocket, Phone, Mail, MessageSquare,
  CalendarDays, FileText, CreditCard, Plus, TrendingUp, Target, DollarSign,
  Activity, ArrowRight, X, Sparkles, Brain,
} from "lucide-react";
import type { Patient, Appointment, TreatmentPlan, BillingClaim } from "@shared/schema";

const REVENUE_TREND = [
  { month: "Jul", implants: 310000, ortho: 245000, perio: 120000, surgery: 190000, total: 865000 },
  { month: "Aug", implants: 345000, ortho: 260000, perio: 135000, surgery: 205000, total: 945000 },
  { month: "Sep", implants: 380000, ortho: 275000, perio: 128000, surgery: 218000, total: 1001000 },
  { month: "Oct", implants: 410000, ortho: 290000, perio: 145000, surgery: 230000, total: 1075000 },
  { month: "Nov", implants: 395000, ortho: 310000, perio: 155000, surgery: 245000, total: 1105000 },
  { month: "Dec", implants: 365000, ortho: 285000, perio: 138000, surgery: 210000, total: 998000 },
  { month: "Jan", implants: 440000, ortho: 320000, perio: 162000, surgery: 260000, total: 1182000 },
  { month: "Feb", implants: 485000, ortho: 348000, perio: 178000, surgery: 285000, total: 1296000 },
];

const PIPELINE_STAGES = [
  { stage: "New Lead", count: 234, value: 1870000, color: "#64748B" },
  { stage: "Consultation Booked", count: 187, value: 1496000, color: "#6366F1" },
  { stage: "Consult Completed", count: 142, value: 1136000, color: "#0EA5E9" },
  { stage: "Treatment Plan Sent", count: 98, value: 784000, color: "#F59E0B" },
  { stage: "Plan Accepted", count: 67, value: 536000, color: "#10B981" },
  { stage: "In Treatment", count: 89, value: 712000, color: "#00E6B4" },
  { stage: "Completed", count: 156, value: 1248000, color: "#22D3EE" },
];

const FUNNEL_DATA = [
  { name: "Website Visitors", value: 14200, fill: "#6366F1" },
  { name: "Form Submissions", value: 3800, fill: "#0EA5E9" },
  { name: "Consultations", value: 1420, fill: "#10B981" },
  { name: "Treatment Plans", value: 890, fill: "#F59E0B" },
  { name: "Cases Started", value: 534, fill: "#00E6B4" },
];

const SPECIALTY_MIX = [
  { name: "Implants", value: 38, color: "#00E6B4" },
  { name: "Ortho", value: 27, color: "#6366F1" },
  { name: "Perio", value: 14, color: "#F59E0B" },
  { name: "Surgery", value: 21, color: "#EF4444" },
];

const PATIENT_SOURCE = [
  { name: "Google Ads", value: 32, color: "#4285F4" },
  { name: "Referrals", value: 24, color: "#00E6B4" },
  { name: "Organic SEO", value: 18, color: "#10B981" },
  { name: "Meta Ads", value: 14, color: "#6366F1" },
  { name: "Direct", value: 8, color: "#F59E0B" },
  { name: "Other", value: 4, color: "#64748B" },
];

const PROVIDER_PERFORMANCE = [
  { name: "Dr. Chen", production: 185000, collections: 172000, acceptance: 82, patients: 134, specialty: "Implants" },
  { name: "Dr. Park", production: 148000, collections: 141000, acceptance: 76, patients: 198, specialty: "Ortho" },
  { name: "Dr. Rivera", production: 125000, collections: 118000, acceptance: 71, patients: 89, specialty: "Perio" },
  { name: "Dr. Okafor", production: 162000, collections: 155000, acceptance: 79, patients: 112, specialty: "Surgery" },
  { name: "Dr. Nguyen", production: 138000, collections: 131000, acceptance: 74, patients: 156, specialty: "Implants" },
];

const RADAR_DATA = [
  { metric: "Revenue Growth", current: 92, benchmark: 65 },
  { metric: "Case Accept.", current: 72, benchmark: 55 },
  { metric: "Patient Retention", current: 85, benchmark: 70 },
  { metric: "Chair Utilization", current: 87, benchmark: 75 },
  { metric: "New Patients", current: 78, benchmark: 60 },
  { metric: "Collections", current: 94, benchmark: 80 },
];

const DAILY_PRODUCTION = Array.from({ length: 20 }, (_, i) => ({
  day: i + 1,
  actual: Math.round(38000 + Math.random() * 28000 + (i > 14 ? 8000 : 0)),
  goal: 52000,
}));

const HOURLY_PATIENTS = [
  { hour: "7AM", count: 4 },{ hour: "8AM", count: 12 },{ hour: "9AM", count: 18 },
  { hour: "10AM", count: 22 },{ hour: "11AM", count: 20 },{ hour: "12PM", count: 8 },
  { hour: "1PM", count: 16 },{ hour: "2PM", count: 21 },{ hour: "3PM", count: 19 },
  { hour: "4PM", count: 14 },{ hour: "5PM", count: 6 },
];

const CRM_PATIENTS = [
  { id: 1, name: "Margaret Sullivan", email: "msullivan@email.com", phone: "(555) 234-8901", stage: "In Treatment", specialty: "Implants", provider: "Dr. Chen", ltv: 24500, lastVisit: "Feb 7, 2026", nextAppt: "Feb 18, 2026", treatmentPlan: "Full Arch Implants (Upper)", status: "active", source: "Google Ads", notes: "All-on-4 upper arch. Phase 1 complete. Healing well.", score: 95, avatar: "MS" },
  { id: 2, name: "Robert Kim", email: "rkim@email.com", phone: "(555) 345-6789", stage: "Treatment Plan Sent", specialty: "Implants", provider: "Dr. Chen", ltv: 8200, lastVisit: "Feb 3, 2026", nextAppt: "Pending", treatmentPlan: "Single Implant #14 + Crown", status: "warm", source: "Referral", notes: "Comparing pricing. Sent finance options. Follow up Feb 12.", score: 72, avatar: "RK" },
  { id: 3, name: "Diana Patel", email: "dpatel@email.com", phone: "(555) 456-7890", stage: "Consult Completed", specialty: "Ortho", provider: "Dr. Park", ltv: 3200, lastVisit: "Jan 28, 2026", nextAppt: "Pending", treatmentPlan: "Invisalign Comprehensive", status: "warm", source: "Meta Ads", notes: "Interested but concerned about treatment time. Send before/after gallery.", score: 65, avatar: "DP" },
  { id: 4, name: "James Okafor", email: "jokafor@email.com", phone: "(555) 567-8901", stage: "In Treatment", specialty: "Ortho", provider: "Dr. Park", ltv: 6800, lastVisit: "Feb 5, 2026", nextAppt: "Mar 5, 2026", treatmentPlan: "Invisalign + Whitening Bundle", status: "active", source: "Organic SEO", notes: "Tray 12 of 24. On track. Great compliance.", score: 88, avatar: "JO" },
  { id: 5, name: "Sarah Chen", email: "schen@email.com", phone: "(555) 678-9012", stage: "New Lead", specialty: "Implants", provider: "Unassigned", ltv: 0, lastVisit: "Never", nextAppt: "Pending", treatmentPlan: "TBD - Inquiry for implant consultation", status: "new", source: "Google Ads", notes: "Submitted form 2 hours ago. Missing 2 lower molars. Has insurance.", score: 45, avatar: "SC" },
  { id: 6, name: "Michael Torres", email: "mtorres@email.com", phone: "(555) 789-0123", stage: "Completed", specialty: "Surgery", provider: "Dr. Okafor", ltv: 18700, lastVisit: "Jan 15, 2026", nextAppt: "Jul 15, 2026", treatmentPlan: "Wisdom Teeth Extraction + Bone Graft", status: "completed", source: "Referral", notes: "Recovery complete. NPS: 10. Request testimonial video. Referral program enrolled.", score: 98, avatar: "MT" },
  { id: 7, name: "Lisa Wang", email: "lwang@email.com", phone: "(555) 890-1234", stage: "Plan Accepted", specialty: "Implants", provider: "Dr. Nguyen", ltv: 4100, lastVisit: "Feb 1, 2026", nextAppt: "Feb 14, 2026", treatmentPlan: "2 Implants #19 #30 + Crowns", status: "active", source: "Google Ads", notes: "Financing approved through Proceed. Surgery scheduled Valentine's Day.", score: 82, avatar: "LW" },
  { id: 8, name: "Carlos Mendez", email: "cmendez@email.com", phone: "(555) 901-2345", stage: "Consultation Booked", specialty: "Perio", provider: "Dr. Rivera", ltv: 1200, lastVisit: "Nov 10, 2025", nextAppt: "Feb 12, 2026", treatmentPlan: "Scaling & Root Planing Evaluation", status: "warm", source: "Direct", notes: "Referred by hygienist for deep pockets. Insurance verified. Stage 3 perio likely.", score: 58, avatar: "CM" },
];

const ACTIVITIES = [
  { time: "2 min ago", type: "ai", text: "AI detected: Robert Kim opened treatment plan email 3x. Recommend immediate call.", icon: Brain },
  { time: "18 min ago", type: "call", text: "Maria L. called Sarah Chen - voicemail left. Auto follow-up SMS scheduled.", icon: Phone },
  { time: "34 min ago", type: "booking", text: "Lisa Wang confirmed surgery appointment for Feb 14 via online portal.", icon: CalendarDays },
  { time: "1 hr ago", type: "payment", text: "Margaret Sullivan - payment of $4,200 processed (Phase 2 deposit).", icon: CreditCard },
  { time: "1.5 hr ago", type: "ai", text: "AI: 12 patients overdue for perio recall. Campaign auto-launched to 234 contacts.", icon: Brain },
  { time: "2 hr ago", type: "review", text: "Michael Torres left 5-star Google review. Referral bonus email auto-sent.", icon: Sparkles },
  { time: "3 hr ago", type: "form", text: "New lead: Sarah Chen submitted implant inquiry form from Google Ads landing page.", icon: FileText },
  { time: "4 hr ago", type: "ai", text: "AI analysis: Tuesday PM slots 23% underbooked. Recommend targeted recall for ortho check-ins.", icon: Brain },
];

const TASKS_CRM = [
  { id: 1, task: "Call Robert Kim - he opened treatment plan 3x today", assignee: "Maria L.", due: "Today", priority: "critical", type: "follow-up", aiGen: true },
  { id: 2, task: "Send Diana Patel before/after Invisalign gallery", assignee: "Jake R.", due: "Today", priority: "high", type: "nurture", aiGen: true },
  { id: 3, task: "Confirm Margaret Sullivan's Feb 18 appointment", assignee: "Front Desk", due: "Feb 14", priority: "medium", type: "admin", aiGen: false },
  { id: 4, task: "Request video testimonial from Michael Torres", assignee: "Dr. Okafor", due: "Feb 12", priority: "high", type: "marketing", aiGen: true },
  { id: 5, task: "Schedule Carlos Mendez CBCT scan before consult", assignee: "Sarah M.", due: "Feb 11", priority: "high", type: "clinical", aiGen: false },
  { id: 6, task: "Process Lisa Wang's insurance pre-auth for implants", assignee: "Billing", due: "Feb 12", priority: "critical", type: "billing", aiGen: false },
];

const fmt = (n: number) => n >= 1000000 ? `$${(n/1000000).toFixed(1)}M` : n >= 1000 ? `$${(n/1000).toFixed(0)}K` : `$${n}`;

const stageColors: Record<string, string> = { "New Lead": "#64748B", "Consultation Booked": "#6366F1", "Consult Completed": "#0EA5E9", "Treatment Plan Sent": "#F59E0B", "Plan Accepted": "#10B981", "In Treatment": "#00E6B4", "Completed": "#22D3EE" };
const statusColors: Record<string, string> = { new: "#6366F1", warm: "#F59E0B", active: "#00E6B4", completed: "#22D3EE" };
const priorityColors: Record<string, string> = { critical: "#EF4444", high: "#F59E0B", medium: "#0EA5E9", low: "#64748B" };

function Spark({ data, color = "#00E6B4", w = 80, h = 28 }: { data: number[]; color?: string; w?: number; h?: number }) {
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  const points = data.map((v, i) => `${(i / (data.length - 1)) * w},${h - ((v - min) / range) * (h - 4) - 2}`).join(" ");
  return (
    <svg width={w} height={h} className="block">
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={w} cy={h - ((data[data.length - 1] - min) / range) * (h - 4) - 2} r="2.5" fill={color} />
    </svg>
  );
}

function KPICard({ label, value, change, spark, color, icon: Icon }: { label: string; value: string; change?: string; spark?: number[]; color?: string; icon?: any }) {
  return (
    <Card data-testid={`kpi-${label.toLowerCase().replace(/\s+/g, "-")}`}>
      <CardContent className="p-4 relative overflow-visible">
        {Icon && <Icon className="absolute top-3 right-3 h-8 w-8 text-muted-foreground/5" />}
        <div className="text-[10px] font-semibold tracking-wider uppercase text-muted-foreground mb-1">{label}</div>
        <div className="flex items-end justify-between gap-2">
          <div>
            <div className="text-2xl font-extrabold tracking-tight">{value}</div>
            {change && (
              <div className={`text-xs font-semibold mt-0.5 ${change.startsWith("+") || change.startsWith("\u2191") ? "text-emerald-500" : change.startsWith("-") || change.startsWith("\u2193") ? "text-red-500" : "text-muted-foreground"}`}>
                {change}
              </div>
            )}
          </div>
          {spark && <Spark data={spark} color={color || "#00E6B4"} />}
        </div>
      </CardContent>
    </Card>
  );
}

function ChartCard({ title, children, className = "" }: { title?: string; children: React.ReactNode; className?: string }) {
  return (
    <Card className={className}>
      <CardContent className="p-4">
        {title && <div className="text-[11px] font-bold tracking-wider uppercase text-muted-foreground mb-3">{title}</div>}
        {children}
      </CardContent>
    </Card>
  );
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border bg-popover p-3 text-xs shadow-md">
      <div className="font-bold mb-1">{label}</div>
      {payload.map((p: any, i: number) => (
        <div key={i} className="flex items-center gap-2 mb-0.5">
          <div className="w-2 h-2 rounded-sm" style={{ background: p.color }} />
          <span className="text-muted-foreground">{p.name}:</span>
          <span className="font-bold">{typeof p.value === "number" && p.value > 999 ? fmt(p.value) : p.value}</span>
        </div>
      ))}
    </div>
  );
};

function NeuralBG() {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = ref.current; if (!c) return;
    const ctx = c.getContext("2d");
    if (!ctx) return;
    c.width = c.offsetWidth * 2; c.height = c.offsetHeight * 2;
    let af: number;
    let t = 0;
    const nodes = Array.from({ length: 30 }, () => ({ x: Math.random() * c.width, y: Math.random() * c.height, vx: (Math.random() - 0.5) * 0.6, vy: (Math.random() - 0.5) * 0.6, r: Math.random() * 2 + 1 }));
    const draw = () => {
      t += 0.008; ctx.clearRect(0, 0, c.width, c.height);
      nodes.forEach((n) => { n.x += n.vx; n.y += n.vy; if (n.x < 0 || n.x > c.width) n.vx *= -1; if (n.y < 0 || n.y > c.height) n.vy *= -1; });
      nodes.forEach((a, i) => nodes.slice(i + 1).forEach((b) => {
        const d = Math.hypot(a.x - b.x, a.y - b.y);
        if (d < 160) { ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.strokeStyle = `rgba(14,165,233,${0.06 * (1 - d / 160)})`; ctx.lineWidth = 0.8; ctx.stroke(); }
      }));
      nodes.forEach((n) => { const p = Math.sin(t * 2 + n.x * 0.01) * 0.5 + 0.5; ctx.beginPath(); ctx.arc(n.x, n.y, n.r + p * 1.5, 0, Math.PI * 2); ctx.fillStyle = `rgba(14,165,233,${0.15 + p * 0.2})`; ctx.fill(); });
      af = requestAnimationFrame(draw);
    };
    draw(); return () => cancelAnimationFrame(af);
  }, []);
  return <canvas ref={ref} className="absolute inset-0 w-full h-full opacity-70" />;
}

interface DashboardStats {
  totalPatients: number;
  todayAppointments: number;
  pendingTreatmentPlans: number;
  pendingClaims: number;
}

export default function CommandCenter() {
  const [mainTab, setMainTab] = useState("dashboard");
  const [biTab, setBiTab] = useState("overview");
  const [selectedPatient, setSelectedPatient] = useState<typeof CRM_PATIENTS[0] | null>(null);
  const [insightIdx, setInsightIdx] = useState(0);

  useEffect(() => {
    const iv = setInterval(() => setInsightIdx((p) => (p + 1) % ACTIVITIES.length), 4000);
    return () => clearInterval(iv);
  }, []);

  const { data: stats } = useQuery<DashboardStats>({ queryKey: ["/api/dashboard/stats"] });
  const { data: patients } = useQuery<Patient[]>({ queryKey: ["/api/patients"] });
  const { data: treatmentPlans } = useQuery<TreatmentPlan[]>({ queryKey: ["/api/treatment-plans"] });

  const patientCount = stats?.totalPatients || patients?.length || 0;
  const planCount = treatmentPlans?.length || 0;
  const approvedPlans = treatmentPlans?.filter(p => p.status === "approved").length || 0;
  const acceptanceRate = planCount > 0 ? Math.round((approvedPlans / planCount) * 100) : 72;

  const ActivityIcon = ACTIVITIES[insightIdx].icon;

  return (
    <div className="space-y-5" data-testid="command-center">
      <Tabs value={mainTab} onValueChange={setMainTab}>
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-2xl font-extrabold tracking-tight" data-testid="text-page-title">Command Center</h1>
            <p className="text-sm text-muted-foreground">Executive intelligence for your dental practice</p>
          </div>
          <TabsList data-testid="command-center-tabs">
            <TabsTrigger value="dashboard" data-testid="tab-dashboard"><Zap className="h-3.5 w-3.5 mr-1.5" />Dashboard</TabsTrigger>
            <TabsTrigger value="crm" data-testid="tab-crm"><Users className="h-3.5 w-3.5 mr-1.5" />CRM</TabsTrigger>
            <TabsTrigger value="analytics" data-testid="tab-analytics"><BarChart3 className="h-3.5 w-3.5 mr-1.5" />Analytics</TabsTrigger>
            <TabsTrigger value="pipeline" data-testid="tab-pipeline"><GitBranch className="h-3.5 w-3.5 mr-1.5" />Pipeline</TabsTrigger>
            <TabsTrigger value="growth" data-testid="tab-growth"><Rocket className="h-3.5 w-3.5 mr-1.5" />Growth</TabsTrigger>
          </TabsList>
        </div>

        {/* ═══ DASHBOARD TAB ═══ */}
        <TabsContent value="dashboard" className="space-y-5 mt-4">
          <Card className="relative overflow-hidden h-[140px]" data-testid="neural-banner">
            <NeuralBG />
            <div className="absolute inset-0 flex items-end p-5" style={{ background: "linear-gradient(transparent 20%, hsl(var(--background) / 0.92))" }}>
              <div className="flex items-center gap-3 flex-1 min-w-0">
                <ActivityIcon className="h-5 w-5 text-sky-500 flex-shrink-0" />
                <div className="min-w-0">
                  <div className="text-[10px] font-bold tracking-widest uppercase text-sky-500 mb-0.5">Neural AI &middot; {ACTIVITIES[insightIdx].time}</div>
                  <div className="text-sm font-bold truncate">{ACTIVITIES[insightIdx].text}</div>
                </div>
              </div>
              <Button size="sm" className="flex-shrink-0" data-testid="button-take-action">
                Take Action <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
              </Button>
            </div>
          </Card>

          <div className="grid gap-3 grid-cols-2 lg:grid-cols-5">
            <KPICard label="Monthly Revenue" value="$1.29M" change={"\u2191 23% MoM"} spark={REVENUE_TREND.map(r => r.total)} color="#00E6B4" icon={DollarSign} />
            <KPICard label="Active Pipeline" value="$4.78M" change="234 opportunities" spark={PIPELINE_STAGES.map(s => s.value)} color="#6366F1" icon={GitBranch} />
            <KPICard label="Patients (Active)" value={patientCount > 0 ? patientCount.toLocaleString() : "3,105"} change="+342 this month" spark={[2400,2520,2680,2750,2840,2920,3010,3105]} color="#0EA5E9" icon={Users} />
            <KPICard label="Case Acceptance" value={`${acceptanceRate}%`} change={`\u2191 8pts (AI scripts)`} spark={[54,58,62,64,66,68,70,acceptanceRate]} color="#F59E0B" icon={Target} />
            <KPICard label="Collections Rate" value="96.2%" change={"\u2191 1.4pts"} spark={[92,93,93.5,94,94.8,95,95.5,96.2]} color="#10B981" icon={CreditCard} />
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <ChartCard title="Revenue by Specialty - 8 Month Trend" className="lg:col-span-2">
              <div className="h-[220px]">
                <ResponsiveContainer>
                  <AreaChart data={REVENUE_TREND} margin={{ top: 5, right: 5, bottom: 0, left: 0 }}>
                    <defs>
                      {[["#00E6B4","implants"],["#6366F1","ortho"],["#F59E0B","perio"],["#EF4444","surgery"]].map(([c,k]) => (
                        <linearGradient key={k} id={`g_${k}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={c} stopOpacity={0.3} /><stop offset="100%" stopColor={c} stopOpacity={0} /></linearGradient>
                      ))}
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                    <XAxis dataKey="month" tick={{ fontSize: 11 }} className="text-muted-foreground" axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={(v) => `$${v/1000}K`} />
                    <Tooltip content={<CustomTooltip />} />
                    <Area type="monotone" dataKey="implants" name="Implants" stroke="#00E6B4" fill="url(#g_implants)" strokeWidth={2} />
                    <Area type="monotone" dataKey="ortho" name="Ortho" stroke="#6366F1" fill="url(#g_ortho)" strokeWidth={2} />
                    <Area type="monotone" dataKey="surgery" name="Surgery" stroke="#EF4444" fill="url(#g_surgery)" strokeWidth={2} />
                    <Area type="monotone" dataKey="perio" name="Perio" stroke="#F59E0B" fill="url(#g_perio)" strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </ChartCard>

            <ChartCard title="Specialty Revenue Mix">
              <div className="h-[220px]">
                <ResponsiveContainer>
                  <PieChart>
                    <Pie data={SPECIALTY_MIX} cx="50%" cy="50%" innerRadius="55%" outerRadius="80%" paddingAngle={3} dataKey="value" stroke="none">
                      {SPECIALTY_MIX.map((s, i) => <Cell key={i} fill={s.color} />)}
                    </Pie>
                    <Tooltip content={<CustomTooltip />} />
                    <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11, fontWeight: 600 }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </ChartCard>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <ChartCard title="Conversion Funnel">
              <div className="flex flex-col gap-2 py-2">
                {FUNNEL_DATA.map((f, i) => {
                  const widthPct = (f.value / FUNNEL_DATA[0].value) * 100;
                  return (
                    <div key={i} className="flex items-center gap-3" data-testid={`funnel-${f.name.toLowerCase().replace(/\s+/g, "-")}`}>
                      <div className="w-[100px] text-[11px] text-muted-foreground text-right flex-shrink-0">{f.name}</div>
                      <div className="flex-1 relative">
                        <div className="h-7 rounded-md overflow-hidden" style={{ background: `${f.fill}15` }}>
                          <div className="h-full rounded-md flex items-center pl-2.5 transition-all duration-1000" style={{ width: `${widthPct}%`, background: `linear-gradient(90deg, ${f.fill}, ${f.fill}99)` }}>
                            <span className="text-[11px] font-extrabold text-white">{f.value.toLocaleString()}</span>
                          </div>
                        </div>
                      </div>
                      {i > 0 && <div className="text-[10px] text-emerald-500 font-bold w-10 text-right">{Math.round((f.value / FUNNEL_DATA[i - 1].value) * 100)}%</div>}
                    </div>
                  );
                })}
              </div>
            </ChartCard>

            <Card>
              <CardContent className="p-4">
                <div className="text-[11px] font-bold tracking-wider uppercase text-muted-foreground mb-3">Live Activity Feed</div>
                <div className="space-y-2 max-h-[230px] overflow-y-auto">
                  {ACTIVITIES.map((a, i) => {
                    const AIcon = a.icon;
                    return (
                      <div key={i} className="flex gap-3 py-2 border-b last:border-0" data-testid={`activity-${i}`}>
                        <AIcon className={`h-4 w-4 flex-shrink-0 mt-0.5 ${a.type === "ai" ? "text-sky-500" : "text-muted-foreground"}`} />
                        <div>
                          <div className={`text-xs font-semibold leading-relaxed ${a.type === "ai" ? "text-sky-500" : ""}`}>{a.text}</div>
                          <div className="text-[10px] text-muted-foreground mt-0.5">{a.time}</div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* ═══ CRM TAB ═══ */}
        <TabsContent value="crm" className="space-y-5 mt-4">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <div>
              <h2 className="text-xl font-extrabold">Patient CRM</h2>
              <p className="text-sm text-muted-foreground">Contact management with AI-powered lead scoring</p>
            </div>
            <Button asChild data-testid="button-new-crm-patient">
              <Link href="/patients/new"><Plus className="mr-2 h-4 w-4" />New Patient</Link>
            </Button>
          </div>

          <div className="grid gap-3 grid-cols-2 lg:grid-cols-5">
            <KPICard label="Total Contacts" value={patientCount > 0 ? patientCount.toLocaleString() : "3,105"} icon={Users} />
            <KPICard label="New Leads (30d)" value="234" change="+18% vs last month" icon={UserPlus} />
            <KPICard label="Open Opps" value="$4.78M" icon={GitBranch} />
            <KPICard label="Avg Lead Score" value="68/100" icon={Target} />
            <KPICard label="Avg LTV" value="$8,740" icon={DollarSign} />
          </div>

          <Card>
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="crm-patient-table">
                <thead>
                  <tr className="border-b">
                    {["Patient", "Stage", "Provider", "LTV", "Lead Score", "Last Visit", "Next Appt", "Source"].map(h => (
                      <th key={h} className="text-left px-4 py-3 text-[10px] font-bold tracking-wider uppercase text-muted-foreground whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {CRM_PATIENTS.map((p) => (
                    <tr key={p.id} className="border-b hover-elevate cursor-pointer" onClick={() => setSelectedPatient(p)} data-testid={`crm-row-${p.id}`}>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <Avatar className="h-8 w-8">
                            <AvatarFallback style={{ background: `${stageColors[p.stage]}18`, color: stageColors[p.stage] }} className="text-xs font-bold">{p.avatar}</AvatarFallback>
                          </Avatar>
                          <div>
                            <div className="font-semibold">{p.name}</div>
                            <div className="text-xs text-muted-foreground">{p.email}</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3"><Badge variant="outline" style={{ borderColor: `${stageColors[p.stage]}40`, color: stageColors[p.stage] }}>{p.stage}</Badge></td>
                      <td className="px-4 py-3 text-muted-foreground">{p.provider}</td>
                      <td className="px-4 py-3 font-bold font-mono" style={{ color: p.ltv > 0 ? "#00E6B4" : undefined }}>${p.ltv.toLocaleString()}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <div className="w-10 h-1.5 rounded-full bg-muted overflow-hidden">
                            <div className="h-full rounded-full" style={{ width: `${p.score}%`, background: p.score > 80 ? "#00E6B4" : p.score > 60 ? "#F59E0B" : "#64748B" }} />
                          </div>
                          <span className="text-xs font-bold">{p.score}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-xs text-muted-foreground whitespace-nowrap">{p.lastVisit}</td>
                      <td className="px-4 py-3 text-xs font-semibold whitespace-nowrap" style={{ color: p.nextAppt === "Pending" ? "#F59E0B" : "#00E6B4" }}>{p.nextAppt}</td>
                      <td className="px-4 py-3 text-xs text-muted-foreground">{p.source}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <Card>
            <CardContent className="p-4">
              <div className="text-[11px] font-bold tracking-wider uppercase text-muted-foreground mb-3">AI-Generated Tasks</div>
              <div className="space-y-2">
                {TASKS_CRM.map(t => (
                  <div key={t.id} className="flex items-center justify-between gap-4 p-3 rounded-lg border" data-testid={`task-${t.id}`}>
                    <div className="flex items-center gap-3 min-w-0">
                      {t.aiGen && <Sparkles className="h-3.5 w-3.5 text-sky-500 flex-shrink-0" />}
                      <div className="min-w-0">
                        <div className="text-sm font-semibold truncate">{t.task}</div>
                        <div className="text-xs text-muted-foreground">{t.assignee} &middot; Due {t.due}</div>
                      </div>
                    </div>
                    <Badge variant="outline" style={{ borderColor: `${priorityColors[t.priority]}40`, color: priorityColors[t.priority] }}>{t.priority}</Badge>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ═══ ANALYTICS TAB ═══ */}
        <TabsContent value="analytics" className="space-y-5 mt-4">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <div>
              <h2 className="text-xl font-extrabold">Business Intelligence</h2>
              <p className="text-sm text-muted-foreground">Practice performance analytics and benchmarking</p>
            </div>
            <Tabs value={biTab} onValueChange={setBiTab}>
              <TabsList>
                <TabsTrigger value="overview">Overview</TabsTrigger>
                <TabsTrigger value="providers">Providers</TabsTrigger>
                <TabsTrigger value="production">Production</TabsTrigger>
                <TabsTrigger value="marketing">Marketing</TabsTrigger>
              </TabsList>
            </Tabs>
          </div>

          {biTab === "overview" && (
            <div className="space-y-4">
              <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
                <KPICard label="Avg Revenue / Day" value="$64.8K" change={"\u2191 18% QoQ"} icon={DollarSign} />
                <KPICard label="Procedures / Day" value="47" change="6 implants, 12 ortho" icon={Activity} />
                <KPICard label="New Patients / Mo" value="342" change={"\u2191 23% YoY"} icon={Users} />
                <KPICard label="Referral Rate" value="22%" change="Target: 40%" icon={TrendingUp} />
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <ChartCard title="Practice Performance vs Benchmark">
                  <div className="h-[260px]">
                    <ResponsiveContainer>
                      <RadarChart data={RADAR_DATA} margin={{ top: 10, right: 30, bottom: 10, left: 30 }}>
                        <PolarGrid className="stroke-border" />
                        <PolarAngleAxis dataKey="metric" tick={{ fontSize: 10 }} />
                        <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fontSize: 9 }} />
                        <Radar name="Your Practice" dataKey="current" stroke="#0EA5E9" fill="#0EA5E9" fillOpacity={0.25} strokeWidth={2} />
                        <Radar name="Industry Avg" dataKey="benchmark" stroke="#64748B" fill="#64748B" fillOpacity={0.1} strokeWidth={1} strokeDasharray="4 4" />
                        <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11 }} />
                      </RadarChart>
                    </ResponsiveContainer>
                  </div>
                </ChartCard>

                <ChartCard title="Patient Acquisition Source">
                  <div className="h-[260px]">
                    <ResponsiveContainer>
                      <PieChart>
                        <Pie data={PATIENT_SOURCE} cx="50%" cy="50%" innerRadius="50%" outerRadius="78%" paddingAngle={2} dataKey="value" stroke="none">
                          {PATIENT_SOURCE.map((s, i) => <Cell key={i} fill={s.color} />)}
                        </Pie>
                        <Tooltip content={<CustomTooltip />} />
                        <Legend iconType="circle" iconSize={7} wrapperStyle={{ fontSize: 10, fontWeight: 600 }} />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                </ChartCard>
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <ChartCard title="Patient Volume by Hour">
                  <div className="h-[220px]">
                    <ResponsiveContainer>
                      <BarChart data={HOURLY_PATIENTS} margin={{ top: 5, right: 5, bottom: 0, left: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                        <XAxis dataKey="hour" tick={{ fontSize: 9 }} axisLine={false} tickLine={false} />
                        <YAxis tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                        <Tooltip content={<CustomTooltip />} />
                        <Bar dataKey="count" name="Patients" radius={[4,4,0,0]}>
                          {HOURLY_PATIENTS.map((h, i) => <Cell key={i} fill={h.count > 18 ? "#00E6B4" : h.count > 12 ? "#0EA5E9" : "#64748B"} />)}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </ChartCard>

                <ChartCard title="Daily Production vs Goal">
                  <div className="h-[220px]">
                    <ResponsiveContainer>
                      <ComposedChart data={DAILY_PRODUCTION} margin={{ top: 5, right: 5, bottom: 0, left: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                        <XAxis dataKey="day" tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                        <YAxis tick={{ fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={(v) => `$${v/1000}K`} />
                        <Tooltip content={<CustomTooltip />} />
                        <Bar dataKey="actual" name="Actual" fill="#00E6B4" radius={[3,3,0,0]} fillOpacity={0.7} />
                        <Line type="monotone" dataKey="goal" name="Goal" stroke="#EF4444" strokeWidth={2} strokeDasharray="6 4" dot={false} />
                      </ComposedChart>
                    </ResponsiveContainer>
                  </div>
                </ChartCard>
              </div>
            </div>
          )}

          {biTab === "providers" && (
            <div className="space-y-4">
              <Card>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm" data-testid="provider-table">
                    <thead>
                      <tr className="border-b">
                        {["Provider", "Specialty", "Production", "Collections", "Col. Rate", "Acceptance", "Patients"].map(h => (
                          <th key={h} className={`px-4 py-3 text-[10px] font-bold tracking-wider uppercase text-muted-foreground whitespace-nowrap ${h !== "Provider" && h !== "Specialty" ? "text-right" : "text-left"}`}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {PROVIDER_PERFORMANCE.map((p, i) => (
                        <tr key={i} className="border-b" data-testid={`provider-row-${i}`}>
                          <td className="px-4 py-3 font-bold">{p.name}</td>
                          <td className="px-4 py-3"><Badge variant="outline" style={{ borderColor: `${p.specialty === "Implants" ? "#00E6B4" : p.specialty === "Ortho" ? "#6366F1" : p.specialty === "Perio" ? "#F59E0B" : "#EF4444"}40`, color: p.specialty === "Implants" ? "#00E6B4" : p.specialty === "Ortho" ? "#6366F1" : p.specialty === "Perio" ? "#F59E0B" : "#EF4444" }}>{p.specialty}</Badge></td>
                          <td className="px-4 py-3 text-right font-mono font-bold">{fmt(p.production)}</td>
                          <td className="px-4 py-3 text-right font-mono">{fmt(p.collections)}</td>
                          <td className="px-4 py-3 text-right font-bold" style={{ color: (p.collections / p.production) > 0.95 ? "#00E6B4" : "#F59E0B" }}>{Math.round((p.collections / p.production) * 100)}%</td>
                          <td className="px-4 py-3 text-right">
                            <div className="flex items-center justify-end gap-2">
                              <div className="w-10 h-1.5 rounded-full bg-muted overflow-hidden">
                                <div className="h-full rounded-full" style={{ width: `${p.acceptance}%`, background: p.acceptance > 75 ? "#00E6B4" : "#F59E0B" }} />
                              </div>
                              <span className="text-xs font-bold">{p.acceptance}%</span>
                            </div>
                          </td>
                          <td className="px-4 py-3 text-right font-semibold">{p.patients}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>

              <ChartCard title="Provider Production Comparison">
                <div className="h-[280px]">
                  <ResponsiveContainer>
                    <BarChart data={PROVIDER_PERFORMANCE} layout="vertical" margin={{ top: 5, right: 20, bottom: 5, left: 60 }}>
                      <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                      <XAxis type="number" tick={{ fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={(v) => fmt(v)} />
                      <YAxis type="category" dataKey="name" tick={{ fontSize: 12, fontWeight: 600 }} axisLine={false} tickLine={false} width={70} />
                      <Tooltip content={<CustomTooltip />} />
                      <Bar dataKey="production" name="Production" fill="#00E6B4" radius={[0,4,4,0]} barSize={16} />
                      <Bar dataKey="collections" name="Collections" fill="#0EA5E9" radius={[0,4,4,0]} barSize={16} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </ChartCard>
            </div>
          )}

          {biTab === "production" && (
            <div className="space-y-4">
              <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
                <KPICard label="MTD Production" value="$1.08M" change="83% of goal" icon={TrendingUp} />
                <KPICard label="Procedures Today" value="47" change="6 implants, 12 ortho" icon={Activity} />
                <KPICard label="Chair Utilization" value="87%" change="Target: 92%" icon={Target} />
                <KPICard label="Avg Production/Chair" value="$6,580" change="+14% QoQ" icon={DollarSign} />
              </div>
              <ChartCard title="Daily Production - February 2026">
                <div className="h-[300px]">
                  <ResponsiveContainer>
                    <ComposedChart data={DAILY_PRODUCTION} margin={{ top: 10, right: 10, bottom: 5, left: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                      <XAxis dataKey="day" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={(v) => `$${v / 1000}K`} />
                      <Tooltip content={<CustomTooltip />} />
                      <Bar dataKey="actual" name="Actual" radius={[4, 4, 0, 0]}>
                        {DAILY_PRODUCTION.map((d, i) => <Cell key={i} fill={d.actual >= d.goal ? "#00E6B4" : d.actual >= d.goal * 0.8 ? "#F59E0B" : "#EF4444"} fillOpacity={0.75} />)}
                      </Bar>
                      <Line type="monotone" dataKey="goal" name="Daily Goal" stroke="#EF4444" strokeWidth={2} strokeDasharray="8 4" dot={false} />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              </ChartCard>
            </div>
          )}

          {biTab === "marketing" && (
            <div className="space-y-4">
              <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
                <KPICard label="Marketing Spend" value="$42K" change="$287 CAC" icon={DollarSign} />
                <KPICard label="Leads Generated" value="234" change="+18% MoM" icon={Target} />
                <KPICard label="Lead-to-Patient" value="23%" icon={TrendingUp} />
                <KPICard label="ROAS" value="8.4x" change="+2.1x from AI optim." icon={DollarSign} />
              </div>
              <div className="grid gap-4 lg:grid-cols-2">
                <ChartCard title="Patient Acquisition Source">
                  <div className="h-[260px]">
                    <ResponsiveContainer>
                      <PieChart>
                        <Pie data={PATIENT_SOURCE} cx="50%" cy="50%" innerRadius="45%" outerRadius="80%" paddingAngle={3} dataKey="value" stroke="none">
                          {PATIENT_SOURCE.map((s, i) => <Cell key={i} fill={s.color} />)}
                        </Pie>
                        <Tooltip content={<CustomTooltip />} />
                        <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11, fontWeight: 600 }} />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                </ChartCard>
                <ChartCard title="Conversion Funnel">
                  <div className="flex flex-col gap-2 h-[260px] justify-center">
                    {FUNNEL_DATA.map((f, i) => {
                      const w = (f.value / FUNNEL_DATA[0].value) * 100;
                      return (
                        <div key={i} className="flex items-center gap-3">
                          <div className="w-[90px] text-[11px] text-muted-foreground text-right flex-shrink-0">{f.name}</div>
                          <div className="flex-1 h-6 rounded overflow-hidden" style={{ background: `${f.fill}12` }}>
                            <div className="h-full rounded flex items-center pl-2" style={{ width: `${w}%`, background: f.fill }}>
                              <span className="text-[10px] font-extrabold text-white">{f.value.toLocaleString()}</span>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </ChartCard>
              </div>
            </div>
          )}
        </TabsContent>

        {/* ═══ PIPELINE TAB ═══ */}
        <TabsContent value="pipeline" className="space-y-5 mt-4">
          <div>
            <h2 className="text-xl font-extrabold">Opportunity Pipeline</h2>
            <p className="text-sm text-muted-foreground">$4.78M in active pipeline across 7 stages</p>
          </div>

          <div className="flex gap-2 overflow-x-auto pb-1">
            {PIPELINE_STAGES.map(s => (
              <Card key={s.stage} className="min-w-[150px] flex-shrink-0" data-testid={`pipeline-stage-${s.stage.toLowerCase().replace(/\s+/g, "-")}`}>
                <CardContent className="p-3">
                  <div className="flex items-center gap-2 mb-1">
                    <div className="w-2 h-2 rounded-full" style={{ background: s.color }} />
                    <div className="text-[10px] font-bold tracking-wider uppercase text-muted-foreground">{s.stage}</div>
                  </div>
                  <div className="text-xl font-extrabold">{s.count}</div>
                  <div className="text-xs font-bold" style={{ color: s.color }}>{fmt(s.value)}</div>
                </CardContent>
              </Card>
            ))}
          </div>

          <div className="flex gap-3 overflow-x-auto pb-3">
            {["New Lead", "Consultation Booked", "Treatment Plan Sent", "Plan Accepted", "In Treatment"].map(stage => {
              const stagePatients = CRM_PATIENTS.filter(p => p.stage === stage);
              return (
                <div key={stage} className="min-w-[260px] flex-shrink-0" data-testid={`kanban-${stage.toLowerCase().replace(/\s+/g, "-")}`}>
                  <Card className="overflow-hidden">
                    <div className="px-3 py-2.5 border-b flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full" style={{ background: stageColors[stage] }} />
                        <span className="text-xs font-bold">{stage}</span>
                      </div>
                      <span className="text-[11px] text-muted-foreground font-bold">{stagePatients.length}</span>
                    </div>
                    <CardContent className="p-2 space-y-2 min-h-[120px]">
                      {stagePatients.map(p => (
                        <div key={p.id} className="rounded-lg border p-2.5 cursor-pointer hover-elevate" onClick={() => setSelectedPatient(p)}>
                          <div className="flex items-center gap-2 mb-1.5">
                            <Avatar className="h-7 w-7">
                              <AvatarFallback style={{ background: `${stageColors[p.stage]}18`, color: stageColors[p.stage] }} className="text-[10px] font-bold">{p.avatar}</AvatarFallback>
                            </Avatar>
                            <span className="text-xs font-bold">{p.name}</span>
                          </div>
                          <div className="text-[11px] text-muted-foreground mb-1.5 line-clamp-1">{p.treatmentPlan}</div>
                          <div className="flex justify-between items-center">
                            <span className="text-xs font-extrabold" style={{ color: p.ltv > 0 ? "#00E6B4" : undefined }}>${p.ltv.toLocaleString()}</span>
                            <span className="text-[10px] text-muted-foreground">{p.provider}</span>
                          </div>
                        </div>
                      ))}
                      {stagePatients.length === 0 && <div className="p-4 text-center text-xs text-muted-foreground">No patients</div>}
                    </CardContent>
                  </Card>
                </div>
              );
            })}
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <ChartCard title="Pipeline Value by Stage">
              <div className="h-[240px]">
                <ResponsiveContainer>
                  <BarChart data={PIPELINE_STAGES} margin={{ top: 5, right: 5, bottom: 40, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                    <XAxis dataKey="stage" tick={{ fontSize: 9 }} axisLine={false} tickLine={false} interval={0} angle={-20} textAnchor="end" height={50} />
                    <YAxis tick={{ fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={(v) => fmt(v)} />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar dataKey="value" name="Value" radius={[6, 6, 0, 0]}>
                      {PIPELINE_STAGES.map((s, i) => <Cell key={i} fill={s.color} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </ChartCard>
            <ChartCard title="Leads by Stage Count">
              <div className="h-[240px]">
                <ResponsiveContainer>
                  <BarChart data={PIPELINE_STAGES} layout="vertical" margin={{ top: 5, right: 20, bottom: 5, left: 80 }}>
                    <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                    <XAxis type="number" tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                    <YAxis type="category" dataKey="stage" tick={{ fontSize: 10 }} axisLine={false} tickLine={false} width={90} />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar dataKey="count" name="Contacts" radius={[0, 6, 6, 0]} barSize={14}>
                      {PIPELINE_STAGES.map((s, i) => <Cell key={i} fill={s.color} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </ChartCard>
          </div>
        </TabsContent>

        {/* ═══ GROWTH ENGINE TAB ═══ */}
        <TabsContent value="growth" className="space-y-5 mt-4">
          <Card className="border-emerald-500/20 bg-emerald-500/[0.02]">
            <CardContent className="p-6">
              <div className="text-[10px] font-bold tracking-widest uppercase text-emerald-500 mb-1">acquisition.com Framework</div>
              <h2 className="text-xl font-extrabold mb-1">$100M Dental Empire Playbook</h2>
              <p className="text-sm text-muted-foreground">Grand Slam Offer x Value Ladder x Acquisition Roll-Up - all AI-orchestrated.</p>
            </CardContent>
          </Card>

          <div className="grid gap-3 grid-cols-2 lg:grid-cols-6">
            {[
              { l: "Patient LTV", v: "$8,740", t: "$12K target", pct: 73, c: "#00E6B4" },
              { l: "CAC", v: "$287", t: "$150 target", pct: 52, c: "#F59E0B" },
              { l: "LTV:CAC", v: "30.5x", t: "80x target", pct: 38, c: "#6366F1" },
              { l: "Churn", v: "8.2%", t: "5% target", pct: 61, c: "#EF4444" },
              { l: "Ascension", v: "34%", t: "60% target", pct: 57, c: "#0EA5E9" },
              { l: "Referral Rate", v: "22%", t: "40% target", pct: 55, c: "#10B981" },
            ].map((m, i) => (
              <Card key={i} data-testid={`growth-metric-${i}`}>
                <CardContent className="p-4 text-center">
                  <div className="text-2xl font-black mb-0.5" style={{ color: m.c }}>{m.v}</div>
                  <div className="text-[11px] font-bold mb-1">{m.l}</div>
                  <div className="h-1.5 bg-muted rounded-full overflow-hidden mb-1">
                    <div className="h-full rounded-full" style={{ width: `${m.pct}%`, background: m.c }} />
                  </div>
                  <div className="text-[10px] text-muted-foreground">{m.t}</div>
                </CardContent>
              </Card>
            ))}
          </div>

          <Card className="border-emerald-500/20">
            <CardContent className="p-5">
              <div className="text-xs font-bold tracking-wider uppercase text-emerald-500 mb-4">Grand Slam Offer - Value Equation</div>
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 text-center">
                {[
                  { l: "Dream Outcome", v: "9.2", d: "Perfect smile, zero pain", c: "#00E6B4", op: "x" },
                  { l: "Likelihood of Success", v: "8.5", d: "3D preview, guarantees", c: "#6366F1", op: "/" },
                  { l: "Time Delay", v: "2.1", d: "Same-day teeth option", c: "#F59E0B", op: "/" },
                  { l: "Effort & Sacrifice", v: "1.8", d: "Sedation + financing", c: "#EF4444", op: "=" },
                ].map((v, i) => (
                  <div key={i}>
                    <div className="text-3xl font-black" style={{ color: v.c }}>{v.v}</div>
                    <div className="text-xs font-bold mb-0.5">{v.l}</div>
                    <div className="text-[10px] text-muted-foreground">{v.d}</div>
                  </div>
                ))}
              </div>
              <div className="text-center mt-5 p-3 bg-emerald-500/5 rounded-lg">
                <span className="font-black text-emerald-500">Offer Score: 21.8</span>
                <span className="text-muted-foreground ml-2 text-sm">&#8594; "Free CBCT + Consult + 3D Smile Preview + Lifetime Warranty"</span>
              </div>
            </CardContent>
          </Card>

          <div>
            <h3 className="text-sm font-bold mb-3">Growth Levers</h3>
            <div className="space-y-2">
              {[
                { lever: "Grand Slam Offer", status: "active", impact: "10x", desc: "Free CBCT + consultation + 3D preview. Zero-risk entry point.", progress: 78, color: "#00E6B4" },
                { lever: "Value Ladder", status: "active", impact: "3x", desc: "Cleaning > Whitening > Invisalign > Implants > Full Mouth Rehab", progress: 65, color: "#6366F1" },
                { lever: "Practice Acquisitions", status: "scouting", impact: "10x", desc: "Roll-up: acquire underperforming practices, inject AI + SOPs", progress: 30, color: "#0EA5E9" },
                { lever: "Referral Engine", status: "building", impact: "3x", desc: "$500 referral bonus + automated post-treatment ask sequence", progress: 38, color: "#F59E0B" },
                { lever: "Paid Acquisition", status: "optimizing", impact: "4x", desc: "Meta + Google + YouTube funnel with AI-optimized creative", progress: 56, color: "#EF4444" },
                { lever: "Lead Magnets", status: "building", impact: "5x", desc: "Free Smile Quiz + Implant Cost Calculator + Before/After Gallery", progress: 42, color: "#10B981" },
              ].map((g, i) => (
                <Card key={i} data-testid={`growth-lever-${i}`}>
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between gap-4 flex-wrap mb-2">
                      <div className="flex items-center gap-3">
                        <span className="font-bold">{g.lever}</span>
                        <Badge variant="outline" style={{ borderColor: `${g.status === "active" ? "#00E6B4" : g.status === "optimizing" ? "#6366F1" : "#F59E0B"}40`, color: g.status === "active" ? "#00E6B4" : g.status === "optimizing" ? "#6366F1" : "#F59E0B" }}>{g.status}</Badge>
                      </div>
                      <span className="text-xs font-extrabold px-2 py-0.5 rounded" style={{ background: `${g.color}12`, color: g.color }}>{g.impact} impact</span>
                    </div>
                    <p className="text-xs text-muted-foreground mb-2">{g.desc}</p>
                    <div className="flex items-center gap-3">
                      <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
                        <div className="h-full rounded-full transition-all" style={{ width: `${g.progress}%`, background: g.color }} />
                      </div>
                      <span className="text-xs font-bold" style={{ color: g.color }}>{g.progress}%</span>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </TabsContent>
      </Tabs>

      {/* Patient Detail Sheet */}
      <Sheet open={!!selectedPatient} onOpenChange={(open) => !open && setSelectedPatient(null)}>
        <SheetContent className="w-[500px] sm:max-w-[500px] overflow-y-auto" data-testid="patient-detail-sheet">
          {selectedPatient && (
            <>
              <SheetHeader className="pb-4">
                <div className="flex items-center gap-3">
                  <Avatar className="h-12 w-12">
                    <AvatarFallback style={{ background: `${stageColors[selectedPatient.stage]}18`, color: stageColors[selectedPatient.stage] }} className="text-sm font-bold">{selectedPatient.avatar}</AvatarFallback>
                  </Avatar>
                  <div>
                    <SheetTitle className="text-xl">{selectedPatient.name}</SheetTitle>
                    <div className="flex gap-2 mt-1">
                      <Badge variant="outline" style={{ borderColor: `${stageColors[selectedPatient.stage]}40`, color: stageColors[selectedPatient.stage] }}>{selectedPatient.stage}</Badge>
                      <Badge variant="outline" style={{ borderColor: `${statusColors[selectedPatient.status]}40`, color: statusColors[selectedPatient.status] }}>{selectedPatient.status}</Badge>
                    </div>
                  </div>
                </div>
              </SheetHeader>

              <div className="space-y-5 mt-2">
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { l: "Email", v: selectedPatient.email },
                    { l: "Phone", v: selectedPatient.phone },
                    { l: "Provider", v: selectedPatient.provider },
                    { l: "Specialty", v: selectedPatient.specialty },
                    { l: "Source", v: selectedPatient.source },
                    { l: "Lead Score", v: `${selectedPatient.score}/100` },
                  ].map((f, i) => (
                    <Card key={i}>
                      <CardContent className="p-3">
                        <div className="text-[10px] font-semibold tracking-wider uppercase text-muted-foreground mb-0.5">{f.l}</div>
                        <div className="text-sm font-bold">{f.v}</div>
                      </CardContent>
                    </Card>
                  ))}
                </div>

                <Card className="border-emerald-500/20 bg-emerald-500/[0.03]">
                  <CardContent className="p-4">
                    <div className="flex justify-between items-center mb-2">
                      <span className="text-xs font-bold tracking-wider uppercase text-emerald-500">Lifetime Value</span>
                      <span className="text-2xl font-black text-emerald-500">${selectedPatient.ltv.toLocaleString()}</span>
                    </div>
                    <div className="h-1.5 bg-emerald-500/10 rounded-full overflow-hidden">
                      <div className="h-full bg-emerald-500 rounded-full" style={{ width: `${Math.min((selectedPatient.ltv / 25000) * 100, 100)}%` }} />
                    </div>
                    <div className="text-[10px] text-muted-foreground mt-1 text-right">Target LTV: $25,000</div>
                  </CardContent>
                </Card>

                <div>
                  <div className="text-xs font-bold tracking-wider uppercase text-muted-foreground mb-2">Treatment Plan</div>
                  <Card><CardContent className="p-3 text-sm font-semibold">{selectedPatient.treatmentPlan}</CardContent></Card>
                </div>

                <div>
                  <div className="text-xs font-bold tracking-wider uppercase text-muted-foreground mb-2">AI Notes</div>
                  <Card><CardContent className="p-3 text-sm text-muted-foreground leading-relaxed">{selectedPatient.notes}</CardContent></Card>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <Card><CardContent className="p-3"><div className="text-[10px] font-semibold tracking-wider uppercase text-muted-foreground mb-0.5">Last Visit</div><div className="text-sm font-bold">{selectedPatient.lastVisit}</div></CardContent></Card>
                  <Card><CardContent className="p-3"><div className="text-[10px] font-semibold tracking-wider uppercase text-muted-foreground mb-0.5">Next Appointment</div><div className="text-sm font-bold" style={{ color: selectedPatient.nextAppt === "Pending" ? "#F59E0B" : "#00E6B4" }}>{selectedPatient.nextAppt}</div></CardContent></Card>
                </div>

                <div className="flex gap-2 flex-wrap">
                  {[
                    { icon: Phone, label: "Call" },
                    { icon: Mail, label: "Email" },
                    { icon: MessageSquare, label: "SMS" },
                    { icon: CalendarDays, label: "Schedule" },
                    { icon: FileText, label: "Treatment Plan" },
                    { icon: CreditCard, label: "Payment" },
                  ].map((a, i) => (
                    <Button key={i} variant="outline" size="sm" data-testid={`action-${a.label.toLowerCase()}`}>
                      <a.icon className="mr-1.5 h-3.5 w-3.5" />{a.label}
                    </Button>
                  ))}
                </div>
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}

function UserPlus(props: any) {
  return <Users {...props} />;
}
