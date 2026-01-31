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
  Syringe, Plus, Clock, CheckCircle, User, Play, Pause, 
  HeartPulse, FileText, Activity, AlertCircle, Sparkles
} from "lucide-react";
import type { SurgerySession, Patient, TreatmentPlan } from "@shared/schema";

const surgeryFormSchema = z.object({
  patientId: z.number().min(1, "Patient is required"),
  treatmentPlanId: z.number().optional(),
  surgeryDate: z.string().min(1, "Surgery date is required"),
  surgeryType: z.string().min(1, "Surgery type is required"),
  archTreated: z.string().min(1, "Arch is required"),
  surgeon: z.string().min(1, "Surgeon is required"),
  assistant: z.string().optional(),
  anesthesiaType: z.string().min(1, "Anesthesia type is required"),
  anesthesiologist: z.string().optional(),
});

type SurgeryFormData = z.infer<typeof surgeryFormSchema>;

const surgeryTypes = [
  { value: "all_on_4", label: "All-on-4" },
  { value: "all_on_6", label: "All-on-6" },
  { value: "implant_placement", label: "Implant Placement" },
  { value: "bone_graft", label: "Bone Graft" },
  { value: "sinus_lift", label: "Sinus Lift" },
  { value: "extraction_immediate", label: "Extraction + Immediate Implants" },
];

const anesthesiaTypes = [
  { value: "local", label: "Local Anesthesia" },
  { value: "oral_sedation", label: "Oral Sedation" },
  { value: "iv_sedation", label: "IV Sedation" },
  { value: "general", label: "General Anesthesia" },
];

