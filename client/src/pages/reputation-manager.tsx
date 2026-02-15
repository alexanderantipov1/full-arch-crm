import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Star, MessageCircle, Send, TrendingUp, BarChart3, Mail, Clock,
  CheckCircle, AlertCircle, Globe, ThumbsUp, ThumbsDown, Award, Target,
  Users, Activity, Eye, ArrowUpRight, Sparkles, Shield, Edit, ChevronRight,
} from "lucide-react";

type TabId = "dashboard" | "campaigns" | "sentiment" | "responses" | "analytics";

const KPI_DATA = [
  { label: "Reputation Score", value: "4.87", sub: "/ 5.0", icon: Award },
  { label: "NPS Score", value: "78", sub: "Excellent", icon: Target },
  { label: "Total Reviews", value: "342", sub: "Across all platforms", icon: MessageCircle },
  { label: "Response Rate", value: "96%", sub: "Within 24hrs", icon: Clock },
  { label: "Requests Sent (MTD)", value: "124", sub: "Review requests", icon: Send },
  { label: "Conversion Rate", value: "38%", sub: "Requests to reviews", icon: TrendingUp },
] as const;

const PLATFORMS = [
  { name: "Google Business", rating: 4.9, reviews: 186, newThisMonth: 12, badge: "Excellent", icon: Globe },
  { name: "Healthgrades", rating: 4.8, reviews: 78, newThisMonth: 4, badge: null, icon: Shield },
  { name: "Yelp", rating: 4.7, reviews: 52, newThisMonth: 3, badge: null, icon: Star },
  { name: "Facebook", rating: 4.9, reviews: 26, newThisMonth: 2, badge: null, icon: Users },
] as const;

const RECENT_REVIEWS = [
  { excerpt: "Dr. Mitchell and her team are incredible...", stars: 5, platform: "Google", timeAgo: "2 hours ago", responseStatus: "Sent" },
  { excerpt: "The billing process was so smooth...", stars: 5, platform: "Healthgrades", timeAgo: "1 day ago", responseStatus: "Sent" },
  { excerpt: "Had to wait 30 minutes past my appointment...", stars: 3, platform: "Google", timeAgo: "2 days ago", responseStatus: "Draft Ready" },
  { excerpt: "Best dental implant experience I've ever had...", stars: 5, platform: "Yelp", timeAgo: "3 days ago", responseStatus: "Sent" },
  { excerpt: "The All-on-4 procedure changed my life...", stars: 5, platform: "Google", timeAgo: "4 days ago", responseStatus: "Pending" },
] as const;

const CAMPAIGNS = [
  { name: "Post-Visit Follow-Up", trigger: "Auto-send 48hrs after appointment", channels: "Email + SMS", conversion: "38%", sent: 89, status: "Active" },
  { name: "Implant Milestone", trigger: "Send after final restoration delivery", channels: "Email only", conversion: "52%", sent: 12, status: "Active" },
  { name: "Quarterly Check-In", trigger: "Every 90 days to existing patients", channels: "Email", conversion: "22%", sent: 34, status: "Paused" },
] as const;

const CAMPAIGN_KPIS = [
  { label: "Emails Sent", value: "124", icon: Mail },
  { label: "Opened", value: "96", sub: "77%", icon: Eye },
  { label: "Clicked", value: "58", sub: "47%", icon: ArrowUpRight },
  { label: "Reviews Left", value: "47", sub: "38%", icon: Star },
] as const;

const POSITIVE_THEMES = [
  { theme: "Friendly staff", mentions: 68 },
  { theme: "Professional care", mentions: 54 },
  { theme: "Pain-free experience", mentions: 42 },
  { theme: "Quick billing", mentions: 38 },
  { theme: "Beautiful results", mentions: 31 },
] as const;

const NEGATIVE_THEMES = [
  { theme: "Wait times", mentions: 8 },
  { theme: "Parking difficulty", mentions: 4 },
  { theme: "Insurance confusion", mentions: 3 },
] as const;

