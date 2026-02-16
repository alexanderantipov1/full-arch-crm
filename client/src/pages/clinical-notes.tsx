import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Progress } from "@/components/ui/progress";
import {
  FileText,
  Mic,
  Brain,
  LayoutTemplate,
  Clock,
  User,
  CheckCircle,
  ArrowRight,
  Code,
  Activity,
  Stethoscope,
  Scissors,
  Sparkles,
} from "lucide-react";

const recentNotes = [
  { id: 1, patient: "Maria Garcia", provider: "Dr. Chen", type: "SOAP", time: "2:42 PM", codes: ["D2750", "D9215"], status: "completed" },
  { id: 2, patient: "Tom Davis", provider: "Dr. Patel", type: "Progress", time: "2:18 PM", codes: ["D0220"], status: "completed" },
  { id: 3, patient: "Sarah Chen", provider: "Dr. Chen", type: "Procedure", time: "1:55 PM", codes: ["D7210", "D9215", "D7953"], status: "in-review" },
  { id: 4, patient: "Frank Morris", provider: "Dr. Patel", type: "SOAP", time: "1:30 PM", codes: ["D4341", "D4342"], status: "completed" },
  { id: 5, patient: "Karen Brown", provider: "Dr. Chen", type: "Progress", time: "12:45 PM", codes: ["D0150"], status: "pending" },
  { id: 6, patient: "Pete Hall", provider: "Dr. Patel", type: "Procedure", time: "11:20 AM", codes: ["D2391", "D2392"], status: "completed" },
  { id: 7, patient: "Lisa Wang", provider: "Dr. Chen", type: "SOAP", time: "10:50 AM", codes: ["D6010", "D6058"], status: "completed" },
  { id: 8, patient: "James Lee", provider: "Dr. Patel", type: "Progress", time: "10:15 AM", codes: ["D8090"], status: "in-review" },
];

const soapTemplates = [
  { name: "Implant Consult", icon: Stethoscope, fields: ["Chief Complaint", "Medical Hx Review", "CBCT Findings", "Bone Density Assessment", "Treatment Options", "Implant System Rec", "Timeline & Phases", "Fee Estimate"] },
  { name: "Crown Prep", icon: Activity, fields: ["Tooth #", "Prep Type (PFM/Zirconia/E.max)", "Shade Selection", "Impression Method", "Temporization", "Occlusion Check", "Cement Type", "Post-Op Instructions"] },
  { name: "Perio Maintenance", icon: FileText, fields: ["Probe Depths (6-point)", "Bleeding on Probing", "Plaque Score", "Calculus Level", "SRP Areas", "Irrigation", "Recall Interval", "Home Care Instructions"] },
  { name: "Extraction", icon: Scissors, fields: ["Tooth #", "Reason for Extraction", "Anesthesia Type", "Surgical vs Simple", "Socket Preservation", "Hemostasis Method", "Post-Op Rx", "Follow-up Plan"] },
  { name: "Composite Filling", icon: Sparkles, fields: ["Tooth #", "Surface(s)", "Caries Depth", "Liner/Base", "Shade Match", "Composite Type", "Curing Protocol", "Occlusal Adjustment"] },
];

const statusColors: Record<string, string> = {
  completed: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400",
  "in-review": "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400",
  pending: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
};

const noteTypeColors: Record<string, string> = {
  SOAP: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400",
  Progress: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
  Procedure: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
};

const aiCodingExamples = [
  {
    narrative: "Crown prep on tooth 3, PFM, with local anesthesia. Patient presented with fractured cusp on #3. Administered 2% lidocaine with 1:100k epi. Prepared tooth for PFM crown, took PVS impression, fabricated and cemented acrylic temporary.",
    codes: [
      { code: "D2750", desc: "Crown - porcelain fused to high noble metal", fee: "$1,280" },
      { code: "D9215", desc: "Local anesthesia in addition to operative procedure", fee: "$45" },
    ],
  },
  {
    narrative: "Scaling and root planing, upper right quadrant, with irrigation. Heavy subgingular calculus noted in UR quadrant. Probe depths 5-7mm on #2, #3, #4. Performed SRP with ultrasonic and hand instruments. Irrigated with chlorhexidine.",
    codes: [
      { code: "D4341", desc: "Periodontal SRP - four or more teeth per quadrant", fee: "$290" },
      { code: "D4921", desc: "Gingival irrigation - per quadrant", fee: "$45" },
    ],
  },
];

