import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Progress } from "@/components/ui/progress";
import {
  Users,
  Clock,
  Calendar,
  GraduationCap,
  AlertTriangle,
  Plus,
  DollarSign,
  CheckCircle,
  XCircle,
  Award,
  FileText,
  Shield,
} from "lucide-react";

const staff = [
  { name: "Dr. Chen", role: "Implantologist", status: "In", clockIn: "7:45 AM", hours: "8.2h", pto: "15d", license: "Dec 2026", licenseWarning: false },
  { name: "Dr. Park", role: "Orthodontist", status: "In", clockIn: "7:50 AM", hours: "8.1h", pto: "12d", license: "Mar 2027", licenseWarning: false },
  { name: "Dr. Okafor", role: "Oral Surgeon", status: "In", clockIn: "8:00 AM", hours: "8.0h", pto: "18d", license: "Jun 2026", licenseWarning: false },
  { name: "Sarah M. RDH", role: "Hygienist", status: "In", clockIn: "7:55 AM", hours: "8.1h", pto: "8d", license: "Apr 2026", licenseWarning: true },
  { name: "Jamie L. RDH", role: "Hyg/Perio", status: "In", clockIn: "8:00 AM", hours: "8.0h", pto: "6d", license: "May 2026", licenseWarning: true },
  { name: "Maria G.", role: "Office Mgr", status: "In", clockIn: "7:30 AM", hours: "8.5h", pto: "10d", license: "\u2014" },
  { name: "Tom R.", role: "Front Desk", status: "Off", clockIn: "\u2014", hours: "\u2014", pto: "5d", license: "\u2014" },
];

const ptoRequests = [
  { id: 1, name: "Sarah M. RDH", type: "Vacation", dates: "Mar 10\u201314, 2026", days: 5, status: "Pending", reason: "Family vacation" },
  { id: 2, name: "Tom R.", type: "Personal", dates: "Feb 20, 2026", days: 1, status: "Pending", reason: "Personal appointment" },
  { id: 3, name: "Dr. Park", type: "Conference", dates: "Apr 5\u20137, 2026", days: 3, status: "Approved", reason: "AAO Annual Session" },
];

