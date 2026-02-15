import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Wrench,
  CheckCircle,
  Clock,
  AlertTriangle,
  DollarSign,
  User,
  Calendar,
  Activity,
} from "lucide-react";

const implantCases = [
  { patient: "Margaret Sullivan", site: "#14", system: "Straumann BLT 4.1x10", phase: "Restoration", placed: "Dec 2025", nextStep: "Final impression (D6058)", nextDate: "Feb 28", healing: 85, status: "on-track", fee: "$5,050" },
  { patient: "Robert Kim", site: "#14", system: "Nobel Active 4.3x11.5", phase: "Planning", placed: "—", nextStep: "CBCT + surgical guide", nextDate: "Feb 20", healing: 0, status: "pending", fee: "$5,050" },
  { patient: "Tom Davis", site: "Full Arch", system: "Straumann Pro Arch", phase: "Healing", placed: "Jan 2026", nextStep: "Post-op check #2", nextDate: "Feb 18", healing: 40, status: "on-track", fee: "$24,800" },
  { patient: "Michael Torres", site: "#17", system: "Zimmer TSV 4.7x10", phase: "Osseointegration", placed: "Jan 2026", nextStep: "4-week check", nextDate: "Feb 22", healing: 55, status: "on-track", fee: "$5,050" },
  { patient: "Frank Morris", site: "#8", system: "Nobel CC 3.5x13", phase: "Bone Graft", placed: "—", nextStep: "Graft healing check", nextDate: "Mar 5", healing: 30, status: "delayed", fee: "$7,200" },
];

const phases = ["Planning", "Bone Graft", "Placement", "Osseointegration", "Healing", "Restoration", "Complete"];

export default function ImplantTrackerPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">
          Implant Case Tracker
        </h1>
        <p className="text-sm text-muted-foreground">
          Track every implant from planning through final restoration
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Wrench className="h-3.5 w-3.5" />
              Active Cases
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-active">24</div>
            <p className="text-xs font-medium text-muted-foreground">5 full arch, 19 single</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Activity className="h-3.5 w-3.5" />
              Healing
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="kpi-healing">18</div>
            <p className="text-xs font-medium text-muted-foreground">100% success rate YTD</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Clock className="h-3.5 w-3.5" />
              Ready for Restore
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-purple-600 dark:text-purple-400" data-testid="kpi-restore">4</div>
            <p className="text-xs font-medium text-muted-foreground">Schedule impression</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <DollarSign className="h-3.5 w-3.5" />
              Pipeline Value
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-pipeline">$186,400</div>
            <p className="text-xs font-medium text-emerald-600 dark:text-emerald-400">$42,800 collected</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Wrench className="h-4 w-4" />
            Implant Cases
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {implantCases.map((c, i) => (
              <div key={i} className="rounded-md border p-4" data-testid={`implant-case-${i}`}>
                <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
                  <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10">
                      <User className="h-4 w-4 text-primary" />
                    </div>
                    <div>
                      <div className="text-sm font-bold">{c.patient}</div>
                      <div className="text-xs text-muted-foreground">
                        Site {c.site} — {c.system}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="font-mono text-xs">{c.fee}</Badge>
                    <Badge
                      variant={c.status === "on-track" ? "default" : c.status === "delayed" ? "destructive" : "outline"}
                    >
                      {c.status === "on-track" ? <CheckCircle className="mr-1 h-3 w-3" /> : c.status === "delayed" ? <AlertTriangle className="mr-1 h-3 w-3" /> : <Clock className="mr-1 h-3 w-3" />}
                      {c.status}
                    </Badge>
                  </div>
                </div>

                <div className="mb-3">
                  <div className="flex items-center gap-1 mb-2">
                    {phases.map((phase, pi) => {
                      const currentIdx = phases.indexOf(c.phase);
                      const isComplete = pi < currentIdx;
                      const isCurrent = pi === currentIdx;
                      return (
                        <div key={phase} className="flex items-center flex-1">
                          <div
                            className={`h-1.5 w-full rounded-full ${
                              isComplete
                                ? "bg-emerald-500"
                                : isCurrent
                                  ? "bg-primary"
                                  : "bg-muted"
                            }`}
                          />
                        </div>
                      );
                    })}
                  </div>
                  <div className="flex items-center justify-between text-[10px] text-muted-foreground">
                    <span>Current: <strong className="text-foreground">{c.phase}</strong></span>
                    <span>Placed: {c.placed}</span>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 text-xs">
                  <div>
                    <span className="text-muted-foreground">Next Step</span>
                    <div className="font-bold">{c.nextStep}</div>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Next Date</span>
                    <div className="font-bold">{c.nextDate}</div>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Healing</span>
                    <div className="flex items-center gap-2">
                      <Progress value={c.healing} className="h-1.5 flex-1" />
                      <span className="font-bold font-mono">{c.healing}%</span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
