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
  CreditCard, DollarSign, Plus, Calendar, Percent, 
  CheckCircle, Clock, XCircle, Building2, Users
} from "lucide-react";
import type { FinancingPlan, Patient, TreatmentPlan } from "@shared/schema";

const financingFormSchema = z.object({
  patientId: z.number().min(1, "Patient is required"),
  treatmentPlanId: z.number().optional(),
  provider: z.string().min(1, "Provider is required"),
  totalAmount: z.string().min(1, "Total amount is required"),
  downPayment: z.string().optional(),
  monthlyPayment: z.string().optional(),
  termMonths: z.string().optional(),
  interestRate: z.string().optional(),
  notes: z.string().optional(),
});

type FinancingFormData = z.infer<typeof financingFormSchema>;

const financingProviders = [
  { value: "cherry", label: "Cherry", color: "bg-red-100 text-red-800" },
  { value: "proceed_finance", label: "Proceed Finance", color: "bg-blue-100 text-blue-800" },
  { value: "stride", label: "Stride", color: "bg-purple-100 text-purple-800" },
  { value: "care_credit", label: "CareCredit", color: "bg-green-100 text-green-800" },
  { value: "lending_club", label: "LendingClub", color: "bg-amber-100 text-amber-800" },
  { value: "in_house", label: "In-House", color: "bg-gray-100 text-gray-800" },
];

const formatCurrency = (amount: string | number | null) => {
  if (!amount) return "$0";
  const num = typeof amount === "string" ? parseFloat(amount) : amount;
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(num);
};

