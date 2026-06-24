import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { useToast } from "@/hooks/use-toast";
import { apiRequest, queryClient } from "@/lib/queryClient";
import {
  Mic,
  Loader2,
  Sparkles,
  User,
  Calendar,
  CheckCircle,
  Printer,
  Stethoscope,
  ChevronDown,
} from "lucide-react";

interface ImplantNote {
  implantSite: string;
  implantSystem: string;
  torqueValue: string;
  isq: string;
  healingAbutment: string;
  nextStep: string;
}

interface SOAPNote {
  subjective: string;
  objective: string;
  assessment: string;
  plan: string;
  implantSpecific?: ImplantNote | null;
}

interface SuggestedCode {
  code: string;
  description: string;
  fee: number;
  confidence: "high" | "medium" | "low";
  rationale: string;
}

interface ScribeSession {
  id: string;
  patientId: string;
  patientName: string;
  providerId: string;
  providerName: string;
  dictationText: string;
  soapNote: SOAPNote;
  cdtCodes: SuggestedCode[];
  status: "draft" | "reviewed" | "signed";
  createdAt: string;
  signedAt: string | null;
}

const EXAMPLE_DICTATION =
  "Patient presents with failed upper right implant at site #3. Pain 6/10. ISQ 48 on resonance frequency analysis. Radiograph shows peri-implant radiolucency. Plan to remove implant, bone graft, and stage new implant in 4 months.";

const statusVariant: Record<ScribeSession["status"], string> = {
  draft: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300",
  reviewed: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
  signed: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
};

const confidenceVariant: Record<SuggestedCode["confidence"], string> = {
  high: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
  medium: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300",
  low: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
};

