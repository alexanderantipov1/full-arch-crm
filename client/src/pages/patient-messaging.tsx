import { useState, useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useLocation } from "wouter";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { apiRequest } from "@/lib/queryClient";
import {
  MessageSquare, Plus, Send, Phone, Mail, Loader2, Search,
  Sparkles, CheckCheck, Shield, User, Clock,
} from "lucide-react";

interface PatientMessage {
  id: number; patientId: number; direction: string; channel: string;
  subject: string | null; body: string; status: string; sentBy: string | null;
  templateUsed: string | null; createdAt: string;
}

interface ThreadSummary {
  patientId: number;
  patientName: string;
  lastBody: string;
  lastCreatedAt: string;
  unreadCount: number;
}

const TEMPLATES = [
  { name: "Appointment Reminder", channel: "sms", body: "Hi {name}, this is a reminder for your appointment tomorrow at {time}. Please call us if you need to confirm or reschedule. Thank you!" },
  { name: "Post-Op Instructions", channel: "sms", body: "Hi {name}, your procedure is complete. Please follow the post-op instructions provided. Call us if you have any concerns." },
  { name: "Lab Case Ready", channel: "sms", body: "Great news, {name}! Your dental work is ready. Please call us to schedule your delivery appointment." },
  { name: "Balance Due", channel: "email", body: "Dear {name},\n\nThis is a friendly reminder that you have an outstanding balance due on your account. Please call our office to arrange payment.\n\nThank you,\nThe Team" },
  { name: "Welcome New Patient", channel: "email", body: "Welcome to our practice, {name}!\n\nWe are so glad to have you as a new patient. Your first appointment is confirmed. If you have any questions, please don't hesitate to reach out.\n\nWarm regards,\nThe Team" },
  { name: "Recall Due", channel: "sms", body: "Hi {name}, it's time for your regular dental check-up! Please call us to schedule your appointment. We look forward to seeing you." },
];

const CHANNEL_CFG: Record<string, { label: string; icon: any; color: string }> = {
  sms:    { label: "SMS",    icon: Phone,         color: "text-emerald-600 dark:text-emerald-400" },
  email:  { label: "Email",  icon: Mail,          color: "text-blue-600 dark:text-blue-400"      },
  in_app: { label: "In-App", icon: MessageSquare, color: "text-purple-600 dark:text-purple-400"  },
};

const STATUS_CFG: Record<string, { label: string }> = {
  sent:      { label: "Sent"      },
  delivered: { label: "Delivered" },
  read:      { label: "Read"      },
  failed:    { label: "Failed"    },
  unread:    { label: "Unread"    },
};

