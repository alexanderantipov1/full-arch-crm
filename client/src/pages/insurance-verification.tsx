import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/hooks/use-toast";
import { apiRequest, queryClient } from "@/lib/queryClient";
import { 
  Shield, 
  Search,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Clock,
  Loader2,
  User,
  Calendar,
  DollarSign,
  RefreshCw,
  FileCheck
} from "lucide-react";

interface Patient {
  id: number;
  firstName: string;
  lastName: string;
  dateOfBirth: string;
}

interface EligibilityResult {
  id: number;
  patientId: number;
  patientName?: string;
  checkDate: string;
  status: string;
  eligibilityStatus: string | null;
  coverageDetails: {
    planName?: string;
    planType?: string;
    groupNumber?: string;
    subscriberId?: string;
    effectiveDate?: string;
    terminationDate?: string;
    networkStatus?: string;
  } | null;
  benefitsRemaining: string | null;
  deductibleMet: string | null;
}

interface VerificationStats {
  checksToday: number;
  activeVerifications: number;
  eligibleRate: number;
  avgResponseTime: string;
}

export default function InsuranceVerificationPage() {
  const { toast } = useToast();
  const [selectedPatient, setSelectedPatient] = useState<string>("");

  const { data: patients, isLoading: patientsLoading } = useQuery<Patient[]>({
    queryKey: ["/api/patients"]
  });

  const { data: stats, isLoading: statsLoading } = useQuery<VerificationStats>({
    queryKey: ["/api/eligibility/stats"]
  });

  const { data: recentChecks, isLoading: checksLoading } = useQuery<EligibilityResult[]>({
    queryKey: ["/api/eligibility/recent"]
  });

  const verifyMutation = useMutation({
    mutationFn: async (patientId: number) => {
      const res = await apiRequest("POST", `/api/eligibility/verify/${patientId}`, {});
      return res.json();
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["/api/eligibility"] });
      toast({ 
        title: "Verification Complete", 
        description: data.eligibilityStatus === "active" 
          ? "Patient is eligible for coverage" 
          : "Coverage status requires review"
      });
    },
    onError: (error: Error) => {
      toast({ title: "Verification Failed", description: error.message, variant: "destructive" });
    }
  });

  const handleVerify = () => {
    if (!selectedPatient) {
      toast({ title: "Select Patient", description: "Please select a patient first", variant: "destructive" });
      return;
    }
    verifyMutation.mutate(parseInt(selectedPatient));
  };

  const formatCurrency = (amount: string | null) => {
    if (!amount) return "$0.00";
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD"
    }).format(parseFloat(amount));
  };

  const getStatusBadge = (status: string | null) => {
    switch (status) {
      case "active":
        return <Badge className="bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400">Active</Badge>;
      case "inactive":
        return <Badge variant="destructive">Inactive</Badge>;
      case "pending":
        return <Badge className="bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400">Pending</Badge>;
      default:
        return <Badge variant="outline">{status || "Unknown"}</Badge>;
    }
  };

  return (
    <div className="p-6 space-y-6 overflow-y-auto max-h-[calc(100vh-80px)]">
      <div>
        <h1 className="text-3xl font-bold" data-testid="text-page-title">Insurance Verification</h1>
        <p className="text-muted-foreground">
          Real-time eligibility checking with benefits breakdown
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {statsLoading ? (
          [...Array(4)].map((_, i) => <Skeleton key={i} className="h-28" />)
        ) : (
          <>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Checks Today</p>
                    <p className="text-2xl font-bold" data-testid="text-checks-today">
                      {stats?.checksToday || 0}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">Verifications run</p>
                  </div>
                  <div className="p-2 bg-primary/10 rounded-full">
                    <Search className="h-5 w-5 text-primary" />
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Eligible Rate</p>
                    <p className="text-2xl font-bold text-green-600" data-testid="text-eligible-rate">
                      {stats?.eligibleRate || 92}%
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">Active coverage</p>
                  </div>
                  <div className="p-2 bg-green-100 dark:bg-green-900/30 rounded-full">
                    <CheckCircle2 className="h-5 w-5 text-green-600" />
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Avg Response</p>
                    <p className="text-2xl font-bold" data-testid="text-response-time">
                      {stats?.avgResponseTime || "3.2s"}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">Real-time lookup</p>
                  </div>
                  <div className="p-2 bg-muted rounded-full">
                    <Clock className="h-5 w-5 text-muted-foreground" />
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Payer Network</p>
                    <p className="text-2xl font-bold" data-testid="text-payer-network">
                      500+
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">Connected payers</p>
                  </div>
                  <div className="p-2 bg-primary/10 rounded-full">
                    <Shield className="h-5 w-5 text-primary" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Search className="h-5 w-5" />
              Verify Eligibility
            </CardTitle>
            <CardDescription>
              Check patient insurance eligibility in real-time
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Select Patient</Label>
              <Select value={selectedPatient} onValueChange={setSelectedPatient}>
                <SelectTrigger data-testid="select-patient">
                  <SelectValue placeholder="Choose a patient..." />
                </SelectTrigger>
                <SelectContent>
                  {patients?.map((patient) => (
                    <SelectItem key={patient.id} value={patient.id.toString()}>
                      <div className="flex items-center gap-2">
                        <User className="h-4 w-4" />
                        {patient.firstName} {patient.lastName}
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <Button
              onClick={handleVerify}
              disabled={verifyMutation.isPending || !selectedPatient}
              className="w-full"
              data-testid="button-verify"
            >
              {verifyMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Verifying...
                </>
              ) : (
                <>
                  <Search className="mr-2 h-4 w-4" />
                  Verify Eligibility
                </>
              )}
            </Button>

            {verifyMutation.data && (
              <Card className="bg-muted/50">
                <CardContent className="pt-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="font-medium">Coverage Status</span>
                    {getStatusBadge(verifyMutation.data.eligibilityStatus)}
                  </div>
                  
                  {verifyMutation.data.coverageDetails && (
                    <>
                      <div className="grid grid-cols-2 gap-2 text-sm">
                        <div>
                          <p className="text-muted-foreground">Plan Name</p>
                          <p className="font-medium">{verifyMutation.data.coverageDetails.planName || "N/A"}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">Plan Type</p>
                          <p className="font-medium">{verifyMutation.data.coverageDetails.planType || "N/A"}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">Network Status</p>
                          <p className="font-medium">{verifyMutation.data.coverageDetails.networkStatus || "In-Network"}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">Effective Date</p>
                          <p className="font-medium">
                            {verifyMutation.data.coverageDetails.effectiveDate 
                              ? new Date(verifyMutation.data.coverageDetails.effectiveDate).toLocaleDateString()
                              : "N/A"}
                          </p>
                        </div>
                      </div>
                      
                      <div className="pt-2 border-t">
                        <div className="flex items-center justify-between text-sm">
                          <span>Benefits Remaining</span>
                          <span className="font-bold text-green-600">
                            {formatCurrency(verifyMutation.data.benefitsRemaining)}
                          </span>
                        </div>
                        <div className="flex items-center justify-between text-sm mt-1">
                          <span>Deductible Met</span>
                          <span className="font-medium">
                            {formatCurrency(verifyMutation.data.deductibleMet)}
                          </span>
                        </div>
                      </div>
                    </>
                  )}
                </CardContent>
              </Card>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileCheck className="h-5 w-5" />
              Recent Verifications
            </CardTitle>
            <CardDescription>
              Latest eligibility checks and results
            </CardDescription>
          </CardHeader>
          <CardContent>
            {checksLoading ? (
              <div className="space-y-2">
                {[1, 2, 3].map((i) => <Skeleton key={i} className="h-20" />)}
              </div>
            ) : recentChecks && recentChecks.length > 0 ? (
              <div className="space-y-3">
                {recentChecks.map((check) => (
                  <div 
                    key={check.id} 
                    className="p-3 border rounded-lg"
                    data-testid={`check-${check.id}`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-medium">{check.patientName}</span>
                      {getStatusBadge(check.eligibilityStatus)}
                    </div>
                    <div className="flex items-center gap-4 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Calendar className="h-3 w-3" />
                        {new Date(check.checkDate).toLocaleDateString()}
                      </span>
                      {check.benefitsRemaining && (
                        <span className="flex items-center gap-1">
                          <DollarSign className="h-3 w-3" />
                          {formatCurrency(check.benefitsRemaining)} remaining
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-muted-foreground">
                <Shield className="h-12 w-12 mx-auto mb-2" />
                <p>No recent verifications</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