const WORD_CLOUD_TAGS = [
  { word: "Friendly", size: "text-lg" }, { word: "Professional", size: "text-base" },
  { word: "Pain-free", size: "text-base" }, { word: "Comfortable", size: "text-sm" },
  { word: "Billing", size: "text-sm" }, { word: "Clean", size: "text-sm" },
  { word: "Implants", size: "text-base" }, { word: "Staff", size: "text-lg" },
  { word: "Welcoming", size: "text-sm" }, { word: "Knowledgeable", size: "text-sm" },
  { word: "Gentle", size: "text-base" }, { word: "Efficient", size: "text-sm" },
  { word: "Results", size: "text-sm" }, { word: "Transparent", size: "text-xs" },
  { word: "Caring", size: "text-base" }, { word: "Modern", size: "text-xs" },
  { word: "Thorough", size: "text-sm" }, { word: "Recommended", size: "text-sm" },
] as const;

const RESPONSE_QUEUE = [
  {
    reviewer: "Jennifer M.",
    stars: 5,
    excerpt: "The entire team made me feel so welcome. My implant looks absolutely amazing and the process was painless.",
    draft: "Thank you so much, Jennifer! Your kind words mean the world to our team. We take great pride in ensuring every patient has a comfortable and positive experience. We look forward to seeing you at your next visit!",
    tone: "Grateful",
  },
  {
    reviewer: "David R.",
    stars: 3,
    excerpt: "Good work on the procedure but I had to wait over 30 minutes past my scheduled time. The staff was apologetic but it was frustrating.",
    draft: "David, thank you for your feedback. We sincerely apologize for the extended wait time during your visit. We understand how valuable your time is and have recently implemented new scheduling improvements to minimize delays. We hope to provide a better experience at your next appointment.",
    tone: "Empathetic",
  },
  {
    reviewer: "Lisa K.",
    stars: 5,
    excerpt: "After years of being self-conscious about my smile, the implant procedure at this practice changed everything. Detailed explanations at every step.",
    draft: "Lisa, thank you for sharing your wonderful experience! We are thrilled that your implant journey exceeded expectations. Our team is dedicated to providing detailed guidance throughout every procedure. Your beautiful new smile is well-deserved!",
    tone: "Professional",
  },
  {
    reviewer: "Mark T.",
    stars: 4,
    excerpt: "Great dental work and friendly staff. Only issue was finding parking near the office. Otherwise a top-notch experience.",
    draft: "Thank you for the fantastic review, Mark! We appreciate you highlighting our team and quality of care. Regarding parking, there is additional parking available on the side street and the municipal lot just one block east. We hope this helps for your next visit!",
    tone: "Professional",
  },
] as const;

const RESPONSE_STATS = [
  { label: "Avg Response Time", value: "4.2 hrs", icon: Clock },
  { label: "AI Accuracy", value: "94%", sub: "Approved without edits", icon: Sparkles },
  { label: "Templates Used", value: "12", icon: Activity },
] as const;

const MONTHLY_TRENDS = [
  { month: "Sep", reviews: 14, rating: "4.7", nps: 72, response: "88%" },
  { month: "Oct", reviews: 18, rating: "4.8", nps: 74, response: "91%" },
  { month: "Nov", reviews: 22, rating: "4.8", nps: 75, response: "93%" },
  { month: "Dec", reviews: 16, rating: "4.9", nps: 76, response: "95%" },
  { month: "Jan", reviews: 24, rating: "4.9", nps: 77, response: "96%" },
  { month: "Feb", reviews: 21, rating: "4.87", nps: 78, response: "96%" },
] as const;

const SOURCE_BREAKDOWN = [
  { source: "Google", pct: 54, color: "bg-blue-500", width: "w-[54%]" },
  { source: "Healthgrades", pct: 23, color: "bg-emerald-500", width: "w-[23%]" },
  { source: "Yelp", pct: 15, color: "bg-red-500", width: "w-[15%]" },
  { source: "Facebook", pct: 8, color: "bg-indigo-500", width: "w-[8%]" },
] as const;