export default function FinancingPage() {
  const { toast } = useToast();
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);

  const { data: plans = [], isLoading } = useQuery<FinancingPlan[]>({
    queryKey: ["/api/financing"],
  });

  const { data: patients = [] } = useQuery<Patient[]>({
    queryKey: ["/api/patients"],
  });

  const { data: treatmentPlans = [] } = useQuery<TreatmentPlan[]>({
    queryKey: ["/api/treatment-plans"],
  });

  const form = useForm<FinancingFormData>({
    resolver: zodResolver(financingFormSchema),
    defaultValues: {
      patientId: 0,
      provider: "",
      totalAmount: "",
      downPayment: "",
      monthlyPayment: "",
      termMonths: "",
      interestRate: "0",
      notes: "",
    },
  });

  const createPlanMutation = useMutation({
    mutationFn: async (data: FinancingFormData) => {
      const res = await apiRequest("POST", "/api/financing", {
        ...data,
        approvedAmount: data.totalAmount,
        downPayment: data.downPayment || "0",
        monthlyPayment: data.monthlyPayment || "0",
        termMonths: data.termMonths ? parseInt(data.termMonths) : 12,
        interestRate: data.interestRate || "0",
        applicationStatus: "pending",
      });
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/financing"] });
      setIsAddDialogOpen(false);
      form.reset();
      toast({ title: "Financing Plan Created", description: "New financing plan has been added" });
    },
    onError: (error: Error) => {
      toast({ title: "Error", description: error.message, variant: "destructive" });
    },
  });

  const updateStatusMutation = useMutation({
    mutationFn: async ({ id, status }: { id: number; status: string }) => {
      const res = await apiRequest("PATCH", `/api/financing/${id}`, { applicationStatus: status });
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/financing"] });
      toast({ title: "Status Updated", description: "Financing status has been updated" });
    },
  });

  const onSubmit = (data: FinancingFormData) => {
    createPlanMutation.mutate(data);
  };

  const getPatientName = (patientId: number | null) => {
    if (!patientId) return "Unknown";
    const patient = patients.find(p => p.id === patientId);
    return patient ? `${patient.firstName} ${patient.lastName}` : "Unknown";
  };

  const getProviderStyle = (provider: string) => {
    return financingProviders.find(p => p.value === provider)?.color || "bg-gray-100 text-gray-800";
  };

  const getStatusBadge = (applicationStatus: string) => {
    switch (applicationStatus) {
      case "pending":
        return <Badge variant="outline"><Clock className="w-3 h-3 mr-1" /> Pending</Badge>;
      case "approved":
        return <Badge className="bg-green-100 text-green-800"><CheckCircle className="w-3 h-3 mr-1" /> Approved</Badge>;
      case "declined":
        return <Badge variant="destructive"><XCircle className="w-3 h-3 mr-1" /> Declined</Badge>;
      case "active":
        return <Badge className="bg-blue-100 text-blue-800"><CreditCard className="w-3 h-3 mr-1" /> Active</Badge>;
      case "paid_off":
        return <Badge className="bg-purple-100 text-purple-800"><CheckCircle className="w-3 h-3 mr-1" /> Paid Off</Badge>;
      default:
        return <Badge variant="outline">{applicationStatus}</Badge>;
    }
  };

  const pendingPlans = plans.filter(p => p.applicationStatus === "pending");
  const approvedPlans = plans.filter(p => p.applicationStatus === "approved" || p.applicationStatus === "active");
  const totalFinanced = plans
    .filter(p => p.applicationStatus === "approved" || p.applicationStatus === "active")
    .reduce((sum, p) => sum + parseFloat(p.approvedAmount || "0"), 0);

  return (
    <div className="flex-1 overflow-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold" data-testid="text-page-title">Patient Financing</h1>
          <p className="text-muted-foreground">Third-party and in-house financing management</p>
        </div>
        <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
          <DialogTrigger asChild>
            <Button data-testid="button-add-financing">
              <Plus className="w-4 h-4 mr-2" />
              New Application
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>Create Financing Application</DialogTitle>
              <DialogDescription>Submit a new patient financing request</DialogDescription>
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
                    name="provider"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Financing Provider</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger data-testid="select-provider">
                              <SelectValue placeholder="Select provider" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {financingProviders.map((opt) => (
                              <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
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
                    name="totalAmount"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Total Amount ($)</FormLabel>
                        <FormControl>
                          <Input {...field} type="number" placeholder="32000" data-testid="input-total" />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="downPayment"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Down Payment ($)</FormLabel>
                        <FormControl>
                          <Input {...field} type="number" placeholder="5000" data-testid="input-down" />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
                <div className="grid grid-cols-3 gap-4">
                  <FormField
                    control={form.control}
                    name="monthlyPayment"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Monthly Payment ($)</FormLabel>
                        <FormControl>
                          <Input {...field} type="number" placeholder="450" data-testid="input-monthly" />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="termMonths"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Term (Months)</FormLabel>
                        <FormControl>
                          <Input {...field} type="number" placeholder="60" data-testid="input-term" />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="interestRate"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Interest Rate (%)</FormLabel>
                        <FormControl>
                          <Input {...field} type="number" step="0.1" placeholder="0" data-testid="input-rate" />
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
                        <Textarea {...field} placeholder="Additional notes..." data-testid="input-notes" />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <div className="flex justify-end gap-2">
                  <Button type="button" variant="outline" onClick={() => setIsAddDialogOpen(false)}>
                    Cancel
                  </Button>
                  <Button type="submit" disabled={createPlanMutation.isPending} data-testid="button-submit-financing">
                    {createPlanMutation.isPending ? "Submitting..." : "Submit Application"}
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
            <CardTitle className="text-sm font-medium">Total Financed</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold" data-testid="stat-total">{formatCurrency(totalFinanced)}</div>
            <p className="text-xs text-muted-foreground">Active financing</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Pending Apps</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-amber-600" data-testid="stat-pending">{pendingPlans.length}</div>
            <p className="text-xs text-muted-foreground">Awaiting approval</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Active Plans</CardTitle>
            <CreditCard className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600" data-testid="stat-active">{approvedPlans.length}</div>
            <p className="text-xs text-muted-foreground">Currently active</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Approval Rate</CardTitle>
            <Percent className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold" data-testid="stat-rate">87%</div>
            <p className="text-xs text-muted-foreground">Last 30 days</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Financing Applications</CardTitle>
          <CardDescription>All patient financing plans and applications</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-muted-foreground text-center py-4">Loading...</p>
          ) : plans.length === 0 ? (
            <div className="text-center py-12">
              <CreditCard className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium mb-2">No Financing Plans</h3>
              <p className="text-muted-foreground mb-4">Create financing applications for patient treatments</p>
              <Button onClick={() => setIsAddDialogOpen(true)} data-testid="button-add-first">
                <Plus className="w-4 h-4 mr-2" />
                New Application
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              {plans.map((plan) => (
                <div key={plan.id} className="flex items-center justify-between p-4 border rounded-lg" data-testid={`financing-row-${plan.id}`}>
                  <div className="flex items-center gap-4">
                    <div>
                      <p className="font-semibold">{getPatientName(plan.patientId)}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <Badge className={getProviderStyle(plan.provider)}>
                          {financingProviders.find(p => p.value === plan.provider)?.label || plan.provider}
                        </Badge>
                        {getStatusBadge(plan.applicationStatus)}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-6">
                    <div className="text-right">
                      <p className="text-xl font-bold">{formatCurrency(plan.approvedAmount)}</p>
                      <p className="text-sm text-muted-foreground">
                        {formatCurrency(plan.monthlyPayment)}/mo × {plan.termMonths} mo
                      </p>
                    </div>
                    <div className="flex gap-2">
                      {plan.applicationStatus === "pending" && (
                        <>
                          <Button 
                            size="sm" 
                            onClick={() => updateStatusMutation.mutate({ id: plan.id, status: "approved" })}
                            data-testid={`approve-${plan.id}`}
                          >
                            Approve
                          </Button>
                          <Button 
                            size="sm" 
                            variant="outline"
                            onClick={() => updateStatusMutation.mutate({ id: plan.id, status: "declined" })}
                            data-testid={`decline-${plan.id}`}
                          >
                            Decline
                          </Button>
                        </>
                      )}
                      {plan.applicationStatus === "approved" && (
                        <Button 
                          size="sm"
                          onClick={() => updateStatusMutation.mutate({ id: plan.id, status: "active" })}
                          data-testid={`activate-${plan.id}`}
                        >
                          Activate
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

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Building2 className="w-5 h-5" />
              Financing Partners
            </CardTitle>
            <CardDescription>Integrated third-party providers</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {financingProviders.slice(0, 5).map((provider) => (
                <div key={provider.value} className="flex items-center justify-between p-3 border rounded-lg">
                  <div className="flex items-center gap-3">
                    <Badge className={provider.color}>{provider.label}</Badge>
                  </div>
                  <div className="text-sm text-muted-foreground">
                    {provider.value === "cherry" && "0% APR up to 24mo"}
                    {provider.value === "proceed_finance" && "Up to $100K, instant approval"}
                    {provider.value === "stride" && "Flexible terms 12-84mo"}
                    {provider.value === "care_credit" && "Promotional financing available"}
                    {provider.value === "lending_club" && "Personal loans 3-7 years"}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users className="w-5 h-5" />
              In-House Financing
            </CardTitle>
            <CardDescription>Practice-managed payment plans</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="p-4 border rounded-lg">
                <h4 className="font-semibold mb-2">Standard Plan</h4>
                <ul className="text-sm text-muted-foreground space-y-1">
                  <li>• 20% down payment required</li>
                  <li>• 0% interest for 12 months</li>
                  <li>• Automatic payment setup</li>
                </ul>
              </div>
              <div className="p-4 border rounded-lg">
                <h4 className="font-semibold mb-2">Extended Plan</h4>
                <ul className="text-sm text-muted-foreground space-y-1">
                  <li>• 10% down payment minimum</li>
                  <li>• 24-36 month terms available</li>
                  <li>• 9.9% APR after 12 months</li>
                </ul>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
