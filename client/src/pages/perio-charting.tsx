import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  BarChart3,
  Droplets,
  TrendingDown,
  Activity,
  User,
  Calendar,
  AlertTriangle,
  CheckCircle,
  Bot,
  Printer,
  FileText,
  ChevronDown,
} from "lucide-react";

const probingData: Record<number, number[]> = {
  3: [3, 2, 3, 4, 5, 3],
  8: [2, 2, 2, 2, 3, 2],
  14: [5, 6, 4, 4, 5, 6],
  19: [4, 3, 3, 3, 4, 4],
  30: [6, 7, 5, 5, 6, 7],
};

const upperTeeth = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16];
const lowerTeeth = [32, 31, 30, 29, 28, 27, 26, 25, 24, 23, 22, 21, 20, 19, 18, 17];

function ProbingValue({ value }: { value: number }) {
  const colorClass =
    value >= 6
      ? "bg-destructive/15 text-destructive font-bold"
      : value >= 4
        ? "bg-yellow-500/15 text-yellow-600 dark:text-yellow-400 font-bold"
        : "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400";
  return (
    <div
      className={`flex h-5 w-4 items-center justify-center rounded text-xs font-mono ${colorClass}`}
      data-testid={`probing-value-${value}`}
    >
      {value}
    </div>
  );
}

export default function PerioChartingPage() {
  const [selectedPatient] = useState("Margaret Sullivan");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">
          Periodontal Charting
        </h1>
        <p className="text-sm text-muted-foreground">
          6-point probing, BOP, recession, furcation, mobility — full perio record
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <BarChart3 className="h-3.5 w-3.5" />
              Avg Probing
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-avg-probing">3.2mm</div>
            <p className="text-xs font-medium text-emerald-600 dark:text-emerald-400">Previous: 3.8mm</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Droplets className="h-3.5 w-3.5" />
              BOP Sites
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-destructive" data-testid="kpi-bop">18%</div>
            <p className="text-xs font-medium text-muted-foreground">Target: &lt;10%</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <TrendingDown className="h-3.5 w-3.5" />
              Sites &gt;4mm
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-sites-4mm">24</div>
            <p className="text-xs font-medium text-yellow-600 dark:text-yellow-400">Previous: 31</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Activity className="h-3.5 w-3.5" />
              Perio Dx
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-perio-dx">Stage III</div>
            <p className="text-xs font-medium text-purple-600 dark:text-purple-400">Grade B — generalized</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-4">
          <CardTitle className="flex items-center gap-2">
            <User className="h-4 w-4" />
            Probing Chart — {selectedPatient}
          </CardTitle>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="font-mono text-xs">
              <Calendar className="mr-1 h-3 w-3" />
              2026-02-11
            </Badge>
            <Button size="sm" data-testid="button-print-chart">
              <Printer className="mr-1 h-3.5 w-3.5" />
              Print
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {[
            { label: "Facial — Upper", teeth: upperTeeth, side: "F" as const },
            { label: "Lingual — Upper", teeth: upperTeeth, side: "L" as const },
            { label: "Facial — Lower", teeth: lowerTeeth, side: "F" as const },
            { label: "Lingual — Lower", teeth: lowerTeeth, side: "L" as const },
          ].map((row) => (
            <div key={row.label} className="mb-4">
              <div className="mb-1.5 text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
                {row.label}
              </div>
              <div className="flex gap-0.5">
                {row.teeth.map((t) => {
                  const p = probingData[t] || [2, 2, 2, 2, 2, 2];
                  const vals = row.side === "F" ? p.slice(0, 3) : p.slice(3, 6);
                  return (
                    <div key={t} className="flex flex-1 flex-col items-center" data-testid={`tooth-${t}`}>
                      <div className="flex gap-px mb-0.5">
                        {vals.map((v, vi) => (
                          <ProbingValue key={vi} value={v} />
                        ))}
                      </div>
                      <div className="text-[9px] font-bold text-muted-foreground">{t}</div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}

          <div className="flex gap-6 border-t pt-4 mt-2">
            {[
              { range: "1-3mm", color: "bg-emerald-500", label: "Healthy" },
              { range: "4-5mm", color: "bg-yellow-500", label: "Moderate" },
              { range: "6mm+", color: "bg-destructive", label: "Severe" },
            ].map((legend) => (
              <div key={legend.range} className="flex items-center gap-2">
                <div className={`h-2.5 w-2.5 rounded-sm ${legend.color}`} />
                <span className="text-xs text-muted-foreground">
                  {legend.range} — {legend.label}
                </span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card className="border-purple-500/20 bg-purple-500/5 dark:bg-purple-500/5">
        <CardContent className="pt-6">
          <div className="flex items-center gap-2 mb-2">
            <Bot className="h-4 w-4 text-purple-600 dark:text-purple-400" />
            <span className="text-sm font-bold text-purple-600 dark:text-purple-400">AI Perio Assessment</span>
          </div>
          <p className="text-sm text-muted-foreground leading-relaxed" data-testid="text-ai-assessment">
            Diagnosis: <strong className="text-foreground">Periodontitis Stage III, Grade B, Generalized</strong>. 24
            sites ≥4mm (improved from 31). BOP at 18%. Recommend: continued SRP, 3-month perio maintenance, consider
            Arestin for sites ≥5mm. Insurance narrative auto-generated for D4341/D4342.
          </p>
          <div className="mt-3 flex gap-2">
            <Button size="sm" variant="outline" data-testid="button-generate-narrative">
              <FileText className="mr-1 h-3.5 w-3.5" />
              Generate Narrative
            </Button>
            <Button size="sm" variant="outline" data-testid="button-compare-previous">
              <TrendingDown className="mr-1 h-3.5 w-3.5" />
              Compare Previous
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
