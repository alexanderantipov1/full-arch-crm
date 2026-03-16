import { useState, useRef, useEffect } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/hooks/use-toast";
import { apiRequest, queryClient } from "@/lib/queryClient";
import {
  Bot, Brain, MessageSquare, FileText, Phone, Mic, Sparkles, Send,
  Copy, Download, Loader2, CheckCircle, TrendingUp, DollarSign,
  Zap, Volume2, Clock, Activity, AlertTriangle, Star, Lightbulb,
  Stethoscope, ClipboardList, FileCheck,
} from "lucide-react";
import type { Patient, TreatmentPlan } from "@shared/schema";

// ─── AI Chat / Assistant Tab ──────────────────────────────────────────────────
interface ChatMessage { role: "user" | "assistant"; content: string; ts: string; }

const CHAT_STARTERS = [
  "What CPT codes apply to All-on-4 procedures?",
  "Draft a medical necessity letter for full arch implants",
  "How do I appeal a D6010 denial for bone loss?",
  "What ICD-10 codes pair with D7310?",
  "Summarize today's outstanding insurance authorizations",
];

function AIAssistantTab() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: "assistant", content: "Hi! I'm your AI dental billing & clinical assistant. I can help with coding questions, appeal drafts, treatment documentation, and more.", ts: new Date().toLocaleTimeString() },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const { toast } = useToast();

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  async function send() {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    const userMsg: ChatMessage = { role: "user", content: text, ts: new Date().toLocaleTimeString() };
    setMessages(m => [...m, userMsg]);
    setLoading(true);
    try {
      const res = await apiRequest("POST", "/api/ai/chat", { message: text });
      const data = await res.json();
      setMessages(m => [...m, { role: "assistant", content: data.response || data.message || "I'm here to help!", ts: new Date().toLocaleTimeString() }]);
    } catch {
      setMessages(m => [...m, { role: "assistant", content: "I'm having trouble connecting right now. Please try again.", ts: new Date().toLocaleTimeString() }]);
    } finally { setLoading(false); }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 h-[calc(100vh-280px)] min-h-[400px]">
      {/* Chat area */}
      <div className="lg:col-span-3 flex flex-col border rounded-xl overflow-hidden">
        <div className="flex items-center gap-2 px-4 py-2.5 border-b bg-muted/30">
          <Bot className="h-4 w-4 text-primary" />
          <span className="font-semibold text-sm">AI Billing & Clinical Assistant</span>
          <Badge className="text-[9px] bg-emerald-100 text-emerald-700 border-emerald-300 border px-1 ml-auto">Online</Badge>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[85%] rounded-xl px-3 py-2 text-sm ${
                m.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted"
              }`}>
                <div className="whitespace-pre-wrap leading-relaxed">{m.content}</div>
                <div className="text-[10px] opacity-60 mt-1 text-right">{m.ts}</div>
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="bg-muted rounded-xl px-3 py-2 flex items-center gap-1.5">
                <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
                <span className="text-xs text-muted-foreground">Thinking…</span>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
        <div className="border-t p-3 flex gap-2">
          <Textarea value={input} onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
            placeholder="Ask about coding, appeals, documentation…"
            className="min-h-[40px] max-h-28 text-sm resize-none" rows={1}
            data-testid="input-chat-message" />
          <Button onClick={send} disabled={!input.trim() || loading} size="sm" className="h-9 px-3" data-testid="btn-send-chat">
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          </Button>
        </div>
      </div>

      {/* Starters + context */}
      <div className="space-y-3">
        <div className="border rounded-xl p-3">
          <div className="text-xs font-semibold mb-2 flex items-center gap-1.5"><Lightbulb className="h-3.5 w-3.5 text-primary" />Quick Questions</div>
          <div className="space-y-1.5">
            {CHAT_STARTERS.map((s, i) => (
              <button key={i} onClick={() => { setInput(s); }}
                className="w-full text-left text-[10px] text-muted-foreground hover:text-primary p-1.5 rounded hover:bg-primary/5 transition-colors">
                {s}
              </button>
            ))}
          </div>
        </div>
        <div className="border rounded-xl p-3">
          <div className="text-xs font-semibold mb-2 flex items-center gap-1.5"><Zap className="h-3.5 w-3.5 text-primary" />AI Capabilities</div>
          {["CDT → CPT/ICD-10 Cross-coding","Medical necessity drafting","Denial analysis & appeals","Fee schedule optimization","Clinical decision support","HIPAA-safe document generation"].map(c => (
            <div key={c} className="flex items-center gap-1.5 text-[10px] text-muted-foreground py-0.5">
              <CheckCircle className="h-2.5 w-2.5 text-emerald-500 shrink-0" />{c}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── AI Documentation Tab ─────────────────────────────────────────────────────
const DOC_TYPES = [
  { value: "medical_necessity", label: "Medical Necessity Letter",   icon: FileCheck },
  { value: "operative_report",  label: "Operative Report",           icon: Stethoscope },
  { value: "progress_note",     label: "Progress Note (SOAP)",       icon: ClipboardList },
  { value: "referral_letter",   label: "Referral Letter",            icon: FileText },
  { value: "predetermination",  label: "Predetermination Letter",    icon: FileText },
  { value: "appeal_letter",     label: "Appeal Letter",              icon: FileText },
];

function AIDocumentationTab() {
  const [docType, setDocType] = useState("medical_necessity");
  const [patientId, setPatientId] = useState("");
  const [context, setContext] = useState("");
  const [generated, setGenerated] = useState("");
  const { toast } = useToast();

  const { data: patients = [] } = useQuery<Patient[]>({ queryKey: ["/api/patients"] });

  const mutation = useMutation({
    mutationFn: async () => {
      const res = await apiRequest("POST", "/api/ai/generate-document", { docType, patientId: patientId ? parseInt(patientId) : undefined, context });
      return res.json();
    },
    onSuccess: (data) => setGenerated(data.document || data.content || "Document generated successfully."),
    onError: () => toast({ title: "Generation failed", variant: "destructive" }),
  });

  const selectedPatient = patients.find(p => p.id === parseInt(patientId));

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
      {/* Input panel */}
      <div className="space-y-4">
        <div>
          <label className="text-xs font-semibold mb-1.5 block">Document Type</label>
          <div className="grid grid-cols-2 gap-2">
            {DOC_TYPES.map(dt => {
              const Icon = dt.icon;
              return (
                <button key={dt.value} onClick={() => setDocType(dt.value)}
                  className={`p-2.5 border rounded-lg text-left transition-colors ${docType === dt.value ? "border-primary bg-primary/5" : "hover:border-primary/40"}`}
                  data-testid={`doctype-${dt.value}`}>
                  <Icon className={`h-3.5 w-3.5 mb-1 ${docType === dt.value ? "text-primary" : "text-muted-foreground"}`} />
                  <div className={`text-[10px] font-medium leading-tight ${docType === dt.value ? "text-primary" : ""}`}>{dt.label}</div>
                </button>
              );
            })}
          </div>
        </div>

        <div>
          <label className="text-xs font-semibold mb-1.5 block">Patient (Optional)</label>
          <Select value={patientId} onValueChange={setPatientId}>
            <SelectTrigger className="h-8 text-xs" data-testid="select-patient">
              <SelectValue placeholder="Select patient…" />
            </SelectTrigger>
            <SelectContent>
              {patients.map(p => (
                <SelectItem key={p.id} value={String(p.id)}>
                  {p.firstName} {p.lastName}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div>
          <label className="text-xs font-semibold mb-1.5 block">Clinical Context / Notes</label>
          <Textarea value={context} onChange={e => setContext(e.target.value)}
            placeholder="Patient has generalized bone loss, missing teeth #3, 4, 14, 19. Recommended full arch All-on-4 implants…"
            className="text-xs min-h-[120px]" data-testid="input-context" />
        </div>

        <Button onClick={() => mutation.mutate()} disabled={mutation.isPending} className="w-full gap-2" data-testid="btn-generate-doc">
          {mutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
          Generate {DOC_TYPES.find(d => d.value === docType)?.label}
        </Button>
      </div>

      {/* Output panel */}
      <div className="border rounded-xl flex flex-col">
        <div className="flex items-center justify-between px-4 py-2.5 border-b bg-muted/30">
          <span className="font-semibold text-sm flex items-center gap-2"><Sparkles className="h-4 w-4 text-primary" />Generated Document</span>
          {generated && (
            <div className="flex gap-1.5">
              <Button size="sm" variant="outline" className="h-7 text-xs gap-1" onClick={() => navigator.clipboard.writeText(generated)} data-testid="btn-copy-doc">
                <Copy className="h-3 w-3" />Copy
              </Button>
              <Button size="sm" variant="outline" className="h-7 text-xs gap-1" data-testid="btn-download-doc">
                <Download className="h-3 w-3" />Export
              </Button>
            </div>
          )}
        </div>
        <div className="flex-1 p-4 overflow-y-auto">
          {mutation.isPending ? (
            <div className="space-y-2">
              {[...Array(8)].map((_, i) => <Skeleton key={i} className={`h-3 ${i % 3 === 2 ? "w-2/3" : "w-full"}`} />)}
            </div>
          ) : generated ? (
            <div className="text-xs leading-relaxed whitespace-pre-wrap font-mono text-muted-foreground">{generated}</div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full gap-3 text-muted-foreground">
              <FileText className="h-10 w-10 opacity-20" />
              <div className="text-xs text-center">Select a document type, add clinical context, and click Generate</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── AI Phone Agent Tab ───────────────────────────────────────────────────────
const RECENT_CALLS = [
  { time: "9:14 AM",  caller: "Maria Gonzalez", type: "New Patient Inquiry",    duration: "3:24", outcome: "Booked consult 3/20",  sentiment: "positive" },
  { time: "9:02 AM",  caller: "Robert Chen",    type: "Reschedule Request",     duration: "1:42", outcome: "Rescheduled to 3/22",  sentiment: "neutral"  },
  { time: "8:54 AM",  caller: "Unknown",        type: "Insurance Question",     duration: "2:11", outcome: "Escalated to Brenda",  sentiment: "neutral"  },
  { time: "8:40 AM",  caller: "Tom Davis",      type: "Post-Op Check-In",       duration: "4:08", outcome: "Follow-up scheduled",  sentiment: "positive" },
  { time: "8:31 AM",  caller: "Angela Kim",     type: "Payment Question",       duration: "1:55", outcome: "Directed to billing",  sentiment: "negative" },
  { time: "Yesterday","caller": "James Morris",  type: "New Patient Inquiry",    duration: "2:48", outcome: "Booked consult 3/19",  sentiment: "positive" },
];

function AIPhoneTab() {
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Calls Today",       value: "124",  icon: Phone,    color: "text-primary"    },
          { label: "Resolved by AI",    value: "91%",  icon: Bot,      color: "text-emerald-600"},
          { label: "Appts Booked",      value: "38",   icon: CheckCircle, color: "text-emerald-600" },
          { label: "Avg Call Duration", value: "2.1m", icon: Clock,    color: "text-blue-600"   },
        ].map(k => (
          <Card key={k.label}>
            <CardContent className="pt-3 pb-3">
              <k.icon className={`h-4 w-4 ${k.color} mb-1`} />
              <div className={`text-xl font-bold font-mono ${k.color}`}>{k.value}</div>
              <div className="text-[10px] text-muted-foreground">{k.label}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Status */}
        <Card className="border-emerald-400/40 bg-emerald-500/5">
          <CardContent className="pt-4 pb-4">
            <div className="flex items-center gap-2 mb-3">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
              <span className="font-semibold text-sm">ARIA — AI Receptionist</span>
              <Badge className="text-[9px] bg-emerald-100 text-emerald-700 border-emerald-300 border px-1 ml-auto">Live</Badge>
            </div>
            {[
              { label: "Status",         value: "Active — handling calls"    },
              { label: "Calls In Queue", value: "2 waiting"                  },
              { label: "Current Call",   value: "Maria G. (1:42 elapsed)"    },
              { label: "Platform",       value: "HIPAA-Compliant VoIP"       },
              { label: "Languages",      value: "EN, ES, ZH"                 },
              { label: "Escalation",     value: "Brenda Torres (backup)"     },
            ].map(item => (
              <div key={item.label} className="flex justify-between text-xs py-1 border-b last:border-0">
                <span className="text-muted-foreground">{item.label}</span>
                <span className="font-medium">{item.value}</span>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Recent calls */}
        <Card className="lg:col-span-2">
          <CardHeader className="pb-2"><CardTitle className="text-sm">Recent Call Log</CardTitle></CardHeader>
          <CardContent className="pt-0 space-y-2">
            {RECENT_CALLS.map((c, i) => (
              <div key={i} className="flex items-center gap-3 p-2 rounded-lg border">
                <div className={`w-2 h-2 rounded-full shrink-0 ${c.sentiment === "positive" ? "bg-emerald-500" : c.sentiment === "negative" ? "bg-red-500" : "bg-amber-400"}`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-xs">{c.caller}</span>
                    <Badge variant="outline" className="text-[9px] px-1">{c.type}</Badge>
                  </div>
                  <div className="text-[10px] text-muted-foreground">{c.outcome}</div>
                </div>
                <div className="text-right text-[10px] text-muted-foreground shrink-0">
                  <div>{c.time}</div>
                  <div>{c.duration}</div>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

// ─── DentBot Advisor Tab ──────────────────────────────────────────────────────
const PRACTICE_INSIGHTS = [
  { category: "Revenue",    insight: "Dr. Kim's case acceptance dropped to 55% this month — recommend case acceptance training or consult shadowing",  priority: "high",   value: "+$14K/mo potential" },
  { category: "Billing",    insight: "14 claims over 45 days outstanding — prioritize D6010 series for proactive appeal before timely filing",          priority: "high",   value: "$42K at risk" },
  { category: "Operations", insight: "Op 4 has 28% utilization — schedule part-time hygienist block to maximize operatory ROI",                         priority: "medium", value: "+$8K/mo" },
  { category: "Marketing",  insight: "Google organic converting at 12.1x ROI — increase AI blog content frequency to 3x/week",                           priority: "medium", value: "+6 patients/mo" },
  { category: "Clinical",   insight: "3 recall patients overdue 6+ months — AI recall outreach recommended to prevent patient attrition",                priority: "low",    value: "Retention" },
  { category: "Compliance", insight: "David Okafor's HIPAA training renewal is due in 12 days — auto-enrolled in LMS",                                  priority: "low",    value: "Risk mgmt" },
];

function DentBotTab() {
  return (
    <div className="space-y-5">
      <div className="rounded-xl border border-primary/30 bg-primary/[0.02] p-4">
        <div className="flex items-center gap-2 mb-2">
          <Brain className="h-5 w-5 text-primary" />
          <span className="font-semibold">DentBot Advisor</span>
          <Badge className="text-[9px] bg-primary/10 text-primary border-primary/30 border px-1">AI Practice Intelligence</Badge>
        </div>
        <p className="text-xs text-muted-foreground">DentBot continuously analyzes your practice data across revenue, operations, clinical outcomes, and marketing — surfacing proactive insights before they become problems.</p>
      </div>

      <div className="space-y-2">
        {PRACTICE_INSIGHTS.map((item, i) => (
          <div key={i} className={`p-3.5 border rounded-xl ${item.priority === "high" ? "border-red-400/40 bg-red-500/[0.02]" : item.priority === "medium" ? "border-amber-400/40 bg-amber-500/[0.02]" : "border-border"}`}
            data-testid={`insight-${i}`}>
            <div className="flex items-start gap-3">
              <div className="mt-0.5">
                {item.priority === "high" && <AlertTriangle className="h-4 w-4 text-red-500" />}
                {item.priority === "medium" && <Lightbulb className="h-4 w-4 text-amber-500" />}
                {item.priority === "low" && <CheckCircle className="h-4 w-4 text-blue-500" />}
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-0.5">
                  <Badge className={`text-[9px] border px-1.5
                    ${item.priority === "high" ? "bg-red-100 text-red-700 border-red-300"
                    : item.priority === "medium" ? "bg-amber-100 text-amber-700 border-amber-300"
                    : "bg-blue-100 text-blue-700 border-blue-300"}`}>{item.priority}</Badge>
                  <span className="text-[10px] font-semibold text-primary uppercase tracking-wider">{item.category}</span>
                </div>
                <div className="text-xs">{item.insight}</div>
              </div>
              <div className="text-right text-[10px] text-emerald-600 font-semibold shrink-0">{item.value}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Voice-to-Code Tab ────────────────────────────────────────────────────────
function VoiceToCodeTab() {
  const [mode, setMode] = useState<"idle"|"listening"|"processing">("idle");
  const [transcript, setTranscript] = useState("");
  const [coded, setCoded] = useState<null|{codes: string[]; description: string}>(null);
  const { toast } = useToast();

  const DEMO_TRANSCRIPTS = [
    { text: "Patient has 8mm pocket depth buccal to tooth 14 with bleeding on probing and furcation involvement grade 2", codes: ["D4341 – Perio SRP (4+ teeth, quad)", "D4910 – Perio maintenance", "ICD-10: K05.31 – Chronic perio stage III"] },
    { text: "Extracted tooth 19 with elevation and forceps, placed 4x10mm Straumann BLT implant, primary stability achieved", codes: ["D7210 – Surgical extraction", "D6010 – Implant placement", "D7953 – Bone graft, extraction socket"] },
    { text: "All-on-4 procedure, 4 implants maxillary arch, immediate load temporary prosthesis delivered", codes: ["D6010 x4 – Endosseous implants", "D6012 x4 – Interim implant body", "CPT 21248 – Reconstruction maxilla, partial"] },
  ];

  function simulate() {
    setMode("listening");
    setTimeout(() => {
      const demo = DEMO_TRANSCRIPTS[Math.floor(Math.random() * DEMO_TRANSCRIPTS.length)];
      setTranscript(demo.text);
      setMode("processing");
      setTimeout(() => {
        setCoded({ codes: demo.codes, description: demo.text });
        setMode("idle");
      }, 1200);
    }, 2000);
  }

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {[
          { label: "Dictations Today", value: "48",   icon: Mic,      color: "text-primary" },
          { label: "Codes Generated",  value: "124",  icon: FileText, color: "text-emerald-600" },
          { label: "Time Saved",       value: "3.2h", icon: Clock,    color: "text-blue-600" },
        ].map(k => (
          <Card key={k.label}>
            <CardContent className="pt-3 pb-3">
              <k.icon className={`h-4 w-4 ${k.color} mb-1`} />
              <div className={`text-xl font-bold font-mono ${k.color}`}>{k.value}</div>
              <div className="text-[10px] text-muted-foreground">{k.label}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Dictation panel */}
        <div className="border rounded-xl p-4 space-y-4">
          <div className="font-semibold text-sm flex items-center gap-2"><Mic className="h-4 w-4 text-primary" /> Voice Dictation</div>
          <div className="flex flex-col items-center gap-4 py-4">
            <button onClick={simulate} disabled={mode !== "idle"}
              className={`w-20 h-20 rounded-full flex items-center justify-center transition-all border-4
                ${mode === "listening" ? "bg-red-500 border-red-400 animate-pulse" : mode === "processing" ? "bg-amber-500 border-amber-400" : "bg-primary border-primary/30 hover:scale-105"}`}
              data-testid="btn-start-recording">
              {mode === "listening" ? <Volume2 className="h-8 w-8 text-white" /> : mode === "processing" ? <Loader2 className="h-8 w-8 text-white animate-spin" /> : <Mic className="h-8 w-8 text-white" />}
            </button>
            <span className="text-xs text-muted-foreground">
              {mode === "idle" ? "Click to start voice dictation" : mode === "listening" ? "Listening… speak your clinical note" : "Processing and generating codes…"}
            </span>
          </div>
          {transcript && (
            <div className="p-3 bg-muted/40 rounded-lg">
              <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">Transcript</div>
              <div className="text-xs leading-relaxed">{transcript}</div>
            </div>
          )}
        </div>

        {/* Generated codes */}
        <div className="border rounded-xl p-4">
          <div className="font-semibold text-sm flex items-center gap-2 mb-4"><Sparkles className="h-4 w-4 text-primary" /> AI-Generated Codes</div>
          {coded ? (
            <div className="space-y-2">
              {coded.codes.map((code, i) => (
                <div key={i} className="flex items-start gap-2 p-2.5 border rounded-lg bg-primary/[0.02]">
                  <CheckCircle className="h-3.5 w-3.5 text-emerald-500 mt-0.5 shrink-0" />
                  <span className="text-xs font-mono">{code}</span>
                </div>
              ))}
              <Button size="sm" className="w-full mt-2 gap-1.5 text-xs" data-testid="btn-apply-codes">
                <CheckCircle className="h-3.5 w-3.5" /> Apply Codes to Claim
              </Button>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-40 gap-2 text-muted-foreground">
              <Sparkles className="h-8 w-8 opacity-20" />
              <div className="text-xs text-center">Dictate a clinical procedure to auto-generate CDT / CPT / ICD-10 codes</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Main Hub ─────────────────────────────────────────────────────────────────
export default function AIHubPage() {
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">AI Command Center</h1>
        <p className="text-sm text-muted-foreground">All AI-powered tools unified — assistant, documentation, phone agent, advisor, and voice coding</p>
      </div>

      <Tabs defaultValue="assistant">
        <TabsList className="flex-wrap h-auto gap-1">
          <TabsTrigger value="assistant" className="text-xs"><MessageSquare className="h-3.5 w-3.5 mr-1" />AI Assistant</TabsTrigger>
          <TabsTrigger value="docs"      className="text-xs"><FileText     className="h-3.5 w-3.5 mr-1" />Documentation</TabsTrigger>
          <TabsTrigger value="phone"     className="text-xs"><Phone        className="h-3.5 w-3.5 mr-1" />Phone Agent</TabsTrigger>
          <TabsTrigger value="dentbot"   className="text-xs"><Brain        className="h-3.5 w-3.5 mr-1" />DentBot Advisor</TabsTrigger>
          <TabsTrigger value="voice"     className="text-xs"><Mic          className="h-3.5 w-3.5 mr-1" />Voice-to-Code</TabsTrigger>
        </TabsList>
        <TabsContent value="assistant" className="mt-4"><AIAssistantTab /></TabsContent>
        <TabsContent value="docs"      className="mt-4"><AIDocumentationTab /></TabsContent>
        <TabsContent value="phone"     className="mt-4"><AIPhoneTab /></TabsContent>
        <TabsContent value="dentbot"   className="mt-4"><DentBotTab /></TabsContent>
        <TabsContent value="voice"     className="mt-4"><VoiceToCodeTab /></TabsContent>
      </Tabs>
    </div>
  );
}
