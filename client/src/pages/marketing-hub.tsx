import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Progress } from "@/components/ui/progress";
import {
  Megaphone, Star, TrendingUp, Users, DollarSign, CheckCircle, Clock,
  FileEdit, Lightbulb, ThumbsUp, ThumbsDown, Minus, MessageSquare,
  Bot, BarChart3, Globe, Instagram, Mail, PlusCircle, Award, Send,
  Sparkles, PenTool, RefreshCw, Target,
} from "lucide-react";

// ─── Channels / Overview Tab ──────────────────────────────────────────────────
const channels = [
  { name: "Google Ads",        spend: "$3,200", patients: 14, cpa: "$229", roi: "8.2x", trend: "up" },
  { name: "Meta/Instagram",    spend: "$2,100", patients: 8,  cpa: "$263", roi: "5.4x", trend: "up" },
  { name: "Google Organic",    spend: "$800",   patients: 6,  cpa: "$133", roi: "12.1x",trend: "up" },
  { name: "Patient Referrals", spend: "$1,500", patients: 6,  cpa: "$250", roi: "9.8x", trend: "flat" },
  { name: "Direct Mail",       spend: "$600",   patients: 2,  cpa: "$300", roi: "4.2x", trend: "down" },
  { name: "Walk-ins",          spend: "$0",     patients: 2,  cpa: "$0",   roi: "∞",    trend: "flat" },
];

const calendar = [
  { day: "Mon", content: "Before/after implant photo",      platform: "IG+FB",    status: "posted",    },
  { day: "Tue", content: "3 Signs You Need RCT video",      platform: "TikTok",   status: "scheduled", },
  { day: "Wed", content: "Patient testimonial — Diana P.",  platform: "IG+FB",    status: "scheduled", },
  { day: "Thu", content: "Blog: Implants vs Bridges",       platform: "Website",  status: "draft",     },
  { day: "Fri", content: "Team BTS reel",                   platform: "IG+TikTok",status: "idea",      },
];

function StatusIcon({ status }: { status: string }) {
  if (status === "posted")    return <CheckCircle className="h-3 w-3 text-emerald-600" />;
  if (status === "scheduled") return <Clock className="h-3 w-3 text-blue-600" />;
  if (status === "draft")     return <FileEdit className="h-3 w-3 text-amber-600" />;
  return <Lightbulb className="h-3 w-3 text-muted-foreground" />;
}

