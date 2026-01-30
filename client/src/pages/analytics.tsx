import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { 
  DollarSign, 
  TrendingUp, 
  TrendingDown,
  Clock,
  CheckCircle2,
  XCircle,
  AlertCircle,
  BarChart3,
  PieChart,
  Activity
} from "lucide-react";

interface RevenueAnalytics {
  summary: {
    totalBilled: number;
    totalCollected: number;
    totalPending: number;
    collectionRate: number;
    denialRate: number;
    avgDaysToPayment: number;
  };
  claims: {
    total: number;
    paid: number;
    denied: number;
    pending: number;
  };
  priorAuthorizations: {
    total: number;
    approved: number;
    denied: number;
    pending: number;
    approvalRate: number;
  };
  agingBuckets: {
    current: number;
    days31to60: number;
    days61to90: number;
    over90: number;
  };
  trends: {
    monthlyCollections: number[];
    monthlyDenials: number[];
    months: string[];
  };
}

export default function AnalyticsPage() {
  const { data: analytics, isLoading } = useQuery<RevenueAnalytics>({
    queryKey: ["/api/analytics/revenue-cycle"]
  });

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(amount);
  };

  if (isLoading) {
    return (
      <div className="p-6 space-y-6">
        <Skeleton className="h-10 w-80" />
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Skeleton className="h-80" />
          <Skeleton className="h-80" />
        </div>
      </div>
    );
  }

  if (!analytics) {
    return (
      <div className="p-6">
        <p className="text-muted-foreground">Failed to load analytics data</p>
      </div>
    );
  }

  const totalAgingClaims = analytics.agingBuckets.current + analytics.agingBuckets.days31to60 + 
    analytics.agingBuckets.days61to90 + analytics.agingBuckets.over90;

  return (
    <div className="p-6 space-y-6 overflow-y-auto max-h-[calc(100vh-80px)]">
      <div>
        <h1 className="text-3xl font-bold" data-testid="text-page-title">Revenue Cycle Command Center</h1>
        <p className="text-muted-foreground">
          Real-time analytics and insights for your billing performance
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Total Billed</p>
                <p className="text-2xl font-bold" data-testid="text-total-billed">
                  {formatCurrency(analytics.summary.totalBilled)}
                </p>
                <p className="text-xs text-muted-foreground mt-1">This period</p>
              </div>
              <div className="p-2 bg-primary/10 rounded-full">
                <DollarSign className="h-5 w-5 text-primary" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Total Collected</p>
                <p className="text-2xl font-bold text-green-600" data-testid="text-total-collected">
                  {formatCurrency(analytics.summary.totalCollected)}
                </p>
                <div className="flex items-center gap-1 mt-1">
                  <TrendingUp className="h-3 w-3 text-green-500" />
                  <span className="text-xs text-green-600">{analytics.summary.collectionRate}% rate</span>
                </div>
              </div>
              <div className="p-2 bg-green-100 dark:bg-green-900/30 rounded-full">
                <CheckCircle2 className="h-5 w-5 text-green-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Pending Claims</p>
                <p className="text-2xl font-bold text-yellow-600" data-testid="text-total-pending">
                  {formatCurrency(analytics.summary.totalPending)}
                </p>
                <p className="text-xs text-muted-foreground mt-1">{analytics.claims.pending} claims</p>
              </div>
              <div className="p-2 bg-yellow-100 dark:bg-yellow-900/30 rounded-full">
                <Clock className="h-5 w-5 text-yellow-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Avg Days to Payment</p>
                <p className="text-2xl font-bold" data-testid="text-avg-days">
                  {analytics.summary.avgDaysToPayment}
                </p>
                <p className="text-xs text-muted-foreground mt-1">Industry avg: 45 days</p>
              </div>
              <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-full">
                <Activity className="h-5 w-5 text-blue-600" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5" />
              Monthly Collections Trend
            </CardTitle>
            <CardDescription>Revenue collected over the past 6 months</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {analytics.trends.months.map((month, index) => {
                const value = analytics.trends.monthlyCollections[index];
                const maxValue = Math.max(...analytics.trends.monthlyCollections);
                const percentage = (value / maxValue) * 100;
                
                return (
                  <div key={month} className="space-y-1">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground w-12">{month}</span>
                      <span className="font-medium">{formatCurrency(value)}</span>
                    </div>
                    <Progress value={percentage} className="h-3" />
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <PieChart className="h-5 w-5" />
              Claims Status
            </CardTitle>
            <CardDescription>Current claim distribution</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="h-3 w-3 rounded-full bg-green-500" />
                  <span className="text-sm">Paid</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="font-medium">{analytics.claims.paid}</span>
                  <Badge variant="secondary" className="text-xs">
                    {analytics.claims.total > 0 ? Math.round((analytics.claims.paid / analytics.claims.total) * 100) : 0}%
                  </Badge>
                </div>
              </div>
              
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="h-3 w-3 rounded-full bg-yellow-500" />
                  <span className="text-sm">Pending</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="font-medium">{analytics.claims.pending}</span>
                  <Badge variant="secondary" className="text-xs">
                    {analytics.claims.total > 0 ? Math.round((analytics.claims.pending / analytics.claims.total) * 100) : 0}%
                  </Badge>
                </div>
              </div>
              
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="h-3 w-3 rounded-full bg-red-500" />
                  <span className="text-sm">Denied</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="font-medium">{analytics.claims.denied}</span>
                  <Badge variant="secondary" className="text-xs">
                    {analytics.claims.total > 0 ? Math.round((analytics.claims.denied / analytics.claims.total) * 100) : 0}%
                  </Badge>
                </div>
              </div>
            </div>

            <div className="pt-4 border-t">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Total Claims</span>
                <span className="font-bold text-lg">{analytics.claims.total}</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Clock className="h-5 w-5" />
              Claims Aging Report
            </CardTitle>
            <CardDescription>Outstanding claims by age</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-center justify-between p-3 border rounded-lg">
                <div className="flex items-center gap-3">
                  <Badge variant="outline" className="border-green-500 text-green-700">Current</Badge>
                  <span className="text-sm text-muted-foreground">0-30 days</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="font-semibold">{analytics.agingBuckets.current}</span>
                  <span className="text-sm text-muted-foreground">claims</span>
                </div>
              </div>
              
              <div className="flex items-center justify-between p-3 border rounded-lg">
                <div className="flex items-center gap-3">
                  <Badge variant="outline" className="border-yellow-500 text-yellow-700">31-60</Badge>
                  <span className="text-sm text-muted-foreground">days old</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="font-semibold">{analytics.agingBuckets.days31to60}</span>
                  <span className="text-sm text-muted-foreground">claims</span>
                </div>
              </div>
              
              <div className="flex items-center justify-between p-3 border rounded-lg">
                <div className="flex items-center gap-3">
                  <Badge variant="outline" className="border-orange-500 text-orange-700">61-90</Badge>
                  <span className="text-sm text-muted-foreground">days old</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="font-semibold">{analytics.agingBuckets.days61to90}</span>
                  <span className="text-sm text-muted-foreground">claims</span>
                </div>
              </div>
              
              <div className="flex items-center justify-between p-3 border rounded-lg bg-red-50 dark:bg-red-900/10">
                <div className="flex items-center gap-3">
                  <Badge variant="outline" className="border-red-500 text-red-700">90+</Badge>
                  <span className="text-sm text-muted-foreground">days old</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-red-600">{analytics.agingBuckets.over90}</span>
                  <span className="text-sm text-muted-foreground">claims</span>
                </div>
              </div>

              {analytics.agingBuckets.over90 > 0 && (
                <div className="flex items-center gap-2 p-3 bg-red-50 dark:bg-red-900/20 rounded-lg">
                  <AlertCircle className="h-4 w-4 text-red-500" />
                  <span className="text-sm text-red-700 dark:text-red-400">
                    {analytics.agingBuckets.over90} claims require immediate follow-up
                  </span>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5" />
              Prior Authorization Performance
            </CardTitle>
            <CardDescription>Authorization request outcomes</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="text-center">
              <div className="text-5xl font-bold text-primary" data-testid="text-auth-approval-rate">
                {analytics.priorAuthorizations.approvalRate}%
              </div>
              <p className="text-sm text-muted-foreground mt-1">Approval Rate</p>
            </div>

            <div className="grid grid-cols-3 gap-4 text-center">
              <div className="p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
                <CheckCircle2 className="h-5 w-5 text-green-500 mx-auto mb-1" />
                <p className="text-xl font-bold text-green-600">{analytics.priorAuthorizations.approved}</p>
                <p className="text-xs text-muted-foreground">Approved</p>
              </div>
              <div className="p-3 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg">
                <Clock className="h-5 w-5 text-yellow-500 mx-auto mb-1" />
                <p className="text-xl font-bold text-yellow-600">{analytics.priorAuthorizations.pending}</p>
                <p className="text-xs text-muted-foreground">Pending</p>
              </div>
              <div className="p-3 bg-red-50 dark:bg-red-900/20 rounded-lg">
                <XCircle className="h-5 w-5 text-red-500 mx-auto mb-1" />
                <p className="text-xl font-bold text-red-600">{analytics.priorAuthorizations.denied}</p>
                <p className="text-xs text-muted-foreground">Denied</p>
              </div>
            </div>

            <div className="pt-4 border-t">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Total Authorizations</span>
                <span className="font-bold">{analytics.priorAuthorizations.total}</span>
              </div>
            </div>

            {analytics.priorAuthorizations.denied > 0 && (
              <div className="flex items-center gap-2 p-3 border rounded-lg">
                <TrendingUp className="h-4 w-4 text-primary" />
                <span className="text-sm">
                  Use AI Appeals to overturn {analytics.priorAuthorizations.denied} denied authorizations
                </span>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingDown className="h-5 w-5 text-red-500" />
            Denial Rate Analysis
          </CardTitle>
          <CardDescription>Understanding and reducing claim denials</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="text-center p-6 border rounded-lg">
              <p className="text-4xl font-bold text-red-600" data-testid="text-denial-rate">
                {analytics.summary.denialRate}%
              </p>
              <p className="text-sm text-muted-foreground mt-1">Current Denial Rate</p>
              <p className="text-xs text-green-600 mt-2">Industry avg: 10-15%</p>
            </div>
            
            <div className="space-y-3">
              <h4 className="font-medium text-sm">Common Denial Reasons</h4>
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span>Missing prior authorization</span>
                  <Badge variant="secondary">35%</Badge>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span>Incorrect coding</span>
                  <Badge variant="secondary">25%</Badge>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span>Insufficient documentation</span>
                  <Badge variant="secondary">20%</Badge>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span>Eligibility issues</span>
                  <Badge variant="secondary">15%</Badge>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span>Other</span>
                  <Badge variant="secondary">5%</Badge>
                </div>
              </div>
            </div>
            
            <div className="space-y-3">
              <h4 className="font-medium text-sm">Recommended Actions</h4>
              <div className="space-y-2 text-sm text-muted-foreground">
                <div className="flex items-start gap-2">
                  <CheckCircle2 className="h-4 w-4 text-green-500 mt-0.5 shrink-0" />
                  <span>Use Coding Engine for accurate CDT/CPT codes</span>
                </div>
                <div className="flex items-start gap-2">
                  <CheckCircle2 className="h-4 w-4 text-green-500 mt-0.5 shrink-0" />
                  <span>Generate AI medical necessity letters</span>
                </div>
                <div className="flex items-start gap-2">
                  <CheckCircle2 className="h-4 w-4 text-green-500 mt-0.5 shrink-0" />
                  <span>Submit prior auths before treatment</span>
                </div>
                <div className="flex items-start gap-2">
                  <CheckCircle2 className="h-4 w-4 text-green-500 mt-0.5 shrink-0" />
                  <span>Verify eligibility at each visit</span>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
