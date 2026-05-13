import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  DollarSign,
  TrendingUp,
  Percent,
  CreditCard,
  FileSpreadsheet,
  PieChart,
  Receipt,
  FlaskConical,
  CheckCircle2,
  Clock,
  Printer,
} from "lucide-react";
import { printPaymentReceipt } from "@/lib/receipt";

interface StripePayment {
  id: number;
  patientId: number;
  patientName: string | null;
  stripePaymentIntentId: string;
  amount: number;
  currency: string;
  status: string;
  description: string | null;
  receiptEmail: string | null;
  testMode: boolean;
  createdAt: string;
}

const plLines = [
  { label: "Production (Gross)", value: "$206,400", pct: null, bold: false, separator: false },
  { label: "Adjustments", value: "($7,200)", pct: "3.5%", bold: false, separator: false },
  { label: "Net Production", value: "$199,200", pct: null, bold: true, separator: true },
  { label: "Collections", value: "$198,240", pct: "99.5%", bold: true, separator: true },
  { label: "Staff Costs", value: "($52,800)", pct: "26.6%", bold: false, separator: false },
  { label: "Facility", value: "($14,400)", pct: "7.3%", bold: false, separator: false },
  { label: "Supplies & Lab", value: "($25,600)", pct: "12.9%", bold: false, separator: false },
  { label: "Marketing", value: "($8,200)", pct: "4.1%", bold: false, separator: false },
  { label: "Admin & Other", value: "($12,800)", pct: "6.5%", bold: false, separator: false },
  { label: "Total Overhead", value: "($113,800)", pct: "57.3%", bold: true, separator: true },
  { label: "NET INCOME", value: "$84,440", pct: "42.6%", bold: true, separator: false },
];

const overheadItems = [
  { label: "Staff (salaries + benefits)", value: 26.6, target: 28, over: false },
  { label: "Supplies & Lab", value: 12.9, target: 14, over: false },
  { label: "Facility (rent + utilities)", value: 7.3, target: 8, over: false },
  { label: "Admin & Technology", value: 6.5, target: 4, over: true },
  { label: "Marketing", value: 4.1, target: 5, over: false },
];

