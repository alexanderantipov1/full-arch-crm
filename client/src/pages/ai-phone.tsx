import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Phone,
  Bot,
  Calendar,
  DollarSign,
  CheckCircle,
  AlertTriangle,
  ArrowUpRight,
  PhoneIncoming,
  PhoneOutgoing,
  PhoneMissed,
  User,
  Settings,
} from "lucide-react";

const callFeed = [
  { time: "2:42 PM", caller: "Maria Garcia (New)", duration: "3:12", type: "AI", action: "Booked NP exam 02/18. Collected insurance (Delta PPO). Sent intake SMS.", status: "resolved", statusColor: "default" as const },
  { time: "2:38 PM", caller: "Diana Patel", duration: "1:45", type: "AI", action: "Confirmed Invisalign check 02/14. Asked about whitening — offered consult.", status: "resolved", statusColor: "default" as const },
  { time: "2:31 PM", caller: "Unknown 916-555-8821", duration: "2:08", type: "AI", action: "Insurance implant question. Explained benefits. Booked free consult.", status: "resolved", statusColor: "default" as const },
  { time: "2:24 PM", caller: "Tom Davis", duration: "0:45", type: "AI", action: "Rx refill request. Flagged for Dr. Chen approval.", status: "escalated", statusColor: "outline" as const },
  { time: "2:18 PM", caller: "Dr. Anderson's Office", duration: "2:30", type: "Staff", action: "Specialist referral — transferred to Maria G.", status: "transferred", statusColor: "secondary" as const },
  { time: "1:55 PM", caller: "Missed 916-555-3344", duration: "—", type: "AI", action: "Auto-callback <2 min. New patient booked 02/20 8AM.", status: "recovered", statusColor: "default" as const },
];

const capabilities = [
  "Answer with practice greeting",
  "Book/reschedule/cancel appointments",
  "Verify insurance on call",
  "Send intake forms via SMS",
  "Answer FAQs (hours, services, pricing)",
  "After-hours emergency triage",
  "Auto-callback missed calls <2min",
  "Reactivation calls to overdue patients",
  "Collections reminder calls",
  "Spanish/Mandarin/Vietnamese",
  "Escalate with full context",
  "Record & transcribe all calls",
];

export default function AIPhonePage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">
          AI Phone & Communication Agent
        </h1>
        <p className="text-sm text-muted-foreground">
          24/7 AI receptionist — answers calls, books appointments, verifies insurance
        </p>
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

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
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
            {callFeed.map((call, i) => (
              <div
                key={i}
                className="rounded-md border-l-4 border-primary/30 bg-muted/30 p-3"
                data-testid={`call-${i}`}
              >
                <div className="flex items-center justify-between mb-1 flex-wrap gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold">{call.caller}</span>
                    <span className="text-[10px] text-muted-foreground">{call.time} / {call.duration}</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Badge variant={call.type === "AI" ? "default" : "outline"} className="text-[10px]">
                      {call.type === "AI" ? <Bot className="mr-1 h-2.5 w-2.5" /> : <User className="mr-1 h-2.5 w-2.5" />}
                      {call.type}
                    </Badge>
                    <Badge variant={call.statusColor} className="text-[10px]">{call.status}</Badge>
                  </div>
                </div>
                <p className="text-xs text-muted-foreground">{call.action}</p>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Bot className="h-4 w-4" />
              AI Agent Capabilities
            </CardTitle>
          </CardHeader>
          <CardContent>
            {capabilities.map((cap, i) => (
              <div key={i} className="flex items-center justify-between border-b py-2.5 last:border-0" data-testid={`capability-${i}`}>
                <span className="text-sm">{cap}</span>
                <Badge variant="default">
                  <CheckCircle className="mr-1 h-3 w-3" />
                  Active
                </Badge>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