export default function ClinicalNotesPage() {
  const [activeTab, setActiveTab] = useState("recent");

  return (
    <div className="flex-1 overflow-auto p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2" data-testid="text-page-title">
            <FileText className="h-6 w-6 text-primary" />
            Clinical Notes
          </h1>
          <p className="text-sm text-muted-foreground">AI-powered clinical documentation with voice-to-SOAP and auto-coding</p>
        </div>
        <Button data-testid="button-new-note">
          <Mic className="h-4 w-4 mr-2" />
          New Voice Note
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <FileText className="h-3.5 w-3.5" />
              Notes Today
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-notes-today">24</div>
            <p className="text-xs font-medium text-muted-foreground">8 SOAP, 10 progress, 6 procedure</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Mic className="h-3.5 w-3.5" />
              Voice Notes
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-voice-notes">18</div>
            <p className="text-xs font-medium text-emerald-600 dark:text-emerald-400">6.8 hrs saved</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Brain className="h-3.5 w-3.5" />
              Auto-Coded
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="kpi-auto-coded">98.4%</div>
            <p className="text-xs font-medium text-muted-foreground">CDT codes auto-assigned</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <LayoutTemplate className="h-3.5 w-3.5" />
              Templates Active
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-templates">12</div>
            <p className="text-xs font-medium text-muted-foreground">5 SOAP, 4 procedure, 3 custom</p>
          </CardContent>
        </Card>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList data-testid="tabs-clinical-notes">
          <TabsTrigger value="recent" data-testid="tab-recent-notes">
            <Clock className="h-4 w-4 mr-1.5" />
            Recent Notes
          </TabsTrigger>
          <TabsTrigger value="templates" data-testid="tab-soap-templates">
            <LayoutTemplate className="h-4 w-4 mr-1.5" />
            SOAP Templates
          </TabsTrigger>
          <TabsTrigger value="voice" data-testid="tab-voice-transcription">
            <Mic className="h-4 w-4 mr-1.5" />
            Voice Transcription
          </TabsTrigger>
          <TabsTrigger value="coding" data-testid="tab-ai-coding">
            <Brain className="h-4 w-4 mr-1.5" />
            AI Coding
          </TabsTrigger>
        </TabsList>

        <TabsContent value="recent">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Clock className="h-4 w-4" />
                Recent Clinical Notes
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Patient</TableHead>
                    <TableHead>Provider</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Time</TableHead>
                    <TableHead>CDT Codes</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {recentNotes.map((note) => (
                    <TableRow key={note.id} data-testid={`note-row-${note.id}`} className="cursor-pointer">
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <User className="h-4 w-4 text-muted-foreground" />
                          <span className="font-medium" data-testid={`note-patient-${note.id}`}>{note.patient}</span>
                        </div>
                      </TableCell>
                      <TableCell className="text-muted-foreground" data-testid={`note-provider-${note.id}`}>{note.provider}</TableCell>
                      <TableCell>
                        <Badge className={noteTypeColors[note.type]} data-testid={`note-type-${note.id}`}>{note.type}</Badge>
                      </TableCell>
                      <TableCell className="text-muted-foreground" data-testid={`note-time-${note.id}`}>{note.time}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1 flex-wrap">
                          {note.codes.map((code) => (
                            <Badge key={code} variant="outline" className="font-mono text-xs" data-testid={`note-code-${note.id}-${code}`}>{code}</Badge>
                          ))}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge className={statusColors[note.status]} data-testid={`note-status-${note.id}`}>{note.status}</Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="templates">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {soapTemplates.map((template, i) => (
              <Card key={i} data-testid={`template-card-${i}`}>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <template.icon className="h-4 w-4 text-primary" />
                    {template.name}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-1.5">
                    {template.fields.map((field, fi) => (
                      <div key={fi} className="flex items-center gap-2 text-sm text-muted-foreground" data-testid={`template-field-${i}-${fi}`}>
                        <CheckCircle className="h-3 w-3 text-emerald-600 dark:text-emerald-400 shrink-0" />
                        {field}
                      </div>
                    ))}
                  </div>
                  <Button variant="outline" className="w-full mt-4" data-testid={`button-use-template-${i}`}>
                    Use Template
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="voice">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Mic className="h-4 w-4 text-primary" />
                  Raw Transcription
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="rounded-md bg-muted/50 p-4 text-sm leading-relaxed" data-testid="voice-raw-transcription">
                  <p className="text-muted-foreground italic">
                    "Patient Maria Garcia presents today for crown prep on tooth number three. She reports sensitivity to cold for the past two weeks. On examination, I noted a large failing amalgam with recurrent decay on the mesial and occlusal surfaces. Radiograph confirms no periapical pathology. I administered two carpules of two percent lidocaine with one to one hundred thousand epinephrine. Prepared the tooth for a porcelain fused to metal crown. Took a PVS impression and fabricated an acrylic temporary. Patient tolerated the procedure well. Advised soft diet and to return in two weeks for cementation. Plan to deliver PFM crown and check occlusion."
                  </p>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <FileText className="h-4 w-4 text-primary" />
                  Extracted SOAP Note
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div data-testid="soap-subjective">
                  <div className="flex items-center gap-2 mb-1">
                    <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400">S</Badge>
                    <span className="text-sm font-semibold">Subjective</span>
                  </div>
                  <p className="text-sm text-muted-foreground pl-8">Patient reports sensitivity to cold on tooth #3 for 2 weeks. No spontaneous pain.</p>
                </div>
                <div data-testid="soap-objective">
                  <div className="flex items-center gap-2 mb-1">
                    <Badge className="bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400">O</Badge>
                    <span className="text-sm font-semibold">Objective</span>
                  </div>
                  <p className="text-sm text-muted-foreground pl-8">Large failing amalgam #3 MOD with recurrent decay. Radiograph: no periapical pathology. Vitality test positive.</p>
                </div>
                <div data-testid="soap-assessment">
                  <div className="flex items-center gap-2 mb-1">
                    <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400">A</Badge>
                    <span className="text-sm font-semibold">Assessment</span>
                  </div>
                  <p className="text-sm text-muted-foreground pl-8">Recurrent caries #3 MOD. Tooth requires full-coverage restoration due to remaining structure.</p>
                </div>
                <div data-testid="soap-plan">
                  <div className="flex items-center gap-2 mb-1">
                    <Badge className="bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400">P</Badge>
                    <span className="text-sm font-semibold">Plan</span>
                  </div>
                  <p className="text-sm text-muted-foreground pl-8">PFM crown prep completed today. Temp cemented. Return 2 weeks for delivery. Check occlusion at seat.</p>
                </div>

                <div className="border-t pt-4 mt-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Code className="h-4 w-4 text-primary" />
                    <span className="text-sm font-semibold">Auto-Generated CDT Codes</span>
                  </div>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between rounded-md bg-muted/50 p-2" data-testid="voice-code-d2750">
                      <div>
                        <span className="font-mono text-sm font-bold">D2750</span>
                        <span className="text-sm text-muted-foreground ml-2">Crown - porcelain fused to high noble metal</span>
                      </div>
                      <Badge variant="outline" className="font-mono">$1,280</Badge>
                    </div>
                    <div className="flex items-center justify-between rounded-md bg-muted/50 p-2" data-testid="voice-code-d9215">
                      <div>
                        <span className="font-mono text-sm font-bold">D9215</span>
                        <span className="text-sm text-muted-foreground ml-2">Local anesthesia</span>
                      </div>
                      <Badge variant="outline" className="font-mono">$45</Badge>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="coding">
          <div className="space-y-6">
            {aiCodingExamples.map((example, i) => (
              <Card key={i} data-testid={`ai-coding-example-${i}`}>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Brain className="h-4 w-4 text-primary" />
                    AI Coding Example {i + 1}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                    <div>
                      <div className="flex items-center gap-2 mb-2">
                        <FileText className="h-4 w-4 text-muted-foreground" />
                        <span className="text-sm font-semibold">Clinical Narrative</span>
                      </div>
                      <div className="rounded-md bg-muted/50 p-4 text-sm text-muted-foreground italic" data-testid={`coding-narrative-${i}`}>
                        "{example.narrative}"
                      </div>
                    </div>
                    <div>
                      <div className="flex items-center gap-2 mb-2">
                        <ArrowRight className="h-4 w-4 text-primary" />
                        <span className="text-sm font-semibold">Extracted CDT Codes</span>
                      </div>
                      <div className="space-y-2">
                        {example.codes.map((code, ci) => (
                          <div key={ci} className="flex items-center justify-between rounded-md border p-3" data-testid={`coding-result-${i}-${code.code}`}>
                            <div>
                              <span className="font-mono text-sm font-bold text-primary">{code.code}</span>
                              <p className="text-xs text-muted-foreground mt-0.5">{code.desc}</p>
                            </div>
                            <Badge variant="outline" className="font-mono text-sm">{code.fee}</Badge>
                          </div>
                        ))}
                        <div className="flex items-center justify-between pt-2 border-t">
                          <span className="text-sm font-semibold">Total</span>
                          <span className="font-mono font-bold" data-testid={`coding-total-${i}`}>
                            ${example.codes.reduce((sum, c) => sum + parseFloat(c.fee.replace(/[$,]/g, "")), 0).toLocaleString()}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Activity className="h-4 w-4 text-primary" />
                  AI Coding Accuracy
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div data-testid="accuracy-exact-match">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm">Exact Code Match</span>
                    <span className="text-sm font-mono font-bold">96.2%</span>
                  </div>
                  <Progress value={96.2} />
                </div>
                <div data-testid="accuracy-fee-accuracy">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm">Fee Schedule Accuracy</span>
                    <span className="text-sm font-mono font-bold">99.1%</span>
                  </div>
                  <Progress value={99.1} />
                </div>
                <div data-testid="accuracy-narrative-coverage">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm">Narrative Coverage</span>
                    <span className="text-sm font-mono font-bold">98.4%</span>
                  </div>
                  <Progress value={98.4} />
                </div>
                <div data-testid="accuracy-provider-override">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm">Provider Override Rate</span>
                    <span className="text-sm font-mono font-bold">1.6%</span>
                  </div>
                  <Progress value={1.6} />
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
