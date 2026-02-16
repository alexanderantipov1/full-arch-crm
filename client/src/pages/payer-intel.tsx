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
  Building2,
  BarChart3,
  Clock,
  DollarSign,
  TrendingUp,
  Users,
  FileText,
  AlertTriangle,
  CalendarClock,
  CheckCircle,
  XCircle,
  Zap,
} from "lucide-react";

const payerProfiles = [
  {
    name: "Delta Dental Premier",
    patients: 342,
    avgDays: 12,
    reimbRate: 94,
    denialRate: 4,
    topDenials: ["Missing pre-auth", "Frequency limitation", "Bundling error"],
  },
  {
    name: "Cigna PPO",
    patients: 218,
    avgDays: 14,
    reimbRate: 88,
    denialRate: 8,
    topDenials: ["Pre-existing condition", "Waiting period", "Non-covered service"],
  },
  {
    name: "MetLife PPO",
    patients: 195,
    avgDays: 22,
    reimbRate: 82,
    denialRate: 12,
    topDenials: ["Missing documentation", "Frequency limitation", "Downcoding"],
  },
  {
    name: "BCBS FEP",
    patients: 164,
    avgDays: 16,
    reimbRate: 90,
    denialRate: 6,
    topDenials: ["Missing X-rays", "Alternate benefit", "Bundling error"],
  },
  {
    name: "Aetna DMO",
    patients: 128,
    avgDays: 20,
    reimbRate: 75,
    denialRate: 9,
    topDenials: ["Non-covered service", "Missing referral", "Waiting period"],
  },
];

const contracts = [
  { payer: "Delta Dental Premier", effective: "01/01/2024", scheduleType: "UCR-Based", reimbPct: 94, renewal: "12/31/2025", status: "Active" as const },
  { payer: "Cigna PPO", effective: "03/15/2024", scheduleType: "PPO Fixed", reimbPct: 88, renewal: "03/14/2026", status: "Active" as const },
  { payer: "MetLife PPO", effective: "06/01/2023", scheduleType: "PPO Fixed", reimbPct: 82, renewal: "05/31/2025", status: "Renewal Due" as const },
  { payer: "BCBS FEP", effective: "09/01/2024", scheduleType: "UCR-Based", reimbPct: 90, renewal: "08/31/2026", status: "Active" as const },
  { payer: "Aetna DMO", effective: "01/01/2023", scheduleType: "DHMO Capitated", reimbPct: 75, renewal: "12/31/2025", status: "Negotiating" as const },
  { payer: "UHC PPO", effective: "04/01/2024", scheduleType: "PPO Fixed", reimbPct: 71, renewal: "03/31/2025", status: "Renewal Due" as const },
  { payer: "Guardian", effective: "07/01/2024", scheduleType: "PPO Fixed", reimbPct: 80, renewal: "06/30/2026", status: "Active" as const },
];

