import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  FileText, Send, Calendar, Search, TrendingUp, BarChart3, Eye, Clock,
  Sparkles, PenTool, Share2, Target, Globe, Hash, ArrowRight, CheckCircle,
  Edit, Copy, RefreshCcw, MessageCircle, Briefcase, MapPin,
} from "lucide-react";

type TabId = "blog" | "social" | "cases" | "seo" | "calendar";

const TABS: { id: TabId; label: string; icon: typeof FileText }[] = [
  { id: "blog", label: "Blog Generator", icon: PenTool },
  { id: "social", label: "Social Media", icon: Share2 },
  { id: "cases", label: "Case Studies", icon: Briefcase },
  { id: "seo", label: "SEO Planner", icon: Search },
  { id: "calendar", label: "Content Calendar", icon: Calendar },
];

const TOPIC_CARDS = [
  { title: "All-on-4 Insurance Billing Guide", trending: true },
  { title: "Maximizing Implant Reimbursements", trending: false },
  { title: "CDT Code Updates 2026", trending: false },
  { title: "Medical Necessity Documentation Tips", trending: false },
  { title: "Dental Implant Pre-Authorization Strategies", trending: false },
  { title: "Understanding ERA Remittance Advice", trending: false },
  { title: "Full Arch Case Acceptance Scripts", trending: false },
  { title: "HIPAA Compliance for Billing Staff", trending: false },
];

const ARTICLE_PREVIEW = {
  title: "The Complete Guide to All-on-4 Dental Implant Insurance Billing in 2026",
  author: "AI Content Engine",
  date: "Feb 15, 2026",
  readingTime: "12 min",
  seoScore: 94,
  status: "Draft",
  wordCount: "2,847",
  keywords: "all-on-4 insurance billing, dental implant coverage, full arch billing",
  paragraphs: [
    "Navigating insurance billing for All-on-4 dental implant procedures requires a thorough understanding of both dental and medical coding systems. As we move into 2026, practices that master the nuances of cross-coding between CDT and CPT systems will see significantly higher reimbursement rates. The key lies in understanding when to bill dental insurance versus medical insurance, and how to properly document medical necessity for full arch rehabilitation.",
    "The foundation of successful All-on-4 billing starts with proper pre-authorization. Before scheduling any surgical procedure, your billing team should submit detailed pre-authorization requests that include comprehensive diagnostic records, CBCT imaging reports, periodontal charting, and a narrative explaining why conventional prosthetics are insufficient. Insurance companies are increasingly requiring this level of documentation, and practices that provide it upfront experience 40% fewer claim denials.",
    "When coding All-on-4 procedures, it is essential to break down the treatment into its component parts. The surgical phase typically involves codes D7210 (surgical extraction), D6010 (implant body placement), and D7953 (bone replacement graft). The prosthetic phase uses D6114 (implant abutment) and D6119 (implant supported prosthesis). Each code must be accompanied by tooth-specific documentation and clinical photographs showing pre-operative conditions.",
    "For practices looking to maximize reimbursement, consider the medical crossover billing opportunity. Many All-on-4 cases qualify for medical insurance coverage when the procedure addresses conditions such as trauma, tumor resection, or severe atrophy that impacts the patient's ability to maintain adequate nutrition. Proper use of ICD-10 codes like K08.1 (complete loss of teeth due to trauma) and M26.69 (other dentofacial anomalies) can unlock medical benefits that significantly reduce patient out-of-pocket costs.",
  ],
};

const RECENT_ARTICLES = [
  { title: "How to Appeal Denied Dental Implant Claims", status: "Published", date: "Feb 12", views: 1240 },
  { title: "2026 CDT Code Changes for Implant Procedures", status: "Published", date: "Feb 8", views: 2180 },
  { title: "Medical vs Dental Insurance for Full Arch Cases", status: "Published", date: "Feb 3", views: 890 },
  { title: "Building a Case for Medical Necessity", status: "Draft", date: "", views: 0 },
  { title: "ERA Processing Best Practices", status: "Scheduled", date: "Feb 18", views: 0 },
];

