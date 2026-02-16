import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Progress } from "@/components/ui/progress";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  Users,
  Calendar,
  ClipboardList,
  DollarSign,
  TrendingUp,
  Clock,
  AlertCircle,
  ArrowRight,
  Plus,
  Target,
  Percent,
  UserPlus,
  ThumbsUp,
  PieChart,
  RotateCcw,
  Activity,
  Heart,
  CheckCircle,
  XCircle,
  BarChart3,
} from "lucide-react";
import { Link } from "wouter";
import { format } from "date-fns";
import type { Patient, Appointment, TreatmentPlan } from "@shared/schema";

const DEO_KPIS = [
  { label: "Production/Day", value: "$52.4K", target: "$55K", pct: 95, icon: DollarSign, color: "text-emerald-600 dark:text-emerald-400" },
  { label: "Collections %", value: "96.2%", target: "98%", pct: 98, icon: Percent, color: "text-blue-600 dark:text-blue-400" },
  { label: "New Patients/Mo", value: "38", target: "45", pct: 84, icon: UserPlus, color: "text-violet-600 dark:text-violet-400" },
  { label: "Case Acceptance", value: "72%", target: "80%", pct: 90, icon: ThumbsUp, color: "text-amber-600 dark:text-amber-400" },
  { label: "Overhead Ratio", value: "57.3%", target: "<59%", pct: 97, icon: PieChart, color: "text-emerald-600 dark:text-emerald-400" },
  { label: "Reappt Rate", value: "87%", target: "90%", pct: 97, icon: RotateCcw, color: "text-sky-600 dark:text-sky-400" },
  { label: "Hygiene Prod %", value: "29%", target: "30%", pct: 97, icon: Activity, color: "text-teal-600 dark:text-teal-400" },
  { label: "Patient LTV", value: "$8,740", target: "$12K", pct: 73, icon: Heart, color: "text-rose-600 dark:text-rose-400" },
];

const WEEKLY_SCORECARD = [
  { metric: "Production", vals: ["$48K", "$52K", "$55K", "$49K", "$51K"], total: "$255K", goal: "$275K", hit: false },
  { metric: "Collections", vals: ["$46K", "$50K", "$53K", "$47K", "$49K"], total: "$245K", goal: "$250K", hit: false },
  { metric: "New Patients", vals: ["3", "2", "4", "2", "3"], total: "14", goal: "10", hit: true },
  { metric: "Cases Presented", vals: ["5", "4", "6", "5", "4"], total: "24", goal: "20", hit: true },
  { metric: "Cases Accepted", vals: ["3", "3", "5", "4", "2"], total: "17", goal: "15", hit: true },
  { metric: "Hygiene Prod.", vals: ["$14K", "$16K", "$15K", "$14K", "$15K"], total: "$74K", goal: "$80K", hit: false },
];

interface DashboardStats {
  totalPatients: number;
  todayAppointments: number;
  pendingTreatmentPlans: number;
  pendingClaims: number;
}

