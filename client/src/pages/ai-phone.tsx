import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  Phone,
  Bot,
  Calendar,
  DollarSign,
  CheckCircle,
  PhoneIncoming,
  User,
  Settings,
  BarChart3,
  Clock,
  Globe,
  MessageSquare,
  Shield,
  Mic,
  PhoneForwarded,
  PhoneMissed,
  AlertTriangle,
  Volume2,
} from "lucide-react";

const callFeed = [
  { id: 1, time: "2:42 PM", caller: "Maria Garcia", duration: "3:12", handler: "AI", action: "Booked NP exam 02/18. Collected insurance (Delta PPO). Sent intake SMS.", status: "resolved", tag: "New Patient" },
  { id: 2, time: "2:38 PM", caller: "Diana Patel", duration: "1:45", handler: "AI", action: "Confirmed Invisalign check 02/14. Asked about whitening — offered consult.", status: "resolved", tag: "Follow-up" },
  { id: 3, time: "2:31 PM", caller: "Unknown 916-555-8821", duration: "2:08", handler: "AI", action: "Insurance implant question. Explained benefits. Booked free consult 02/19.", status: "resolved", tag: "Inquiry" },
  { id: 4, time: "2:24 PM", caller: "Tom Davis", duration: "0:45", handler: "AI", action: "Rx refill request. Flagged for Dr. Chen approval.", status: "escalated", tag: "Clinical" },
  { id: 5, time: "2:18 PM", caller: "Dr. Anderson's Office", duration: "2:30", handler: "Staff", action: "Specialist referral coordination — transferred to Maria G.", status: "transferred", tag: "Referral" },
  { id: 6, time: "1:55 PM", caller: "Missed 916-555-3344", duration: "0:00", handler: "AI", action: "Auto-callback <2 min. New patient booked 02/20 8AM.", status: "recovered", tag: "Recovery" },
  { id: 7, time: "1:42 PM", caller: "James Lee", duration: "1:20", handler: "AI", action: "Rescheduled cleaning from 02/15 to 02/22. Confirmed via SMS.", status: "resolved", tag: "Reschedule" },
  { id: 8, time: "1:30 PM", caller: "Karen Brown", duration: "4:15", handler: "Staff", action: "Complex treatment plan discussion. Scheduled in-person consult.", status: "resolved", tag: "Treatment" },
  { id: 9, time: "1:15 PM", caller: "Pete Hall", duration: "1:05", handler: "AI", action: "Post-op check-in call. Patient reports normal healing. No concerns.", status: "resolved", tag: "Post-Op" },
  { id: 10, time: "12:50 PM", caller: "Rosa Martinez", duration: "2:45", handler: "AI", action: "Llamada en espanol. Cita programada 02/21. Formularios enviados por SMS.", status: "resolved", tag: "Spanish" },
];

const capabilities = [
  { name: "Answer with practice greeting", icon: Volume2, desc: "Custom branded greeting with practice name and hours" },
  { name: "Book/reschedule/cancel appointments", icon: Calendar, desc: "Full scheduling access with real-time availability" },
  { name: "Verify insurance on call", icon: Shield, desc: "Live eligibility check during the call" },
  { name: "Send intake forms via SMS", icon: MessageSquare, desc: "Auto-send digital forms after booking" },
  { name: "Answer FAQs (hours, services, pricing)", icon: MessageSquare, desc: "Trained on practice-specific knowledge base" },
  { name: "After-hours emergency triage", icon: AlertTriangle, desc: "Route emergencies to on-call provider" },
  { name: "Auto-callback missed calls <2min", icon: PhoneMissed, desc: "Automatic follow-up on every missed call" },
  { name: "Reactivation calls to overdue patients", icon: PhoneForwarded, desc: "Proactive outreach for patients overdue 6+ months" },
  { name: "Collections reminder calls", icon: DollarSign, desc: "Friendly payment reminders with balance info" },
  { name: "Spanish/Mandarin/Vietnamese support", icon: Globe, desc: "Multilingual AI with native-quality fluency" },
  { name: "Escalate with full context", icon: Phone, desc: "Warm transfer with call summary to staff" },
  { name: "Record & transcribe all calls", icon: Mic, desc: "Full transcription with searchable archive" },
];

