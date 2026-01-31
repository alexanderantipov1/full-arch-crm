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
  Wrench, Plus, Clock, CheckCircle, Package, Truck, 
  AlertCircle, Palette, FileText, DollarSign
} from "lucide-react";
import type { LabCase, Patient } from "@shared/schema";

const labCaseFormSchema = z.object({
  patientId: z.number().min(1, "Patient is required"),
  caseType: z.string().min(1, "Case type is required"),
  labName: z.string().optional(),
  prosthesisType: z.string().min(1, "Prosthesis type is required"),
  materialType: z.string().min(1, "Material is required"),
  shade: z.string().optional(),
  notes: z.string().optional(),
});

type LabCaseFormData = z.infer<typeof labCaseFormSchema>;

const caseTypes = [
  { value: "temporary", label: "Temporary Prosthesis (PMMA)" },
  { value: "final_design", label: "Final Design" },
  { value: "try_in", label: "Try-In" },
  { value: "final_prosthesis", label: "Final Prosthesis" },
  { value: "repair", label: "Repair" },
  { value: "replacement", label: "Replacement" },
];

const prosthesisTypes = [
  { value: "fp1", label: "FP-1 (Fixed Complete Denture)" },
  { value: "fp2", label: "FP-2 (Fixed Complete Denture w/ Pink)" },
  { value: "fp3", label: "FP-3 (Hybrid with Metal Frame)" },
];

const materialTypes = [
  { value: "solid_zirconia", label: "Solid Zirconia", price: "Premium" },
  { value: "zirconia_pmma", label: "Zirconia + PMMA", price: "Standard" },
  { value: "titanium_acrylic", label: "Titanium Bar + Acrylic", price: "Value" },
  { value: "titanium_zirconia", label: "Titanium Bar + Zirconia", price: "Premium+" },
  { value: "pmma_temp", label: "PMMA (Temporary)", price: "Temporary" },
  { value: "peek", label: "PEEK Framework", price: "Alternative" },
];

const statusOptions = [
  { value: "pending", label: "Pending", color: "outline" },
  { value: "design_in_progress", label: "Design In Progress", color: "blue" },
  { value: "sent_to_lab", label: "Sent to Lab", color: "purple" },
  { value: "in_fabrication", label: "In Fabrication", color: "orange" },
  { value: "shipped", label: "Shipped", color: "cyan" },
  { value: "received", label: "Received", color: "green" },
  { value: "try_in_scheduled", label: "Try-In Scheduled", color: "yellow" },
  { value: "completed", label: "Completed", color: "green" },
];

