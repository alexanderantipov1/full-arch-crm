import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  Brain,
  AlertTriangle,
  CheckCircle,
  Lightbulb,
  FileText,
  Activity,
  Pill,
  Heart,
  Shield,
  TriangleAlert,
  ArrowRight,
  Bot,
} from "lucide-react";

const clinicalAlerts = [
  {
    patient: "Tom Davis",
    alert: "Warfarin detected — INR check required before extraction",
    severity: "critical",
    action: "Request INR from PCP. Target <3.0 for minor surgery.",
  },
  {
    patient: "Margaret Sullivan",
    alert: "Bisphosphonate history — MRONJ risk assessment needed",
    severity: "high",
    action: "Alendronate 5yr+ use. Consider drug holiday consult with physician.",
  },
  {
    patient: "Robert Kim",
    alert: "Diabetes A1C 7.8% — healing risk for implant",
    severity: "moderate",
    action: "A1C borderline. Proceed with enhanced post-op protocol. Re-check in 3mo.",
  },
  {
    patient: "Diana Patel",
    alert: "Latex allergy flagged — ensure non-latex gloves for all procedures",
    severity: "info",
    action: "Chart note confirmed. All operatories stocked with nitrile.",
  },
];

const treatmentGuidelines = [
  { condition: "Missing #14 with sufficient bone", recommendation: "Implant (D6010) preferred over FPD. CBCT confirms 12mm available bone.", evidence: "ADA Clinical Practice Guideline 2024", confidence: 96 },
  { condition: "Stage III Perio — generalized", recommendation: "SRP all quadrants (D4341). Reassess 4-6 weeks. Consider Arestin sites ≥5mm.", evidence: "AAP/EFP Classification 2023", confidence: 94 },
  { condition: "Caries #3 mesial — moderate", recommendation: "Crown (D2740) due to >50% structure loss. MOD composite insufficient.", evidence: "ADA Caries Management Guidelines", confidence: 91 },
  { condition: "#31 periapical radiolucency", recommendation: "Vitality testing + PA radiograph. If non-vital → RCT (D3330) + crown.", evidence: "AAE Position Statement 2024", confidence: 87 },
];

const drugInteractions = [
  { drug1: "Warfarin", drug2: "Ibuprofen", severity: "Major", effect: "Increased bleeding risk. Use acetaminophen instead." },
  { drug1: "Metformin", drug2: "Contrast dye", severity: "Moderate", effect: "Hold metformin 48hr if IV contrast needed for CBCT with contrast." },
  { drug1: "Lisinopril", drug2: "NSAIDs", severity: "Moderate", effect: "NSAIDs may reduce antihypertensive effect. Short course OK." },
];

export default function DecisionSupportPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">
          AI Clinical Decision Support
        </h1>
        <p className="text-sm text-muted-foreground">
          Evidence-based alerts, drug interactions, treatment guidelines, and AI recommendations
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <AlertTriangle className="h-3.5 w-3.5" />
              Active Alerts
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-destructive" data-testid="kpi-alerts">4</div>
            <p className="text-xs font-medium text-muted-foreground">1 critical, 1 high</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Pill className="h-3.5 w-3.5" />
              Drug Checks
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-drug-checks">12</div>
            <p className="text-xs font-medium text-yellow-600 dark:text-yellow-400">3 interactions flagged</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Lightbulb className="h-3.5 w-3.5" />
              AI Suggestions
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-purple-600 dark:text-purple-400" data-testid="kpi-suggestions">8</div>
            <p className="text-xs font-medium text-muted-foreground">Evidence-based</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Shield className="h-3.5 w-3.5" />
              Compliance Score
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="kpi-compliance">98%</div>
            <p className="text-xs font-medium text-muted-foreground">Guidelines followed</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TriangleAlert className="h-4 w-4 text-destructive" />
              Clinical Alerts — Today's Patients
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {clinicalAlerts.map((alert, i) => {
              const borderColor =
                alert.severity === "critical"
                  ? "border-destructive"
                  : alert.severity === "high"
                    ? "border-yellow-500"
                    : alert.severity === "moderate"
                      ? "border-orange-500"
                      : "border-blue-500";
              const bgColor =
                alert.severity === "critical"
                  ? "bg-destructive/5"
                  : alert.severity === "high"
                    ? "bg-yellow-500/5"
                    : alert.severity === "moderate"
                      ? "bg-orange-500/5"
                      : "bg-blue-500/5";
              return (
                <div key={i} className={`rounded-md border-l-4 ${borderColor} ${bgColor} p-3`} data-testid={`alert-${i}`}>
                  <div className="flex items-center justify-between mb-1 flex-wrap gap-2">
                    <span className="text-xs font-bold">{alert.patient}</span>
                    <Badge
                      variant={alert.severity === "critical" ? "destructive" : "outline"}
                      className="text-[10px]"
                    >
                      {alert.severity}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground mb-1">{alert.alert}</p>
                  <p className="text-xs text-emerald-600 dark:text-emerald-400">
                    <Bot className="inline mr-1 h-3 w-3" />
                    {alert.action}
                  </p>
                </div>
              );
            })}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Brain className="h-4 w-4 text-purple-600 dark:text-purple-400" />
              AI Treatment Guidelines
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {treatmentGuidelines.map((guide, i) => (
              <div key={i} className="border-b pb-3 last:border-0 last:pb-0" data-testid={`guideline-${i}`}>
                <div className="text-xs font-bold mb-1">{guide.condition}</div>
                <p className="text-xs text-muted-foreground mb-1.5">{guide.recommendation}</p>
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <span className="text-[10px] text-muted-foreground">{guide.evidence}</span>
                  <div className="flex items-center gap-2">
                    <Progress value={guide.confidence} className="h-1.5 w-16" />
                    <span className="text-[10px] font-bold font-mono text-emerald-600 dark:text-emerald-400">
                      {guide.confidence}%
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Pill className="h-4 w-4" />
            Drug Interaction Monitor
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            {drugInteractions.map((di, i) => (
              <div
                key={i}
                className={`rounded-md p-3 ${
                  di.severity === "Major" ? "border-l-4 border-destructive bg-destructive/5" : "border-l-4 border-yellow-500 bg-yellow-500/5"
                }`}
                data-testid={`drug-interaction-${i}`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <Badge variant={di.severity === "Major" ? "destructive" : "outline"} className="text-[10px]">
                    {di.severity}
                  </Badge>
                </div>
                <div className="text-xs font-bold mb-0.5">
                  {di.drug1} + {di.drug2}
                </div>
                <p className="text-xs text-muted-foreground">{di.effect}</p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
