import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Link } from "wouter";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DollarSign,
  FileText,
  AlertCircle,
  CheckCircle2,
  Clock,
  XCircle,
  Search,
  Plus,
  TrendingUp,
  ArrowRight,
  Send,
  Brain,
  Phone,
  Calendar,
  MessageSquare,
  RefreshCw,
  FileCheck,
  AlertTriangle,
  Users,
  Loader2,
} from "lucide-react";
import { format } from "date-fns";
import type { BillingClaim, TreatmentPlan, PriorAuthorization } from "@shared/schema";
import { queryClient, apiRequest } from "@/lib/queryClient";
import { useToast } from "@/hooks/use-toast";

interface BillingStats {
  totalBilled: number;
  totalCollected: number;
  pendingClaims: number;
  deniedClaims: number;
  averageReimbursement: number;
}

const statusColors: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400",
  submitted: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
  in_review: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
  approved: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
  paid: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
  denied: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
  appealed: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400",
  peer_review: "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400",
  partial: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400",
};

const fullArchCodes = [
  { code: "D6114", description: "Implant/abutment supported fixed denture for completely edentulous arch", fee: 28500 },
  { code: "D6010", description: "Surgical placement of implant body: endosteal implant", fee: 2200 },
  { code: "D6056", description: "Prefabricated abutment", fee: 650 },
  { code: "D6058", description: "Abutment supported porcelain/ceramic crown", fee: 1400 },
  { code: "D7210", description: "Extraction, erupted tooth requiring elevation of mucoperiosteal flap", fee: 285 },
  { code: "D7953", description: "Bone replacement graft", fee: 875 },
];

