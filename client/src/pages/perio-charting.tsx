import { useState, useCallback, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { apiRequest } from "@/lib/queryClient";
import {
  BarChart3, Droplets, TrendingDown, Activity, User, Calendar,
  Bot, Printer, FileText, Plus, Save, History, ChevronRight,
  AlertTriangle, CheckCircle, Loader2,
} from "lucide-react";

// ─── Types ───────────────────────────────────────────────────────────────────
interface ToothData {
  facialProbing: [number, number, number];
  lingualProbing: [number, number, number];
  facialBop: [boolean, boolean, boolean];
  lingualBop: [boolean, boolean, boolean];
  facialRecession: [number, number, number];
  lingualRecession: [number, number, number];
  mobility: number;
  furcation: number;
  missing: boolean;
  implant: boolean;
}

type ProbingData = Record<number, ToothData>;

const FURCATION_TEETH = [3, 4, 5, 6, 12, 13, 14, 15, 19, 20, 21, 28, 29, 30];
const UPPER_TEETH = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16];
const LOWER_TEETH = [32, 31, 30, 29, 28, 27, 26, 25, 24, 23, 22, 21, 20, 19, 18, 17];

function defaultTooth(): ToothData {
  return {
    facialProbing: [2, 2, 2],
    lingualProbing: [2, 2, 2],
    facialBop: [false, false, false],
    lingualBop: [false, false, false],
    facialRecession: [0, 0, 0],
    lingualRecession: [0, 0, 0],
    mobility: 0,
    furcation: 0,
    missing: false,
    implant: false,
  };
}

function defaultProbingData(): ProbingData {
  const data: ProbingData = {};
  for (let t = 1; t <= 32; t++) data[t] = defaultTooth();
  return data;
}

function depthColor(v: number) {
  if (v >= 6) return "bg-red-500/20 text-red-600 dark:text-red-400 font-bold border border-red-400/40";
  if (v >= 4) return "bg-amber-400/20 text-amber-600 dark:text-amber-400 font-bold border border-amber-400/40";
  return "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-transparent";
}

function furcationSymbol(f: number) {
  if (f === 0) return null;
  return <span className={`text-[8px] font-bold ${f === 3 ? "text-red-500" : f === 2 ? "text-amber-500" : "text-blue-500"}`}>{["", "▲", "▲▲", "▲▲▲"][f]}</span>;
}

