import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/hooks/use-toast";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { apiRequest, queryClient } from "@/lib/queryClient";
import { Bell, Calendar, Clock, MessageSquare, Phone, Mail, Send, CheckCircle, AlertTriangle, XCircle } from "lucide-react";
import type { Appointment, Patient, AppointmentReminder } from "@shared/schema";

const reminderFormSchema = z.object({
  appointmentId: z.number(),
  reminderType: z.string().min(1, "Type is required"),
  channel: z.string().min(1, "Channel is required"),
  scheduledFor: z.string().min(1, "Scheduled time is required"),
  message: z.string().optional(),
});

type ReminderFormData = z.infer<typeof reminderFormSchema>;

const reminderTypes = [
  { value: "confirmation", label: "Appointment Confirmation" },
  { value: "reminder_7day", label: "7-Day Reminder" },
  { value: "reminder_2day", label: "2-Day Reminder" },
  { value: "reminder_1day", label: "1-Day Reminder" },
  { value: "reminder_2hour", label: "2-Hour Reminder" },
  { value: "pre_surgery", label: "Pre-Surgery Instructions" },
  { value: "payment", label: "Payment Reminder" },
];

const channels = [
  { value: "sms", label: "SMS", icon: MessageSquare },
  { value: "email", label: "Email", icon: Mail },
  { value: "phone", label: "Phone Call", icon: Phone },
];

const formatDate = (date: string | Date | null) => {
  if (!date) return "N/A";
  return new Date(date).toLocaleDateString("en-US", { 
    weekday: "short", 
    month: "short", 
    day: "numeric", 
    year: "numeric",
    hour: "numeric",
    minute: "2-digit"
  });
};