export default function LabPage() {
  const { toast } = useToast();
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);

  const { data: labCases = [], isLoading } = useQuery<LabCase[]>({
    queryKey: ["/api/lab-cases"],
  });

  const { data: patients = [] } = useQuery<Patient[]>({
    queryKey: ["/api/patients"],
  });

  const form = useForm<LabCaseFormData>({
    resolver: zodResolver(labCaseFormSchema),
    defaultValues: {
      patientId: 0,
      caseType: "",
      labName: "",
      prosthesisType: "",
      materialType: "",
      shade: "",
      notes: "",
    },
  });

  const createCaseMutation = useMutation({
    mutationFn: async (data: LabCaseFormData) => {
      const res = await apiRequest("POST", "/api/lab-cases", {
        ...data,
        status: "pending",
        designIncluded: 2,
        designsUsed: 0,
      });
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/lab-cases"] });
      setIsAddDialogOpen(false);
      form.reset();
      toast({ title: "Lab Case Created", description: "New lab case has been added" });
    },
    onError: (error: Error) => {
      toast({ title: "Error", description: error.message, variant: "destructive" });
    },
  });

  const updateCaseMutation = useMutation({
    mutationFn: async ({ id, updates }: { id: number; updates: Record<string, unknown> }) => {
      const res = await apiRequest("PATCH", `/api/lab-cases/${id}`, updates);
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/lab-cases"] });
      toast({ title: "Updated", description: "Lab case has been updated" });
    },
  });

  const onSubmit = (data: LabCaseFormData) => {
    createCaseMutation.mutate(data);
  };

  const getPatientName = (patientId: number | null) => {
    if (!patientId) return "Unknown";
    const patient = patients.find(p => p.id === patientId);
    return patient ? `${patient.firstName} ${patient.lastName}` : "Unknown";
  };

  const getStatusBadge = (status: string) => {
    const statusInfo = statusOptions.find(s => s.value === status) || { label: status, color: "outline" };
    const colorClasses: Record<string, string> = {
      outline: "",
      blue: "bg-blue-100 text-blue-800",
      purple: "bg-purple-100 text-purple-800",
      orange: "bg-orange-100 text-orange-800",
      cyan: "bg-cyan-100 text-cyan-800",
      green: "bg-green-100 text-green-800",
      yellow: "bg-yellow-100 text-yellow-800",
    };
    return (
      <Badge className={colorClasses[statusInfo.color] || ""} variant={statusInfo.color === "outline" ? "outline" : "default"}>
        {statusInfo.label}
      </Badge>
    );
  };

  const updateStatus = (caseId: number, newStatus: string) => {
    const updates: Record<string, unknown> = { status: newStatus };
    if (newStatus === "sent_to_lab") {
      updates.sentToLabDate = new Date();
    } else if (newStatus === "received") {
      updates.receivedDate = new Date();
    }
    updateCaseMutation.mutate({ id: caseId, updates });
  };

  const addDesignRevision = (caseId: number, currentUsed: number, included: number) => {
    const newUsed = currentUsed + 1;
    const updates: Record<string, unknown> = { designsUsed: newUsed };
    if (newUsed > included) {
      updates.additionalDesignFee = String((newUsed - included) * 150);
    }
    updateCaseMutation.mutate({ id: caseId, updates });
  };

  const pendingCount = labCases.filter(c => c.status === "pending").length;
  const inProgressCount = labCases.filter(c => ["design_in_progress", "sent_to_lab", "in_fabrication"].includes(c.status)).length;
  const shippedCount = labCases.filter(c => c.status === "shipped").length;

  return (
    <div className="flex-1 overflow-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold" data-testid="text-page-title">Lab & Design</h1>
          <p className="text-muted-foreground">Manage lab cases, prosthesis design, and revisions</p>
        </div>
        <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
          <DialogTrigger asChild>
            <Button data-testid="button-add-case">
              <Plus className="w-4 h-4 mr-2" />
              New Lab Case
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>Create Lab Case</DialogTitle>
              <DialogDescription>Add a new prosthesis fabrication case</DialogDescription>
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
                    name="caseType"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Case Type</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger data-testid="select-case-type">
                              <SelectValue placeholder="Select type" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {caseTypes.map((type) => (
                              <SelectItem key={type.value} value={type.value}>{type.label}</SelectItem>
                            ))}
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
                    name="prosthesisType"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Prosthesis Type</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger data-testid="select-prosthesis">
                              <SelectValue placeholder="Select type" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {prosthesisTypes.map((type) => (
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
                    name="materialType"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Material</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger data-testid="select-material">
                              <SelectValue placeholder="Select material" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {materialTypes.map((type) => (
                              <SelectItem key={type.value} value={type.value}>
                                {type.label} ({type.price})
                              </SelectItem>
                            ))}
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
                    name="labName"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Lab Name</FormLabel>
                        <FormControl>
                          <Input {...field} placeholder="Dental lab name" data-testid="input-lab" />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="shade"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Shade</FormLabel>
                        <FormControl>
                          <Input {...field} placeholder="A1, A2, B1, etc." data-testid="input-shade" />
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
                        <Textarea {...field} placeholder="Special instructions..." data-testid="input-notes" />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <div className="flex justify-end gap-2">
                  <Button type="button" variant="outline" onClick={() => setIsAddDialogOpen(false)}>
                    Cancel
                  </Button>
                  <Button type="submit" disabled={createCaseMutation.isPending} data-testid="button-submit">
                    {createCaseMutation.isPending ? "Creating..." : "Create Case"}
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
            <CardTitle className="text-sm font-medium">Pending</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold" data-testid="stat-pending">{pendingCount}</div>
            <p className="text-xs text-muted-foreground">Awaiting design</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">In Progress</CardTitle>
            <Wrench className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600" data-testid="stat-in-progress">{inProgressCount}</div>
            <p className="text-xs text-muted-foreground">Being fabricated</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">In Transit</CardTitle>
            <Truck className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-purple-600" data-testid="stat-shipped">{shippedCount}</div>
            <p className="text-xs text-muted-foreground">Shipped from lab</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Total Cases</CardTitle>
            <Package className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold" data-testid="stat-total">{labCases.length}</div>
            <p className="text-xs text-muted-foreground">All lab cases</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Lab Cases</CardTitle>
          <CardDescription>Track prosthesis design and fabrication</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-muted-foreground text-center py-4">Loading...</p>
          ) : labCases.length === 0 ? (
            <div className="text-center py-12">
              <Package className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium mb-2">No Lab Cases</h3>
              <p className="text-muted-foreground mb-4">Create your first lab case to get started</p>
              <Button onClick={() => setIsAddDialogOpen(true)} data-testid="button-add-first">
                <Plus className="w-4 h-4 mr-2" />
                New Lab Case
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              {labCases.map((labCase) => (
                <div key={labCase.id} className="border rounded-lg p-4" data-testid={`case-row-${labCase.id}`}>
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <h3 className="font-semibold text-lg">{getPatientName(labCase.patientId)}</h3>
                        {getStatusBadge(labCase.status)}
                      </div>
                      <div className="flex flex-wrap gap-2 mb-2">
                        <Badge variant="outline">
                          {prosthesisTypes.find(t => t.value === labCase.prosthesisType)?.label || labCase.prosthesisType}
                        </Badge>
                        <Badge variant="outline">
                          <Palette className="w-3 h-3 mr-1" />
                          {materialTypes.find(t => t.value === labCase.materialType)?.label || labCase.materialType}
                        </Badge>
                        {labCase.shade && (
                          <Badge variant="outline">Shade: {labCase.shade}</Badge>
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {caseTypes.find(t => t.value === labCase.caseType)?.label}
                        {labCase.labName && ` | Lab: ${labCase.labName}`}
                      </p>
                      <div className="flex items-center gap-4 mt-3">
                        <div className="flex items-center gap-2">
                          <FileText className="w-4 h-4 text-muted-foreground" />
                          <span className="text-sm">
                            Designs: {labCase.designsUsed || 0} / {labCase.designIncluded || 2} included
                          </span>
                          {Number(labCase.designsUsed || 0) > Number(labCase.designIncluded || 2) && (
                            <Badge variant="destructive" className="text-xs">
                              <DollarSign className="w-3 h-3 mr-1" />
                              +${labCase.additionalDesignFee || 0}
                            </Badge>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="flex flex-col gap-2 items-end">
                      <Select 
                        value={labCase.status} 
                        onValueChange={(status) => updateStatus(labCase.id, status)}
                      >
                        <SelectTrigger className="w-[180px]" data-testid={`status-${labCase.id}`}>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {statusOptions.map((status) => (
                            <SelectItem key={status.value} value={status.value}>
                              {status.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <Button 
                        variant="outline" 
                        size="sm"
                        onClick={() => addDesignRevision(labCase.id, labCase.designsUsed || 0, labCase.designIncluded || 2)}
                        data-testid={`revision-${labCase.id}`}
                      >
                        <Plus className="w-4 h-4 mr-1" />
                        Add Revision
                      </Button>
                    </div>
                  </div>
                  {labCase.notes && (
                    <div className="mt-3 pt-3 border-t">
                      <p className="text-sm text-muted-foreground">{labCase.notes}</p>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
