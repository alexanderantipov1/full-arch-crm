import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Users,
  Clock,
  Calendar,
  GraduationCap,
  AlertTriangle,
  Plus,
  User,
  DollarSign,
} from "lucide-react";

const staff = [
  { name: "Dr. Chen", role: "Implantologist", status: "In", clockIn: "7:45 AM", hours: "8.2h", pto: "15d", license: "Dec 2026" },
  { name: "Dr. Park", role: "Orthodontist", status: "In", clockIn: "7:50 AM", hours: "8.1h", pto: "12d", license: "Mar 2027" },
  { name: "Dr. Okafor", role: "Oral Surgeon", status: "In", clockIn: "8:00 AM", hours: "8.0h", pto: "18d", license: "Jun 2026" },
  { name: "Sarah M. RDH", role: "Hygienist", status: "In", clockIn: "7:55 AM", hours: "8.1h", pto: "8d", license: "Apr 2026", licenseWarning: true },
  { name: "Jamie L. RDH", role: "Hyg/Perio", status: "In", clockIn: "8:00 AM", hours: "8.0h", pto: "6d", license: "May 2026", licenseWarning: true },
  { name: "Maria G.", role: "Office Mgr", status: "In", clockIn: "7:30 AM", hours: "8.5h", pto: "10d", license: "—" },
  { name: "Tom R.", role: "Front Desk", status: "Off", clockIn: "—", hours: "—", pto: "5d", license: "—" },
];

export default function HRPayrollPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">
            HR & Employee Management
          </h1>
          <p className="text-sm text-muted-foreground">
            Time clock, PTO, scheduling, payroll, CE tracking, license alerts
          </p>
        </div>
        <Button data-testid="button-run-payroll">
          <DollarSign className="mr-2 h-4 w-4" />
          Run Payroll
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Users className="h-3.5 w-3.5" />
              Total Staff
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-total-staff">14</div>
            <p className="text-xs font-medium text-muted-foreground">3 providers, 11 team</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Clock className="h-3.5 w-3.5" />
              Clocked In
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="kpi-clocked-in">12</div>
            <p className="text-xs font-medium text-muted-foreground">2 off today</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Calendar className="h-3.5 w-3.5" />
              PTO Requests
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-yellow-600 dark:text-yellow-400" data-testid="kpi-pto">3</div>
            <p className="text-xs font-medium text-muted-foreground">2 pending approval</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <GraduationCap className="h-3.5 w-3.5" />
              CE Expiring &lt;90d
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-destructive" data-testid="kpi-ce-expiring">2</div>
            <p className="text-xs font-medium text-muted-foreground">Sarah M, Jamie L</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="h-4 w-4" />
            Staff Roster
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs font-bold uppercase tracking-wider text-muted-foreground">
                  <th className="pb-3 pr-4">Name</th>
                  <th className="pb-3 pr-4">Role</th>
                  <th className="pb-3 pr-4">Status</th>
                  <th className="pb-3 pr-4">Clock In</th>
                  <th className="pb-3 pr-4">Hours</th>
                  <th className="pb-3 pr-4">PTO Bal</th>
                  <th className="pb-3">License Exp</th>
                </tr>
              </thead>
              <tbody>
                {staff.map((s, i) => (
                  <tr key={i} className="border-b last:border-0" data-testid={`staff-row-${i}`}>
                    <td className="py-3 pr-4 font-bold">{s.name}</td>
                    <td className="py-3 pr-4 text-muted-foreground">{s.role}</td>
                    <td className="py-3 pr-4">
                      <Badge variant={s.status === "In" ? "default" : "outline"}>{s.status}</Badge>
                    </td>
                    <td className="py-3 pr-4 text-muted-foreground">{s.clockIn}</td>
                    <td className="py-3 pr-4 font-mono">{s.hours}</td>
                    <td className="py-3 pr-4">{s.pto}</td>
                    <td className="py-3">
                      <span className={s.licenseWarning ? "font-bold text-destructive" : "text-muted-foreground"}>
                        {s.license}
                        {s.licenseWarning && <AlertTriangle className="inline ml-1 h-3 w-3" />}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