const reimbursementByCategory = [
  {
    payer: "Delta Dental",
    preventive: 98,
    basic: 92,
    major: 85,
    implant: 72,
    ortho: 65,
  },
  {
    payer: "Cigna",
    preventive: 95,
    basic: 88,
    major: 78,
    implant: 60,
    ortho: 55,
  },
  {
    payer: "MetLife",
    preventive: 90,
    basic: 82,
    major: 72,
    implant: 55,
    ortho: 50,
  },
  {
    payer: "BCBS",
    preventive: 96,
    basic: 90,
    major: 82,
    implant: 68,
    ortho: 60,
  },
  {
    payer: "Aetna",
    preventive: 88,
    basic: 78,
    major: 68,
    implant: 50,
    ortho: 45,
  },
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
              Active Payers
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-active-payers">24</div>
            <p className="text-xs font-medium text-muted-foreground">In-network contracts</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <DollarSign className="h-3.5 w-3.5" />
              Avg Reimbursement
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="kpi-avg-reimbursement">78%</div>
            <Progress value={78} className="mt-2 h-1.5" />
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Zap className="h-3.5 w-3.5" />
              Fastest Payer
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-purple-600 dark:text-purple-400" data-testid="kpi-fastest-payer">Cigna</div>
            <p className="text-xs font-medium text-muted-foreground">14 days avg turnaround</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <CalendarClock className="h-3.5 w-3.5" />
              Contract Renewals
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-yellow-600 dark:text-yellow-400" data-testid="kpi-renewals">3</div>
            <p className="text-xs font-medium text-muted-foreground">Due within 90 days</p>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="overview" data-testid="tabs-payer-intel">
        <TabsList data-testid="tabslist-payer-intel">
          <TabsTrigger value="overview" data-testid="tab-overview">Overview</TabsTrigger>
          <TabsTrigger value="payer-profiles" data-testid="tab-payer-profiles">Payer Profiles</TabsTrigger>
          <TabsTrigger value="contract-analysis" data-testid="tab-contract-analysis">Contract Analysis</TabsTrigger>
          <TabsTrigger value="reimbursement-trends" data-testid="tab-reimbursement-trends">Reimbursement Trends</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4 mt-4">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Building2 className="h-4 w-4" />
                  Top Payer Scorecard
                </CardTitle>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Payer</TableHead>
                      <TableHead className="text-right">Patients</TableHead>
                      <TableHead className="text-right">Reimb %</TableHead>
                      <TableHead className="text-right">Avg Days</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {payerProfiles.map((p) => (
                      <TableRow key={p.name} data-testid={`overview-payer-${p.name.replace(/\s+/g, '-').toLowerCase()}`}>
                        <TableCell className="font-bold">{p.name}</TableCell>
                        <TableCell className="text-right font-mono">{p.patients}</TableCell>
                        <TableCell className="text-right font-mono text-emerald-600 dark:text-emerald-400">{p.reimbRate}%</TableCell>
                        <TableCell className="text-right font-mono">{p.avgDays}d</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <TrendingUp className="h-4 w-4" />
                  Denial Rate by Payer
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {payerProfiles.map((p) => (
                  <div key={p.name} data-testid={`overview-denial-${p.name.replace(/\s+/g, '-').toLowerCase()}`}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm">{p.name}</span>
                      <span className={`text-sm font-bold font-mono ${p.denialRate > 10 ? "text-destructive" : p.denialRate > 7 ? "text-yellow-600 dark:text-yellow-400" : "text-emerald-600 dark:text-emerald-400"}`}>
                        {p.denialRate}%
                      </span>
                    </div>
                    <Progress value={p.denialRate * 5} className="h-1.5" />
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="payer-profiles" className="space-y-4 mt-4">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {payerProfiles.map((p) => (
              <Card key={p.name} data-testid={`profile-card-${p.name.replace(/\s+/g, '-').toLowerCase()}`}>
                <CardHeader>
                  <CardTitle className="flex items-center justify-between flex-wrap gap-2">
                    <div className="flex items-center gap-2">
                      <Building2 className="h-4 w-4" />
                      {p.name}
                    </div>
                    <Badge variant={p.denialRate <= 5 ? "default" : p.denialRate <= 9 ? "secondary" : "destructive"}>
                      {p.denialRate <= 5 ? "Low Risk" : p.denialRate <= 9 ? "Medium Risk" : "High Risk"}
                    </Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 mb-4">
                    <div>
                      <div className="flex items-center gap-1 text-xs text-muted-foreground mb-1">
                        <Users className="h-3 w-3" />
                        Patients
                      </div>
                      <div className="font-bold font-mono" data-testid={`profile-patients-${p.name.replace(/\s+/g, '-').toLowerCase()}`}>{p.patients}</div>
                    </div>
                    <div>
                      <div className="flex items-center gap-1 text-xs text-muted-foreground mb-1">
                        <Clock className="h-3 w-3" />
                        Avg Days
                      </div>
                      <div className="font-bold font-mono" data-testid={`profile-days-${p.name.replace(/\s+/g, '-').toLowerCase()}`}>{p.avgDays}d</div>
                    </div>
                    <div>
                      <div className="flex items-center gap-1 text-xs text-muted-foreground mb-1">
                        <DollarSign className="h-3 w-3" />
                        Reimb Rate
                      </div>
                      <div className="font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid={`profile-reimb-${p.name.replace(/\s+/g, '-').toLowerCase()}`}>{p.reimbRate}%</div>
                    </div>
                    <div>
                      <div className="flex items-center gap-1 text-xs text-muted-foreground mb-1">
                        <XCircle className="h-3 w-3" />
                        Denial Rate
                      </div>
                      <div className={`font-bold font-mono ${p.denialRate > 10 ? "text-destructive" : "text-yellow-600 dark:text-yellow-400"}`} data-testid={`profile-denial-${p.name.replace(/\s+/g, '-').toLowerCase()}`}>{p.denialRate}%</div>
                    </div>
                  </div>
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">Top Denial Reasons</div>
                    <div className="flex flex-wrap gap-2">
                      {p.topDenials.map((d, i) => (
                        <Badge key={i} variant="outline" data-testid={`denial-reason-${p.name.replace(/\s+/g, '-').toLowerCase()}-${i}`}>
                          <AlertTriangle className="mr-1 h-3 w-3" />
                          {d}
                        </Badge>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="contract-analysis" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="h-4 w-4" />
                Contract Analysis
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Payer</TableHead>
                    <TableHead>Effective Date</TableHead>
                    <TableHead>Fee Schedule</TableHead>
                    <TableHead className="text-right">Reimb %</TableHead>
                    <TableHead>Renewal Date</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {contracts.map((c) => (
                    <TableRow key={c.payer} data-testid={`contract-row-${c.payer.replace(/\s+/g, '-').toLowerCase()}`}>
                      <TableCell className="font-bold">{c.payer}</TableCell>
                      <TableCell className="font-mono text-muted-foreground">{c.effective}</TableCell>
                      <TableCell>{c.scheduleType}</TableCell>
                      <TableCell className="text-right font-mono font-bold text-emerald-600 dark:text-emerald-400">{c.reimbPct}%</TableCell>
                      <TableCell className="font-mono text-muted-foreground">{c.renewal}</TableCell>
                      <TableCell>
                        <Badge
                          variant={c.status === "Active" ? "default" : c.status === "Renewal Due" ? "destructive" : "secondary"}
                          data-testid={`contract-status-${c.payer.replace(/\s+/g, '-').toLowerCase()}`}
                        >
                          {c.status === "Active" && <CheckCircle className="mr-1 h-3 w-3" />}
                          {c.status === "Renewal Due" && <CalendarClock className="mr-1 h-3 w-3" />}
                          {c.status === "Negotiating" && <BarChart3 className="mr-1 h-3 w-3" />}
                          {c.status}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="reimbursement-trends" className="space-y-4 mt-4">
          {reimbursementByCategory.map((payer) => (
            <Card key={payer.payer} data-testid={`reimb-card-${payer.payer.replace(/\s+/g, '-').toLowerCase()}`}>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Building2 className="h-4 w-4" />
                  {payer.payer}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {[
                  { label: "Preventive", value: payer.preventive },
                  { label: "Basic", value: payer.basic },
                  { label: "Major", value: payer.major },
                  { label: "Implant", value: payer.implant },
                  { label: "Ortho", value: payer.ortho },
                ].map((cat) => (
                  <div key={cat.label} data-testid={`reimb-${payer.payer.replace(/\s+/g, '-').toLowerCase()}-${cat.label.toLowerCase()}`}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm">{cat.label}</span>
                      <span className={`text-sm font-bold font-mono ${cat.value >= 85 ? "text-emerald-600 dark:text-emerald-400" : cat.value >= 65 ? "text-yellow-600 dark:text-yellow-400" : "text-destructive"}`}>
                        {cat.value}%
                      </span>
                    </div>
                    <Progress value={cat.value} className="h-2" />
                  </div>
                ))}
              </CardContent>
            </Card>
          ))}
        </TabsContent>
      </Tabs>
    </div>
  );
}
