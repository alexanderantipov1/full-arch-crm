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
import { Checkbox } from "@/components/ui/checkbox";
import { useToast } from "@/hooks/use-toast";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { apiRequest, queryClient } from "@/lib/queryClient";
import { 
  Stethoscope, Plus, Clock, CheckCircle, Calendar, 
  Camera, Heart, AlertCircle, ClipboardCheck
} from "lucide-react";
import type { PostOpVisit, Patient } from "@shared/schema";

const postOpFormSchema = z.object({
  patientId: z.number().min(1, "Patient is required"),
  visitType: z.string().min(1, "Visit type is required"),
  visitDate: z.string().min(1, "Visit date is required"),
  daysSinceSurgery: z.number().optional(),
  healingStatus: z.string().optional(),
  notes: z.string().optional(),
});

type PostOpFormData = z.infer<typeof postOpFormSchema>;

const visitTypes = [
  { value: "24_hour", label: "24-Hour Post-Op Check" },
  { value: "1_week", label: "1-Week Follow-Up" },
  { value: "2_week", label: "2-Week Follow-Up" },
  { value: "1_month", label: "1-Month Check" },
  { value: "3_month", label: "3-Month Follow-Up" },
  { value: "6_month", label: "6-Month Follow-Up" },
  { value: "try_in", label: "Prosthesis Try-In" },
  { value: "final_delivery", label: "Final Prosthesis Delivery" },
  { value: "adjustment", label: "Adjustment Visit" },
  { value: "emergency", label: "Emergency Visit" },
];

const healingStatuses = [
  { value: "excellent", label: "Excellent - Healing as expected" },
  { value: "good", label: "Good - Minor issues" },
  { value: "fair", label: "Fair - Requires monitoring" },
  { value: "poor", label: "Poor - Intervention needed" },
  { value: "complications", label: "Complications Present" },
];