type PlatformId = "facebook" | "instagram" | "linkedin" | "google";

const PLATFORM_TABS: { id: PlatformId; label: string; icon: typeof Globe }[] = [
  { id: "facebook", label: "Facebook", icon: Globe },
  { id: "instagram", label: "Instagram", icon: MessageCircle },
  { id: "linkedin", label: "LinkedIn", icon: Briefcase },
  { id: "google", label: "Google Business", icon: MapPin },
];

const PLATFORM_POSTS: Record<PlatformId, { content: string; hashtags: string }> = {
  facebook: {
    content: "Did you know that proper documentation can increase your dental implant insurance approval rate by up to 40%? Our latest guide covers the essential steps every billing team needs to master for All-on-4 cases in 2026. From pre-authorization to final claim submission, we break down the entire process.",
    hashtags: "#DentalBilling #ImplantDentistry #DentalInsurance #AllOn4",
  },
  instagram: {
    content: "Struggling with dental implant claim denials? You are not alone. 3 out of 5 implant claims are initially denied due to insufficient documentation. Swipe to learn our top 5 tips for getting claims approved on the first submission.",
    hashtags: "#DentalBilling #ImplantSuccess #DentalPractice #BillingTips",
  },
  linkedin: {
    content: "The dental implant billing landscape is evolving rapidly. With 2026 CDT code updates and increasing insurance requirements, practices need to stay ahead of the curve. I have compiled our team's top strategies for maximizing reimbursements while maintaining compliance. Key insight: medical crossover billing for qualified cases can increase collections by 25-35%.",
    hashtags: "#DentalIndustry #HealthcareBilling #PracticeManagement",
  },
  google: {
    content: "Our practice utilizes the latest dental implant billing technology to ensure maximum insurance coverage for our patients. We handle all pre-authorizations and insurance coordination so you can focus on your smile transformation. Schedule a free consultation today.",
    hashtags: "",
  },
};

const POST_QUEUE = [
  { title: "All-on-4 Insurance Guide Promo", platform: "Facebook", date: "Feb 16", status: "Scheduled" },
  { title: "Implant Billing Tips Carousel", platform: "Instagram", date: "Feb 17", status: "Scheduled" },
  { title: "CDT Code Update Summary", platform: "LinkedIn", date: "Feb 18", status: "Scheduled" },
  { title: "Patient Testimonial - Insurance Success", platform: "Facebook", date: "Feb 14", status: "Posted" },
  { title: "Practice Update - New Technology", platform: "Google Business", date: "Feb 13", status: "Posted" },
  { title: "ERA Processing Tips Infographic", platform: "Instagram", date: "Feb 19", status: "Draft" },
];

const ENGAGEMENT_METRICS = [
  { label: "Total Reach", value: "12.4K", icon: Eye },
  { label: "Engagement Rate", value: "4.2%", icon: TrendingUp },
  { label: "Click-throughs", value: "342", icon: ArrowRight },
  { label: "Best Time to Post", value: "Tue/Thu 10am", icon: Clock },
];

const CASE_STUDIES = [
  {
    title: "Full Arch Transformation: 68-Year-Old Regains Confidence",
    views: 4200,
    status: "Published",
    procedure: "All-on-4 Full Arch Rehabilitation",
    insuranceSaved: "$12,400",
    satisfaction: 98,
  },
  {
    title: "From Dentures to All-on-4: A Patient Journey",
    views: 2800,
    status: "Published",
    procedure: "Full Arch Implant Conversion",
    insuranceSaved: "$8,900",
    satisfaction: 96,
  },
  {
    title: "Complex Bone Graft + Implant: Insurance Approval Success",
    views: 0,
    status: "Draft",
    procedure: "Bone Graft with Implant Placement",
    insuranceSaved: "$6,200",
    satisfaction: 94,
  },
];

