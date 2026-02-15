import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Target,
  DollarSign,
  CheckCircle,
  Clock,
  User,
  Bot,
  TrendingUp,
  BarChart3,
} from "lucide-react";

const presentations = [
  { patient: "Robert Kim", tx: "Implant #14", total: "$5,050", insurance: "$2,095", oop: "$2,955", monthly: "$123/mo", status: "pending", days: 3 },
  { patient: "Margaret Sullivan", tx: "Crown #3 + SRP", total: "$2,100", insurance: "$1,240", oop: "$860", monthly: "$143/mo", status: "accepted", days: 0 },
  { patient: "Sophia Adams", tx: "Invisalign Full", total: "$5,500", insurance: "$2,000", oop: "$3,500", monthly: "$291/mo", status: "pending", days: 7 },
  { patient: "Tom Davis", tx: "Full Arch", total: "$24,800", insurance: "$4,000", oop: "$20,800", monthly: "$433/mo", status: "pending", days: 14 },
  { patient: "Emma Rodriguez", tx: "Veneers x4", total: "$6,400", insurance: "$0", oop: "$6,400", monthly: "$266/mo", status: "declined", days: 5 },
];

const objections = [
  { reason: "Too expensive", pct: 42, aiResponse: "Auto-show monthly payment options", color: "text-destructive" },
  { reason: "Need to think", pct: 28, aiResponse: "3-day follow-up with education content", color: "text-yellow-600 dark:text-yellow-400" },
  { reason: "Not sure if necessary", pct: 18, aiResponse: "Send AI X-ray overlay with explanation", color: "text-orange-600 dark:text-orange-400" },
  { reason: "Want 2nd opinion", pct: 8, aiResponse: "Share ADA clinical guidelines", color: "text-primary" },
  { reason: "Dental anxiety", pct: 4, aiResponse: "Offer sedation options + testimonials", color: "text-purple-600 dark:text-purple-400" },
];

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
            <p className="text-xs font-medium text-emerald-600 dark:text-emerald-400">Up from 58% pre-AI</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <DollarSign className="h-3.5 w-3.5" />
              Presented MTD
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-presented">$186,400</div>
            <p className="text-xs font-medium text-muted-foreground">42 presentations</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <CheckCircle className="h-3.5 w-3.5" />
              Accepted MTD
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="kpi-accepted">$138,000</div>
            <p className="text-xs font-medium text-muted-foreground">74% of presented</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Clock className="h-3.5 w-3.5" />
              Pending
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-yellow-600 dark:text-yellow-400" data-testid="kpi-pending">$32,800</div>
            <p className="text-xs font-medium text-muted-foreground">18 pts — AI following up</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Target className="h-4 w-4" />
              Active Presentations
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {presentations.map((p, i) => (
              <div
                key={i}
                className="rounded-md border p-3"
                data-testid={`presentation-${i}`}
              >
                <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold">{p.patient}</span>
                    <span className="text-xs text-muted-foreground">{p.days}d ago</span>
                  </div>
                  <Badge variant={p.status === "accepted" ? "default" : p.status === "declined" ? "destructive" : "outline"}>
                    {p.status === "accepted" ? <CheckCircle className="mr-1 h-3 w-3" /> : <Clock className="mr-1 h-3 w-3" />}
                    {p.status}
                  </Badge>
                </div>
                <div className="text-xs text-muted-foreground mb-2">{p.tx}</div>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 text-xs">
                  <div>
                    <span className="text-muted-foreground">Total</span>
                    <div className="font-bold font-mono">{p.total}</div>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Insurance</span>
                    <div className="font-bold font-mono text-emerald-600 dark:text-emerald-400">{p.insurance}</div>
                  </div>
                  <div>
                    <span className="text-muted-foreground">OOP</span>
                    <div className="font-bold font-mono text-yellow-600 dark:text-yellow-400">{p.oop}</div>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Monthly</span>
                    <div className="font-bold font-mono text-cyan-600 dark:text-cyan-400">{p.monthly}</div>
                  </div>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="h-4 w-4" />
              Objection Analysis
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {objections.map((obj, i) => (
              <div key={i} data-testid={`objection-${i}`}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm">{obj.reason}</span>
                  <span className={`text-sm font-bold font-mono ${obj.color}`}>{obj.pct}%</span>
                </div>
                <Progress value={obj.pct} className="h-1.5 mb-1" />
                <p className="text-xs text-emerald-600 dark:text-emerald-400">
                  <Bot className="inline mr-1 h-3 w-3" />
                  {obj.aiResponse}
                </p>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
