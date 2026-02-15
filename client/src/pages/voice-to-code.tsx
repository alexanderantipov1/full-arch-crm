import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  Mic,
  Zap,
  CheckCircle,
  FileText,
  Clock,
  Bot,
  Play,
  Square,
} from "lucide-react";

const soapNote = {
  provider: "Dr. Chen",
  patient: "Michael Torres",
  time: "2:18 PM",
  sections: [
    { label: "S — Subjective", text: "Patient presents for implant follow-up #17. Reports mild tenderness, no pain. Chewing carefully.", color: "text-primary" },
    { label: "O — Objective", text: "Implant #17 stable. Tissue healing well. No suppuration. Probing 2mm circumferential. Occlusion checked.", color: "text-teal-600 dark:text-teal-400" },
    { label: "A — Assessment", text: "Implant #17 osseointegration progressing normally at 8 weeks.", color: "text-purple-600 dark:text-purple-400" },
    { label: "P — Plan", text: "Continue soft diet 2 weeks. Return 4 weeks for final impression. D6058 abutment + D6065 crown.", color: "text-orange-600 dark:text-orange-400" },
  ],
  codes: [
    { code: "D6058", fee: "$950" },
    { code: "D6065", fee: "$1,650" },
  ],
};

const recentTranscriptions = [
  { provider: "Dr. Chen", patient: "Margaret Sullivan", procedure: "Implant Follow-up #14", time: "2:42 PM", codes: 2, status: "signed" },
  { provider: "Dr. Park", patient: "Diana Patel", procedure: "Invisalign Check #8", time: "2:15 PM", codes: 1, status: "signed" },
  { provider: "Dr. Okafor", patient: "James Okafor", procedure: "Perio Maintenance", time: "1:45 PM", codes: 3, status: "draft" },
  { provider: "Dr. Chen", patient: "Robert Kim", procedure: "Implant Consult", time: "11:30 AM", codes: 2, status: "signed" },
];

export default function VoiceToCodePage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">
          Voice-to-Code Pipeline
        </h1>
        <p className="text-sm text-muted-foreground">
          Speak naturally — AI generates SOAP notes and auto-codes CDT procedures
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Mic className="h-3.5 w-3.5" />
              Voice Notes Today
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-voice-notes">24</div>
            <p className="text-xs font-medium text-emerald-600 dark:text-emerald-400">6.8 hrs saved</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Zap className="h-3.5 w-3.5" />
              Processing Speed
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="kpi-speed">2.8 sec</div>
            <p className="text-xs font-medium text-muted-foreground">Speech to SOAP + codes</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <CheckCircle className="h-3.5 w-3.5" />
              Auto-Coded
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="kpi-auto-coded">98.4%</div>
            <p className="text-xs font-medium text-muted-foreground">Accuracy rate</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <FileText className="h-3.5 w-3.5" />
              Claims Generated
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-claims">22</div>
            <p className="text-xs font-medium text-muted-foreground">From voice notes</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Mic className="h-4 w-4 text-cyan-600 dark:text-cyan-400" />
            Latest Voice Transcription
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border-l-4 border-cyan-500 bg-cyan-500/5 p-4 mb-4">
            <div className="text-xs font-bold text-cyan-600 dark:text-cyan-400 mb-4">
              {soapNote.provider} — {soapNote.patient} — {soapNote.time}
            </div>
            {soapNote.sections.map((section, i) => (
              <div key={i} className="mb-3 rounded-md border-l-2 border-muted pl-3 py-1">
                <span className={`text-[10px] font-bold uppercase tracking-wider ${section.color}`}>
                  {section.label}
                </span>
                <p className="text-xs text-muted-foreground mt-0.5">{section.text}</p>
              </div>
            ))}
            <div className="flex items-center gap-2 mt-4 flex-wrap">
              {soapNote.codes.map((c, i) => (
                <Badge key={i} variant="outline" className="font-mono">
                  {c.code} — {c.fee}
                </Badge>
              ))}
              <Badge variant="default">
                <CheckCircle className="mr-1 h-3 w-3" />
                Auto-Coded
              </Badge>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Button data-testid="button-start-recording">
              <Mic className="mr-2 h-4 w-4" />
              Start Recording
            </Button>
            <Button variant="outline" data-testid="button-sign-note">
              <CheckCircle className="mr-2 h-4 w-4" />
              Sign Note
            </Button>
            <Button variant="outline" data-testid="button-ai-expand">
              <Bot className="mr-2 h-4 w-4" />
              AI Expand
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-4 w-4" />
            Recent Transcriptions
          </CardTitle>
        </CardHeader>
        <CardContent>
          {recentTranscriptions.map((t, i) => (
            <div key={i} className="flex items-center justify-between border-b py-3 last:border-0 gap-4" data-testid={`transcription-${i}`}>
              <div>
                <div className="text-sm font-bold">{t.patient}</div>
                <div className="text-xs text-muted-foreground">{t.procedure} / {t.provider} / {t.time}</div>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="font-mono text-xs">{t.codes} codes</Badge>
                <Badge variant={t.status === "signed" ? "default" : "outline"}>
                  {t.status === "signed" ? <CheckCircle className="mr-1 h-3 w-3" /> : <Clock className="mr-1 h-3 w-3" />}
                  {t.status}
                </Badge>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
