import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  Video,
  Camera,
  CheckCircle,
  Clock,
  Calendar,
  Shield,
  DollarSign,
  AlertTriangle,
  Image,
  Monitor,
  FileText,
  Zap,
} from "lucide-react";

const todayQueue = [
  { id: 1, patient: "Sarah Chen", reason: "Implant consult (new lead)", time: "11:00 AM", type: "Video", status: "waiting" },
  { id: 2, patient: "Tom Davis", reason: "Post-op check (extraction #14)", time: "1:00 PM", type: "Video", status: "scheduled" },
  { id: 3, patient: "Nina Fox", reason: "Photo triage (swelling R mandible)", time: "ASAP", type: "Photo", status: "urgent" },
  { id: 4, patient: "Frank Morris", reason: "Crown sensitivity follow-up", time: "2:30 PM", type: "Video", status: "scheduled" },
  { id: 5, patient: "Lisa Wang", reason: "Invisalign tracking check", time: "3:00 PM", type: "Video", status: "waiting" },
  { id: 6, patient: "James Lee", reason: "Photo triage (gum recession)", time: "3:30 PM", type: "Photo", status: "waiting" },
];

const photoTriageItems = [
  { id: 1, patient: "Nina Fox", area: "Right mandible / molar area", urgency: "High", aiAssessment: "Possible post-extraction infection. Swelling + erythema noted. Recommend in-office visit within 24 hours.", status: "Needs in-office" },
  { id: 2, patient: "James Lee", area: "Lower anterior lingual", urgency: "Medium", aiAssessment: "Mild gingival recession noted on #24, #25. No active inflammation. Monitor and discuss at next hygiene visit.", status: "Advice only" },
  { id: 3, patient: "Karen Brown", area: "Upper right premolar", urgency: "Low", aiAssessment: "Minor staining around restoration margin #4. No caries detected. Normal post-crown appearance.", status: "Advice only" },
  { id: 4, patient: "Pete Hall", area: "Maxillary anterior", urgency: "Medium", aiAssessment: "Chipped incisal edge #8. Cosmetic concern. Can be repaired with composite bonding. Schedule at convenience.", status: "Schedule appt" },
  { id: 5, patient: "Rosa Martinez", area: "Left buccal mucosa", urgency: "High", aiAssessment: "White lesion on L buccal mucosa ~8mm. Duration unknown. Recommend biopsy. Schedule within 1 week.", status: "Needs in-office" },
];

const billingCodes = [
  { code: "D9995", description: "Teledentistry - synchronous; real-time encounter", type: "Synchronous", avgReimbursement: "$75", payerCoverage: "85%", notes: "Live video consult with patient" },
  { code: "D9996", description: "Teledentistry - asynchronous; information stored and forwarded", type: "Asynchronous", avgReimbursement: "$55", payerCoverage: "72%", notes: "Photo/store-and-forward review" },
  { code: "D0140", description: "Limited oral evaluation - problem focused", type: "Add-on", avgReimbursement: "$65", payerCoverage: "92%", notes: "Can be billed with D9995/D9996" },
  { code: "D0170", description: "Re-evaluation - limited, problem focused", type: "Add-on", avgReimbursement: "$50", payerCoverage: "88%", notes: "Post-op or follow-up re-eval" },
  { code: "D9310", description: "Consultation - diagnostic service by specialist", type: "Specialist", avgReimbursement: "$120", payerCoverage: "78%", notes: "Specialist teleconsultation" },
  { code: "D0350", description: "2D oral/facial photographic image", type: "Photo", avgReimbursement: "$25", payerCoverage: "65%", notes: "Photo documentation for triage" },
];