const statusConfig: Record<string, { color: string; variant: "default" | "outline" | "secondary" | "destructive" }> = {
  resolved: { color: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400", variant: "default" },
  escalated: { color: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400", variant: "outline" },
  transferred: { color: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400", variant: "secondary" },
  recovered: { color: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400", variant: "default" },
};

const analyticsMetrics = [
  { label: "AI Resolution Rate", value: 84, total: "35 / 42 calls resolved without staff" },
  { label: "First-Call Resolution", value: 91, total: "No callback needed" },
  { label: "Appointment Conversion", value: 72, total: "18 appointments from 25 inquiries" },
  { label: "Patient Satisfaction", value: 94, total: "Based on post-call survey" },
  { label: "Avg Hold Time", value: 8, total: "< 5 seconds (AI answers instantly)" },
  { label: "After-Hours Capture", value: 100, total: "All after-hours calls handled by AI" },
];

const peakHours = [
  { hour: "8 AM", calls: 8, pct: 40 },
  { hour: "9 AM", calls: 12, pct: 60 },
  { hour: "10 AM", calls: 15, pct: 75 },
  { hour: "11 AM", calls: 10, pct: 50 },
  { hour: "12 PM", calls: 6, pct: 30 },
  { hour: "1 PM", calls: 8, pct: 40 },
  { hour: "2 PM", calls: 14, pct: 70 },
  { hour: "3 PM", calls: 11, pct: 55 },
  { hour: "4 PM", calls: 9, pct: 45 },
  { hour: "5 PM", calls: 5, pct: 25 },
];

export default function AIPhonePage() {
  const [activeTab, setActiveTab] = useState("feed");

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">
            AI Phone & Communication Agent
          </h1>
          <p className="text-sm text-muted-foreground">
            24/7 AI receptionist — answers calls, books appointments, verifies insurance
          </p>
        </div>
        <Button data-testid="button-configure-agent">
          <Settings className="h-4 w-4 mr-2" />
          Configure Agent
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Phone className="h-3.5 w-3.5" />
              Calls Today
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-calls">67</div>
            <p className="text-xs font-medium text-muted-foreground">42 AI, 25 staff</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Bot className="h-3.5 w-3.5" />
              AI Resolution
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="kpi-resolution">84%</div>
            <p className="text-xs font-medium text-muted-foreground">No staff needed</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Calendar className="h-3.5 w-3.5" />
              Appts Booked
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-booked">18</div>
            <p className="text-xs font-medium text-muted-foreground">11 AI, 7 staff</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <DollarSign className="h-3.5 w-3.5" />
              Revenue Recovered
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="kpi-revenue">$4,200</div>
            <p className="text-xs font-medium text-muted-foreground">Missed call follow-up</p>
          </CardContent>
        </Card>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList data-testid="tabs-ai-phone">
          <TabsTrigger value="feed" data-testid="tab-live-feed">
            <PhoneIncoming className="h-4 w-4 mr-1.5" />
            Live Feed
          </TabsTrigger>
          <TabsTrigger value="capabilities" data-testid="tab-ai-capabilities">
            <Bot className="h-4 w-4 mr-1.5" />
            AI Capabilities
          </TabsTrigger>
          <TabsTrigger value="analytics" data-testid="tab-call-analytics">
            <BarChart3 className="h-4 w-4 mr-1.5" />
            Call Analytics
          </TabsTrigger>
          <TabsTrigger value="settings" data-testid="tab-settings">
            <Settings className="h-4 w-4 mr-1.5" />
            Settings
          </TabsTrigger>
        </TabsList>

        <TabsContent value="feed">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <PhoneIncoming className="h-4 w-4" />
                Live Call Feed
                <Badge variant="default" className="ml-2">
                  <span className="mr-1 h-1.5 w-1.5 rounded-full bg-white animate-pulse inline-block" />
                  Live
                </Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {callFeed.map((call) => (
                <div
                  key={call.id}
                  className="rounded-md bg-muted/30 p-3"
                  data-testid={`call-${call.id}`}
                >
                  <div className="flex items-center justify-between mb-1 flex-wrap gap-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-bold" data-testid={`call-caller-${call.id}`}>{call.caller}</span>
                      <span className="text-xs text-muted-foreground">{call.time}</span>
                      <span className="text-xs text-muted-foreground">{call.duration}</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <Badge variant="outline" className="text-xs">{call.tag}</Badge>
                      <Badge variant={call.handler === "AI" ? "default" : "outline"} className="text-xs" data-testid={`call-handler-${call.id}`}>
                        {call.handler === "AI" ? <Bot className="mr-1 h-2.5 w-2.5" /> : <User className="mr-1 h-2.5 w-2.5" />}
                        {call.handler}
                      </Badge>
                      <Badge className={statusConfig[call.status]?.color} data-testid={`call-status-${call.id}`}>
                        {call.status}
                      </Badge>
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground" data-testid={`call-action-${call.id}`}>{call.action}</p>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="capabilities">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Bot className="h-4 w-4" />
                AI Agent Capabilities
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-1">
                {capabilities.map((cap, i) => (
                  <div key={i} className="flex items-center justify-between border-b py-3 last:border-0 gap-4" data-testid={`capability-${i}`}>
                    <div className="flex items-center gap-3 min-w-0">
                      <cap.icon className="h-4 w-4 text-primary shrink-0" />
                      <div className="min-w-0">
                        <span className="text-sm font-medium" data-testid={`capability-name-${i}`}>{cap.name}</span>
                        <p className="text-xs text-muted-foreground">{cap.desc}</p>
                      </div>
                    </div>
                    <Badge variant="default" data-testid={`capability-status-${i}`}>
                      <CheckCircle className="mr-1 h-3 w-3" />
                      Active
                    </Badge>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="analytics">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <BarChart3 className="h-4 w-4" />
                  Performance Metrics
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {analyticsMetrics.map((metric, i) => (
                  <div key={i} data-testid={`metric-${i}`}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm">{metric.label}</span>
                      <span className="text-sm font-mono font-bold">{metric.value}%</span>
                    </div>
                    <Progress value={metric.value} />
                    <p className="text-xs text-muted-foreground mt-0.5">{metric.total}</p>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Clock className="h-4 w-4" />
                  Peak Hours Today
                </CardTitle>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Hour</TableHead>
                      <TableHead>Calls</TableHead>
                      <TableHead>Volume</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {peakHours.map((h, i) => (
                      <TableRow key={i} data-testid={`peak-hour-${i}`}>
                        <TableCell className="font-medium">{h.hour}</TableCell>
                        <TableCell className="font-mono">{h.calls}</TableCell>
                        <TableCell className="w-40">
                          <Progress value={h.pct} />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>

            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Phone className="h-4 w-4" />
                  Call Outcomes Summary
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                  <div className="text-center" data-testid="outcome-resolved">
                    <div className="text-2xl font-bold font-mono">52</div>
                    <p className="text-xs text-muted-foreground">Resolved</p>
                    <Progress value={78} className="mt-2" />
                  </div>
                  <div className="text-center" data-testid="outcome-escalated">
                    <div className="text-2xl font-bold font-mono">6</div>
                    <p className="text-xs text-muted-foreground">Escalated</p>
                    <Progress value={9} className="mt-2" />
                  </div>
                  <div className="text-center" data-testid="outcome-transferred">
                    <div className="text-2xl font-bold font-mono">5</div>
                    <p className="text-xs text-muted-foreground">Transferred</p>
                    <Progress value={7} className="mt-2" />
                  </div>
                  <div className="text-center" data-testid="outcome-recovered">
                    <div className="text-2xl font-bold font-mono">4</div>
                    <p className="text-xs text-muted-foreground">Recovered</p>
                    <Progress value={6} className="mt-2" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="settings">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Settings className="h-4 w-4" />
                  AI Agent Configuration
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between" data-testid="setting-greeting">
                  <div>
                    <p className="text-sm font-medium">Practice Greeting</p>
                    <p className="text-xs text-muted-foreground">"Thank you for calling Dental Excellence..."</p>
                  </div>
                  <Button variant="outline" data-testid="button-edit-greeting">Edit</Button>
                </div>
                <div className="flex items-center justify-between" data-testid="setting-hours">
                  <div>
                    <p className="text-sm font-medium">Business Hours</p>
                    <p className="text-xs text-muted-foreground">Mon-Fri 8AM-5PM, Sat 9AM-1PM</p>
                  </div>
                  <Button variant="outline" data-testid="button-edit-hours">Edit</Button>
                </div>
                <div className="flex items-center justify-between" data-testid="setting-escalation">
                  <div>
                    <p className="text-sm font-medium">Escalation Rules</p>
                    <p className="text-xs text-muted-foreground">Emergency, Rx refills, complex treatment</p>
                  </div>
                  <Button variant="outline" data-testid="button-edit-escalation">Edit</Button>
                </div>
                <div className="flex items-center justify-between" data-testid="setting-callback">
                  <div>
                    <p className="text-sm font-medium">Auto-Callback Delay</p>
                    <p className="text-xs text-muted-foreground">2 minutes after missed call</p>
                  </div>
                  <Button variant="outline" data-testid="button-edit-callback">Edit</Button>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Globe className="h-4 w-4" />
                  Language & Integrations
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div data-testid="setting-languages">
                  <p className="text-sm font-medium mb-2">Active Languages</p>
                  <div className="flex items-center gap-2 flex-wrap">
                    <Badge variant="default">English</Badge>
                    <Badge variant="default">Spanish</Badge>
                    <Badge variant="default">Mandarin</Badge>
                    <Badge variant="default">Vietnamese</Badge>
                    <Button variant="outline" size="sm" data-testid="button-add-language">Add</Button>
                  </div>
                </div>
                <div data-testid="setting-integrations">
                  <p className="text-sm font-medium mb-2">Connected Systems</p>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">PMS / Scheduling</span>
                      <Badge variant="default"><CheckCircle className="mr-1 h-3 w-3" />Connected</Badge>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Insurance Verification</span>
                      <Badge variant="default"><CheckCircle className="mr-1 h-3 w-3" />Connected</Badge>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">SMS / Messaging</span>
                      <Badge variant="default"><CheckCircle className="mr-1 h-3 w-3" />Connected</Badge>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">VoIP Provider</span>
                      <Badge variant="default"><CheckCircle className="mr-1 h-3 w-3" />Connected</Badge>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
