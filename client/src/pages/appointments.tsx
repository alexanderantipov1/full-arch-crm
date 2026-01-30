import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "wouter";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Calendar as CalendarComponent } from "@/components/ui/calendar";
import {
  Plus,
  Calendar,
  Clock,
  User,
  MapPin,
  ChevronLeft,
  ChevronRight,
  Stethoscope,
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

export default function AppointmentsPage() {
  const [selectedDate, setSelectedDate] = useState<Date>(new Date());
  const [view, setView] = useState<"day" | "week">("day");

  const { data: appointments, isLoading } = useQuery<Appointment[]>({
    queryKey: ["/api/appointments"],
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
        <Button asChild data-testid="button-new-appointment">
          <Link href="/appointments/new">
            <Plus className="mr-2 h-4 w-4" />
            New Appointment
          </Link>
        </Button>
      </div>

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
              <div className="flex items-center justify-between text-sm">
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
              <div className="flex items-center justify-between text-sm">
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
              <div className="flex items-center justify-between text-sm">
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
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <Button variant="outline" size="icon" onClick={() => navigateDate("prev")}>
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  <Button variant="outline" size="icon" onClick={() => navigateDate("next")}>
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
                <div>
                  <CardTitle className="text-lg">
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
                  <TabsTrigger value="day">Day</TabsTrigger>
                  <TabsTrigger value="week">Week</TabsTrigger>
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
                          >
                            <div className="flex items-start justify-between gap-2">
                              <div>
                                <div className="flex items-center gap-2">
                                  <p className="font-medium">{apt.title}</p>
                                  <Badge
                                    className={
                                      appointmentTypeColors[apt.appointmentType] || ""
                                    }
                                  >
                                    {apt.appointmentType}
                                  </Badge>
                                </div>
                                <div className="mt-1 flex items-center gap-3 text-sm text-muted-foreground">
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
                              <Button variant="ghost" size="sm" asChild>
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
                <Button asChild>
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
    </div>
  );
}
