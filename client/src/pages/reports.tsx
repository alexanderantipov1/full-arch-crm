import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { BarChart3, TrendingUp, Users, DollarSign, Calendar, FileText, Download, PieChart } from "lucide-react";
import { format, subDays, subMonths, startOfMonth, endOfMonth } from "date-fns";
import type { Patient, BillingClaim, TreatmentPlan, PaymentPosting, Appointment } from "@shared/schema";

export default function ReportsPage() {
  const [dateRange, setDateRange] = useState("30");
  const [activeTab, setActiveTab] = useState("revenue");

  const { data: patients = [] } = useQuery<Patient[]>({
    queryKey: ["/api/patients"],
  });

  const { data: claims = [] } = useQuery<BillingClaim[]>({
    queryKey: ["/api/billing/claims"],
  });

  const { data: treatmentPlans = [] } = useQuery<TreatmentPlan[]>({
    queryKey: ["/api/treatment-plans"],
  });

  const { data: payments = [] } = useQuery<PaymentPosting[]>({
    queryKey: ["/api/era/postings"],
  });

  const { data: appointments = [] } = useQuery<Appointment[]>({
    queryKey: ["/api/appointments"],
  });

  // Calculate date range
  const days = parseInt(dateRange);
  const startDate = subDays(new Date(), days);
  const prevStartDate = subDays(startDate, days);

  // Revenue metrics
  const periodPayments = payments.filter(p => new Date(p.paymentDate) >= startDate);
  const prevPeriodPayments = payments.filter(p => {
    const date = new Date(p.paymentDate);
    return date >= prevStartDate && date < startDate;
  });

  const totalRevenue = periodPayments.reduce((sum, p) => sum + parseFloat(p.paymentAmount || "0"), 0);
  const prevRevenue = prevPeriodPayments.reduce((sum, p) => sum + parseFloat(p.paymentAmount || "0"), 0);
  const revenueChange = prevRevenue > 0 ? ((totalRevenue - prevRevenue) / prevRevenue) * 100 : 0;

  // Claims metrics
  const periodClaims = claims.filter(c => new Date(c.createdAt) >= startDate);
  const approvedClaims = periodClaims.filter(c => c.status === "paid");
  const deniedClaims = periodClaims.filter(c => c.status === "denied");
  const pendingClaims = periodClaims.filter(c => c.status === "submitted" || c.status === "pending");
  const approvalRate = periodClaims.length > 0 ? (approvedClaims.length / periodClaims.length) * 100 : 0;

  // Patient metrics
  const newPatients = patients.filter(p => new Date(p.createdAt) >= startDate);
  const prevNewPatients = patients.filter(p => {
    const date = new Date(p.createdAt);
    return date >= prevStartDate && date < startDate;
  });
  const patientGrowth = prevNewPatients.length > 0 ? ((newPatients.length - prevNewPatients.length) / prevNewPatients.length) * 100 : 0;

  // Treatment metrics
  const periodTreatments = treatmentPlans.filter(t => new Date(t.createdAt) >= startDate);
  const completedTreatments = periodTreatments.filter(t => t.status === "completed");
  const totalTreatmentValue = periodTreatments.reduce((sum, t) => sum + parseFloat(t.estimatedCost || "0"), 0);

  // Appointment metrics
  const periodAppointments = appointments.filter(a => new Date(a.date) >= startDate);
  const completedAppointments = periodAppointments.filter(a => a.status === "completed");
  const noShowAppointments = periodAppointments.filter(a => a.status === "no-show");
  const showRate = periodAppointments.length > 0 ? (completedAppointments.length / periodAppointments.length) * 100 : 0;

  // Monthly breakdown for charts
  const getMonthlyData = () => {
    const months = [];
    for (let i = 5; i >= 0; i--) {
      const monthStart = startOfMonth(subMonths(new Date(), i));
      const monthEnd = endOfMonth(subMonths(new Date(), i));
      
      const monthPayments = payments.filter(p => {
        const date = new Date(p.paymentDate);
        return date >= monthStart && date <= monthEnd;
      });
      
      const monthRevenue = monthPayments.reduce((sum, p) => sum + parseFloat(p.paymentAmount || "0"), 0);
      
      months.push({
        month: format(monthStart, "MMM"),
        revenue: monthRevenue,
        patients: patients.filter(p => {
          const date = new Date(p.createdAt);
          return date >= monthStart && date <= monthEnd;
        }).length,
      });
    }
    return months;
  };

  const monthlyData = getMonthlyData();
  const maxRevenue = Math.max(...monthlyData.map(m => m.revenue), 1);

  return (
    <div className="flex-1 overflow-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-2" data-testid="text-page-title">
            <BarChart3 className="h-8 w-8 text-primary" />
            Reports & Analytics
          </h1>
          <p className="text-muted-foreground">Comprehensive practice performance insights</p>
        </div>
        <div className="flex gap-2">
          <Select value={dateRange} onValueChange={setDateRange}>
            <SelectTrigger className="w-40" data-testid="filter-date-range">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="7">Last 7 days</SelectItem>
              <SelectItem value="30">Last 30 days</SelectItem>
              <SelectItem value="90">Last 90 days</SelectItem>
              <SelectItem value="365">Last 12 months</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="outline" data-testid="button-export">
            <Download className="h-4 w-4 mr-2" />
            Export
          </Button>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Total Revenue</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold" data-testid="stat-revenue">
              ${totalRevenue.toLocaleString("en-US", { minimumFractionDigits: 2 })}
            </div>
            <p className={`text-xs ${revenueChange >= 0 ? "text-green-600" : "text-red-600"}`}>
              {revenueChange >= 0 ? "+" : ""}{revenueChange.toFixed(1)}% vs previous period
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">New Patients</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold" data-testid="stat-patients">{newPatients.length}</div>
            <p className={`text-xs ${patientGrowth >= 0 ? "text-green-600" : "text-red-600"}`}>
              {patientGrowth >= 0 ? "+" : ""}{patientGrowth.toFixed(1)}% growth
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Claim Approval Rate</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold" data-testid="stat-approval">{approvalRate.toFixed(1)}%</div>
            <p className="text-xs text-muted-foreground">
              {approvedClaims.length} approved, {deniedClaims.length} denied
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Show Rate</CardTitle>
            <Calendar className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold" data-testid="stat-show-rate">{showRate.toFixed(1)}%</div>
            <p className="text-xs text-muted-foreground">
              {noShowAppointments.length} no-shows
            </p>
          </CardContent>
        </Card>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="revenue" data-testid="tab-revenue">Revenue</TabsTrigger>
          <TabsTrigger value="claims" data-testid="tab-claims">Claims</TabsTrigger>
          <TabsTrigger value="patients" data-testid="tab-patients">Patients</TabsTrigger>
          <TabsTrigger value="productivity" data-testid="tab-productivity">Productivity</TabsTrigger>
        </TabsList>

        <TabsContent value="revenue" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Monthly Revenue Trend</CardTitle>
              <CardDescription>Revenue collected over the past 6 months</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-64 flex items-end justify-between gap-2">
                {monthlyData.map((month, i) => (
                  <div key={i} className="flex-1 flex flex-col items-center gap-2">
                    <div className="w-full bg-primary/20 rounded-t relative" style={{ height: `${(month.revenue / maxRevenue) * 200}px`, minHeight: "4px" }}>
                      <div className="absolute -top-6 left-1/2 -translate-x-1/2 text-xs font-medium whitespace-nowrap">
                        ${(month.revenue / 1000).toFixed(0)}k
                      </div>
                    </div>
                    <span className="text-xs text-muted-foreground">{month.month}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle>Revenue Breakdown</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex justify-between items-center">
                  <span>Insurance Payments</span>
                  <span className="font-bold">
                    ${periodPayments.filter(p => p.payerName?.toLowerCase().includes("insurance")).reduce((s, p) => s + parseFloat(p.paymentAmount || "0"), 0).toLocaleString()}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span>Patient Payments</span>
                  <span className="font-bold">
                    ${periodPayments.filter(p => !p.payerName?.toLowerCase().includes("insurance")).reduce((s, p) => s + parseFloat(p.paymentAmount || "0"), 0).toLocaleString()}
                  </span>
                </div>
                <div className="flex justify-between items-center border-t pt-4">
                  <span className="font-medium">Total</span>
                  <span className="font-bold text-lg">${totalRevenue.toLocaleString()}</span>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Treatment Value</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex justify-between items-center">
                  <span>Active Treatments</span>
                  <span className="font-bold">{periodTreatments.filter(t => t.status === "active").length}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span>Completed</span>
                  <span className="font-bold">{completedTreatments.length}</span>
                </div>
                <div className="flex justify-between items-center border-t pt-4">
                  <span className="font-medium">Total Value</span>
                  <span className="font-bold text-lg">${totalTreatmentValue.toLocaleString()}</span>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="claims" className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Submitted</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold text-blue-600">{periodClaims.length}</div>
                <p className="text-sm text-muted-foreground">Total claims</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Approved/Paid</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold text-green-600">{approvedClaims.length}</div>
                <p className="text-sm text-muted-foreground">{approvalRate.toFixed(0)}% approval rate</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Denied</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold text-red-600">{deniedClaims.length}</div>
                <p className="text-sm text-muted-foreground">Requires attention</p>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Claim Status Distribution</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {[
                  { label: "Paid", count: approvedClaims.length, color: "bg-green-500" },
                  { label: "Pending", count: pendingClaims.length, color: "bg-amber-500" },
                  { label: "Denied", count: deniedClaims.length, color: "bg-red-500" },
                ].map((item) => (
                  <div key={item.label} className="flex items-center gap-4">
                    <span className="w-20 text-sm">{item.label}</span>
                    <div className="flex-1 h-4 bg-muted rounded-full overflow-hidden">
                      <div
                        className={`h-full ${item.color}`}
                        style={{ width: `${periodClaims.length > 0 ? (item.count / periodClaims.length) * 100 : 0}%` }}
                      />
                    </div>
                    <span className="w-12 text-right font-medium">{item.count}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="patients" className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle>Patient Growth</CardTitle>
                <CardDescription>New patients per month</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-48 flex items-end justify-between gap-2">
                  {monthlyData.map((month, i) => (
                    <div key={i} className="flex-1 flex flex-col items-center gap-2">
                      <div
                        className="w-full bg-blue-500/20 rounded-t"
                        style={{ height: `${Math.max(month.patients * 20, 8)}px` }}
                      />
                      <span className="text-xs text-muted-foreground">{month.month}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Patient Summary</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex justify-between items-center">
                  <span>Total Patients</span>
                  <span className="font-bold">{patients.length}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span>New This Period</span>
                  <span className="font-bold text-green-600">+{newPatients.length}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span>With Active Treatment</span>
                  <span className="font-bold">{treatmentPlans.filter(t => t.status === "active").length}</span>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="productivity" className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Appointments Completed</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold">{completedAppointments.length}</div>
                <p className="text-sm text-muted-foreground">of {periodAppointments.length} scheduled</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Treatment Plans Created</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold">{periodTreatments.length}</div>
                <p className="text-sm text-muted-foreground">This period</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Avg Revenue per Patient</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold">
                  ${patients.length > 0 ? (totalRevenue / newPatients.length || 0).toLocaleString("en-US", { maximumFractionDigits: 0 }) : "0"}
                </div>
                <p className="text-sm text-muted-foreground">New patients</p>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