function fmtTime(iso: string) {
  const d = new Date(iso);
  const now = new Date();
  const isToday = d.toDateString() === now.toDateString();
  if (isToday) return d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function fmtFull(iso: string) {
  return new Date(iso).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

export default function PatientMessagingPage() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const threadEndRef = useRef<HTMLDivElement>(null);
  const [location] = useLocation();

  const [selectedPatientId, setSelectedPatientId] = useState<number | null>(null);
  const [selectedPatientName, setSelectedPatientName] = useState<string>("");
  const [searchThread, setSearchThread] = useState("");
  const [composing, setComposing] = useState(false);
  const [form, setForm] = useState({ channel: "sms", subject: "", body: "", templateUsed: "" });
  const [aiLoading, setAiLoading] = useState(false);

  // Pre-select patient from URL query params (e.g. from patient profile "Message" button)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const pid = params.get("patientId");
    const pname = params.get("patientName");
    const compose = params.get("compose");
    if (pid && pname) {
      setSelectedPatientId(parseInt(pid));
      setSelectedPatientName(decodeURIComponent(pname));
      if (compose === "true") setComposing(true);
    }
  }, [location]);

  const { data: threads = [], isLoading: threadsLoading } = useQuery<ThreadSummary[]>({
    queryKey: ["/api/patient-messages/threads"],
    queryFn: () => fetch("/api/patient-messages/threads", { credentials: "include" }).then(r => r.json()),
    refetchInterval: 30000,
  });

  const { data: patients = [] } = useQuery<any[]>({ queryKey: ["/api/patients"] });

  const { data: messages = [], isLoading: msgLoading } = useQuery<PatientMessage[]>({
    queryKey: ["/api/patient-messages", selectedPatientId],
    queryFn: () => fetch(`/api/patient-messages?patientId=${selectedPatientId}`, { credentials: "include" }).then(r => r.json()),
    enabled: !!selectedPatientId,
  });

  const markReadMut = useMutation({
    mutationFn: (id: number) => apiRequest("PATCH", `/api/patient-messages/${id}/read`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/patient-messages"] });
      queryClient.invalidateQueries({ queryKey: ["/api/patient-messages/threads"] });
      queryClient.invalidateQueries({ queryKey: ["/api/patient-messages/unread-count"] });
    },
  });

  const threadOpenMut = useMutation({
    mutationFn: (patientId: number) => apiRequest("POST", `/api/patient-messages/${patientId}/open`, {}),
  });

  const sendMut = useMutation({
    mutationFn: () => apiRequest("POST", "/api/patient-messages", {
      patientId: selectedPatientId!,
      direction: "outbound",
      channel: form.channel,
      subject: form.subject || null,
      body: form.body,
      status: "sent",
      sentBy: "Staff",
      templateUsed: form.templateUsed || null,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/patient-messages"] });
      queryClient.invalidateQueries({ queryKey: ["/api/patient-messages/threads"] });
      toast({ title: "Message sent" });
      setComposing(false);
      setForm({ channel: "sms", subject: "", body: "", templateUsed: "" });
    },
    onError: () => toast({ title: "Error sending message", variant: "destructive" }),
  });

  useEffect(() => {
    if (messages.length > 0) {
      threadEndRef.current?.scrollIntoView({ behavior: "smooth" });
      messages.filter(m => m.direction === "inbound" && m.status !== "read").forEach(m => markReadMut.mutate(m.id));
    }
  }, [messages]);

  async function handleAiSuggest() {
    const lastInbound = [...messages].reverse().find(m => m.direction === "inbound");
    if (!lastInbound) {
      toast({ title: "No patient message to reply to", variant: "destructive" });
      return;
    }
    setAiLoading(true);
    try {
      const res = await fetch("/api/ai/suggest-reply", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ patientName: selectedPatientName, lastMessage: lastInbound.body, channel: form.channel }),
      });
      const data = await res.json();
      if (data.suggestion) {
        setForm(f => ({ ...f, body: data.suggestion }));
        setComposing(true);
        toast({ title: "AI reply ready" });
      }
    } catch {
      toast({ title: "AI suggestion failed", variant: "destructive" });
    } finally {
      setAiLoading(false);
    }
  }

  const filteredThreads = threads.filter(t =>
    t.patientName.toLowerCase().includes(searchThread.toLowerCase())
  );

  const allPatientsWithNoThread = patients.filter(
    p => !threads.find(t => t.patientId === p.id) &&
    `${p.firstName} ${p.lastName}`.toLowerCase().includes(searchThread.toLowerCase())
  );

  const totalUnread = threads.reduce((sum, t) => sum + t.unreadCount, 0);

  return (
    <div className="h-full flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">Patient Messaging</h1>
          <p className="text-sm text-muted-foreground">2-way messaging via SMS, email & in-app · PHI access auto-logged</p>
        </div>
        <div className="flex items-center gap-2">
          {totalUnread > 0 && (
            <Badge variant="destructive" className="text-xs" data-testid="badge-total-unread">{totalUnread} unread</Badge>
          )}
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground border rounded-md px-2.5 py-1.5">
            <Shield className="h-3.5 w-3.5 text-emerald-500" />
            HIPAA compliant
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 flex-1 min-h-0">
        {/* Thread List (left panel) */}
        <Card className="flex flex-col overflow-hidden">
          <CardHeader className="pb-2 shrink-0">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm">Conversations</CardTitle>
              {totalUnread > 0 && <Badge className="text-[10px]">{totalUnread} new</Badge>}
            </div>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
              <Input className="pl-8 h-8 text-xs" placeholder="Search patients…" value={searchThread}
                onChange={e => setSearchThread(e.target.value)} data-testid="input-search-thread" />
            </div>
          </CardHeader>
          <CardContent className="pt-0 flex-1 overflow-y-auto">
            <div className="space-y-0.5">
              {/* Active threads (have message history) */}
              {filteredThreads.map(t => (
                <button
                  key={t.patientId}
                  onClick={() => { setSelectedPatientId(t.patientId); setSelectedPatientName(t.patientName); setComposing(false); threadOpenMut.mutate(t.patientId); }}
                  className={`w-full text-left px-3 py-2.5 rounded-lg flex items-start gap-2.5 transition-colors ${
                    selectedPatientId === t.patientId
                      ? "bg-primary/10 border border-primary/30"
                      : "hover:bg-muted border border-transparent"
                  }`}
                  data-testid={`thread-${t.patientId}`}
                >
                  <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center shrink-0 mt-0.5">
                    <span className="text-[10px] font-bold text-primary">{t.patientName.split(" ").map(n => n[0]).join("").slice(0, 2)}</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-0.5">
                      <span className={`text-sm ${t.unreadCount > 0 ? "font-semibold" : "font-medium"}`}>{t.patientName}</span>
                      <span className="text-[10px] text-muted-foreground shrink-0 ml-1">{fmtTime(t.lastCreatedAt)}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <p className="text-xs text-muted-foreground truncate pr-2">{t.lastBody}</p>
                      {t.unreadCount > 0 && (
                        <span className="shrink-0 text-[10px] font-semibold bg-primary text-primary-foreground rounded-full px-1.5 py-0.5 leading-tight" data-testid={`unread-badge-${t.patientId}`}>
                          {t.unreadCount}
                        </span>
                      )}
                    </div>
                  </div>
                </button>
              ))}

              {/* Patients with no messages yet */}
              {allPatientsWithNoThread.slice(0, 10).map((p: any) => (
                <button
                  key={p.id}
                  onClick={() => { setSelectedPatientId(p.id); setSelectedPatientName(`${p.firstName} ${p.lastName}`); setComposing(false); threadOpenMut.mutate(p.id); }}
                  className={`w-full text-left px-3 py-2.5 rounded-lg flex items-center gap-2.5 transition-colors ${
                    selectedPatientId === p.id
                      ? "bg-primary/10 border border-primary/30"
                      : "hover:bg-muted border border-transparent"
                  }`}
                  data-testid={`patient-item-${p.id}`}
                >
                  <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center shrink-0">
                    <User className="h-3.5 w-3.5 text-muted-foreground" />
                  </div>
                  <div className="min-w-0">
                    <div className="text-sm font-medium">{p.firstName} {p.lastName}</div>
                    <div className="text-xs text-muted-foreground truncate">{p.phone || p.email || "No contact info"}</div>
                  </div>
                </button>
              ))}

              {filteredThreads.length === 0 && allPatientsWithNoThread.length === 0 && (
                <p className="text-xs text-muted-foreground text-center py-8">No patients found</p>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Thread / Message View (right panel) */}
        <div className="lg:col-span-2 flex flex-col gap-3">
          {!selectedPatientId ? (
            <Card className="border-dashed flex-1">
              <CardContent className="h-full flex flex-col items-center justify-center py-20 text-muted-foreground">
                <MessageSquare className="h-10 w-10 mb-3 opacity-30" />
                <p className="text-sm">Select a conversation to view messages</p>
                <p className="text-xs mt-1 opacity-60">Or start a new conversation with any patient</p>
              </CardContent>
            </Card>
          ) : (
            <>
              {/* Thread Header */}
              <Card>
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <div className="w-9 h-9 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                        <span className="text-xs font-bold text-primary">
                          {selectedPatientName.split(" ").map(n => n[0]).join("").slice(0, 2)}
                        </span>
                      </div>
                      <div>
                        <div className="font-semibold text-sm">{selectedPatientName}</div>
                        <div className="text-xs text-muted-foreground flex items-center gap-1">
                          <Shield className="h-2.5 w-2.5 text-emerald-500" />
                          PHI access logged on thread open
                        </div>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      {messages.some(m => m.direction === "inbound") && (
                        <Button size="sm" variant="outline" onClick={handleAiSuggest} disabled={aiLoading} data-testid="button-ai-suggest">
                          {aiLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" /> : <Sparkles className="h-3.5 w-3.5 mr-1 text-purple-500" />}
                          AI Reply
                        </Button>
                      )}
                      <Button size="sm" onClick={() => setComposing(true)} data-testid="button-compose">
                        <Plus className="h-3.5 w-3.5 mr-1" /> Compose
                      </Button>
                    </div>
                  </div>
                </CardHeader>

                {/* Message Bubbles */}
                <CardContent className="pt-0">
                  {msgLoading ? (
                    <div className="flex justify-center py-8"><Loader2 className="h-5 w-5 animate-spin" /></div>
                  ) : messages.length === 0 ? (
                    <div className="text-center py-10 text-muted-foreground">
                      <MessageSquare className="h-7 w-7 mx-auto mb-2 opacity-30" />
                      <p className="text-sm">No messages yet</p>
                      <p className="text-xs mt-1">Compose a message or use a template below</p>
                    </div>
                  ) : (
                    <div className="space-y-2 max-h-[420px] overflow-y-auto px-1 pb-1" data-testid="thread-messages">
                      {messages.map(m => {
                        const chCfg = CHANNEL_CFG[m.channel] || CHANNEL_CFG.sms;
                        const stCfg = STATUS_CFG[m.status] || STATUS_CFG.sent;
                        const Icon = chCfg.icon;
                        const isOut = m.direction === "outbound";
                        const senderName = isOut ? (m.sentBy || "Staff") : selectedPatientName.split(" ")[0];
                        return (
                          <div key={m.id} className={`flex flex-col ${isOut ? "items-end" : "items-start"}`} data-testid={`msg-${m.id}`}>
                            <div className={`flex items-end gap-1.5 max-w-[78%] ${isOut ? "flex-row-reverse" : "flex-row"}`}>
                              {/* Avatar */}
                              <div className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 mb-1 ${isOut ? "bg-primary/20" : "bg-muted"}`}>
                                <span className="text-[8px] font-bold text-foreground/70">{senderName[0]}</span>
                              </div>
                              {/* Bubble */}
                              <div className={`rounded-2xl px-3.5 py-2.5 ${isOut ? "bg-primary text-primary-foreground rounded-br-sm" : "bg-muted rounded-bl-sm"}`}>
                                <div className={`flex items-center gap-1.5 mb-0.5 text-[9px] ${isOut ? "opacity-60 justify-end" : "opacity-50"}`}>
                                  <Icon className="h-2.5 w-2.5" />
                                  <span>{chCfg.label}</span>
                                  {m.templateUsed && <><span>·</span><span>{m.templateUsed}</span></>}
                                </div>
                                {m.subject && <div className="font-semibold text-xs mb-1">{m.subject}</div>}
                                <div className="text-sm whitespace-pre-wrap leading-snug">{m.body}</div>
                              </div>
                            </div>
                            {/* Metadata row */}
                            <div className={`flex items-center gap-1.5 mt-0.5 px-8 text-[10px] text-muted-foreground ${isOut ? "flex-row-reverse" : "flex-row"}`}>
                              <span className="font-medium">{senderName}</span>
                              <span>·</span>
                              <Clock className="h-2.5 w-2.5" />
                              <span>{fmtFull(m.createdAt)}</span>
                              {isOut && (
                                <>
                                  <span>·</span>
                                  {m.status === "read" && <CheckCheck className="h-3 w-3 text-teal-500" />}
                                  <span className={m.status === "read" ? "text-teal-500" : m.status === "failed" ? "text-red-500" : ""}>{stCfg.label}</span>
                                </>
                              )}
                            </div>
                          </div>
                        );
                      })}
                      <div ref={threadEndRef} />
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Compose Panel */}
              {composing && (
                <Card className="border-primary/30">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-sm flex items-center gap-2">
                      <Send className="h-3.5 w-3.5" />
                      New Message to {selectedPatientName.split(" ")[0]}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <Label className="text-xs">Channel</Label>
                        <Select value={form.channel} onValueChange={v => setForm(f => ({ ...f, channel: v }))}>
                          <SelectTrigger className="h-8 text-xs mt-1" data-testid="select-channel"><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="sms">SMS</SelectItem>
                            <SelectItem value="email">Email</SelectItem>
                            <SelectItem value="in_app">In-App</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div>
                        <Label className="text-xs">Template</Label>
                        <Select value={form.templateUsed} onValueChange={v => {
                          const tpl = TEMPLATES.find(t => t.name === v);
                          if (tpl) setForm(f => ({ ...f, templateUsed: v, body: tpl.body, channel: tpl.channel }));
                        }}>
                          <SelectTrigger className="h-8 text-xs mt-1"><SelectValue placeholder="Use template…" /></SelectTrigger>
                          <SelectContent>{TEMPLATES.map(t => <SelectItem key={t.name} value={t.name}>{t.name}</SelectItem>)}</SelectContent>
                        </Select>
                      </div>
                    </div>
                    {form.channel === "email" && (
                      <div>
                        <Label className="text-xs">Subject</Label>
                        <Input value={form.subject} onChange={e => setForm(f => ({ ...f, subject: e.target.value }))} className="h-8 text-xs mt-1" data-testid="input-subject" />
                      </div>
                    )}
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <Label className="text-xs">Message *</Label>
                        {form.channel === "sms" && (
                          <span className={`text-[10px] ${form.body.length > 160 ? "text-amber-500" : "text-muted-foreground"}`}>{form.body.length}/160</span>
                        )}
                      </div>
                      <Textarea value={form.body} onChange={e => setForm(f => ({ ...f, body: e.target.value }))} rows={4} className="text-xs" data-testid="textarea-message" />
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" onClick={() => sendMut.mutate()} disabled={sendMut.isPending || !form.body.trim()} data-testid="button-send">
                        {sendMut.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" /> : <Send className="h-3.5 w-3.5 mr-1" />}
                        Send
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => { setComposing(false); setForm({ channel: "sms", subject: "", body: "", templateUsed: "" }); }}>
                        Cancel
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              )}
            </>
          )}
        </div>
      </div>

      {/* Templates Row */}
      <Card>
        <CardHeader className="pb-3"><CardTitle className="text-sm">Message Templates</CardTitle></CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {TEMPLATES.map(t => {
              const cfg = CHANNEL_CFG[t.channel] || CHANNEL_CFG.sms;
              const Icon = cfg.icon;
              return (
                <div key={t.name}
                  className="rounded-lg border p-3 hover:border-primary/40 cursor-pointer transition-colors"
                  onClick={() => {
                    if (selectedPatientId) {
                      setForm(f => ({ ...f, body: t.body, channel: t.channel, templateUsed: t.name }));
                      setComposing(true);
                    } else {
                      toast({ title: "Select a patient first" });
                    }
                  }}
                  data-testid={`template-${t.name.toLowerCase().replace(/ /g, "-")}`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <Icon className={`h-3.5 w-3.5 ${cfg.color}`} />
                    <span className="text-xs font-semibold">{t.name}</span>
                    <Badge variant="outline" className="text-[10px] ml-auto">{cfg.label}</Badge>
                  </div>
                  <p className="text-[10px] text-muted-foreground line-clamp-2">{t.body}</p>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
