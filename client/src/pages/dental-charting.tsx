import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useParams, Link } from "wouter";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/hooks/use-toast";
import { apiRequest, queryClient } from "@/lib/queryClient";
import { Odontogram, CONDITION_LABELS, CONDITION_COLORS, TOOTH_NAMES } from "@/components/odontogram";
import {
  ArrowLeft,
  Plus,
  Trash2,
  Save,
  CircleDot,
  ListChecks,
  DollarSign,
  FileText,
} from "lucide-react";
import type {
  Patient,
  ToothCondition,
  TreatmentPlan,
  TreatmentPlanProcedure,
} from "@shared/schema";
import { format } from "date-fns";

const CONDITION_TYPES = [
  "missing", "implant", "crown", "bridge", "filling", "decay",
  "fracture", "root_canal", "extraction_needed", "pontic",
  "veneer", "inlay_onlay", "impacted", "healthy",
];

const SURFACES = ["Mesial", "Distal", "Buccal", "Lingual", "Occlusal", "Incisal"];
const SEVERITIES = ["mild", "moderate", "severe"];

const CDT_CODES = [
  { code: "D6010", description: "Surgical placement of implant body - endosteal implant", fee: "2200" },
  { code: "D6056", description: "Prefabricated abutment", fee: "650" },
  { code: "D6058", description: "Abutment supported porcelain/ceramic crown", fee: "1400" },
  { code: "D6114", description: "Implant/abutment supported fixed denture - maxillary", fee: "28500" },
  { code: "D6115", description: "Implant/abutment supported fixed denture - mandibular", fee: "28500" },
  { code: "D7210", description: "Extraction, surgical, erupted tooth w/ elevation of flap", fee: "285" },
  { code: "D7953", description: "Bone replacement graft - first site in quadrant", fee: "875" },
  { code: "D0330", description: "Panoramic radiographic image", fee: "150" },
  { code: "D0367", description: "Cone beam CT capture and interpretation", fee: "350" },
  { code: "D2740", description: "Crown - porcelain/ceramic substrate", fee: "1200" },
  { code: "D2750", description: "Crown - porcelain fused to high noble metal", fee: "1100" },
  { code: "D2950", description: "Core buildup, including any pins when required", fee: "350" },
  { code: "D3310", description: "Endodontic therapy, anterior tooth", fee: "850" },
  { code: "D3330", description: "Endodontic therapy, molar tooth", fee: "1200" },
  { code: "D4341", description: "Periodontal scaling and root planing - four or more teeth", fee: "250" },
  { code: "D9310", description: "Consultation - diagnostic service by specialist", fee: "175" },
];