const COMPETITORS = [
  { name: "Auburn Dental Implants", rating: 4.2, reviews: 124, comparison: "Below You" },
  { name: "Sierra Implant Center", rating: 4.6, reviews: 98, comparison: "Below You" },
  { name: "Capital Oral Surgery", rating: 4.5, reviews: 156, comparison: "Below You" },
] as const;

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    sent: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
    active: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
    excellent: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
    "below you": "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
    "draft ready": "bg-amber-500/15 text-amber-700 dark:text-amber-400",
    paused: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
    pending: "bg-blue-500/15 text-blue-700 dark:text-blue-400",
  };
  const cls = map[status.toLowerCase()] || "bg-muted text-muted-foreground";
  return (
    <Badge variant="secondary" className={`text-[10px] no-default-hover-elevate no-default-active-elevate ${cls}`} data-testid={`badge-${status.toLowerCase().replace(/\s+/g, "-")}`}>
      {status}
    </Badge>
  );
}

function StarRating({ count }: { count: number }) {
  return (
    <div className="flex items-center gap-0.5">
      {Array.from({ length: 5 }, (_, i) => (
        <Star
          key={i}
          className={`h-3.5 w-3.5 ${i < count ? "fill-amber-400 text-amber-400" : "text-muted-foreground/30"}`}
        />
      ))}
    </div>
  );
}

function ToneBadge({ tone }: { tone: string }) {
  const map: Record<string, string> = {
    professional: "bg-blue-500/15 text-blue-700 dark:text-blue-400",
    empathetic: "bg-purple-500/15 text-purple-700 dark:text-purple-400",
    grateful: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
  };
  const cls = map[tone.toLowerCase()] || "bg-muted text-muted-foreground";
  return (
    <Badge variant="secondary" className={`text-[10px] no-default-hover-elevate no-default-active-elevate ${cls}`} data-testid={`badge-tone-${tone.toLowerCase()}`}>
      {tone}
    </Badge>
  );
}

