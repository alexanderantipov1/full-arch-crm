import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  BarChart3, TrendingUp, TrendingDown, DollarSign, Users, Calendar,
  FileText, Download, PieChart, AlertTriangle, Target, Lightbulb,
  Activity, Bot, Brain, Award, CheckCircle, ArrowUpRight, ArrowDownRight,
} from "lucide-react";
import { exportToCSV, exportToPDF } from "@/lib/export";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { format, subDays, subMonths, startOfMonth, endOfMonth } from "date-fns";
import type { Patient, BillingClaim, TreatmentPlan, PaymentPosting, Appointment } from "@shared/schema";

// ─── Shared format helpers ───────────────────────────────────────────────────
const fmt$ = (n: number) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n);
const fmtPct = (n: number) => `${n.toFixed(1)}%`;

// ─── Revenue Cycle Tab ────────────────────────────────────────────────────────
interface RevenueAnalytics {
  summary: { totalBilled: number; totalCollected: number; totalPending: number; collectionRate: number; denialRate: number; avgDaysToPayment: number };
  claims: { total: number; paid: number; denied: number; pending: number };
  priorAuthorizations: { total: number; approved: number; denied: number; pending: number; approvalRate: number };
  agingBuckets: { current: number; days31to60: number; days61to90: number; over90: number };
  trends: { monthlyCollections: number[]; monthlyDenials: number[]; months: string[] };
}

