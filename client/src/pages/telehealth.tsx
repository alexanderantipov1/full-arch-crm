import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Video,
  Camera,
  CheckCircle,
  Clock,
  AlertTriangle,
  Calendar,
  User,
  Shield,
  Phone,
} from "lucide-react";

const todayQueue = [
  { patient: "Sarah Chen", reason: "Implant consult (new lead)", time: "11:00 AM", type: "Video", status: "waiting", statusColor: "outline" as const },
  { patient: "Tom Davis", reason: "Post-op check (extraction)", time: "1:00 PM", type: "Video", status: "scheduled", statusColor: "default" as const },
  { patient: "Nina Fox", reason: "Photo triage (swelling)", time: "ASAP", type: "Photo", status: "urgent", statusColor: "destructive" as const },
];

const recentConsults = [
  { patient: "Frank Morris", type: "Post-op #8 implant", duration: "8 min", outcome: "Healing normal. No in-office needed.", billed: "D9995 — $75", date: "Feb 13" },
  { patient: "Karen Brown", type: "Crown sensitivity check", duration: "5 min", outcome: "Advised warm salt rinse. Monitor 1 week.", billed: "D9995 — $75", date: "Feb 12" },
  { patient: "Pete Hall", type: "Swelling triage (photo)", duration: "3 min", outcome: "Normal post-extraction. Prescribed rinse.", billed: "D9996 — $55", date: "Feb 11" },
  { patient: "Lisa Wang", type: "Invisalign tracking check", duration: "6 min", outcome: "Aligner fits well. Proceed to next set.", billed: "D9995 — $75", date: "Feb 10" },
];

export default function TelehealthPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">
          Teledentistry Module
        </h1>
        <p className="text-sm text-muted-foreground">
          HIPAA-compliant video consults, photo triage, remote monitoring (D9995/D9996)
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Video className="h-3.5 w-3.5" />
              Video Consults MTD
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-video">24</div>
            <p className="text-xs font-medium text-emerald-600 dark:text-emerald-400">$4,800 billed</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Camera className="h-3.5 w-3.5" />
              Photo Triage
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-photo">18</div>
            <p className="text-xs font-medium text-muted-foreground">12 in-office, 6 advice only</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <CheckCircle className="h-3.5 w-3.5" />
              Post-Op Checks
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="kpi-postop">34</div>
            <p className="text-xs font-medium text-muted-foreground">0 complications</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Calendar className="h-4 w-4" />
              Today's Telehealth Queue
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {todayQueue.map((q, i) => (
              <div key={i} className="flex items-center justify-between border-b pb-3 last:border-0 gap-4" data-testid={`telehealth-queue-${i}`}>
                <div>
                  <div className="text-sm font-bold">{q.patient}</div>
                  <div className="text-xs text-muted-foreground">{q.reason} / {q.time} / {q.type}</div>
                </div>
                <Badge variant={q.statusColor}>{q.status}</Badge>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card className="flex flex-col items-center justify-center p-8 bg-muted/30">
          <Video className="h-12 w-12 text-muted-foreground/30 mb-4" />
          <p className="text-sm font-semibold text-muted-foreground mb-4">HIPAA-Compliant Video Room</p>
          <div className="flex items-center gap-2 mb-2">
            <Shield className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
            <span className="text-xs text-emerald-600 dark:text-emerald-400 font-medium">End-to-end encrypted</span>
          </div>
          <Button size="lg" className="mt-2" data-testid="button-start-video">
            <Video className="mr-2 h-4 w-4" />
            Start Video Consult
          </Button>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-4 w-4" />
            Recent Consults
          </CardTitle>
        </CardHeader>
        <CardContent>
          {recentConsults.map((c, i) => (
            <div key={i} className="flex items-center justify-between border-b py-3 last:border-0 gap-4" data-testid={`recent-consult-${i}`}>
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-bold">{c.patient}</span>
                  <span className="text-xs text-muted-foreground">{c.date}</span>
                </div>
                <div className="text-xs text-muted-foreground">{c.type} / {c.duration}</div>
                <div className="text-xs text-muted-foreground mt-0.5">{c.outcome}</div>
              </div>
              <Badge variant="outline" className="font-mono text-xs whitespace-nowrap">{c.billed}</Badge>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
