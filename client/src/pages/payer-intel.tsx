import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Building2,
  BarChart3,
  Clock,
  DollarSign,
  TrendingUp,
} from "lucide-react";

const payers = [
  { name: "Delta Dental Premier", approval: "92%", days: "12d", denial: "4%", reimb: "94%", crossCode: "Medium", score: "A+", scoreColor: "text-emerald-600 dark:text-emerald-400" },
  { name: "Cigna PPO", approval: "86%", days: "18d", denial: "8%", reimb: "88%", crossCode: "High", score: "A", scoreColor: "text-emerald-600 dark:text-emerald-400" },
  { name: "MetLife PPO", approval: "81%", days: "22d", denial: "12%", reimb: "82%", crossCode: "High", score: "B+", scoreColor: "text-yellow-600 dark:text-yellow-400" },
  { name: "Aetna DMO", approval: "78%", days: "16d", denial: "9%", reimb: "75%", crossCode: "Low", score: "B", scoreColor: "text-yellow-600 dark:text-yellow-400" },
  { name: "UHC PPO", approval: "74%", days: "28d", denial: "15%", reimb: "71%", crossCode: "High", score: "C+", scoreColor: "text-destructive" },
  { name: "BCBS FEP", approval: "88%", days: "14d", denial: "6%", reimb: "90%", crossCode: "Medium", score: "A", scoreColor: "text-emerald-600 dark:text-emerald-400" },
];

export default function PayerIntelPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">
          Payer Intelligence Dashboard
        </h1>
        <p className="text-sm text-muted-foreground">
          AI learns from every claim — payer profiles, playbooks, revenue opportunities
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Building2 className="h-3.5 w-3.5" />
              Payer Profiles
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-profiles">340+</div>
            <p className="text-xs font-medium text-muted-foreground">AI-analyzed</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <BarChart3 className="h-3.5 w-3.5" />
              Claims Analyzed
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-purple-600 dark:text-purple-400" data-testid="kpi-claims">12,400+</div>
            <p className="text-xs font-medium text-muted-foreground">Historical data</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Clock className="h-3.5 w-3.5" />
              Avg Days to Pay
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="kpi-days">14.2</div>
            <p className="text-xs font-medium text-muted-foreground">Across all payers</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <DollarSign className="h-3.5 w-3.5" />
              Opportunities
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="kpi-opportunities">$18,400</div>
            <p className="text-xs font-medium text-muted-foreground">Revenue detected</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Building2 className="h-4 w-4" />
            Top Payer Scorecard
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs font-bold uppercase tracking-wider text-muted-foreground">
                  <th className="pb-3 pr-4">Payer</th>
                  <th className="pb-3 pr-4">Approval %</th>
                  <th className="pb-3 pr-4">Avg Days</th>
                  <th className="pb-3 pr-4">Denial %</th>
                  <th className="pb-3 pr-4">Reimb %</th>
                  <th className="pb-3 pr-4">X-Code Opp</th>
                  <th className="pb-3">Score</th>
                </tr>
              </thead>
              <tbody>
                {payers.map((p, i) => (
                  <tr key={i} className="border-b last:border-0" data-testid={`payer-row-${i}`}>
                    <td className="py-3 pr-4 font-bold">{p.name}</td>
                    <td className="py-3 pr-4 text-emerald-600 dark:text-emerald-400">{p.approval}</td>
                    <td className="py-3 pr-4 font-mono">{p.days}</td>
                    <td className="py-3 pr-4">
                      <span className={parseFloat(p.denial) > 10 ? "text-destructive font-bold" : "text-yellow-600 dark:text-yellow-400"}>
                        {p.denial}
                      </span>
                    </td>
                    <td className="py-3 pr-4 font-mono">{p.reimb}</td>
                    <td className="py-3 pr-4">
                      <span className={p.crossCode === "High" ? "text-purple-600 dark:text-purple-400 font-bold" : "text-muted-foreground"}>
                        {p.crossCode}
                      </span>
                    </td>
                    <td className="py-3">
                      <span className={`text-lg font-black ${p.scoreColor}`}>{p.score}</span>
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