function RevenueCycleTab() {
  const { data: analytics, isLoading } = useQuery<RevenueAnalytics>({ queryKey: ["/api/analytics/revenue-cycle"] });
  if (isLoading) return <div className="space-y-3">{[...Array(6)].map((_, i) => <Skeleton key={i} className="h-24" />)}</div>;
  const a = analytics;
  const agingTotal = a ? (a.agingBuckets.current + a.agingBuckets.days31to60 + a.agingBuckets.days61to90 + a.agingBuckets.over90) || 1 : 1;

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {[
          { label: "Total Billed",     value: a ? fmt$(a.summary.totalBilled)     : "—", color: "text-foreground" },
          { label: "Total Collected",  value: a ? fmt$(a.summary.totalCollected)  : "—", color: "text-emerald-600" },
          { label: "Pending",          value: a ? fmt$(a.summary.totalPending)    : "—", color: "text-amber-600"   },
          { label: "Collection Rate",  value: a ? fmtPct(a.summary.collectionRate): "—", color: "text-emerald-600" },
          { label: "Denial Rate",      value: a ? fmtPct(a.summary.denialRate)   : "—", color: a && a.summary.denialRate > 5 ? "text-red-600" : "text-emerald-600" },
          { label: "Avg Days to Pay",  value: a ? `${a.summary.avgDaysToPayment}d`: "—", color: "text-primary"     },
        ].map(k => (
          <Card key={k.label}>
            <CardContent className="pt-3 pb-3">
              <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-0.5">{k.label}</div>
              <div className={`text-lg font-bold font-mono ${k.color}`}>{k.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">Claims Breakdown</CardTitle></CardHeader>
          <CardContent className="pt-0 space-y-2">
            {a && [
              { label: "Paid / Approved",  val: a.claims.paid,    pct: a.claims.total ? (a.claims.paid / a.claims.total) * 100 : 0,    color: "bg-emerald-500" },
              { label: "Denied",           val: a.claims.denied,  pct: a.claims.total ? (a.claims.denied / a.claims.total) * 100 : 0,  color: "bg-red-500"     },
              { label: "Pending Review",   val: a.claims.pending, pct: a.claims.total ? (a.claims.pending / a.claims.total) * 100 : 0, color: "bg-amber-500"   },
            ].map(item => (
              <div key={item.label}>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-muted-foreground">{item.label}</span>
                  <span className="font-semibold">{item.val} ({fmtPct(item.pct)})</span>
                </div>
                <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                  <div className={`h-full rounded-full ${item.color}`} style={{ width: `${item.pct}%` }} />
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">A/R Aging</CardTitle></CardHeader>
          <CardContent className="pt-0 space-y-2">
            {a && [
              { label: "Current (0–30 days)", val: a.agingBuckets.current,    color: "bg-emerald-500" },
              { label: "31–60 days",          val: a.agingBuckets.days31to60, color: "bg-blue-500"    },
              { label: "61–90 days",          val: a.agingBuckets.days61to90, color: "bg-amber-500"   },
              { label: "Over 90 days",        val: a.agingBuckets.over90,     color: "bg-red-500"     },
            ].map(item => (
              <div key={item.label}>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-muted-foreground">{item.label}</span>
                  <span className="font-semibold">{fmt$(item.val)}</span>
                </div>
                <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                  <div className={`h-full rounded-full ${item.color}`} style={{ width: `${agingTotal > 0 ? (item.val / agingTotal) * 100 : 0}%` }} />
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">Prior Authorization Success</CardTitle></CardHeader>
          <CardContent className="pt-0">
            {a && (
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <div className="text-3xl font-bold text-emerald-600 font-mono">{fmtPct(a.priorAuthorizations.approvalRate)}</div>
                  <div className="text-xs text-muted-foreground">Approval Rate<br />{a.priorAuthorizations.total} total requests</div>
                </div>
                <div className="grid grid-cols-3 gap-2 text-center text-xs">
                  <div className="rounded-lg bg-emerald-500/10 p-2"><div className="font-bold text-emerald-600">{a.priorAuthorizations.approved}</div><div className="text-muted-foreground">Approved</div></div>
                  <div className="rounded-lg bg-amber-500/10 p-2"><div className="font-bold text-amber-600">{a.priorAuthorizations.pending}</div><div className="text-muted-foreground">Pending</div></div>
                  <div className="rounded-lg bg-red-500/10 p-2"><div className="font-bold text-red-600">{a.priorAuthorizations.denied}</div><div className="text-muted-foreground">Denied</div></div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">Monthly Collection Trend</CardTitle></CardHeader>
          <CardContent className="pt-0">
            {a && a.trends && (
              <div className="space-y-1.5">
                {a.trends.months.map((month, i) => {
                  const maxVal = Math.max(...a.trends.monthlyCollections, 1);
                  return (
                    <div key={month} className="flex items-center gap-2">
                      <div className="w-8 text-[10px] text-muted-foreground">{month}</div>
                      <div className="flex-1 h-5 bg-muted rounded overflow-hidden">
                        <div className="h-full bg-primary/70 rounded flex items-center pl-2"
                          style={{ width: `${(a.trends.monthlyCollections[i] / maxVal) * 100}%` }}>
                          <span className="text-[9px] text-white font-semibold whitespace-nowrap">{fmt$(a.trends.monthlyCollections[i])}</span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

// ─── Reports Tab ──────────────────────────────────────────────────────────────
function ReportsTab({ onExport }: { onExport?: () => void }) {
  const [dateRange, setDateRange] = useState("30");
  const { data: patients = [] } = useQuery<Patient[]>({ queryKey: ["/api/patients"] });
  const { data: claims = [] } = useQuery<BillingClaim[]>({ queryKey: ["/api/billing/claims"] });
  const { data: treatmentPlans = [] } = useQuery<TreatmentPlan[]>({ queryKey: ["/api/treatment-plans"] });
  const { data: payments = [] } = useQuery<PaymentPosting[]>({ queryKey: ["/api/era/postings"] });
  const { data: appointments = [] } = useQuery<Appointment[]>({ queryKey: ["/api/appointments"] });

  const days = parseInt(dateRange);
  const startDate = subDays(new Date(), days);
  const prevStartDate = subDays(startDate, days);

  const periodPayments = payments.filter(p => new Date(p.paymentDate) >= startDate);
  const prevPeriodPayments = payments.filter(p => { const d = new Date(p.paymentDate); return d >= prevStartDate && d < startDate; });
  const totalRevenue = periodPayments.reduce((s, p) => s + parseFloat(p.paymentAmount || "0"), 0);
  const prevRevenue = prevPeriodPayments.reduce((s, p) => s + parseFloat(p.paymentAmount || "0"), 0);
  const revenueChange = prevRevenue > 0 ? ((totalRevenue - prevRevenue) / prevRevenue) * 100 : 0;

  const periodClaims = claims.filter(c => new Date(c.createdAt) >= startDate);
  const approvedClaims = periodClaims.filter(c => c.claimStatus === "paid");
  const deniedClaims = periodClaims.filter(c => c.claimStatus === "denied");
  const approvalRate = periodClaims.length > 0 ? (approvedClaims.length / periodClaims.length) * 100 : 0;

  const newPatients = patients.filter(p => new Date(p.createdAt) >= startDate);
  const prevNewPatients = patients.filter(p => { const d = new Date(p.createdAt); return d >= prevStartDate && d < startDate; });
  const patientGrowth = prevNewPatients.length > 0 ? ((newPatients.length - prevNewPatients.length) / prevNewPatients.length) * 100 : 0;

  const periodAppointments = appointments.filter(a => new Date(a.startTime) >= startDate);
  const completedAppts = periodAppointments.filter(a => a.status === "completed");
  const noShowAppts = periodAppointments.filter(a => a.status === "no-show");
  const showRate = periodAppointments.length > 0 ? (completedAppts.length / periodAppointments.length) * 100 : 0;

  const monthlyData = (() => {
    const months = [];
    for (let i = 5; i >= 0; i--) {
      const ms = startOfMonth(subMonths(new Date(), i));
      const me = endOfMonth(subMonths(new Date(), i));
      const mp = payments.filter(p => { const d = new Date(p.paymentDate); return d >= ms && d <= me; });
      months.push({ month: format(ms, "MMM"), revenue: mp.reduce((s, p) => s + parseFloat(p.paymentAmount || "0"), 0) });
    }
    return months;
  })();
  const maxRev = Math.max(...monthlyData.map(m => m.revenue), 1);

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Select value={dateRange} onValueChange={setDateRange}>
          <SelectTrigger className="w-36 h-8 text-xs" data-testid="filter-date-range">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="7">Last 7 days</SelectItem>
            <SelectItem value="30">Last 30 days</SelectItem>
            <SelectItem value="90">Last 90 days</SelectItem>
            <SelectItem value="180">Last 6 months</SelectItem>
          </SelectContent>
        </Select>
        <Button size="sm" variant="outline" className="h-8 gap-1.5 text-xs ml-auto" onClick={onExport} data-testid="button-reports-export"><Download className="h-3.5 w-3.5" />Export CSV</Button>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Revenue", value: fmt$(totalRevenue), change: revenueChange, icon: DollarSign, color: "text-emerald-600" },
          { label: "New Patients", value: newPatients.length, change: patientGrowth, icon: Users, color: "text-blue-600" },
          { label: "Approval Rate", value: `${approvalRate.toFixed(0)}%`, change: null, icon: CheckCircle, color: "text-primary" },
          { label: "Show Rate", value: `${showRate.toFixed(0)}%`, change: null, icon: Calendar, color: "text-purple-600" },
        ].map(k => (
          <Card key={k.label}>
            <CardContent className="pt-3 pb-3">
              <div className="flex items-center gap-1.5 mb-1">
                <k.icon className={`h-3.5 w-3.5 ${k.color}`} />
                <span className="text-[10px] text-muted-foreground uppercase tracking-wider">{k.label}</span>
              </div>
              <div className={`text-xl font-bold font-mono ${k.color}`}>{String(k.value)}</div>
              {k.change !== null && k.change !== undefined && (
                <div className={`text-[10px] flex items-center gap-0.5 ${k.change >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                  {k.change >= 0 ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
                  {Math.abs(k.change).toFixed(1)}% vs prev period
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">6-Month Revenue Trend</CardTitle></CardHeader>
          <CardContent className="pt-0 space-y-1.5">
            {monthlyData.map(m => (
              <div key={m.month} className="flex items-center gap-2">
                <div className="w-8 text-[10px] text-muted-foreground">{m.month}</div>
                <div className="flex-1 h-5 bg-muted rounded overflow-hidden">
                  <div className="h-full bg-primary/70 rounded flex items-center pl-2"
                    style={{ width: `${(m.revenue / maxRev) * 100}%` }}>
                    {m.revenue > 0 && <span className="text-[9px] text-white font-semibold">{fmt$(m.revenue)}</span>}
                  </div>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">Claims Summary ({periodClaims.length} claims)</CardTitle></CardHeader>
          <CardContent className="pt-0 space-y-2">
            {[
              { label: "Approved / Paid", count: approvedClaims.length, color: "bg-emerald-500", pct: periodClaims.length ? (approvedClaims.length/periodClaims.length)*100 : 0 },
              { label: "Denied", count: deniedClaims.length, color: "bg-red-500", pct: periodClaims.length ? (deniedClaims.length/periodClaims.length)*100 : 0 },
              { label: "Pending", count: periodClaims.filter(c=>c.claimStatus==="submitted"||c.claimStatus==="pending").length, color: "bg-amber-500", pct: 0 },
            ].map(item => (
              <div key={item.label}>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-muted-foreground">{item.label}</span>
                  <span className="font-semibold">{item.count}</span>
                </div>
                <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                  <div className={`h-full rounded-full ${item.color}`} style={{ width: `${item.pct || (item.count ? 50 : 0)}%` }} />
                </div>
              </div>
            ))}
            <div className="grid grid-cols-2 gap-2 mt-3 pt-3 border-t text-xs">
              <div><div className="text-muted-foreground">No-shows</div><div className="font-semibold">{noShowAppts.length}</div></div>
              <div><div className="text-muted-foreground">Completed Appts</div><div className="font-semibold">{completedAppts.length}</div></div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

// ─── Business Intelligence Tab ────────────────────────────────────────────────
const aiValueItems = [
  { label: "AI Diagnostics", value: "$8,400" }, { label: "AI Phone Agent", value: "$18,400" },
  { label: "Claims Engine", value: "$6,200" }, { label: "Cross-Coding", value: "$28,400" },
  { label: "Denial Appeals", value: "$34,200" }, { label: "Case Acceptance", value: "$22,800" },
  { label: "Smart Scheduling", value: "$12,400" }, { label: "Voice Pipeline", value: "$4,800" },
  { label: "Fee Optimization", value: "$3,600" }, { label: "Compliance", value: "$2,400" },
];

const benchmarkData = [
  { metric: "Production/Operatory", yours: "$24,800", national: "$18,200", percentile: "94th" },
  { metric: "Collection Rate",      yours: "99.5%",   national: "96.2%",   percentile: "98th" },
  { metric: "Overhead %",           yours: "57.3%",   national: "62.8%",   percentile: "88th" },
  { metric: "New Patients/Mo",      yours: "38",       national: "28",       percentile: "86th" },
  { metric: "Case Acceptance",      yours: "74%",      national: "58%",      percentile: "92nd" },
  { metric: "Days in A/R",          yours: "18.4",     national: "32",       percentile: "95th" },
  { metric: "Hygiene Reappt",       yours: "88%",      national: "82%",      percentile: "78th", flag: true },
  { metric: "Patient Retention",    yours: "91%",      national: "85%",      percentile: "84th" },
];

function BusinessIntelTab() {
  const totalAiValue = aiValueItems.reduce((sum, i) => sum + parseFloat(i.value.replace(/[$,]/g,"")), 0);
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Annualized Revenue", value: "$2.38M", color: "text-emerald-600" },
          { label: "YoY Growth",          value: "+18%",   color: "text-emerald-600" },
          { label: "AI Value Added/Mo",   value: fmt$(totalAiValue), color: "text-primary" },
          { label: "EBITDA Margin",        value: "42.6%",  color: "text-emerald-600" },
        ].map(k => (
          <Card key={k.label}>
            <CardContent className="pt-3 pb-3">
              <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-0.5">{k.label}</div>
              <div className={`text-xl font-bold font-mono ${k.color}`}>{k.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm flex items-center gap-2"><Bot className="h-4 w-4 text-primary" /> AI Value Attribution (Monthly)</CardTitle></CardHeader>
          <CardContent className="pt-0 space-y-1.5">
            {aiValueItems.map(item => (
              <div key={item.label} className="flex justify-between text-xs py-1 border-b last:border-0">
                <span className="text-muted-foreground">{item.label}</span>
                <span className="font-semibold text-emerald-600">{item.value}</span>
              </div>
            ))}
            <div className="flex justify-between text-sm font-bold pt-2 border-t">
              <span>Total AI Revenue Impact</span>
              <span className="text-emerald-600">{fmt$(totalAiValue)}</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm flex items-center gap-2"><Award className="h-4 w-4 text-primary" /> National Benchmarks</CardTitle></CardHeader>
          <CardContent className="pt-0">
            <div className="space-y-1">
              {benchmarkData.map(b => (
                <div key={b.metric} className={`flex items-center gap-2 text-xs p-1.5 rounded ${b.flag ? "bg-amber-500/10" : ""}`}>
                  <span className="flex-1 text-muted-foreground">{b.metric}</span>
                  <span className="font-semibold w-14 text-right">{b.yours}</span>
                  <span className="text-muted-foreground w-14 text-right">{b.national}</span>
                  <Badge className={`text-[9px] px-1 w-10 justify-center ${b.flag ? "bg-amber-100 text-amber-700 border-amber-300 border" : "bg-emerald-100 text-emerald-700 border-emerald-300 border"}`}>{b.percentile}</Badge>
                  {b.flag && <AlertTriangle className="h-3 w-3 text-amber-500 shrink-0" />}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

// ─── Provider Intelligence Tab ─────────────────────────────────────────────────
const providers = [
  { name: "Dr. Chen",  specialty: "Implantologist", production: "$98,400", perDay: "$8,200", patients: "142", caseAccept: "78%", collections: "$96,200", score: "A+", ok: true },
  { name: "Dr. Blake", specialty: "Oral Surgeon",   production: "$87,600", perDay: "$9,250", patients: "108", caseAccept: "74%", collections: "$85,800", score: "A+", ok: true },
  { name: "Dr. Moreau",specialty: "Associate",      production: "$62,400", perDay: "$6,200", patients: "180", caseAccept: "68%", collections: "$61,000", score: "A",  ok: true },
  { name: "Dr. Kim",   specialty: "Associate",      production: "$44,000", perDay: "$5,500", patients: "132", caseAccept: "55%", collections: "$43,200", score: "B",  ok: false },
  { name: "Sarah B.",  specialty: "Hygienist",      production: "$18,400", perDay: "$920",   patients: "164", caseAccept: "—",   collections: "$18,100", score: "A",  ok: true },
  { name: "Omar F.",   specialty: "Hygienist",      production: "$16,800", perDay: "$840",   patients: "148", caseAccept: "—",   collections: "$16,500", score: "B+", ok: true },
];

function ProviderIntelTab() {
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Providers Active", value: "6",      color: "text-primary" },
          { label: "Avg Production/Day", value: "$5,152", color: "text-emerald-600" },
          { label: "Top Case Acceptance", value: "78%",  color: "text-emerald-600" },
          { label: "Providers At Target", value: "5/6",  color: "text-blue-600" },
        ].map(k => (
          <Card key={k.label}>
            <CardContent className="pt-3 pb-3">
              <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-0.5">{k.label}</div>
              <div className={`text-xl font-bold font-mono ${k.color}`}>{k.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader className="pb-2"><CardTitle className="text-sm">Provider Production Scorecard</CardTitle></CardHeader>
        <CardContent className="pt-0 overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b">
                {["Provider","Specialty","Production","Per Day","Patients","Case Accept","Collections","Score"].map(h => (
                  <th key={h} className="py-2 px-3 text-left font-semibold text-muted-foreground whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {providers.map(p => (
                <tr key={p.name} className="border-b hover:bg-muted/30">
                  <td className="py-2 px-3 font-semibold">{p.name}</td>
                  <td className="py-2 px-3 text-muted-foreground">{p.specialty}</td>
                  <td className="py-2 px-3 font-mono">{p.production}</td>
                  <td className="py-2 px-3 font-mono">{p.perDay}</td>
                  <td className="py-2 px-3">{p.patients}</td>
                  <td className="py-2 px-3">{p.caseAccept}</td>
                  <td className="py-2 px-3 font-mono text-emerald-600">{p.collections}</td>
                  <td className="py-2 px-3">
                    <Badge className={`text-[10px] border px-1.5 ${p.ok ? "bg-emerald-100 text-emerald-700 border-emerald-300" : "bg-amber-100 text-amber-700 border-amber-300"}`}>{p.score}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}

// ─── Predictive Analytics Tab ─────────────────────────────────────────────────
interface PredictiveData {
  collections: { predictedNext30Days: number; predictedNext60Days: number; predictedNext90Days: number; confidence: number; trend: "up"|"down"|"stable"; percentChange: number };
  atRiskClaims: { count: number; totalValue: number; claims: { id: number; patientName: string; amount: number; riskScore: number; riskReason: string; daysOutstanding: number }[] };
  benchmarks: { cleanClaimRate: { current: number; industry: number; percentile: number }; denialRate: { current: number; industry: number; percentile: number }; daysToPayment: { current: number; industry: number; percentile: number }; collectionRate: { current: number; industry: number; percentile: number }; appealSuccessRate: { current: number; industry: number; percentile: number } };
  recommendations: { id: string; priority: "high"|"medium"|"low"; title: string; description: string; potentialImpact: string }[];
}

function PredictiveTab() {
  const { data: predictive, isLoading } = useQuery<PredictiveData>({ queryKey: ["/api/analytics/predictive"] });
  if (isLoading) return <div className="space-y-3">{[...Array(4)].map((_, i) => <Skeleton key={i} className="h-32" />)}</div>;
  const p = predictive;

  const priorityColor = (pr: string) => pr === "high" ? "bg-red-100 text-red-700 border-red-300" : pr === "medium" ? "bg-amber-100 text-amber-700 border-amber-300" : "bg-emerald-100 text-emerald-700 border-emerald-300";
  const riskColor = (s: number) => s >= 70 ? "text-red-600" : s >= 40 ? "text-amber-600" : "text-emerald-600";

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {[
          { label: "Predicted 30-Day Collections", value: p ? fmt$(p.collections.predictedNext30Days) : "—", trend: p?.collections.trend },
          { label: "Predicted 60-Day Collections", value: p ? fmt$(p.collections.predictedNext60Days) : "—" },
          { label: "Predicted 90-Day Collections", value: p ? fmt$(p.collections.predictedNext90Days) : "—" },
        ].map(k => (
          <Card key={k.label}>
            <CardContent className="pt-3 pb-3">
              <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-0.5">{k.label}</div>
              <div className="flex items-center gap-2">
                <span className="text-xl font-bold font-mono text-primary">{k.value}</span>
                {k.trend === "up" && <TrendingUp className="h-4 w-4 text-emerald-500" />}
                {k.trend === "down" && <TrendingDown className="h-4 w-4 text-red-500" />}
              </div>
              {p && <div className="text-[10px] text-muted-foreground">Confidence: {p.collections.confidence}%</div>}
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {p && p.atRiskClaims.claims.length > 0 && (
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm flex items-center gap-2"><AlertTriangle className="h-4 w-4 text-amber-500" /> At-Risk Claims ({p.atRiskClaims.count})</CardTitle></CardHeader>
            <CardContent className="pt-0 space-y-2">
              {p.atRiskClaims.claims.slice(0, 5).map((c, i) => (
                <div key={i} className="flex items-center gap-2 p-2 border rounded-lg">
                  <div className="flex-1 text-xs">
                    <div className="font-medium">{c.patientName}</div>
                    <div className="text-muted-foreground">{c.riskReason} · {c.daysOutstanding}d outstanding</div>
                  </div>
                  <div className="text-right">
                    <div className="text-xs font-mono font-semibold">{fmt$(c.amount)}</div>
                    <div className={`text-[10px] font-semibold ${riskColor(c.riskScore)}`}>Risk: {c.riskScore}</div>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        {p && p.recommendations.length > 0 && (
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm flex items-center gap-2"><Lightbulb className="h-4 w-4 text-primary" /> AI Recommendations</CardTitle></CardHeader>
            <CardContent className="pt-0 space-y-2">
              {p.recommendations.map(r => (
                <div key={r.id} className="p-2 border rounded-lg">
                  <div className="flex items-center gap-1.5 mb-0.5">
                    <Badge className={`text-[9px] border px-1 ${priorityColor(r.priority)}`}>{r.priority}</Badge>
                    <span className="font-medium text-xs">{r.title}</span>
                  </div>
                  <div className="text-[10px] text-muted-foreground">{r.description}</div>
                  <div className="text-[10px] text-emerald-600 font-semibold mt-0.5">Impact: {r.potentialImpact}</div>
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">Industry Benchmarks</CardTitle></CardHeader>
          <CardContent className="pt-0">
            {p && Object.entries(p.benchmarks).map(([key, val]) => {
              const label = key.replace(/([A-Z])/g, " $1").replace(/^./, s => s.toUpperCase());
              return (
                <div key={key} className="mb-2">
                  <div className="flex justify-between text-xs mb-0.5">
                    <span className="text-muted-foreground">{label}</span>
                    <span className="font-semibold">{val.current}% <span className="text-muted-foreground font-normal">(industry: {val.industry}%)</span></span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Progress value={val.percentile} className="flex-1 h-1.5" />
                    <span className="text-[10px] text-primary font-semibold">{val.percentile}th</span>
                  </div>
                </div>
              );
            })}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

// ─── Main Hub ─────────────────────────────────────────────────────────────────
export default function AnalyticsHubPage() {
  const [activeTab, setActiveTab] = useState("revenue");

  const { data: analytics } = useQuery<{
    summary: { totalBilled: number; totalCollected: number; totalPending: number; collectionRate: number; denialRate: number; avgDaysToPayment: number };
    claims: { total: number; paid: number; denied: number; pending: number };
    trends: { monthlyCollections: number[]; monthlyDenials: number[]; months: string[] };
  }>({ queryKey: ["/api/analytics/revenue-cycle"] });

  const { data: claims = [] } = useQuery<BillingClaim[]>({ queryKey: ["/api/billing/claims"] });
  const { data: patients = [] } = useQuery<Patient[]>({ queryKey: ["/api/patients"] });
  const { data: payments = [] } = useQuery<PaymentPosting[]>({ queryKey: ["/api/era/postings"] });

  function handleExportCSV() {
    if (activeTab === "reports") {
      const rows = payments.slice().reverse().map((p) => ({
        "Payment Date": new Date(p.paymentDate).toLocaleDateString(),
        "Payer": p.payerName,
        "Amount ($)": p.paymentAmount,
        "Status": p.postingStatus,
      }));
      exportToCSV(rows.length > 0 ? rows : [{ "Payment Date": "—", Payer: "—", "Amount ($)": "—", Status: "—" }], "Reports");
    } else {
      const a = analytics;
      const rows = a
        ? a.trends.months.map((month, i) => ({
            Month: month,
            "Collections ($)": a.trends.monthlyCollections[i] ?? 0,
            "Denials ($)": a.trends.monthlyDenials[i] ?? 0,
          }))
        : [{ Month: "—", "Collections ($)": 0, "Denials ($)": 0 }];
      exportToCSV(rows, "RevenueCycle");
    }
  }

  function handleExportPDF() {
    const a = analytics;
    if (activeTab === "reports") {
      const startDate = subDays(new Date(), 30);
      const periodPayments = payments.filter((p) => new Date(p.paymentDate) >= startDate);
      const totalRevenue = periodPayments.reduce((s, p) => s + parseFloat(p.paymentAmount || "0"), 0);
      const periodClaims = claims.filter((c) => new Date(c.createdAt) >= startDate);
      const approvedClaims = periodClaims.filter((c) => c.claimStatus === "paid");
      const deniedClaims = periodClaims.filter((c) => c.claimStatus === "denied");
      const approvalRate = periodClaims.length > 0 ? (approvedClaims.length / periodClaims.length) * 100 : 0;
      const newPatients = patients.filter((p) => new Date(p.createdAt) >= startDate);
      exportToPDF(
        [
          { type: "title", title: "Practice Reports — Last 30 Days", subtitle: `Generated ${new Date().toLocaleDateString()} — Golden State Dental` },
          {
            type: "kpis",
            heading: "Period Summary",
            items: [
              { label: "Revenue (30d)", value: fmt$(totalRevenue) },
              { label: "New Patients", value: String(newPatients.length) },
              { label: "Claims Filed", value: String(periodClaims.length) },
              { label: "Approval Rate", value: fmtPct(approvalRate) },
              { label: "Approved Claims", value: String(approvedClaims.length) },
              { label: "Denied Claims", value: String(deniedClaims.length) },
            ],
          },
          {
            type: "table",
            heading: "Recent Payments",
            columns: ["Date", "Payer", "Amount"],
            rows: periodPayments.slice(0, 20).map((p) => [
              new Date(p.paymentDate).toLocaleDateString(),
              p.payerName,
              fmt$(parseFloat(p.paymentAmount || "0")),
            ]),
          },
        ],
        "ReportsTab",
      );
    } else {
      exportToPDF(
        [
          { type: "title", title: "Analytics & Revenue Cycle Report", subtitle: `Generated ${new Date().toLocaleDateString()} — Golden State Dental` },
          {
            type: "kpis",
            heading: "Revenue Summary",
            items: [
              { label: "Total Billed", value: a ? fmt$(a.summary.totalBilled) : "—" },
              { label: "Total Collected", value: a ? fmt$(a.summary.totalCollected) : "—" },
              { label: "Pending", value: a ? fmt$(a.summary.totalPending) : "—" },
              { label: "Collection Rate", value: a ? fmtPct(a.summary.collectionRate) : "—" },
              { label: "Denial Rate", value: a ? fmtPct(a.summary.denialRate) : "—" },
              { label: "Avg Days to Pay", value: a ? `${a.summary.avgDaysToPayment}d` : "—" },
            ],
          },
          {
            type: "table",
            heading: "Monthly Trends",
            columns: ["Month", "Collections", "Denials"],
            rows: a
              ? a.trends.months.map((month, i) => [month, fmt$(a.trends.monthlyCollections[i] ?? 0), fmt$(a.trends.monthlyDenials[i] ?? 0)])
              : [["No data", "—", "—"]],
          },
          {
            type: "table",
            heading: "Claims Breakdown",
            columns: ["Category", "Count"],
            rows: a
              ? [
                  ["Total Claims", a.claims.total],
                  ["Paid / Approved", a.claims.paid],
                  ["Denied", a.claims.denied],
                  ["Pending Review", a.claims.pending],
                ]
              : [["No data", "—"]],
          },
        ],
        "AnalyticsReport",
      );
    }
  }

  const TAB_LABELS: Record<string, string> = {
    revenue: "Revenue Cycle",
    reports: "Reports",
    bi: "Business Intelligence",
    providers: "Provider Intelligence",
    predictive: "Predictive AI",
  };

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">Analytics & Intelligence Hub</h1>
          <p className="text-sm text-muted-foreground">Revenue cycle, reports, business intelligence, provider performance, and predictive analytics — all in one place</p>
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm" data-testid="button-export-report">
              <Download className="mr-2 h-3.5 w-3.5" />
              Export {TAB_LABELS[activeTab] ?? "Report"}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={handleExportPDF} data-testid="menu-export-pdf">
              <FileText className="mr-2 h-4 w-4" />
              Export as PDF
            </DropdownMenuItem>
            <DropdownMenuItem onClick={handleExportCSV} data-testid="menu-export-csv">
              <Download className="mr-2 h-4 w-4" />
              Export as CSV
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="flex-wrap h-auto gap-1">
          <TabsTrigger value="revenue"    className="text-xs"><Activity className="h-3.5 w-3.5 mr-1" />Revenue Cycle</TabsTrigger>
          <TabsTrigger value="reports"    className="text-xs"><BarChart3 className="h-3.5 w-3.5 mr-1" />Reports</TabsTrigger>
          <TabsTrigger value="bi"         className="text-xs"><Brain className="h-3.5 w-3.5 mr-1" />Business Intel</TabsTrigger>
          <TabsTrigger value="providers"  className="text-xs"><Users className="h-3.5 w-3.5 mr-1" />Provider Intel</TabsTrigger>
          <TabsTrigger value="predictive" className="text-xs"><TrendingUp className="h-3.5 w-3.5 mr-1" />Predictive AI</TabsTrigger>
        </TabsList>
        <TabsContent value="revenue"    className="mt-4"><RevenueCycleTab /></TabsContent>
        <TabsContent value="reports"    className="mt-4"><ReportsTab onExport={handleExportCSV} /></TabsContent>
        <TabsContent value="bi"         className="mt-4"><BusinessIntelTab /></TabsContent>
        <TabsContent value="providers"  className="mt-4"><ProviderIntelTab /></TabsContent>
        <TabsContent value="predictive" className="mt-4"><PredictiveTab /></TabsContent>
      </Tabs>
    </div>
  );
}
