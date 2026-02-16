import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Shield,
  FileSearch,
  AlertTriangle,
  DollarSign,
  ClipboardCheck,
  Bot,
  CheckCircle,
} from "lucide-react";

const auditItems = [
  {
    issue: "D2950 without crown code",
    provider: "Dr. Chen",
    cases: 2,
    severity: "HIGH",
    resolution: "Unbundling risk \u2014 D2740 attached",
  },
  {
    issue: "D0220 PA + D0330 Pano same day",
    provider: "Dr. Park",
    cases: 1,
    severity: "MED",
    resolution: "Modifier documentation added",
  },
  {
    issue: "D4341 SRP without perio chart",
    provider: "Sarah RDH",
    cases: 3,
    severity: "HIGH",
    resolution: "Perio charts attached retroactively",
  },
  {
    issue: "Narrative missing D2740 >$1,200",
    provider: "Dr. Chen",
    cases: 2,
    severity: "MED",
    resolution: "AI auto-generated narratives",
  },
];

const docCompleteness = [
  { label: "SOAP notes signed", value: 98 },
  { label: "Perio charts with SRP", value: 88 },
  { label: "Consent forms on file", value: 100 },
  { label: "X-rays attached to claims", value: 95 },
  { label: "Medical history <12mo", value: 82 },
  { label: "Narratives on major procs", value: 91 },
  { label: "Pre-auth documentation", value: 96 },
];

export default function CompliancePage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">
          AI Compliance & Coding Audit
        </h1>
        <p className="text-sm text-muted-foreground">
          Automated chart auditing, coding compliance, and documentation completeness
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Shield className="h-3.5 w-3.5" />
              Compliance Score
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="kpi-compliance-score">96.4%</div>
            <p className="text-xs font-medium text-emerald-600 dark:text-emerald-400">Excellent</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <FileSearch className="h-3.5 w-3.5" />
              Charts Audited
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-blue-600 dark:text-blue-400" data-testid="kpi-charts-audited">342</div>
            <p className="text-xs font-medium text-muted-foreground">100% auto-audited</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <AlertTriangle className="h-3.5 w-3.5" />
              Issues Found
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-yellow-600 dark:text-yellow-400" data-testid="kpi-issues-found">12</div>
            <p className="text-xs font-medium text-muted-foreground">8 resolved, 4 pending</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <DollarSign className="h-3.5 w-3.5" />
              Risk Avoided
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="kpi-risk-avoided">$28,400</div>
            <p className="text-xs font-medium text-muted-foreground">Potential audit exposure</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ClipboardCheck className="h-4 w-4" />
              Coding Audit &mdash; This Week
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {auditItems.map((item, i) => {
              const isHigh = item.severity === "HIGH";
              const borderColor = isHigh ? "border-destructive" : "border-yellow-500";
              const bgColor = isHigh ? "bg-destructive/5" : "bg-yellow-500/5";
              return (
                <div key={i} className={`rounded-md border-l-4 ${borderColor} ${bgColor} p-3`} data-testid={`audit-item-${i}`}>
                  <div className="flex items-center justify-between mb-1 flex-wrap gap-2">
                    <span className="text-xs font-bold">{item.issue}</span>
                    <Badge
                      variant={isHigh ? "destructive" : "outline"}
                      className={`text-[10px] ${!isHigh ? "text-yellow-600 dark:text-yellow-400 border-yellow-500" : ""}`}
                      data-testid={`badge-severity-${i}`}
                    >
                      {item.severity}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-muted-foreground mb-1 flex-wrap">
                    <span>{item.provider}</span>
                    <span>{item.cases} {item.cases === 1 ? "case" : "cases"}</span>
                  </div>
                  <p className="text-xs text-emerald-600 dark:text-emerald-400">
                    <Bot className="inline mr-1 h-3 w-3" />
                    {item.resolution}
                  </p>
                </div>
              );
            })}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileSearch className="h-4 w-4" />
              Documentation Completeness
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {docCompleteness.map((doc, i) => {
              const valueColor =
                doc.value >= 95
                  ? "text-emerald-600 dark:text-emerald-400"
                  : doc.value >= 90
                    ? "text-foreground"
                    : "text-yellow-600 dark:text-yellow-400";
              const progressClass =
                doc.value < 90 ? "[&>div]:bg-yellow-500" : "";
              return (
                <div key={i} data-testid={`doc-completeness-${i}`}>
                  <div className="flex items-center justify-between mb-1 flex-wrap gap-2">
                    <span className="text-xs font-medium">{doc.label}</span>
                    <span className={`text-xs font-bold font-mono ${valueColor}`}>{doc.value}%</span>
                  </div>
                  <Progress value={doc.value} className={`h-2 ${progressClass}`} />
                </div>
              );
            })}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
