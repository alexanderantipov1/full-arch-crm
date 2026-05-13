import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "wouter";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Calendar as CalendarComponent } from "@/components/ui/calendar";
import { useToast } from "@/hooks/use-toast";
import { apiRequest } from "@/lib/queryClient";
import {
  Plus,
  Calendar,
  Clock,
  User,
  MapPin,
  ChevronLeft,
  ChevronRight,
  Stethoscope,
  Armchair,
  DollarSign,
  AlertTriangle,
  ListChecks,
  Brain,
  Bell,
  UserPlus,
  ShieldAlert,
  Zap,
  Shield,
  CheckCircle2,
  Loader2,
} from "lucide-react";
import { format, startOfDay, isSameDay, addDays, startOfWeek, endOfWeek } from "date-fns";
import type { Appointment } from "@shared/schema";

const appointmentTypeColors: Record<string, string> = {
  consultation: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
  surgery: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
  follow_up: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
  imaging: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400",
  preop: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400",
};

const riskColors: Record<string, string> = {
  low: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
  medium: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400",
  high: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
};

const tomorrowSchedule = [
  { time: "8:00", duration: "60m", chair: "Op 1", provider: "Dr. Chen", patient: "Robert Kim", procedure: "Implant Consult + CBCT", production: 2450, risk: "low" },
  { time: "8:00", duration: "60m", chair: "Op 2", provider: "Dr. Park", patient: "Diana Patel", procedure: "Invisalign Check #9", production: 280, risk: "low" },
  { time: "9:00", duration: "90m", chair: "Op 1", provider: "Dr. Chen", patient: "Margaret Sullivan", procedure: "Crown Seat #14", production: 1280, risk: "low" },
  { time: "10:00", duration: "120m", chair: "Op 1", provider: "Dr. Chen", patient: "Michael Torres", procedure: "Crown Prep #3", production: 1840, risk: "low" },
];

const noShowRisks = [
  { name: "Maria Garcia", tag: "New", risk: 38, reason: "New pt, no deposit" },
  { name: "James Okafor", tag: null, risk: 22, reason: "Missed last 2 hyg" },
  { name: "Tyler Nguyen", tag: null, risk: 18, reason: "History of reschedule" },
];

const aiWaitlist = [
  { name: "Frank Morris", procedure: "Crown seat #8", production: 1280, availability: "Any AM" },
  { name: "Karen Brown", procedure: "Filling #18", production: 240, availability: "Tue/Thu PM" },
  { name: "Pete Hall", procedure: "Implant F/U", production: 0, availability: "Flexible" },
];