export default function ReputationManagerPage() {
  const [activeTab, setActiveTab] = useState<TabId>("dashboard");

  return (
    <div className="space-y-5 p-5" data-testid="reputation-manager">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight" data-testid="text-page-title">Reputation Manager</h1>
        <p className="text-sm text-muted-foreground">Monitor and manage your practice reputation, reviews, and patient satisfaction</p>
      </div>

      <div className="grid gap-3 grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        {KPI_DATA.map((kpi) => {
          const Icon = kpi.icon;
          return (
            <Card key={kpi.label} data-testid={`kpi-${kpi.label.toLowerCase().replace(/\s+/g, "-")}`}>
              <CardContent className="p-4">
                <div className="flex items-center gap-2 mb-1">
                  <Icon className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="text-[10px] font-semibold tracking-wider uppercase text-muted-foreground">{kpi.label}</span>
                </div>
                <div className="text-2xl font-extrabold tracking-tight">{kpi.value}</div>
                <div className="text-xs text-muted-foreground mt-0.5">{kpi.sub}</div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as TabId)}>
        <TabsList data-testid="reputation-tabs">
          <TabsTrigger value="dashboard" data-testid="tab-dashboard"><BarChart3 className="h-3.5 w-3.5 mr-1.5" />Review Dashboard</TabsTrigger>
          <TabsTrigger value="campaigns" data-testid="tab-campaigns"><Send className="h-3.5 w-3.5 mr-1.5" />Campaign Manager</TabsTrigger>
          <TabsTrigger value="sentiment" data-testid="tab-sentiment"><Sparkles className="h-3.5 w-3.5 mr-1.5" />Sentiment Analysis</TabsTrigger>
          <TabsTrigger value="responses" data-testid="tab-responses"><MessageCircle className="h-3.5 w-3.5 mr-1.5" />Review Responses</TabsTrigger>
          <TabsTrigger value="analytics" data-testid="tab-analytics"><TrendingUp className="h-3.5 w-3.5 mr-1.5" />Analytics</TabsTrigger>
        </TabsList>

        <TabsContent value="dashboard" className="space-y-5 mt-4">
          <h2 className="text-xl font-black" data-testid="text-section-title">Review Monitoring Dashboard</h2>

          <div className="grid gap-3 grid-cols-1 sm:grid-cols-2 xl:grid-cols-4">
            {PLATFORMS.map((p) => {
              const Icon = p.icon;
              return (
                <Card key={p.name} data-testid={`platform-${p.name.toLowerCase().replace(/\s+/g, "-")}`}>
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between gap-2 flex-wrap mb-2">
                      <div className="flex items-center gap-2">
                        <Icon className="h-4 w-4 text-muted-foreground" />
                        <span className="text-sm font-bold">{p.name}</span>
                      </div>
                      {p.badge && <StatusBadge status={p.badge} />}
                    </div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-2xl font-extrabold">{p.rating}</span>
                      <StarRating count={Math.round(p.rating)} />
                    </div>
                    <div className="text-xs text-muted-foreground">{p.reviews} reviews</div>
                    <div className="text-xs font-semibold text-emerald-500 mt-1">+{p.newThisMonth} this month</div>
                  </CardContent>
                </Card>
              );
            })}
          </div>

          <Card>
            <CardContent className="p-4">
              <div className="text-[11px] font-bold tracking-wider uppercase text-muted-foreground mb-3">Recent Reviews</div>
              <div className="space-y-3">
                {RECENT_REVIEWS.map((review, i) => (
                  <div key={i} className="flex items-start gap-3 py-3 border-b last:border-0" data-testid={`review-${i}`}>
                    <div className="flex-shrink-0 mt-0.5">
                      <StarRating count={review.stars} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium leading-relaxed truncate">{review.excerpt}</p>
                      <div className="flex items-center gap-3 mt-1 flex-wrap">
                        <span className="text-[10px] text-muted-foreground font-semibold">{review.platform}</span>
                        <span className="text-[10px] text-muted-foreground">{review.timeAgo}</span>
                      </div>
                    </div>
                    <div className="flex-shrink-0">
                      <StatusBadge status={review.responseStatus} />
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="campaigns" className="space-y-5 mt-4">
          <h2 className="text-xl font-black" data-testid="text-campaigns-title">Review Request Campaigns</h2>

          <div className="grid gap-3 grid-cols-1 lg:grid-cols-3">
            {CAMPAIGNS.map((c, i) => (
              <Card key={i} data-testid={`campaign-${i}`}>
                <CardContent className="p-4">
                  <div className="flex items-center justify-between gap-2 flex-wrap mb-2">
                    <span className="text-sm font-bold">{c.name}</span>
                    <StatusBadge status={c.status} />
                  </div>
                  <div className="space-y-1.5 text-xs text-muted-foreground">
                    <div className="flex items-center gap-2">
                      <Clock className="h-3 w-3 flex-shrink-0" />
                      <span>{c.trigger}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Mail className="h-3 w-3 flex-shrink-0" />
                      <span>{c.channels}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <TrendingUp className="h-3 w-3 flex-shrink-0" />
                      <span>{c.conversion} conversion</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Send className="h-3 w-3 flex-shrink-0" />
                      <span>{c.sent} sent this month</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          <Card>
            <CardContent className="p-4">
              <div className="text-[11px] font-bold tracking-wider uppercase text-muted-foreground mb-3">Email Template Preview</div>
              <div className="rounded-md border p-4 space-y-3">
                <div>
                  <span className="text-[10px] font-semibold uppercase text-muted-foreground">Subject</span>
                  <p className="text-sm font-bold mt-0.5">How was your visit with Dr. Mitchell?</p>
                </div>
                <div className="text-sm text-muted-foreground leading-relaxed">
                  <p>Hi <Badge variant="secondary" className="text-[10px] no-default-hover-elevate no-default-active-elevate">{"PatientName"}</Badge>,</p>
                  <p className="mt-2">Thank you for choosing <Badge variant="secondary" className="text-[10px] no-default-hover-elevate no-default-active-elevate">{"PracticeName"}</Badge> for your recent visit with <Badge variant="secondary" className="text-[10px] no-default-hover-elevate no-default-active-elevate">{"DoctorName"}</Badge>. We hope your experience was excellent!</p>
                  <p className="mt-2">Your feedback helps us improve and helps other patients find quality dental care.</p>
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  <Button size="sm" data-testid="button-review-google">
                    <Globe className="h-3.5 w-3.5 mr-1.5" />Leave a Google Review
                  </Button>
                  <Button size="sm" variant="outline" data-testid="button-review-healthgrades">
                    <Shield className="h-3.5 w-3.5 mr-1.5" />Review on Healthgrades
                  </Button>
                </div>
                <div className="rounded-md bg-muted/50 p-3 mt-2">
                  <div className="flex items-start gap-2">
                    <AlertCircle className="h-3.5 w-3.5 text-muted-foreground mt-0.5 flex-shrink-0" />
                    <span className="text-xs text-muted-foreground">Patients scoring 9-10 get Google review link. Patients scoring 1-6 route to office manager.</span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
            {CAMPAIGN_KPIS.map((kpi) => {
              const Icon = kpi.icon;
              return (
                <Card key={kpi.label} data-testid={`campaign-kpi-${kpi.label.toLowerCase().replace(/\s+/g, "-")}`}>
                  <CardContent className="p-4">
                    <div className="flex items-center gap-2 mb-1">
                      <Icon className="h-3.5 w-3.5 text-muted-foreground" />
                      <span className="text-[10px] font-semibold tracking-wider uppercase text-muted-foreground">{kpi.label}</span>
                    </div>
                    <div className="text-2xl font-extrabold tracking-tight">{kpi.value}</div>
                    {"sub" in kpi && kpi.sub && <div className="text-xs text-muted-foreground mt-0.5">{kpi.sub}</div>}
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </TabsContent>

        <TabsContent value="sentiment" className="space-y-5 mt-4">
          <h2 className="text-xl font-black" data-testid="text-sentiment-title">AI Sentiment Analysis</h2>

          <Card>
            <CardContent className="p-4">
              <div className="text-[11px] font-bold tracking-wider uppercase text-muted-foreground mb-3">Sentiment Overview</div>
              <div className="grid gap-4 grid-cols-1 sm:grid-cols-3">
                <div>
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <div className="flex items-center gap-2">
                      <ThumbsUp className="h-3.5 w-3.5 text-emerald-500" />
                      <span className="text-sm font-bold">Positive</span>
                    </div>
                    <span className="text-sm font-extrabold text-emerald-500">89%</span>
                  </div>
                  <Progress value={89} className="h-2" />
                </div>
                <div>
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <div className="flex items-center gap-2">
                      <Activity className="h-3.5 w-3.5 text-amber-500" />
                      <span className="text-sm font-bold">Neutral</span>
                    </div>
                    <span className="text-sm font-extrabold text-amber-500">8%</span>
                  </div>
                  <Progress value={8} className="h-2" />
                </div>
                <div>
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <div className="flex items-center gap-2">
                      <ThumbsDown className="h-3.5 w-3.5 text-red-500" />
                      <span className="text-sm font-bold">Negative</span>
                    </div>
                    <span className="text-sm font-extrabold text-red-500">3%</span>
                  </div>
                  <Progress value={3} className="h-2" />
                </div>
              </div>
            </CardContent>
          </Card>

          <div className="grid gap-4 grid-cols-1 lg:grid-cols-2">
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-2 mb-3">
                  <ThumbsUp className="h-3.5 w-3.5 text-emerald-500" />
                  <span className="text-[11px] font-bold tracking-wider uppercase text-muted-foreground">Top Positive Themes</span>
                </div>
                <div className="space-y-2">
                  {POSITIVE_THEMES.map((t, i) => (
                    <div key={i} className="flex items-center justify-between gap-2 py-1.5 border-b last:border-0" data-testid={`positive-theme-${i}`}>
                      <span className="text-sm font-medium">{t.theme}</span>
                      <Badge variant="secondary" className="text-[10px] no-default-hover-elevate no-default-active-elevate bg-emerald-500/15 text-emerald-700 dark:text-emerald-400">{t.mentions} mentions</Badge>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-2 mb-3">
                  <ThumbsDown className="h-3.5 w-3.5 text-red-500" />
                  <span className="text-[11px] font-bold tracking-wider uppercase text-muted-foreground">Top Negative Themes</span>
                </div>
                <div className="space-y-2">
                  {NEGATIVE_THEMES.map((t, i) => (
                    <div key={i} className="flex items-center justify-between gap-2 py-1.5 border-b last:border-0" data-testid={`negative-theme-${i}`}>
                      <span className="text-sm font-medium">{t.theme}</span>
                      <Badge variant="secondary" className="text-[10px] no-default-hover-elevate no-default-active-elevate bg-red-500/15 text-red-700 dark:text-red-400">{t.mentions} mentions</Badge>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardContent className="p-4">
              <div className="text-[11px] font-bold tracking-wider uppercase text-muted-foreground mb-3">Word Cloud</div>
              <div className="flex flex-wrap gap-2 items-center justify-center py-4">
                {WORD_CLOUD_TAGS.map((tag, i) => (
                  <Badge key={i} variant="secondary" className={`${tag.size} no-default-hover-elevate no-default-active-elevate`} data-testid={`word-${tag.word.toLowerCase()}`}>
                    {tag.word}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4">
              <div className="flex items-start gap-3">
                <Sparkles className="h-5 w-5 text-amber-500 flex-shrink-0 mt-0.5" />
                <div>
                  <div className="text-[11px] font-bold tracking-wider uppercase text-muted-foreground mb-1">AI Insight</div>
                  <p className="text-sm leading-relaxed" data-testid="text-ai-insight">
                    Your practice excels in patient care and billing transparency. The primary area for improvement is wait times, which accounts for 53% of negative sentiment. Consider implementing a patient queue notification system.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="responses" className="space-y-5 mt-4">
          <h2 className="text-xl font-black" data-testid="text-responses-title">AI-Generated Review Responses</h2>

          <div className="space-y-3">
            {RESPONSE_QUEUE.map((r, i) => (
              <Card key={i} data-testid={`response-${i}`}>
                <CardContent className="p-4 space-y-3">
                  <div className="flex items-center justify-between gap-2 flex-wrap">
                    <div className="flex items-center gap-2">
                      <StarRating count={r.stars} />
                      <span className="text-sm font-bold">{r.reviewer}</span>
                    </div>
                    <ToneBadge tone={r.tone} />
                  </div>
                  <div className="rounded-md bg-muted/50 p-3">
                    <div className="flex items-start gap-2">
                      <MessageCircle className="h-3.5 w-3.5 text-muted-foreground mt-0.5 flex-shrink-0" />
                      <p className="text-xs text-muted-foreground leading-relaxed">{r.excerpt}</p>
                    </div>
                  </div>
                  <div className="rounded-md border p-3">
                    <div className="flex items-start gap-2">
                      <Sparkles className="h-3.5 w-3.5 text-amber-500 mt-0.5 flex-shrink-0" />
                      <p className="text-xs leading-relaxed">{r.draft}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <Button size="sm" data-testid={`button-approve-${i}`}>
                      <CheckCircle className="h-3.5 w-3.5 mr-1.5" />Approve & Send
                    </Button>
                    <Button size="sm" variant="outline" data-testid={`button-edit-${i}`}>
                      <Edit className="h-3.5 w-3.5 mr-1.5" />Edit Response
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          <div className="grid gap-3 grid-cols-1 sm:grid-cols-3">
            {RESPONSE_STATS.map((stat) => {
              const Icon = stat.icon;
              return (
                <Card key={stat.label} data-testid={`response-stat-${stat.label.toLowerCase().replace(/\s+/g, "-")}`}>
                  <CardContent className="p-4">
                    <div className="flex items-center gap-2 mb-1">
                      <Icon className="h-3.5 w-3.5 text-muted-foreground" />
                      <span className="text-[10px] font-semibold tracking-wider uppercase text-muted-foreground">{stat.label}</span>
                    </div>
                    <div className="text-2xl font-extrabold tracking-tight">{stat.value}</div>
                    {"sub" in stat && stat.sub && <div className="text-xs text-muted-foreground mt-0.5">{stat.sub}</div>}
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </TabsContent>

        <TabsContent value="analytics" className="space-y-5 mt-4">
          <h2 className="text-xl font-black" data-testid="text-analytics-title">Reputation Analytics</h2>

          <Card>
            <CardContent className="p-4">
              <div className="text-[11px] font-bold tracking-wider uppercase text-muted-foreground mb-3">Monthly Trend</div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      {["Month", "Reviews Received", "Avg Rating", "NPS", "Response Rate"].map((h) => (
                        <th key={h} className="text-left py-2 px-3 text-[10px] font-semibold tracking-wider uppercase text-muted-foreground">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {MONTHLY_TRENDS.map((row, i) => (
                      <tr key={i} className="border-b last:border-0" data-testid={`trend-row-${i}`}>
                        <td className="py-2 px-3 font-bold">{row.month}</td>
                        <td className="py-2 px-3">{row.reviews}</td>
                        <td className="py-2 px-3">{row.rating}</td>
                        <td className="py-2 px-3">{row.nps}</td>
                        <td className="py-2 px-3">{row.response}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4">
              <div className="text-[11px] font-bold tracking-wider uppercase text-muted-foreground mb-3">Review Source Breakdown</div>
              <div className="space-y-3">
                {SOURCE_BREAKDOWN.map((s, i) => (
                  <div key={i} className="flex items-center gap-3" data-testid={`source-${s.source.toLowerCase()}`}>
                    <span className="text-sm font-medium w-28 flex-shrink-0">{s.source}</span>
                    <div className="flex-1">
                      <div className="h-2 rounded-full bg-muted overflow-hidden">
                        <div className={`h-full rounded-full ${s.color} ${s.width}`} />
                      </div>
                    </div>
                    <span className="text-sm font-bold w-10 text-right">{s.pct}%</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4">
              <div className="text-[11px] font-bold tracking-wider uppercase text-muted-foreground mb-3">Competitor Benchmark</div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      {["Competitor", "Rating", "Reviews", "vs. You"].map((h) => (
                        <th key={h} className="text-left py-2 px-3 text-[10px] font-semibold tracking-wider uppercase text-muted-foreground">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {COMPETITORS.map((c, i) => (
                      <tr key={i} className="border-b last:border-0" data-testid={`competitor-${i}`}>
                        <td className="py-2 px-3 font-bold">{c.name}</td>
                        <td className="py-2 px-3">
                          <div className="flex items-center gap-1">
                            <Star className="h-3 w-3 fill-amber-400 text-amber-400" />
                            <span>{c.rating}</span>
                          </div>
                        </td>
                        <td className="py-2 px-3">{c.reviews}</td>
                        <td className="py-2 px-3"><StatusBadge status={c.comparison} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4">
              <div className="flex items-start gap-3">
                <Target className="h-5 w-5 text-emerald-500 flex-shrink-0 mt-0.5" />
                <div>
                  <div className="text-[11px] font-bold tracking-wider uppercase text-muted-foreground mb-1">Growth Target</div>
                  <p className="text-sm leading-relaxed" data-testid="text-growth-target">
                    At current pace, you'll reach 400 reviews by May 2026. To hit 500 by Q3, increase request rate by 15%.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