function PaymentActivityFeed() {
  const { data: payments = [], isLoading } = useQuery<StripePayment[]>({
    queryKey: ["/api/payments/history"],
  });

  const totalCollected = payments
    .filter(p => p.status === "succeeded")
    .reduce((acc, p) => acc + p.amount / 100, 0);

  const todayPayments = payments.filter(p => {
    const d = new Date(p.createdAt);
    const now = new Date();
    return d.toDateString() === now.toDateString();
  });

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card>
          <CardContent className="pt-5">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1">
              <CreditCard className="h-3.5 w-3.5" />
              Total Collected
            </div>
            <div className="text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="kpi-total-collected">
              ${totalCollected.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <p className="text-xs text-muted-foreground">{payments.filter(p => p.status === "succeeded").length} transactions</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-5">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1">
              <Clock className="h-3.5 w-3.5" />
              Today
            </div>
            <div className="text-2xl font-bold font-mono" data-testid="kpi-today-payments">
              {todayPayments.length}
            </div>
            <p className="text-xs text-muted-foreground">payment{todayPayments.length !== 1 ? "s" : ""} processed</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-5">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1">
              <Receipt className="h-3.5 w-3.5" />
              Transactions
            </div>
            <div className="text-2xl font-bold font-mono" data-testid="kpi-transaction-count">
              {payments.length}
            </div>
            <p className="text-xs text-muted-foreground">all time</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Receipt className="h-4 w-4" />
            Patient Payment Activity
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="text-sm text-muted-foreground text-center py-8">Loading transactions…</div>
          ) : payments.length === 0 ? (
            <div className="text-center py-12">
              <CreditCard className="mx-auto h-10 w-10 text-muted-foreground/30 mb-3" />
              <p className="text-sm font-medium text-muted-foreground">No patient payments yet</p>
              <p className="text-xs text-muted-foreground mt-1">Payments collected via "Collect Payment" or patient portal will appear here.</p>
            </div>
          ) : (
            <div className="space-y-0 divide-y">
              {payments.map(p => (
                <div key={p.id} className="flex items-center justify-between gap-4 py-3 first:pt-0 last:pb-0" data-testid={`payment-row-${p.id}`}>
                  <div className="flex items-center gap-3 min-w-0">
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
                      p.status === "succeeded"
                        ? "bg-emerald-100 dark:bg-emerald-950/40"
                        : "bg-red-100 dark:bg-red-950/40"
                    }`}>
                      <CheckCircle2 className={`h-4 w-4 ${p.status === "succeeded" ? "text-emerald-600 dark:text-emerald-400" : "text-red-500"}`} />
                    </div>
                    <div className="min-w-0">
                      <div className="text-sm font-medium truncate" data-testid={`payment-patient-${p.id}`}>
                        {p.patientName || `Patient #${p.patientId}`}
                      </div>
                      <div className="text-xs text-muted-foreground truncate">
                        {p.description || "Patient payment"}
                      </div>
                      <div className="text-[10px] text-muted-foreground font-mono mt-0.5" data-testid={`payment-id-${p.id}`}>
                        {p.stripePaymentIntentId}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <div className="text-right">
                      <div className={`font-bold font-mono text-sm ${p.status === "succeeded" ? "text-emerald-600 dark:text-emerald-400" : "text-destructive"}`} data-testid={`payment-amount-${p.id}`}>
                        ${(p.amount / 100).toFixed(2)}
                      </div>
                      <div className="flex items-center justify-end gap-1 mt-0.5">
                        <Badge
                          variant="outline"
                          className={`text-[10px] h-4 capitalize ${
                            p.status === "succeeded"
                              ? "border-emerald-400/50 text-emerald-600 dark:text-emerald-400"
                              : "border-red-400/50 text-red-500"
                          }`}
                          data-testid={`payment-status-${p.id}`}
                        >
                          {p.status}
                        </Badge>
                        {p.testMode && (
                          <Badge variant="outline" className="text-[10px] h-4 border-amber-400/50 text-amber-600 dark:text-amber-400 gap-0.5">
                            <FlaskConical className="h-2.5 w-2.5" />
                            TEST
                          </Badge>
                        )}
                      </div>
                      <div className="text-[10px] text-muted-foreground mt-0.5">
                        {new Date(p.createdAt).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-muted-foreground hover:text-foreground shrink-0"
                      title="Print Receipt"
                      onClick={() =>
                        printPaymentReceipt({
                          patientName: p.patientName || `Patient #${p.patientId}`,
                          amount: p.amount,
                          currency: p.currency,
                          date: p.createdAt,
                          stripePaymentIntentId: p.stripePaymentIntentId,
                          description: p.description,
                          receiptEmail: p.receiptEmail,
                          status: p.status,
                          testMode: p.testMode,
                        })
                      }
                      data-testid={`button-print-receipt-${p.id}`}
                    >
                      <Printer className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default function FinancialPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">
          Financial Command Center
        </h1>
        <p className="text-sm text-muted-foreground">
          P&L, overhead analysis, cash flow, patient payments
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <DollarSign className="h-3.5 w-3.5" />
              YTD Revenue
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="kpi-ytd-revenue">$498,240</div>
            <p className="text-xs font-medium text-emerald-600 dark:text-emerald-400">Up 18% vs LY</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <TrendingUp className="h-3.5 w-3.5" />
              Net Income MTD
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="kpi-net-income">$86,400</div>
            <p className="text-xs font-medium text-muted-foreground">43.2% margin</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Percent className="h-3.5 w-3.5" />
              Overhead %
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-overhead">57.3%</div>
            <p className="text-xs font-medium text-emerald-600 dark:text-emerald-400">Target: &lt;59%</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <CreditCard className="h-3.5 w-3.5" />
              A/P Outstanding
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-yellow-600 dark:text-yellow-400" data-testid="kpi-ap-outstanding">$18,200</div>
            <p className="text-xs font-medium text-muted-foreground">3 vendors due</p>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="pl">
        <TabsList>
          <TabsTrigger value="pl">P&L Summary</TabsTrigger>
          <TabsTrigger value="overhead">Overhead</TabsTrigger>
          <TabsTrigger value="payments" data-testid="tab-payment-activity">Payment Activity</TabsTrigger>
        </TabsList>

        <TabsContent value="pl" className="mt-4">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FileSpreadsheet className="h-4 w-4" />
                  P&L Summary — February 2026
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-0">
                  {plLines.map((line, i) => (
                    <div
                      key={i}
                      className={`flex items-center justify-between gap-4 py-2 ${line.separator ? "border-b" : ""} ${line.bold ? "font-bold" : ""}`}
                      data-testid={`pl-line-${i}`}
                    >
                      <span className={`text-sm ${line.bold ? "" : "text-muted-foreground"}`} data-testid={`pl-label-${i}`}>{line.label}</span>
                      <div className="flex items-center gap-3">
                        {line.pct && (
                          <span className="text-xs text-muted-foreground" data-testid={`pl-pct-${i}`}>{line.pct}</span>
                        )}
                        <span className={`font-mono text-sm ${line.bold ? "text-foreground" : ""}`} data-testid={`pl-value-${i}`}>{line.value}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <PieChart className="h-4 w-4" />
                  Overhead Breakdown
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-5">
                  {overheadItems.map((item, i) => (
                    <div key={i} data-testid={`overhead-item-${i}`}>
                      <div className="flex items-center justify-between gap-2 mb-1">
                        <span className="text-sm font-medium" data-testid={`overhead-label-${i}`}>{item.label}</span>
                        <span className={`text-sm font-mono font-bold ${item.over ? "text-destructive" : ""}`} data-testid={`overhead-value-${i}`}>
                          {item.value}% / {item.target}% target
                        </span>
                      </div>
                      <Progress
                        value={(item.value / item.target) * 100 > 100 ? 100 : (item.value / item.target) * 100}
                        className={`h-2 ${item.over ? "[&>div]:bg-destructive" : ""}`}
                      />
                      {item.over && (
                        <p className="text-xs text-destructive mt-1 font-medium" data-testid={`overhead-status-${i}`}>Over budget</p>
                      )}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="overhead" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <PieChart className="h-4 w-4" />
                Overhead Breakdown
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-5">
                {overheadItems.map((item, i) => (
                  <div key={i}>
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <span className="text-sm font-medium">{item.label}</span>
                      <span className={`text-sm font-mono font-bold ${item.over ? "text-destructive" : ""}`}>
                        {item.value}% / {item.target}% target
                      </span>
                    </div>
                    <Progress
                      value={(item.value / item.target) * 100 > 100 ? 100 : (item.value / item.target) * 100}
                      className={`h-2 ${item.over ? "[&>div]:bg-destructive" : ""}`}
                    />
                    {item.over && (
                      <p className="text-xs text-destructive mt-1 font-medium">Over budget</p>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="payments" className="mt-4">
          <PaymentActivityFeed />
        </TabsContent>
      </Tabs>
    </div>
  );
}
