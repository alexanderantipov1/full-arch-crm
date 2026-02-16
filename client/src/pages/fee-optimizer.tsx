import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DollarSign,
  BarChart3,
  TrendingUp,
  TrendingDown,
  Target,
  ArrowUpRight,
  Lightbulb,
  Building2,
  CheckCircle,
  AlertTriangle,
  MinusCircle,
} from "lucide-react";

const feeAnalysisData = [
  { code: "D0120", desc: "Periodic Oral Eval", current: 65, p50: 72, p75: 85, p90: 98, status: "Below" as const },
  { code: "D0274", desc: "Bitewings - Four Films", current: 35, p50: 42, p75: 48, p90: 55, status: "Below" as const },
  { code: "D1110", desc: "Adult Prophylaxis", current: 110, p50: 125, p75: 140, p90: 155, status: "Below" as const },
  { code: "D2740", desc: "Crown - Porcelain/Ceramic", current: 1200, p50: 1280, p75: 1400, p90: 1520, status: "Below" as const },
  { code: "D6010", desc: "Endosteal Implant Body", current: 2200, p50: 2350, p75: 2500, p90: 2650, status: "At Market" as const },
  { code: "D7210", desc: "Surgical Extraction", current: 285, p50: 310, p75: 340, p90: 375, status: "At Market" as const },
];

const recommendations = [
  { code: "D0120", title: "Raise D0120 by $20 to match 75th percentile", projected: "$8,400/yr", desc: "Periodic oral evaluation is significantly below market. A $20 increase aligns with the 75th percentile without impacting patient volume.", priority: "High" as const },
  { code: "D0274", title: "Raise D0274 by $13 to match 75th percentile", projected: "$5,200/yr", desc: "Bitewing radiographs are priced well below average. This adjustment captures lost revenue on a high-volume procedure.", priority: "High" as const },
  { code: "D1110", title: "Raise D1110 by $30 to match 75th percentile", projected: "$12,600/yr", desc: "Adult prophylaxis is your highest-volume procedure. Even a modest increase yields significant annual revenue gains.", priority: "High" as const },
  { code: "D2740", title: "Raise D2740 by $200 to approach 75th percentile", projected: "$6,800/yr", desc: "Crown fees are below the 50th percentile. A phased increase over 6 months minimizes patient friction.", priority: "Medium" as const },
  { code: "D6010", title: "Consider raising D6010 by $150", projected: "$3,000/yr", desc: "Implant body pricing is near market but could be optimized to match regional demand. Monitor competitor adjustments.", priority: "Low" as const },
];

const payerComparison = [
  { code: "D0120", desc: "Periodic Eval", delta: 58, metlife: 52, cigna: 48, bcbs: 62, aetna: 55 },
  { code: "D0274", desc: "Bitewings x4", delta: 32, metlife: 30, cigna: 28, bcbs: 35, aetna: 31 },
  { code: "D1110", desc: "Adult Prophy", delta: 95, metlife: 88, cigna: 82, bcbs: 98, aetna: 90 },
  { code: "D2740", desc: "Crown Porcelain", delta: 980, metlife: 920, cigna: 880, bcbs: 1050, aetna: 940 },
  { code: "D6010", desc: "Implant Body", delta: 1650, metlife: 1580, cigna: 1520, bcbs: 1720, aetna: 1600 },
  { code: "D7210", desc: "Surgical Extract", delta: 265, metlife: 248, cigna: 235, bcbs: 280, aetna: 255 },
];

