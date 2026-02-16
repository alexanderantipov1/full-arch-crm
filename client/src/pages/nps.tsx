import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  TrendingUp,
  ThumbsUp,
  Minus,
  ThumbsDown,
  Bot,
  Star,
  MessageSquare,
  BarChart3,
  CheckCircle,
  AlertTriangle,
} from "lucide-react";

const surveyResponses = [
  { name: "Margaret Sullivan", score: 10, comment: "Amazing experience with my implant!", category: "Promoter" },
  { name: "Robert Kim", score: 9, comment: "Very professional team", category: "Promoter" },
  { name: "Diana Patel", score: 8, comment: "Good but wait time was long", category: "Passive" },
  { name: "Tom Davis", score: 7, comment: "Billing process confusing", category: "Passive" },
  { name: "James Okafor", score: 4, comment: "Front desk was rude", category: "Detractor", action: "Office manager contacted \u2014 resolved" },
];

const satisfactionCategories = [
  { label: "Provider care", value: 96 },
  { label: "Treatment outcomes", value: 94 },
  { label: "Facility cleanliness", value: 98 },
  { label: "Wait time", value: 72 },
  { label: "Billing clarity", value: 68 },
  { label: "Front desk", value: 82 },
  { label: "Overall experience", value: 91 },
];

export default function NpsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">
          Patient NPS & Satisfaction
        </h1>
        <p className="text-sm text-muted-foreground">
          Net Promoter Score tracking, survey responses, and satisfaction trends
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <TrendingUp className="h-3.5 w-3.5" />
              NPS Score
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="kpi-nps-score">78</div>
            <p className="text-xs font-medium text-emerald-600 dark:text-emerald-400">Excellent (target: 70+)</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <ThumbsUp className="h-3.5 w-3.5" />
              Promoters
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="kpi-promoters">82%</div>
            <p className="text-xs font-medium text-muted-foreground">Score 9-10</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Minus className="h-3.5 w-3.5" />
              Passives
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-yellow-600 dark:text-yellow-400" data-testid="kpi-passives">14%</div>
            <p className="text-xs font-medium text-muted-foreground">Score 7-8</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <ThumbsDown className="h-3.5 w-3.5" />
              Detractors
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-destructive" data-testid="kpi-detractors">4%</div>
            <p className="text-xs font-medium text-muted-foreground">3 patients</p>
          </CardContent>
        </Card>
      </div>

      <Card className="border-purple-500/20 bg-purple-500/5 dark:bg-purple-500/5">
        <CardContent className="pt-6">
          <div className="flex items-center gap-2 mb-2">
            <Bot className="h-4 w-4 text-purple-600 dark:text-purple-400" />
            <span className="text-sm font-bold text-purple-600 dark:text-purple-400">AI Review Routing</span>
          </div>
          <p className="text-sm text-muted-foreground leading-relaxed" data-testid="text-ai-review-routing">
            Patients scoring 9-10 auto-receive Google review link. Scores &lt;=6 route to office manager. AI generates draft response for each review within 30 minutes.
          </p>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <MessageSquare className="h-4 w-4" />
              Recent Survey Responses
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {surveyResponses.map((r, i) => {
              const badgeVariant =
                r.category === "Promoter"
                  ? "default"
                  : r.category === "Passive"
                    ? "outline"
                    : "destructive";
              const badgeClass =
                r.category === "Promoter"
                  ? "bg-emerald-600 dark:bg-emerald-500"
                  : r.category === "Passive"
                    ? "text-yellow-600 dark:text-yellow-400 border-yellow-500"
                    : "";
              const scoreColor =
                r.score >= 9
                  ? "text-emerald-600 dark:text-emerald-400"
                  : r.score >= 7
                    ? "text-yellow-600 dark:text-yellow-400"
                    : "text-destructive";
              return (
                <div key={i} className="border-b pb-3 last:border-0 last:pb-0" data-testid={`survey-response-${i}`}>
                  <div className="flex items-center justify-between mb-1 flex-wrap gap-2">
                    <span className="text-xs font-bold" data-testid={`survey-name-${i}`}>{r.name}</span>
                    <div className="flex items-center gap-2">
                      <span className={`text-xs font-bold font-mono ${scoreColor}`} data-testid={`survey-score-${i}`}>
                        <Star className="inline mr-0.5 h-3 w-3" />
                        {r.score}
                      </span>
                      <Badge variant={badgeVariant} className={`text-[10px] ${badgeClass}`} data-testid={`badge-category-${i}`}>
                        {r.category}
                      </Badge>
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground" data-testid={`survey-comment-${i}`}>"{r.comment}"</p>
                  {r.action && (
                    <p className="text-xs text-emerald-600 dark:text-emerald-400 mt-1" data-testid={`survey-action-${i}`}>
                      <CheckCircle className="inline mr-1 h-3 w-3" />
                      {r.action}
                    </p>
                  )}
                </div>
              );
            })}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="h-4 w-4" />
              NPS Trend & Categories
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {satisfactionCategories.map((cat, i) => {
              const valueColor =
                cat.value >= 90
                  ? "text-emerald-600 dark:text-emerald-400"
                  : cat.value >= 80
                    ? "text-foreground"
                    : "text-yellow-600 dark:text-yellow-400";
              const progressClass =
                cat.value < 80 ? "[&>div]:bg-yellow-500" : "";
              return (
                <div key={i} data-testid={`satisfaction-category-${i}`}>
                  <div className="flex items-center justify-between mb-1 flex-wrap gap-2">
                    <span className="text-xs font-medium" data-testid={`satisfaction-label-${i}`}>{cat.label}</span>
                    <span className={`text-xs font-bold font-mono ${valueColor}`} data-testid={`satisfaction-value-${i}`}>{cat.value}%</span>
                  </div>
                  <Progress value={cat.value} className={`h-2 ${progressClass}`} />
                </div>
              );
            })}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
