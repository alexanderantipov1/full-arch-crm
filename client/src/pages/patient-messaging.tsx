import { useState, useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
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
  ChevronRight, Sparkles, CheckCheck, Shield,
} from "lucide-react";

interface PatientMessage {
  id: number; patientId: number; direction: string; channel: string;
  subject: string | null; body: string; status: string; sentBy: string | null;
  templateUsed: string | null; createdAt: string;
}

const TEMPLATES = [
  { name: "Appointment Reminder", channel: "sms", body: "Hi {name}, this is a reminder for your appointment tomorrow at {time}. Please call us at {phone} to confirm or reschedule. Thank you!" },
  { name: "Post-Op Instructions", channel: "sms", body: "Hi {name}, your surgery is complete. Please follow the post-op instructions provided. Call us at {phone} if you have any concerns." },
  { name: "Lab Case Ready", channel: "sms", body: "Great news, {name}! Your dental work is ready. Please call us at {phone} to schedule your delivery appointment." },
  { name: "Balance Due", channel: "email", body: "Dear {name},\n\nThis is a friendly reminder that you have an outstanding balance due on your account. Please call our office to arrange payment.\n\nThank you,\nThe Team" },
  { name: "Welcome New Patient", channel: "email", body: "Welcome to our practice, {name}!\n\nWe are so glad to have you as a new patient. Your first appointment is confirmed. If you have any questions, please don't hesitate to reach out.\n\nWarm regards,\nThe Team" },
  { name: "Recall Due", channel: "sms", body: "Hi {name}, it's time for your regular dental check-up! Please call us at {phone} to schedule your appointment. We look forward to seeing you." },
];

const CHANNEL_CFG: Record<string, { label: string; icon: any; color: string }> = {
  sms:   { label: "SMS",    icon: Phone,        color: "text-emerald-600 dark:text-emerald-400" },
  email: { label: "Email",  icon: Mail,         color: "text-blue-600 dark:text-blue-400"    },
  in_app:{ label: "In-App", icon: MessageSquare, color: "text-purple-600 dark:text-purple-400" },
};

const STATUS_CFG: Record<string, { label: string; color: string }> = {
  sent:      { label: "Sent",      color: "text-blue-400"    },
  delivered: { label: "Delivered", color: "text-emerald-400" },
  read:      { label: "Read",      color: "text-teal-400"    },
  failed:    { label: "Failed",    color: "text-red-400"     },
  unread:    { label: "Unread",    color: "text-amber-400"   },
};

