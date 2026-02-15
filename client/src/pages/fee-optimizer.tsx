import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DollarSign,
  BarChart3,
  TrendingUp,
  RefreshCcw,
  ArrowUp,
  CheckCircle,
} from "lucide-react";

const feeData = [
  { code: "D0120", desc: "Periodic Eval", yourFee: "$52", ucr: "$65", delta: "$48", cigna: "$45", action: "Raise 20%", actionColor: "outline" as const },
  { code: "D1110", desc: "Adult Prophy", yourFee: "$110", ucr: "$142", delta: "$95", cigna: "$88", action: "Raise 23%", actionColor: "outline" as const },
  { code: "D2391", desc: "Composite 1-surf", yourFee: "$195", ucr: "$228", delta: "$165", cigna: "$158", action: "Raise 14%", actionColor: "outline" as const },
  { code: "D2740", desc: "Crown Porcelain", yourFee: "$1,280", ucr: "$1,420", delta: "$980", cigna: "$920", action: "Good", actionColor: "default" as const },
  { code: "D4341", desc: "SRP 4+ teeth", yourFee: "$245", ucr: "$290", delta: "$205", cigna: "$195", action: "Raise 16%", actionColor: "outline" as const },
  { code: "D6010", desc: "Implant Body", yourFee: "$2,200", ucr: "$2,480", delta: "$1,650", cigna: "$1,580", action: "Good", actionColor: "default" as const },
];

export default function FeeOptimizerPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">
          AI Fee Schedule Optimizer
        </h1>
        <p className="text-sm text-muted-foreground">
          UCR analysis, PPO fee negotiation, procedure profitability
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <DollarSign className="h-3.5 w-3.5" />
              Revenue Opportunity
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="kpi-revenue-opp">$42,800</div>
            <p className="text-xs font-medium text-muted-foreground">From fee optimization</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <BarChart3 className="h-3.5 w-3.5" />
              Below UCR
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-yellow-600 dark:text-yellow-400" data-testid="kpi-below-ucr">34</div>
            <p className="text-xs font-medium text-muted-foreground">Of 180 active codes</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <TrendingUp className="h-3.5 w-3.5" />
              Fee vs UCR
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-fee-ucr">88%</div>
            <p className="text-xs font-medium text-muted-foreground">Target: 95%</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <RefreshCcw className="h-3.5 w-3.5" />
              PPO Contracts
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-purple-600 dark:text-purple-400" data-testid="kpi-ppo">8</div>
            <p className="text-xs font-medium text-muted-foreground">3 need renegotiation</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <DollarSign className="h-4 w-4" />
            Fee Schedule — Top Procedures
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs font-bold uppercase tracking-wider text-muted-foreground">
                  <th className="pb-3 pr-4">CDT</th>
                  <th className="pb-3 pr-4">Procedure</th>
                  <th className="pb-3 pr-4">Your Fee</th>
                  <th className="pb-3 pr-4">UCR 80th</th>
                  <th className="pb-3 pr-4">Delta</th>
                  <th className="pb-3 pr-4">Cigna</th>
                  <th className="pb-3">Action</th>
                </tr>
              </thead>
              <tbody>
                {feeData.map((f, i) => (
                  <tr key={i} className="border-b last:border-0" data-testid={`fee-row-${i}`}>
                    <td className="py-3 pr-4 font-mono font-bold text-purple-600 dark:text-purple-400">{f.code}</td>
                    <td className="py-3 pr-4 text-muted-foreground">{f.desc}</td>
                    <td className="py-3 pr-4 font-mono font-bold">{f.yourFee}</td>
                    <td className="py-3 pr-4 font-mono text-emerald-600 dark:text-emerald-400">{f.ucr}</td>
                    <td className="py-3 pr-4 font-mono text-yellow-600 dark:text-yellow-400">{f.delta}</td>
                    <td className="py-3 pr-4 font-mono text-destructive">{f.cigna}</td>
                    <td className="py-3">
                      <Badge variant={f.actionColor}>
                        {f.action === "Good" ? <CheckCircle className="mr-1 h-3 w-3" /> : <ArrowUp className="mr-1 h-3 w-3" />}
                        {f.action}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
