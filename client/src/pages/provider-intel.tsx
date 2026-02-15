import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Users,
  DollarSign,
  BarChart3,
  Target,
  User,
  TrendingUp,
} from "lucide-react";

const providers = [
  { name: "Dr. Chen", specialty: "Implantologist", production: "$98,400", perDay: "$8,200", patients: "142", caseAccept: "78%", avgTx: "$2,840", collections: "$96,200", score: "A+", scoreColor: "text-emerald-600 dark:text-emerald-400" },
  { name: "Dr. Park", specialty: "Orthodontist", production: "$62,800", perDay: "$7,850", patients: "98", caseAccept: "72%", avgTx: "$1,680", collections: "$61,400", score: "A", scoreColor: "text-emerald-600 dark:text-emerald-400" },
  { name: "Dr. Okafor", specialty: "Oral Surgeon", production: "$37,000", perDay: "$9,250", patients: "48", caseAccept: "68%", avgTx: "$3,420", collections: "$36,200", score: "A-", scoreColor: "text-emerald-600 dark:text-emerald-400" },
  { name: "Sarah M.", specialty: "Hygienist", production: "$18,400", perDay: "$920", patients: "164", caseAccept: "—", avgTx: "$112", collections: "$18,100", score: "A", scoreColor: "text-emerald-600 dark:text-emerald-400" },
  { name: "Jamie L.", specialty: "Hyg/Perio", production: "$16,800", perDay: "$840", patients: "148", caseAccept: "—", avgTx: "$114", collections: "$16,500", score: "B+", scoreColor: "text-yellow-600 dark:text-yellow-400" },
];

export default function ProviderIntelPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">
          Provider Performance Intelligence
        </h1>
        <p className="text-sm text-muted-foreground">
          Production, coding patterns, speed metrics, compensation modeling
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Users className="h-3.5 w-3.5" />
              Providers
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-providers">3</div>
            <p className="text-xs font-medium text-muted-foreground">+ 2 hygienists</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <DollarSign className="h-3.5 w-3.5" />
              Production MTD
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="kpi-production">$198,200</div>
            <p className="text-xs font-medium text-muted-foreground">All providers</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <BarChart3 className="h-3.5 w-3.5" />
              Avg Prod/Day
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="kpi-avg-prod">$8,260</div>
            <p className="text-xs font-medium text-muted-foreground">Across all providers</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Target className="h-3.5 w-3.5" />
              Avg Acceptance
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-cyan-600 dark:text-cyan-400" data-testid="kpi-acceptance">74%</div>
            <p className="text-xs font-medium text-emerald-600 dark:text-emerald-400">Up 6% with AI</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="h-4 w-4" />
            Provider Scorecard
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs font-bold uppercase tracking-wider text-muted-foreground">
                  <th className="pb-3 pr-4">Provider</th>
                  <th className="pb-3 pr-4">Production</th>
                  <th className="pb-3 pr-4">Prod/Day</th>
                  <th className="pb-3 pr-4">Patients</th>
                  <th className="pb-3 pr-4">Accept %</th>
                  <th className="pb-3 pr-4">Avg Tx</th>
                  <th className="pb-3 pr-4">Collections</th>
                  <th className="pb-3">Score</th>
                </tr>
              </thead>
              <tbody>
                {providers.map((p, i) => (
                  <tr key={i} className="border-b last:border-0" data-testid={`provider-row-${i}`}>
                    <td className="py-3 pr-4">
                      <div className="font-bold">{p.name}</div>
                      <div className="text-xs text-muted-foreground">{p.specialty}</div>
                    </td>
                    <td className="py-3 pr-4 font-mono font-bold">{p.production}</td>
                    <td className="py-3 pr-4 font-mono">{p.perDay}</td>
                    <td className="py-3 pr-4">{p.patients}</td>
                    <td className="py-3 pr-4">
                      <span className={`font-bold ${
                        p.caseAccept === "—" ? "text-muted-foreground" :
                        parseInt(p.caseAccept) >= 75 ? "text-emerald-600 dark:text-emerald-400" :
                        parseInt(p.caseAccept) >= 65 ? "text-yellow-600 dark:text-yellow-400" : "text-muted-foreground"
                      }`}>{p.caseAccept}</span>
                    </td>
                    <td className="py-3 pr-4 font-mono">{p.avgTx}</td>
                    <td className="py-3 pr-4 font-mono text-emerald-600 dark:text-emerald-400">{p.collections}</td>
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