const SEO_KEYWORDS = [
  { keyword: "dental implant cost", volume: 18100, difficulty: 72, cpc: "$14.20" },
  { keyword: "all-on-4 dental implants", volume: 12400, difficulty: 65, cpc: "$22.50" },
  { keyword: "dental implant insurance", volume: 8200, difficulty: 58, cpc: "$11.80" },
  { keyword: "full arch dental implants", volume: 6800, difficulty: 52, cpc: "$18.90" },
  { keyword: "dental implant billing codes", volume: 2400, difficulty: 38, cpc: "$8.40" },
  { keyword: "CDT codes dental implants", volume: 1800, difficulty: 32, cpc: "$6.20" },
  { keyword: "medical necessity dental implants", volume: 1200, difficulty: 28, cpc: "$9.80" },
  { keyword: "dental implant pre authorization", volume: 980, difficulty: 24, cpc: "$7.50" },
];

const CONTENT_GAP_OPPORTUNITIES = [
  { topic: "Insurance appeal letter templates for implants", competition: "Low", potential: "High" },
  { topic: "Step-by-step medical crossover billing guide", competition: "Low", potential: "High" },
  { topic: "CDT vs CPT coding comparison for implants", competition: "Medium", potential: "High" },
  { topic: "Patient financing vs insurance for full arch cases", competition: "Low", potential: "Medium" },
];

const CALENDAR_WEEK = [
  { day: "Mon", items: [{ title: "Blog post draft", type: "Blog" }, { title: "Instagram post", type: "Social" }] },
  { day: "Tue", items: [{ title: "LinkedIn article", type: "Blog" }, { title: "Facebook ad", type: "Social" }] },
  { day: "Wed", items: [{ title: "Case study publish", type: "Case Study" }, { title: "Google Business update", type: "Social" }] },
  { day: "Thu", items: [{ title: "Email newsletter", type: "Email" }, { title: "Blog post", type: "Blog" }] },
  { day: "Fri", items: [{ title: "Week recap post", type: "Social" }, { title: "Review response", type: "Social" }] },
];

const CALENDAR_KPIS = [
  { label: "Total Content Pieces", value: "42" },
  { label: "Published", value: "28" },
  { label: "Scheduled", value: "8" },
  { label: "Drafts", value: "6" },
  { label: "Avg Engagement", value: "3.8%" },
];

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    published: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
    posted: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
    draft: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
    scheduled: "bg-blue-500/15 text-blue-700 dark:text-blue-400",
  };
  const cls = map[status.toLowerCase()] || "bg-muted text-muted-foreground";
  return (
    <Badge variant="secondary" className={`text-[10px] no-default-hover-elevate no-default-active-elevate ${cls}`} data-testid={`badge-status-${status.toLowerCase()}`}>
      {status}
    </Badge>
  );
}

function getDifficultyColor(d: number): string {
  if (d >= 60) return "text-red-600 dark:text-red-400";
  if (d >= 40) return "text-amber-600 dark:text-amber-400";
  return "text-emerald-600 dark:text-emerald-400";
}

function getDifficultyLabel(d: number): string {
  if (d >= 60) return "Hard";
  if (d >= 40) return "Medium";
  return "Easy";
}

const typeColorMap: Record<string, string> = {
  "Blog": "bg-blue-500/15 text-blue-700 dark:text-blue-400",
  "Social": "bg-purple-500/15 text-purple-700 dark:text-purple-400",
  "Case Study": "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
  "Email": "bg-amber-500/15 text-amber-700 dark:text-amber-400",
};

export default function ContentEnginePage() {
  const [activeTab, setActiveTab] = useState<TabId>("blog");
  const [activePlatform, setActivePlatform] = useState<PlatformId>("facebook");

  return (
    <div className="space-y-5" data-testid="content-engine-page">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight" data-testid="text-page-title">AI Content Engine</h1>
          <p className="text-sm text-muted-foreground">AI-powered content marketing management for your practice</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            return (
              <Button
                key={tab.id}
                variant={activeTab === tab.id ? "default" : "outline"}
                size="sm"
                onClick={() => setActiveTab(tab.id)}
                data-testid={`tab-${tab.id}`}
                className="toggle-elevate"
              >
                <Icon className="h-3.5 w-3.5 mr-1.5" />
                {tab.label}
              </Button>
            );
          })}
        </div>
      </div>

      {activeTab === "blog" && <BlogGeneratorTab />}
      {activeTab === "social" && <SocialMediaTab activePlatform={activePlatform} setActivePlatform={setActivePlatform} />}
      {activeTab === "cases" && <CaseStudiesTab />}
      {activeTab === "seo" && <SEOPlannerTab />}
      {activeTab === "calendar" && <ContentCalendarTab />}
    </div>
  );
}

