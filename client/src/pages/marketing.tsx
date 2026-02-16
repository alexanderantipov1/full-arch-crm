import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Users,
  DollarSign,
  UserPlus,
  Star,
  Megaphone,
  CalendarDays,
  CheckCircle,
  Clock,
  FileEdit,
  Lightbulb,
} from "lucide-react";

const channels = [
  { name: "Google Ads", spend: "$3,200", patients: 14, cpa: "$229", roi: "8.2x" },
  { name: "Meta/Instagram", spend: "$2,100", patients: 8, cpa: "$263", roi: "5.4x" },
  { name: "Google Organic", spend: "$800", patients: 6, cpa: "$133", roi: "12.1x" },
  { name: "Patient Referrals", spend: "$1,500", patients: 6, cpa: "$250", roi: "9.8x" },
  { name: "Direct Mail", spend: "$600", patients: 2, cpa: "$300", roi: "4.2x" },
  { name: "Walk-ins", spend: "$0", patients: 2, cpa: "$0", roi: "\u221E" },
];

const calendar = [
  { day: "Mon", content: "Before/after implant photo", platform: "IG+FB", status: "posted", statusColor: "default" as const },
  { day: "Tue", content: "3 Signs You Need RCT video", platform: "TikTok", status: "scheduled", statusColor: "secondary" as const },
  { day: "Wed", content: "Patient testimonial — Diana P.", platform: "IG+FB", status: "scheduled", statusColor: "secondary" as const },
  { day: "Thu", content: "Blog: Implants vs Bridges", platform: "Website", status: "draft", statusColor: "outline" as const },
  { day: "Fri", content: "Team BTS reel", platform: "IG+TikTok", status: "idea", statusColor: "outline" as const },
];

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case "posted":
      return <CheckCircle className="h-3 w-3 text-emerald-600 dark:text-emerald-400" />;
    case "scheduled":
      return <Clock className="h-3 w-3 text-blue-600 dark:text-blue-400" />;
    case "draft":
      return <FileEdit className="h-3 w-3 text-yellow-600 dark:text-yellow-400" />;
    case "idea":
      return <Lightbulb className="h-3 w-3 text-muted-foreground" />;
    default:
      return null;
  }
}

export default function MarketingPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">
          Marketing Suite
        </h1>
        <p className="text-sm text-muted-foreground">
          Channel performance, content calendar, patient acquisition analytics
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <UserPlus className="h-3.5 w-3.5" />
              New Patients Feb
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-new-patients">38</div>
            <p className="text-xs font-medium text-yellow-600 dark:text-yellow-400">Target: 45</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <DollarSign className="h-3.5 w-3.5" />
              Marketing Spend
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-marketing-spend">$8,200</div>
            <p className="text-xs font-medium text-muted-foreground">4.1% of revenue</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Users className="h-3.5 w-3.5" />
              Cost/Patient
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="kpi-cost-patient">$216</div>
            <p className="text-xs font-medium text-emerald-600 dark:text-emerald-400">Target: &lt;$300</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Star className="h-3.5 w-3.5" />
              Google Rating
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-yellow-600 dark:text-yellow-400" data-testid="kpi-google-rating">4.9</div>
            <p className="text-xs font-medium text-muted-foreground">234 reviews</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Megaphone className="h-4 w-4" />
              Channel Performance
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-xs font-bold uppercase tracking-wider text-muted-foreground">
                    <th className="pb-3 pr-4">Channel</th>
                    <th className="pb-3 pr-4">Spend</th>
                    <th className="pb-3 pr-4">Patients</th>
                    <th className="pb-3 pr-4">CPA</th>
                    <th className="pb-3">ROI</th>
                  </tr>
                </thead>
                <tbody>
                  {channels.map((c, i) => (
                    <tr key={i} className="border-b last:border-0" data-testid={`channel-row-${i}`}>
                      <td className="py-3 pr-4 font-medium">{c.name}</td>
                      <td className="py-3 pr-4 font-mono">{c.spend}</td>
                      <td className="py-3 pr-4 font-mono font-bold">{c.patients}</td>
                      <td className="py-3 pr-4 font-mono">{c.cpa}</td>
                      <td className="py-3 font-mono font-bold text-emerald-600 dark:text-emerald-400">{c.roi}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <CalendarDays className="h-4 w-4" />
              Content Calendar
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {calendar.map((item, i) => (
                <div
                  key={i}
                  className={`border-l-2 pl-3 py-2 ${
                    item.status === "posted"
                      ? "border-emerald-500"
                      : item.status === "scheduled"
                        ? "border-blue-500"
                        : item.status === "draft"
                          ? "border-yellow-500"
                          : "border-muted-foreground/30"
                  }`}
                  data-testid={`calendar-item-${i}`}
                >
                  <div className="flex items-start justify-between gap-2 flex-wrap">
                    <div>
                      <span className="text-xs font-bold uppercase text-muted-foreground mr-2">{item.day}</span>
                      <span className="text-sm">{item.content}</span>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <Badge variant="outline" className="text-xs" data-testid={`calendar-platform-${i}`}>
                        {item.platform}
                      </Badge>
                      <Badge variant={item.statusColor} className="text-xs" data-testid={`calendar-status-${i}`}>
                        <StatusIcon status={item.status} />
                        <span className="ml-1">{item.status}</span>
                      </Badge>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
