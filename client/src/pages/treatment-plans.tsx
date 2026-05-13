import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Link } from "wouter";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Plus,
  Search,
  DollarSign,
  FileText,
  CheckCircle2,
  Clock,
  AlertCircle,
  Brain,
  ArrowRight,
  Calculator,
  Send,
  Download,
} from "lucide-react";
import { exportToPDF } from "@/lib/export";
import { format } from "date-fns";
import { useToast } from "@/hooks/use-toast";
import { apiRequest, queryClient } from "@/lib/queryClient";
import type { TreatmentPlan, Patient } from "@shared/schema";

const statusConfig: Record<string, { label: string; color: string; icon: any }> = {
  draft: { label: "Draft", color: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300", icon: FileText },
  pending: { label: "Pending Approval", color: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400", icon: Clock },
  approved: { label: "Approved", color: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400", icon: CheckCircle2 },
  in_progress: { label: "In Progress", color: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400", icon: Clock },
  completed: { label: "Completed", color: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400", icon: CheckCircle2 },
};

const fullArchPackages = [
  {
    name: "All-on-4 Lower Arch",
    description: "4 implants with fixed hybrid denture - mandibular arch",
    totalCost: 28500,
    avgInsurance: 8500,
    patientOop: 20000,
  },
  {
    name: "All-on-4 Upper Arch",
    description: "4 implants with fixed hybrid denture - maxillary arch",
    totalCost: 32000,
    avgInsurance: 9000,
    patientOop: 23000,
  },
  {
    name: "All-on-6 Full Mouth",
    description: "6 implants per arch with zirconia prosthesis",
    totalCost: 75000,
    avgInsurance: 18000,
    patientOop: 57000,
  },
  {
    name: "Full Mouth Reconstruction",
    description: "Complete restoration with implants, bone grafting, extractions",
    totalCost: 95000,
    avgInsurance: 22000,
    patientOop: 73000,
  },
];

const cosmeticPackages = [
  {
    name: "Smile Design Package",
    description: "Digital smile design, temporary try-in, final zirconia",
    addOnCost: 4500,
  },
  {
    name: "Pink Aesthetics",
    description: "Gingival ceramic for natural tissue appearance",
    addOnCost: 2500,
  },
  {
    name: "Premium Zirconia Upgrade",
    description: "Multilayer zirconia with individual characterization",
    addOnCost: 6000,
  },
];

const orthoPreauth = {
  commonCodes: [
    { code: "D8080", description: "Comprehensive orthodontic treatment - adult", fee: 6500 },
    { code: "D8090", description: "Comprehensive orthodontic treatment - child", fee: 5500 },
    { code: "D8670", description: "Periodic orthodontic treatment visit", fee: 250 },
  ],
  requiredDocs: [
    "Panoramic radiograph",
    "Cephalometric radiograph",
    "Intraoral photos (9 views)",
    "Study models or digital scans",
    "Treatment plan narrative",
  ],
};

export default function TreatmentPlansPage() {
  const { toast } = useToast();
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [showPackages, setShowPackages] = useState(false);
  const [showCopayCalculator, setShowCopayCalculator] = useState(false);
  const [showCosmeticPackages, setShowCosmeticPackages] = useState(false);
  const [showOrthoPreauth, setShowOrthoPreauth] = useState(false);
  const [showNewPlanDialog, setShowNewPlanDialog] = useState(false);
  const [newPlan, setNewPlan] = useState({
    patientId: "",
    planName: "",
    diagnosis: "",
    diagnosisCode: "",
    totalCost: "35000",
    notes: "",
  });
  
  const [copayCalc, setCopayCalc] = useState({
    treatmentCost: 35000,
    medicalDeductible: 2500,
    medicalCoinsurance: 80,
    dentalMax: 2000,
    medicalMaxOop: 8000,
  });

  const { data: plans, isLoading } = useQuery<TreatmentPlan[]>({
    queryKey: ["/api/treatment-plans"],
  });

  const { data: patients = [] } = useQuery<Patient[]>({
    queryKey: ["/api/patients"],
  });

  const createPlanMutation = useMutation({
    mutationFn: async (data: typeof newPlan) => {
      const res = await apiRequest("POST", "/api/treatment-plans", {
        patientId: parseInt(data.patientId),
        planName: data.planName,
        diagnosis: data.diagnosis,
        diagnosisCode: data.diagnosisCode,
        totalCost: data.totalCost,
        status: "draft",
        notes: data.notes || null,
        procedures: [],
      });
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/treatment-plans"] });
      setShowNewPlanDialog(false);
      setNewPlan({ patientId: "", planName: "", diagnosis: "", diagnosisCode: "", totalCost: "35000", notes: "" });
      toast({ title: "Treatment Plan Created", description: "The treatment plan has been created successfully." });
    },
    onError: (error: Error) => {
      toast({ title: "Error", description: error.message, variant: "destructive" });
    },
  });

  const filteredPlans = plans?.filter((plan) => {
    const matchesSearch =
      plan.planName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      plan.diagnosis?.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === "all" || plan.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const formatCurrency = (amount: number | string | null | undefined) => {
    if (!amount) return "$0";
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 0,
    }).format(Number(amount));
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Treatment Plans</h1>
          <p className="text-muted-foreground">
            Create and manage full arch implant treatment plans with cost estimates
          </p>
        </div>
        <div className="flex gap-3">
          <Dialog open={showPackages} onOpenChange={setShowPackages}>
            <DialogTrigger asChild>
              <Button variant="outline" data-testid="button-view-packages">
                <Calculator className="mr-2 h-4 w-4" />
                Package Pricing
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl">
              <DialogHeader>
                <DialogTitle>Full Arch Implant Packages</DialogTitle>
                <DialogDescription>
                  Standard pricing for common full arch procedures
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4 mt-4">
                {fullArchPackages.map((pkg) => (
                  <div
                    key={pkg.name}
                    className="flex items-center justify-between rounded-lg border p-4"
                  >
                    <div>
                      <p className="font-medium">{pkg.name}</p>
                      <p className="text-sm text-muted-foreground">{pkg.description}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-lg font-bold">{formatCurrency(pkg.totalCost)}</p>
                      <p className="text-sm text-muted-foreground">
                        Ins: {formatCurrency(pkg.avgInsurance)} | OOP: {formatCurrency(pkg.patientOop)}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </DialogContent>
          </Dialog>
          <Dialog open={showNewPlanDialog} onOpenChange={setShowNewPlanDialog}>
            <DialogTrigger asChild>
              <Button data-testid="button-new-plan">
                <Plus className="mr-2 h-4 w-4" />
                New Plan
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-lg">
              <DialogHeader>
                <DialogTitle>Create Treatment Plan</DialogTitle>
                <DialogDescription>Create a new treatment plan for a patient</DialogDescription>
              </DialogHeader>
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label>Patient</Label>
                  <Select value={newPlan.patientId} onValueChange={(v) => setNewPlan({ ...newPlan, patientId: v })}>
                    <SelectTrigger data-testid="select-patient">
                      <SelectValue placeholder="Select patient" />
                    </SelectTrigger>
                    <SelectContent>
                      {patients.map((p) => (
                        <SelectItem key={p.id} value={p.id.toString()}>
                          {p.firstName} {p.lastName}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Plan Name</Label>
                  <Select value={newPlan.planName} onValueChange={(v) => setNewPlan({ ...newPlan, planName: v })}>
                    <SelectTrigger data-testid="select-plan-name">
                      <SelectValue placeholder="Select plan type" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="All-on-4 Lower Arch">All-on-4 Lower Arch</SelectItem>
                      <SelectItem value="All-on-4 Upper Arch">All-on-4 Upper Arch</SelectItem>
                      <SelectItem value="All-on-6 Full Mouth">All-on-6 Full Mouth</SelectItem>
                      <SelectItem value="Full Mouth Reconstruction">Full Mouth Reconstruction</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Diagnosis</Label>
                    <Input 
                      placeholder="e.g., Complete edentulism"
                      value={newPlan.diagnosis}
                      onChange={(e) => setNewPlan({ ...newPlan, diagnosis: e.target.value })}
                      data-testid="input-diagnosis"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>ICD-10 Code</Label>
                    <Input 
                      placeholder="e.g., K08.1"
                      value={newPlan.diagnosisCode}
                      onChange={(e) => setNewPlan({ ...newPlan, diagnosisCode: e.target.value })}
                      data-testid="input-diagnosis-code"
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>Estimated Total Cost</Label>
                  <Input 
                    type="number"
                    value={newPlan.totalCost}
                    onChange={(e) => setNewPlan({ ...newPlan, totalCost: e.target.value })}
                    data-testid="input-cost"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Notes</Label>
                  <Textarea 
                    placeholder="Additional notes..."
                    value={newPlan.notes}
                    onChange={(e) => setNewPlan({ ...newPlan, notes: e.target.value })}
                    data-testid="input-notes"
                  />
                </div>
                <div className="flex justify-end gap-2">
                  <Button variant="outline" onClick={() => setShowNewPlanDialog(false)}>Cancel</Button>
                  <Button 
                    onClick={() => createPlanMutation.mutate(newPlan)}
                    disabled={!newPlan.patientId || !newPlan.planName || createPlanMutation.isPending}
                    data-testid="button-submit"
                  >
                    {createPlanMutation.isPending ? "Creating..." : "Create Plan"}
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Total Plans</p>
                <p className="text-2xl font-bold">{plans?.length || 0}</p>
              </div>
              <FileText className="h-8 w-8 text-muted-foreground/30" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Pending Auth</p>
                <p className="text-2xl font-bold text-yellow-600">
                  {plans?.filter((p) => p.priorAuthStatus === "pending").length || 0}
                </p>
              </div>
              <AlertCircle className="h-8 w-8 text-yellow-500/30" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Total Value</p>
                <p className="text-2xl font-bold text-primary">
                  {formatCurrency(
                    plans?.reduce((sum, p) => sum + (Number(p.totalCost) || 0), 0)
                  )}
                </p>
              </div>
              <DollarSign className="h-8 w-8 text-primary/30" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Avg Plan Value</p>
                <p className="text-2xl font-bold">
                  {formatCurrency(
                    plans && plans.length > 0
                      ? plans.reduce((sum, p) => sum + (Number(p.totalCost) || 0), 0) / plans.length
                      : 0
                  )}
                </p>
              </div>
              <Calculator className="h-8 w-8 text-muted-foreground/30" />
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="pb-4">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search by plan name or diagnosis..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
                data-testid="input-search-plans"
              />
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[180px]" data-testid="select-status-filter">
                <SelectValue placeholder="Filter by status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Statuses</SelectItem>
                <SelectItem value="draft">Draft</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="approved">Approved</SelectItem>
                <SelectItem value="in_progress">In Progress</SelectItem>
                <SelectItem value="completed">Completed</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-24 w-full" />
              ))}
            </div>
          ) : filteredPlans && filteredPlans.length > 0 ? (
            <div className="space-y-4">
              {filteredPlans.map((plan) => {
                const status = statusConfig[plan.status] || statusConfig.draft;
                const StatusIcon = status.icon;

                return (
                  <div
                    key={plan.id}
                    className="flex flex-col gap-4 rounded-lg border p-4 hover-elevate sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div className="flex items-start gap-4">
                      <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10">
                        <FileText className="h-6 w-6 text-primary" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <Link
                            href={`/treatment-plans/${plan.id}`}
                            className="font-semibold hover:underline"
                          >
                            {plan.planName}
                          </Link>
                          {plan.cosmeticPackage && (
                            <Badge variant="outline" className="text-xs">
                              Cosmetic
                            </Badge>
                          )}
                        </div>
                        <p className="text-sm text-muted-foreground">
                          {plan.diagnosis || "No diagnosis specified"}
                        </p>
                        {plan.aiDiagnosis && (
                          <div className="mt-1 flex items-center gap-1 text-xs text-chart-3">
                            <Brain className="h-3 w-3" />
                            AI-assisted diagnosis
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="flex flex-wrap items-center gap-4">
                      <div className="text-right">
                        <p className="text-lg font-bold">{formatCurrency(plan.totalCost)}</p>
                        <p className="text-xs text-muted-foreground">
                          Patient: {formatCurrency(plan.patientResponsibility)}
                        </p>
                      </div>

                      <div className="flex items-center gap-2">
                        {plan.priorAuthStatus === "pending" && (
                          <Badge variant="outline" className="gap-1">
                            <Clock className="h-3 w-3" />
                            Auth Pending
                          </Badge>
                        )}
                        <Badge className={status.color}>
                          <StatusIcon className="mr-1 h-3 w-3" />
                          {status.label}
                        </Badge>
                      </div>

                      <Button
                        variant="ghost"
                        size="icon"
                        title="Export for Patient"
                        data-testid={`button-export-plan-${plan.id}`}
                        onClick={() => {
                          const patient = patients.find((p) => p.id === plan.patientId);
                          const patientName = patient ? `${patient.firstName} ${patient.lastName}` : "Patient";
                          const procedures = Array.isArray(plan.procedures) ? plan.procedures as { name?: string; code?: string; cost?: number }[] : [];
                          exportToPDF(
                            [
                              {
                                type: "title",
                                title: "Treatment Plan Summary",
                                subtitle: `Golden State Dental — Prepared for ${patientName}`,
                              },
                              {
                                type: "kpis",
                                heading: "Plan Overview",
                                items: [
                                  { label: "Patient", value: patientName },
                                  { label: "Plan Name", value: plan.planName },
                                  { label: "Diagnosis", value: plan.diagnosis ?? "—" },
                                  { label: "ICD-10 Code", value: plan.diagnosisCode ?? "—" },
                                  { label: "Status", value: plan.status },
                                  { label: "Prior Auth", value: plan.priorAuthStatus ?? "Not required" },
                                ],
                              },
                              {
                                type: "kpis",
                                heading: "Financial Summary",
                                items: [
                                  { label: "Total Cost", value: formatCurrency(plan.totalCost) },
                                  { label: "Insurance Coverage", value: formatCurrency(plan.insuranceCoverage) },
                                  { label: "Patient Responsibility", value: formatCurrency(plan.patientResponsibility) },
                                ],
                              },
                              ...(procedures.length > 0
                                ? [{
                                    type: "table" as const,
                                    heading: "Procedure List",
                                    columns: ["Procedure", "Code", "Est. Cost ($)"],
                                    rows: procedures.map((proc) => [
                                      proc.name ?? "—",
                                      proc.code ?? "—",
                                      proc.cost != null ? formatCurrency(proc.cost) : "—",
                                    ]),
                                  }]
                                : []),
                              ...(plan.notes
                                ? [{
                                    type: "table" as const,
                                    heading: "Clinical Notes",
                                    columns: ["Notes"],
                                    rows: [[plan.notes]],
                                  }]
                                : []),
                            ],
                            `TreatmentPlan_${plan.id}`,
                          );
                        }}
                      >
                        <Download className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="icon" asChild>
                        <Link href={`/treatment-plans/${plan.id}`}>
                          <ArrowRight className="h-4 w-4" />
                        </Link>
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-muted">
                <FileText className="h-8 w-8 text-muted-foreground" />
              </div>
              <h3 className="mb-2 text-lg font-semibold">No treatment plans found</h3>
              <p className="mb-6 max-w-sm text-sm text-muted-foreground">
                Create a treatment plan with AI-assisted diagnosis and automatic cost calculation
              </p>
              <Button onClick={() => setShowNewPlanDialog(true)}>
                <Plus className="mr-2 h-4 w-4" />
                Create Treatment Plan
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