function ChannelsTab() {
  const totalSpend   = channels.reduce((s, c) => s + parseFloat(c.spend.replace(/[$,]/g, "")), 0);
  const totalPatients = channels.reduce((s, c) => s + c.patients, 0);
  const avgCPA = totalSpend / (totalPatients || 1);

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Total Ad Spend/Mo",  value: `$${totalSpend.toLocaleString()}`, color: "text-foreground" },
          { label: "New Patients/Mo",    value: totalPatients,                      color: "text-emerald-600" },
          { label: "Avg Cost/Patient",   value: `$${avgCPA.toFixed(0)}`,            color: "text-blue-600" },
          { label: "Best Channel ROI",   value: "12.1x (SEO)",                      color: "text-emerald-600" },
        ].map(k => (
          <Card key={k.label}>
            <CardContent className="pt-3 pb-3">
              <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-0.5">{k.label}</div>
              <div className={`text-xl font-bold font-mono ${k.color}`}>{String(k.value)}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">Channel Performance</CardTitle></CardHeader>
          <CardContent className="pt-0 overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b">
                  {["Channel","Spend","Patients","CPA","ROI","Trend"].map(h => (
                    <th key={h} className="py-2 px-2 text-left font-semibold text-muted-foreground">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {channels.map((c, i) => (
                  <tr key={i} className="border-b hover:bg-muted/30">
                    <td className="py-2 px-2 font-medium">{c.name}</td>
                    <td className="py-2 px-2 font-mono">{c.spend}</td>
                    <td className="py-2 px-2 font-semibold">{c.patients}</td>
                    <td className="py-2 px-2">{c.cpa}</td>
                    <td className="py-2 px-2 font-bold text-emerald-600">{c.roi}</td>
                    <td className="py-2 px-2">
                      <TrendingUp className={`h-3 w-3 ${c.trend === "up" ? "text-emerald-500" : c.trend === "down" ? "text-red-500 rotate-180" : "text-muted-foreground"}`} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">This Week's Content Calendar</CardTitle></CardHeader>
          <CardContent className="pt-0 space-y-2">
            {calendar.map((item, i) => (
              <div key={i} className="flex items-center gap-3 p-2 border rounded-lg">
                <div className="w-8 text-[10px] font-semibold text-muted-foreground">{item.day}</div>
                <StatusIcon status={item.status} />
                <div className="flex-1 min-w-0">
                  <div className="text-xs truncate">{item.content}</div>
                  <div className="text-[10px] text-muted-foreground">{item.platform}</div>
                </div>
                <Badge variant="outline" className="text-[9px] px-1 capitalize">{item.status}</Badge>
              </div>
            ))}
            <Button size="sm" variant="outline" className="w-full gap-1.5 h-7 text-xs mt-1" data-testid="btn-add-content">
              <PlusCircle className="h-3.5 w-3.5" /> Add Content
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

// ─── Content Engine Tab ───────────────────────────────────────────────────────
const CONTENT_IDEAS = [
  { type: "Blog",      title: "All-on-4 vs All-on-6: Which Is Right for You?",     keywords: 1840, difficulty: "Low",  status: "draft"    },
  { type: "Video",     title: "Day in the Life of an Implant Patient",               keywords: null, difficulty: null,   status: "idea"     },
  { type: "Blog",      title: "How Medical Insurance Covers Dental Implants",        keywords: 2100, difficulty: "Med",  status: "published"},
  { type: "Social",    title: "Before/After: Margaret's Full Arch Transformation",   keywords: null, difficulty: null,   status: "posted"   },
  { type: "Email",     title: "6-Month Recall: Is Your Implant Performing?",         keywords: null, difficulty: null,   status: "scheduled"},
  { type: "Blog",      title: "ICD-10 Medical Necessity for Bone Grafting",          keywords: 890,  difficulty: "High", status: "draft"    },
];

function ContentEngineTab() {
  const [prompt, setPrompt] = useState("");
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState("");

  async function generateContent() {
    if (!prompt) return;
    setGenerating(true);
    setTimeout(() => {
      setResult(`# ${prompt}\n\n## Introduction\nFull arch dental implants represent one of the most transformative procedures in modern dentistry, offering patients a complete smile restoration that looks, feels, and functions like natural teeth.\n\n## Key Benefits\n- **Permanent solution**: Unlike dentures, implants integrate with the jawbone\n- **Preserved bone density**: Stimulates natural bone growth to prevent deterioration\n- **Medical insurance crossover**: Many All-on-4 cases qualify for medical billing under CPT codes\n\n## The Procedure\nTypically completed in a single surgical session, the All-on-4 protocol uses four strategically placed implants to support a full arch prosthesis...\n\n[Continue writing...]`);
      setGenerating(false);
    }, 1800);
  }

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* AI Content Generator */}
        <div className="lg:col-span-1 space-y-3">
          <h3 className="font-semibold text-sm flex items-center gap-2"><Sparkles className="h-4 w-4 text-primary" /> AI Content Generator</h3>
          <div className="space-y-2">
            <Input value={prompt} onChange={e => setPrompt(e.target.value)} className="h-8 text-xs" placeholder="Blog topic, email subject, social idea…" data-testid="input-content-prompt" />
            <div className="grid grid-cols-2 gap-1.5">
              {["Blog post","Social caption","Email campaign","Patient FAQ","Video script","Press release"].map(t => (
                <button key={t} onClick={() => setPrompt(t)} className="text-[10px] p-1.5 border rounded hover:border-primary/50 text-left text-muted-foreground hover:text-foreground transition-colors">{t}</button>
              ))}
            </div>
            <Button onClick={generateContent} disabled={generating || !prompt} className="w-full gap-2 h-8 text-xs" data-testid="btn-generate-content">
              {generating ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <PenTool className="h-3.5 w-3.5" />}
              {generating ? "Generating…" : "Generate Content"}
            </Button>
          </div>
          {result && (
            <div className="border rounded-lg p-3 bg-muted/30 max-h-64 overflow-y-auto">
              <pre className="text-[10px] whitespace-pre-wrap leading-relaxed">{result}</pre>
            </div>
          )}
        </div>

        {/* Content pipeline */}
        <div className="lg:col-span-2 space-y-3">
          <h3 className="font-semibold text-sm">Content Pipeline</h3>
          <div className="space-y-2">
            {CONTENT_IDEAS.map((item, i) => (
              <div key={i} className="flex items-center gap-3 p-3 border rounded-lg" data-testid={`content-${i}`}>
                <Badge variant="outline" className="text-[9px] px-1.5 shrink-0">{item.type}</Badge>
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-medium truncate">{item.title}</div>
                  {item.keywords && <div className="text-[10px] text-muted-foreground">{item.keywords.toLocaleString()} searches/mo · Difficulty: {item.difficulty}</div>}
                </div>
                <Badge className={`text-[9px] border px-1.5 shrink-0
                  ${item.status === "published" || item.status === "posted" ? "bg-emerald-100 text-emerald-700 border-emerald-300"
                  : item.status === "scheduled" ? "bg-blue-100 text-blue-700 border-blue-300"
                  : item.status === "draft" ? "bg-amber-100 text-amber-700 border-amber-300"
                  : "bg-gray-100 text-gray-600 border-gray-300"}`}>{item.status}</Badge>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Reputation Tab ───────────────────────────────────────────────────────────
const reviews = [
  { platform: "Google",  name: "Margaret Sullivan", stars: 5, text: "Best dental experience of my life! Dr. Blake and the entire team were exceptional. My implants look perfect.", date: "3 days ago", replied: true },
  { platform: "Yelp",    name: "Robert Kim",        stars: 5, text: "Very professional. The implant process was explained step by step. Great communication throughout.", date: "1 week ago", replied: true },
  { platform: "Google",  name: "Diana Patel",       stars: 4, text: "Great care overall. Only reason not 5 stars is the wait time on my first appointment.", date: "2 weeks ago", replied: false },
  { platform: "Facebook",name: "Tom Davis",         stars: 3, text: "Billing process was confusing. Good clinical work though.", date: "3 weeks ago", replied: false },
  { platform: "Google",  name: "James Okafor",      stars: 5, text: "Incredible results. I can smile again after years of hiding my teeth. Worth every penny.", date: "1 month ago", replied: true },
];

function ReputationTab() {
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Google Rating",   value: "4.8 ★", color: "text-amber-500"   },
          { label: "Total Reviews",   value: "284",    color: "text-foreground"  },
          { label: "Reviews This Mo", value: "28",     color: "text-emerald-600" },
          { label: "Response Rate",   value: "96%",    color: "text-primary"     },
        ].map(k => (
          <Card key={k.label}>
            <CardContent className="pt-3 pb-3">
              <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-0.5">{k.label}</div>
              <div className={`text-xl font-bold font-mono ${k.color}`}>{k.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="space-y-3">
        {reviews.map((r, i) => (
          <div key={i} className="p-4 border rounded-xl" data-testid={`review-${i}`}>
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-2">
                <div className="flex gap-0.5">
                  {[...Array(5)].map((_, s) => (
                    <Star key={s} className={`h-3.5 w-3.5 ${s < r.stars ? "text-amber-400 fill-amber-400" : "text-gray-200"}`} />
                  ))}
                </div>
                <span className="font-semibold text-xs">{r.name}</span>
                <Badge variant="outline" className="text-[9px] px-1">{r.platform}</Badge>
              </div>
              <span className="text-[10px] text-muted-foreground shrink-0">{r.date}</span>
            </div>
            <p className="text-xs text-muted-foreground mt-2">{r.text}</p>
            {!r.replied && (
              <div className="flex gap-2 mt-2.5">
                <Input className="h-7 text-xs flex-1" placeholder="Write a response…" data-testid={`input-reply-${i}`} />
                <Button size="sm" className="h-7 text-xs gap-1" data-testid={`btn-reply-${i}`}><Send className="h-3 w-3" />Reply</Button>
                <Button size="sm" variant="outline" className="h-7 text-xs gap-1"><Bot className="h-3 w-3" />AI Draft</Button>
              </div>
            )}
            {r.replied && <div className="mt-2 text-[10px] text-emerald-600 flex items-center gap-1"><CheckCircle className="h-3 w-3" />Responded</div>}
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Patient NPS Tab ──────────────────────────────────────────────────────────
const surveyResponses = [
  { name: "Margaret Sullivan", score: 10, comment: "Amazing experience with my implant!",      category: "Promoter" },
  { name: "Robert Kim",        score: 9,  comment: "Very professional team",                   category: "Promoter" },
  { name: "Diana Patel",       score: 8,  comment: "Good but wait time was long",              category: "Passive"  },
  { name: "Tom Davis",         score: 7,  comment: "Billing process confusing",               category: "Passive"  },
  { name: "James Okafor",      score: 4,  comment: "Front desk was rude",                     category: "Detractor", action: "Mgr contacted — resolved" },
];

const satisfactionCategories = [
  { label: "Provider care",        value: 96 },
  { label: "Treatment outcomes",   value: 94 },
  { label: "Facility cleanliness", value: 98 },
  { label: "Wait time",            value: 72 },
  { label: "Billing clarity",      value: 68 },
  { label: "Front desk",           value: 82 },
  { label: "Overall experience",   value: 91 },
];

function NPSTab() {
  const promoters  = surveyResponses.filter(r => r.score >= 9).length;
  const passives   = surveyResponses.filter(r => r.score >= 7 && r.score <= 8).length;
  const detractors = surveyResponses.filter(r => r.score <= 6).length;
  const nps = Math.round(((promoters - detractors) / surveyResponses.length) * 100);

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "NPS Score",     value: nps,          color: nps >= 50 ? "text-emerald-600" : "text-amber-600", icon: Target },
          { label: "Promoters",     value: `${promoters}  (${Math.round((promoters/surveyResponses.length)*100)}%)`, color: "text-emerald-600", icon: ThumbsUp },
          { label: "Passives",      value: `${passives}   (${Math.round((passives/surveyResponses.length)*100)}%)`, color: "text-amber-600",   icon: Minus },
          { label: "Detractors",    value: `${detractors} (${Math.round((detractors/surveyResponses.length)*100)}%)`,color: "text-red-600",     icon: ThumbsDown },
        ].map(k => (
          <Card key={k.label}>
            <CardContent className="pt-3 pb-3">
              <k.icon className={`h-4 w-4 ${k.color} mb-1`} />
              <div className={`text-xl font-bold font-mono ${k.color}`}>{String(k.value).trim()}</div>
              <div className="text-[10px] text-muted-foreground">{k.label}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">Satisfaction by Category</CardTitle></CardHeader>
          <CardContent className="pt-0 space-y-2">
            {satisfactionCategories.map(c => (
              <div key={c.label}>
                <div className="flex justify-between text-xs mb-0.5">
                  <span className="text-muted-foreground">{c.label}</span>
                  <span className={`font-semibold ${c.value >= 90 ? "text-emerald-600" : c.value >= 75 ? "text-blue-600" : "text-amber-600"}`}>{c.value}%</span>
                </div>
                <Progress value={c.value} className={`h-1.5 ${c.value < 75 ? "[&>div]:bg-amber-500" : ""}`} />
              </div>
            ))}
          </CardContent>
        </Card>

        <div className="space-y-2">
          <h3 className="font-semibold text-sm">Recent Responses</h3>
          {surveyResponses.map((r, i) => (
            <div key={i} className="p-3 border rounded-lg" data-testid={`nps-${i}`}>
              <div className="flex items-center gap-2 mb-1">
                <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-white
                  ${r.score >= 9 ? "bg-emerald-500" : r.score >= 7 ? "bg-amber-500" : "bg-red-500"}`}>{r.score}</div>
                <span className="font-medium text-xs">{r.name}</span>
                <Badge className={`text-[9px] border px-1.5 ml-auto
                  ${r.category === "Promoter" ? "bg-emerald-100 text-emerald-700 border-emerald-300"
                  : r.category === "Passive" ? "bg-amber-100 text-amber-700 border-amber-300"
                  : "bg-red-100 text-red-700 border-red-300"}`}>{r.category}</Badge>
              </div>
              <div className="text-[10px] text-muted-foreground">{r.comment}</div>
              {r.action && <div className="text-[10px] text-primary mt-0.5 font-medium">{r.action}</div>}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Testimonials Tab ─────────────────────────────────────────────────────────
const testimonials = [
  { name: "Margaret Sullivan", procedure: "Full Arch All-on-4",    quote: "After losing all my upper teeth in a car accident, Dr. Blake gave me my smile back. The implants feel completely natural.",  featured: true,  photo: "MS", rating: 5, date: "Feb 2026" },
  { name: "Tom Davis",         procedure: "All-on-4 + Bone Graft", quote: "I was terrified at first. Now I eat steak for the first time in 10 years. Worth every penny and every moment of recovery.", featured: true,  photo: "TD", rating: 5, date: "Jan 2026" },
  { name: "Diana Patel",       procedure: "Single Implant #3",     quote: "Painless procedure. Dr. Moreau was gentle and explained everything. I wish I had done this sooner.",                          featured: false, photo: "DP", rating: 5, date: "Dec 2025" },
  { name: "James Morris",      procedure: "Implant-Supported OD",  quote: "My lower denture always slipped. These implants snapped it in place. Total game changer for confidence.",                   featured: false, photo: "JM", rating: 5, date: "Nov 2025" },
  { name: "Angela Torres",     procedure: "Sinus Lift + Implants", quote: "Complex case handled beautifully. The team kept me informed the whole time. Professional and caring.",                       featured: true,  photo: "AT", rating: 5, date: "Oct 2025" },
];

function TestimonialsTab() {
  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div className="grid grid-cols-3 gap-3">
          {[
            { label: "Total Testimonials", value: testimonials.length },
            { label: "Featured",           value: testimonials.filter(t=>t.featured).length },
            { label: "Avg Rating",         value: "5.0 ★" },
          ].map(k => (
            <Card key={k.label}>
              <CardContent className="pt-3 pb-3">
                <div className="text-xl font-bold font-mono text-emerald-600">{k.value}</div>
                <div className="text-[10px] text-muted-foreground">{k.label}</div>
              </CardContent>
            </Card>
          ))}
        </div>
        <Button size="sm" className="gap-1.5 text-xs" data-testid="btn-add-testimonial">
          <PlusCircle className="h-3.5 w-3.5" /> Add Testimonial
        </Button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {testimonials.map((t, i) => (
          <div key={i} className={`p-4 border rounded-xl space-y-3 ${t.featured ? "border-primary/30 bg-primary/[0.02]" : ""}`} data-testid={`testimonial-${i}`}>
            <div className="flex items-start gap-2">
              <div className="w-10 h-10 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-sm shrink-0">{t.photo}</div>
              <div>
                <div className="font-semibold text-sm">{t.name}</div>
                <div className="text-[10px] text-muted-foreground">{t.procedure}</div>
                <div className="flex gap-0.5 mt-0.5">
                  {[...Array(t.rating)].map((_, s) => <Star key={s} className="h-2.5 w-2.5 text-amber-400 fill-amber-400" />)}
                </div>
              </div>
              {t.featured && <Badge className="text-[9px] bg-primary/10 text-primary border-primary/30 border px-1 ml-auto">Featured</Badge>}
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed italic">"{t.quote}"</p>
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-muted-foreground">{t.date}</span>
              <div className="flex gap-1.5">
                <Button size="sm" variant="outline" className="h-6 text-[10px] px-2">Edit</Button>
                <Button size="sm" variant="outline" className="h-6 text-[10px] px-2">Share</Button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Main Hub ─────────────────────────────────────────────────────────────────
export default function MarketingHubPage() {
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">Marketing Hub</h1>
        <p className="text-sm text-muted-foreground">Channel performance, content engine, reputation management, NPS, and patient testimonials — all unified</p>
      </div>

      <Tabs defaultValue="channels">
        <TabsList className="flex-wrap h-auto gap-1">
          <TabsTrigger value="channels"     className="text-xs"><BarChart3     className="h-3.5 w-3.5 mr-1" />Channels</TabsTrigger>
          <TabsTrigger value="content"      className="text-xs"><PenTool      className="h-3.5 w-3.5 mr-1" />Content Engine</TabsTrigger>
          <TabsTrigger value="reputation"   className="text-xs"><Star         className="h-3.5 w-3.5 mr-1" />Reputation</TabsTrigger>
          <TabsTrigger value="nps"          className="text-xs"><ThumbsUp     className="h-3.5 w-3.5 mr-1" />Patient NPS</TabsTrigger>
          <TabsTrigger value="testimonials" className="text-xs"><MessageSquare className="h-3.5 w-3.5 mr-1" />Testimonials</TabsTrigger>
        </TabsList>
        <TabsContent value="channels"     className="mt-4"><ChannelsTab /></TabsContent>
        <TabsContent value="content"      className="mt-4"><ContentEngineTab /></TabsContent>
        <TabsContent value="reputation"   className="mt-4"><ReputationTab /></TabsContent>
        <TabsContent value="nps"          className="mt-4"><NPSTab /></TabsContent>
        <TabsContent value="testimonials" className="mt-4"><TestimonialsTab /></TabsContent>
      </Tabs>
    </div>
  );
}
