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
  HeartPulse, Plus, Clock, CheckCircle, XCircle, 
  Phone, FileText, AlertCircle, User, Printer
} from "lucide-react";
import type { MedicalClearance, Patient } from "@shared/schema";

const clearanceFormSchema = z.object({
  patientId: z.number().min(1, "Patient is required"),
  clearanceType: z.string().min(1, "Clearance type is required"),
  physicianName: z.string().optional(),
  physicianPhone: z.string().optional(),
  physicianFax: z.string().optional(),
  clearanceNotes: z.string().optional(),
});

type ClearanceFormData = z.infer<typeof clearanceFormSchema>;

const clearanceTypes = [
  { value: "cardiac", label: "Cardiac Clearance" },
  { value: "diabetic", label: "Diabetic Clearance" },
  { value: "general", label: "General Medical Clearance" },
  { value: "anticoagulant", label: "Anticoagulant Management" },
  { value: "immunocompromised", label: "Immunocompromised Patient" },
  { value: "organ_transplant", label: "Organ Transplant" },
  { value: "bisphosphonate", label: "Bisphosphonate Review" },
];

export default function MedicalClearancePage() {
  const { toast } = useToast();
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const { data: clearances = [], isLoading } = useQuery<MedicalClearance[]>({
    queryKey: ["/api/medical-clearances"],
  });

  const { data: patients = [] } = useQuery<Patient[]>({
    queryKey: ["/api/patients"],
  });

  const form = useForm<ClearanceFormData>({
    resolver: zodResolver(clearanceFormSchema),
    defaultValues: {
      patientId: 0,
      clearanceType: "",
      physicianName: "",
      physicianPhone: "",
      physicianFax: "",
      clearanceNotes: "",
    },
  });

  const createClearanceMutation = useMutation({
    mutationFn: async (data: ClearanceFormData) => {
      const res = await apiRequest("POST", "/api/medical-clearances", data);
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/medical-clearances"] });
      setIsAddDialogOpen(false);
      form.reset();
      toast({ title: "Clearance Request Created", description: "Medical clearance request has been sent" });
    },
    onError: (error: Error) => {
      toast({ title: "Error", description: error.message, variant: "destructive" });
    },
  });

  const updateStatusMutation = useMutation({
    mutationFn: async ({ id, status, receivedDate }: { id: number; status: string; receivedDate?: Date }) => {
      const res = await apiRequest("PATCH", `/api/medical-clearances/${id}`, { 
        status, 
        receivedDate: receivedDate || (status === "approved" || status === "approved_with_restrictions" ? new Date() : undefined) 
      });
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/medical-clearances"] });
      toast({ title: "Status Updated", description: "Clearance status has been updated" });
    },
  });

  const onSubmit = (data: ClearanceFormData) => {
    createClearanceMutation.mutate(data);
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
        return <Badge className="bg-blue-100 text-blue-800"><FileText className="w-3 h-3 mr-1" /> Sent</Badge>;
      case "approved":
        return <Badge className="bg-green-100 text-green-800"><CheckCircle className="w-3 h-3 mr-1" /> Approved</Badge>;
      case "approved_with_restrictions":
        return <Badge className="bg-amber-100 text-amber-800"><AlertCircle className="w-3 h-3 mr-1" /> Approved w/ Restrictions</Badge>;
      case "denied":
        return <Badge variant="destructive"><XCircle className="w-3 h-3 mr-1" /> Denied</Badge>;
      case "expired":
        return <Badge variant="outline" className="text-muted-foreground"><Clock className="w-3 h-3 mr-1" /> Expired</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  const formatDate = (date: Date | string | null) => {
    if (!date) return "N/A";
    return new Date(date).toLocaleDateString();
  };

  const filteredClearances = statusFilter === "all" 
    ? clearances 
    : clearances.filter(c => c.status === statusFilter);

  const pendingCount = clearances.filter(c => c.status === "pending" || c.status === "sent").length;
  const approvedCount = clearances.filter(c => c.status === "approved" || c.status === "approved_with_restrictions").length;

  return (
    <div className="flex-1 overflow-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold" data-testid="text-page-title">Medical Clearance</h1>
          <p className="text-muted-foreground">Pre-surgery medical clearance tracking</p>
        </div>
        <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
          <DialogTrigger asChild>
            <Button data-testid="button-add-clearance">
              <Plus className="w-4 h-4 mr-2" />
              Request Clearance
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>Request Medical Clearance</DialogTitle>
              <DialogDescription>Submit a new medical clearance request for a patient</DialogDescription>
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
                    name="clearanceType"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Clearance Type</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger data-testid="select-clearance-type">
                              <SelectValue placeholder="Select type" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {clearanceTypes.map((type) => (
                              <SelectItem key={type.value} value={type.value}>{type.label}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
                <div className="grid grid-cols-3 gap-4">
                  <FormField
                    control={form.control}
                    name="physicianName"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Physician Name</FormLabel>
                        <FormControl>
                          <Input {...field} placeholder="Dr. Smith" data-testid="input-physician" />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="physicianPhone"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Phone</FormLabel>
                        <FormControl>
                          <Input {...field} placeholder="(555) 123-4567" data-testid="input-phone" />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="physicianFax"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Fax</FormLabel>
                        <FormControl>
                          <Input {...field} placeholder="(555) 123-4568" data-testid="input-fax" />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
                <FormField
                  control={form.control}
                  name="clearanceNotes"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Notes</FormLabel>
                      <FormControl>
                        <Textarea {...field} placeholder="Patient conditions, medications, special considerations..." data-testid="input-notes" />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <div className="flex justify-end gap-2">
                  <Button type="button" variant="outline" onClick={() => setIsAddDialogOpen(false)}>
                    Cancel
                  </Button>
                  <Button type="submit" disabled={createClearanceMutation.isPending} data-testid="button-submit">
                    {createClearanceMutation.isPending ? "Submitting..." : "Submit Request"}
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
            <CardTitle className="text-sm font-medium">Total Requests</CardTitle>
            <HeartPulse className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold" data-testid="stat-total">{clearances.length}</div>
            <p className="text-xs text-muted-foreground">All time</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Pending</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-amber-600" data-testid="stat-pending">{pendingCount}</div>
            <p className="text-xs text-muted-foreground">Awaiting response</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Approved</CardTitle>
            <CheckCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600" data-testid="stat-approved">{approvedCount}</div>
            <p className="text-xs text-muted-foreground">Ready for surgery</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Avg. Response Time</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold" data-testid="stat-avg-time">2.3 days</div>
            <p className="text-xs text-muted-foreground">Last 30 days</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Clearance Requests</CardTitle>
              <CardDescription>Medical clearance tracking for pre-surgery patients</CardDescription>
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-48" data-testid="filter-status">
                <SelectValue placeholder="Filter by status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Statuses</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="sent">Sent</SelectItem>
                <SelectItem value="approved">Approved</SelectItem>
                <SelectItem value="approved_with_restrictions">Approved w/ Restrictions</SelectItem>
                <SelectItem value="denied">Denied</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-muted-foreground text-center py-4">Loading...</p>
          ) : filteredClearances.length === 0 ? (
            <div className="text-center py-12">
              <HeartPulse className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium mb-2">No Clearance Requests</h3>
              <p className="text-muted-foreground mb-4">Request medical clearance for patients with health conditions</p>
              <Button onClick={() => setIsAddDialogOpen(true)} data-testid="button-add-first">
                <Plus className="w-4 h-4 mr-2" />
                Request Clearance
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              {filteredClearances.map((clearance) => (
                <div key={clearance.id} className="flex items-center justify-between p-4 border rounded-lg" data-testid={`clearance-row-${clearance.id}`}>
                  <div className="flex items-center gap-4">
                    <div className="flex items-center justify-center w-10 h-10 rounded-full bg-primary/10">
                      <User className="w-5 h-5 text-primary" />
                    </div>
                    <div>
                      <p className="font-semibold">{getPatientName(clearance.patientId)}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <Badge variant="outline">
                          {clearanceTypes.find(t => t.value === clearance.clearanceType)?.label || clearance.clearanceType}
                        </Badge>
                        {getStatusBadge(clearance.status)}
                      </div>
                      {clearance.physicianName && (
                        <p className="text-sm text-muted-foreground mt-1">
                          <Phone className="w-3 h-3 inline mr-1" /> {clearance.physicianName}
                          {clearance.physicianPhone && ` - ${clearance.physicianPhone}`}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="text-right text-sm">
                      <p>Requested: {formatDate(clearance.requestedDate)}</p>
                      {clearance.receivedDate && (
                        <p className="text-muted-foreground">Received: {formatDate(clearance.receivedDate)}</p>
                      )}
                    </div>
                    <div className="flex gap-2">
                      {clearance.status === "pending" && (
                        <>
                          <Button 
                            size="sm" 
                            variant="outline"
                            onClick={() => updateStatusMutation.mutate({ id: clearance.id, status: "sent" })}
                            data-testid={`send-${clearance.id}`}
                          >
                            Mark Sent
                          </Button>
                          <Button 
                            size="icon" 
                            variant="outline"
                            data-testid={`print-${clearance.id}`}
                          >
                            <Printer className="w-4 h-4" />
                          </Button>
                        </>
                      )}
                      {clearance.status === "sent" && (
                        <>
                          <Button 
                            size="sm"
                            onClick={() => updateStatusMutation.mutate({ id: clearance.id, status: "approved" })}
                            data-testid={`approve-${clearance.id}`}
                          >
                            Approved
                          </Button>
                          <Button 
                            size="sm" 
                            variant="outline"
                            onClick={() => updateStatusMutation.mutate({ id: clearance.id, status: "approved_with_restrictions" })}
                            data-testid={`approve-restrictions-${clearance.id}`}
                          >
                            w/ Restrictions
                          </Button>
                          <Button 
                            size="sm" 
                            variant="outline"
                            onClick={() => updateStatusMutation.mutate({ id: clearance.id, status: "denied" })}
                            data-testid={`deny-${clearance.id}`}
                          >
                            Denied
                          </Button>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="w-5 h-5" />
              Common Conditions
            </CardTitle>
            <CardDescription>Pre-surgery considerations for full arch patients</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="p-3 border rounded-lg">
                <h4 className="font-semibold text-sm">Cardiac Conditions</h4>
                <p className="text-xs text-muted-foreground mt-1">Heart disease, recent MI, pacemaker, valve replacement</p>
              </div>
              <div className="p-3 border rounded-lg">
                <h4 className="font-semibold text-sm">Diabetes Management</h4>
                <p className="text-xs text-muted-foreground mt-1">HbA1c levels, insulin management during surgery</p>
              </div>
              <div className="p-3 border rounded-lg">
                <h4 className="font-semibold text-sm">Anticoagulant Therapy</h4>
                <p className="text-xs text-muted-foreground mt-1">Warfarin, Eliquis, Plavix - bridging protocols</p>
              </div>
              <div className="p-3 border rounded-lg">
                <h4 className="font-semibold text-sm">Bisphosphonate Use</h4>
                <p className="text-xs text-muted-foreground mt-1">BRONJ risk assessment, drug holiday consideration</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertCircle className="w-5 h-5" />
              Clearance Guidelines
            </CardTitle>
            <CardDescription>When to request medical clearance</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-start gap-3">
                <div className="w-6 h-6 rounded-full bg-red-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <span className="text-xs font-bold text-red-600">!</span>
                </div>
                <div>
                  <h4 className="font-semibold text-sm">Always Required</h4>
                  <p className="text-xs text-muted-foreground">IV sedation, cardiac history, organ transplant, immunocompromised</p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="w-6 h-6 rounded-full bg-amber-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <span className="text-xs font-bold text-amber-600">?</span>
                </div>
                <div>
                  <h4 className="font-semibold text-sm">Case-by-Case</h4>
                  <p className="text-xs text-muted-foreground">Controlled diabetes, hypertension, osteoporosis</p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="w-6 h-6 rounded-full bg-green-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <CheckCircle className="w-3 h-3 text-green-600" />
                </div>
                <div>
                  <h4 className="font-semibold text-sm">Typically Not Required</h4>
                  <p className="text-xs text-muted-foreground">Healthy adults, well-controlled conditions, local anesthesia only</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
