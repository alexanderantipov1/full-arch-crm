import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "wouter";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import {
  ArrowLeft,
  User,
  Phone,
  Mail,
  MapPin,
  Calendar,
  FileText,
  DollarSign,
  Stethoscope,
  ClipboardList,
  Image,
  Plus,
  Edit,
  Shield,
  AlertTriangle,
  Activity,
  Ruler,
  UserCheck,
  FileCheck,
  RefreshCw,
  Wind,
  MessageSquare,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import { format } from "date-fns";
import type { Patient, MedicalHistory, DentalInfo, Insurance, TreatmentPlan, Appointment, FacialEvaluation, Cephalometric, MedicalConsult, FullArchExam } from "@shared/schema";

interface EligibilityCheck {
  id: number; patientId: number; checkDate: string; eligibilityStatus: string | null;
  benefitsRemaining: string | null; coverageDetails: Record<string, unknown> | null;
}

interface PatientDetailData extends Patient {
  medicalHistory?: MedicalHistory;
  dentalInfo?: DentalInfo;
  facialEvaluation?: FacialEvaluation;
  insurance?: Insurance[];
  treatmentPlans?: TreatmentPlan[];
  appointments?: Appointment[];
  cephalometrics?: Cephalometric[];
  medicalConsults?: MedicalConsult[];
  fullArchExams?: FullArchExam[];
}

export default function PatientDetailPage() {
  const params = useParams();
  const patientId = params.id;

  const { data: patient, isLoading } = useQuery<PatientDetailData>({
    queryKey: ["/api/patients", patientId],
  });

  const { data: eligibilityHistory } = useQuery<EligibilityCheck[]>({
    queryKey: ["/api/eligibility/patient", patientId],
    queryFn: () => fetch(`/api/eligibility/patient/${patientId}`, { credentials: "include" }).then(r => r.json()),
    enabled: !!patientId,
  });

  const latestEligibility = eligibilityHistory?.[0];

  const formatCurrency = (amount: number | string | null | undefined) => {
    if (!amount) return "$0";
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 0,
    }).format(Number(amount));
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-48" />
        <Skeleton className="h-[200px] w-full" />
        <Skeleton className="h-[400px] w-full" />
      </div>
    );
  }

  if (!patient) {
    return (
      <div className="flex flex-col items-center justify-center py-16">
        <h2 className="text-xl font-semibold">Patient not found</h2>
        <Button asChild className="mt-4">
          <Link href="/patients">Back to Patients</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/patients">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold tracking-tight">
            {patient.firstName} {patient.lastName}
          </h1>
          <p className="text-muted-foreground">Patient ID: {patient.id}</p>
        </div>
        <Button variant="outline" asChild>
          <Link href={`/patients/${patient.id}/edit`}>
            <Edit className="mr-2 h-4 w-4" />
            Edit
          </Link>
        </Button>
        <Button variant="outline" asChild>
          <Link href={`/dental-charting/${patient.id}`}>
            <Activity className="mr-2 h-4 w-4" />
            Dental Chart
          </Link>
        </Button>
        {/* Eligibility badge — Active / Inactive / Unknown */}
        <Link href={`/eligibility?patientId=${patient.id}`}>
          <Badge
            className={`cursor-pointer gap-1 px-2.5 py-1 text-xs ${
              latestEligibility?.eligibilityStatus === "active"
                ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300 hover:bg-green-200 dark:hover:bg-green-900/50"
                : latestEligibility?.eligibilityStatus === "inactive" || latestEligibility?.eligibilityStatus === "terminated"
                ? "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300 hover:bg-red-200"
                : latestEligibility
                ? "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300 hover:bg-yellow-200"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            }`}
            data-testid={`badge-eligibility-${patient.id}`}
          >
            {latestEligibility?.eligibilityStatus === "active" ? (
              <CheckCircle2 className="h-3 w-3" />
            ) : latestEligibility?.eligibilityStatus === "inactive" || latestEligibility?.eligibilityStatus === "terminated" ? (
              <XCircle className="h-3 w-3" />
            ) : latestEligibility ? (
              <AlertTriangle className="h-3 w-3" />
            ) : (
              <Shield className="h-3 w-3" />
            )}
            {latestEligibility
              ? (() => {
                  const s = latestEligibility.eligibilityStatus;
                  const label = s === "active" ? "Active" : s === "inactive" || s === "terminated" ? "Inactive" : "Unknown";
                  const date = new Date(latestEligibility.checkDate).toLocaleDateString("en-US", { month: "short", day: "numeric" });
                  return `${label} · ${date}`;
                })()
              : "Check Eligibility"}
          </Badge>
        </Link>
        <Button variant="outline" asChild data-testid={`button-message-patient-${patient.id}`}>
          <Link href={`/patient-messaging?patientId=${patient.id}&patientName=${encodeURIComponent(`${patient.firstName} ${patient.lastName}`)}&compose=true`}>
            <MessageSquare className="mr-2 h-4 w-4" />
            Message
          </Link>
        </Button>
        <Button asChild>
          <Link href={`/treatment-plans/new?patientId=${patient.id}`}>
            <Plus className="mr-2 h-4 w-4" />
            New Treatment Plan
          </Link>
        </Button>
      </div>

      <Card>
        <CardContent className="p-6">
          <div className="flex flex-col gap-6 md:flex-row md:items-start">
            <Avatar className="h-24 w-24 shrink-0">
              <AvatarFallback className="bg-primary/10 text-primary text-2xl">
                {patient.firstName[0]}{patient.lastName[0]}
              </AvatarFallback>
            </Avatar>

            <div className="flex-1 grid gap-6 md:grid-cols-3">
              <div className="space-y-3">
                <h3 className="text-sm font-medium text-muted-foreground">Personal Info</h3>
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-sm">
                    <Calendar className="h-4 w-4 text-muted-foreground" />
                    <span>DOB: {format(new Date(patient.dateOfBirth), "MMM d, yyyy")}</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    <User className="h-4 w-4 text-muted-foreground" />
                    <span className="capitalize">{patient.gender}</span>
                  </div>
                </div>
              </div>

              <div className="space-y-3">
                <h3 className="text-sm font-medium text-muted-foreground">Contact</h3>
                <div className="space-y-2">
                  {patient.email && (
                    <div className="flex items-center gap-2 text-sm">
                      <Mail className="h-4 w-4 text-muted-foreground" />
                      <span>{patient.email}</span>
                    </div>
                  )}
                  {patient.phone && (
                    <div className="flex items-center gap-2 text-sm">
                      <Phone className="h-4 w-4 text-muted-foreground" />
                      <span>{patient.phone}</span>
                    </div>
                  )}
                </div>
              </div>

              <div className="space-y-3">
                <h3 className="text-sm font-medium text-muted-foreground">Address</h3>
                <div className="flex items-start gap-2 text-sm">
                  <MapPin className="h-4 w-4 shrink-0 text-muted-foreground" />
                  <span>
                    {patient.address && `${patient.address}, `}
                    {patient.city && `${patient.city}, `}
                    {patient.state} {patient.zipCode}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList className="flex-wrap">
          <TabsTrigger value="overview" data-testid="tab-overview">Overview</TabsTrigger>
          <TabsTrigger value="medical" data-testid="tab-medical">Medical History</TabsTrigger>
          <TabsTrigger value="dental" data-testid="tab-dental">Dental Info</TabsTrigger>
          <TabsTrigger value="clinical" data-testid="tab-clinical">Clinical Exams</TabsTrigger>
          <TabsTrigger value="insurance" data-testid="tab-insurance">Insurance</TabsTrigger>
          <TabsTrigger value="treatment" data-testid="tab-treatment">Treatment Plans</TabsTrigger>
          <TabsTrigger value="billing" data-testid="tab-billing">Billing</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                    <ClipboardList className="h-5 w-5 text-primary" />
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Treatment Plans</p>
                    <p className="text-xl font-bold">{patient.treatmentPlans?.length || 0}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-100 dark:bg-green-900/30">
                    <Calendar className="h-5 w-5 text-green-600" />
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Appointments</p>
                    <p className="text-xl font-bold">{patient.appointments?.length || 0}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-chart-3/10">
                    <DollarSign className="h-5 w-5 text-chart-3" />
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Total Billed</p>
                    <p className="text-xl font-bold">
                      {formatCurrency(
                        patient.treatmentPlans?.reduce((sum, p) => sum + (Number(p.totalCost) || 0), 0)
                      )}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100 dark:bg-blue-900/30">
                    <Shield className="h-5 w-5 text-blue-600" />
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Insurance</p>
                    <p className="text-xl font-bold">{patient.insurance?.length || 0}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Recent Treatment Plans</CardTitle>
              </CardHeader>
              <CardContent>
                {patient.treatmentPlans && patient.treatmentPlans.length > 0 ? (
                  <div className="space-y-3">
                    {patient.treatmentPlans.slice(0, 3).map((plan) => (
                      <div
                        key={plan.id}
                        className="flex items-center justify-between rounded-lg border p-3 hover-elevate"
                      >
                        <div>
                          <p className="font-medium">{plan.planName}</p>
                          <p className="text-sm text-muted-foreground">{plan.diagnosis}</p>
                        </div>
                        <div className="text-right">
                          <p className="font-medium">{formatCurrency(plan.totalCost)}</p>
                          <Badge variant="secondary">{plan.status}</Badge>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-6 text-sm text-muted-foreground">
                    No treatment plans yet
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Upcoming Appointments</CardTitle>
              </CardHeader>
              <CardContent>
                {patient.appointments && patient.appointments.length > 0 ? (
                  <div className="space-y-3">
                    {patient.appointments.slice(0, 3).map((apt) => (
                      <div
                        key={apt.id}
                        className="flex items-center justify-between rounded-lg border p-3 hover-elevate"
                      >
                        <div>
                          <p className="font-medium">{apt.title}</p>
                          <p className="text-sm text-muted-foreground">
                            {format(new Date(apt.startTime), "MMM d, yyyy h:mm a")}
                          </p>
                        </div>
                        <Badge>{apt.appointmentType}</Badge>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-6 text-sm text-muted-foreground">
                    No upcoming appointments
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="medical" className="space-y-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Medical History</CardTitle>
                <CardDescription>Patient medical conditions and history</CardDescription>
              </div>
              <Button variant="outline" size="sm">
                <Edit className="mr-2 h-4 w-4" />
                Update
              </Button>
            </CardHeader>
            <CardContent>
              {patient.medicalHistory ? (
                <div className="grid gap-6 md:grid-cols-2">
                  <div className="space-y-4">
                    <div>
                      <h4 className="text-sm font-medium text-muted-foreground mb-2">Medical Conditions</h4>
                      <div className="flex flex-wrap gap-2">
                        {patient.medicalHistory.conditions?.map((condition, i) => (
                          <Badge key={i} variant="secondary">{condition}</Badge>
                        )) || <span className="text-sm text-muted-foreground">None reported</span>}
                      </div>
                    </div>
                    <div>
                      <h4 className="text-sm font-medium text-muted-foreground mb-2">Allergies</h4>
                      <div className="flex flex-wrap gap-2">
                        {patient.medicalHistory.allergies?.map((allergy, i) => (
                          <Badge key={i} variant="destructive">{allergy}</Badge>
                        )) || <span className="text-sm text-muted-foreground">None reported</span>}
                      </div>
                    </div>
                    <div>
                      <h4 className="text-sm font-medium text-muted-foreground mb-2">Current Medications</h4>
                      <div className="flex flex-wrap gap-2">
                        {patient.medicalHistory.medications?.map((med, i) => (
                          <Badge key={i} variant="outline">{med}</Badge>
                        )) || <span className="text-sm text-muted-foreground">None reported</span>}
                      </div>
                    </div>
                  </div>
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <h4 className="text-sm font-medium text-muted-foreground">Blood Pressure</h4>
                        <p className="font-medium">{patient.medicalHistory.bloodPressure || "N/A"}</p>
                      </div>
                      <div>
                        <h4 className="text-sm font-medium text-muted-foreground">Heart Rate</h4>
                        <p className="font-medium">{patient.medicalHistory.heartRate || "N/A"}</p>
                      </div>
                      <div>
                        <h4 className="text-sm font-medium text-muted-foreground">Weight</h4>
                        <p className="font-medium">{patient.medicalHistory.weight || "N/A"}</p>
                      </div>
                      <div>
                        <h4 className="text-sm font-medium text-muted-foreground">Height</h4>
                        <p className="font-medium">{patient.medicalHistory.height || "N/A"}</p>
                      </div>
                    </div>
                    <div>
                      <h4 className="text-sm font-medium text-muted-foreground mb-2">Smoking Status</h4>
                      <p className="text-sm">{patient.medicalHistory.smokingStatus || "Not reported"}</p>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-center py-8">
                  <Activity className="mx-auto h-10 w-10 text-muted-foreground/50 mb-3" />
                  <p className="text-sm text-muted-foreground mb-4">No medical history on file</p>
                  <Button>Add Medical History</Button>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="dental" className="space-y-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Dental Information</CardTitle>
                <CardDescription>Dental history and current conditions</CardDescription>
              </div>
              <Button variant="outline" size="sm">
                <Edit className="mr-2 h-4 w-4" />
                Update
              </Button>
            </CardHeader>
            <CardContent>
              {patient.dentalInfo ? (
                <div className="grid gap-6 md:grid-cols-2">
                  <div className="space-y-4">
                    <div>
                      <h4 className="text-sm font-medium text-muted-foreground mb-2">Chief Complaint</h4>
                      <p className="text-sm">{patient.dentalInfo.chiefComplaint || "None specified"}</p>
                    </div>
                    <div>
                      <h4 className="text-sm font-medium text-muted-foreground mb-2">Missing Teeth</h4>
                      <div className="flex flex-wrap gap-2">
                        {patient.dentalInfo.missingTeeth?.map((tooth, i) => (
                          <Badge key={i} variant="outline">{tooth}</Badge>
                        )) || <span className="text-sm text-muted-foreground">None</span>}
                      </div>
                    </div>
                    <div>
                      <h4 className="text-sm font-medium text-muted-foreground mb-2">Existing Implants</h4>
                      <div className="flex flex-wrap gap-2">
                        {patient.dentalInfo.implants?.map((impl, i) => (
                          <Badge key={i} variant="secondary">{impl}</Badge>
                        )) || <span className="text-sm text-muted-foreground">None</span>}
                      </div>
                    </div>
                  </div>
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <h4 className="text-sm font-medium text-muted-foreground">TMJ Issues</h4>
                        <p className="font-medium">{patient.dentalInfo.tmjIssues ? "Yes" : "No"}</p>
                      </div>
                      <div>
                        <h4 className="text-sm font-medium text-muted-foreground">Grinding/Clenching</h4>
                        <p className="font-medium">{patient.dentalInfo.grindingClenching ? "Yes" : "No"}</p>
                      </div>
                    </div>
                    <div>
                      <h4 className="text-sm font-medium text-muted-foreground mb-2">Orthodontic History</h4>
                      <p className="text-sm">{patient.dentalInfo.orthodonticHistory || "None reported"}</p>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-center py-8">
                  <Stethoscope className="mx-auto h-10 w-10 text-muted-foreground/50 mb-3" />
                  <p className="text-sm text-muted-foreground mb-4">No dental information on file</p>
                  <Button>Add Dental Info</Button>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="clinical" className="space-y-4">
          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between gap-2">
                <div>
                  <CardTitle className="text-lg flex items-center gap-2">
                    <User className="h-5 w-5" />
                    Arnett-Gunson Facial Evaluation
                  </CardTitle>
                  <CardDescription>Comprehensive facial profile analysis</CardDescription>
                </div>
                <Button variant="outline" size="sm">
                  <Plus className="mr-2 h-4 w-4" />
                  Add Exam
                </Button>
              </CardHeader>
              <CardContent>
                {patient.facialEvaluation ? (
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <p className="text-muted-foreground">Profile Type</p>
                        <p className="font-medium capitalize">{patient.facialEvaluation.facialProfile || "N/A"}</p>
                      </div>
                      <div>
                        <p className="text-muted-foreground">Lip Position</p>
                        <p className="font-medium">{patient.facialEvaluation.lipPosition || "N/A"}</p>
                      </div>
                      <div>
                        <p className="text-muted-foreground">Bite Classification</p>
                        <p className="font-medium">{patient.facialEvaluation.biteClassification || "N/A"}</p>
                      </div>
                      <div>
                        <p className="text-muted-foreground">Mallampati Score</p>
                        <Badge variant={patient.facialEvaluation.mallampatiScore && parseInt(patient.facialEvaluation.mallampatiScore) >= 3 ? "destructive" : "secondary"}>
                          Class {patient.facialEvaluation.mallampatiScore || "N/A"}
                        </Badge>
                      </div>
                    </div>
                    {patient.facialEvaluation.airwayAssessment && (
                      <div>
                        <p className="text-muted-foreground text-sm mb-1">Airway Assessment</p>
                        <p className="text-sm">{patient.facialEvaluation.airwayAssessment}</p>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-center py-6">
                    <User className="mx-auto h-8 w-8 text-muted-foreground/50 mb-2" />
                    <p className="text-sm text-muted-foreground">No facial evaluation on file</p>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between gap-2">
                <div>
                  <CardTitle className="text-lg flex items-center gap-2">
                    <Ruler className="h-5 w-5" />
                    Cephalometric Analysis
                  </CardTitle>
                  <CardDescription>Skeletal measurements and analysis</CardDescription>
                </div>
                <Button variant="outline" size="sm">
                  <Plus className="mr-2 h-4 w-4" />
                  Add Analysis
                </Button>
              </CardHeader>
              <CardContent>
                {patient.cephalometrics && patient.cephalometrics.length > 0 ? (
                  <div className="space-y-3">
                    {patient.cephalometrics.slice(0, 2).map((ceph) => (
                      <div key={ceph.id} className="rounded-lg border p-3">
                        <div className="flex items-center justify-between mb-2">
                          <p className="text-sm font-medium">
                            {format(new Date(ceph.analysisDate || new Date()), "MMM d, yyyy")}
                          </p>
                          <Badge variant="outline">{ceph.skeletalClassification || "Unclassified"}</Badge>
                        </div>
                        <div className="grid grid-cols-4 gap-2 text-xs">
                          <div>
                            <p className="text-muted-foreground">SNA</p>
                            <p className="font-medium">{ceph.sna || "-"}</p>
                          </div>
                          <div>
                            <p className="text-muted-foreground">SNB</p>
                            <p className="font-medium">{ceph.snb || "-"}</p>
                          </div>
                          <div>
                            <p className="text-muted-foreground">ANB</p>
                            <p className="font-medium">{ceph.anb || "-"}</p>
                          </div>
                          <div>
                            <p className="text-muted-foreground">FMA</p>
                            <p className="font-medium">{ceph.fma || "-"}</p>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-6">
                    <Ruler className="mx-auto h-8 w-8 text-muted-foreground/50 mb-2" />
                    <p className="text-sm text-muted-foreground">No cephalometric data on file</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between gap-2">
                <div>
                  <CardTitle className="text-lg flex items-center gap-2">
                    <Wind className="h-5 w-5" />
                    Full Arch Evaluations
                  </CardTitle>
                  <CardDescription>Comprehensive implant evaluations</CardDescription>
                </div>
                <Button variant="outline" size="sm">
                  <Plus className="mr-2 h-4 w-4" />
                  New Exam
                </Button>
              </CardHeader>
              <CardContent>
                {patient.fullArchExams && patient.fullArchExams.length > 0 ? (
                  <div className="space-y-3">
                    {patient.fullArchExams.slice(0, 2).map((exam) => (
                      <div key={exam.id} className="rounded-lg border p-3 hover-elevate">
                        <div className="flex items-center justify-between mb-2">
                          <p className="font-medium">Full Arch Evaluation</p>
                          <Badge>{exam.edentulousArch || "Full Arch"}</Badge>
                        </div>
                        <p className="text-sm text-muted-foreground">
                          {format(new Date(exam.examDate), "MMM d, yyyy")}
                        </p>
                        {exam.boneQuality && (
                          <p className="text-xs text-muted-foreground mt-1">
                            Bone Quality: {exam.boneQuality}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-6">
                    <Wind className="mx-auto h-8 w-8 text-muted-foreground/50 mb-2" />
                    <p className="text-sm text-muted-foreground">No full arch exams on file</p>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between gap-2">
                <div>
                  <CardTitle className="text-lg flex items-center gap-2">
                    <UserCheck className="h-5 w-5" />
                    Medical Consultations
                  </CardTitle>
                  <CardDescription>Preoperative clearances and specialist consults</CardDescription>
                </div>
                <Button variant="outline" size="sm">
                  <Plus className="mr-2 h-4 w-4" />
                  Request Consult
                </Button>
              </CardHeader>
              <CardContent>
                {patient.medicalConsults && patient.medicalConsults.length > 0 ? (
                  <div className="space-y-3">
                    {patient.medicalConsults.slice(0, 3).map((consult) => (
                      <div key={consult.id} className="rounded-lg border p-3">
                        <div className="flex items-center justify-between mb-1">
                          <p className="font-medium text-sm">{consult.consultType}</p>
                          <Badge variant={
                            consult.status === "completed" ? "default" :
                            consult.status === "pending" ? "secondary" : "outline"
                          }>
                            {consult.status}
                          </Badge>
                        </div>
                        <p className="text-xs text-muted-foreground">{consult.consultingPhysician || "Pending assignment"}</p>
                        {consult.requestDate && (
                          <p className="text-xs text-muted-foreground mt-1">
                            Requested: {format(new Date(consult.requestDate), "MMM d, yyyy")}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-6">
                    <UserCheck className="mx-auto h-8 w-8 text-muted-foreground/50 mb-2" />
                    <p className="text-sm text-muted-foreground">No medical consultations on file</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="insurance" className="space-y-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Insurance Coverage</CardTitle>
                <CardDescription>Medical and dental insurance policies</CardDescription>
              </div>
              <Button size="sm">
                <Plus className="mr-2 h-4 w-4" />
                Add Insurance
              </Button>
            </CardHeader>
            <CardContent>
              {patient.insurance && patient.insurance.length > 0 ? (
                <div className="space-y-4">
                  {patient.insurance.map((ins) => (
                    <div key={ins.id} className="rounded-lg border p-4">
                      <div className="flex items-start justify-between mb-3">
                        <div>
                          <div className="flex items-center gap-2">
                            <h4 className="font-medium">{ins.providerName}</h4>
                            <Badge>{ins.insuranceType}</Badge>
                          </div>
                          <p className="text-sm text-muted-foreground">Policy: {ins.policyNumber}</p>
                        </div>
                        <Button variant="ghost" size="sm">
                          <Edit className="h-4 w-4" />
                        </Button>
                      </div>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                        <div>
                          <p className="text-muted-foreground">Annual Max</p>
                          <p className="font-medium">{formatCurrency(ins.annualMaximum)}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">Deductible</p>
                          <p className="font-medium">{formatCurrency(ins.deductible)}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">Remaining</p>
                          <p className="font-medium text-green-600">{formatCurrency(ins.remainingBenefit)}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">Coverage</p>
                          <p className="font-medium">{ins.coveragePercentage}%</p>
                        </div>
                      </div>
                      {ins.priorAuthRequired && (
                        <div className="mt-3 flex items-center gap-2 text-sm text-yellow-600">
                          <AlertTriangle className="h-4 w-4" />
                          Prior authorization required
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8">
                  <Shield className="mx-auto h-10 w-10 text-muted-foreground/50 mb-3" />
                  <p className="text-sm text-muted-foreground mb-4">No insurance on file</p>
                  <Button>Add Insurance</Button>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="treatment" className="space-y-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Treatment Plans</CardTitle>
                <CardDescription>All treatment plans for this patient</CardDescription>
              </div>
              <Button asChild>
                <Link href={`/treatment-plans/new?patientId=${patient.id}`}>
                  <Plus className="mr-2 h-4 w-4" />
                  New Plan
                </Link>
              </Button>
            </CardHeader>
            <CardContent>
              {patient.treatmentPlans && patient.treatmentPlans.length > 0 ? (
                <div className="space-y-4">
                  {patient.treatmentPlans.map((plan) => (
                    <div key={plan.id} className="rounded-lg border p-4 hover-elevate">
                      <div className="flex items-start justify-between mb-3">
                        <div>
                          <Link
                            href={`/treatment-plans/${plan.id}`}
                            className="font-medium hover:underline"
                          >
                            {plan.planName}
                          </Link>
                          <p className="text-sm text-muted-foreground">{plan.diagnosis}</p>
                        </div>
                        <Badge>{plan.status}</Badge>
                      </div>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                        <div>
                          <p className="text-muted-foreground">Total Cost</p>
                          <p className="font-medium">{formatCurrency(plan.totalCost)}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">Insurance</p>
                          <p className="font-medium text-green-600">{formatCurrency(plan.insuranceCoverage)}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">Patient OOP</p>
                          <p className="font-medium">{formatCurrency(plan.patientResponsibility)}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">Auth Status</p>
                          <p className="font-medium capitalize">{plan.priorAuthStatus || "N/A"}</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8">
                  <ClipboardList className="mx-auto h-10 w-10 text-muted-foreground/50 mb-3" />
                  <p className="text-sm text-muted-foreground mb-4">No treatment plans created yet</p>
                  <Button asChild>
                    <Link href={`/treatment-plans/new?patientId=${patient.id}`}>
                      Create Treatment Plan
                    </Link>
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="billing" className="space-y-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Billing & Claims</CardTitle>
                <CardDescription>Insurance claims and billing history</CardDescription>
              </div>
              <Button asChild>
                <Link href={`/billing?patientId=${patient.id}`}>
                  View All Claims
                </Link>
              </Button>
            </CardHeader>
            <CardContent>
              <div className="text-center py-8">
                <DollarSign className="mx-auto h-10 w-10 text-muted-foreground/50 mb-3" />
                <p className="text-sm text-muted-foreground mb-4">
                  View and manage billing claims for this patient
                </p>
                <Button variant="outline" asChild>
                  <Link href={`/billing?patientId=${patient.id}`}>Go to Billing</Link>
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
