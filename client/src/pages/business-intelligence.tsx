import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  DollarSign,
  TrendingUp,
  Award,
  Bot,
  Brain,
  BarChart3,
  Lightbulb,
  Sparkles,
} from "lucide-react";

const aiValueItems = [
  { label: "AI Diagnostics", value: "$8,400" },
  { label: "AI Phone Agent", value: "$18,400" },
  { label: "Claims Engine", value: "$6,200" },
  { label: "Cross-Coding", value: "$28,400" },
  { label: "Denial Appeals", value: "$34,200" },
  { label: "Case Acceptance", value: "$22,800" },
  { label: "Smart Scheduling", value: "$12,400" },
  { label: "Voice Pipeline", value: "$4,800" },
  { label: "Fee Optimization", value: "$3,600" },
  { label: "Compliance", value: "$2,400" },
];

const benchmarkData = [
  { metric: "Production/Operatory", yours: "$24,800", national: "$18,200", percentile: "94th" },
  { metric: "Collection Rate", yours: "99.5%", national: "96.2%", percentile: "98th" },
  { metric: "Overhead %", yours: "57.3%", national: "62.8%", percentile: "88th" },
  { metric: "New Patients/Mo", yours: "38", national: "28", percentile: "86th" },
  { metric: "Case Acceptance", yours: "74%", national: "58%", percentile: "92nd" },
  { metric: "Days in A/R", yours: "18.4", national: "32", percentile: "95th" },
  { metric: "Hygiene Reappt", yours: "88%", national: "82%", percentile: "78th", flag: true },
  { metric: "Patient Retention", yours: "91%", national: "85%", percentile: "84th" },
];

const strategicRecommendations = [
  "Hygiene reappt at 88% \u2014 implement AI phone recall for non-responders",
  "Cross-coding at 34/mo \u2014 potential 60+ with TMJ, sleep, trauma detection",
  "Rocklin 68.4% overhead \u2014 share hygienist with Auburn until breakeven",
  "SEO ROI at 12.1x \u2014 increase AI blog content to 2x/week",
];

export default function BusinessIntelligencePage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">
          Unified Business Intelligence
        </h1>
        <p className="text-sm text-muted-foreground">
          Revenue analytics, AI value attribution, national benchmarks, and strategic recommendations
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <DollarSign className="h-3.5 w-3.5" />
              Annualized Revenue
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="kpi-annualized-revenue">$2.38M</div>
            <p className="text-xs font-medium text-muted-foreground">Run rate</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <TrendingUp className="h-3.5 w-3.5" />
              Growth Rate
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="kpi-growth-rate">+18%</div>
            <p className="text-xs font-medium text-muted-foreground">YoY</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Award className="h-3.5 w-3.5" />
              Percentile
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-blue-600 dark:text-blue-400" data-testid="kpi-percentile">92nd</div>
            <p className="text-xs font-medium text-muted-foreground">vs national</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Sparkles className="h-3.5 w-3.5" />
              AI Impact
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-purple-600 dark:text-purple-400" data-testid="kpi-ai-impact">$384K</div>
            <p className="text-xs font-medium text-muted-foreground">Annual value from AI</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Brain className="h-4 w-4 text-purple-600 dark:text-purple-400" />
              AI Value Attribution &mdash; Monthly
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {aiValueItems.map((item, i) => (
                <div key={i} className="flex items-center justify-between py-1.5 border-b last:border-0" data-testid={`ai-value-${i}`}>
                  <span className="text-xs font-medium" data-testid={`ai-value-label-${i}`}>{item.label}</span>
                  <span className="text-xs font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid={`ai-value-amount-${i}`}>{item.value}</span>
                </div>
              ))}
            </div>
            <div className="mt-4 pt-3 border-t-2">
              <div className="flex items-center justify-between">
                <span className="text-sm font-bold">Total Monthly AI Value</span>
                <span className="text-sm font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="total-ai-value">$141,600</span>
              </div>
              <p className="text-xs text-muted-foreground mt-1" data-testid="text-ai-annual">
                = $1.7M/year from AI &mdash; at $497/mo
              </p>
            </div>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="h-4 w-4" />
                Practice vs Benchmarks
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-xs font-bold uppercase tracking-wider text-muted-foreground">
                      <th className="pb-3 pr-4">Metric</th>
                      <th className="pb-3 pr-4">Yours</th>
                      <th className="pb-3 pr-4">National</th>
                      <th className="pb-3">Percentile</th>
                    </tr>
                  </thead>
                  <tbody>
                    {benchmarkData.map((row, i) => (
                      <tr key={i} className="border-b last:border-0" data-testid={`benchmark-row-${i}`}>
                        <td className="py-2.5 pr-4 text-xs font-medium" data-testid={`benchmark-metric-${i}`}>{row.metric}</td>
                        <td className="py-2.5 pr-4 text-xs font-bold font-mono" data-testid={`benchmark-yours-${i}`}>{row.yours}</td>
                        <td className="py-2.5 pr-4 text-xs font-mono text-muted-foreground" data-testid={`benchmark-national-${i}`}>{row.national}</td>
                        <td className="py-2.5">
                          <Badge
                            variant="outline"
                            className={`text-[10px] font-mono ${row.flag ? "text-yellow-600 dark:text-yellow-400 border-yellow-500" : ""}`}
                            data-testid={`badge-percentile-${i}`}
                          >
                            {row.percentile}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          <Card className="border-purple-500/20 bg-purple-500/5 dark:bg-purple-500/5">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Lightbulb className="h-4 w-4 text-purple-600 dark:text-purple-400" />
                <span className="text-purple-600 dark:text-purple-400">AI Strategic Recommendations</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {strategicRecommendations.map((rec, i) => (
                <div key={i} className="flex gap-2" data-testid={`recommendation-${i}`}>
                  <Bot className="h-3.5 w-3.5 mt-0.5 shrink-0 text-purple-600 dark:text-purple-400" />
                  <p className="text-xs text-muted-foreground leading-relaxed" data-testid={`recommendation-text-${i}`}>{rec}</p>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
