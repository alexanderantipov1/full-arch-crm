import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { useToast } from "@/hooks/use-toast";
import { apiRequest, queryClient } from "@/lib/queryClient";
import { 
  UserCheck, Clock, Calendar, Search, CheckCircle, AlertCircle, Users, 
  Phone, FileText, CreditCard, ClipboardCheck 
} from "lucide-react";
import type { Appointment, Patient, PatientCheckIn } from "@shared/schema";

const formatTime = (date: string | Date | null) => {
  if (!date) return "N/A";
  return new Date(date).toLocaleTimeString("en-US", { 
    hour: "numeric",
    minute: "2-digit",
    hour12: true
  });
};

const formatDate = (date: string | Date | null) => {
  if (!date) return "N/A";
  return new Date(date).toLocaleDateString("en-US", { 
    weekday: "short",
    month: "short",
    day: "numeric"
  });
};

export default function PatientCheckInPage() {
  const { toast } = useToast();
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedPatient, setSelectedPatient] = useState<Patient | null>(null);
  const [isVerifyDialogOpen, setIsVerifyDialogOpen] = useState(false);

  const { data: appointments = [], isLoading: loadingAppointments } = useQuery<Appointment[]>({
    queryKey: ["/api/appointments"],
  });

  const { data: patients = [] } = useQuery<Patient[]>({
    queryKey: ["/api/patients"],
  });

  const { data: checkIns = [], isLoading: loadingCheckIns } = useQuery<PatientCheckIn[]>({
    queryKey: ["/api/checkins"],
  });

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  
  const todaysAppointments = appointments.filter(apt => {
    const aptDate = new Date(apt.startTime);
    aptDate.setHours(0, 0, 0, 0);
    return aptDate.getTime() === today.getTime();
  }).sort((a, b) => new Date(a.startTime).getTime() - new Date(b.startTime).getTime());

  const getPatient = (patientId: number | null) => {
    if (!patientId) return null;
    return patients.find(p => p.id === patientId);
  };

  const getPatientName = (patientId: number | null) => {
    const patient = getPatient(patientId);
    return patient ? `${patient.firstName} ${patient.lastName}` : "Unknown";
  };

  const getCheckInStatus = (appointmentId: number) => {
    return checkIns.find(c => c.appointmentId === appointmentId);
  };

  const isCheckedIn = (appointmentId: number) => {
    return !!checkIns.find(c => c.appointmentId === appointmentId);
  };

  const checkInMutation = useMutation({
    mutationFn: async (data: { appointmentId: number; patientId: number }) => {
      const res = await apiRequest("POST", "/api/checkins", {
        appointmentId: data.appointmentId,
        patientId: data.patientId,
        checkInTime: new Date().toISOString(),
        checkInMethod: "manual",
        greeted: true,
        offeredRefreshment: false,
      });
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/checkins"] });
      setIsVerifyDialogOpen(false);
      setSelectedPatient(null);
      toast({ title: "Check-in Complete", description: "Patient has been checked in successfully" });
    },
    onError: (error: Error) => {
      toast({ title: "Error", description: error.message, variant: "destructive" });
    },
  });

  const filteredAppointments = searchQuery 
    ? todaysAppointments.filter(apt => {
        const patient = getPatient(apt.patientId);
        const searchLower = searchQuery.toLowerCase();
        return patient && (
          patient.firstName.toLowerCase().includes(searchLower) ||
          patient.lastName.toLowerCase().includes(searchLower) ||
          patient.phone?.includes(searchQuery)
        );
      })
    : todaysAppointments;

  const checkedInCount = todaysAppointments.filter(apt => isCheckedIn(apt.id)).length;
  const waitingCount = todaysAppointments.filter(apt => !isCheckedIn(apt.id)).length;

  const handleCheckIn = (appointment: Appointment) => {
    const patient = getPatient(appointment.patientId);
    if (patient) {
      setSelectedPatient(patient);
      checkInMutation.mutate({ appointmentId: appointment.id, patientId: appointment.patientId });
    }
  };

  return (
    <div className="flex-1 overflow-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold" data-testid="text-page-title">Patient Check-In</h1>
          <p className="text-muted-foreground">Front desk arrival tracking and patient greeting</p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-lg py-2 px-4">
            <Calendar className="w-4 h-4 mr-2" />
            {formatDate(new Date())}
          </Badge>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Today's Appointments</CardTitle>
            <Calendar className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold" data-testid="stat-total">{todaysAppointments.length}</div>
            <p className="text-xs text-muted-foreground">Scheduled for today</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Checked In</CardTitle>
            <CheckCircle className="h-4 w-4 text-green-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600" data-testid="stat-checkedin">{checkedInCount}</div>
            <p className="text-xs text-muted-foreground">Arrived and verified</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Waiting</CardTitle>
            <Clock className="h-4 w-4 text-amber-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-amber-600" data-testid="stat-waiting">{waitingCount}</div>
            <p className="text-xs text-muted-foreground">Not yet arrived</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Average Wait</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold" data-testid="stat-avgwait">12 min</div>
            <p className="text-xs text-muted-foreground">Check-in to room</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Today's Schedule</CardTitle>
              <CardDescription>Click to check in arriving patients</CardDescription>
            </div>
            <div className="relative w-72">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search by name or phone..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
                data-testid="input-search"
              />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {loadingAppointments ? (
            <p className="text-muted-foreground text-center py-4">Loading...</p>
          ) : filteredAppointments.length === 0 ? (
            <div className="text-center py-12">
              <Calendar className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium mb-2">No Appointments</h3>
              <p className="text-muted-foreground">No appointments scheduled for today</p>
            </div>
          ) : (
            <div className="space-y-2">
              {filteredAppointments.map((apt) => {
                const patient = getPatient(apt.patientId);
                const checkIn = getCheckInStatus(apt.id);
                const checkedInStatus = !!checkIn;
                
                return (
                  <div 
                    key={apt.id} 
                    className={`flex items-center justify-between p-4 border rounded-lg transition-colors ${
                      checkedInStatus ? "bg-green-50 dark:bg-green-900/20 border-green-200" : "hover-elevate"
                    }`}
                    data-testid={`appointment-row-${apt.id}`}
                  >
                    <div className="flex items-center gap-4">
                      <div className="text-center min-w-[80px]">
                        <p className="text-lg font-bold">{formatTime(apt.startTime)}</p>
                        <p className="text-xs text-muted-foreground">{apt.appointmentType}</p>
                      </div>
                      <div className="h-12 w-px bg-border" />
                      <div>
                        <p className="font-semibold text-lg">{getPatientName(apt.patientId)}</p>
                        <div className="flex items-center gap-3 text-sm text-muted-foreground">
                          {patient?.phone && (
                            <span className="flex items-center gap-1">
                              <Phone className="w-3 h-3" /> {patient.phone}
                            </span>
                          )}
                          <span>{apt.title || apt.description}</span>
                        </div>
                      </div>
                    </div>
                    
                    <div className="flex items-center gap-3">
                      {checkedInStatus ? (
                        <>
                          <div className="flex gap-2">
                            {checkIn?.greeted && (
                              <Badge variant="outline" className="text-green-600">
                                <CheckCircle className="w-3 h-3 mr-1" /> Greeted
                              </Badge>
                            )}
                            {checkIn?.offeredRefreshment && (
                              <Badge variant="outline" className="text-green-600">
                                <CheckCircle className="w-3 h-3 mr-1" /> Refreshment
                              </Badge>
                            )}
                            {checkIn?.assignedRoom && (
                              <Badge variant="outline" className="text-green-600">
                                <ClipboardCheck className="w-3 h-3 mr-1" /> Room {checkIn.assignedRoom}
                              </Badge>
                            )}
                          </div>
                          <Badge className="bg-green-100 text-green-800">
                            <CheckCircle className="w-3 h-3 mr-1" /> Checked In
                          </Badge>
                        </>
                      ) : (
                        <Button 
                          onClick={() => handleCheckIn(apt)}
                          disabled={checkInMutation.isPending}
                          data-testid={`button-checkin-${apt.id}`}
                        >
                          <UserCheck className="w-4 h-4 mr-2" />
                          Check In
                        </Button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ClipboardCheck className="w-5 h-5" />
              Check-In Checklist
            </CardTitle>
            <CardDescription>Standard verification process</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="flex items-center gap-3 p-3 border rounded-lg">
                <FileText className="w-5 h-5 text-blue-600" />
                <div>
                  <p className="font-medium">Verify Photo ID</p>
                  <p className="text-sm text-muted-foreground">Check government-issued ID matches patient</p>
                </div>
              </div>
              <div className="flex items-center gap-3 p-3 border rounded-lg">
                <CreditCard className="w-5 h-5 text-blue-600" />
                <div>
                  <p className="font-medium">Verify Insurance Card</p>
                  <p className="text-sm text-muted-foreground">Confirm coverage is current and active</p>
                </div>
              </div>
              <div className="flex items-center gap-3 p-3 border rounded-lg">
                <ClipboardCheck className="w-5 h-5 text-blue-600" />
                <div>
                  <p className="font-medium">Review Intake Forms</p>
                  <p className="text-sm text-muted-foreground">Medical history, consent, HIPAA acknowledgment</p>
                </div>
              </div>
              <div className="flex items-center gap-3 p-3 border rounded-lg">
                <CreditCard className="w-5 h-5 text-blue-600" />
                <div>
                  <p className="font-medium">Collect Payment</p>
                  <p className="text-sm text-muted-foreground">Copay, deposit, or treatment prepayment</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertCircle className="w-5 h-5" />
              Alerts & Reminders
            </CardTitle>
            <CardDescription>Special patient notes</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="p-3 border rounded-lg border-amber-200 bg-amber-50 dark:bg-amber-900/20">
                <p className="font-medium text-amber-800 dark:text-amber-200">Pre-Surgery Patient</p>
                <p className="text-sm text-muted-foreground">Verify NPO status (nothing by mouth since midnight)</p>
              </div>
              <div className="p-3 border rounded-lg border-blue-200 bg-blue-50 dark:bg-blue-900/20">
                <p className="font-medium text-blue-800 dark:text-blue-200">Financing Required</p>
                <p className="text-sm text-muted-foreground">Confirm financing approved before treatment</p>
              </div>
              <div className="p-3 border rounded-lg border-purple-200 bg-purple-50 dark:bg-purple-900/20">
                <p className="font-medium text-purple-800 dark:text-purple-200">Medical Clearance</p>
                <p className="text-sm text-muted-foreground">Check for signed clearance from physician</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