function StatusBadge({ status }: { status: "Below" | "At Market" | "Above" }) {
  if (status === "Below") {
    return (
      <Badge variant="destructive" data-testid={`badge-status-below`}>
        <TrendingDown className="mr-1 h-3 w-3" />
        Below
      </Badge>
    );
  }
  if (status === "At Market") {
    return (
      <Badge variant="secondary" data-testid={`badge-status-at-market`}>
        <MinusCircle className="mr-1 h-3 w-3" />
        At Market
      </Badge>
    );
  }
  return (
    <Badge variant="default" data-testid={`badge-status-above`}>
      <CheckCircle className="mr-1 h-3 w-3" />
      Above
    </Badge>
  );
}

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
              Revenue Impact
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="kpi-revenue-impact">$34K/yr</div>
            <p className="text-xs font-medium text-muted-foreground">Potential from optimization</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <BarChart3 className="h-3.5 w-3.5" />
              Fees Analyzed
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-fees-analyzed">248</div>
            <p className="text-xs font-medium text-muted-foreground">Active CDT codes</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <TrendingDown className="h-3.5 w-3.5" />
              Below Market
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-yellow-600 dark:text-yellow-400" data-testid="kpi-below-market">23</div>
            <p className="text-xs font-medium text-muted-foreground">Codes need adjustment</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Target className="h-3.5 w-3.5" />
              Optimization Score
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-purple-600 dark:text-purple-400" data-testid="kpi-optimization-score">87%</div>
            <Progress value={87} className="mt-2 h-1.5" />
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="overview" data-testid="tabs-fee-optimizer">
        <TabsList data-testid="tabslist-fee-optimizer">
          <TabsTrigger value="overview" data-testid="tab-overview">Overview</TabsTrigger>
          <TabsTrigger value="fee-analysis" data-testid="tab-fee-analysis">Fee Analysis</TabsTrigger>
          <TabsTrigger value="recommendations" data-testid="tab-recommendations">Recommendations</TabsTrigger>
          <TabsTrigger value="payer-comparison" data-testid="tab-payer-comparison">Payer Comparison</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4 mt-4">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BarChart3 className="h-4 w-4" />
                  Fee Distribution Summary
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div data-testid="overview-below-market">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm">Below Market</span>
                    <span className="text-sm font-bold font-mono text-destructive">23 codes</span>
                  </div>
                  <Progress value={9} className="h-2" />
                </div>
                <div data-testid="overview-at-market">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm">At Market</span>
                    <span className="text-sm font-bold font-mono text-yellow-600 dark:text-yellow-400">189 codes</span>
                  </div>
                  <Progress value={76} className="h-2" />
                </div>
                <div data-testid="overview-above-market">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm">Above Market</span>
                    <span className="text-sm font-bold font-mono text-emerald-600 dark:text-emerald-400">36 codes</span>
                  </div>
                  <Progress value={15} className="h-2" />
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <TrendingUp className="h-4 w-4" />
                  Revenue Opportunity by Category
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div data-testid="overview-cat-preventive">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm">Preventive</span>
                    <span className="text-sm font-bold font-mono">$12,400/yr</span>
                  </div>
                  <Progress value={36} className="h-2" />
                </div>
                <div data-testid="overview-cat-restorative">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm">Restorative</span>
                    <span className="text-sm font-bold font-mono">$9,800/yr</span>
                  </div>
                  <Progress value={29} className="h-2" />
                </div>
                <div data-testid="overview-cat-surgical">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm">Surgical</span>
                    <span className="text-sm font-bold font-mono">$6,200/yr</span>
                  </div>
                  <Progress value={18} className="h-2" />
                </div>
                <div data-testid="overview-cat-implants">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm">Implants</span>
                    <span className="text-sm font-bold font-mono">$5,600/yr</span>
                  </div>
                  <Progress value={17} className="h-2" />
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="fee-analysis" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <DollarSign className="h-4 w-4" />
                Fee Schedule Analysis — Market Percentiles
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Procedure</TableHead>
                    <TableHead className="text-right">Current Fee</TableHead>
                    <TableHead className="text-right">50th %ile</TableHead>
                    <TableHead className="text-right">75th %ile</TableHead>
                    <TableHead className="text-right">90th %ile</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {feeAnalysisData.map((f) => (
                    <TableRow key={f.code} data-testid={`fee-row-${f.code}`}>
                      <TableCell>
                        <div className="font-bold">{f.code}</div>
                        <div className="text-xs text-muted-foreground">{f.desc}</div>
                      </TableCell>
                      <TableCell className="text-right font-mono font-bold">${f.current.toLocaleString()}</TableCell>
                      <TableCell className="text-right font-mono text-muted-foreground">${f.p50.toLocaleString()}</TableCell>
                      <TableCell className="text-right font-mono text-emerald-600 dark:text-emerald-400">${f.p75.toLocaleString()}</TableCell>
                      <TableCell className="text-right font-mono text-purple-600 dark:text-purple-400">${f.p90.toLocaleString()}</TableCell>
                      <TableCell>
                        <StatusBadge status={f.status} />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="recommendations" className="space-y-4 mt-4">
          {recommendations.map((rec) => (
            <Card key={rec.code} data-testid={`rec-card-${rec.code}`}>
              <CardContent className="pt-6">
                <div className="flex items-start justify-between flex-wrap gap-2 mb-3">
                  <div className="flex items-center gap-2">
                    <Lightbulb className="h-4 w-4 text-yellow-600 dark:text-yellow-400" />
                    <span className="font-bold text-sm">{rec.title}</span>
                  </div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <Badge variant={rec.priority === "High" ? "destructive" : rec.priority === "Medium" ? "secondary" : "outline"} data-testid={`rec-priority-${rec.code}`}>
                      {rec.priority} Priority
                    </Badge>
                    <Badge variant="default" data-testid={`rec-projected-${rec.code}`}>
                      <ArrowUpRight className="mr-1 h-3 w-3" />
                      {rec.projected}
                    </Badge>
                  </div>
                </div>
                <p className="text-sm text-muted-foreground">{rec.desc}</p>
                <div className="mt-3 flex gap-2 flex-wrap">
                  <Button size="sm" data-testid={`btn-apply-${rec.code}`}>
                    Apply Recommendation
                  </Button>
                  <Button variant="outline" size="sm" data-testid={`btn-dismiss-${rec.code}`}>
                    Dismiss
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </TabsContent>

        <TabsContent value="payer-comparison" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Building2 className="h-4 w-4" />
                Payer Reimbursement Comparison
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Procedure</TableHead>
                    <TableHead className="text-right">Delta Dental</TableHead>
                    <TableHead className="text-right">MetLife</TableHead>
                    <TableHead className="text-right">Cigna</TableHead>
                    <TableHead className="text-right">BCBS</TableHead>
                    <TableHead className="text-right">Aetna</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {payerComparison.map((pc) => (
                    <TableRow key={pc.code} data-testid={`payer-comp-${pc.code}`}>
                      <TableCell>
                        <div className="font-bold">{pc.code}</div>
                        <div className="text-xs text-muted-foreground">{pc.desc}</div>
                      </TableCell>
                      <TableCell className="text-right font-mono">${pc.delta.toLocaleString()}</TableCell>
                      <TableCell className="text-right font-mono">${pc.metlife.toLocaleString()}</TableCell>
                      <TableCell className="text-right font-mono">${pc.cigna.toLocaleString()}</TableCell>
                      <TableCell className="text-right font-mono text-emerald-600 dark:text-emerald-400 font-bold">${pc.bcbs.toLocaleString()}</TableCell>
                      <TableCell className="text-right font-mono">${pc.aetna.toLocaleString()}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              <div className="mt-4 flex items-center gap-2 text-xs text-muted-foreground">
                <AlertTriangle className="h-3.5 w-3.5" />
                <span>Green highlights indicate highest reimbursement among compared payers</span>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