export default function DentalChartingPage() {
  const params = useParams();
  const patientId = params.id ? parseInt(params.id) : null;
  const { toast } = useToast();
  const [selectedTooth, setSelectedTooth] = useState<number | null>(null);
  const [addConditionOpen, setAddConditionOpen] = useState(false);
  const [addProcedureOpen, setAddProcedureOpen] = useState(false);
  const [conditionForm, setConditionForm] = useState({
    conditionType: "",
    surface: "",
    severity: "",
    notes: "",
  });
  const [procedureForm, setProcedureForm] = useState({
    treatmentPlanId: "",
    cdtCode: "",
    description: "",
    surface: "",
    fee: "",
    insuranceEstimate: "",
    patientCost: "",
    priority: "1",
    notes: "",
  });

  const { data: patient, isLoading: patientLoading } = useQuery<Patient>({
    queryKey: ["/api/patients", patientId],
    enabled: !!patientId,
  });

  const { data: conditions = [], isLoading: conditionsLoading } = useQuery<ToothCondition[]>({
    queryKey: ["/api/patients", patientId, "tooth-conditions"],
    enabled: !!patientId,
  });

  const { data: treatmentPlans = [] } = useQuery<TreatmentPlan[]>({
    queryKey: ["/api/treatment-plans"],
    enabled: !!patientId,
  });

  const { data: procedures = [], isLoading: proceduresLoading } = useQuery<TreatmentPlanProcedure[]>({
    queryKey: ["/api/patients", patientId, "procedures"],
    enabled: !!patientId,
  });

  const createConditionMutation = useMutation({
    mutationFn: async (data: any) => {
      const res = await apiRequest("POST", `/api/patients/${patientId}/tooth-conditions`, data);
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/patients", patientId, "tooth-conditions"] });
      setAddConditionOpen(false);
      setConditionForm({ conditionType: "", surface: "", severity: "", notes: "" });
      toast({ title: "Condition added", description: "Tooth condition recorded successfully." });
    },
    onError: () => {
      toast({ title: "Error", description: "Failed to add condition.", variant: "destructive" });
    },
  });

  const deleteConditionMutation = useMutation({
    mutationFn: async (id: number) => {
      await apiRequest("DELETE", `/api/tooth-conditions/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/patients", patientId, "tooth-conditions"] });
      toast({ title: "Condition removed" });
    },
  });

  const createProcedureMutation = useMutation({
    mutationFn: async (data: any) => {
      const planId = data.treatmentPlanId;
      const res = await apiRequest("POST", `/api/treatment-plans/${planId}/procedures`, data);
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/patients", patientId, "procedures"] });
      setAddProcedureOpen(false);
      setProcedureForm({ treatmentPlanId: "", cdtCode: "", description: "", surface: "", fee: "", insuranceEstimate: "", patientCost: "", priority: "1", notes: "" });
      toast({ title: "Procedure added", description: "Treatment procedure linked to tooth." });
    },
    onError: () => {
      toast({ title: "Error", description: "Failed to add procedure.", variant: "destructive" });
    },
  });

  const deleteProcedureMutation = useMutation({
    mutationFn: async (id: number) => {
      await apiRequest("DELETE", `/api/procedures/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/patients", patientId, "procedures"] });
      toast({ title: "Procedure removed" });
    },
  });

  const handleAddCondition = () => {
    if (!selectedTooth || !conditionForm.conditionType) return;
    createConditionMutation.mutate({
      patientId,
      toothNumber: selectedTooth,
      conditionType: conditionForm.conditionType,
      surface: conditionForm.surface || null,
      severity: conditionForm.severity || null,
      notes: conditionForm.notes || null,
    });
  };

  const handleAddProcedure = () => {
    if (!procedureForm.treatmentPlanId || !procedureForm.cdtCode || !procedureForm.fee) return;
    createProcedureMutation.mutate({
      treatmentPlanId: parseInt(procedureForm.treatmentPlanId),
      patientId,
      toothNumber: selectedTooth,
      cdtCode: procedureForm.cdtCode,
      description: procedureForm.description,
      surface: procedureForm.surface || null,
      fee: procedureForm.fee,
      insuranceEstimate: procedureForm.insuranceEstimate || null,
      patientCost: procedureForm.patientCost || null,
      priority: parseInt(procedureForm.priority),
      notes: procedureForm.notes || null,
    });
  };

  const handleCdtSelect = (code: string) => {
    const cdt = CDT_CODES.find(c => c.code === code);
    if (cdt) {
      setProcedureForm(f => ({ ...f, cdtCode: code, description: cdt.description, fee: cdt.fee }));
    }
  };

  const selectedToothConditions = selectedTooth ? conditions.filter(c => c.toothNumber === selectedTooth) : [];
  const selectedToothProcedures = selectedTooth ? procedures.filter(p => p.toothNumber === selectedTooth) : [];

  const totalFees = procedures.reduce((sum, p) => sum + parseFloat(p.fee || "0"), 0);
  const totalInsurance = procedures.reduce((sum, p) => sum + parseFloat(p.insuranceEstimate || "0"), 0);
  const totalPatient = procedures.reduce((sum, p) => sum + parseFloat(p.patientCost || "0"), 0);

  if (!patientId) {
    return (
      <div className="p-6">
        <Card>
          <CardContent className="p-8 text-center">
            <p className="text-muted-foreground">No patient selected. Please navigate from a patient record.</p>
            <Link href="/patients">
              <Button className="mt-4" data-testid="link-patients">View Patients</Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (patientLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-[300px] w-full" />
        <Skeleton className="h-[200px] w-full" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 overflow-y-auto h-full">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-3">
          <Link href={`/patients/${patientId}`}>
            <Button variant="ghost" size="icon" data-testid="button-back">
              <ArrowLeft />
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold" data-testid="text-page-title">
              Dental Chart
            </h1>
            <p className="text-muted-foreground">
              {patient ? `${patient.firstName} ${patient.lastName}` : "Patient"} - Interactive Odontogram
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <Badge variant="outline" className="text-xs">
            {conditions.filter(c => c.status === "active").length} Active Conditions
          </Badge>
          <Badge variant="outline" className="text-xs">
            {procedures.length} Procedures
          </Badge>
        </div>
      </div>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-lg">
            <CircleDot className="w-5 h-5" />
            Odontogram
          </CardTitle>
        </CardHeader>
        <CardContent>
          {conditionsLoading ? (
            <Skeleton className="h-[200px] w-full" />
          ) : (
            <Odontogram
              conditions={conditions}
              selectedTooth={selectedTooth}
              onSelectTooth={setSelectedTooth}
            />
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1">
          <Card className="h-full">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center justify-between gap-2 text-base">
                <span className="flex items-center gap-2">
                  <FileText className="w-4 h-4" />
                  {selectedTooth ? `Tooth #${selectedTooth}` : "Select a Tooth"}
                </span>
                {selectedTooth && (
                  <Dialog open={addConditionOpen} onOpenChange={setAddConditionOpen}>
                    <DialogTrigger asChild>
                      <Button size="sm" data-testid="button-add-condition">
                        <Plus className="w-4 h-4 mr-1" /> Condition
                      </Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>Add Condition - Tooth #{selectedTooth}</DialogTitle>
                      </DialogHeader>
                      <div className="space-y-4">
                        <div>
                          <Label>Condition Type</Label>
                          <Select value={conditionForm.conditionType} onValueChange={v => setConditionForm(f => ({ ...f, conditionType: v }))}>
                            <SelectTrigger data-testid="select-condition-type">
                              <SelectValue placeholder="Select condition" />
                            </SelectTrigger>
                            <SelectContent>
                              {CONDITION_TYPES.map(type => (
                                <SelectItem key={type} value={type}>
                                  <span className="flex items-center gap-2">
                                    <span className="w-2 h-2 rounded-full inline-block" style={{ backgroundColor: CONDITION_COLORS[type] }} />
                                    {CONDITION_LABELS[type]}
                                  </span>
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                        <div>
                          <Label>Surface (optional)</Label>
                          <Select value={conditionForm.surface} onValueChange={v => setConditionForm(f => ({ ...f, surface: v }))}>
                            <SelectTrigger data-testid="select-surface">
                              <SelectValue placeholder="Select surface" />
                            </SelectTrigger>
                            <SelectContent>
                              {SURFACES.map(s => (
                                <SelectItem key={s} value={s}>{s}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                        <div>
                          <Label>Severity (optional)</Label>
                          <Select value={conditionForm.severity} onValueChange={v => setConditionForm(f => ({ ...f, severity: v }))}>
                            <SelectTrigger data-testid="select-severity">
                              <SelectValue placeholder="Select severity" />
                            </SelectTrigger>
                            <SelectContent>
                              {SEVERITIES.map(s => (
                                <SelectItem key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                        <div>
                          <Label>Notes</Label>
                          <Textarea
                            value={conditionForm.notes}
                            onChange={e => setConditionForm(f => ({ ...f, notes: e.target.value }))}
                            placeholder="Clinical notes..."
                            data-testid="input-condition-notes"
                          />
                        </div>
                        <Button onClick={handleAddCondition} className="w-full" disabled={createConditionMutation.isPending} data-testid="button-save-condition">
                          <Save className="w-4 h-4 mr-1" />
                          {createConditionMutation.isPending ? "Saving..." : "Save Condition"}
                        </Button>
                      </div>
                    </DialogContent>
                  </Dialog>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {!selectedTooth ? (
                <p className="text-sm text-muted-foreground py-4 text-center">
                  Click a tooth on the chart above to view its conditions and procedures.
                </p>
              ) : (
                <div className="space-y-3">
                  <p className="text-sm text-muted-foreground">{TOOTH_NAMES[selectedTooth]}</p>
                  {selectedToothConditions.length === 0 ? (
                    <p className="text-sm text-muted-foreground italic">No conditions recorded</p>
                  ) : (
                    selectedToothConditions.map(c => (
                      <div key={c.id} className="flex items-start justify-between gap-2 p-2 rounded-md border" data-testid={`condition-item-${c.id}`}>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: CONDITION_COLORS[c.conditionType] }} />
                            <span className="text-sm font-medium">{CONDITION_LABELS[c.conditionType] || c.conditionType}</span>
                            {c.surface && <Badge variant="outline" className="text-xs">{c.surface}</Badge>}
                            {c.severity && <Badge variant="secondary" className="text-xs">{c.severity}</Badge>}
                          </div>
                          {c.notes && <p className="text-xs text-muted-foreground mt-1">{c.notes}</p>}
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => deleteConditionMutation.mutate(c.id)}
                          data-testid={`button-delete-condition-${c.id}`}
                        >
                          <Trash2 className="w-3 h-3" />
                        </Button>
                      </div>
                    ))
                  )}

                  {selectedToothProcedures.length > 0 && (
                    <>
                      <Separator />
                      <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Procedures</p>
                      {selectedToothProcedures.map(p => (
                        <div key={p.id} className="p-2 rounded-md border text-sm" data-testid={`procedure-item-${p.id}`}>
                          <div className="flex items-center justify-between gap-2 flex-wrap">
                            <span className="font-mono text-xs">{p.cdtCode}</span>
                            <Badge variant={p.status === "completed" ? "default" : "outline"} className="text-xs">{p.status}</Badge>
                          </div>
                          <p className="text-xs text-muted-foreground mt-0.5">{p.description}</p>
                          <p className="text-xs font-medium mt-1">${parseFloat(p.fee).toLocaleString()}</p>
                        </div>
                      ))}
                    </>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="lg:col-span-2">
          <Tabs defaultValue="procedures">
            <TabsList>
              <TabsTrigger value="procedures" data-testid="tab-procedures">
                <ListChecks className="w-4 h-4 mr-1" /> Procedures
              </TabsTrigger>
              <TabsTrigger value="summary" data-testid="tab-summary">
                <DollarSign className="w-4 h-4 mr-1" /> Summary
              </TabsTrigger>
            </TabsList>

            <TabsContent value="procedures">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center justify-between gap-2 text-base flex-wrap">
                    <span>All Treatment Procedures</span>
                    <Dialog open={addProcedureOpen} onOpenChange={setAddProcedureOpen}>
                      <DialogTrigger asChild>
                        <Button size="sm" data-testid="button-add-procedure">
                          <Plus className="w-4 h-4 mr-1" /> Add Procedure
                        </Button>
                      </DialogTrigger>
                      <DialogContent className="max-w-lg">
                        <DialogHeader>
                          <DialogTitle>
                            Add Procedure {selectedTooth ? `- Tooth #${selectedTooth}` : ""}
                          </DialogTitle>
                        </DialogHeader>
                        <div className="space-y-4 max-h-[60vh] overflow-y-auto pr-1">
                          <div>
                            <Label>Treatment Plan</Label>
                            <Select value={procedureForm.treatmentPlanId} onValueChange={v => setProcedureForm(f => ({ ...f, treatmentPlanId: v }))}>
                              <SelectTrigger data-testid="select-treatment-plan">
                                <SelectValue placeholder="Select treatment plan" />
                              </SelectTrigger>
                              <SelectContent>
                                {treatmentPlans.map(tp => (
                                  <SelectItem key={tp.id} value={String(tp.id)}>
                                    {tp.planName} - {tp.status}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>
                          <div>
                            <Label>CDT Code</Label>
                            <Select value={procedureForm.cdtCode} onValueChange={handleCdtSelect}>
                              <SelectTrigger data-testid="select-cdt-code">
                                <SelectValue placeholder="Select CDT code" />
                              </SelectTrigger>
                              <SelectContent>
                                {CDT_CODES.map(c => (
                                  <SelectItem key={c.code} value={c.code}>
                                    {c.code} - {c.description.slice(0, 50)}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>
                          <div>
                            <Label>Description</Label>
                            <Input
                              value={procedureForm.description}
                              onChange={e => setProcedureForm(f => ({ ...f, description: e.target.value }))}
                              data-testid="input-procedure-description"
                            />
                          </div>
                          <div className="grid grid-cols-3 gap-3">
                            <div>
                              <Label>Fee ($)</Label>
                              <Input
                                type="number"
                                value={procedureForm.fee}
                                onChange={e => setProcedureForm(f => ({ ...f, fee: e.target.value }))}
                                data-testid="input-fee"
                              />
                            </div>
                            <div>
                              <Label>Ins. Est. ($)</Label>
                              <Input
                                type="number"
                                value={procedureForm.insuranceEstimate}
                                onChange={e => setProcedureForm(f => ({ ...f, insuranceEstimate: e.target.value }))}
                                data-testid="input-insurance-estimate"
                              />
                            </div>
                            <div>
                              <Label>Pt. Cost ($)</Label>
                              <Input
                                type="number"
                                value={procedureForm.patientCost}
                                onChange={e => setProcedureForm(f => ({ ...f, patientCost: e.target.value }))}
                                data-testid="input-patient-cost"
                              />
                            </div>
                          </div>
                          <div className="grid grid-cols-2 gap-3">
                            <div>
                              <Label>Surface</Label>
                              <Select value={procedureForm.surface} onValueChange={v => setProcedureForm(f => ({ ...f, surface: v }))}>
                                <SelectTrigger data-testid="select-procedure-surface">
                                  <SelectValue placeholder="Optional" />
                                </SelectTrigger>
                                <SelectContent>
                                  {SURFACES.map(s => (
                                    <SelectItem key={s} value={s}>{s}</SelectItem>
                                  ))}
                                </SelectContent>
                              </Select>
                            </div>
                            <div>
                              <Label>Priority</Label>
                              <Select value={procedureForm.priority} onValueChange={v => setProcedureForm(f => ({ ...f, priority: v }))}>
                                <SelectTrigger data-testid="select-priority">
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="1">1 - Urgent</SelectItem>
                                  <SelectItem value="2">2 - High</SelectItem>
                                  <SelectItem value="3">3 - Normal</SelectItem>
                                  <SelectItem value="4">4 - Low</SelectItem>
                                </SelectContent>
                              </Select>
                            </div>
                          </div>
                          <div>
                            <Label>Notes</Label>
                            <Textarea
                              value={procedureForm.notes}
                              onChange={e => setProcedureForm(f => ({ ...f, notes: e.target.value }))}
                              placeholder="Procedure notes..."
                              data-testid="input-procedure-notes"
                            />
                          </div>
                          <Button onClick={handleAddProcedure} className="w-full" disabled={createProcedureMutation.isPending} data-testid="button-save-procedure">
                            <Save className="w-4 h-4 mr-1" />
                            {createProcedureMutation.isPending ? "Saving..." : "Save Procedure"}
                          </Button>
                        </div>
                      </DialogContent>
                    </Dialog>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {proceduresLoading ? (
                    <Skeleton className="h-[200px] w-full" />
                  ) : procedures.length === 0 ? (
                    <p className="text-sm text-muted-foreground text-center py-8">
                      No procedures added yet. Select a tooth and click "Add Procedure" to begin treatment planning.
                    </p>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm" data-testid="table-procedures">
                        <thead>
                          <tr className="border-b text-left text-muted-foreground">
                            <th className="py-2 pr-3">Tooth</th>
                            <th className="py-2 pr-3">CDT</th>
                            <th className="py-2 pr-3">Description</th>
                            <th className="py-2 pr-3">Surface</th>
                            <th className="py-2 pr-3 text-right">Fee</th>
                            <th className="py-2 pr-3 text-right">Ins Est.</th>
                            <th className="py-2 pr-3 text-right">Pt Cost</th>
                            <th className="py-2 pr-3">Status</th>
                            <th className="py-2 w-10"></th>
                          </tr>
                        </thead>
                        <tbody>
                          {procedures.map(p => (
                            <tr key={p.id} className="border-b hover-elevate" data-testid={`row-procedure-${p.id}`}>
                              <td className="py-2 pr-3 font-mono">
                                {p.toothNumber ? `#${p.toothNumber}` : "-"}
                              </td>
                              <td className="py-2 pr-3 font-mono font-medium">{p.cdtCode}</td>
                              <td className="py-2 pr-3 max-w-[200px] truncate">{p.description}</td>
                              <td className="py-2 pr-3">{p.surface || "-"}</td>
                              <td className="py-2 pr-3 text-right font-medium">${parseFloat(p.fee).toLocaleString()}</td>
                              <td className="py-2 pr-3 text-right">{p.insuranceEstimate ? `$${parseFloat(p.insuranceEstimate).toLocaleString()}` : "-"}</td>
                              <td className="py-2 pr-3 text-right">{p.patientCost ? `$${parseFloat(p.patientCost).toLocaleString()}` : "-"}</td>
                              <td className="py-2 pr-3">
                                <Badge variant={p.status === "completed" ? "default" : "outline"} className="text-xs">
                                  {p.status}
                                </Badge>
                              </td>
                              <td className="py-2">
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  onClick={() => deleteProcedureMutation.mutate(p.id)}
                                  data-testid={`button-delete-procedure-${p.id}`}
                                >
                                  <Trash2 className="w-3 h-3" />
                                </Button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="summary">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">Financial Summary</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <div className="p-4 rounded-md border text-center">
                      <p className="text-xs text-muted-foreground uppercase tracking-wider">Total Fees</p>
                      <p className="text-2xl font-bold mt-1" data-testid="text-total-fees">
                        ${totalFees.toLocaleString()}
                      </p>
                    </div>
                    <div className="p-4 rounded-md border text-center">
                      <p className="text-xs text-muted-foreground uppercase tracking-wider">Insurance Estimate</p>
                      <p className="text-2xl font-bold mt-1 text-green-600" data-testid="text-total-insurance">
                        ${totalInsurance.toLocaleString()}
                      </p>
                    </div>
                    <div className="p-4 rounded-md border text-center">
                      <p className="text-xs text-muted-foreground uppercase tracking-wider">Patient Responsibility</p>
                      <p className="text-2xl font-bold mt-1 text-amber-600" data-testid="text-total-patient">
                        ${totalPatient.toLocaleString()}
                      </p>
                    </div>
                  </div>

                  <Separator className="my-4" />

                  <div className="space-y-2">
                    <p className="text-sm font-medium">Conditions Summary</p>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                      {Object.entries(
                        conditions.filter(c => c.status === "active").reduce((acc, c) => {
                          acc[c.conditionType] = (acc[c.conditionType] || 0) + 1;
                          return acc;
                        }, {} as Record<string, number>)
                      ).map(([type, count]) => (
                        <div key={type} className="flex items-center gap-2 p-2 rounded-md border">
                          <span className="w-3 h-3 rounded-sm flex-shrink-0" style={{ backgroundColor: CONDITION_COLORS[type] }} />
                          <span className="text-xs">{CONDITION_LABELS[type]}</span>
                          <Badge variant="secondary" className="ml-auto text-xs">{count}</Badge>
                        </div>
                      ))}
                    </div>
                  </div>

                  <Separator className="my-4" />

                  <div className="space-y-2">
                    <p className="text-sm font-medium">Procedures by Status</p>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                      {Object.entries(
                        procedures.reduce((acc, p) => {
                          acc[p.status] = (acc[p.status] || 0) + 1;
                          return acc;
                        }, {} as Record<string, number>)
                      ).map(([status, count]) => (
                        <div key={status} className="flex items-center justify-between p-2 rounded-md border">
                          <span className="text-xs capitalize">{status}</span>
                          <Badge variant="secondary" className="text-xs">{count}</Badge>
                        </div>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  );
}