const statusConfig: Record<string, { color: string }> = {
  waiting: { color: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400" },
  scheduled: { color: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400" },
  urgent: { color: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400" },
};

const urgencyConfig: Record<string, string> = {
  High: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
  Medium: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400",
  Low: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
};

const triageStatusConfig: Record<string, string> = {
  "Needs in-office": "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
  "Advice only": "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
  "Schedule appt": "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
};

export default function TelehealthPage() {
  const [activeTab, setActiveTab] = useState("queue");

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">
            Teledentistry Module
          </h1>
          <p className="text-sm text-muted-foreground">
            HIPAA-compliant video consults, photo triage, remote monitoring (D9995/D9996)
          </p>
        </div>
        <Button data-testid="button-new-consult">
          <Video className="h-4 w-4 mr-2" />
          New Consult
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Video className="h-3.5 w-3.5" />
              Video Consults MTD
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-video">24</div>
            <p className="text-xs font-medium text-emerald-600 dark:text-emerald-400">$4,800 billed</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Camera className="h-3.5 w-3.5" />
              Photo Triage
            </div>
            <div className="mt-1 text-2xl font-bold font-mono" data-testid="kpi-photo">18</div>
            <p className="text-xs font-medium text-muted-foreground">12 in-office, 6 advice only</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <CheckCircle className="h-3.5 w-3.5" />
              Post-Op Checks
            </div>
            <div className="mt-1 text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="kpi-postop">34</div>
            <p className="text-xs font-medium text-muted-foreground">0 complications</p>
          </CardContent>
        </Card>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList data-testid="tabs-telehealth">
          <TabsTrigger value="queue" data-testid="tab-queue">
            <Calendar className="h-4 w-4 mr-1.5" />
            Queue
          </TabsTrigger>
          <TabsTrigger value="video" data-testid="tab-video-room">
            <Monitor className="h-4 w-4 mr-1.5" />
            Video Room
          </TabsTrigger>
          <TabsTrigger value="photo" data-testid="tab-photo-triage">
            <Image className="h-4 w-4 mr-1.5" />
            Photo Triage
          </TabsTrigger>
          <TabsTrigger value="billing" data-testid="tab-billing">
            <DollarSign className="h-4 w-4 mr-1.5" />
            Billing
          </TabsTrigger>
        </TabsList>

        <TabsContent value="queue">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Calendar className="h-4 w-4" />
                Today's Telehealth Queue
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Patient</TableHead>
                    <TableHead>Reason</TableHead>
                    <TableHead>Time</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {todayQueue.map((q) => (
                    <TableRow key={q.id} data-testid={`queue-row-${q.id}`}>
                      <TableCell className="font-medium" data-testid={`queue-patient-${q.id}`}>{q.patient}</TableCell>
                      <TableCell className="text-muted-foreground text-sm" data-testid={`queue-reason-${q.id}`}>{q.reason}</TableCell>
                      <TableCell data-testid={`queue-time-${q.id}`}>
                        <div className="flex items-center gap-1.5">
                          <Clock className="h-3.5 w-3.5 text-muted-foreground" />
                          <span className="text-sm">{q.time}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" data-testid={`queue-type-${q.id}`}>
                          {q.type === "Video" ? <Video className="mr-1 h-3 w-3" /> : <Camera className="mr-1 h-3 w-3" />}
                          {q.type}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge className={statusConfig[q.status]?.color} data-testid={`queue-status-${q.id}`}>{q.status}</Badge>
                      </TableCell>
                      <TableCell>
                        {q.type === "Video" ? (
                          <Button size="sm" data-testid={`button-join-${q.id}`}>
                            <Video className="h-3.5 w-3.5 mr-1" />
                            Join
                          </Button>
                        ) : (
                          <Button size="sm" variant="outline" data-testid={`button-review-${q.id}`}>
                            <Image className="h-3.5 w-3.5 mr-1" />
                            Review
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="video">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card className="flex flex-col items-center justify-center p-8 bg-muted/30">
              <div className="rounded-lg bg-zinc-900 dark:bg-zinc-950 p-12 flex flex-col items-center justify-center w-full max-w-md">
                <Video className="h-16 w-16 text-zinc-500 mb-4" />
                <p className="text-sm font-semibold text-zinc-300 mb-2">HIPAA-Compliant Video Room</p>
                <div className="flex items-center gap-2 mb-4">
                  <Shield className="h-4 w-4 text-emerald-400" />
                  <span className="text-xs text-emerald-400 font-medium">End-to-end encrypted</span>
                </div>
                <Button size="lg" data-testid="button-start-video">
                  <Video className="mr-2 h-4 w-4" />
                  Start Video Consult
                </Button>
              </div>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <FileText className="h-4 w-4" />
                  Billing Codes Reference
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="rounded-md bg-muted/50 p-4" data-testid="billing-ref-d9995">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-mono text-sm font-bold">D9995</span>
                    <Badge variant="outline" className="font-mono">$75</Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">Teledentistry - synchronous; real-time encounter</p>
                  <p className="text-xs text-muted-foreground mt-1">Use for live video consultations with patient present</p>
                </div>
                <div className="rounded-md bg-muted/50 p-4" data-testid="billing-ref-d9996">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-mono text-sm font-bold">D9996</span>
                    <Badge variant="outline" className="font-mono">$55</Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">Teledentistry - asynchronous; information stored and forwarded</p>
                  <p className="text-xs text-muted-foreground mt-1">Use for photo triage and store-and-forward reviews</p>
                </div>
                <div className="rounded-md bg-muted/50 p-4" data-testid="billing-ref-tips">
                  <div className="flex items-center gap-2 mb-1">
                    <Zap className="h-4 w-4 text-primary" />
                    <span className="text-sm font-semibold">Billing Tips</span>
                  </div>
                  <ul className="text-xs text-muted-foreground space-y-1 mt-1">
                    <li className="flex items-center gap-1.5"><CheckCircle className="h-3 w-3 text-emerald-500 shrink-0" />D9995/D9996 can be billed with D0140 (limited eval)</li>
                    <li className="flex items-center gap-1.5"><CheckCircle className="h-3 w-3 text-emerald-500 shrink-0" />Document patient consent for telehealth visit</li>
                    <li className="flex items-center gap-1.5"><CheckCircle className="h-3 w-3 text-emerald-500 shrink-0" />Include screenshot/photo in patient record</li>
                    <li className="flex items-center gap-1.5"><CheckCircle className="h-3 w-3 text-emerald-500 shrink-0" />State licensure requirements must be met</li>
                  </ul>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="photo">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Camera className="h-4 w-4" />
                Photo Triage Submissions
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {photoTriageItems.map((item) => (
                  <div key={item.id} className="rounded-md bg-muted/30 p-4" data-testid={`photo-triage-${item.id}`}>
                    <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-bold" data-testid={`triage-patient-${item.id}`}>{item.patient}</span>
                        <span className="text-xs text-muted-foreground">{item.area}</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <Badge className={urgencyConfig[item.urgency]} data-testid={`triage-urgency-${item.id}`}>
                          {item.urgency === "High" && <AlertTriangle className="mr-1 h-3 w-3" />}
                          {item.urgency}
                        </Badge>
                        <Badge className={triageStatusConfig[item.status]} data-testid={`triage-status-${item.id}`}>
                          {item.status}
                        </Badge>
                      </div>
                    </div>
                    <div className="flex items-start gap-2 mt-2">
                      <Zap className="h-4 w-4 text-primary mt-0.5 shrink-0" />
                      <p className="text-xs text-muted-foreground" data-testid={`triage-assessment-${item.id}`}>
                        <span className="font-medium text-foreground">AI Assessment:</span> {item.aiAssessment}
                      </p>
                    </div>
                    <div className="flex items-center gap-2 mt-3">
                      <Button size="sm" variant="outline" data-testid={`button-view-photos-${item.id}`}>
                        <Image className="h-3.5 w-3.5 mr-1" />
                        View Photos
                      </Button>
                      <Button size="sm" variant="outline" data-testid={`button-respond-${item.id}`}>
                        <FileText className="h-3.5 w-3.5 mr-1" />
                        Respond
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="billing">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <DollarSign className="h-4 w-4" />
                Teledentistry Billing Codes & Reimbursement
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>CDT Code</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Avg Reimbursement</TableHead>
                    <TableHead>Payer Coverage</TableHead>
                    <TableHead>Notes</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {billingCodes.map((bc, i) => (
                    <TableRow key={i} data-testid={`billing-code-${bc.code}`}>
                      <TableCell>
                        <span className="font-mono text-sm font-bold text-primary">{bc.code}</span>
                      </TableCell>
                      <TableCell className="text-sm" data-testid={`billing-desc-${bc.code}`}>{bc.description}</TableCell>
                      <TableCell>
                        <Badge variant="outline" className="text-xs">{bc.type}</Badge>
                      </TableCell>
                      <TableCell>
                        <span className="font-mono font-bold" data-testid={`billing-reimb-${bc.code}`}>{bc.avgReimbursement}</span>
                      </TableCell>
                      <TableCell>
                        <span className="text-sm" data-testid={`billing-coverage-${bc.code}`}>{bc.payerCoverage}</span>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">{bc.notes}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
                <Card>
                  <CardContent className="pt-6 text-center">
                    <div className="text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400" data-testid="billing-total-mtd">$4,800</div>
                    <p className="text-xs text-muted-foreground mt-1">Total Billed MTD</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-6 text-center">
                    <div className="text-2xl font-bold font-mono" data-testid="billing-collection-rate">92%</div>
                    <p className="text-xs text-muted-foreground mt-1">Collection Rate</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-6 text-center">
                    <div className="text-2xl font-bold font-mono" data-testid="billing-avg-per-visit">$68</div>
                    <p className="text-xs text-muted-foreground mt-1">Avg Per Visit</p>
                  </CardContent>
                </Card>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