export default function BillingPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState("claims");
  const [showAuthDialog, setShowAuthDialog] = useState(false);
  const [showP2PDialog, setShowP2PDialog] = useState(false);
  const [selectedAuth, setSelectedAuth] = useState<PriorAuthorization | null>(null);
  const [appealText, setAppealText] = useState("");
  const [generatingAppeal, setGeneratingAppeal] = useState(false);
  const [newAuthPatientId, setNewAuthPatientId] = useState("");
  const [newAuthType, setNewAuthType] = useState<"medical" | "dental">("medical");
  const [p2pNotes, setP2pNotes] = useState("");
  const [p2pOutcome, setP2pOutcome] = useState("");
  const { toast } = useToast();

  const { data: stats, isLoading: statsLoading } = useQuery<BillingStats>({
    queryKey: ["/api/billing/stats"],
  });

  const { data: claims, isLoading: claimsLoading } = useQuery<BillingClaim[]>({
    queryKey: ["/api/billing/claims"],
  });

  const { data: priorAuths, isLoading: authsLoading } = useQuery<PriorAuthorization[]>({
    queryKey: ["/api/prior-authorizations"],
  });

  const { data: treatmentPlans } = useQuery<TreatmentPlan[]>({
    queryKey: ["/api/treatment-plans"],
  });

  const { data: patients } = useQuery<{ id: number; firstName: string; lastName: string }[]>({
    queryKey: ["/api/patients"],
  });

  const deniedAuths = priorAuths?.filter(auth => auth.status === "denied") || [];
  const pendingP2P = priorAuths?.filter(auth => auth.peerToPeerRequired && !auth.peerToPeerOutcome) || [];

  const updateAuthMutation = useMutation({
    mutationFn: async ({ id, data }: { id: number; data: Partial<PriorAuthorization> }) => {
      return apiRequest("PATCH", `/api/prior-authorizations/${id}`, data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/prior-authorizations"] });
      toast({ title: "Authorization updated successfully" });
    },
    onError: (error: Error) => {
      toast({ title: "Error updating authorization", description: error.message, variant: "destructive" });
    },
  });

  const generateAppealMutation = useMutation({
    mutationFn: async (authId: number) => {
      const auth = priorAuths?.find(a => a.id === authId);
      if (!auth) throw new Error("Authorization not found");
      
      const response = await apiRequest("POST", "/api/ai/appeal-letter", {
        patientId: auth.patientId,
        treatmentPlanId: auth.treatmentPlanId,
        denialReason: auth.denialReason || "Medical necessity not demonstrated",
        insuranceType: "medical",
      });
      return response.json();
    },
    onSuccess: (data, authId) => {
      setAppealText(data.appealLetter || "");
      toast({ title: "Appeal letter generated successfully" });
    },
    onError: (error: Error) => {
      toast({ title: "Error generating appeal", description: error.message, variant: "destructive" });
    },
  });

  const createAuthMutation = useMutation({
    mutationFn: async (data: { patientId: number; authType: string }) => {
      return apiRequest("POST", "/api/prior-authorizations", data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/prior-authorizations"] });
      toast({ title: "Prior authorization created successfully" });
      setShowAuthDialog(false);
      setNewAuthPatientId("");
      setNewAuthType("medical");
    },
    onError: (error: Error) => {
      toast({ title: "Error creating authorization", description: error.message, variant: "destructive" });
    },
  });

  const handleCreateAuth = () => {
    if (!newAuthPatientId) {
      toast({ title: "Please select a patient", variant: "destructive" });
      return;
    }
    createAuthMutation.mutate({
      patientId: parseInt(newAuthPatientId),
      authType: newAuthType,
    });
  };

  const handleP2PSubmit = async () => {
    if (!selectedAuth || !p2pOutcome) return;
    
    await updateAuthMutation.mutateAsync({
      id: selectedAuth.id,
      data: {
        peerToPeerOutcome: p2pOutcome,
        peerToPeerNotes: p2pNotes,
        status: p2pOutcome === "approved" ? "approved" : p2pOutcome === "denied" ? "denied" : "in_review",
      },
    });
    setShowP2PDialog(false);
    setSelectedAuth(null);
    setP2pNotes("");
    setP2pOutcome("");
  };

  const filteredClaims = claims?.filter((claim) =>
    claim.procedureCode?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    claim.description?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const formatCurrency = (amount: number | string | null | undefined) => {
    if (!amount) return "$0.00";
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
    }).format(Number(amount));
  };

  const handleScheduleP2P = (auth: PriorAuthorization) => {
    setSelectedAuth(auth);
    setShowP2PDialog(true);
  };

  const handleGenerateAppeal = async (authId: number) => {
    setGeneratingAppeal(true);
    try {
      await generateAppealMutation.mutateAsync(authId);
    } finally {
      setGeneratingAppeal(false);
    }
  };

  const handleSubmitAppeal = async (authId: number) => {
    await updateAuthMutation.mutateAsync({
      id: authId,
      data: {
        status: "appealed",
        appealLetter: appealText,
        lastAppealDate: new Date().toISOString().split('T')[0],
        appealCount: (selectedAuth?.appealCount || 0) + 1,
      },
    });
    setAppealText("");
    setSelectedAuth(null);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Billing & Claims</h1>
          <p className="text-muted-foreground">
            Manage insurance claims, prior authorizations, and billing for full arch implants
          </p>
        </div>
        <div className="flex gap-3">
          <Button variant="outline" data-testid="button-batch-submit">
            <Send className="mr-2 h-4 w-4" />
            Batch Submit
          </Button>
          <Button data-testid="button-new-claim">
            <Plus className="mr-2 h-4 w-4" />
            New Claim
          </Button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Total Billed</p>
                {statsLoading ? (
                  <Skeleton className="mt-1 h-8 w-24" />
                ) : (
                  <p className="text-2xl font-bold">{formatCurrency(stats?.totalBilled)}</p>
                )}
              </div>
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                <DollarSign className="h-5 w-5 text-primary" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Collected</p>
                {statsLoading ? (
                  <Skeleton className="mt-1 h-8 w-24" />
                ) : (
                  <p className="text-2xl font-bold text-green-600">{formatCurrency(stats?.totalCollected)}</p>
                )}
              </div>
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-100 dark:bg-green-900/30">
                <CheckCircle2 className="h-5 w-5 text-green-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Pending</p>
                {statsLoading ? (
                  <Skeleton className="mt-1 h-8 w-16" />
                ) : (
                  <p className="text-2xl font-bold text-yellow-600">{stats?.pendingClaims || 0}</p>
                )}
              </div>
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-yellow-100 dark:bg-yellow-900/30">
                <Clock className="h-5 w-5 text-yellow-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Denied</p>
                {statsLoading ? (
                  <Skeleton className="mt-1 h-8 w-16" />
                ) : (
                  <p className="text-2xl font-bold text-red-600">{stats?.deniedClaims || 0}</p>
                )}
              </div>
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-red-100 dark:bg-red-900/30">
                <XCircle className="h-5 w-5 text-red-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Avg. Reimb.</p>
                {statsLoading ? (
                  <Skeleton className="mt-1 h-8 w-16" />
                ) : (
                  <p className="text-2xl font-bold">{stats?.averageReimbursement || 0}%</p>
                )}
              </div>
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-chart-3/10">
                <TrendingUp className="h-5 w-5 text-chart-3" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList>
          <TabsTrigger value="claims" data-testid="tab-claims">Claims</TabsTrigger>
          <TabsTrigger value="prior-auth" data-testid="tab-prior-auth">
            Prior Authorizations
            {priorAuths && priorAuths.filter(a => a.status === "pending" || a.status === "submitted").length > 0 && (
              <Badge variant="secondary" className="ml-2">
                {priorAuths.filter(a => a.status === "pending" || a.status === "submitted").length}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="peer-review" data-testid="tab-peer-review">
            Peer-to-Peer
            {pendingP2P.length > 0 && (
              <Badge variant="destructive" className="ml-2">{pendingP2P.length}</Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="denials" data-testid="tab-denials">
            Denials & Appeals
            {deniedAuths.length > 0 && (
              <Badge variant="destructive" className="ml-2">{deniedAuths.length}</Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="fee-schedule" data-testid="tab-fee-schedule">Fee Schedule</TabsTrigger>
        </TabsList>

        <TabsContent value="claims" className="space-y-4">
          <Card>
            <CardHeader className="pb-4">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="relative flex-1 max-w-md">
                  <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    placeholder="Search claims by code or description..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-9"
                    data-testid="input-search-claims"
                  />
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {claimsLoading ? (
                <div className="space-y-3">
                  {[1, 2, 3, 4].map((i) => (
                    <Skeleton key={i} className="h-16 w-full" />
                  ))}
                </div>
              ) : filteredClaims && filteredClaims.length > 0 ? (
                <div className="rounded-md border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Claim #</TableHead>
                        <TableHead>Procedure</TableHead>
                        <TableHead>Service Date</TableHead>
                        <TableHead>Charged</TableHead>
                        <TableHead>Paid</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredClaims.map((claim) => (
                        <TableRow key={claim.id}>
                          <TableCell className="font-mono text-sm">
                            {claim.claimNumber || `CLM-${claim.id}`}
                          </TableCell>
                          <TableCell>
                            <div>
                              <p className="font-medium">{claim.procedureCode}</p>
                              <p className="text-sm text-muted-foreground">{claim.description}</p>
                            </div>
                          </TableCell>
                          <TableCell>
                            {claim.serviceDate && format(new Date(claim.serviceDate), "MMM d, yyyy")}
                          </TableCell>
                          <TableCell>{formatCurrency(claim.chargedAmount)}</TableCell>
                          <TableCell className="text-green-600">
                            {formatCurrency(claim.paidAmount)}
                          </TableCell>
                          <TableCell>
                            <Badge className={statusColors[claim.claimStatus] || ""}>
                              {claim.claimStatus}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-right">
                            <Button variant="ghost" size="sm" data-testid={`button-view-claim-${claim.id}`}>
                              <ArrowRight className="h-4 w-4" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-muted">
                    <FileText className="h-8 w-8 text-muted-foreground" />
                  </div>
                  <h3 className="mb-2 text-lg font-semibold">No claims found</h3>
                  <p className="mb-6 max-w-sm text-sm text-muted-foreground">
                    Create treatment plans to generate billing claims
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="prior-auth" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-3">
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-yellow-100 dark:bg-yellow-900/30">
                    <Clock className="h-5 w-5 text-yellow-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{priorAuths?.filter(a => a.status === "pending").length || 0}</p>
                    <p className="text-sm text-muted-foreground">Pending Submission</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100 dark:bg-blue-900/30">
                    <RefreshCw className="h-5 w-5 text-blue-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{priorAuths?.filter(a => a.status === "submitted" || a.status === "in_review").length || 0}</p>
                    <p className="text-sm text-muted-foreground">Under Review</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-100 dark:bg-green-900/30">
                    <CheckCircle2 className="h-5 w-5 text-green-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{priorAuths?.filter(a => a.status === "approved").length || 0}</p>
                    <p className="text-sm text-muted-foreground">Approved</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Prior Authorization Requests</CardTitle>
                  <CardDescription>
                    Track and manage insurance pre-authorizations for full arch implant cases
                  </CardDescription>
                </div>
                <Button onClick={() => setShowAuthDialog(true)} data-testid="button-new-auth">
                  <Plus className="mr-2 h-4 w-4" />
                  New Authorization
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {authsLoading ? (
                <div className="space-y-3">
                  {[1, 2, 3].map((i) => (
                    <Skeleton key={i} className="h-20 w-full" />
                  ))}
                </div>
              ) : priorAuths && priorAuths.length > 0 ? (
                <div className="space-y-4">
                  {priorAuths.map((auth) => (
                    <div
                      key={auth.id}
                      className="flex items-center justify-between rounded-lg border p-4 hover-elevate"
                      data-testid={`auth-item-${auth.id}`}
                    >
                      <div className="flex items-center gap-4">
                        <div className={`flex h-12 w-12 items-center justify-center rounded-lg ${
                          auth.status === "approved" ? "bg-green-100 dark:bg-green-900/30" :
                          auth.status === "denied" ? "bg-red-100 dark:bg-red-900/30" :
                          auth.status === "submitted" || auth.status === "in_review" ? "bg-blue-100 dark:bg-blue-900/30" :
                          "bg-yellow-100 dark:bg-yellow-900/30"
                        }`}>
                          {auth.status === "approved" ? <CheckCircle2 className="h-6 w-6 text-green-600" /> :
                           auth.status === "denied" ? <XCircle className="h-6 w-6 text-red-600" /> :
                           auth.status === "submitted" || auth.status === "in_review" ? <RefreshCw className="h-6 w-6 text-blue-600" /> :
                           <Clock className="h-6 w-6 text-yellow-600" />}
                        </div>
                        <div>
                          <p className="font-medium">
                            {auth.authType === "medical" ? "Medical Insurance Auth" : "Dental Insurance Auth"}
                            {auth.authNumber && <span className="ml-2 text-muted-foreground font-mono text-sm">#{auth.authNumber}</span>}
                          </p>
                          <p className="text-sm text-muted-foreground">
                            Patient ID: {auth.patientId}
                            {auth.submissionDate && ` • Submitted: ${format(new Date(auth.submissionDate), "MMM d, yyyy")}`}
                          </p>
                          {auth.peerToPeerRequired && !auth.peerToPeerOutcome && (
                            <Badge variant="outline" className="mt-1 border-orange-300 text-orange-600">
                              <Phone className="mr-1 h-3 w-3" />
                              P2P Required
                            </Badge>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <Badge className={statusColors[auth.status] || ""}>
                          {auth.status.replace("_", " ")}
                        </Badge>
                        {auth.status === "pending" && (
                          <Button 
                            size="sm"
                            disabled={updateAuthMutation.isPending}
                            onClick={() => updateAuthMutation.mutate({ 
                              id: auth.id, 
                              data: { 
                                status: "submitted", 
                                submissionDate: new Date().toISOString().split('T')[0] 
                              } 
                            })}
                            data-testid={`button-submit-auth-${auth.id}`}
                          >
                            {updateAuthMutation.isPending ? (
                              <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                            ) : (
                              <Send className="mr-1 h-3 w-3" />
                            )}
                            Submit
                          </Button>
                        )}
                        {auth.peerToPeerRequired && !auth.peerToPeerOutcome && (
                          <Button 
                            size="sm" 
                            variant="outline"
                            onClick={() => handleScheduleP2P(auth)}
                            data-testid={`button-schedule-p2p-${auth.id}`}
                          >
                            <Phone className="mr-1 h-3 w-3" />
                            Schedule P2P
                          </Button>
                        )}
                        {auth.status === "denied" && (
                          <Button 
                            size="sm" 
                            variant="outline"
                            onClick={() => {
                              setSelectedAuth(auth);
                              setActiveTab("denials");
                            }}
                            data-testid={`button-appeal-${auth.id}`}
                          >
                            <Brain className="mr-1 h-3 w-3" />
                            Appeal
                          </Button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <FileCheck className="mb-3 h-10 w-10 text-muted-foreground/50" />
                  <h3 className="text-lg font-semibold">No prior authorizations</h3>
                  <p className="text-sm text-muted-foreground mb-4">
                    Create a prior authorization request to start the approval process
                  </p>
                  <Button onClick={() => setShowAuthDialog(true)} data-testid="button-create-first-auth">
                    <Plus className="mr-2 h-4 w-4" />
                    Create Authorization
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="peer-review" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <Phone className="h-5 w-5" />
                    Peer-to-Peer Reviews
                  </CardTitle>
                  <CardDescription>
                    Schedule and track peer-to-peer reviews with insurance medical directors
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {pendingP2P.length > 0 ? (
                <div className="space-y-4">
                  {pendingP2P.map((auth) => (
                    <div
                      key={auth.id}
                      className="rounded-lg border border-orange-200 bg-orange-50/50 p-4 dark:border-orange-900 dark:bg-orange-950/20"
                      data-testid={`p2p-item-${auth.id}`}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex items-start gap-4">
                          <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-orange-100 dark:bg-orange-900/30">
                            <Users className="h-6 w-6 text-orange-600" />
                          </div>
                          <div>
                            <p className="font-medium">Peer-to-Peer Review Required</p>
                            <p className="text-sm text-muted-foreground">
                              {auth.authType === "medical" ? "Medical Insurance" : "Dental Insurance"} • Patient ID: {auth.patientId}
                            </p>
                            {auth.peerToPeerDate && (
                              <p className="text-sm mt-1">
                                <Calendar className="inline h-3 w-3 mr-1" />
                                Scheduled: {format(new Date(auth.peerToPeerDate), "MMM d, yyyy 'at' h:mm a")}
                              </p>
                            )}
                            <div className="mt-2 p-2 rounded bg-background/80 text-sm">
                              <p className="font-medium text-xs text-muted-foreground mb-1">TIPS FOR P2P SUCCESS:</p>
                              <ul className="text-xs text-muted-foreground space-y-1">
                                <li>• Emphasize functional impairment and medical necessity</li>
                                <li>• Reference Arnett-Gunson facial evaluation findings</li>
                                <li>• Discuss airway/sleep apnea concerns if applicable</li>
                                <li>• Highlight nutritional deficiencies from inability to chew</li>
                              </ul>
                            </div>
                          </div>
                        </div>
                        <div className="flex flex-col gap-2">
                          <Button 
                            size="sm"
                            onClick={() => handleScheduleP2P(auth)}
                            data-testid={`button-manage-p2p-${auth.id}`}
                          >
                            <Calendar className="mr-1 h-3 w-3" />
                            {auth.peerToPeerDate ? "Update" : "Schedule"}
                          </Button>
                          <Button 
                            size="sm" 
                            variant="outline"
                            onClick={() => {
                              setSelectedAuth(auth);
                              setShowP2PDialog(true);
                            }}
                            data-testid={`button-complete-p2p-${auth.id}`}
                          >
                            <CheckCircle2 className="mr-1 h-3 w-3" />
                            Record Outcome
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <CheckCircle2 className="mb-3 h-10 w-10 text-green-500" />
                  <h3 className="text-lg font-semibold">No pending peer reviews</h3>
                  <p className="text-sm text-muted-foreground">
                    All peer-to-peer reviews have been completed or none are required
                  </p>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Completed Peer Reviews</CardTitle>
              <CardDescription>History of completed P2P calls and their outcomes</CardDescription>
            </CardHeader>
            <CardContent>
              {priorAuths?.filter(a => a.peerToPeerOutcome).length ? (
                <div className="space-y-3">
                  {priorAuths.filter(a => a.peerToPeerOutcome).map((auth) => (
                    <div key={auth.id} className="flex items-center justify-between rounded-lg border p-3">
                      <div className="flex items-center gap-3">
                        <Badge className={auth.peerToPeerOutcome === "approved" ? statusColors.approved : statusColors.denied}>
                          {auth.peerToPeerOutcome}
                        </Badge>
                        <div>
                          <p className="font-medium text-sm">Patient ID: {auth.patientId}</p>
                          {auth.peerToPeerDate && (
                            <p className="text-xs text-muted-foreground">
                              {format(new Date(auth.peerToPeerDate), "MMM d, yyyy")}
                            </p>
                          )}
                        </div>
                      </div>
                      {auth.peerToPeerNotes && (
                        <Button variant="ghost" size="sm" data-testid={`button-p2p-notes-${auth.id}`}>
                          <MessageSquare className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground text-center py-4">No completed peer reviews yet</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="denials" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <AlertTriangle className="h-5 w-5 text-red-500" />
                    Denial Management
                  </CardTitle>
                  <CardDescription>
                    Review denied authorizations and generate AI-powered appeal letters
                  </CardDescription>
                </div>
                <Button 
                  variant="outline" 
                  onClick={() => {
                    deniedAuths.forEach(auth => handleGenerateAppeal(auth.id));
                  }}
                  disabled={deniedAuths.length === 0 || generatingAppeal}
                  data-testid="button-auto-appeal-all"
                >
                  {generatingAppeal && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  <Brain className="mr-2 h-4 w-4" />
                  AI Auto-Appeal All
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {deniedAuths.length > 0 ? (
                <div className="space-y-4">
                  {deniedAuths.map((auth) => (
                    <div
                      key={auth.id}
                      className="rounded-lg border border-red-200 bg-red-50/50 p-4 dark:border-red-900 dark:bg-red-950/20"
                      data-testid={`denial-item-${auth.id}`}
                    >
                      <div className="flex items-start justify-between mb-3">
                        <div className="flex items-start gap-4">
                          <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-red-100 dark:bg-red-900/30">
                            <XCircle className="h-6 w-6 text-red-600" />
                          </div>
                          <div>
                            <p className="font-medium">
                              Authorization Denied
                              {auth.authNumber && <span className="ml-2 text-muted-foreground font-mono text-sm">#{auth.authNumber}</span>}
                            </p>
                            <p className="text-sm text-muted-foreground">
                              Patient ID: {auth.patientId} • {auth.authType === "medical" ? "Medical" : "Dental"} Insurance
                            </p>
                            {auth.responseDate && (
                              <p className="text-xs text-muted-foreground mt-1">
                                Denied on {format(new Date(auth.responseDate), "MMM d, yyyy")}
                              </p>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          {auth.appealCount && auth.appealCount > 0 && (
                            <Badge variant="outline">
                              {auth.appealCount} Appeal{auth.appealCount > 1 ? "s" : ""}
                            </Badge>
                          )}
                          <Badge className={statusColors.denied}>Denied</Badge>
                        </div>
                      </div>

                      {auth.denialReason && (
                        <div className="mb-3 p-3 rounded-lg bg-background/80">
                          <p className="text-xs font-medium text-muted-foreground mb-1">DENIAL REASON:</p>
                          <p className="text-sm">{auth.denialReason}</p>
                        </div>
                      )}

                      <div className="flex items-center gap-2">
                        <Button 
                          onClick={() => {
                            setSelectedAuth(auth);
                            handleGenerateAppeal(auth.id);
                          }}
                          disabled={generatingAppeal}
                          data-testid={`button-generate-appeal-${auth.id}`}
                        >
                          {generatingAppeal && selectedAuth?.id === auth.id ? (
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          ) : (
                            <Brain className="mr-2 h-4 w-4" />
                          )}
                          Generate AI Appeal
                        </Button>
                        <Button variant="outline" data-testid={`button-manual-appeal-${auth.id}`}>
                          <FileText className="mr-2 h-4 w-4" />
                          Manual Appeal
                        </Button>
                        <Button variant="ghost" size="sm" data-testid={`button-view-denial-${auth.id}`}>
                          View Details
                          <ArrowRight className="ml-1 h-4 w-4" />
                        </Button>
                      </div>

                      {appealText && selectedAuth?.id === auth.id && (
                        <div className="mt-4 p-4 rounded-lg border bg-background">
                          <div className="flex items-center justify-between mb-2">
                            <p className="font-medium text-sm">Generated Appeal Letter</p>
                            <Button 
                              size="sm"
                              onClick={() => handleSubmitAppeal(auth.id)}
                              disabled={updateAuthMutation.isPending}
                              data-testid={`button-submit-appeal-${auth.id}`}
                            >
                              {updateAuthMutation.isPending ? (
                                <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                              ) : (
                                <Send className="mr-1 h-3 w-3" />
                              )}
                              Submit Appeal
                            </Button>
                          </div>
                          <Textarea
                            value={appealText}
                            onChange={(e) => setAppealText(e.target.value)}
                            className="min-h-[200px] text-sm"
                            data-testid={`textarea-appeal-${auth.id}`}
                          />
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-100 dark:bg-green-900/30">
                    <CheckCircle2 className="h-8 w-8 text-green-600" />
                  </div>
                  <h3 className="mb-2 text-lg font-semibold">No denied authorizations</h3>
                  <p className="max-w-sm text-sm text-muted-foreground">
                    All your prior authorizations are either approved, pending, or under review
                  </p>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Appeal Success Strategies</CardTitle>
              <CardDescription>Best practices for successful full arch implant appeals</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="p-4 rounded-lg border">
                  <h4 className="font-medium mb-2 flex items-center gap-2">
                    <FileCheck className="h-4 w-4 text-primary" />
                    Medical Necessity Documentation
                  </h4>
                  <ul className="text-sm text-muted-foreground space-y-1">
                    <li>• Include Arnett-Gunson facial evaluation</li>
                    <li>• Document functional impairment (chewing, speech)</li>
                    <li>• Reference nutritional assessment if applicable</li>
                    <li>• Include cephalometric analysis with skeletal classification</li>
                  </ul>
                </div>
                <div className="p-4 rounded-lg border">
                  <h4 className="font-medium mb-2 flex items-center gap-2">
                    <Brain className="h-4 w-4 text-primary" />
                    AI Appeal Tips
                  </h4>
                  <ul className="text-sm text-muted-foreground space-y-1">
                    <li>• Let AI reference clinical literature</li>
                    <li>• Include specific ICD-10/CDT codes in appeal</li>
                    <li>• Emphasize quality of life improvements</li>
                    <li>• Reference peer-reviewed studies on implant success</li>
                  </ul>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="fee-schedule" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Full Arch Implant Fee Schedule</CardTitle>
              <CardDescription>
                Standard CDT codes and fees for full arch dental implant procedures
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>CDT Code</TableHead>
                      <TableHead>Description</TableHead>
                      <TableHead className="text-right">UCR Fee</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {fullArchCodes.map((code) => (
                      <TableRow key={code.code}>
                        <TableCell className="font-mono font-medium">{code.code}</TableCell>
                        <TableCell>{code.description}</TableCell>
                        <TableCell className="text-right font-medium">
                          {formatCurrency(code.fee)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <Dialog open={showAuthDialog} onOpenChange={setShowAuthDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>New Prior Authorization</DialogTitle>
            <DialogDescription>
              Create a new prior authorization request for a full arch implant case.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Patient</Label>
              <Select value={newAuthPatientId} onValueChange={setNewAuthPatientId}>
                <SelectTrigger data-testid="select-auth-patient">
                  <SelectValue placeholder="Select patient" />
                </SelectTrigger>
                <SelectContent>
                  {patients?.map((patient) => (
                    <SelectItem key={patient.id} value={patient.id.toString()}>
                      {patient.firstName} {patient.lastName}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Insurance Type</Label>
              <Select value={newAuthType} onValueChange={(v) => setNewAuthType(v as "medical" | "dental")}>
                <SelectTrigger data-testid="select-auth-type">
                  <SelectValue placeholder="Select type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="medical">Medical Insurance</SelectItem>
                  <SelectItem value="dental">Dental Insurance</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setShowAuthDialog(false)} data-testid="button-cancel-auth">
              Cancel
            </Button>
            <Button 
              onClick={handleCreateAuth} 
              disabled={createAuthMutation.isPending}
              data-testid="button-submit-new-auth"
            >
              {createAuthMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Create Authorization
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={showP2PDialog} onOpenChange={setShowP2PDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Peer-to-Peer Review Outcome</DialogTitle>
            <DialogDescription>
              Record the outcome of the peer-to-peer review call with the insurance medical director.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Outcome</Label>
              <Select value={p2pOutcome} onValueChange={setP2pOutcome}>
                <SelectTrigger data-testid="select-p2p-outcome">
                  <SelectValue placeholder="Select outcome" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="approved">Approved</SelectItem>
                  <SelectItem value="denied">Denied</SelectItem>
                  <SelectItem value="additional_info">Additional Info Requested</SelectItem>
                  <SelectItem value="pending">Still Pending</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="p2p-notes">Notes</Label>
              <Textarea
                id="p2p-notes"
                value={p2pNotes}
                onChange={(e) => setP2pNotes(e.target.value)}
                placeholder="Document key points from the P2P call..."
                className="min-h-[100px]"
                data-testid="textarea-p2p-notes"
              />
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setShowP2PDialog(false)} data-testid="button-cancel-p2p">
              Cancel
            </Button>
            <Button 
              onClick={handleP2PSubmit} 
              disabled={!p2pOutcome || updateAuthMutation.isPending}
              data-testid="button-submit-p2p"
            >
              {updateAuthMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Record Outcome
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