export default function SurgeryDayPage() {
  const { toast } = useToast();
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [selectedSession, setSelectedSession] = useState<SurgerySession | null>(null);

  const { data: sessions = [], isLoading } = useQuery<SurgerySession[]>({
    queryKey: ["/api/surgery-sessions"],
  });

  const { data: patients = [] } = useQuery<Patient[]>({
    queryKey: ["/api/patients"],
  });

  const { data: treatmentPlans = [] } = useQuery<TreatmentPlan[]>({
    queryKey: ["/api/treatment-plans"],
  });

  const form = useForm<SurgeryFormData>({
    resolver: zodResolver(surgeryFormSchema),
    defaultValues: {
      patientId: 0,
      surgeryType: "",
      archTreated: "",
      surgeon: "",
      assistant: "",
      anesthesiaType: "",
      anesthesiologist: "",
      surgeryDate: new Date().toISOString().split('T')[0],
    },
  });

  const createSessionMutation = useMutation({
    mutationFn: async (data: SurgeryFormData) => {
      const res = await apiRequest("POST", "/api/surgery-sessions", {
        ...data,
        surgeryDate: new Date(data.surgeryDate),
        status: "scheduled",
      });
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/surgery-sessions"] });
      setIsAddDialogOpen(false);
      form.reset();
      toast({ title: "Surgery Scheduled", description: "Surgery session has been created" });
    },
    onError: (error: Error) => {
      toast({ title: "Error", description: error.message, variant: "destructive" });
    },
  });

  const updateSessionMutation = useMutation({
    mutationFn: async ({ id, updates }: { id: number; updates: Record<string, unknown> }) => {
      const res = await apiRequest("PATCH", `/api/surgery-sessions/${id}`, updates);
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/surgery-sessions"] });
      toast({ title: "Session Updated", description: "Surgery session has been updated" });
    },
  });

  const onSubmit = (data: SurgeryFormData) => {
    createSessionMutation.mutate(data);
  };

  const startSurgery = (session: SurgerySession) => {
    updateSessionMutation.mutate({
      id: session.id,
      updates: { startTime: new Date(), status: "in_progress" }
    });
  };

  const endSurgery = (session: SurgerySession) => {
    updateSessionMutation.mutate({
      id: session.id,
      updates: { endTime: new Date(), status: "completed" }
    });
  };

  const getPatientName = (patientId: number | null) => {
    if (!patientId) return "Unknown";
    const patient = patients.find(p => p.id === patientId);
    return patient ? `${patient.firstName} ${patient.lastName}` : "Unknown";
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "scheduled":
        return <Badge variant="outline"><Clock className="w-3 h-3 mr-1" /> Scheduled</Badge>;
      case "in_progress":
        return <Badge className="bg-blue-100 text-blue-800"><Activity className="w-3 h-3 mr-1" /> In Progress</Badge>;
      case "completed":
        return <Badge className="bg-green-100 text-green-800"><CheckCircle className="w-3 h-3 mr-1" /> Completed</Badge>;
      case "cancelled":
        return <Badge variant="destructive"><AlertCircle className="w-3 h-3 mr-1" /> Cancelled</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  const formatDate = (date: Date | string | null) => {
    if (!date) return "N/A";
    return new Date(date).toLocaleDateString();
  };

  const formatTime = (date: Date | string | null) => {
    if (!date) return "--:--";
    return new Date(date).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const calculateDuration = (start: Date | string | null, end: Date | string | null) => {
    if (!start || !end) return "N/A";
    const startTime = new Date(start).getTime();
    const endTime = new Date(end).getTime();
    const durationMs = endTime - startTime;
    const hours = Math.floor(durationMs / (1000 * 60 * 60));
    const minutes = Math.floor((durationMs % (1000 * 60 * 60)) / (1000 * 60));
    return `${hours}h ${minutes}m`;
  };

  const todaySessions = sessions.filter(s => {
    const today = new Date().toDateString();
    return new Date(s.surgeryDate).toDateString() === today;
  });

  const inProgressCount = sessions.filter(s => s.status === "in_progress").length;
  const completedToday = todaySessions.filter(s => s.status === "completed").length;

  return (
    <div className="flex-1 overflow-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold" data-testid="text-page-title">Surgery Day</h1>
          <p className="text-muted-foreground">Real-time surgery tracking and documentation</p>
        </div>
        <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
          <DialogTrigger asChild>
            <Button data-testid="button-add-surgery">
              <Plus className="w-4 h-4 mr-2" />
              Schedule Surgery
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>Schedule Surgery</DialogTitle>
              <DialogDescription>Create a new surgery session</DialogDescription>
            </DialogHeader>
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
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
                  <FormField
                    control={form.control}
                    name="surgeryDate"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Surgery Date</FormLabel>
                        <FormControl>
                          <Input {...field} type="date" data-testid="input-date" />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <FormField
                    control={form.control}
                    name="surgeryType"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Surgery Type</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger data-testid="select-type">
                              <SelectValue placeholder="Select type" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {surgeryTypes.map((type) => (
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
                    name="archTreated"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Arch Treated</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger data-testid="select-arch">
                              <SelectValue placeholder="Select arch" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            <SelectItem value="upper">Upper Arch</SelectItem>
                            <SelectItem value="lower">Lower Arch</SelectItem>
                            <SelectItem value="both">Both Arches</SelectItem>
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <FormField
                    control={form.control}
                    name="surgeon"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Surgeon</FormLabel>
                        <FormControl>
                          <Input {...field} placeholder="Dr. Smith" data-testid="input-surgeon" />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="assistant"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Surgical Assistant</FormLabel>
                        <FormControl>
                          <Input {...field} placeholder="Assistant name" data-testid="input-assistant" />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <FormField
                    control={form.control}
                    name="anesthesiaType"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Anesthesia Type</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger data-testid="select-anesthesia">
                              <SelectValue placeholder="Select type" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {anesthesiaTypes.map((type) => (
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
                    name="anesthesiologist"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Anesthesiologist</FormLabel>
                        <FormControl>
                          <Input {...field} placeholder="Optional" data-testid="input-anesthesiologist" />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
                <div className="flex justify-end gap-2">
                  <Button type="button" variant="outline" onClick={() => setIsAddDialogOpen(false)}>
                    Cancel
                  </Button>
                  <Button type="submit" disabled={createSessionMutation.isPending} data-testid="button-submit">
                    {createSessionMutation.isPending ? "Scheduling..." : "Schedule Surgery"}
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
            <CardTitle className="text-sm font-medium">Today's Surgeries</CardTitle>
            <Syringe className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold" data-testid="stat-today">{todaySessions.length}</div>
            <p className="text-xs text-muted-foreground">Scheduled for today</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">In Progress</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600" data-testid="stat-active">{inProgressCount}</div>
            <p className="text-xs text-muted-foreground">Currently operating</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Completed Today</CardTitle>
            <CheckCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600" data-testid="stat-completed">{completedToday}</div>
            <p className="text-xs text-muted-foreground">Successful surgeries</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">All Sessions</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold" data-testid="stat-total">{sessions.length}</div>
            <p className="text-xs text-muted-foreground">Total surgeries</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle>Surgery Sessions</CardTitle>
            <CardDescription>Track and manage surgical procedures</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <p className="text-muted-foreground text-center py-4">Loading...</p>
            ) : sessions.length === 0 ? (
              <div className="text-center py-12">
                <Syringe className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
                <h3 className="text-lg font-medium mb-2">No Surgery Sessions</h3>
                <p className="text-muted-foreground mb-4">Schedule your first surgery session</p>
                <Button onClick={() => setIsAddDialogOpen(true)} data-testid="button-add-first">
                  <Plus className="w-4 h-4 mr-2" />
                  Schedule Surgery
                </Button>
              </div>
            ) : (
              <div className="space-y-3">
                {sessions.map((session) => (
                  <div key={session.id} className="flex items-center justify-between p-4 border rounded-lg" data-testid={`session-row-${session.id}`}>
                    <div className="flex items-center gap-4">
                      <div className="flex items-center justify-center w-12 h-12 rounded-full bg-primary/10">
                        <User className="w-6 h-6 text-primary" />
                      </div>
                      <div>
                        <p className="font-semibold text-lg">{getPatientName(session.patientId)}</p>
                        <div className="flex items-center gap-2 mt-1">
                          <Badge variant="outline">
                            {surgeryTypes.find(t => t.value === session.surgeryType)?.label || session.surgeryType}
                          </Badge>
                          <Badge variant="outline">{session.archTreated} arch</Badge>
                          {getStatusBadge(session.status)}
                        </div>
                        <p className="text-sm text-muted-foreground mt-1">
                          {formatDate(session.surgeryDate)} | {session.surgeon}
                          {session.anesthesiaType && ` | ${anesthesiaTypes.find(a => a.value === session.anesthesiaType)?.label}`}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="text-right text-sm">
                        <p>Start: {formatTime(session.startTime)}</p>
                        <p>End: {formatTime(session.endTime)}</p>
                        {session.startTime && session.endTime && (
                          <p className="text-muted-foreground">
                            Duration: {calculateDuration(session.startTime, session.endTime)}
                          </p>
                        )}
                      </div>
                      <div className="flex gap-2">
                        {session.status === "scheduled" && (
                          <Button 
                            size="sm"
                            onClick={() => startSurgery(session)}
                            data-testid={`start-${session.id}`}
                          >
                            <Play className="w-4 h-4 mr-1" />
                            Start
                          </Button>
                        )}
                        {session.status === "in_progress" && (
                          <Button 
                            size="sm"
                            onClick={() => endSurgery(session)}
                            data-testid={`end-${session.id}`}
                          >
                            <Pause className="w-4 h-4 mr-1" />
                            End
                          </Button>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <HeartPulse className="w-5 h-5" />
                Anesthesia Monitoring
              </CardTitle>
              <CardDescription>Real-time vital signs</CardDescription>
            </CardHeader>
            <CardContent>
              {inProgressCount > 0 ? (
                <div className="space-y-4">
                  <div className="flex justify-between items-center">
                    <span className="text-sm">Heart Rate</span>
                    <span className="font-mono font-bold text-lg">72 bpm</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm">Blood Pressure</span>
                    <span className="font-mono font-bold text-lg">120/80</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm">O2 Saturation</span>
                    <span className="font-mono font-bold text-lg text-green-600">98%</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm">Temperature</span>
                    <span className="font-mono font-bold text-lg">98.6°F</span>
                  </div>
                </div>
              ) : (
                <p className="text-muted-foreground text-center py-4">No active surgery</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="w-5 h-5" />
                AI Surgery Notes
              </CardTitle>
              <CardDescription>AI-powered documentation</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <p className="text-sm text-muted-foreground">
                  AI surgery notes will be auto-generated during and after procedures based on:
                </p>
                <ul className="text-sm space-y-1 text-muted-foreground">
                  <li>• Implant placement details</li>
                  <li>• Bone quality observations</li>
                  <li>• Prosthesis specifications</li>
                  <li>• Complications (if any)</li>
                </ul>
                <Button variant="outline" className="w-full mt-4" disabled={inProgressCount === 0}>
                  <Sparkles className="w-4 h-4 mr-2" />
                  Generate Notes
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
