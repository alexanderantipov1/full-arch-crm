import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  FileCheck,
  DollarSign,
  Clock,
  ArrowLeftRight,
  FileText,
  AlertTriangle,
  Mic,
  Globe,
  Activity,
  Gauge,
  Send,
  ShieldCheck,
  Repeat,
  FileSignature,
  Scale,
  AudioLines,
  MailCheck,
  CheckCircle,
} from "lucide-react";

const activityFeed = [
  { time: "2:42 PM", text: "Claim D2740 #3 — Margaret Sullivan auto-submitted to Delta", amount: "$1,280", color: "border-emerald-500" },
  { time: "2:38 PM", text: "Insurance verified — Robert Kim (Cigna PPO) implant benefits confirmed", amount: null, color: "border-blue-500" },
  { time: "2:31 PM", text: "Cross-coded: Sleep appliance D5988 to G47.33 to E0486 for medical billing", amount: "$2,400", color: "border-purple-500" },
  { time: "2:24 PM", text: "Medical necessity letter generated for SRP D4341 — James Okafor", amount: null, color: "border-yellow-500" },
  { time: "2:18 PM", text: "Appeal auto-submitted: Denied crown D2740 — MetLife — clinical narrative attached", amount: "$1,280", color: "border-destructive" },
  { time: "2:10 PM", text: "Voice note to SOAP to CDT auto-coded: Dr. Chen — Michael Torres implant follow-up", amount: null, color: "border-cyan-500" },
  { time: "1:55 PM", text: "ERA auto-posted: Cigna batch $8,420 — 12 claims reconciled", amount: "$8,420", color: "border-emerald-500" },
];

const engineMetrics = [
  { label: "Claim Accuracy", value: 97.8 },
  { label: "Verification Speed", value: 95, sub: "4.2 sec" },
  { label: "Cross-Code Match", value: 89 },
  { label: "Necessity Approval", value: 91 },
  { label: "Appeal Overturn", value: 68 },
  { label: "Voice-to-Code", value: 98.4 },
  { label: "ERA Auto-Post", value: 96 },
  { label: "First-Pass Rate", value: 94.2 },
];

export default function RcmPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">
          Revenue Cycle Command Center
        </h1>
        <p className="text-sm text-muted-foreground">
          Claims, collections, cross-coding, appeals, voice-to-code, ERA auto-posting
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <FileCheck className="h-3.5 w-3.5" />
              Claims MTD
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-claims-mtd">847</div>
            <p className="text-xs font-medium text-emerald-600 dark:text-emerald-400">94.2% first-pass rate</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <DollarSign className="h-3.5 w-3.5" />
              Collections MTD
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="kpi-collections-mtd">$198,240</div>
            <p className="text-xs font-medium text-muted-foreground">99.5% of net production</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Clock className="h-3.5 w-3.5" />
              Days in A/R
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-days-ar">18.4</div>
            <p className="text-xs font-medium text-emerald-600 dark:text-emerald-400">Down from 32 days</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <ArrowLeftRight className="h-3.5 w-3.5" />
              Cross-Coded
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-purple-600 dark:text-purple-400" data-testid="kpi-cross-coded">34</div>
            <p className="text-xs font-medium text-muted-foreground">$28,400 medical revenue</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <FileText className="h-3.5 w-3.5" />
              Necessity Letters
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-necessity-letters">18</div>
            <p className="text-xs font-medium text-emerald-600 dark:text-emerald-400">91% approval rate</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <AlertTriangle className="h-3.5 w-3.5" />
              Open Denials
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-destructive" data-testid="kpi-open-denials">$12,840</div>
            <p className="text-xs font-medium text-muted-foreground">68% overturn rate</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Mic className="h-3.5 w-3.5" />
              Voice Notes
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-voice-notes">24</div>
            <p className="text-xs font-medium text-muted-foreground">6.8 hrs saved today</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Globe className="h-3.5 w-3.5" />
              Payer Connections
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-cyan-600 dark:text-cyan-400" data-testid="kpi-payer-connections">340+</div>
            <p className="text-xs font-medium text-muted-foreground">All major payers</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-4 w-4" />
              Live Revenue Activity
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {activityFeed.map((item, i) => (
                <div
                  key={i}
                  className={`border-l-2 ${item.color} pl-3 py-1`}
                  data-testid={`activity-item-${i}`}
                >
                  <div className="flex items-start justify-between gap-2 flex-wrap">
                    <div className="text-sm">
                      <span className="font-mono text-xs font-bold text-muted-foreground mr-2" data-testid={`activity-time-${i}`}>{item.time}</span>
                      <span data-testid={`activity-text-${i}`}>{item.text}</span>
                    </div>
                    {item.amount && (
                      <Badge variant="outline" className="font-mono text-xs shrink-0" data-testid={`activity-amount-${i}`}>
                        {item.amount}
                      </Badge>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Gauge className="h-4 w-4" />
              Engine Performance
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {engineMetrics.map((m, i) => (
                <div key={i} data-testid={`engine-metric-${i}`}>
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <span className="text-sm font-medium" data-testid={`engine-metric-label-${i}`}>{m.label}</span>
                    <span className="text-sm font-mono font-bold" data-testid={`engine-metric-value-${i}`}>
                      {m.sub ? `${m.sub} (${m.value}%)` : `${m.value}%`}
                    </span>
                  </div>
                  <Progress value={m.value} className="h-2" />
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
