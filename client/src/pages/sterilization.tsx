import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Progress } from "@/components/ui/progress";
import {
  FlaskConical,
  CheckCircle,
  Shield,
  AlertTriangle,
  Thermometer,
  Clock,
  FileText,
  Plus,
  Activity,
  ClipboardCheck,
  XCircle,
} from "lucide-react";

const autoclaveLogs = [
  { cycle: 1842, date: "Feb 14, 2026", time: "7:30 AM", loadType: "General Instruments", temp: "273\u00b0F", pressure: "30 PSI", duration: "30 min", operator: "Sarah M.", result: "Pass" },
  { cycle: 1843, date: "Feb 14, 2026", time: "8:15 AM", loadType: "Surgical Packs", temp: "275\u00b0F", pressure: "30 PSI", duration: "30 min", operator: "Sarah M.", result: "Pass" },
  { cycle: 1844, date: "Feb 14, 2026", time: "9:00 AM", loadType: "Handpieces", temp: "270\u00b0F", pressure: "28 PSI", duration: "20 min", operator: "Jamie L.", result: "Pass" },
  { cycle: 1845, date: "Feb 14, 2026", time: "10:00 AM", loadType: "Implant Kits", temp: "273\u00b0F", pressure: "30 PSI", duration: "30 min", operator: "Sarah M.", result: "Pass" },
  { cycle: 1846, date: "Feb 14, 2026", time: "11:00 AM", loadType: "General Instruments", temp: "273\u00b0F", pressure: "30 PSI", duration: "30 min", operator: "Jamie L.", result: "Pass" },
  { cycle: 1847, date: "Feb 14, 2026", time: "1:00 PM", loadType: "Hygiene Instruments", temp: "270\u00b0F", pressure: "28 PSI", duration: "20 min", operator: "Sarah M.", result: "Pass" },
  { cycle: 1848, date: "Feb 14, 2026", time: "2:30 PM", loadType: "Surgical Packs", temp: "275\u00b0F", pressure: "30 PSI", duration: "30 min", operator: "Jamie L.", result: "Pass" },
  { cycle: 1849, date: "Feb 14, 2026", time: "3:45 PM", loadType: "General Instruments", temp: "273\u00b0F", pressure: "30 PSI", duration: "30 min", operator: "Sarah M.", result: "Pass" },
];

const sporeTests = [
  { id: 1, date: "Feb 10, 2026", autoclaveId: "AC-001", indicator: "Geobacillus stearothermophilus", incubation: "48 hrs", result: "Pass", nextDue: "Feb 17, 2026" },
  { id: 2, date: "Feb 10, 2026", autoclaveId: "AC-002", indicator: "Geobacillus stearothermophilus", incubation: "48 hrs", result: "Pass", nextDue: "Feb 17, 2026" },
  { id: 3, date: "Feb 3, 2026", autoclaveId: "AC-001", indicator: "Geobacillus stearothermophilus", incubation: "48 hrs", result: "Pass", nextDue: "\u2014" },
  { id: 4, date: "Feb 3, 2026", autoclaveId: "AC-002", indicator: "Geobacillus stearothermophilus", incubation: "48 hrs", result: "Pass", nextDue: "\u2014" },
  { id: 5, date: "Jan 27, 2026", autoclaveId: "AC-001", indicator: "Geobacillus stearothermophilus", incubation: "48 hrs", result: "Pass", nextDue: "\u2014" },
  { id: 6, date: "Jan 27, 2026", autoclaveId: "AC-002", indicator: "Geobacillus stearothermophilus", incubation: "48 hrs", result: "Pass", nextDue: "\u2014" },
];