function BlogGeneratorTab() {
  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-xl font-black" data-testid="text-blog-title">AI Blog & Article Generator</h2>
        <p className="text-sm text-muted-foreground">Generate SEO-optimized dental billing content with AI</p>
      </div>

      <div>
        <div className="text-xs font-bold tracking-wider uppercase text-muted-foreground mb-3">Select a Topic</div>
        <div className="grid gap-3 grid-cols-2 md:grid-cols-4">
          {TOPIC_CARDS.map((topic, i) => (
            <Card key={i} className="hover-elevate cursor-pointer" data-testid={`topic-card-${i}`}>
              <CardContent className="p-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <FileText className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                    <span className="text-sm font-semibold leading-tight">{topic.title}</span>
                  </div>
                  {topic.trending && (
                    <Badge variant="secondary" className="text-[9px] no-default-hover-elevate no-default-active-elevate bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 flex-shrink-0">
                      <TrendingUp className="h-3 w-3 mr-0.5" />Trending
                    </Badge>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      <Card data-testid="article-preview">
        <CardContent className="p-6 space-y-4">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div className="space-y-2">
              <h3 className="text-lg font-extrabold leading-tight">{ARTICLE_PREVIEW.title}</h3>
              <div className="flex items-center gap-3 flex-wrap text-xs text-muted-foreground">
                <span className="flex items-center gap-1"><Sparkles className="h-3 w-3" />{ARTICLE_PREVIEW.author}</span>
                <span className="flex items-center gap-1"><Calendar className="h-3 w-3" />{ARTICLE_PREVIEW.date}</span>
                <span className="flex items-center gap-1"><Clock className="h-3 w-3" />{ARTICLE_PREVIEW.readingTime}</span>
                <span className="flex items-center gap-1"><FileText className="h-3 w-3" />{ARTICLE_PREVIEW.wordCount} words</span>
              </div>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <Badge variant="secondary" className="no-default-hover-elevate no-default-active-elevate bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 text-xs">
                SEO: {ARTICLE_PREVIEW.seoScore}/100
              </Badge>
              <StatusBadge status={ARTICLE_PREVIEW.status} />
            </div>
          </div>

          <div className="text-xs text-muted-foreground">
            <span className="font-semibold">Target Keywords:</span> {ARTICLE_PREVIEW.keywords}
          </div>

          <div className="space-y-3 text-sm leading-relaxed text-muted-foreground border-t pt-4">
            {ARTICLE_PREVIEW.paragraphs.map((p, i) => (
              <p key={i}>{p}</p>
            ))}
          </div>

          <div className="flex items-center gap-2 flex-wrap pt-2 border-t">
            <Button size="sm" data-testid="button-publish-blog">
              <Send className="h-3.5 w-3.5 mr-1.5" />Publish to Blog
            </Button>
            <Button size="sm" variant="outline" data-testid="button-edit-draft">
              <Edit className="h-3.5 w-3.5 mr-1.5" />Edit Draft
            </Button>
            <Button size="sm" variant="outline" data-testid="button-regenerate">
              <RefreshCcw className="h-3.5 w-3.5 mr-1.5" />Regenerate
            </Button>
            <Button size="sm" variant="outline" data-testid="button-copy-html">
              <Copy className="h-3.5 w-3.5 mr-1.5" />Copy HTML
            </Button>
          </div>
        </CardContent>
      </Card>

      <div>
        <div className="text-xs font-bold tracking-wider uppercase text-muted-foreground mb-3">Recent Articles</div>
        <Card>
          <CardContent className="p-0">
            <div className="divide-y">
              {RECENT_ARTICLES.map((article, i) => (
                <div key={i} className="flex items-center justify-between gap-4 flex-wrap px-4 py-3" data-testid={`recent-article-${i}`}>
                  <div className="flex items-center gap-3 min-w-0">
                    <FileText className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                    <span className="text-sm font-semibold truncate">{article.title}</span>
                  </div>
                  <div className="flex items-center gap-3 flex-shrink-0">
                    <StatusBadge status={article.status} />
                    {article.date && <span className="text-xs text-muted-foreground">{article.date}</span>}
                    <span className="text-xs text-muted-foreground flex items-center gap-1">
                      <Eye className="h-3 w-3" />{article.views.toLocaleString()}
                    </span>
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

function SocialMediaTab({ activePlatform, setActivePlatform }: { activePlatform: PlatformId; setActivePlatform: (p: PlatformId) => void }) {
  const currentPost = PLATFORM_POSTS[activePlatform];

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-xl font-black" data-testid="text-social-title">Social Media Post Generator</h2>
        <p className="text-sm text-muted-foreground">Create engaging posts for practice marketing</p>
      </div>

      <div className="grid gap-4 grid-cols-2 md:grid-cols-4">
        {ENGAGEMENT_METRICS.map((metric, i) => {
          const Icon = metric.icon;
          return (
            <Card key={i} data-testid={`metric-${metric.label.toLowerCase().replace(/\s+/g, "-")}`}>
              <CardContent className="p-4">
                <div className="flex items-center gap-2 mb-1">
                  <Icon className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="text-[10px] font-semibold tracking-wider uppercase text-muted-foreground">{metric.label}</span>
                </div>
                <div className="text-2xl font-extrabold tracking-tight">{metric.value}</div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        {PLATFORM_TABS.map((p) => {
          const Icon = p.icon;
          return (
            <Button
              key={p.id}
              variant={activePlatform === p.id ? "default" : "outline"}
              size="sm"
              onClick={() => setActivePlatform(p.id)}
              data-testid={`platform-${p.id}`}
              className="toggle-elevate"
            >
              <Icon className="h-3.5 w-3.5 mr-1.5" />{p.label}
            </Button>
          );
        })}
      </div>

      <Card data-testid="social-post-preview">
        <CardContent className="p-5 space-y-3">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-muted-foreground" />
            <span className="text-xs font-bold tracking-wider uppercase text-muted-foreground">AI Generated Post</span>
          </div>
          <p className="text-sm leading-relaxed">{currentPost.content}</p>
          {currentPost.hashtags && (
            <p className="text-xs text-muted-foreground flex items-center gap-1">
              <Hash className="h-3 w-3" />{currentPost.hashtags}
            </p>
          )}
          <div className="flex items-center gap-2 flex-wrap pt-2">
            <Button size="sm" data-testid="button-schedule-post">
              <Send className="h-3.5 w-3.5 mr-1.5" />Schedule Post
            </Button>
            <Button size="sm" variant="outline" data-testid="button-edit-post">
              <Edit className="h-3.5 w-3.5 mr-1.5" />Edit
            </Button>
            <Button size="sm" variant="outline" data-testid="button-regenerate-post">
              <RefreshCcw className="h-3.5 w-3.5 mr-1.5" />Regenerate
            </Button>
          </div>
        </CardContent>
      </Card>

      <div>
        <div className="text-xs font-bold tracking-wider uppercase text-muted-foreground mb-3">Post Queue</div>
        <Card>
          <CardContent className="p-0">
            <div className="divide-y">
              {POST_QUEUE.map((post, i) => (
                <div key={i} className="flex items-center justify-between gap-4 flex-wrap px-4 py-3" data-testid={`post-queue-${i}`}>
                  <div className="flex items-center gap-3 min-w-0">
                    <Share2 className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                    <span className="text-sm font-semibold truncate">{post.title}</span>
                  </div>
                  <div className="flex items-center gap-3 flex-shrink-0">
                    <Badge variant="secondary" className="text-[10px] no-default-hover-elevate no-default-active-elevate">{post.platform}</Badge>
                    <span className="text-xs text-muted-foreground">{post.date}</span>
                    <StatusBadge status={post.status} />
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

function CaseStudiesTab() {
  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-xl font-black" data-testid="text-cases-title">Case Study Builder</h2>
          <p className="text-sm text-muted-foreground">Transform patient outcomes into compelling marketing stories</p>
        </div>
        <Button size="sm" data-testid="button-new-case-study">
          <Sparkles className="h-3.5 w-3.5 mr-1.5" />New Case Study
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {CASE_STUDIES.map((cs, i) => (
          <Card key={i} className="hover-elevate" data-testid={`case-study-${i}`}>
            <CardContent className="p-0">
              <div className="h-36 bg-muted flex items-center justify-center border-b">
                <div className="text-center">
                  <Eye className="h-8 w-8 text-muted-foreground/30 mx-auto mb-1" />
                  <span className="text-[10px] text-muted-foreground">Before / After</span>
                </div>
              </div>
              <div className="p-4 space-y-3">
                <div className="flex items-start justify-between gap-2">
                  <h3 className="text-sm font-bold leading-tight">{cs.title}</h3>
                  <StatusBadge status={cs.status} />
                </div>
                <div className="space-y-1.5 text-xs text-muted-foreground">
                  <div className="flex items-center justify-between gap-2">
                    <span>Procedure</span>
                    <span className="font-semibold text-foreground">{cs.procedure}</span>
                  </div>
                  <div className="flex items-center justify-between gap-2">
                    <span>Insurance Saved</span>
                    <span className="font-semibold text-emerald-600 dark:text-emerald-400">{cs.insuranceSaved}</span>
                  </div>
                  <div className="flex items-center justify-between gap-2">
                    <span>Satisfaction</span>
                    <span className="font-semibold text-foreground">{cs.satisfaction}/100</span>
                  </div>
                </div>
                <div className="flex items-center justify-between gap-2 pt-1">
                  <span className="text-xs text-muted-foreground flex items-center gap-1">
                    <Eye className="h-3 w-3" />{cs.views.toLocaleString()} views
                  </span>
                  <Button size="sm" variant="outline" data-testid={`button-view-case-${i}`}>
                    View <ArrowRight className="h-3 w-3 ml-1" />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

function SEOPlannerTab() {
  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-xl font-black" data-testid="text-seo-title">SEO Keyword Planner</h2>
        <p className="text-sm text-muted-foreground">Find high-value keywords for dental implant content</p>
      </div>

      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  {["Keyword", "Volume", "Difficulty", "CPC", "Action"].map((h) => (
                    <th key={h} className="px-4 py-3 text-left text-[10px] font-bold tracking-wider uppercase text-muted-foreground">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {SEO_KEYWORDS.map((kw, i) => (
                  <tr key={i} className="border-b last:border-0" data-testid={`seo-keyword-${i}`}>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <Search className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />
                        <span className="font-semibold">{kw.keyword}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 font-semibold">{kw.volume.toLocaleString()}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="w-16">
                          <Progress value={kw.difficulty} className="h-1.5" />
                        </div>
                        <span className={`text-xs font-semibold ${getDifficultyColor(kw.difficulty)}`}>
                          {kw.difficulty} - {getDifficultyLabel(kw.difficulty)}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3 font-semibold">{kw.cpc}</td>
                    <td className="px-4 py-3">
                      <Button size="sm" variant="outline" data-testid={`button-create-content-${i}`}>
                        <PenTool className="h-3 w-3 mr-1" />Create Content
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <Card data-testid="content-gap-analysis">
        <CardContent className="p-5 space-y-3">
          <div className="flex items-center gap-2 mb-1">
            <Target className="h-4 w-4 text-muted-foreground" />
            <span className="text-xs font-bold tracking-wider uppercase text-muted-foreground">Content Gap Analysis</span>
          </div>
          <p className="text-sm text-muted-foreground">Opportunities identified where competitors have content but you do not:</p>
          <div className="space-y-2">
            {CONTENT_GAP_OPPORTUNITIES.map((opp, i) => (
              <div key={i} className="flex items-center justify-between gap-4 flex-wrap py-2 border-b last:border-0" data-testid={`gap-opportunity-${i}`}>
                <div className="flex items-center gap-2 min-w-0">
                  <Sparkles className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />
                  <span className="text-sm font-semibold">{opp.topic}</span>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <Badge variant="secondary" className="text-[10px] no-default-hover-elevate no-default-active-elevate">Competition: {opp.competition}</Badge>
                  <Badge variant="secondary" className={`text-[10px] no-default-hover-elevate no-default-active-elevate ${opp.potential === "High" ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400" : "bg-amber-500/15 text-amber-700 dark:text-amber-400"}`}>
                    Potential: {opp.potential}
                  </Badge>
                  <Button size="sm" variant="outline" data-testid={`button-write-${i}`}>
                    <PenTool className="h-3 w-3 mr-1" />Write
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function ContentCalendarTab() {
  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-xl font-black" data-testid="text-calendar-title">Content Calendar</h2>
          <p className="text-sm text-muted-foreground">Plan and schedule your content strategy</p>
        </div>
        <Button size="sm" data-testid="button-add-content">
          <Calendar className="h-3.5 w-3.5 mr-1.5" />Add Content
        </Button>
      </div>

      <div className="grid gap-3 grid-cols-2 md:grid-cols-5">
        {CALENDAR_KPIS.map((kpi, i) => (
          <Card key={i} data-testid={`calendar-kpi-${i}`}>
            <CardContent className="p-4">
              <div className="text-[10px] font-semibold tracking-wider uppercase text-muted-foreground mb-1">{kpi.label}</div>
              <div className="text-2xl font-extrabold tracking-tight">{kpi.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div>
        <div className="text-xs font-bold tracking-wider uppercase text-muted-foreground mb-3">This Week - Feb 10-14, 2026</div>
        <div className="grid gap-3 grid-cols-1 md:grid-cols-5">
          {CALENDAR_WEEK.map((day, di) => (
            <Card key={di} data-testid={`calendar-day-${day.day.toLowerCase()}`}>
              <CardContent className="p-4">
                <div className="text-sm font-bold mb-3">{day.day}</div>
                <div className="space-y-2">
                  {day.items.map((item, ii) => (
                    <div key={ii} className="flex items-start gap-2">
                      <CheckCircle className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0 mt-0.5" />
                      <div>
                        <div className="text-xs font-semibold leading-tight">{item.title}</div>
                        <Badge variant="secondary" className={`text-[9px] mt-1 no-default-hover-elevate no-default-active-elevate ${typeColorMap[item.type] || ""}`}>
                          {item.type}
                        </Badge>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      <Card data-testid="monthly-overview">
        <CardContent className="p-5">
          <div className="flex items-center gap-2 mb-4">
            <BarChart3 className="h-4 w-4 text-muted-foreground" />
            <span className="text-xs font-bold tracking-wider uppercase text-muted-foreground">Monthly Content Overview</span>
          </div>
          <div className="grid gap-4 grid-cols-2 md:grid-cols-4">
            <div>
              <div className="text-xs text-muted-foreground mb-1">Blog Posts</div>
              <div className="flex items-center gap-2">
                <Progress value={75} className="h-1.5 flex-1" />
                <span className="text-xs font-semibold">12/16</span>
              </div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground mb-1">Social Posts</div>
              <div className="flex items-center gap-2">
                <Progress value={65} className="h-1.5 flex-1" />
                <span className="text-xs font-semibold">18/28</span>
              </div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground mb-1">Case Studies</div>
              <div className="flex items-center gap-2">
                <Progress value={50} className="h-1.5 flex-1" />
                <span className="text-xs font-semibold">2/4</span>
              </div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground mb-1">Email Campaigns</div>
              <div className="flex items-center gap-2">
                <Progress value={80} className="h-1.5 flex-1" />
                <span className="text-xs font-semibold">4/5</span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}