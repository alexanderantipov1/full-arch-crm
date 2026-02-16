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
  Target,
  DollarSign,
  CheckCircle,
  Clock,
  Bot,
  BarChart3,
  Users,
  Phone,
  Calendar,
  AlertTriangle,
  MessageSquare,
  ArrowRight,
} from "lucide-react";

const pendingCases = [
  { patient: "Robert Kim", treatment: "Implant #14 + Custom Abutment + Crown", total: 5050, insurance: 2095, oop: 2955, monthly: "$123/mo", status: "Presented" as const },
  { patient: "Sophia Adams", treatment: "Invisalign Full Comprehensive", total: 5500, insurance: 2000, oop: 3500, monthly: "$291/mo", status: "Considering" as const },
  { patient: "Tom Davis", treatment: "Full Arch Implant Restoration (Upper)", total: 24800, insurance: 4000, oop: 20800, monthly: "$433/mo", status: "Presented" as const },
  { patient: "Emma Rodriguez", treatment: "Porcelain Veneers x4 (#6-#11)", total: 6400, insurance: 0, oop: 6400, monthly: "$266/mo", status: "Considering" as const },
  { patient: "James Chen", treatment: "Crown #3 + SRP All Quads", total: 2100, insurance: 1240, oop: 860, monthly: "$143/mo", status: "Scheduled" as const },
  { patient: "Maria Lopez", treatment: "Bridge #18-#20 (3-unit)", total: 3600, insurance: 1800, oop: 1800, monthly: "$150/mo", status: "Presented" as const },
  { patient: "William Park", treatment: "Implant #30 + Crown", total: 4200, insurance: 1680, oop: 2520, monthly: "$105/mo", status: "Considering" as const },
];

const objections = [
  { reason: "Too expensive", pct: 42, aiStrategy: "Automatically present monthly payment options, show insurance breakdown, and highlight cost of delayed treatment. Offer CareCredit/Sunbit pre-qualification.", color: "text-destructive" },
  { reason: "Need to think about it", pct: 28, aiStrategy: "Schedule 3-day automated follow-up with educational content. Send personalized video from provider explaining clinical necessity and outcomes.", color: "text-yellow-600 dark:text-yellow-400" },
  { reason: "Not sure if necessary", pct: 18, aiStrategy: "Send AI-annotated X-ray overlay with visual explanation. Include ADA clinical guidelines and peer-reviewed research supporting the treatment.", color: "text-orange-600 dark:text-orange-400" },
  { reason: "Want second opinion", pct: 8, aiStrategy: "Share ADA clinical practice guidelines, before/after case studies from similar patients, and offer complimentary consultation with associate provider.", color: "text-purple-600 dark:text-purple-400" },
  { reason: "Dental anxiety", pct: 4, aiStrategy: "Offer sedation options with pricing, share patient testimonials about comfort, and provide virtual office tour video with calm environment highlights.", color: "text-cyan-600 dark:text-cyan-400" },
];

const followUpQueue = [
  { patient: "Tom Davis", treatment: "Full Arch Implant (Upper)", value: 24800, daysSince: 14, staff: "Dr. Sarah Mitchell", method: "Phone Call", priority: "High" as const },
  { patient: "Emma Rodriguez", treatment: "Porcelain Veneers x4", value: 6400, daysSince: 5, staff: "Lisa (TC)", method: "Text Message", priority: "Medium" as const },
  { patient: "Sophia Adams", treatment: "Invisalign Full", value: 5500, daysSince: 7, staff: "Lisa (TC)", method: "Email + Call", priority: "High" as const },
  { patient: "Robert Kim", treatment: "Implant #14", value: 5050, daysSince: 3, staff: "Dr. Sarah Mitchell", method: "In-Person", priority: "Medium" as const },
  { patient: "Maria Lopez", treatment: "Bridge #18-#20", value: 3600, daysSince: 10, staff: "Amy (Front Desk)", method: "Phone Call", priority: "High" as const },
  { patient: "William Park", treatment: "Implant #30 + Crown", value: 4200, daysSince: 6, staff: "Lisa (TC)", method: "Text Message", priority: "Medium" as const },
  { patient: "David Brown", treatment: "Crown Lengthening + Crown #19", value: 2800, daysSince: 12, staff: "Amy (Front Desk)", method: "Phone Call", priority: "High" as const },
  { patient: "Karen White", treatment: "Night Guard + Composites x3", value: 1950, daysSince: 4, staff: "Lisa (TC)", method: "Email", priority: "Low" as const },
  { patient: "Michael Torres", treatment: "SRP All Quads + Re-eval", value: 1200, daysSince: 8, staff: "Amy (Front Desk)", method: "Text Message", priority: "Medium" as const },
  { patient: "Jennifer Nguyen", treatment: "Extraction #1 + Implant Consult", value: 850, daysSince: 2, staff: "Dr. Sarah Mitchell", method: "In-Person", priority: "Low" as const },
  { patient: "Anthony Patel", treatment: "Composite Veneers x2", value: 1600, daysSince: 9, staff: "Lisa (TC)", method: "Email + Call", priority: "Medium" as const },
  { patient: "Samantha Lee", treatment: "Whitening + Bonding", value: 980, daysSince: 11, staff: "Amy (Front Desk)", method: "Phone Call", priority: "Low" as const },
];