export default function AIScribePage() {
  const { toast } = useToast();
  const [patientName, setPatientName] = useState("");
  const [providerName, setProviderName] = useState("");
  const [dictationText, setDictationText] = useState("");
  const [session, setSession] = useState<ScribeSession | null>(null);
  const [soap, setSoap] = useState<SOAPNote | null>(null);

  const { data: recentSessions, isLoading: sessionsLoading } = useQuery<ScribeSession[]>({
    queryKey: ["/api/scribe/sessions"],
  });

  const isSigned = session?.status === "signed";

  const generateMutation = useMutation({
    mutationFn: async () => {
      const res = await apiRequest("POST", "/api/scribe/generate", {
        dictationText,
        patientName: patientName || "Patient",
        providerName: providerName || "Provider",
      });
      return (await res.json()) as ScribeSession;
    },
    onSuccess: (data) => {
      setSession(data);
      setSoap(data.soapNote);
      queryClient.invalidateQueries({ queryKey: ["/api/scribe/sessions"] });
      toast({ title: "SOAP Note Generated", description: "Review and edit before signing." });
    },
    onError: (error: Error) => {
      toast({ title: "Generation Failed", description: error.message, variant: "destructive" });
    },
  });

  const saveSoapMutation = useMutation({
    mutationFn: async (soapNote: SOAPNote) => {
      const res = await apiRequest("PATCH", `/api/scribe/sessions/${session!.id}/soap`, { soapNote });
      return (await res.json()) as ScribeSession;
    },
    onSuccess: (data) => {
      setSession(data);
      setSoap(data.soapNote);
      queryClient.invalidateQueries({ queryKey: ["/api/scribe/sessions"] });
    },
  });

  const statusMutation = useMutation({
    mutationFn: async (status: ScribeSession["status"]) => {
      // Persist any local SOAP edits before changing status.
      if (soap && session) {
        await apiRequest("PATCH", `/api/scribe/sessions/${session.id}/soap`, { soapNote: soap });
      }
      const res = await apiRequest("PATCH", `/api/scribe/sessions/${session!.id}/status`, { status });
      return (await res.json()) as ScribeSession;
    },
    onSuccess: (data) => {
      setSession(data);
      setSoap(data.soapNote);
      queryClient.invalidateQueries({ queryKey: ["/api/scribe/sessions"] });
      toast({
        title: data.status === "signed" ? "Note Signed & Locked" : "Marked Reviewed",
        description: data.status === "signed" ? "This note is now read-only." : undefined,
      });
    },
    onError: (error: Error) => {
      toast({ title: "Update Failed", description: error.message, variant: "destructive" });
    },
  });

  const handleGenerate = () => {
    if (!dictationText.trim()) {
      toast({ title: "Dictation Required", description: "Enter clinical findings first.", variant: "destructive" });
      return;
    }
    generateMutation.mutate();
  };

  const updateSoapField = (field: keyof SOAPNote, value: string) => {
    setSoap((prev) => (prev ? { ...prev, [field]: value } : prev));
  };

  const totalFee = session?.cdtCodes.reduce((sum, c) => sum + (Number(c.fee) || 0), 0) ?? 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold flex items-center gap-2" data-testid="text-page-title">
          <Mic className="h-7 w-7 text-primary" />
          AI Scribe
        </h1>
        <p className="text-muted-foreground">
          Dictate clinical findings — AI transcribes and structures them into a SOAP note with CDT code suggestions.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left column — Dictation Input */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Stethoscope className="h-5 w-5 text-primary" />
                Dictation
              </CardTitle>
              <CardDescription>Enter patient, provider, and dictated clinical findings.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Patient Name</Label>
                  <Input
                    value={patientName}
                    onChange={(e) => setPatientName(e.target.value)}
                    placeholder="Jane Doe"
                    data-testid="input-patient-name"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Provider Name</Label>
                  <Input
                    value={providerName}
                    onChange={(e) => setProviderName(e.target.value)}
                    placeholder="Dr. Smith"
                    data-testid="input-provider-name"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label>Clinical Findings</Label>
                <Textarea
                  value={dictationText}
                  onChange={(e) => setDictationText(e.target.value)}
                  rows={10}
                  placeholder={`Dictate clinical findings here... (paste typed transcription or dictation)\n\ne.g. ${EXAMPLE_DICTATION}`}
                  data-testid="input-dictation"
                />
              </div>

              <Button
                onClick={handleGenerate}
                disabled={generateMutation.isPending}
                className="w-full"
                data-testid="button-generate"
              >
                {generateMutation.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Generating...
                  </>
                ) : (
                  <>
                    <Sparkles className="mr-2 h-4 w-4" />
                    Generate SOAP Note
                  </>
                )}
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Recent Sessions</CardTitle>
              <CardDescription>Previously generated scribe sessions.</CardDescription>
            </CardHeader>
            <CardContent>
              {sessionsLoading ? (
                <div className="space-y-2">
                  {[1, 2, 3].map((i) => (
                    <Skeleton key={i} className="h-14" />
                  ))}
                </div>
              ) : recentSessions && recentSessions.length > 0 ? (
                <div className="space-y-2">
                  {recentSessions.map((s) => (
                    <button
                      key={s.id}
                      className="w-full text-left p-3 border rounded-lg hover-elevate"
                      onClick={() => {
                        setSession(s);
                        setSoap(s.soapNote);
                      }}
                      data-testid={`session-${s.id}`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-sm flex items-center gap-1.5">
                          <User className="h-3.5 w-3.5" />
                          {s.patientName}
                        </span>
                        <Badge className={statusVariant[s.status]}>{s.status}</Badge>
                      </div>
                      <div className="flex items-center gap-1.5 mt-1 text-xs text-muted-foreground">
                        <Calendar className="h-3 w-3" />
                        {new Date(s.createdAt).toLocaleString()}
                      </div>
                    </button>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground text-center py-4">No sessions yet.</p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right column — SOAP Note Output */}
        <div className="space-y-6">
          {session && soap ? (
            <>
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center gap-2">
                      SOAP Note
                      {isSigned && <CheckCircle className="h-5 w-5 text-green-600" />}
                    </CardTitle>
                    <Badge className={statusVariant[session.status]} data-testid="badge-status">
                      {session.status}
                    </Badge>
                  </div>
                  <CardDescription>
                    {session.patientName} · {session.providerName}
                    {isSigned && session.signedAt && (
                      <span className="block text-green-600 mt-1">
                        Signed {new Date(session.signedAt).toLocaleString()}
                      </span>
                    )}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {(["subjective", "objective", "assessment", "plan"] as const).map((field) => (
                    <div key={field} className="space-y-2">
                      <Label className="capitalize">{field}</Label>
                      <Textarea
                        value={soap[field]}
                        onChange={(e) => updateSoapField(field, e.target.value)}
                        onBlur={() => !isSigned && saveSoapMutation.mutate(soap)}
                        rows={4}
                        disabled={isSigned}
                        data-testid={`input-soap-${field}`}
                      />
                    </div>
                  ))}

                  {soap.implantSpecific && (
                    <Collapsible defaultOpen>
                      <CollapsibleTrigger className="flex items-center gap-2 text-sm font-medium w-full" data-testid="toggle-implant">
                        <ChevronDown className="h-4 w-4" />
                        Implant Details
                      </CollapsibleTrigger>
                      <CollapsibleContent className="pt-3 grid grid-cols-1 md:grid-cols-2 gap-3">
                        {(
                          [
                            ["implantSite", "Site"],
                            ["implantSystem", "System"],
                            ["torqueValue", "Torque"],
                            ["isq", "ISQ"],
                            ["healingAbutment", "Healing Abutment"],
                            ["nextStep", "Next Step"],
                          ] as const
                        ).map(([key, label]) => (
                          <div key={key} className="text-sm">
                            <span className="text-muted-foreground">{label}: </span>
                            <span className="font-medium" data-testid={`implant-${key}`}>
                              {soap.implantSpecific![key] || "—"}
                            </span>
                          </div>
                        ))}
                      </CollapsibleContent>
                    </Collapsible>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Suggested CDT Codes</CardTitle>
                  <CardDescription>AI-suggested billing codes — verify before submission.</CardDescription>
                </CardHeader>
                <CardContent>
                  {session.cdtCodes.length > 0 ? (
                    <div className="space-y-3">
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="text-left text-muted-foreground border-b">
                              <th className="py-2 pr-2">Code</th>
                              <th className="py-2 pr-2">Description</th>
                              <th className="py-2 pr-2 text-right">Fee</th>
                              <th className="py-2 pr-2">Conf.</th>
                            </tr>
                          </thead>
                          <tbody>
                            {session.cdtCodes.map((c, i) => (
                              <tr key={`${c.code}-${i}`} className="border-b align-top" data-testid={`cdt-row-${i}`}>
                                <td className="py-2 pr-2 font-mono font-medium">{c.code}</td>
                                <td className="py-2 pr-2">
                                  {c.description}
                                  {c.rationale && (
                                    <span className="block text-xs text-muted-foreground mt-0.5">{c.rationale}</span>
                                  )}
                                </td>
                                <td className="py-2 pr-2 text-right whitespace-nowrap">${Number(c.fee).toLocaleString()}</td>
                                <td className="py-2 pr-2">
                                  <Badge className={confidenceVariant[c.confidence]}>{c.confidence}</Badge>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                      <div className="flex justify-end font-semibold" data-testid="text-total-fee">
                        Total Estimate: ${totalFee.toLocaleString()}
                      </div>
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground text-center py-4">No codes suggested.</p>
                  )}
                </CardContent>
              </Card>

              <div className="flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  onClick={() => statusMutation.mutate("reviewed")}
                  disabled={isSigned || statusMutation.isPending}
                  data-testid="button-reviewed"
                >
                  Mark Reviewed
                </Button>
                <Button
                  onClick={() => statusMutation.mutate("signed")}
                  disabled={isSigned || statusMutation.isPending}
                  data-testid="button-sign"
                >
                  {statusMutation.isPending ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <CheckCircle className="mr-2 h-4 w-4" />
                  )}
                  Sign &amp; Lock
                </Button>
                <Button variant="outline" onClick={() => window.print()} data-testid="button-print">
                  <Printer className="mr-2 h-4 w-4" />
                  Print/Export
                </Button>
              </div>
            </>
          ) : (
            <Card className="flex items-center justify-center min-h-[300px]">
              <CardContent className="text-center text-muted-foreground py-12">
                <Mic className="h-10 w-10 mx-auto mb-3 opacity-40" />
                <p>Generate a SOAP note to see structured output here.</p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
