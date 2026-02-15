import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  FlaskConical,
  CheckCircle,
  Shield,
  AlertTriangle,
  Calendar,
  Thermometer,
  Clock,
} from "lucide-react";

const autoclaveLogs = Array.from({ length: 8 }, (_, i) => ({
  cycle: i + 1,
  time: `${7 + Math.floor((i + 1) / 2)}:${(i + 1) % 2 === 0 ? "00" : "30"} AM`,
  temp: "270°F",
  duration: "30 min",
  status: "Pass",
}));

const oshaChecklist = [
  { item: "Exposure Control Plan", frequency: "Annual", lastDate: "Jan 2026", status: "current" },
  { item: "Hazard Communication", frequency: "Annual", lastDate: "Jan 2026", status: "current" },
  { item: "Bloodborne Pathogen Training", frequency: "Annual", lastDate: "Dec 2025", status: "current" },
  { item: "Fire Safety Inspection", frequency: "Annual", lastDate: "Nov 2025", status: "current" },
  { item: "Radiation Safety Certificate", frequency: "Biennial", lastDate: "Mar 2024", status: "due_soon" },
  { item: "Emergency Eyewash Testing", frequency: "Weekly", lastDate: "Feb 10", status: "current" },
  { item: "SDS Binder Updated", frequency: "Ongoing", lastDate: "Feb 2026", status: "current" },
];

export default function SterilizationPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">
          Sterilization & OSHA Compliance
        </h1>
        <p className="text-sm text-muted-foreground">
          Autoclave logs, biological indicators, compliance checklists
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <FlaskConical className="h-3.5 w-3.5" />
              Cycles Today
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="kpi-cycles">8</div>
            <p className="text-xs font-medium text-emerald-600 dark:text-emerald-400">All passed</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <CheckCircle className="h-3.5 w-3.5" />
              Last Spore Test
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="kpi-spore">Pass</div>
            <p className="text-xs font-medium text-muted-foreground">Feb 10, 2026</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Shield className="h-3.5 w-3.5" />
              OSHA Compliance
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-osha">98%</div>
            <p className="text-xs font-medium text-yellow-600 dark:text-yellow-400">1 item due</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Thermometer className="h-3.5 w-3.5" />
              Radiation Badges
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-radiation">Current</div>
            <p className="text-xs font-medium text-muted-foreground">Next: Mar 1</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FlaskConical className="h-4 w-4" />
              Today's Autoclave Log
            </CardTitle>
          </CardHeader>
          <CardContent>
            {autoclaveLogs.map((log, i) => (
              <div
                key={i}
                className="flex items-center justify-between border-b py-2.5 last:border-0"
                data-testid={`autoclave-cycle-${log.cycle}`}
              >
                <div className="flex items-center gap-3">
                  <span className="text-sm font-bold">Cycle #{log.cycle}</span>
                  <span className="text-xs text-muted-foreground">{log.time}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-muted-foreground">
                    {log.temp} / {log.duration}
                  </span>
                  <Badge variant="default">
                    <CheckCircle className="mr-1 h-3 w-3" />
                    {log.status}
                  </Badge>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Shield className="h-4 w-4" />
              OSHA Compliance Checklist
            </CardTitle>
          </CardHeader>
          <CardContent>
            {oshaChecklist.map((item, i) => (
              <div
                key={i}
                className="flex items-center justify-between border-b py-2.5 last:border-0 gap-4"
                data-testid={`osha-item-${i}`}
              >
                <div>
                  <div className="text-sm font-bold">{item.item}</div>
                  <div className="text-xs text-muted-foreground">
                    {item.frequency} — Last: {item.lastDate}
                  </div>
                </div>
                <Badge variant={item.status === "current" ? "default" : "outline"}>
                  {item.status === "current" ? (
                    <CheckCircle className="mr-1 h-3 w-3" />
                  ) : (
                    <AlertTriangle className="mr-1 h-3 w-3" />
                  )}
                  {item.status === "current" ? "Current" : "Due Soon"}
                </Badge>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
