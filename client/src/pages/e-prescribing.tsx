import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Pill,
  Send,
  AlertTriangle,
  CheckCircle,
  Clock,
  Search,
  Plus,
  FileText,
  ShieldCheck,
  RefreshCcw,
  User,
} from "lucide-react";

const recentPrescriptions = [
  { patient: "Margaret Sullivan", med: "Amoxicillin 500mg", sig: "1 cap TID x 7 days", pharmacy: "CVS Auburn", status: "sent", provider: "Dr. Chen" },
  { patient: "Robert Kim", med: "Ibuprofen 600mg", sig: "1 tab Q6H PRN pain", pharmacy: "Walgreens", status: "sent", provider: "Dr. Chen" },
  { patient: "James Okafor", med: "Chlorhexidine 0.12%", sig: "Rinse BID x 2 weeks", pharmacy: "CVS Auburn", status: "pending", provider: "Dr. Park" },
  { patient: "Diana Patel", med: "Acetaminophen/Codeine #3", sig: "1-2 tabs Q4-6H PRN", pharmacy: "Rite Aid", status: "sent", provider: "Dr. Okafor" },
  { patient: "Tom Davis", med: "Clindamycin 300mg", sig: "1 cap QID x 10 days", pharmacy: "CVS Roseville", status: "pending", provider: "Dr. Chen" },
];

const drugAlerts = [
  { patient: "Diana Patel", alert: "Codeine — check allergy: listed sulfa allergy (no contraindication)", level: "info" },
  { patient: "Tom Davis", alert: "Clindamycin — C. diff risk. Consider Amoxicillin if not PCN allergic", level: "warning" },
  { patient: "James Okafor", alert: "Chlorhexidine — avoid eating/drinking 30 min after use", level: "info" },
];

const favoriteRx = [
  { med: "Amoxicillin 500mg", sig: "#21 / 1 TID x 7d", use: "Post-surgical prophylaxis" },
  { med: "Ibuprofen 600mg", sig: "#20 / 1 Q6H PRN", use: "Post-op pain" },
  { med: "Chlorhexidine 0.12%", sig: "473mL / BID x 14d", use: "Perio/surgical rinse" },
  { med: "Acetaminophen/Codeine #3", sig: "#16 / 1-2 Q4-6H PRN", use: "Moderate-severe pain" },
  { med: "Dexamethasone 4mg", sig: "#3 / Medrol dose pack", use: "Post-surgical swelling" },
  { med: "Metronidazole 500mg", sig: "#21 / 1 TID x 7d", use: "Anaerobic infections" },
];

export default function EPrescribingPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">
            E-Prescribing
          </h1>
          <p className="text-sm text-muted-foreground">
            EPCS-certified electronic prescriptions with drug interaction checking
          </p>
        </div>
        <Button data-testid="button-new-rx">
          <Plus className="mr-2 h-4 w-4" />
          New Prescription
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Pill className="h-3.5 w-3.5" />
              Rx Today
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-rx-today">8</div>
            <p className="text-xs font-medium text-emerald-600 dark:text-emerald-400">All EPCS verified</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Send className="h-3.5 w-3.5" />
              E-Sent
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="kpi-e-sent">6</div>
            <p className="text-xs font-medium text-muted-foreground">2 pending approval</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <AlertTriangle className="h-3.5 w-3.5" />
              Drug Alerts
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-yellow-600 dark:text-yellow-400" data-testid="kpi-alerts">3</div>
            <p className="text-xs font-medium text-muted-foreground">1 interaction, 2 info</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <RefreshCcw className="h-3.5 w-3.5" />
              Refill Requests
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-refills">2</div>
            <p className="text-xs font-medium text-muted-foreground">Awaiting provider review</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="h-4 w-4" />
              Recent Prescriptions
            </CardTitle>
          </CardHeader>
          <CardContent>
            {recentPrescriptions.map((rx, i) => (
              <div
                key={i}
                className="flex items-center justify-between border-b py-3 last:border-0 gap-4"
                data-testid={`rx-${i}`}
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-bold">{rx.patient}</span>
                    <span className="text-xs text-muted-foreground">{rx.provider}</span>
                  </div>
                  <div className="text-xs text-muted-foreground mt-0.5">
                    {rx.med} — {rx.sig}
                  </div>
                  <div className="text-xs text-muted-foreground">{rx.pharmacy}</div>
                </div>
                <Badge variant={rx.status === "sent" ? "default" : "outline"}>
                  {rx.status === "sent" ? (
                    <CheckCircle className="mr-1 h-3 w-3" />
                  ) : (
                    <Clock className="mr-1 h-3 w-3" />
                  )}
                  {rx.status}
                </Badge>
              </div>
            ))}
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-yellow-600 dark:text-yellow-400" />
                Drug Interaction Alerts
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {drugAlerts.map((alert, i) => (
                <div
                  key={i}
                  className={`rounded-md p-3 ${
                    alert.level === "warning"
                      ? "border-l-4 border-yellow-500 bg-yellow-500/5"
                      : "border-l-4 border-blue-500 bg-blue-500/5"
                  }`}
                  data-testid={`drug-alert-${i}`}
                >
                  <div className="text-xs font-bold mb-0.5">{alert.patient}</div>
                  <p className="text-xs text-muted-foreground">{alert.alert}</p>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Pill className="h-4 w-4" />
                Favorite Rx Templates
              </CardTitle>
            </CardHeader>
            <CardContent>
              {favoriteRx.map((rx, i) => (
                <div key={i} className="flex items-center justify-between border-b py-2 last:border-0 gap-4">
                  <div>
                    <div className="text-xs font-bold">{rx.med}</div>
                    <div className="text-[11px] text-muted-foreground">{rx.sig} — {rx.use}</div>
                  </div>
                  <Button size="sm" variant="ghost" data-testid={`button-quick-rx-${i}`}>
                    <Send className="h-3.5 w-3.5" />
                  </Button>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