export default function PostOpPage() {
  const { toast } = useToast();
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);

  const { data: visits = [], isLoading } = useQuery<PostOpVisit[]>({
    queryKey: ["/api/post-op-visits"],
  });

  const { data: patients = [] } = useQuery<Patient[]>({
    queryKey: ["/api/patients"],
  });

  const form = useForm<PostOpFormData>({
    resolver: zodResolver(postOpFormSchema),
    defaultValues: {
      patientId: 0,
      visitType: "",
      visitDate: new Date().toISOString().split('T')[0],
      healingStatus: "",
      notes: "",
    },
  });

  const createVisitMutation = useMutation({
    mutationFn: async (data: PostOpFormData) => {
      const res = await apiRequest("POST", "/api/post-op-visits", {
        ...data,
        visitDate: new Date(data.visitDate),
      });
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/post-op-visits"] });
      setIsAddDialogOpen(false);
      form.reset();
      toast({ title: "Visit Scheduled", description: "Post-op visit has been created" });
    },
    onError: (error: Error) => {
      toast({ title: "Error", description: error.message, variant: "destructive" });
    },
  });

  const updateVisitMutation = useMutation({
    mutationFn: async ({ id, updates }: { id: number; updates: Record<string, unknown> }) => {
      const res = await apiRequest("PATCH", `/api/post-op-visits/${id}`, updates);
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/post-op-visits"] });
      toast({ title: "Updated", description: "Visit has been updated" });
    },
  });

  const onSubmit = (data: PostOpFormData) => {
    createVisitMutation.mutate(data);
  };

  const getPatientName = (patientId: number | null) => {
    if (!patientId) return "Unknown";
    const patient = patients.find(p => p.id === patientId);
    return patient ? `${patient.firstName} ${patient.lastName}` : "Unknown";
  };

  const getHealingBadge = (status: string | null) => {
    if (!status) return <Badge variant="outline">Not assessed</Badge>;
    const statusColors: Record<string, string> = {
      excellent: "bg-green-100 text-green-800",
      good: "bg-blue-100 text-blue-800",
      fair: "bg-yellow-100 text-yellow-800",
      poor: "bg-orange-100 text-orange-800",
      complications: "bg-red-100 text-red-800",
    };
    return (
      <Badge className={statusColors[status] || ""}>
        {healingStatuses.find(s => s.value === status)?.label.split(" - ")[0] || status}
      </Badge>
    );
  };

  const formatDate = (date: Date | string | null) => {
    if (!date) return "N/A";
    return new Date(date).toLocaleDateString();
  };

  const toggleCheck = (visitId: number, field: string, currentValue: boolean | null) => {
    updateVisitMutation.mutate({ 
      id: visitId, 
      updates: { [field]: !currentValue } 
    });
  };

  const upcomingVisits = visits.filter(v => new Date(v.visitDate) >= new Date()).length;
  const deliveriesScheduled = visits.filter(v => v.visitType === "final_delivery").length;
  const completedToday = visits.filter(v => {
    const today = new Date().toDateString();
    return new Date(v.visitDate).toDateString() === today;
  }).length;

  return (
    <div className="flex-1 overflow-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold" data-testid="text-page-title">Post-Op & Delivery</h1>
          <p className="text-muted-foreground">Follow-up visits and final prosthesis delivery tracking</p>
        </div>
        <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
          <DialogTrigger asChild>
            <Button data-testid="button-add-visit">
              <Plus className="w-4 h-4 mr-2" />
              Schedule Visit
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle>Schedule Post-Op Visit</DialogTitle>
              <DialogDescription>Add a new follow-up or delivery appointment</DialogDescription>
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
                    name="visitType"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Visit Type</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger data-testid="select-type">
                              <SelectValue placeholder="Select type" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {visitTypes.map((type) => (
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
                    name="visitDate"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Visit Date</FormLabel>
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
                  name="healingStatus"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Healing Status (Optional)</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl>
                          <SelectTrigger data-testid="select-healing">
                            <SelectValue placeholder="Assess after visit" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {healingStatuses.map((status) => (
                            <SelectItem key={status.value} value={status.value}>{status.label}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="notes"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Notes</FormLabel>
                      <FormControl>
                        <Textarea {...field} placeholder="Visit notes..." data-testid="input-notes" />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <div className="flex justify-end gap-2">
                  <Button type="button" variant="outline" onClick={() => setIsAddDialogOpen(false)}>
                    Cancel
                  </Button>
                  <Button type="submit" disabled={createVisitMutation.isPending} data-testid="button-submit">
                    {createVisitMutation.isPending ? "Scheduling..." : "Schedule Visit"}
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
            <CardTitle className="text-sm font-medium">Upcoming Visits</CardTitle>
            <Calendar className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold" data-testid="stat-upcoming">{upcomingVisits}</div>
            <p className="text-xs text-muted-foreground">Scheduled follow-ups</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Deliveries</CardTitle>
            <CheckCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600" data-testid="stat-deliveries">{deliveriesScheduled}</div>
            <p className="text-xs text-muted-foreground">Final prosthesis</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Today</CardTitle>
            <Stethoscope className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600" data-testid="stat-today">{completedToday}</div>
            <p className="text-xs text-muted-foreground">Visits today</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Total</CardTitle>
            <ClipboardCheck className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold" data-testid="stat-total">{visits.length}</div>
            <p className="text-xs text-muted-foreground">All visits</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Post-Op Visits</CardTitle>
          <CardDescription>Follow-up appointments and prosthesis deliveries</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-muted-foreground text-center py-4">Loading...</p>
          ) : visits.length === 0 ? (
            <div className="text-center py-12">
              <Stethoscope className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium mb-2">No Post-Op Visits</h3>
              <p className="text-muted-foreground mb-4">Schedule your first follow-up visit</p>
              <Button onClick={() => setIsAddDialogOpen(true)} data-testid="button-add-first">
                <Plus className="w-4 h-4 mr-2" />
                Schedule Visit
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              {visits.map((visit) => (
                <div key={visit.id} className="flex items-center justify-between p-4 border rounded-lg" data-testid={`visit-row-${visit.id}`}>
                  <div className="flex items-center gap-4">
                    <div className="flex items-center justify-center w-12 h-12 rounded-full bg-primary/10">
                      {visit.visitType === "final_delivery" ? (
                        <CheckCircle className="w-6 h-6 text-green-600" />
                      ) : (
                        <Stethoscope className="w-6 h-6 text-primary" />
                      )}
                    </div>
                    <div>
                      <p className="font-semibold text-lg">{getPatientName(visit.patientId)}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <Badge variant="outline">
                          {visitTypes.find(t => t.value === visit.visitType)?.label || visit.visitType}
                        </Badge>
                        {getHealingBadge(visit.healingStatus)}
                      </div>
                      <p className="text-sm text-muted-foreground mt-1">
                        {formatDate(visit.visitDate)}
                        {visit.daysSinceSurgery && ` | Day ${visit.daysSinceSurgery} post-op`}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="flex flex-col gap-2">
                      <div className="flex items-center gap-2">
                        <Checkbox 
                          checked={visit.suturesRemoved || false}
                          onCheckedChange={() => toggleCheck(visit.id, "suturesRemoved", visit.suturesRemoved)}
                          data-testid={`sutures-${visit.id}`}
                        />
                        <span className="text-sm">Sutures removed</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Checkbox 
                          checked={visit.screwsTightened || false}
                          onCheckedChange={() => toggleCheck(visit.id, "screwsTightened", visit.screwsTightened)}
                          data-testid={`screws-${visit.id}`}
                        />
                        <span className="text-sm">Screws tightened</span>
                      </div>
                    </div>
                    <Button variant="outline" size="sm" data-testid={`photos-${visit.id}`}>
                      <Camera className="w-4 h-4 mr-1" />
                      Photos
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
