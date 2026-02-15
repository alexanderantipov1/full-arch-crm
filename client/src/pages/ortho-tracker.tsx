import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  Smile,
  Calendar,
  Clock,
  DollarSign,
  Camera,
  ArrowRight,
  CheckCircle,
  AlertTriangle,
  User,
} from "lucide-react";

const activeCases = [
  { patient: "Diana Patel", type: "Invisalign Full", aligner: "8/24", nextVisit: "Feb 18", compliance: 92, status: "on-track", startDate: "Aug 2025", estEnd: "Jun 2026", totalFee: "$5,500", remaining: "$3,500" },
  { patient: "Tyler Nguyen", type: "Invisalign Lite", aligner: "3/14", nextVisit: "Feb 22", compliance: 88, status: "on-track", startDate: "Dec 2025", estEnd: "Jul 2026", totalFee: "$3,800", remaining: "$2,800" },
  { patient: "Sarah Chen", type: "Metal Braces", aligner: "Mo 6/18", nextVisit: "Mar 1", compliance: 95, status: "on-track", startDate: "Aug 2025", estEnd: "Feb 2027", totalFee: "$4,200", remaining: "$2,400" },
  { patient: "Jake Morrison", type: "Invisalign Full", aligner: "18/30", nextVisit: "Feb 20", compliance: 74, status: "behind", startDate: "Mar 2025", estEnd: "Sep 2026", totalFee: "$5,500", remaining: "$1,200" },
  { patient: "Lily Park", type: "Clear Braces", aligner: "Mo 3/14", nextVisit: "Feb 25", compliance: 96, status: "on-track", startDate: "Nov 2025", estEnd: "Jan 2027", totalFee: "$4,800", remaining: "$3,600" },
];

export default function OrthoTrackerPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">
          Ortho Case Tracker
        </h1>
        <p className="text-sm text-muted-foreground">
          Aligner tracking, compliance monitoring, treatment milestones
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Smile className="h-3.5 w-3.5" />
              Active Cases
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-active-cases">18</div>
            <p className="text-xs font-medium text-emerald-600 dark:text-emerald-400">14 Invisalign, 4 Braces</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <CheckCircle className="h-3.5 w-3.5" />
              On Track
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="kpi-on-track">15</div>
            <p className="text-xs font-medium text-muted-foreground">83% compliance avg</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <AlertTriangle className="h-3.5 w-3.5" />
              Behind Schedule
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-yellow-600 dark:text-yellow-400" data-testid="kpi-behind">3</div>
            <p className="text-xs font-medium text-muted-foreground">AI follow-up scheduled</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <DollarSign className="h-3.5 w-3.5" />
              Outstanding AR
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-ortho-ar">$42,800</div>
            <p className="text-xs font-medium text-muted-foreground">94% on-time payments</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Smile className="h-4 w-4" />
            Active Ortho Cases
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {activeCases.map((c, i) => (
              <div
                key={i}
                className="rounded-md border p-4"
                data-testid={`ortho-case-${i}`}
              >
                <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
                  <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10">
                      <User className="h-4 w-4 text-primary" />
                    </div>
                    <div>
                      <div className="text-sm font-bold">{c.patient}</div>
                      <div className="text-xs text-muted-foreground">{c.type}</div>
                    </div>
                  </div>
                  <Badge variant={c.status === "on-track" ? "default" : "outline"}>
                    {c.status === "on-track" ? (
                      <CheckCircle className="mr-1 h-3 w-3" />
                    ) : (
                      <AlertTriangle className="mr-1 h-3 w-3" />
                    )}
                    {c.status}
                  </Badge>
                </div>
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-6 text-xs">
                  <div>
                    <span className="text-muted-foreground">Progress</span>
                    <div className="font-bold font-mono">{c.aligner}</div>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Next Visit</span>
                    <div className="font-bold">{c.nextVisit}</div>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Compliance</span>
                    <div className={`font-bold font-mono ${c.compliance >= 85 ? "text-emerald-600 dark:text-emerald-400" : "text-yellow-600 dark:text-yellow-400"}`}>
                      {c.compliance}%
                    </div>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Est. End</span>
                    <div className="font-bold">{c.estEnd}</div>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Total Fee</span>
                    <div className="font-bold font-mono">{c.totalFee}</div>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Remaining</span>
                    <div className="font-bold font-mono text-yellow-600 dark:text-yellow-400">{c.remaining}</div>
                  </div>
                </div>
                <div className="mt-3">
                  <Progress value={c.compliance} className="h-1.5" />
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