export default function AppointmentRemindersPage() {
  const { toast } = useToast();
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [selectedAppointment, setSelectedAppointment] = useState<Appointment | null>(null);

  const { data: appointments = [], isLoading: loadingAppointments } = useQuery<Appointment[]>({
    queryKey: ["/api/appointments"],
  });

  const { data: reminders = [], isLoading: loadingReminders } = useQuery<AppointmentReminder[]>({
    queryKey: ["/api/reminders"],
  });

  const { data: patients = [] } = useQuery<Patient[]>({
    queryKey: ["/api/patients"],
  });

  const upcomingAppointments = appointments
    .filter(a => a.startTime && new Date(a.startTime) > new Date())
    .sort((a, b) => new Date(a.startTime).getTime() - new Date(b.startTime).getTime());

  const form = useForm<ReminderFormData>({
    resolver: zodResolver(reminderFormSchema),
    defaultValues: {
      appointmentId: 0,
      reminderType: "",
      channel: "sms",
      scheduledFor: "",
      message: "",
    },
  });

  const createReminderMutation = useMutation({
    mutationFn: async (data: ReminderFormData) => {
      const res = await apiRequest("POST", "/api/reminders", {
        ...data,
        scheduledFor: new Date(data.scheduledFor).toISOString(),
      });
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/reminders"] });
      setIsAddDialogOpen(false);
      form.reset();
      toast({ title: "Reminder Scheduled", description: "Reminder has been scheduled successfully" });
    },
    onError: (error: Error) => {
      toast({ title: "Error", description: error.message, variant: "destructive" });
    },
  });

  const sendReminderMutation = useMutation({
    mutationFn: async (reminderId: number) => {
      const res = await apiRequest("POST", `/api/reminders/${reminderId}/send`, {});
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/reminders"] });
      toast({ title: "Reminder Sent", description: "Reminder has been sent successfully" });
    },
    onError: (error: Error) => {
      toast({ title: "Error", description: error.message, variant: "destructive" });
    },
  });

  const onSubmit = (data: ReminderFormData) => {
    createReminderMutation.mutate(data);
  };

  const getPatientName = (patientId: number | null) => {
    if (!patientId) return "Unknown";
    const patient = patients.find(p => p.id === patientId);
    return patient ? `${patient.firstName} ${patient.lastName}` : "Unknown";
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "pending":
        return <Badge variant="outline"><Clock className="w-3 h-3 mr-1" /> Pending</Badge>;
      case "sent":
        return <Badge className="bg-blue-100 text-blue-800"><Send className="w-3 h-3 mr-1" /> Sent</Badge>;
      case "delivered":
        return <Badge className="bg-green-100 text-green-800"><CheckCircle className="w-3 h-3 mr-1" /> Delivered</Badge>;
      case "failed":
        return <Badge variant="destructive"><XCircle className="w-3 h-3 mr-1" /> Failed</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  const getChannelIcon = (channel: string) => {
    switch (channel) {
      case "sms": return <MessageSquare className="w-4 h-4" />;
      case "email": return <Mail className="w-4 h-4" />;
      case "phone": return <Phone className="w-4 h-4" />;
      default: return <Bell className="w-4 h-4" />;
    }
  };

  const pendingReminders = reminders.filter(r => r.status === "pending");
  const sentReminders = reminders.filter(r => r.status === "sent" || r.status === "delivered");

  return (
    <div className="flex-1 overflow-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold" data-testid="text-page-title">Appointment Reminders</h1>
          <p className="text-muted-foreground">Automated patient communication and follow-up tracking</p>
        </div>
        <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
          <DialogTrigger asChild>
            <Button data-testid="button-add-reminder">
              <Bell className="w-4 h-4 mr-2" />
              Schedule Reminder
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Schedule Reminder</DialogTitle>
              <DialogDescription>Set up automated patient reminders</DialogDescription>
            </DialogHeader>
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                <FormField
                  control={form.control}
                  name="appointmentId"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Appointment</FormLabel>
                      <Select onValueChange={(v) => field.onChange(parseInt(v))} value={field.value?.toString()}>
                        <FormControl>
                          <SelectTrigger data-testid="select-appointment">
                            <SelectValue placeholder="Select appointment" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {upcomingAppointments.map((apt) => (
                            <SelectItem key={apt.id} value={apt.id.toString()}>
                              {getPatientName(apt.patientId)} - {formatDate(apt.startTime)}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <div className="grid grid-cols-2 gap-4">
                  <FormField
                    control={form.control}
                    name="reminderType"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Reminder Type</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger data-testid="select-type">
                              <SelectValue placeholder="Select type" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {reminderTypes.map((opt) => (
                              <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="channel"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Channel</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger data-testid="select-channel">
                              <SelectValue placeholder="Select channel" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {channels.map((opt) => (
                              <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
                <FormField
                  control={form.control}
                  name="scheduledFor"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Schedule For</FormLabel>
                      <FormControl>
                        <Input {...field} type="datetime-local" data-testid="input-scheduled" />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="message"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Custom Message (Optional)</FormLabel>
                      <FormControl>
                        <Textarea {...field} placeholder="Leave blank for auto-generated message" data-testid="input-message" />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <div className="flex justify-end gap-2">
                  <Button type="button" variant="outline" onClick={() => setIsAddDialogOpen(false)}>
                    Cancel
                  </Button>
                  <Button type="submit" disabled={createReminderMutation.isPending} data-testid="button-submit-reminder">
                    {createReminderMutation.isPending ? "Scheduling..." : "Schedule Reminder"}
                  </Button>
                </div>
              </form>
            </Form>
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Pending Reminders</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold" data-testid="stat-pending">{pendingReminders.length}</div>
            <p className="text-xs text-muted-foreground">Scheduled to send</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Sent Today</CardTitle>
            <Send className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold" data-testid="stat-sent">{sentReminders.length}</div>
            <p className="text-xs text-muted-foreground">Successfully delivered</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Upcoming Appts</CardTitle>
            <Calendar className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold" data-testid="stat-upcoming">{upcomingAppointments.length}</div>
            <p className="text-xs text-muted-foreground">Need reminders</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Confirmation Rate</CardTitle>
            <CheckCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600" data-testid="stat-rate">94%</div>
            <p className="text-xs text-muted-foreground">Patients confirmed</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Clock className="w-5 h-5" />
              Pending Reminders
            </CardTitle>
            <CardDescription>Scheduled reminders waiting to be sent</CardDescription>
          </CardHeader>
          <CardContent>
            {loadingReminders ? (
              <p className="text-muted-foreground text-center py-4">Loading...</p>
            ) : pendingReminders.length === 0 ? (
              <div className="text-center py-8">
                <Bell className="w-12 h-12 mx-auto text-muted-foreground mb-2" />
                <p className="text-muted-foreground">No pending reminders</p>
              </div>
            ) : (
              <div className="space-y-3">
                {pendingReminders.map((reminder) => {
                  const appointment = appointments.find(a => a.id === reminder.appointmentId);
                  return (
                    <div key={reminder.id} className="flex items-center justify-between p-3 border rounded-lg" data-testid={`reminder-${reminder.id}`}>
                      <div className="flex items-center gap-3">
                        {getChannelIcon(reminder.channel)}
                        <div>
                          <p className="font-medium">{getPatientName(appointment?.patientId || null)}</p>
                          <p className="text-sm text-muted-foreground">
                            {reminder.reminderType.replace(/_/g, " ")} - {formatDate(reminder.scheduledFor)}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {getStatusBadge(reminder.status)}
                        <Button 
                          size="sm" 
                          onClick={() => sendReminderMutation.mutate(reminder.id)}
                          disabled={sendReminderMutation.isPending}
                          data-testid={`send-reminder-${reminder.id}`}
                        >
                          <Send className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Calendar className="w-5 h-5" />
              Upcoming Appointments
            </CardTitle>
            <CardDescription>Schedule reminders for upcoming visits</CardDescription>
          </CardHeader>
          <CardContent>
            {loadingAppointments ? (
              <p className="text-muted-foreground text-center py-4">Loading...</p>
            ) : upcomingAppointments.length === 0 ? (
              <div className="text-center py-8">
                <Calendar className="w-12 h-12 mx-auto text-muted-foreground mb-2" />
                <p className="text-muted-foreground">No upcoming appointments</p>
              </div>
            ) : (
              <div className="space-y-3">
                {upcomingAppointments.slice(0, 5).map((apt) => {
                  const aptReminders = reminders.filter(r => r.appointmentId === apt.id);
                  return (
                    <div key={apt.id} className="flex items-center justify-between p-3 border rounded-lg" data-testid={`appointment-${apt.id}`}>
                      <div>
                        <p className="font-medium">{getPatientName(apt.patientId)}</p>
                        <p className="text-sm text-muted-foreground">{formatDate(apt.startTime)}</p>
                        <p className="text-xs text-muted-foreground">{apt.appointmentType} - {apt.status}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge variant="outline">{aptReminders.length} reminders</Badge>
                        <Button 
                          size="sm" 
                          variant="outline"
                          onClick={() => {
                            form.setValue("appointmentId", apt.id);
                            setIsAddDialogOpen(true);
                          }}
                          data-testid={`add-reminder-${apt.id}`}
                        >
                          <Bell className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Reminder Templates</CardTitle>
          <CardDescription>Pre-configured reminder messages for common scenarios</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 border rounded-lg">
              <h4 className="font-semibold mb-2">Appointment Confirmation</h4>
              <p className="text-sm text-muted-foreground mb-3">
                "Hi [Name], this is a reminder of your appointment on [Date]. Reply YES to confirm or call us to reschedule."
              </p>
              <Badge variant="outline">SMS Recommended</Badge>
            </div>
            <div className="p-4 border rounded-lg">
              <h4 className="font-semibold mb-2">Pre-Surgery Instructions</h4>
              <p className="text-sm text-muted-foreground mb-3">
                "Your surgery is scheduled for [Date]. Please remember: no food after midnight, bring your insurance card and ID."
              </p>
              <Badge variant="outline">Email + SMS</Badge>
            </div>
            <div className="p-4 border rounded-lg">
              <h4 className="font-semibold mb-2">Payment Reminder</h4>
              <p className="text-sm text-muted-foreground mb-3">
                "Reminder: Your treatment balance of [Amount] is due. Payment plans available. Call us to discuss options."
              </p>
              <Badge variant="outline">Email Recommended</Badge>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