const certifications = [
  { name: "Sarah M. RDH", cert: "RDH License", state: "CA", expires: "Apr 2026", ceHours: "12/24", status: "expiring" },
  { name: "Jamie L. RDH", cert: "RDH License", state: "CA", expires: "May 2026", ceHours: "8/24", status: "expiring" },
  { name: "Dr. Chen", cert: "DDS License", state: "CA", expires: "Dec 2026", ceHours: "20/50", status: "current" },
  { name: "Dr. Park", cert: "DMD License", state: "CA", expires: "Mar 2027", ceHours: "35/50", status: "current" },
  { name: "Dr. Okafor", cert: "DDS License", state: "CA", expires: "Jun 2026", ceHours: "30/50", status: "current" },
  { name: "All Providers", cert: "CPR/BLS", state: "\u2014", expires: "Aug 2026", ceHours: "\u2014", status: "current" },
  { name: "All Staff", cert: "OSHA Training", state: "\u2014", expires: "Jan 2027", ceHours: "\u2014", status: "current" },
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

      <Tabs defaultValue="directory" className="space-y-4">
        <TabsList data-testid="tabs-hr">
          <TabsTrigger value="directory" data-testid="tab-directory">
            <Users className="mr-1.5 h-3.5 w-3.5" />
            Staff Directory
          </TabsTrigger>
          <TabsTrigger value="timeclock" data-testid="tab-timeclock">
            <Clock className="mr-1.5 h-3.5 w-3.5" />
            Time Clock
          </TabsTrigger>
          <TabsTrigger value="pto" data-testid="tab-pto">
            <Calendar className="mr-1.5 h-3.5 w-3.5" />
            PTO
          </TabsTrigger>
          <TabsTrigger value="certifications" data-testid="tab-certifications">
            <Award className="mr-1.5 h-3.5 w-3.5" />
            Certifications
          </TabsTrigger>
        </TabsList>

        <TabsContent value="directory">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between gap-4">
              <CardTitle className="flex items-center gap-2">
                <Users className="h-4 w-4" />
                Staff Directory
              </CardTitle>
              <Button variant="outline" data-testid="button-add-staff">
                <Plus className="mr-2 h-4 w-4" />
                Add Staff
              </Button>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Role</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Clock In</TableHead>
                      <TableHead>Hours</TableHead>
                      <TableHead>PTO Balance</TableHead>
                      <TableHead>License Expiry</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {staff.map((s, i) => (
                      <TableRow key={i} data-testid={`staff-row-${i}`}>
                        <TableCell className="font-bold" data-testid={`staff-name-${i}`}>{s.name}</TableCell>
                        <TableCell className="text-muted-foreground">{s.role}</TableCell>
                        <TableCell>
                          <Badge variant={s.status === "In" ? "default" : "outline"} data-testid={`staff-status-${i}`}>
                            {s.status}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-muted-foreground">{s.clockIn}</TableCell>
                        <TableCell className="font-mono">{s.hours}</TableCell>
                        <TableCell data-testid={`staff-pto-${i}`}>{s.pto}</TableCell>
                        <TableCell>
                          <span className={s.licenseWarning ? "font-bold text-destructive" : "text-muted-foreground"} data-testid={`staff-license-${i}`}>
                            {s.license}
                            {s.licenseWarning && <AlertTriangle className="inline ml-1 h-3 w-3" />}
                          </span>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="timeclock">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Clock className="h-4 w-4" />
                Time Clock \u2014 Today
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <Card>
                  <CardContent className="pt-6">
                    <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Total Hours Today</div>
                    <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-total-hours">56.9h</div>
                    <p className="text-xs text-muted-foreground">Across 6 staff</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-6">
                    <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Overtime This Week</div>
                    <div className="mt-1 text-2xl font-bold font-mono text-yellow-600 dark:text-yellow-400" data-testid="kpi-overtime">2.3h</div>
                    <p className="text-xs text-muted-foreground">Maria G. \u2014 8.5h today</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-6">
                    <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Avg Clock-In</div>
                    <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-avg-clockin">7:50 AM</div>
                    <p className="text-xs text-muted-foreground">Target: 8:00 AM</p>
                  </CardContent>
                </Card>
              </div>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Employee</TableHead>
                      <TableHead>Clock In</TableHead>
                      <TableHead>Clock Out</TableHead>
                      <TableHead>Break</TableHead>
                      <TableHead>Total Hours</TableHead>
                      <TableHead>Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {staff.filter(s => s.status === "In").map((s, i) => (
                      <TableRow key={i} data-testid={`timeclock-row-${i}`}>
                        <TableCell className="font-bold">{s.name}</TableCell>
                        <TableCell className="font-mono">{s.clockIn}</TableCell>
                        <TableCell className="text-muted-foreground">\u2014</TableCell>
                        <TableCell className="text-muted-foreground">30 min</TableCell>
                        <TableCell className="font-mono">{s.hours}</TableCell>
                        <TableCell>
                          <Badge variant="default">
                            <Clock className="mr-1 h-3 w-3" />
                            Active
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                    <TableRow data-testid="timeclock-row-off">
                      <TableCell className="font-bold">Tom R.</TableCell>
                      <TableCell className="text-muted-foreground">\u2014</TableCell>
                      <TableCell className="text-muted-foreground">\u2014</TableCell>
                      <TableCell className="text-muted-foreground">\u2014</TableCell>
                      <TableCell className="text-muted-foreground">\u2014</TableCell>
                      <TableCell>
                        <Badge variant="outline">Off</Badge>
                      </TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="pto">
          <div className="space-y-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between gap-4">
                <CardTitle className="flex items-center gap-2">
                  <Calendar className="h-4 w-4" />
                  PTO Requests
                </CardTitle>
                <Button variant="outline" data-testid="button-new-pto">
                  <Plus className="mr-2 h-4 w-4" />
                  New Request
                </Button>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Employee</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Dates</TableHead>
                        <TableHead>Days</TableHead>
                        <TableHead>Reason</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {ptoRequests.map((req) => (
                        <TableRow key={req.id} data-testid={`pto-row-${req.id}`}>
                          <TableCell className="font-bold" data-testid={`pto-name-${req.id}`}>{req.name}</TableCell>
                          <TableCell>
                            <Badge variant="outline">{req.type}</Badge>
                          </TableCell>
                          <TableCell className="text-muted-foreground" data-testid={`pto-dates-${req.id}`}>{req.dates}</TableCell>
                          <TableCell className="font-mono">{req.days}</TableCell>
                          <TableCell className="text-muted-foreground">{req.reason}</TableCell>
                          <TableCell>
                            <Badge
                              variant={req.status === "Approved" ? "default" : "outline"}
                              data-testid={`pto-status-${req.id}`}
                            >
                              {req.status === "Approved" ? (
                                <CheckCircle className="mr-1 h-3 w-3" />
                              ) : (
                                <Clock className="mr-1 h-3 w-3" />
                              )}
                              {req.status}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            {req.status === "Pending" ? (
                              <div className="flex gap-2">
                                <Button size="sm" data-testid={`button-approve-pto-${req.id}`}>
                                  <CheckCircle className="mr-1 h-3 w-3" />
                                  Approve
                                </Button>
                                <Button size="sm" variant="outline" data-testid={`button-deny-pto-${req.id}`}>
                                  <XCircle className="mr-1 h-3 w-3" />
                                  Deny
                                </Button>
                              </div>
                            ) : (
                              <span className="text-xs text-muted-foreground">\u2014</span>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FileText className="h-4 w-4" />
                  PTO Balances
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Employee</TableHead>
                        <TableHead>Total Days</TableHead>
                        <TableHead>Used</TableHead>
                        <TableHead>Remaining</TableHead>
                        <TableHead>Usage</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {[
                        { name: "Dr. Chen", total: 20, used: 5, remaining: 15 },
                        { name: "Dr. Park", total: 20, used: 8, remaining: 12 },
                        { name: "Dr. Okafor", total: 20, used: 2, remaining: 18 },
                        { name: "Sarah M. RDH", total: 15, used: 7, remaining: 8 },
                        { name: "Jamie L. RDH", total: 15, used: 9, remaining: 6 },
                        { name: "Maria G.", total: 15, used: 5, remaining: 10 },
                        { name: "Tom R.", total: 10, used: 5, remaining: 5 },
                      ].map((emp, i) => (
                        <TableRow key={i} data-testid={`pto-balance-row-${i}`}>
                          <TableCell className="font-bold">{emp.name}</TableCell>
                          <TableCell className="font-mono">{emp.total}d</TableCell>
                          <TableCell className="font-mono">{emp.used}d</TableCell>
                          <TableCell className="font-mono" data-testid={`pto-remaining-${i}`}>{emp.remaining}d</TableCell>
                          <TableCell className="w-32">
                            <Progress value={(emp.used / emp.total) * 100} className="h-2" />
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="certifications">
          <div className="space-y-4">
            <Alert variant="destructive" data-testid="alert-ce-expiring">
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>
                2 staff members have licenses expiring within 90 days. Sarah M. RDH (Apr 2026) and Jamie L. RDH (May 2026) need CE hours completed.
              </AlertDescription>
            </Alert>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between gap-4">
                <CardTitle className="flex items-center gap-2">
                  <Shield className="h-4 w-4" />
                  License & CE Tracking
                </CardTitle>
                <Button variant="outline" data-testid="button-add-cert">
                  <Plus className="mr-2 h-4 w-4" />
                  Add Certification
                </Button>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Staff Member</TableHead>
                        <TableHead>Certification</TableHead>
                        <TableHead>State</TableHead>
                        <TableHead>Expires</TableHead>
                        <TableHead>CE Hours</TableHead>
                        <TableHead>Status</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {certifications.map((cert, i) => (
                        <TableRow key={i} data-testid={`cert-row-${i}`}>
                          <TableCell className="font-bold" data-testid={`cert-name-${i}`}>{cert.name}</TableCell>
                          <TableCell>{cert.cert}</TableCell>
                          <TableCell className="text-muted-foreground">{cert.state}</TableCell>
                          <TableCell data-testid={`cert-expires-${i}`}>
                            <span className={cert.status === "expiring" ? "font-bold text-destructive" : "text-muted-foreground"}>
                              {cert.expires}
                              {cert.status === "expiring" && <AlertTriangle className="inline ml-1 h-3 w-3" />}
                            </span>
                          </TableCell>
                          <TableCell>
                            {cert.ceHours !== "\u2014" ? (
                              <div className="space-y-1">
                                <span className="text-sm font-mono">{cert.ceHours}</span>
                                <Progress
                                  value={(parseInt(cert.ceHours.split("/")[0]) / parseInt(cert.ceHours.split("/")[1])) * 100}
                                  className="h-1.5"
                                />
                              </div>
                            ) : (
                              <span className="text-muted-foreground">\u2014</span>
                            )}
                          </TableCell>
                          <TableCell>
                            <Badge
                              variant={cert.status === "expiring" ? "destructive" : "default"}
                              data-testid={`cert-status-${i}`}
                            >
                              {cert.status === "expiring" ? (
                                <AlertTriangle className="mr-1 h-3 w-3" />
                              ) : (
                                <CheckCircle className="mr-1 h-3 w-3" />
                              )}
                              {cert.status === "expiring" ? "Expiring" : "Current"}
                            </Badge>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