// ─── Cell: editable probing depth ─────────────────────────────────────────
function ProbingCell({ value, onChange, bop, onBopToggle }: {
  value: number; onChange: (v: number) => void;
  bop: boolean; onBopToggle: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [raw, setRaw] = useState(String(value));

  if (editing) {
    return (
      <input
        autoFocus
        className={`w-5 h-5 text-center text-[10px] font-mono rounded outline-none focus:ring-1 focus:ring-primary ${depthColor(value)}`}
        value={raw}
        onChange={e => setRaw(e.target.value)}
        onBlur={() => {
          const n = parseInt(raw);
          if (!isNaN(n) && n >= 0 && n <= 12) onChange(n);
          setEditing(false);
        }}
        onKeyDown={e => {
          if (e.key === "Enter" || e.key === "Tab") {
            const n = parseInt(raw);
            if (!isNaN(n) && n >= 0 && n <= 12) onChange(n);
            setEditing(false);
          }
          if (e.key === "Escape") setEditing(false);
        }}
        style={{ width: 20, height: 20 }}
      />
    );
  }

  return (
    <div className="flex flex-col items-center gap-0.5">
      <div
        className={`w-5 h-5 flex items-center justify-center rounded text-[10px] font-mono cursor-pointer hover:opacity-80 ${depthColor(value)}`}
        onClick={() => { setRaw(String(value)); setEditing(true); }}
        data-testid={`probing-cell-${value}`}
      >
        {value}
      </div>
      <button
        onClick={onBopToggle}
        className={`w-2 h-2 rounded-full border transition-colors ${bop ? "bg-red-500 border-red-600" : "border-muted-foreground/30 hover:border-red-400"}`}
        title={bop ? "BOP: Yes" : "BOP: No"}
        data-testid={`bop-dot-${bop}`}
      />
    </div>
  );
}

// ─── Single tooth column ───────────────────────────────────────────────────
function ToothColumn({ toothNum, data, onChange }: {
  toothNum: number;
  data: ToothData;
  onChange: (t: number, d: ToothData) => void;
}) {
  const update = useCallback((patch: Partial<ToothData>) => onChange(toothNum, { ...data, ...patch }), [data, onChange, toothNum]);

  const hasFurcation = FURCATION_TEETH.includes(toothNum);
  const isUpper = UPPER_TEETH.includes(toothNum);

  return (
    <div
      className={`flex flex-col items-center gap-0.5 min-w-0 flex-1 ${data.missing ? "opacity-30" : ""}`}
      data-testid={`tooth-col-${toothNum}`}
    >
      {/* Facial probing row */}
      <div className="flex gap-px">
        {data.facialProbing.map((v, i) => (
          <ProbingCell
            key={i}
            value={v}
            onChange={nv => { const p = [...data.facialProbing] as [number, number, number]; p[i] = nv; update({ facialProbing: p }); }}
            bop={data.facialBop[i]}
            onBopToggle={() => { const b = [...data.facialBop] as [boolean, boolean, boolean]; b[i] = !b[i]; update({ facialBop: b }); }}
          />
        ))}
      </div>

      {/* Tooth number + controls */}
      <div className="flex flex-col items-center gap-px">
        {hasFurcation && furcationSymbol(data.furcation) && (
          <button
            className="cursor-pointer"
            onClick={() => update({ furcation: (data.furcation + 1) % 4 })}
            title={`Furcation Class ${data.furcation} (click to change)`}
          >
            {furcationSymbol(data.furcation)}
          </button>
        )}
        <div
          className={`text-[9px] font-bold leading-none select-none cursor-pointer px-0.5 rounded ${data.missing ? "text-muted-foreground line-through" : "text-foreground"} ${data.implant ? "text-blue-500" : ""}`}
          onClick={() => update({ missing: !data.missing })}
          title="Click to toggle missing"
        >
          {toothNum}
        </div>
        {/* Mobility */}
        <button
          className={`text-[8px] leading-none px-0.5 rounded ${data.mobility > 0 ? "text-amber-600 dark:text-amber-400 font-bold" : "text-muted-foreground/40"}`}
          onClick={() => update({ mobility: (data.mobility + 1) % 4 })}
          title={`Mobility: ${data.mobility} (click to change)`}
        >
          {data.mobility > 0 ? `M${data.mobility}` : "·"}
        </button>
      </div>

      {/* Lingual probing row */}
      <div className="flex gap-px">
        {data.lingualProbing.map((v, i) => (
          <ProbingCell
            key={i}
            value={v}
            onChange={nv => { const p = [...data.lingualProbing] as [number, number, number]; p[i] = nv; update({ lingualProbing: p }); }}
            bop={data.lingualBop[i]}
            onBopToggle={() => { const b = [...data.lingualBop] as [boolean, boolean, boolean]; b[i] = !b[i]; update({ lingualBop: b }); }}
          />
        ))}
      </div>
    </div>
  );
}

// ─── Stats calculation ─────────────────────────────────────────────────────
function calcStats(data: ProbingData) {
  const depths: number[] = [];
  let bopCount = 0, totalSites = 0, gt4 = 0, gt6 = 0;
  Object.entries(data).forEach(([, t]) => {
    if (t.missing) return;
    const ds = [...t.facialProbing, ...t.lingualProbing];
    const bs = [...t.facialBop, ...t.lingualBop];
    ds.forEach(d => { depths.push(d); totalSites++; if (d >= 4) gt4++; if (d >= 6) gt6++; });
    bs.forEach(b => { if (b) bopCount++; });
  });
  const avg = depths.length ? (depths.reduce((a, b) => a + b, 0) / depths.length).toFixed(1) : "0";
  const bopPct = totalSites ? Math.round((bopCount / totalSites) * 100) : 0;
  return { avg, bopPct, gt4, gt6, totalSites };
}

// ─── Main Page ─────────────────────────────────────────────────────────────
export default function PerioChartingPage() {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const [selectedPatientId, setSelectedPatientId] = useState<number | null>(null);
  const [selectedExamId, setSelectedExamId] = useState<number | null>(null);
  const [probingData, setProbingData] = useState<ProbingData>(defaultProbingData());
  const [examDate, setExamDate] = useState(new Date().toISOString().split("T")[0]);
  const [diagnosisStage, setDiagnosisStage] = useState("III");
  const [diagnosisGrade, setDiagnosisGrade] = useState("B");
  const [diagnosisExtent, setDiagnosisExtent] = useState("Generalized");
  const [notes, setNotes] = useState("");
  const [aiAssessment, setAiAssessment] = useState("");
  const [aiLoading, setAiLoading] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  const { data: patients = [] } = useQuery<any[]>({ queryKey: ["/api/patients"] });
  const { data: exams = [] } = useQuery<any[]>({
    queryKey: ["/api/perio", selectedPatientId],
    enabled: !!selectedPatientId,
    queryFn: () => fetch(`/api/perio/${selectedPatientId}`, { credentials: "include" }).then(r => r.json()),
  });

  const selectedPatient = patients.find((p: any) => p.id === selectedPatientId);
  const stats = calcStats(probingData);

  const saveMutation = useMutation({
    mutationFn: async () => {
      const body = {
        patientId: selectedPatientId,
        examDate,
        probingData,
        diagnosisStage,
        diagnosisGrade,
        diagnosisExtent,
        notes,
        aiAssessment,
        providerName: "Dr. Provider",
      };
      if (selectedExamId) {
        return apiRequest("PUT", `/api/perio/exam/${selectedExamId}`, body);
      }
      return apiRequest("POST", "/api/perio", body);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/perio", selectedPatientId] });
      toast({ title: "Perio exam saved", description: "Chart saved successfully." });
    },
    onError: () => toast({ title: "Error", description: "Failed to save exam.", variant: "destructive" }),
  });

  const handleToothChange = useCallback((t: number, d: ToothData) => {
    setProbingData(prev => ({ ...prev, [t]: d }));
  }, []);

  const loadExam = (exam: any) => {
    setSelectedExamId(exam.id);
    setProbingData((exam.probingData as ProbingData) || defaultProbingData());
    setExamDate(exam.examDate);
    setDiagnosisStage(exam.diagnosisStage || "III");
    setDiagnosisGrade(exam.diagnosisGrade || "B");
    setDiagnosisExtent(exam.diagnosisExtent || "Generalized");
    setNotes(exam.notes || "");
    setAiAssessment(exam.aiAssessment || "");
    setShowHistory(false);
  };

  const newExam = () => {
    setSelectedExamId(null);
    setProbingData(defaultProbingData());
    setExamDate(new Date().toISOString().split("T")[0]);
    setAiAssessment("");
    setNotes("");
  };

  const generateAi = async () => {
    if (!selectedPatient) return;
    setAiLoading(true);
    try {
      const res = await apiRequest("POST", "/api/perio/ai-assessment", {
        probingData,
        patientName: `${selectedPatient.firstName} ${selectedPatient.lastName}`,
      });
      const data = await res.json();
      setAiAssessment(data.assessment || "");
    } catch {
      toast({ title: "AI Error", description: "Could not generate assessment.", variant: "destructive" });
    } finally {
      setAiLoading(false);
    }
  };

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">Periodontal Charting</h1>
          <p className="text-sm text-muted-foreground">6-point probing · BOP · Recession · Mobility · Furcation · AI Diagnosis</p>
        </div>
        <div className="flex items-center gap-2">
          {selectedPatientId && (
            <>
              <Button size="sm" variant="outline" onClick={() => setShowHistory(!showHistory)} data-testid="button-history">
                <History className="h-3.5 w-3.5 mr-1" />
                History ({exams.length})
              </Button>
              <Button size="sm" variant="outline" onClick={newExam} data-testid="button-new-exam">
                <Plus className="h-3.5 w-3.5 mr-1" />
                New Exam
              </Button>
              <Button
                size="sm"
                onClick={() => saveMutation.mutate()}
                disabled={saveMutation.isPending}
                data-testid="button-save-exam"
              >
                {saveMutation.isPending ? <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" /> : <Save className="h-3.5 w-3.5 mr-1" />}
                Save Chart
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Patient + Exam Selector */}
      <Card>
        <CardContent className="pt-4 pb-4">
          <div className="flex flex-wrap items-end gap-4">
            <div className="flex-1 min-w-[200px]">
              <Label className="text-xs text-muted-foreground mb-1 block">Patient</Label>
              <Select
                value={selectedPatientId?.toString() || ""}
                onValueChange={v => { setSelectedPatientId(parseInt(v)); setSelectedExamId(null); setProbingData(defaultProbingData()); }}
              >
                <SelectTrigger data-testid="select-patient">
                  <SelectValue placeholder="Select patient…" />
                </SelectTrigger>
                <SelectContent>
                  {patients.map((p: any) => (
                    <SelectItem key={p.id} value={p.id.toString()}>
                      {p.firstName} {p.lastName}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {selectedPatientId && (
              <>
                <div>
                  <Label className="text-xs text-muted-foreground mb-1 block">Exam Date</Label>
                  <input
                    type="date"
                    value={examDate}
                    onChange={e => setExamDate(e.target.value)}
                    className="h-9 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
                    data-testid="input-exam-date"
                  />
                </div>
                <div>
                  <Label className="text-xs text-muted-foreground mb-1 block">Diagnosis Stage</Label>
                  <Select value={diagnosisStage} onValueChange={setDiagnosisStage}>
                    <SelectTrigger className="w-28" data-testid="select-stage">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {["I", "II", "III", "IV"].map(s => <SelectItem key={s} value={s}>Stage {s}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-xs text-muted-foreground mb-1 block">Grade</Label>
                  <Select value={diagnosisGrade} onValueChange={setDiagnosisGrade}>
                    <SelectTrigger className="w-24" data-testid="select-grade">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {["A", "B", "C"].map(g => <SelectItem key={g} value={g}>Grade {g}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-xs text-muted-foreground mb-1 block">Extent</Label>
                  <Select value={diagnosisExtent} onValueChange={setDiagnosisExtent}>
                    <SelectTrigger className="w-36" data-testid="select-extent">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {["Localized", "Generalized", "Molar-incisor"].map(x => <SelectItem key={x} value={x}>{x}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
              </>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Exam History Panel */}
      {showHistory && exams.length > 0 && (
        <Card className="border-blue-500/20 bg-blue-500/5">
          <CardHeader className="pb-2 pt-4">
            <CardTitle className="text-sm flex items-center gap-2">
              <History className="h-4 w-4" /> Exam History
            </CardTitle>
          </CardHeader>
          <CardContent className="pb-4">
            <div className="flex flex-wrap gap-2">
              {exams.map((e: any) => (
                <button
                  key={e.id}
                  onClick={() => loadExam(e)}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-sm transition-colors ${
                    selectedExamId === e.id
                      ? "bg-primary text-primary-foreground border-primary"
                      : "bg-background border-border hover:border-primary/50"
                  }`}
                  data-testid={`button-load-exam-${e.id}`}
                >
                  <Calendar className="h-3 w-3" />
                  {e.examDate}
                  <Badge variant="outline" className="text-[10px]">
                    Stage {e.diagnosisStage} / Grade {e.diagnosisGrade}
                  </Badge>
                  <ChevronRight className="h-3 w-3 opacity-50" />
                </button>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* KPI Stats */}
      {selectedPatientId && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <Card>
            <CardContent className="pt-4 pb-4">
              <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1">
                <BarChart3 className="h-3 w-3" /> Avg Probing
              </div>
              <div className="text-2xl font-bold font-mono" data-testid="kpi-avg-probing">{stats.avg}mm</div>
              <p className={`text-xs font-medium mt-0.5 ${parseFloat(stats.avg) >= 4 ? "text-amber-600 dark:text-amber-400" : "text-emerald-600 dark:text-emerald-400"}`}>
                {parseFloat(stats.avg) >= 4 ? "Moderate concern" : "Within normal"}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 pb-4">
              <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1">
                <Droplets className="h-3 w-3" /> BOP %
              </div>
              <div className={`text-2xl font-bold font-mono ${stats.bopPct >= 10 ? "text-red-600 dark:text-red-400" : "text-emerald-600 dark:text-emerald-400"}`} data-testid="kpi-bop">
                {stats.bopPct}%
              </div>
              <p className="text-xs text-muted-foreground mt-0.5">Target: &lt;10%</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 pb-4">
              <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1">
                <TrendingDown className="h-3 w-3" /> Sites ≥4mm
              </div>
              <div className={`text-2xl font-bold font-mono ${stats.gt4 > 20 ? "text-amber-600 dark:text-amber-400" : ""}`} data-testid="kpi-sites-4mm">{stats.gt4}</div>
              <p className="text-xs text-muted-foreground mt-0.5">of {stats.totalSites} total sites</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 pb-4">
              <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1">
                <Activity className="h-3 w-3" /> Sites ≥6mm
              </div>
              <div className={`text-2xl font-bold font-mono ${stats.gt6 > 0 ? "text-red-600 dark:text-red-400" : "text-emerald-600 dark:text-emerald-400"}`} data-testid="kpi-sites-6mm">{stats.gt6}</div>
              <div className="mt-0.5">
                <Badge variant="outline" className="text-[10px] px-1">
                  Stage {diagnosisStage} / Grade {diagnosisGrade}
                </Badge>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Interactive Chart */}
      {selectedPatientId ? (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <User className="h-4 w-4" />
              Probing Chart {selectedPatient && `— ${selectedPatient.firstName} ${selectedPatient.lastName}`}
              {selectedExamId && <Badge variant="secondary" className="text-[10px]">Saved Exam #{selectedExamId}</Badge>}
            </CardTitle>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1.5">
                {[
                  { label: "Facial", cls: "bg-sky-500/30 text-sky-700 dark:text-sky-300" },
                  { label: "Lingual", cls: "bg-violet-500/30 text-violet-700 dark:text-violet-300" },
                ].map(l => (
                  <span key={l.label} className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${l.cls}`}>{l.label}</span>
                ))}
              </div>
              <Button size="sm" variant="outline" data-testid="button-print-chart" onClick={() => window.print()}>
                <Printer className="h-3.5 w-3.5 mr-1" /> Print
              </Button>
            </div>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <div className="min-w-[900px]">
              {/* Legend */}
              <div className="flex items-center gap-4 mb-3 text-[10px]">
                <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-emerald-500/20 border border-emerald-400/40 inline-block" /> 1-3mm Healthy</span>
                <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-amber-400/20 border border-amber-400/40 inline-block" /> 4-5mm Moderate</span>
                <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-red-500/20 border border-red-400/40 inline-block" /> 6mm+ Severe</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-500 inline-block" /> BOP</span>
                <span className="text-muted-foreground">Click depth cell to edit · Click tooth# to mark missing · Click M to change mobility · ▲ = furcation</span>
              </div>

              {/* UPPER ARCH */}
              <div className="mb-1 text-[9px] font-bold uppercase tracking-widest text-muted-foreground">Facial — Upper</div>
              <div className="flex gap-0.5 mb-1 bg-sky-500/5 rounded p-1">
                {UPPER_TEETH.map(t => (
                  <ToothColumn key={t} toothNum={t} data={probingData[t]} onChange={handleToothChange} />
                ))}
              </div>
              <div className="mb-3 text-[9px] font-bold uppercase tracking-widest text-muted-foreground">Lingual — Upper</div>

              <div className="border-t border-dashed border-border my-2" />

              {/* LOWER ARCH */}
              <div className="mb-1 text-[9px] font-bold uppercase tracking-widest text-muted-foreground">Lingual — Lower</div>
              <div className="flex gap-0.5 mb-1 bg-violet-500/5 rounded p-1">
                {LOWER_TEETH.map(t => (
                  <ToothColumn key={t} toothNum={t} data={probingData[t]} onChange={handleToothChange} />
                ))}
              </div>
              <div className="mb-1 text-[9px] font-bold uppercase tracking-widest text-muted-foreground">Facial — Lower</div>
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card className="border-dashed">
          <CardContent className="pt-12 pb-12 flex flex-col items-center gap-3 text-muted-foreground">
            <User className="h-10 w-10 opacity-30" />
            <p className="text-sm">Select a patient to begin or continue a perio chart</p>
          </CardContent>
        </Card>
      )}

      {/* Notes + AI */}
      {selectedPatientId && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <FileText className="h-4 w-4" /> Clinical Notes
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Textarea
                placeholder="Clinical observations, patient compliance, home care instructions…"
                value={notes}
                onChange={e => setNotes(e.target.value)}
                rows={5}
                data-testid="textarea-notes"
              />
            </CardContent>
          </Card>

          <Card className="border-purple-500/20 bg-purple-500/5 dark:bg-purple-500/5">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <Bot className="h-4 w-4 text-purple-600 dark:text-purple-400" />
                <span className="text-purple-600 dark:text-purple-400">AI Perio Assessment (Claude)</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {aiAssessment ? (
                <p className="text-sm text-muted-foreground leading-relaxed" data-testid="text-ai-assessment">{aiAssessment}</p>
              ) : (
                <p className="text-sm text-muted-foreground italic">Click below to generate AI-powered periodontal assessment with CDT code recommendations.</p>
              )}
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={generateAi}
                  disabled={aiLoading || !selectedPatientId}
                  data-testid="button-generate-ai"
                >
                  {aiLoading ? <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" /> : <Bot className="h-3.5 w-3.5 mr-1" />}
                  {aiLoading ? "Generating…" : "Generate Assessment"}
                </Button>
                {aiAssessment && (
                  <Button size="sm" variant="outline" data-testid="button-compare">
                    <TrendingDown className="h-3.5 w-3.5 mr-1" /> Compare to Previous
                  </Button>
                )}
              </div>

              {/* Quick diagnosis summary */}
              <div className="pt-2 border-t border-purple-200/30 dark:border-purple-700/20">
                <div className="flex flex-wrap gap-2">
                  <Badge variant="outline" className="text-[10px] bg-background">
                    {stats.gt4} sites ≥4mm
                  </Badge>
                  <Badge variant="outline" className="text-[10px] bg-background">
                    {stats.gt6} sites ≥6mm
                  </Badge>
                  <Badge variant="outline" className={`text-[10px] bg-background ${stats.bopPct >= 10 ? "border-red-400/50 text-red-600 dark:text-red-400" : "border-emerald-400/50 text-emerald-600 dark:text-emerald-400"}`}>
                    BOP {stats.bopPct}%
                  </Badge>
                  <Badge className="text-[10px] bg-purple-600 text-white">
                    Stage {diagnosisStage} / Grade {diagnosisGrade} / {diagnosisExtent}
                  </Badge>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