export default function PatientMessagingPage() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const threadEndRef = useRef<HTMLDivElement>(null);

  const [selectedPatient, setSelectedPatient] = useState<any | null>(null);
  const [searchPatient, setSearchPatient] = useState("");
  const [composing, setComposing] = useState(false);
  const [form, setForm] = useState({ channel: "sms", subject: "", body: "", templateUsed: "" });
  const [aiLoading, setAiLoading] = useState(false);

  const { data: patients = [] } = useQuery<any[]>({ queryKey: ["/api/patients"] });

  const { data: messages = [], isLoading } = useQuery<PatientMessage[]>({
    queryKey: ["/api/patient-messages", selectedPatient?.id],
    queryFn: () => fetch(`/api/patient-messages${selectedPatient ? `?patientId=${selectedPatient.id}` : ""}`, { credentials: "include" }).then(r => r.json()),
    enabled: !!selectedPatient,
  });

  const markReadMut = useMutation({
    mutationFn: (id: number) => apiRequest("PATCH", `/api/patient-messages/${id}/read`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/patient-messages"] });
      queryClient.invalidateQueries({ queryKey: ["/api/patient-messages/unread-count"] });
    },
  });

  const sendMut = useMutation({
    mutationFn: () => apiRequest("POST", "/api/patient-messages", {
      patientId: selectedPatient!.id,
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
      toast({ title: "Message sent" });
      setComposing(false);
      setForm({ channel: "sms", subject: "", body: "", templateUsed: "" });
    },
    onError: () => toast({ title: "Error sending message", variant: "destructive" }),
  });

  useEffect(() => {
    if (messages.length > 0) {
      threadEndRef.current?.scrollIntoView({ behavior: "smooth" });
      const unread = messages.filter(m => m.direction === "inbound" && m.status !== "read");
      unread.forEach(m => markReadMut.mutate(m.id));
    }
  }, [messages]);

  async function handleAiSuggest() {
    const inbound = messages.filter(m => m.direction === "inbound");
    const lastInbound = inbound[inbound.length - 1];
    if (!lastInbound) {
      toast({ title: "No inbound message to reply to", variant: "destructive" });
      return;
    }
    setAiLoading(true);
    try {
      const res = await fetch("/api/ai/suggest-reply", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          patientName: `${selectedPatient?.firstName} ${selectedPatient?.lastName}`,
          lastMessage: lastInbound.body,
          channel: form.channel,
        }),
      });
      const data = await res.json();
      if (data.suggestion) {
        setForm(f => ({ ...f, body: data.suggestion }));
        setComposing(true);
        toast({ title: "AI reply suggestion ready" });
      }
    } catch {
      toast({ title: "AI suggestion failed", variant: "destructive" });
    } finally {
      setAiLoading(false);
    }
  }

  const filteredPatients = patients.filter((p: any) =>
    `${p.firstName} ${p.lastName}`.toLowerCase().includes(searchPatient.toLowerCase())
  );

  const totalSent     = messages.filter(m => m.direction === "outbound").length;
  const totalInbound  = messages.filter(m => m.direction === "inbound").length;
  const unreadCount   = messages.filter(m => m.direction === "inbound" && m.status !== "read").length;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">Patient Communication</h1>
          <p className="text-sm text-muted-foreground">2-way messaging via SMS, email, and in-app · HIPAA-compliant</p>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground border rounded-md px-2.5 py-1.5">
          <Shield className="h-3.5 w-3.5 text-emerald-500" />
          PHI access logged
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Total Messages", value: messages.length },
          { label: "Outbound", value: totalSent },
          { label: "Inbound", value: totalInbound },
          { label: "Unread", value: unreadCount },
        ].map(k => (
          <Card key={k.label}>
            <CardContent className="pt-4 pb-4">
              <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">{k.label}</div>
              <div className="text-2xl font-bold font-mono" data-testid={`kpi-${k.label.toLowerCase().replace(/ /g, "-")}`}>{k.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Patient List */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Patients</CardTitle>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
              <Input className="pl-8 h-8 text-xs" placeholder="Search…" value={searchPatient}
                onChange={e => setSearchPatient(e.target.value)} data-testid="input-search-patient" />
            </div>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="space-y-1 max-h-[520px] overflow-y-auto">
              {filteredPatients.slice(0, 30).map((p: any) => (
                <button
                  key={p.id}
                  onClick={() => { setSelectedPatient(p); setComposing(false); }}
                  className={`w-full text-left px-3 py-2.5 rounded-lg border flex items-center justify-between transition-colors ${
                    selectedPatient?.id === p.id ? "border-primary bg-primary/5" : "border-transparent hover:border-border"
                  }`}
                  data-testid={`patient-item-${p.id}`}
                >
                  <div className="min-w-0">
                    <div className="text-sm font-medium truncate">{p.firstName} {p.lastName}</div>
                    <div className="text-xs text-muted-foreground truncate">{p.phone || p.email || "—"}</div>
                  </div>
                  <ChevronRight className="h-3.5 w-3.5 text-muted-foreground shrink-0 ml-2" />
                </button>
              ))}
              {filteredPatients.length === 0 && (
                <p className="text-xs text-muted-foreground text-center py-6">No patients found</p>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Thread Panel */}
        <div className="lg:col-span-2 flex flex-col gap-3">
          {!selectedPatient ? (
            <Card className="border-dashed">
              <CardContent className="py-20 text-center text-muted-foreground">
                <MessageSquare className="h-10 w-10 mx-auto mb-3 opacity-30" />
                <p className="text-sm">Select a patient to view their message thread</p>
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
                          {selectedPatient.firstName?.[0]}{selectedPatient.lastName?.[0]}
                        </span>
                      </div>
                      <div>
                        <div className="font-semibold text-sm">{selectedPatient.firstName} {selectedPatient.lastName}</div>
                        <div className="text-xs text-muted-foreground">{selectedPatient.phone} · {selectedPatient.email}</div>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      {messages.filter(m => m.direction === "inbound").length > 0 && (
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
                <CardContent className="pt-0">
                  {isLoading ? (
                    <div className="flex justify-center py-8"><Loader2 className="h-5 w-5 animate-spin" /></div>
                  ) : messages.length === 0 ? (
                    <p className="text-sm text-muted-foreground italic text-center py-8">No messages yet. Compose the first one.</p>
                  ) : (
                    <div className="space-y-2 max-h-[420px] overflow-y-auto px-1">
                      {messages.map(m => {
                        const chCfg = CHANNEL_CFG[m.channel] || CHANNEL_CFG.sms;
                        const stCfg = STATUS_CFG[m.status] || STATUS_CFG.sent;
                        const Icon = chCfg.icon;
                        const isOut = m.direction === "outbound";
                        return (
                          <div key={m.id} className={`flex ${isOut ? "justify-end" : "justify-start"}`} data-testid={`msg-${m.id}`}>
                            {!isOut && (
                              <div className="w-7 h-7 rounded-full bg-muted flex items-center justify-center mr-1.5 shrink-0 self-end mb-1">
                                <span className="text-[9px] font-bold">{selectedPatient.firstName?.[0]}</span>
                              </div>
                            )}
                            <div className={`max-w-[72%] rounded-2xl px-3.5 py-2.5 ${
                              isOut ? "bg-primary text-primary-foreground rounded-br-sm" : "bg-muted rounded-bl-sm"
                            }`}>
                              <div className={`flex items-center gap-1 mb-1 text-[9px] ${isOut ? "opacity-60 justify-end" : "opacity-50"}`}>
                                <Icon className="h-2.5 w-2.5" />
                                <span>{chCfg.label}</span>
                                {m.templateUsed && <span>· {m.templateUsed}</span>}
                              </div>
                              {m.subject && <div className="font-semibold text-xs mb-1">{m.subject}</div>}
                              <div className="text-sm whitespace-pre-wrap leading-snug">{m.body}</div>
                              <div className={`flex items-center gap-1 mt-1 text-[9px] ${isOut ? "justify-end opacity-60" : "opacity-50"}`}>
                                <span>{new Date(m.createdAt).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}</span>
                                {isOut && (
                                  <span className={stCfg.color}>
                                    {m.status === "read" ? <CheckCheck className="h-2.5 w-2.5 inline" /> : null}
                                    {" "}{stCfg.label}
                                  </span>
                                )}
                              </div>
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
                      New Message to {selectedPatient.firstName}
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
                          <span className={`text-[10px] ${form.body.length > 160 ? "text-amber-500" : "text-muted-foreground"}`}>
                            {form.body.length}/160
                          </span>
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

      {/* Templates */}
      <Card>
        <CardHeader><CardTitle className="text-sm">Message Templates</CardTitle></CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {TEMPLATES.map(t => {
              const cfg = CHANNEL_CFG[t.channel] || CHANNEL_CFG.sms;
              const Icon = cfg.icon;
              return (
                <div key={t.name}
                  className="rounded-lg border p-3 hover:border-primary/40 cursor-pointer transition-colors"
                  onClick={() => {
                    if (selectedPatient) {
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
