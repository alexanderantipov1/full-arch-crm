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
  Shield, Plus, FileText, Calendar, AlertCircle, CheckCircle, Clock
} from "lucide-react";
import type { WarrantyRecord, Patient, TreatmentPlan } from "@shared/schema";

const warrantyFormSchema = z.object({
  patientId: z.number().min(1, "Patient is required"),
  treatmentPlanId: z.number().optional(),
  warrantyType: z.string().min(1, "Warranty type is required"),
  startDate: z.string().min(1, "Start date is required"),
  endDate: z.string().min(1, "End date is required"),
  coverageDetails: z.string().optional(),
});

type WarrantyFormData = z.infer<typeof warrantyFormSchema>;

const warrantyTypes = [
  { value: "implant_5yr", label: "Implant Warranty - 5 Years" },
  { value: "implant_10yr", label: "Implant Warranty - 10 Years" },
  { value: "prosthesis_3yr", label: "Prosthesis Warranty - 3 Years" },
  { value: "prosthesis_5yr", label: "Prosthesis Warranty - 5 Years" },
  { value: "zirconia_lifetime", label: "Zirconia Lifetime Warranty" },
  { value: "bone_graft_2yr", label: "Bone Graft - 2 Years" },
];

export default function WarrantyPage() {
  const { toast } = useToast();
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);

  const { data: warranties = [], isLoading } = useQuery<WarrantyRecord[]>({
    queryKey: ["/api/warranty-records"],
  });

  const { data: patients = [] } = useQuery<Patient[]>({
    queryKey: ["/api/patients"],
  });

  const { data: treatmentPlans = [] } = useQuery<TreatmentPlan[]>({
    queryKey: ["/api/treatment-plans"],
  });

  const form = useForm<WarrantyFormData>({
    resolver: zodResolver(warrantyFormSchema),
    defaultValues: {
      patientId: 0,
      warrantyType: "",
      startDate: new Date().toISOString().split('T')[0],
      endDate: "",
      coverageDetails: "",
    },
  });

  const createWarrantyMutation = useMutation({
    mutationFn: async (data: WarrantyFormData) => {
      const res = await apiRequest("POST", "/api/warranty-records", {
        patientId: data.patientId,
        treatmentPlanId: data.treatmentPlanId,
        warrantyType: data.warrantyType,
        startDate: data.startDate,
        endDate: data.endDate,
        coverageDetails: data.coverageDetails || null,
      });
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/warranty-records"] });
      setIsAddDialogOpen(false);
      form.reset();
      toast({ title: "Warranty Created", description: "Warranty record has been added" });
    },
    onError: (error: Error) => {
      toast({ title: "Error", description: error.message, variant: "destructive" });
    },
  });

  const onSubmit = (data: WarrantyFormData) => {
    createWarrantyMutation.mutate(data);
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

  const isExpiringSoon = (endDate: Date | string | null) => {
    if (!endDate) return false;
    const end = new Date(endDate);
    const now = new Date();
    const daysUntilExpiry = (end.getTime() - now.getTime()) / (1000 * 60 * 60 * 24);
    return daysUntilExpiry > 0 && daysUntilExpiry <= 90;
  };

  const isExpired = (endDate: Date | string | null) => {
    if (!endDate) return false;
    return new Date(endDate) < new Date();
  };

  const activeCount = warranties.filter(w => !isExpired(w.endDate)).length;
  const expiringCount = warranties.filter(w => isExpiringSoon(w.endDate)).length;
  const expiredCount = warranties.filter(w => isExpired(w.endDate)).length;

  return (
    <div className="flex-1 overflow-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold" data-testid="text-page-title">Warranty & Coverage</h1>
          <p className="text-muted-foreground">Manage implant and prosthesis warranties</p>
        </div>
        <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
          <DialogTrigger asChild>
            <Button data-testid="button-add-warranty">
              <Plus className="w-4 h-4 mr-2" />
              Add Warranty
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle>Create Warranty Record</DialogTitle>
              <DialogDescription>Add warranty coverage for a patient</DialogDescription>
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
                <FormField
                  control={form.control}
                  name="warrantyType"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Warranty Type</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl>
                          <SelectTrigger data-testid="select-type">
                            <SelectValue placeholder="Select type" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {warrantyTypes.map((type) => (
                            <SelectItem key={type.value} value={type.value}>{type.label}</SelectItem>
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
                    name="startDate"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Start Date</FormLabel>
                        <FormControl>
                          <Input {...field} type="date" data-testid="input-start" />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="endDate"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>End Date</FormLabel>
                        <FormControl>
                          <Input {...field} type="date" data-testid="input-end" />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
                <FormField
                  control={form.control}
                  name="coverageDetails"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Coverage Details</FormLabel>
                      <FormControl>
                        <Textarea {...field} placeholder="What's covered..." data-testid="input-coverage" />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <div className="flex justify-end gap-2">
                  <Button type="button" variant="outline" onClick={() => setIsAddDialogOpen(false)}>
                    Cancel
                  </Button>
                  <Button type="submit" disabled={createWarrantyMutation.isPending} data-testid="button-submit">
                    {createWarrantyMutation.isPending ? "Creating..." : "Create Warranty"}
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
            <CardTitle className="text-sm font-medium">Active Warranties</CardTitle>
            <Shield className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600" data-testid="stat-active">{activeCount}</div>
            <p className="text-xs text-muted-foreground">Currently covered</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Expiring Soon</CardTitle>
            <Clock className="h-4 w-4 text-orange-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-orange-600" data-testid="stat-expiring">{expiringCount}</div>
            <p className="text-xs text-muted-foreground">Within 90 days</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Expired</CardTitle>
            <AlertCircle className="h-4 w-4 text-red-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600" data-testid="stat-expired">{expiredCount}</div>
            <p className="text-xs text-muted-foreground">No longer covered</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Total Records</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold" data-testid="stat-total">{warranties.length}</div>
            <p className="text-xs text-muted-foreground">All warranties</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Warranty Records</CardTitle>
          <CardDescription>Track implant and prosthesis coverage</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-muted-foreground text-center py-4">Loading...</p>
          ) : warranties.length === 0 ? (
            <div className="text-center py-12">
              <Shield className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium mb-2">No Warranty Records</h3>
              <p className="text-muted-foreground mb-4">Add warranty coverage for patients</p>
              <Button onClick={() => setIsAddDialogOpen(true)} data-testid="button-add-first">
                <Plus className="w-4 h-4 mr-2" />
                Add Warranty
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              {warranties.map((warranty) => (
                <div key={warranty.id} className="flex items-center justify-between p-4 border rounded-lg" data-testid={`warranty-${warranty.id}`}>
                  <div className="flex items-center gap-4">
                    <div className="flex items-center justify-center w-12 h-12 rounded-full bg-primary/10">
                      <Shield className={`w-6 h-6 ${isExpired(warranty.endDate) ? "text-red-500" : isExpiringSoon(warranty.endDate) ? "text-orange-500" : "text-green-500"}`} />
                    </div>
                    <div>
                      <p className="font-semibold text-lg">{getPatientName(warranty.patientId)}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <Badge variant="outline">
                          {warrantyTypes.find(t => t.value === warranty.warrantyType)?.label || warranty.warrantyType}
                        </Badge>
                        {isExpired(warranty.endDate) ? (
                          <Badge variant="destructive">Expired</Badge>
                        ) : isExpiringSoon(warranty.endDate) ? (
                          <Badge className="bg-orange-100 text-orange-800">Expiring Soon</Badge>
                        ) : (
                          <Badge className="bg-green-100 text-green-800">Active</Badge>
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground mt-1">
                        {formatDate(warranty.startDate)} - {formatDate(warranty.endDate)}
                      </p>
                    </div>
                  </div>
                  <Button variant="outline" size="sm" data-testid={`view-${warranty.id}`}>
                    <FileText className="w-4 h-4 mr-1" />
                    View Details
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
