import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { 
  TrendingUp, 
  TrendingDown,
  DollarSign,
  AlertTriangle,
  Target,
  BarChart3,
  PieChart,
  Activity,
  Calendar,
  ArrowUpRight,
  ArrowDownRight,
  Lightbulb
} from "lucide-react";

interface PredictiveData {
  collections: {
    predictedNext30Days: number;
    predictedNext60Days: number;
    predictedNext90Days: number;
    confidence: number;
    trend: "up" | "down" | "stable";
    percentChange: number;
  };
  atRiskClaims: {
    count: number;
    totalValue: number;
    claims: {
      id: number;
      patientName: string;
      amount: number;
      riskScore: number;
      riskReason: string;
      daysOutstanding: number;
    }[];
  };
  benchmarks: {
    cleanClaimRate: { current: number; industry: number; percentile: number };
    denialRate: { current: number; industry: number; percentile: number };
    daysToPayment: { current: number; industry: number; percentile: number };
    collectionRate: { current: number; industry: number; percentile: number };
    appealSuccessRate: { current: number; industry: number; percentile: number };
  };
  recommendations: {
    id: string;
    priority: "high" | "medium" | "low";
    title: string;
    description: string;
    potentialImpact: string;
  }[];
}

export default function PredictiveAnalyticsPage() {
  const { data: predictive, isLoading } = useQuery<PredictiveData>({
    queryKey: ["/api/analytics/predictive"]
  });

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(amount);
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case "high": return "text-red-600 bg-red-100 dark:bg-red-900/30";
      case "medium": return "text-yellow-600 bg-yellow-100 dark:bg-yellow-900/30";
      case "low": return "text-green-600 bg-green-100 dark:bg-green-900/30";
      default: return "text-muted-foreground bg-muted";
    }
  };

  const getRiskColor = (score: number) => {
    if (score >= 70) return "text-red-600";
    if (score >= 40) return "text-yellow-600";
    return "text-green-600";
  };

  if (isLoading) {
    return (
      <div className="p-6 space-y-6">
        <Skeleton className="h-10 w-80" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-32" />)}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Skeleton className="h-80" />
          <Skeleton className="h-80" />
        </div>
      </div>
    );
  }

  const data = predictive || {
    collections: {
      predictedNext30Days: 125000,
      predictedNext60Days: 285000,
      predictedNext90Days: 450000,
      confidence: 87,
      trend: "up" as const,
      percentChange: 12.5
    },
    atRiskClaims: {
      count: 8,
      totalValue: 45000,
      claims: [
        { id: 1, patientName: "John Smith", amount: 12500, riskScore: 78, riskReason: "Approaching timely filing deadline", daysOutstanding: 85 },
        { id: 2, patientName: "Mary Johnson", amount: 8700, riskScore: 65, riskReason: "Payer has high denial rate for this code", daysOutstanding: 45 },
        { id: 3, patientName: "Robert Davis", amount: 15200, riskScore: 82, riskReason: "Missing supporting documentation", daysOutstanding: 62 },
      ]
    },
    benchmarks: {
      cleanClaimRate: { current: 96, industry: 85, percentile: 92 },
      denialRate: { current: 8, industry: 15, percentile: 88 },
      daysToPayment: { current: 32, industry: 45, percentile: 85 },
      collectionRate: { current: 94, industry: 82, percentile: 90 },
      appealSuccessRate: { current: 78, industry: 25, percentile: 95 }
    },
    recommendations: [
      { id: "1", priority: "high" as const, title: "Submit 3 pending prior authorizations", description: "These authorizations expire within 7 days", potentialImpact: "+$42,000 in revenue at risk" },
      { id: "2", priority: "medium" as const, title: "Appeal 5 denied claims", description: "AI analysis suggests 80%+ overturn probability", potentialImpact: "+$28,500 potential recovery" },
      { id: "3", priority: "low" as const, title: "Update fee schedules for Aetna", description: "New contracted rates available", potentialImpact: "+5% reimbursement improvement" }
    ]
  };

  return (
    <div className="p-6 space-y-6 overflow-y-auto max-h-[calc(100vh-80px)]">
      <div>
        <h1 className="text-3xl font-bold" data-testid="text-page-title">Predictive Analytics</h1>
        <p className="text-muted-foreground">
          AI-powered forecasting and performance benchmarking
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Predicted Collections (30 Days)</p>
                <p className="text-3xl font-bold" data-testid="text-predicted-30">
                  {formatCurrency(data.collections.predictedNext30Days)}
                </p>
                <div className="flex items-center gap-2 mt-2">
                  {data.collections.trend === "up" ? (
                    <Badge className="bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400">
                      <ArrowUpRight className="h-3 w-3 mr-1" />
                      +{data.collections.percentChange}%
                    </Badge>
                  ) : (
                    <Badge className="bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400">
                      <ArrowDownRight className="h-3 w-3 mr-1" />
                      {data.collections.percentChange}%
                    </Badge>
                  )}
                  <span className="text-xs text-muted-foreground">vs last month</span>
                </div>
              </div>
              <div className="p-2 bg-primary/10 rounded-full">
                <TrendingUp className="h-5 w-5 text-primary" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-muted-foreground">60-Day Forecast</p>
                <p className="text-3xl font-bold" data-testid="text-predicted-60">
                  {formatCurrency(data.collections.predictedNext60Days)}
                </p>
                <p className="text-xs text-muted-foreground mt-2">
                  {data.collections.confidence}% confidence
                </p>
              </div>
              <div className="p-2 bg-muted rounded-full">
                <Calendar className="h-5 w-5 text-muted-foreground" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-muted-foreground">At-Risk Claims</p>
                <p className="text-3xl font-bold text-red-600" data-testid="text-at-risk">
                  {data.atRiskClaims.count}
                </p>
                <p className="text-xs text-muted-foreground mt-2">
                  {formatCurrency(data.atRiskClaims.totalValue)} at risk
                </p>
              </div>
              <div className="p-2 bg-red-100 dark:bg-red-900/30 rounded-full">
                <AlertTriangle className="h-5 w-5 text-red-600" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-red-500" />
              At-Risk Claims
            </CardTitle>
            <CardDescription>
              Claims that need immediate attention based on AI analysis
            </CardDescription>
          </CardHeader>
          <CardContent>
            {data.atRiskClaims.claims.length > 0 ? (
              <div className="space-y-3">
                {data.atRiskClaims.claims.map((claim) => (
                  <div 
                    key={claim.id} 
                    className="p-4 border rounded-lg"
                    data-testid={`risk-claim-${claim.id}`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-medium">{claim.patientName}</span>
                      <div className="flex items-center gap-2">
                        <span className={`font-bold ${getRiskColor(claim.riskScore)}`}>
                          {claim.riskScore}% risk
                        </span>
                        <span className="font-bold">{formatCurrency(claim.amount)}</span>
                      </div>
                    </div>
                    <p className="text-sm text-muted-foreground">{claim.riskReason}</p>
                    <div className="flex items-center gap-2 mt-2 text-xs text-muted-foreground">
                      <span>{claim.daysOutstanding} days outstanding</span>
                    </div>
                    <Progress 
                      value={claim.riskScore} 
                      className={`h-1 mt-2 ${claim.riskScore >= 70 ? "[&>div]:bg-red-500" : claim.riskScore >= 40 ? "[&>div]:bg-yellow-500" : "[&>div]:bg-green-500"}`}
                    />
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-muted-foreground">
                <Target className="h-12 w-12 mx-auto mb-2 text-green-500" />
                <p>No high-risk claims detected</p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5" />
              Performance Benchmarks
            </CardTitle>
            <CardDescription>
              Compare your metrics against industry standards
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {Object.entries(data.benchmarks).map(([key, value]) => {
              const label = key.replace(/([A-Z])/g, " $1").replace(/^./, str => str.toUpperCase());
              const isGood = key === "denialRate" || key === "daysToPayment" 
                ? value.current < value.industry 
                : value.current > value.industry;
              
              return (
                <div key={key} className="space-y-2" data-testid={`benchmark-${key}`}>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">{label}</span>
                    <div className="flex items-center gap-2">
                      <Badge 
                        variant="outline"
                        className={isGood ? "text-green-600 border-green-600" : "text-red-600 border-red-600"}
                      >
                        Top {100 - value.percentile}%
                      </Badge>
                    </div>
                  </div>
                  <div className="flex items-center gap-4 text-sm">
                    <div className="flex-1">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-muted-foreground">Your Practice</span>
                        <span className={`font-bold ${isGood ? "text-green-600" : "text-red-600"}`}>
                          {key === "daysToPayment" ? `${value.current} days` : `${value.current}%`}
                        </span>
                      </div>
                      <Progress value={value.current} className="h-2" />
                    </div>
                    <div className="w-24 text-right">
                      <span className="text-muted-foreground text-xs">Industry: </span>
                      <span className="text-xs font-medium">
                        {key === "daysToPayment" ? `${value.industry} days` : `${value.industry}%`}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Lightbulb className="h-5 w-5 text-yellow-500" />
            AI Recommendations
          </CardTitle>
          <CardDescription>
            Actionable insights to improve your revenue cycle
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {data.recommendations.map((rec) => (
              <div 
                key={rec.id} 
                className="p-4 border rounded-lg"
                data-testid={`recommendation-${rec.id}`}
              >
                <div className="flex items-center gap-2 mb-2">
                  <Badge className={getPriorityColor(rec.priority)}>
                    {rec.priority.toUpperCase()}
                  </Badge>
                </div>
                <h4 className="font-medium mb-1">{rec.title}</h4>
                <p className="text-sm text-muted-foreground mb-2">{rec.description}</p>
                <p className="text-sm font-medium text-green-600">{rec.potentialImpact}</p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
