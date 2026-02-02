import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Activity, CheckCircle, Clock, AlertCircle, Calendar, User, TrendingUp, FileText, ArrowRight } from "lucide-react";
import { format } from "date-fns";
import { useToast } from "@/hooks/use-toast";
import { apiRequest, queryClient } from "@/lib/queryClient";
import type { Patient, TreatmentPlan, Appointment } from "@shared/schema";

const treatmentPhases = [
  { id: 1, name: "Initial Consultation", description: "Patient evaluation and treatment planning" },
  { id: 2, name: "Medical Clearance", description: "Medical history review and clearances" },
  { id: 3, name: "Pre-Surgery Prep", description: "Imaging, impressions, and surgical planning" },
  { id: 4, name: "Extractions", description: "Removal of remaining teeth if needed" },
  { id: 5, name: "Implant Placement", description: "Surgical placement of implant fixtures" },
  { id: 6, name: "Healing Period", description: "Osseointegration (3-6 months)" },
  { id: 7, name: "Abutment Placement", description: "Attachment of healing abutments" },
  { id: 8, name: "Impressions", description: "Final impressions for prosthesis" },
  { id: 9, name: "Try-In", description: "Framework and aesthetic try-in" },
  { id: 10, name: "Final Delivery", description: "Delivery and adjustment of final prosthesis" },
  { id: 11, name: "Post-Op Follow-Up", description: "Healing verification and adjustments" },
  { id: 12, name: "Maintenance", description: "Regular cleaning and maintenance schedule" },
];

