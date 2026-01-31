import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/hooks/use-toast";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { apiRequest, queryClient } from "@/lib/queryClient";
import { 
  Wrench, Plus, Calendar, Clock, CheckCircle, AlertCircle, RefreshCcw
} from "lucide-react";
import type { MaintenanceAppointment, Patient } from "@shared/schema";

const maintenanceFormSchema = z.object({
  patientId: z.number().min(1, "Patient is required"),
  maintenanceType: z.string().min(1, "Maintenance type is required"),
  scheduledDate: z.string().min(1, "Date is required"),
  notes: z.string().optional(),
});

type MaintenanceFormData = z.infer<typeof maintenanceFormSchema>;

const appointmentTypes = [
  { value: "cleaning_6mo", label: "6-Month Cleaning" },
  { value: "cleaning_annual", label: "Annual Cleaning" },
  { value: "checkup", label: "Routine Check-Up" },
  { value: "screw_tightening", label: "Screw Tightening" },
  { value: "occlusion_check", label: "Occlusion Adjustment" },
  { value: "xray", label: "X-Ray Review" },
  { value: "hygiene", label: "Hygiene Maintenance" },
];

export default function MaintenancePage() {
  const { toast } = useToast();
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);

  const { data: appointments = [], isLoading } = useQuery<MaintenanceAppointment[]>({
    queryKey: ["/api/maintenance"],
  });

  const { data: patients = [] } = useQuery<Patient[]>({
    queryKey: ["/api/patients"],
  });

  const form = useForm<MaintenanceFormData>({
    resolver: zodResolver(maintenanceFormSchema),
    defaultValues: {
      patientId: 0,
      maintenanceType: "",
      scheduledDate: "",
      notes: "",
    },
  });

  const createAppointmentMutation = useMutation({
    mutationFn: async (data: MaintenanceFormData) => {
      const res = await apiRequest("POST", "/api/maintenance", {
        patientId: data.patientId,
        maintenanceType: data.maintenanceType,
        scheduledDate: new Date(data.scheduledDate).toISOString(),
        notes: data.notes || null,
      });
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/maintenance"] });
      setIsAddDialogOpen(false);
      form.reset();
      toast({ title: "Appointment Scheduled", description: "Maintenance appointment has been added" });
    },
    onError: (error: Error) => {
      toast({ title: "Error", description: error.message, variant: "destructive" });
    },
  });

  const updateAppointmentMutation = useMutation({
    mutationFn: async ({ id, updates }: { id: number; updates: Record<string, unknown> }) => {
      const res = await apiRequest("PATCH", `/api/maintenance/${id}`, updates);
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/maintenance"] });
      toast({ title: "Updated", description: "Appointment status updated" });
    },
  });

  const onSubmit = (data: MaintenanceFormData) => {
    createAppointmentMutation.mutate(data);
  };

  const getPatientName = (patientId: number | null) => {
    if (!patientId) return "Unknown";
    const patient = patients.find(p => p.id === patientId);
    return patient ? `${patient.firstName} ${patient.lastName}` : "Unknown";
  };

  const formatDate = (date: Date | string | null) => {
    if (!date) return "N/A";
    return new Date(date).toLocaleDateString();
  };

  const completeAppointment = (id: number) => {
    updateAppointmentMutation.mutate({
      id,
      updates: { completedDate: new Date() }
    });
  };

  const upcomingCount = appointments.filter(a => 
    !a.completedDate && new Date(a.scheduledDate) >= new Date()
  ).length;
  
  const overdueCount = appointments.filter(a => 
    !a.completedDate && new Date(a.scheduledDate) < new Date()
  ).length;
  
  const completedCount = appointments.filter(a => a.completedDate).length;

  return (
    <div className="flex-1 overflow-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold" data-testid="text-page-title">Maintenance Schedule</h1>
          <p className="text-muted-foreground">Long-term care and cleaning appointments</p>
        </div>
        <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
          <DialogTrigger asChild>
            <Button data-testid="button-add-appointment">
              <Plus className="w-4 h-4 mr-2" />
              Schedule Maintenance
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle>Schedule Maintenance</DialogTitle>
              <DialogDescription>Add a maintenance appointment</DialogDescription>
            </DialogHeader>
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                <FormField
                  control={form.control}
                  name="patientId"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Patient</FormLabel>
                      <Select onValueChange={(v) => field.onChange(parseInt(v))} value={field.value?.toString()}>
                        <FormControl>
                          <SelectTrigger data-testid="select-patient">
                            <SelectValue placeholder="Select patient" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {patients.map((patient) => (
                            <SelectItem key={patient.id} value={patient.id.toString()}>
                              {patient.firstName} {patient.lastName}
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
                    name="maintenanceType"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Maintenance Type</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger data-testid="select-type">
                              <SelectValue placeholder="Select type" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {appointmentTypes.map((type) => (
                              <SelectItem key={type.value} value={type.value}>{type.label}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="scheduledDate"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Date</FormLabel>
                        <FormControl>
                          <Input {...field} type="date" data-testid="input-date" />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
                <FormField
                  control={form.control}
                  name="notes"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Notes</FormLabel>
                      <FormControl>
                        <Textarea {...field} placeholder="Appointment notes..." data-testid="input-notes" />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <div className="flex justify-end gap-2">
                  <Button type="button" variant="outline" onClick={() => setIsAddDialogOpen(false)}>
                    Cancel
                  </Button>
                  <Button type="submit" disabled={createAppointmentMutation.isPending} data-testid="button-submit">
                    {createAppointmentMutation.isPending ? "Scheduling..." : "Schedule"}
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
            <CardTitle className="text-sm font-medium">Upcoming</CardTitle>
            <Calendar className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600" data-testid="stat-upcoming">{upcomingCount}</div>
            <p className="text-xs text-muted-foreground">Scheduled appointments</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Overdue</CardTitle>
            <AlertCircle className="h-4 w-4 text-red-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600" data-testid="stat-overdue">{overdueCount}</div>
            <p className="text-xs text-muted-foreground">Need rescheduling</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Completed</CardTitle>
            <CheckCircle className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600" data-testid="stat-completed">{completedCount}</div>
            <p className="text-xs text-muted-foreground">This year</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Total</CardTitle>
            <RefreshCcw className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold" data-testid="stat-total">{appointments.length}</div>
            <p className="text-xs text-muted-foreground">All maintenance</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Maintenance Appointments</CardTitle>
          <CardDescription>Regular cleaning and care schedule</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-muted-foreground text-center py-4">Loading...</p>
          ) : appointments.length === 0 ? (
            <div className="text-center py-12">
              <Wrench className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium mb-2">No Maintenance Scheduled</h3>
              <p className="text-muted-foreground mb-4">Schedule cleaning and care appointments</p>
              <Button onClick={() => setIsAddDialogOpen(true)} data-testid="button-add-first">
                <Plus className="w-4 h-4 mr-2" />
                Schedule Maintenance
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              {appointments.map((appointment) => {
                const isOverdue = !appointment.completedDate && new Date(appointment.scheduledDate) < new Date();
                const isCompleted = !!appointment.completedDate;
                
                return (
                  <div key={appointment.id} className="flex items-center justify-between p-4 border rounded-lg" data-testid={`appointment-${appointment.id}`}>
                    <div className="flex items-center gap-4">
                      <div className="flex items-center justify-center w-12 h-12 rounded-full bg-primary/10">
                        {isCompleted ? (
                          <CheckCircle className="w-6 h-6 text-green-500" />
                        ) : isOverdue ? (
                          <AlertCircle className="w-6 h-6 text-red-500" />
                        ) : (
                          <Calendar className="w-6 h-6 text-blue-500" />
                        )}
                      </div>
                      <div>
                        <p className="font-semibold text-lg">{getPatientName(appointment.patientId)}</p>
                        <div className="flex items-center gap-2 mt-1">
                          <Badge variant="outline">
                            {appointmentTypes.find(t => t.value === appointment.maintenanceType)?.label || appointment.maintenanceType}
                          </Badge>
                          {isCompleted ? (
                            <Badge className="bg-green-100 text-green-800">Completed</Badge>
                          ) : isOverdue ? (
                            <Badge variant="destructive">Overdue</Badge>
                          ) : (
                            <Badge className="bg-blue-100 text-blue-800">Scheduled</Badge>
                          )}
                        </div>
                        <p className="text-sm text-muted-foreground mt-1">
                          {formatDate(appointment.scheduledDate)}
                        </p>
                      </div>
                    </div>
                    {!isCompleted && (
                      <Button 
                        size="sm" 
                        onClick={() => completeAppointment(appointment.id)}
                        data-testid={`complete-${appointment.id}`}
                      >
                        <CheckCircle className="w-4 h-4 mr-1" />
                        Complete
                      </Button>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