const complianceChecklist = [
  { id: 1, task: "Morning Sterilization Check", frequency: "Daily", lastCompleted: "Feb 14, 2026", status: "Complete", category: "daily" },
  { id: 2, task: "Autoclave Temp Verification", frequency: "Daily", lastCompleted: "Feb 14, 2026", status: "Complete", category: "daily" },
  { id: 3, task: "Chemical Indicator Review", frequency: "Daily", lastCompleted: "Feb 14, 2026", status: "Complete", category: "daily" },
  { id: 4, task: "Instrument Packaging Inspection", frequency: "Daily", lastCompleted: "Feb 14, 2026", status: "Complete", category: "daily" },
  { id: 5, task: "Spore Test (Biological)", frequency: "Weekly", lastCompleted: "Feb 10, 2026", status: "Complete", category: "weekly" },
  { id: 6, task: "Emergency Eyewash Test", frequency: "Weekly", lastCompleted: "Feb 10, 2026", status: "Complete", category: "weekly" },
  { id: 7, task: "Sharps Container Check", frequency: "Weekly", lastCompleted: "Feb 10, 2026", status: "Complete", category: "weekly" },
  { id: 8, task: "Autoclave Maintenance Log", frequency: "Monthly", lastCompleted: "Feb 1, 2026", status: "Complete", category: "monthly" },
  { id: 9, task: "Exposure Control Plan Review", frequency: "Annual", lastCompleted: "Jan 2026", status: "Complete", category: "annual" },
  { id: 10, task: "Bloodborne Pathogen Training", frequency: "Annual", lastCompleted: "Dec 2025", status: "Complete", category: "annual" },
  { id: 11, task: "Hazard Communication Update", frequency: "Annual", lastCompleted: "Jan 2026", status: "Complete", category: "annual" },
  { id: 12, task: "Radiation Safety Certificate", frequency: "Biennial", lastCompleted: "Mar 2024", status: "Due", category: "annual" },
];

