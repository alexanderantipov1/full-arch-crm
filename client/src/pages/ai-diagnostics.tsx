import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  Microscope,
  AlertTriangle,
  CheckCircle,
  DollarSign,
  BarChart3,
  Bot,
  Eye,
  Layers,
  Upload,
  FileText,
  ZoomIn,
  Share2,
} from "lucide-react";

const findings = [
  {
    side: "BWX — Right",
    items: [
      { tooth: "#3 Mesial", type: "Caries", confidence: 94, severity: "moderate", variant: "destructive" as const },
      { tooth: "#14 Mesial", type: "Bone Loss", confidence: 89, severity: "4.2mm", variant: "secondary" as const },
    ],
  },
  {
    side: "BWX — Left",
    items: [
      { tooth: "#19 Distal", type: "Caries", confidence: 87, severity: "early", variant: "outline" as const },
      { tooth: "#30 Mesial", type: "Bone Loss", confidence: 91, severity: "5.8mm", variant: "destructive" as const },
      { tooth: "#31 Periapical", type: "Radiolucency", confidence: 78, severity: "eval", variant: "outline" as const },
    ],
  },
];

const treatmentOpportunities = [
  { procedure: "Crown #3 (D2740)", fee: "$1,280", color: "text-emerald-600 dark:text-emerald-400" },
  { procedure: "Implant #14 (D6010)", fee: "$2,200", color: "text-emerald-600 dark:text-emerald-400" },
  { procedure: "SRP All Quads (D4341)", fee: "$820", color: "text-emerald-600 dark:text-emerald-400" },
  { procedure: "Filling #19 (D2391)", fee: "$195", color: "text-emerald-600 dark:text-emerald-400" },
  { procedure: "PA + Vitality #31 (D0220)", fee: "$35", color: "text-muted-foreground" },
];

export default function AIDiagnosticsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">
          AI Diagnostic Imaging Engine
        </h1>
        <p className="text-sm text-muted-foreground">
          Real-time radiograph analysis, caries & bone loss detection
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Microscope className="h-3.5 w-3.5" />
              Scans Analyzed
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-scans">42</div>
            <p className="text-xs font-medium text-muted-foreground">38 BWX, 4 CBCT</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <AlertTriangle className="h-3.5 w-3.5" />
              Pathologies Found
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-destructive" data-testid="kpi-pathologies">18</div>
            <p className="text-xs font-medium text-muted-foreground">12 caries, 4 bone, 2 other</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <BarChart3 className="h-3.5 w-3.5" />
              Detection Accuracy
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="kpi-accuracy">96.2%</div>
            <p className="text-xs font-medium text-muted-foreground">Validated vs provider dx</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <DollarSign className="h-3.5 w-3.5" />
              Revenue Found
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="kpi-revenue">$8,400</div>
            <p className="text-xs font-medium text-muted-foreground">AI-detected treatment</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
        <div className="lg:col-span-3 space-y-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between gap-4">
              <CardTitle>Margaret Sullivan — BWX R/L</CardTitle>
              <Badge variant="default" data-testid="badge-ai-analyzed">AI Analyzed</Badge>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2 mb-4">
                {findings.map((xr) => (
                  <Card key={xr.side} className="bg-muted/30">
                    <CardContent className="pt-4">
                      <div className="mb-3 text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
                        {xr.side}
                      </div>
                      <div className="relative mb-4 flex h-20 items-center justify-center rounded-md bg-muted/50 border">
                        <Microscope className="h-8 w-8 text-muted-foreground/20" />
                        <div className="absolute right-2 top-2 flex flex-col gap-1">
                          {xr.items.map((f, fi) => (
                            <Badge key={fi} variant={f.variant} className="text-[10px]">
                              <AlertTriangle className="mr-1 h-2.5 w-2.5" />
                              {f.tooth}
                            </Badge>
                          ))}
                        </div>
                      </div>
                      {xr.items.map((f, fi) => (
                        <div
                          key={fi}
                          className="mb-2 border-b pb-2 last:border-0 last:pb-0"
                          data-testid={`finding-${f.tooth.replace(/\s+/g, "-").replace("#", "")}`}
                        >
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs font-bold">
                              {f.type} — {f.tooth}
                            </span>
                            <Badge variant={f.variant} className="text-[10px]">{f.severity}</Badge>
                          </div>
                          <div className="flex items-center gap-2">
                            <Progress value={f.confidence} className="h-1" />
                            <span className="text-xs font-bold font-mono text-muted-foreground">{f.confidence}%</span>
                          </div>
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                ))}
              </div>
              <div className="flex flex-wrap gap-2">
                {["AI Overlay", "Bone Levels", "Caries Map", "Compare", "Enhance", "Annotate"].map((t) => (
                  <Button key={t} size="sm" variant="outline" className="text-xs" data-testid={`button-${t.toLowerCase().replace(/\s+/g, "-")}`}>
                    {t}
                  </Button>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="lg:col-span-2 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Bot className="h-4 w-4" />
                AI Diagnostic Summary
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="rounded-md border-l-4 border-destructive bg-destructive/5 p-3">
                <div className="text-xs font-bold text-destructive mb-1">3 Carious Lesions</div>
                <p className="text-xs text-muted-foreground">#3M (94%), #19D (87%), #14M (82%)</p>
              </div>
              <div className="rounded-md border-l-4 border-purple-500 bg-purple-500/5 p-3">
                <div className="text-xs font-bold text-purple-600 dark:text-purple-400 mb-1">Bone Loss Quantified</div>
                <p className="text-xs text-muted-foreground">#14M: 4.2mm (30%) / #30M: 5.8mm (45%). Stage III Perio.</p>
              </div>
              <div className="rounded-md border-l-4 border-yellow-500 bg-yellow-500/5 p-3">
                <div className="text-xs font-bold text-yellow-600 dark:text-yellow-400 mb-1">Periapical Finding</div>
                <p className="text-xs text-muted-foreground">#31: Radiolucency 3x4mm — vitality test + PA recommended</p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <DollarSign className="h-4 w-4" />
                AI Treatment Opportunity
              </CardTitle>
            </CardHeader>
            <CardContent>
              {treatmentOpportunities.map((tx, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between border-b py-2 last:border-0"
                  data-testid={`treatment-opp-${i}`}
                >
                  <span className="text-xs text-muted-foreground">{tx.procedure}</span>
                  <span className={`text-xs font-bold font-mono ${tx.color}`}>{tx.fee}</span>
                </div>
              ))}
              <div className="mt-3 flex items-center justify-between border-t pt-3">
                <span className="text-sm font-bold">Total Opportunity</span>
                <span className="text-sm font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="text-total-opportunity">
                  $4,530
                </span>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