export default function TreatmentProgressPage() {
  const [patientFilter, setPatientFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [selectedPlan, setSelectedPlan] = useState<TreatmentPlan | null>(null);
  const { toast } = useToast();

  const { data: patients = [] } = useQuery<Patient[]>({
    queryKey: ["/api/patients"],
  });

  const { data: treatmentPlans = [], isLoading } = useQuery<TreatmentPlan[]>({
    queryKey: ["/api/treatment-plans"],
  });

  const { data: appointments = [] } = useQuery<Appointment[]>({
    queryKey: ["/api/appointments"],
  });

  const updatePlanMutation = useMutation({
    mutationFn: async ({ id, status }: { id: number; status: string }) => {
      return apiRequest(`/api/treatment-plans/${id}`, {
        method: "PUT",
        body: JSON.stringify({ status }),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/treatment-plans"] });
      toast({ title: "Treatment plan updated" });
    },
    onError: () => {
      toast({ title: "Failed to update treatment plan", variant: "destructive" });
    },
  });

  const getPatientName = (patientId: number) => {
    const patient = patients.find((p) => p.id === patientId);
    return patient ? `${patient.firstName} ${patient.lastName}` : "Unknown";
  };

  const getPhaseProgress = (plan: TreatmentPlan) => {
    const status = plan.status?.toLowerCase() || "";
    if (status === "completed") return 100;
    if (status === "active") return 45;
    if (status === "pending") return 0;
    return 30;
  };

  const getCurrentPhase = (plan: TreatmentPlan) => {
    const status = plan.status?.toLowerCase() || "";
    if (status === "completed") return treatmentPhases[11];
    if (status === "active") return treatmentPhases[4];
    return treatmentPhases[0];
  };

  const getPatientAppointments = (patientId: number) => {
    return appointments.filter(a => a.patientId === patientId);
  };

  const filteredPlans = treatmentPlans.filter((plan) => {
    const matchesPatient = patientFilter === "all" || plan.patientId.toString() === patientFilter;
    const matchesStatus = statusFilter === "all" || plan.status === statusFilter;
    return matchesPatient && matchesStatus;
  });

  const activePlans = treatmentPlans.filter(p => p.status === "active").length;
  const completedPlans = treatmentPlans.filter(p => p.status === "completed").length;
  const pendingPlans = treatmentPlans.filter(p => p.status === "pending" || p.status === "planned").length;

  return (
    <div className="flex-1 overflow-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-2" data-testid="text-page-title">
            <Activity className="h-8 w-8 text-primary" />
            Treatment Progress
          </h1>
          <p className="text-muted-foreground">Track patient treatment milestones and phases</p>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Total Plans</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold" data-testid="stat-total">{treatmentPlans.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Active Treatments</CardTitle>
            <Activity className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600" data-testid="stat-active">{activePlans}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Completed</CardTitle>
            <CheckCircle className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600" data-testid="stat-completed">{completedPlans}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Pending Start</CardTitle>
            <Clock className="h-4 w-4 text-amber-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-amber-600" data-testid="stat-pending">{pendingPlans}</div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <CardTitle>Treatment Tracking</CardTitle>
              <CardDescription>Monitor patient progress through treatment phases</CardDescription>
            </div>
            <div className="flex gap-2">
              <Select value={patientFilter} onValueChange={setPatientFilter}>
                <SelectTrigger className="w-48" data-testid="filter-patient">
                  <SelectValue placeholder="All Patients" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Patients</SelectItem>
                  {patients.map((patient) => (
                    <SelectItem key={patient.id} value={patient.id.toString()}>
                      {patient.firstName} {patient.lastName}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-32" data-testid="filter-status">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Status</SelectItem>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="completed">Completed</SelectItem>
                  <SelectItem value="pending">Pending</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-center py-8 text-muted-foreground">Loading treatment plans...</p>
          ) : filteredPlans.length === 0 ? (
            <div className="text-center py-12">
              <Activity className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium mb-2">No Treatment Plans</h3>
              <p className="text-muted-foreground">Create treatment plans from patient records</p>
            </div>
          ) : (
            <div className="space-y-4">
              {filteredPlans.map((plan) => {
                const progress = getPhaseProgress(plan);
                const currentPhase = getCurrentPhase(plan);
                const patientAppts = getPatientAppointments(plan.patientId);
                const nextAppt = patientAppts.find(a => new Date(a.date) >= new Date() && a.status !== "completed");

                return (
                  <div
                    key={plan.id}
                    className="border rounded-lg p-4 hover-elevate cursor-pointer"
                    onClick={() => setSelectedPlan(plan)}
                    data-testid={`plan-card-${plan.id}`}
                  >
                    <div className="flex items-start justify-between mb-4">
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <User className="h-4 w-4 text-muted-foreground" />
                          <span className="font-medium">{getPatientName(plan.patientId)}</span>
                          <Badge variant={
                            plan.status === "completed" ? "default" :
                            plan.status === "active" ? "secondary" : "outline"
                          }>
                            {plan.status}
                          </Badge>
                        </div>
                        <p className="text-sm text-muted-foreground">{plan.treatmentType}</p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-medium">${parseFloat(plan.estimatedCost || "0").toLocaleString()}</p>
                        <p className="text-xs text-muted-foreground">Est. Cost</p>
                      </div>
                    </div>

                    <div className="space-y-2 mb-4">
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">Progress</span>
                        <span className="font-medium">{progress}%</span>
                      </div>
                      <Progress value={progress} className="h-2" />
                      <div className="flex items-center gap-2 text-sm">
                        <Badge variant="outline" className="text-xs">
                          Phase {currentPhase.id}/12
                        </Badge>
                        <span className="text-muted-foreground">{currentPhase.name}</span>
                      </div>
                    </div>

                    {nextAppt && (
                      <div className="flex items-center gap-2 text-sm bg-muted/50 rounded p-2">
                        <Calendar className="h-4 w-4 text-blue-500" />
                        <span className="text-muted-foreground">Next:</span>
                        <span className="font-medium">{nextAppt.title}</span>
                        <span className="text-muted-foreground">-</span>
                        <span>{format(new Date(nextAppt.date), "MMM d, yyyy")}</span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Treatment Plan Detail Dialog */}
      <Dialog open={!!selectedPlan} onOpenChange={() => setSelectedPlan(null)}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Treatment Timeline</DialogTitle>
            <DialogDescription>
              {selectedPlan && getPatientName(selectedPlan.patientId)} - {selectedPlan?.treatmentType}
            </DialogDescription>
          </DialogHeader>
          {selectedPlan && (
            <div className="space-y-6">
              <div className="flex items-center gap-4 p-4 bg-muted/50 rounded-lg">
                <div className="flex-1">
                  <p className="text-sm text-muted-foreground">Overall Progress</p>
                  <Progress value={getPhaseProgress(selectedPlan)} className="h-3 mt-2" />
                </div>
                <div className="text-right">
                  <p className="text-2xl font-bold">{getPhaseProgress(selectedPlan)}%</p>
                  <p className="text-xs text-muted-foreground">Complete</p>
                </div>
              </div>

              <div className="space-y-3">
                <h4 className="font-medium">Treatment Phases</h4>
                {treatmentPhases.map((phase, index) => {
                  const currentPhase = getCurrentPhase(selectedPlan);
                  const isCompleted = phase.id < currentPhase.id;
                  const isCurrent = phase.id === currentPhase.id;
                  const isPending = phase.id > currentPhase.id;

                  return (
                    <div
                      key={phase.id}
                      className={`flex items-start gap-4 p-3 rounded-lg ${
                        isCurrent ? "bg-primary/10 border border-primary/20" :
                        isCompleted ? "bg-green-50 dark:bg-green-900/10" : "bg-muted/30"
                      }`}
                    >
                      <div className={`p-2 rounded-full ${
                        isCompleted ? "bg-green-500" :
                        isCurrent ? "bg-primary" : "bg-muted"
                      }`}>
                        {isCompleted ? (
                          <CheckCircle className="h-4 w-4 text-white" />
                        ) : isCurrent ? (
                          <Activity className="h-4 w-4 text-white" />
                        ) : (
                          <Clock className="h-4 w-4 text-muted-foreground" />
                        )}
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className={`font-medium ${isPending ? "text-muted-foreground" : ""}`}>
                            {phase.name}
                          </span>
                          {isCurrent && (
                            <Badge variant="default" className="text-xs">Current</Badge>
                          )}
                        </div>
                        <p className={`text-sm ${isPending ? "text-muted-foreground/60" : "text-muted-foreground"}`}>
                          {phase.description}
                        </p>
                      </div>
                      {index < treatmentPhases.length - 1 && (
                        <ArrowRight className="h-4 w-4 text-muted-foreground mt-2" />
                      )}
                    </div>
                  );
                })}
              </div>

              <div className="border-t pt-4">
                <h4 className="font-medium mb-3">Update Status</h4>
                <div className="flex gap-2">
                  <Button
                    variant={selectedPlan.status === "pending" ? "default" : "outline"}
                    onClick={() => updatePlanMutation.mutate({ id: selectedPlan.id, status: "pending" })}
                  >
                    Pending
                  </Button>
                  <Button
                    variant={selectedPlan.status === "active" ? "default" : "outline"}
                    onClick={() => updatePlanMutation.mutate({ id: selectedPlan.id, status: "active" })}
                  >
                    Active
                  </Button>
                  <Button
                    variant={selectedPlan.status === "completed" ? "default" : "outline"}
                    onClick={() => updatePlanMutation.mutate({ id: selectedPlan.id, status: "completed" })}
                  >
                    Completed
                  </Button>
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
