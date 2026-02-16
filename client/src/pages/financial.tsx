import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import {
  DollarSign,
  TrendingUp,
  Percent,
  CreditCard,
  FileSpreadsheet,
  PieChart,
} from "lucide-react";

const plLines = [
  { label: "Production (Gross)", value: "$206,400", pct: null, bold: false, separator: false },
  { label: "Adjustments", value: "($7,200)", pct: "3.5%", bold: false, separator: false },
  { label: "Net Production", value: "$199,200", pct: null, bold: true, separator: true },
  { label: "Collections", value: "$198,240", pct: "99.5%", bold: true, separator: true },
  { label: "Staff Costs", value: "($52,800)", pct: "26.6%", bold: false, separator: false },
  { label: "Facility", value: "($14,400)", pct: "7.3%", bold: false, separator: false },
  { label: "Supplies & Lab", value: "($25,600)", pct: "12.9%", bold: false, separator: false },
  { label: "Marketing", value: "($8,200)", pct: "4.1%", bold: false, separator: false },
  { label: "Admin & Other", value: "($12,800)", pct: "6.5%", bold: false, separator: false },
  { label: "Total Overhead", value: "($113,800)", pct: "57.3%", bold: true, separator: true },
  { label: "NET INCOME", value: "$84,440", pct: "42.6%", bold: true, separator: false },
];

const overheadItems = [
  { label: "Staff (salaries + benefits)", value: 26.6, target: 28, over: false },
  { label: "Supplies & Lab", value: 12.9, target: 14, over: false },
  { label: "Facility (rent + utilities)", value: 7.3, target: 8, over: false },
  { label: "Admin & Technology", value: 6.5, target: 4, over: true },
  { label: "Marketing", value: 4.1, target: 5, over: false },
];

export default function FinancialPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">
          Financial Command Center
        </h1>
        <p className="text-sm text-muted-foreground">
          P&L, overhead analysis, cash flow, accounts payable
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <DollarSign className="h-3.5 w-3.5" />
              YTD Revenue
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="kpi-ytd-revenue">$498,240</div>
            <p className="text-xs font-medium text-emerald-600 dark:text-emerald-400">Up 18% vs LY</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <TrendingUp className="h-3.5 w-3.5" />
              Net Income MTD
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="kpi-net-income">$86,400</div>
            <p className="text-xs font-medium text-muted-foreground">43.2% margin</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Percent className="h-3.5 w-3.5" />
              Overhead %
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-overhead">57.3%</div>
            <p className="text-xs font-medium text-emerald-600 dark:text-emerald-400">Target: &lt;59%</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <CreditCard className="h-3.5 w-3.5" />
              A/P Outstanding
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-yellow-600 dark:text-yellow-400" data-testid="kpi-ap-outstanding">$18,200</div>
            <p className="text-xs font-medium text-muted-foreground">3 vendors due</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileSpreadsheet className="h-4 w-4" />
              P&L Summary — February 2026
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-0">
              {plLines.map((line, i) => (
                <div
                  key={i}
                  className={`flex items-center justify-between gap-4 py-2 ${line.separator ? "border-b" : ""} ${line.bold ? "font-bold" : ""}`}
                  data-testid={`pl-line-${i}`}
                >
                  <span className={`text-sm ${line.bold ? "" : "text-muted-foreground"}`} data-testid={`pl-label-${i}`}>{line.label}</span>
                  <div className="flex items-center gap-3">
                    {line.pct && (
                      <span className="text-xs text-muted-foreground" data-testid={`pl-pct-${i}`}>{line.pct}</span>
                    )}
                    <span className={`font-mono text-sm ${line.bold ? "text-foreground" : ""}`} data-testid={`pl-value-${i}`}>{line.value}</span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <PieChart className="h-4 w-4" />
              Overhead Breakdown
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-5">
              {overheadItems.map((item, i) => (
                <div key={i} data-testid={`overhead-item-${i}`}>
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <span className="text-sm font-medium" data-testid={`overhead-label-${i}`}>{item.label}</span>
                    <span className={`text-sm font-mono font-bold ${item.over ? "text-destructive" : ""}`} data-testid={`overhead-value-${i}`}>
                      {item.value}% / {item.target}% target
                    </span>
                  </div>
                  <Progress
                    value={(item.value / item.target) * 100 > 100 ? 100 : (item.value / item.target) * 100}
                    className={`h-2 ${item.over ? "[&>div]:bg-destructive" : ""}`}
                  />
                  {item.over && (
                    <p className="text-xs text-destructive mt-1 font-medium" data-testid={`overhead-status-${i}`}>Over budget</p>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