function StatusBadge({ status }: { status: "Presented" | "Considering" | "Scheduled" }) {
  if (status === "Presented") {
    return (
      <Badge variant="outline" data-testid={`badge-status-presented`}>
        <Clock className="mr-1 h-3 w-3" />
        Presented
      </Badge>
    );
  }
  if (status === "Considering") {
    return (
      <Badge variant="secondary" data-testid={`badge-status-considering`}>
        <MessageSquare className="mr-1 h-3 w-3" />
        Considering
      </Badge>
    );
  }
  return (
    <Badge variant="default" data-testid={`badge-status-scheduled`}>
      <Calendar className="mr-1 h-3 w-3" />
      Scheduled
    </Badge>
  );
}

export default function CaseAcceptancePage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">
          AI Case Acceptance Engine
        </h1>
        <p className="text-sm text-muted-foreground">
          Visual treatment presentation, financing integration, AI follow-up sequences
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Target className="h-3.5 w-3.5" />
              Acceptance Rate
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="kpi-accept-rate">74%</div>
            <Progress value={74} className="mt-2 h-1.5" />
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <DollarSign className="h-3.5 w-3.5" />
              Presented MTD
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-presented">$186K</div>
            <p className="text-xs font-medium text-muted-foreground">42 presentations</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <CheckCircle className="h-3.5 w-3.5" />
              Accepted MTD
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="kpi-accepted">$137K</div>
            <p className="text-xs font-medium text-muted-foreground">74% of presented</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Clock className="h-3.5 w-3.5" />
              Pending Follow-Up
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-yellow-600 dark:text-yellow-400" data-testid="kpi-pending-followup">12</div>
            <p className="text-xs font-medium text-muted-foreground">Patients awaiting decision</p>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="overview" data-testid="tabs-case-acceptance">
        <TabsList data-testid="tabslist-case-acceptance">
          <TabsTrigger value="overview" data-testid="tab-overview">Overview</TabsTrigger>
          <TabsTrigger value="pending-cases" data-testid="tab-pending-cases">Pending Cases</TabsTrigger>
          <TabsTrigger value="objection-analysis" data-testid="tab-objection-analysis">Objection Analysis</TabsTrigger>
          <TabsTrigger value="follow-up-queue" data-testid="tab-follow-up-queue">Follow-Up Queue</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4 mt-4">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BarChart3 className="h-4 w-4" />
                  Acceptance by Treatment Type
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {[
                  { type: "Preventive", rate: 92 },
                  { type: "Restorative", rate: 78 },
                  { type: "Crowns/Bridges", rate: 71 },
                  { type: "Implants", rate: 58 },
                  { type: "Ortho", rate: 65 },
                  { type: "Cosmetic", rate: 48 },
                ].map((t) => (
                  <div key={t.type} data-testid={`overview-accept-${t.type.toLowerCase().replace(/\//g, '-')}`}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm">{t.type}</span>
                      <span className={`text-sm font-bold font-mono ${t.rate >= 75 ? "text-emerald-600 dark:text-emerald-400" : t.rate >= 60 ? "text-yellow-600 dark:text-yellow-400" : "text-destructive"}`}>{t.rate}%</span>
                    </div>
                    <Progress value={t.rate} className="h-2" />
                  </div>
                ))}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Target className="h-4 w-4" />
                  Case Status Breakdown
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div data-testid="overview-status-accepted">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm">Accepted</span>
                    <span className="text-sm font-bold font-mono text-emerald-600 dark:text-emerald-400">31 cases</span>
                  </div>
                  <Progress value={74} className="h-2" />
                </div>
                <div data-testid="overview-status-pending">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm">Pending / Considering</span>
                    <span className="text-sm font-bold font-mono text-yellow-600 dark:text-yellow-400">8 cases</span>
                  </div>
                  <Progress value={19} className="h-2" />
                </div>
                <div data-testid="overview-status-declined">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm">Declined</span>
                    <span className="text-sm font-bold font-mono text-destructive">3 cases</span>
                  </div>
                  <Progress value={7} className="h-2" />
                </div>
                <div className="pt-4 border-t">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <div className="text-xs text-muted-foreground">Avg Case Value</div>
                      <div className="font-bold font-mono text-lg" data-testid="overview-avg-case">$4,436</div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground">Avg Days to Accept</div>
                      <div className="font-bold font-mono text-lg" data-testid="overview-avg-days">4.2 days</div>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="pending-cases" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Users className="h-4 w-4" />
                Pending Cases
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Patient</TableHead>
                    <TableHead>Treatment</TableHead>
                    <TableHead className="text-right">Total Cost</TableHead>
                    <TableHead className="text-right">Insurance Est.</TableHead>
                    <TableHead className="text-right">OOP Est.</TableHead>
                    <TableHead className="text-right">Monthly</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {pendingCases.map((c, i) => (
                    <TableRow key={i} data-testid={`pending-case-${i}`}>
                      <TableCell className="font-bold">{c.patient}</TableCell>
                      <TableCell className="text-muted-foreground max-w-[200px] truncate">{c.treatment}</TableCell>
                      <TableCell className="text-right font-mono font-bold">${c.total.toLocaleString()}</TableCell>
                      <TableCell className="text-right font-mono text-emerald-600 dark:text-emerald-400">${c.insurance.toLocaleString()}</TableCell>
                      <TableCell className="text-right font-mono text-yellow-600 dark:text-yellow-400">${c.oop.toLocaleString()}</TableCell>
                      <TableCell className="text-right font-mono text-cyan-600 dark:text-cyan-400">{c.monthly}</TableCell>
                      <TableCell>
                        <StatusBadge status={c.status} />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="objection-analysis" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="h-4 w-4" />
                Objection Breakdown with AI Counter-Strategies
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {objections.map((obj, i) => (
                <div key={i} data-testid={`objection-${i}`}>
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                      <AlertTriangle className={`h-4 w-4 ${obj.color}`} />
                      <span className="text-sm font-bold">{obj.reason}</span>
                    </div>
                    <span className={`text-sm font-bold font-mono ${obj.color}`}>{obj.pct}%</span>
                  </div>
                  <Progress value={obj.pct} className="h-2 mb-2" />
                  <div className="rounded-md border p-3">
                    <div className="flex items-start gap-2">
                      <Bot className="h-4 w-4 mt-0.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
                      <p className="text-sm text-muted-foreground" data-testid={`objection-strategy-${i}`}>{obj.aiStrategy}</p>
                    </div>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="follow-up-queue" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Phone className="h-4 w-4" />
                Follow-Up Queue
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {followUpQueue.map((f, i) => (
                <div
                  key={i}
                  className="rounded-md border p-3"
                  data-testid={`followup-${i}`}
                >
                  <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-bold">{f.patient}</span>
                      <Badge variant={f.priority === "High" ? "destructive" : f.priority === "Medium" ? "secondary" : "outline"} data-testid={`followup-priority-${i}`}>
                        {f.priority}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground">{f.daysSince}d since presentation</span>
                      <Button size="sm" variant="outline" data-testid={`btn-followup-${i}`}>
                        <ArrowRight className="mr-1 h-3 w-3" />
                        Follow Up
                      </Button>
                    </div>
                  </div>
                  <div className="text-xs text-muted-foreground mb-2">{f.treatment}</div>
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 text-xs">
                    <div>
                      <span className="text-muted-foreground">Value</span>
                      <div className="font-bold font-mono" data-testid={`followup-value-${i}`}>${f.value.toLocaleString()}</div>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Assigned</span>
                      <div className="font-bold" data-testid={`followup-staff-${i}`}>{f.staff}</div>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Method</span>
                      <div className="font-bold" data-testid={`followup-method-${i}`}>{f.method}</div>
                    </div>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