export default function AppointmentsPage() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [selectedDate, setSelectedDate] = useState<Date>(new Date());
  const [view, setView] = useState<"day" | "week">("day");
  const [mainTab, setMainTab] = useState<string>("calendar");
  const [batchResults, setBatchResults] = useState<any[] | null>(null);

  const { data: appointments, isLoading } = useQuery<Appointment[]>({
    queryKey: ["/api/appointments"],
  });

  const batchVerifyMut = useMutation({
    mutationFn: () => apiRequest("POST", "/api/eligibility/batch-tomorrow", {}).then(r => r.json()),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["/api/eligibility"] });
      setBatchResults(data.results ?? []);
      const active = (data.results ?? []).filter((r: any) => r.eligibilityStatus === "active").length;
      const issues = data.checked - active;
      toast({ title: `Batch Verify Complete`, description: `${active} active, ${issues} need review` });
    },
    onError: () => toast({ title: "Batch verify failed", variant: "destructive" }),
  });

  const filteredAppointments = appointments?.filter((apt) => {
    const aptDate = new Date(apt.startTime);
    if (view === "day") {
      return isSameDay(aptDate, selectedDate);
    } else {
      const weekStart = startOfWeek(selectedDate, { weekStartsOn: 0 });
      const weekEnd = endOfWeek(selectedDate, { weekStartsOn: 0 });
      return aptDate >= weekStart && aptDate <= weekEnd;
    }
  });

  const navigateDate = (direction: "prev" | "next") => {
    const days = view === "day" ? 1 : 7;
    setSelectedDate((prev) =>
      direction === "next" ? addDays(prev, days) : addDays(prev, -days)
    );
  };

  const timeSlots = Array.from({ length: 12 }, (_, i) => i + 7);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Appointments</h1>
          <p className="text-muted-foreground">
            Manage surgery schedules and patient appointments
          </p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <Button
            variant="outline"
            onClick={() => batchVerifyMut.mutate()}
            disabled={batchVerifyMut.isPending}
            data-testid="button-batch-verify-tomorrow"
          >
            {batchVerifyMut.isPending
              ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Verifying…</>
              : <><Shield className="mr-2 h-4 w-4" />Verify Tomorrow's Patients</>}
          </Button>
          <Button asChild data-testid="button-new-appointment">
            <Link href="/appointments/new">
              <Plus className="mr-2 h-4 w-4" />
              New Appointment
            </Link>
          </Button>
        </div>
      </div>

      {batchResults && batchResults.length > 0 && (
        <Card className="border-blue-200 dark:border-blue-800" data-testid="card-batch-verify-results">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Shield className="h-4 w-4 text-blue-500" />
              Tomorrow's Eligibility — {batchResults.length} patients checked
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {batchResults.map((r, i) => (
                <Badge
                  key={i}
                  variant={r.eligibilityStatus === "active" ? "secondary" : "destructive"}
                  className="text-xs"
                  data-testid={`batch-result-${i}`}
                >
                  {r.eligibilityStatus === "active"
                    ? <CheckCircle2 className="h-3 w-3 mr-1" />
                    : <AlertTriangle className="h-3 w-3 mr-1" />}
                  Pt {r.patientId}: {r.eligibilityStatus ?? r.status}
                  {r.cached ? " (cached)" : ""}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
      {batchResults && batchResults.length === 0 && (
        <Card data-testid="card-batch-verify-empty">
          <CardContent className="py-4 text-center text-sm text-muted-foreground">
            No appointments scheduled for tomorrow.
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card data-testid="kpi-chair-utilization">
          <CardHeader className="flex flex-row items-center justify-between gap-2 space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Chair Utilization</CardTitle>
            <Armchair className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold" data-testid="value-chair-utilization">91%</div>
            <Progress value={91} className="mt-2" data-testid="progress-chair-utilization" />
            <p className="mt-1 text-xs text-muted-foreground">Target 85%</p>
          </CardContent>
        </Card>

        <Card data-testid="kpi-tomorrows-production">
          <CardHeader className="flex flex-row items-center justify-between gap-2 space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Tomorrow's Production</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold" data-testid="value-tomorrows-production">$24,800</div>
            <p className="mt-1 text-xs text-muted-foreground">Across all providers</p>
          </CardContent>
        </Card>

        <Card data-testid="kpi-noshow-risk">
          <CardHeader className="flex flex-row items-center justify-between gap-2 space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">No-Show Risk</CardTitle>
            <AlertTriangle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold" data-testid="value-noshow-risk">3</div>
            <p className="mt-1 text-xs text-muted-foreground">AI sending reminders</p>
          </CardContent>
        </Card>

        <Card data-testid="kpi-sameday-fills">
          <CardHeader className="flex flex-row items-center justify-between gap-2 space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Same-Day Fills</CardTitle>
            <Zap className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold" data-testid="value-sameday-fills">4</div>
            <p className="mt-1 text-xs text-muted-foreground">From AI waitlist</p>
          </CardContent>
        </Card>
      </div>

      <Tabs value={mainTab} onValueChange={setMainTab}>
        <TabsList data-testid="tabs-main-schedule">
          <TabsTrigger value="calendar" data-testid="tab-calendar">
            <Calendar className="mr-2 h-4 w-4" />
            Calendar
          </TabsTrigger>
          <TabsTrigger value="smart" data-testid="tab-smart-schedule">
            <Brain className="mr-2 h-4 w-4" />
            Smart Schedule
          </TabsTrigger>
        </TabsList>

        <TabsContent value="calendar" className="mt-4">
          <div className="grid gap-6 lg:grid-cols-[300px_1fr]">
            <div className="space-y-4">
              <Card>
                <CardContent className="p-4">
                  <CalendarComponent
                    mode="single"
                    selected={selectedDate}
                    onSelect={(date) => date && setSelectedDate(date)}
                    className="rounded-md"
                  />
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm font-medium">Today's Summary</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex items-center justify-between gap-2 text-sm">
                    <div className="flex items-center gap-2">
                      <div className="h-2 w-2 rounded-full bg-blue-500" />
                      <span>Consultations</span>
                    </div>
                    <span className="font-medium">
                      {appointments?.filter(
                        (a) =>
                          a.appointmentType === "consultation" &&
                          isSameDay(new Date(a.startTime), new Date())
                      ).length || 0}
                    </span>
                  </div>
                  <div className="flex items-center justify-between gap-2 text-sm">
                    <div className="flex items-center gap-2">
                      <div className="h-2 w-2 rounded-full bg-red-500" />
                      <span>Surgeries</span>
                    </div>
                    <span className="font-medium">
                      {appointments?.filter(
                        (a) =>
                          a.appointmentType === "surgery" &&
                          isSameDay(new Date(a.startTime), new Date())
                      ).length || 0}
                    </span>
                  </div>
                  <div className="flex items-center justify-between gap-2 text-sm">
                    <div className="flex items-center gap-2">
                      <div className="h-2 w-2 rounded-full bg-green-500" />
                      <span>Follow-ups</span>
                    </div>
                    <span className="font-medium">
                      {appointments?.filter(
                        (a) =>
                          a.appointmentType === "follow_up" &&
                          isSameDay(new Date(a.startTime), new Date())
                      ).length || 0}
                    </span>
                  </div>
                </CardContent>
              </Card>
            </div>

            <Card>
              <CardHeader className="border-b pb-4">
                <div className="flex items-center justify-between gap-4 flex-wrap">
                  <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2">
                      <Button variant="outline" size="icon" onClick={() => navigateDate("prev")} data-testid="button-prev-date">
                        <ChevronLeft className="h-4 w-4" />
                      </Button>
                      <Button variant="outline" size="icon" onClick={() => navigateDate("next")} data-testid="button-next-date">
                        <ChevronRight className="h-4 w-4" />
                      </Button>
                    </div>
                    <div>
                      <CardTitle className="text-lg" data-testid="text-current-date">
                        {view === "day"
                          ? format(selectedDate, "EEEE, MMMM d, yyyy")
                          : `Week of ${format(startOfWeek(selectedDate), "MMM d")} - ${format(
                              endOfWeek(selectedDate),
                              "MMM d, yyyy"
                            )}`}
                      </CardTitle>
                    </div>
                  </div>
                  <Tabs value={view} onValueChange={(v) => setView(v as "day" | "week")}>
                    <TabsList>
                      <TabsTrigger value="day" data-testid="tab-day-view">Day</TabsTrigger>
                      <TabsTrigger value="week" data-testid="tab-week-view">Week</TabsTrigger>
                    </TabsList>
                  </Tabs>
                </div>
              </CardHeader>
              <CardContent className="p-0">
                {isLoading ? (
                  <div className="p-6 space-y-3">
                    {[1, 2, 3, 4].map((i) => (
                      <Skeleton key={i} className="h-20 w-full" />
                    ))}
                  </div>
                ) : filteredAppointments && filteredAppointments.length > 0 ? (
                  <div className="divide-y">
                    {timeSlots.map((hour) => {
                      const hourAppointments = filteredAppointments.filter((apt) => {
                        const aptHour = new Date(apt.startTime).getHours();
                        return aptHour === hour;
                      });

                      return (
                        <div key={hour} className="flex min-h-[80px]">
                          <div className="w-20 shrink-0 border-r bg-muted/30 p-3 text-sm text-muted-foreground">
                            {format(new Date().setHours(hour, 0), "h:mm a")}
                          </div>
                          <div className="flex-1 p-2">
                            {hourAppointments.map((apt) => (
                              <div
                                key={apt.id}
                                className="mb-2 rounded-md border p-3 hover-elevate"
                                data-testid={`appointment-slot-${apt.id}`}
                              >
                                <div className="flex items-start justify-between gap-2">
                                  <div>
                                    <div className="flex items-center gap-2 flex-wrap">
                                      <p className="font-medium">{apt.title}</p>
                                      <Badge
                                        className={
                                          appointmentTypeColors[apt.appointmentType] || ""
                                        }
                                      >
                                        {apt.appointmentType}
                                      </Badge>
                                    </div>
                                    <div className="mt-1 flex items-center gap-3 text-sm text-muted-foreground flex-wrap">
                                      <div className="flex items-center gap-1">
                                        <Clock className="h-3 w-3" />
                                        {format(new Date(apt.startTime), "h:mm a")} -{" "}
                                        {format(new Date(apt.endTime), "h:mm a")}
                                      </div>
                                      {apt.location && (
                                        <div className="flex items-center gap-1">
                                          <MapPin className="h-3 w-3" />
                                          {apt.location}
                                        </div>
                                      )}
                                    </div>
                                  </div>
                                  <Button variant="ghost" size="sm" asChild data-testid={`button-view-appointment-${apt.id}`}>
                                    <Link href={`/appointments/${apt.id}`}>View</Link>
                                  </Button>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center py-16 text-center">
                    <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-muted">
                      <Calendar className="h-8 w-8 text-muted-foreground" />
                    </div>
                    <h3 className="mb-2 text-lg font-semibold">No appointments</h3>
                    <p className="mb-6 max-w-sm text-sm text-muted-foreground">
                      No appointments scheduled for {format(selectedDate, "MMMM d, yyyy")}
                    </p>
                    <Button asChild data-testid="button-schedule-empty">
                      <Link href="/appointments/new">
                        <Plus className="mr-2 h-4 w-4" />
                        Schedule Appointment
                      </Link>
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="smart" className="mt-4">
          <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
            <Card data-testid="card-tomorrow-schedule">
              <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                  <ListChecks className="h-5 w-5 text-muted-foreground" />
                  <CardTitle className="text-lg">Tomorrow's Schedule</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm" data-testid="table-tomorrow-schedule">
                    <thead>
                      <tr className="border-b bg-muted/40">
                        <th className="px-4 py-3 text-left font-medium text-muted-foreground">Time</th>
                        <th className="px-4 py-3 text-left font-medium text-muted-foreground">Duration</th>
                        <th className="px-4 py-3 text-left font-medium text-muted-foreground">Chair</th>
                        <th className="px-4 py-3 text-left font-medium text-muted-foreground">Provider</th>
                        <th className="px-4 py-3 text-left font-medium text-muted-foreground">Patient</th>
                        <th className="px-4 py-3 text-left font-medium text-muted-foreground">Procedure</th>
                        <th className="px-4 py-3 text-right font-medium text-muted-foreground">Production</th>
                        <th className="px-4 py-3 text-center font-medium text-muted-foreground">Risk</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {tomorrowSchedule.map((row, idx) => (
                        <tr key={idx} className="hover-elevate" data-testid={`row-schedule-${idx}`}>
                          <td className="px-4 py-3 font-medium" data-testid={`text-schedule-time-${idx}`}>{row.time}</td>
                          <td className="px-4 py-3 text-muted-foreground" data-testid={`text-schedule-duration-${idx}`}>{row.duration}</td>
                          <td className="px-4 py-3" data-testid={`text-schedule-chair-${idx}`}>
                            <Badge variant="outline" className="no-default-hover-elevate no-default-active-elevate">{row.chair}</Badge>
                          </td>
                          <td className="px-4 py-3" data-testid={`text-schedule-provider-${idx}`}>
                            <div className="flex items-center gap-1">
                              <Stethoscope className="h-3 w-3 text-muted-foreground" />
                              {row.provider}
                            </div>
                          </td>
                          <td className="px-4 py-3" data-testid={`text-schedule-patient-${idx}`}>
                            <div className="flex items-center gap-1">
                              <User className="h-3 w-3 text-muted-foreground" />
                              {row.patient}
                            </div>
                          </td>
                          <td className="px-4 py-3" data-testid={`text-schedule-procedure-${idx}`}>{row.procedure}</td>
                          <td className="px-4 py-3 text-right font-medium" data-testid={`text-schedule-production-${idx}`}>
                            ${row.production.toLocaleString()}
                          </td>
                          <td className="px-4 py-3 text-center" data-testid={`badge-schedule-risk-${idx}`}>
                            <Badge className={riskColors[row.risk]}>{row.risk}</Badge>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>

            <div className="space-y-4">
              <Card data-testid="card-noshow-risk">
                <CardHeader className="pb-3">
                  <div className="flex items-center gap-2">
                    <ShieldAlert className="h-5 w-5 text-muted-foreground" />
                    <CardTitle className="text-sm font-medium">No-Show Risk</CardTitle>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  {noShowRisks.map((item, idx) => (
                    <div key={idx} className="space-y-2" data-testid={`noshow-risk-item-${idx}`}>
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-medium text-sm" data-testid={`text-noshow-name-${idx}`}>{item.name}</span>
                          {item.tag && (
                            <Badge variant="secondary" className="text-xs" data-testid={`badge-noshow-tag-${idx}`}>{item.tag}</Badge>
                          )}
                        </div>
                        <Badge className={item.risk >= 30 ? riskColors.high : item.risk >= 20 ? riskColors.medium : riskColors.low} data-testid={`badge-noshow-risk-${idx}`}>
                          {item.risk}%
                        </Badge>
                      </div>
                      <Progress value={item.risk} className="h-1.5" data-testid={`progress-noshow-risk-${idx}`} />
                      <p className="text-xs text-muted-foreground" data-testid={`text-noshow-reason-${idx}`}>{item.reason}</p>
                    </div>
                  ))}
                </CardContent>
              </Card>

              <Card data-testid="card-ai-waitlist">
                <CardHeader className="pb-3">
                  <div className="flex items-center gap-2">
                    <UserPlus className="h-5 w-5 text-muted-foreground" />
                    <CardTitle className="text-sm font-medium">AI Waitlist</CardTitle>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  {aiWaitlist.map((item, idx) => (
                    <div key={idx} className="flex items-start justify-between gap-2 rounded-md border p-3" data-testid={`waitlist-item-${idx}`}>
                      <div className="space-y-1">
                        <p className="text-sm font-medium" data-testid={`text-waitlist-name-${idx}`}>{item.name}</p>
                        <p className="text-xs text-muted-foreground" data-testid={`text-waitlist-procedure-${idx}`}>{item.procedure}</p>
                        <p className="text-xs text-muted-foreground" data-testid={`text-waitlist-availability-${idx}`}>{item.availability}</p>
                      </div>
                      <span className="text-sm font-medium" data-testid={`text-waitlist-production-${idx}`}>
                        ${item.production.toLocaleString()}
                      </span>
                    </div>
                  ))}
                  <div className="flex items-center gap-2 rounded-md bg-muted/50 p-3 dark:bg-muted/20">
                    <Bell className="h-4 w-4 shrink-0 text-muted-foreground" />
                    <p className="text-xs text-muted-foreground" data-testid="text-waitlist-footer">
                      Cancellation leads to AI contacts waitlist in 30 sec
                    </p>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