export default function Dashboard() {
  const { data: stats, isLoading: statsLoading } = useQuery<DashboardStats>({
    queryKey: ["/api/dashboard/stats"],
  });

  const { data: allPatients, isLoading: patientsLoading } = useQuery<Patient[]>({
    queryKey: ["/api/patients"],
  });
  const recentPatients = allPatients?.slice(0, 5);

  const { data: upcomingAppointments, isLoading: appointmentsLoading } = useQuery<Appointment[]>({
    queryKey: ["/api/appointments/upcoming"],
  });

  const { data: allPlans, isLoading: plansLoading } = useQuery<TreatmentPlan[]>({
    queryKey: ["/api/treatment-plans"],
  });
  const pendingPlans = allPlans?.filter(p => p.status === "pending");

  const statCards = [
    {
      title: "Total Patients",
      value: stats?.totalPatients || 0,
      icon: Users,
      color: "text-primary",
      bgColor: "bg-primary/10",
    },
    {
      title: "Today's Appointments",
      value: stats?.todayAppointments || 0,
      icon: Calendar,
      color: "text-accent",
      bgColor: "bg-accent/10",
    },
    {
      title: "Pending Plans",
      value: stats?.pendingTreatmentPlans || 0,
      icon: ClipboardList,
      color: "text-chart-3",
      bgColor: "bg-chart-3/10",
    },
    {
      title: "Pending Claims",
      value: stats?.pendingClaims || 0,
      icon: DollarSign,
      color: "text-chart-4",
      bgColor: "bg-chart-4/10",
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground">
            Welcome back. Here's an overview of your practice.
          </p>
        </div>
        <div className="flex gap-3">
          <Button asChild data-testid="button-new-patient">
            <Link href="/patients/new">
              <Plus className="mr-2 h-4 w-4" />
              New Patient
            </Link>
          </Button>
          <Button variant="outline" asChild data-testid="button-new-appointment">
            <Link href="/appointments/new">
              <Calendar className="mr-2 h-4 w-4" />
              Schedule
            </Link>
          </Button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {statCards.map((stat) => (
          <Card key={stat.title}>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">{stat.title}</p>
                  {statsLoading ? (
                    <Skeleton className="mt-1 h-8 w-16" />
                  ) : (
                    <p className="text-3xl font-bold">{stat.value}</p>
                  )}
                </div>
                <div className={`flex h-12 w-12 items-center justify-center rounded-lg ${stat.bgColor}`}>
                  <stat.icon className={`h-6 w-6 ${stat.color}`} />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-lg font-semibold flex flex-wrap items-center gap-2">
              <BarChart3 className="h-5 w-5 text-blue-600 dark:text-blue-400" />
              DEO Practice KPIs
            </h2>
            <p className="text-sm text-muted-foreground">Dental Entrepreneur Organization standard metrics</p>
          </div>
          <Badge variant="outline" data-testid="badge-deo-standard">DEO Standard</Badge>
        </div>
        <div className="grid gap-3 grid-cols-2 md:grid-cols-4">
          {DEO_KPIS.map((kpi) => (
            <Card
              key={kpi.label}
              data-testid={`kpi-card-${kpi.label.toLowerCase().replace(/[^a-z0-9]/g, "-")}`}
            >
              <CardContent className="p-4 text-center space-y-2">
                <div className="flex items-center justify-center">
                  <kpi.icon className={`h-5 w-5 ${kpi.color}`} />
                </div>
                <div className={`text-2xl font-bold ${kpi.color}`} data-testid={`kpi-value-${kpi.label.toLowerCase().replace(/[^a-z0-9]/g, "-")}`}>
                  {kpi.value}
                </div>
                <div className="text-xs font-semibold">{kpi.label}</div>
                <Progress value={kpi.pct} className="h-1.5" />
                <div className="text-xs text-muted-foreground">Target: {kpi.target}</div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-4 space-y-0 pb-4">
          <div>
            <CardTitle className="text-lg flex flex-wrap items-center gap-2">
              <Target className="h-5 w-5 text-amber-600 dark:text-amber-400" />
              Weekly Scorecard
            </CardTitle>
            <CardDescription>DEO Framework - Daily performance tracking</CardDescription>
          </div>
          <Badge variant="outline" className="text-amber-600 dark:text-amber-400 border-amber-300 dark:border-amber-700" data-testid="badge-deo-weekly">
            This Week
          </Badge>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="table-weekly-scorecard">
              <thead>
                <tr className="border-b">
                  <th className="py-2 px-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Metric</th>
                  {["Mon", "Tue", "Wed", "Thu", "Fri"].map((d) => (
                    <th key={d} className="py-2 px-3 text-center text-xs font-semibold text-muted-foreground uppercase tracking-wider">{d}</th>
                  ))}
                  <th className="py-2 px-3 text-center text-xs font-semibold text-muted-foreground uppercase tracking-wider">Week Total</th>
                  <th className="py-2 px-3 text-center text-xs font-semibold text-muted-foreground uppercase tracking-wider">Goal</th>
                  <th className="py-2 px-3 text-center text-xs font-semibold text-muted-foreground uppercase tracking-wider">Status</th>
                </tr>
              </thead>
              <tbody>
                {WEEKLY_SCORECARD.map((row) => (
                  <tr key={row.metric} className="border-b last:border-0" data-testid={`scorecard-row-${row.metric.toLowerCase().replace(/\s+/g, "-")}`}>
                    <td className="py-2.5 px-3 font-semibold">{row.metric}</td>
                    {row.vals.map((v, j) => (
                      <td key={j} className="py-2.5 px-3 text-center text-muted-foreground font-mono text-xs">{v}</td>
                    ))}
                    <td className="py-2.5 px-3 text-center font-bold font-mono text-xs">{row.total}</td>
                    <td className="py-2.5 px-3 text-center text-muted-foreground text-xs">{row.goal}</td>
                    <td className="py-2.5 px-3 text-center">
                      {row.hit ? (
                        <Badge variant="secondary" className="gap-1 text-emerald-700 dark:text-emerald-400 bg-emerald-100 dark:bg-emerald-900/30" data-testid={`scorecard-status-${row.metric.toLowerCase().replace(/\s+/g, "-")}`}>
                          <CheckCircle className="h-3 w-3" />
                          HIT
                        </Badge>
                      ) : (
                        <Badge variant="secondary" className="gap-1 text-red-700 dark:text-red-400 bg-red-100 dark:bg-red-900/30" data-testid={`scorecard-status-${row.metric.toLowerCase().replace(/\s+/g, "-")}`}>
                          <XCircle className="h-3 w-3" />
                          MISS
                        </Badge>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between gap-4 space-y-0 pb-4">
            <div>
              <CardTitle className="text-lg">Upcoming Appointments</CardTitle>
              <CardDescription>Scheduled for today and tomorrow</CardDescription>
            </div>
            <Button variant="ghost" size="sm" asChild>
              <Link href="/appointments">
                View All
                <ArrowRight className="ml-1 h-4 w-4" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent>
            {appointmentsLoading ? (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <Skeleton key={i} className="h-16 w-full" />
                ))}
              </div>
            ) : upcomingAppointments && upcomingAppointments.length > 0 ? (
              <div className="space-y-3">
                {upcomingAppointments.slice(0, 5).map((apt) => (
                  <div
                    key={apt.id}
                    className="flex items-center justify-between rounded-lg border p-3 hover-elevate"
                  >
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-md bg-primary/10">
                        <Clock className="h-5 w-5 text-primary" />
                      </div>
                      <div>
                        <p className="font-medium">{apt.title}</p>
                        <p className="text-sm text-muted-foreground">
                          {format(new Date(apt.startTime), "MMM d, h:mm a")}
                        </p>
                      </div>
                    </div>
                    <Badge variant="secondary">{apt.appointmentType}</Badge>
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <Calendar className="mb-3 h-10 w-10 text-muted-foreground/50" />
                <p className="text-sm text-muted-foreground">No upcoming appointments</p>
                <Button variant="ghost" size="sm" asChild className="mt-2">
                  <Link href="/appointments/new">Schedule one now</Link>
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between gap-4 space-y-0 pb-4">
            <div>
              <CardTitle className="text-lg">Recent Patients</CardTitle>
              <CardDescription>Latest patient registrations</CardDescription>
            </div>
            <Button variant="ghost" size="sm" asChild>
              <Link href="/patients">
                View All
                <ArrowRight className="ml-1 h-4 w-4" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent>
            {patientsLoading ? (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <Skeleton key={i} className="h-16 w-full" />
                ))}
              </div>
            ) : recentPatients && recentPatients.length > 0 ? (
              <div className="space-y-3">
                {recentPatients.slice(0, 5).map((patient) => (
                  <Link
                    key={patient.id}
                    href={`/patients/${patient.id}`}
                    className="flex items-center justify-between rounded-lg border p-3 hover-elevate cursor-pointer"
                  >
                    <div className="flex items-center gap-3">
                      <Avatar className="h-10 w-10">
                        <AvatarFallback className="bg-primary/10 text-primary">
                          {patient.firstName[0]}{patient.lastName[0]}
                        </AvatarFallback>
                      </Avatar>
                      <div>
                        <p className="font-medium">
                          {patient.firstName} {patient.lastName}
                        </p>
                        <p className="text-sm text-muted-foreground">{patient.email}</p>
                      </div>
                    </div>
                    <ArrowRight className="h-4 w-4 text-muted-foreground" />
                  </Link>
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <Users className="mb-3 h-10 w-10 text-muted-foreground/50" />
                <p className="text-sm text-muted-foreground">No patients yet</p>
                <Button variant="ghost" size="sm" asChild className="mt-2">
                  <Link href="/patients/new">Add your first patient</Link>
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-4 space-y-0 pb-4">
          <div>
            <CardTitle className="text-lg">Pending Treatment Plans</CardTitle>
            <CardDescription>Plans awaiting approval or action</CardDescription>
          </div>
          <Button variant="ghost" size="sm" asChild>
            <Link href="/treatment-plans">
              View All
              <ArrowRight className="ml-1 h-4 w-4" />
            </Link>
          </Button>
        </CardHeader>
        <CardContent>
          {plansLoading ? (
            <div className="space-y-3">
              {[1, 2].map((i) => (
                <Skeleton key={i} className="h-20 w-full" />
              ))}
            </div>
          ) : pendingPlans && pendingPlans.length > 0 ? (
            <div className="space-y-3">
              {pendingPlans.slice(0, 4).map((plan) => (
                <div
                  key={plan.id}
                  className="flex items-center justify-between rounded-lg border p-4 hover-elevate"
                >
                  <div className="flex items-center gap-4">
                    <div className="flex h-10 w-10 items-center justify-center rounded-md bg-chart-3/10">
                      <ClipboardList className="h-5 w-5 text-chart-3" />
                    </div>
                    <div>
                      <p className="font-medium">{plan.planName}</p>
                      <p className="text-sm text-muted-foreground">{plan.diagnosis}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    {plan.priorAuthStatus === "pending" && (
                      <Badge variant="outline" className="gap-1">
                        <AlertCircle className="h-3 w-3" />
                        Auth Pending
                      </Badge>
                    )}
                    <Badge>{plan.status}</Badge>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <ClipboardList className="mb-3 h-10 w-10 text-muted-foreground/50" />
              <p className="text-sm text-muted-foreground">No pending treatment plans</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