export default function SterilizationPage() {
  const [checkedItems, setCheckedItems] = useState<Set<number>>(
    new Set(complianceChecklist.filter(c => c.status === "Complete").map(c => c.id))
  );

  const toggleCheck = (id: number) => {
    setCheckedItems(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const completedCount = checkedItems.size;
  const totalCount = complianceChecklist.length;
  const compliancePercent = Math.round((completedCount / totalCount) * 100);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">
            Sterilization & OSHA Compliance
          </h1>
          <p className="text-sm text-muted-foreground">
            Autoclave logs, biological indicators, compliance checklists
          </p>
        </div>
        <Button data-testid="button-new-cycle">
          <Plus className="mr-2 h-4 w-4" />
          Log Cycle
        </Button>
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
              <Activity className="h-3.5 w-3.5" />
              Pass Rate
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="kpi-pass-rate">100%</div>
            <p className="text-xs font-medium text-muted-foreground">8/8 cycles today</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <CheckCircle className="h-3.5 w-3.5" />
              Spore Tests
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="kpi-spore">Pass</div>
            <p className="text-xs font-medium text-muted-foreground">Weekly \u2014 Last: Feb 10</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Shield className="h-3.5 w-3.5" />
              OSHA Compliance
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-osha">100%</div>
            <p className="text-xs font-medium text-emerald-600 dark:text-emerald-400">All items current</p>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="dashboard" className="space-y-4">
        <TabsList data-testid="tabs-sterilization">
          <TabsTrigger value="dashboard" data-testid="tab-dashboard">
            <Activity className="mr-1.5 h-3.5 w-3.5" />
            Dashboard
          </TabsTrigger>
          <TabsTrigger value="autoclave" data-testid="tab-autoclave">
            <Thermometer className="mr-1.5 h-3.5 w-3.5" />
            Autoclave Logs
          </TabsTrigger>
          <TabsTrigger value="spore" data-testid="tab-spore">
            <FlaskConical className="mr-1.5 h-3.5 w-3.5" />
            Spore Tests
          </TabsTrigger>
          <TabsTrigger value="compliance" data-testid="tab-compliance">
            <ClipboardCheck className="mr-1.5 h-3.5 w-3.5" />
            Compliance Checklist
          </TabsTrigger>
        </TabsList>

        <TabsContent value="dashboard">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FlaskConical className="h-4 w-4" />
                  Today's Autoclave Log
                </CardTitle>
              </CardHeader>
              <CardContent>
                {autoclaveLogs.map((log) => (
                  <div
                    key={log.cycle}
                    className="flex items-center justify-between border-b py-2.5 last:border-0 gap-4"
                    data-testid={`autoclave-cycle-${log.cycle}`}
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-sm font-bold">#{log.cycle}</span>
                      <span className="text-xs text-muted-foreground">{log.time}</span>
                      <span className="text-xs text-muted-foreground">{log.loadType}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-muted-foreground">
                        {log.temp} / {log.pressure}
                      </span>
                      <Badge variant="default" data-testid={`cycle-result-${log.cycle}`}>
                        <CheckCircle className="mr-1 h-3 w-3" />
                        {log.result}
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
                  Compliance Overview
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Overall Compliance</span>
                    <span className="text-sm font-mono font-bold" data-testid="compliance-percent">{compliancePercent}%</span>
                  </div>
                  <Progress value={compliancePercent} className="h-2" />
                </div>
                <div className="space-y-3">
                  {[
                    { label: "Daily Tasks", count: complianceChecklist.filter(c => c.category === "daily").length, completed: complianceChecklist.filter(c => c.category === "daily" && checkedItems.has(c.id)).length },
                    { label: "Weekly Tasks", count: complianceChecklist.filter(c => c.category === "weekly").length, completed: complianceChecklist.filter(c => c.category === "weekly" && checkedItems.has(c.id)).length },
                    { label: "Monthly Tasks", count: complianceChecklist.filter(c => c.category === "monthly").length, completed: complianceChecklist.filter(c => c.category === "monthly" && checkedItems.has(c.id)).length },
                    { label: "Annual Tasks", count: complianceChecklist.filter(c => c.category === "annual").length, completed: complianceChecklist.filter(c => c.category === "annual" && checkedItems.has(c.id)).length },
                  ].map((group, i) => (
                    <div key={i} className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">{group.label}</span>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-mono">{group.completed}/{group.count}</span>
                        <Badge variant={group.completed === group.count ? "default" : "outline"}>
                          {group.completed === group.count ? (
                            <CheckCircle className="mr-1 h-3 w-3" />
                          ) : (
                            <Clock className="mr-1 h-3 w-3" />
                          )}
                          {group.completed === group.count ? "Complete" : "In Progress"}
                        </Badge>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="space-y-2 pt-2">
                  <div className="text-sm font-medium">Recent Spore Tests</div>
                  {sporeTests.slice(0, 2).map((test) => (
                    <div key={test.id} className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">{test.date} \u2014 {test.autoclaveId}</span>
                      <Badge variant="default">
                        <CheckCircle className="mr-1 h-3 w-3" />
                        {test.result}
                      </Badge>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="autoclave">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between gap-4">
              <CardTitle className="flex items-center gap-2">
                <Thermometer className="h-4 w-4" />
                Autoclave Cycle Log
              </CardTitle>
              <Button variant="outline" data-testid="button-export-logs">
                <FileText className="mr-2 h-4 w-4" />
                Export
              </Button>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Cycle #</TableHead>
                      <TableHead>Date/Time</TableHead>
                      <TableHead>Load Type</TableHead>
                      <TableHead>Temp</TableHead>
                      <TableHead>Pressure</TableHead>
                      <TableHead>Duration</TableHead>
                      <TableHead>Operator</TableHead>
                      <TableHead>Result</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {autoclaveLogs.map((log) => (
                      <TableRow key={log.cycle} data-testid={`autoclave-row-${log.cycle}`}>
                        <TableCell className="font-mono font-bold" data-testid={`cycle-number-${log.cycle}`}>{log.cycle}</TableCell>
                        <TableCell className="text-muted-foreground">
                          <div>{log.date}</div>
                          <div className="text-xs">{log.time}</div>
                        </TableCell>
                        <TableCell>{log.loadType}</TableCell>
                        <TableCell className="font-mono" data-testid={`cycle-temp-${log.cycle}`}>{log.temp}</TableCell>
                        <TableCell className="font-mono" data-testid={`cycle-pressure-${log.cycle}`}>{log.pressure}</TableCell>
                        <TableCell className="text-muted-foreground">{log.duration}</TableCell>
                        <TableCell className="text-muted-foreground">{log.operator}</TableCell>
                        <TableCell>
                          <Badge
                            variant={log.result === "Pass" ? "default" : "destructive"}
                            data-testid={`autoclave-result-${log.cycle}`}
                          >
                            {log.result === "Pass" ? (
                              <CheckCircle className="mr-1 h-3 w-3" />
                            ) : (
                              <XCircle className="mr-1 h-3 w-3" />
                            )}
                            {log.result}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="spore">
          <div className="space-y-4">
            <Alert data-testid="alert-spore-info">
              <FlaskConical className="h-4 w-4" />
              <AlertDescription>
                Biological monitoring (spore testing) is performed weekly on all autoclaves per CDC/OSAP guidelines. Next tests due: Feb 17, 2026.
              </AlertDescription>
            </Alert>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between gap-4">
                <CardTitle className="flex items-center gap-2">
                  <FlaskConical className="h-4 w-4" />
                  Biological Indicator Results
                </CardTitle>
                <Button variant="outline" data-testid="button-log-spore">
                  <Plus className="mr-2 h-4 w-4" />
                  Log Test
                </Button>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Date</TableHead>
                        <TableHead>Autoclave ID</TableHead>
                        <TableHead>Indicator Type</TableHead>
                        <TableHead>Incubation</TableHead>
                        <TableHead>Result</TableHead>
                        <TableHead>Next Due</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {sporeTests.map((test) => (
                        <TableRow key={test.id} data-testid={`spore-row-${test.id}`}>
                          <TableCell className="font-medium" data-testid={`spore-date-${test.id}`}>{test.date}</TableCell>
                          <TableCell className="font-mono" data-testid={`spore-autoclave-${test.id}`}>{test.autoclaveId}</TableCell>
                          <TableCell className="text-muted-foreground text-xs">{test.indicator}</TableCell>
                          <TableCell className="text-muted-foreground">{test.incubation}</TableCell>
                          <TableCell>
                            <Badge
                              variant={test.result === "Pass" ? "default" : "destructive"}
                              data-testid={`spore-result-${test.id}`}
                            >
                              {test.result === "Pass" ? (
                                <CheckCircle className="mr-1 h-3 w-3" />
                              ) : (
                                <XCircle className="mr-1 h-3 w-3" />
                              )}
                              {test.result}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-muted-foreground" data-testid={`spore-next-${test.id}`}>{test.nextDue}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="compliance">
          <div className="space-y-4">
            {complianceChecklist.some(c => c.status === "Due" || c.status === "Overdue") && (
              <Alert variant="destructive" data-testid="alert-compliance-due">
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>
                  {complianceChecklist.filter(c => c.status === "Due" || c.status === "Overdue").length} compliance item(s) require attention. Review and complete overdue tasks immediately.
                </AlertDescription>
              </Alert>
            )}

            <Card>
              <CardHeader className="flex flex-row items-center justify-between gap-4">
                <CardTitle className="flex items-center gap-2">
                  <ClipboardCheck className="h-4 w-4" />
                  OSHA Compliance Checklist
                </CardTitle>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground font-mono" data-testid="compliance-counter">
                    {completedCount}/{totalCount}
                  </span>
                  <Progress value={compliancePercent} className="h-2 w-24" />
                </div>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-12">Done</TableHead>
                        <TableHead>Task</TableHead>
                        <TableHead>Frequency</TableHead>
                        <TableHead>Last Completed</TableHead>
                        <TableHead>Status</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {complianceChecklist.map((item) => (
                        <TableRow key={item.id} data-testid={`compliance-row-${item.id}`}>
                          <TableCell>
                            <Button
                              size="icon"
                              variant={checkedItems.has(item.id) ? "default" : "outline"}
                              data-testid={`button-check-${item.id}`}
                              onClick={() => toggleCheck(item.id)}
                            >
                              {checkedItems.has(item.id) ? (
                                <CheckCircle className="h-4 w-4" />
                              ) : (
                                <XCircle className="h-4 w-4" />
                              )}
                            </Button>
                          </TableCell>
                          <TableCell className="font-medium" data-testid={`compliance-task-${item.id}`}>{item.task}</TableCell>
                          <TableCell>
                            <Badge variant="outline">{item.frequency}</Badge>
                          </TableCell>
                          <TableCell className="text-muted-foreground">{item.lastCompleted}</TableCell>
                          <TableCell>
                            <Badge
                              variant={
                                item.status === "Complete" ? "default" :
                                item.status === "Due" ? "outline" :
                                "destructive"
                              }
                              data-testid={`compliance-status-${item.id}`}
                            >
                              {item.status === "Complete" ? (
                                <CheckCircle className="mr-1 h-3 w-3" />
                              ) : item.status === "Due" ? (
                                <Clock className="mr-1 h-3 w-3" />
                              ) : (
                                <AlertTriangle className="mr-1 h-3 w-3" />
                              )}
                              {item.status}
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
