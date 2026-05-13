import { useState, Fragment } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Link } from "wouter";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
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
  ShieldCheck,
  ShieldAlert,
  Wrench,
  ChevronRight,
  Info,
  Download,
} from "lucide-react";
import { exportToCSV } from "@/lib/export";
import { format } from "date-fns";
import type { BillingClaim, TreatmentPlan, PriorAuthorization, ClaimPreflightResult } from "@shared/schema";
import { queryClient, apiRequest } from "@/lib/queryClient";
import { useToast } from "@/hooks/use-toast";

interface BillingStats {
  totalBilled: number;
  totalCollected: number;
  pendingClaims: number;
  deniedClaims: number;
  averageReimbursement: number;
}

interface PreflightIssue {
  code: string;
  severity: "critical" | "warning" | "info";
  description: string;
  suggestion: string;
  autoFixable: boolean;
  fixValue?: string;
}

interface PreflightCheckItem {
  label: string;
  passed: boolean;
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

function RiskGauge({ score }: { score: number }) {
  const color = score >= 80 ? "text-green-600" : score >= 60 ? "text-yellow-600" : "text-red-600";
  const bgColor = score >= 80 ? "bg-green-100 dark:bg-green-900/30" : score >= 60 ? "bg-yellow-100 dark:bg-yellow-900/30" : "bg-red-100 dark:bg-red-900/30";
  const label = score >= 80 ? "Low Risk" : score >= 60 ? "Moderate Risk" : "High Risk";
  const radius = 40;
  const circumference = 2 * Math.PI * radius;
  const progress = (score / 100) * circumference;

  return (
    <div className={`flex flex-col items-center p-4 rounded-xl ${bgColor}`}>
      <svg width="100" height="60" viewBox="0 0 100 60">
        <path
          d={`M 10 50 A 40 40 0 0 1 90 50`}
          fill="none"
          stroke="currentColor"
          strokeWidth="8"
          className="text-muted/20"
        />
        <path
          d={`M 10 50 A 40 40 0 0 1 90 50`}
          fill="none"
          stroke="currentColor"
          strokeWidth="8"
          strokeDasharray={`${(score / 100) * 125.7} 125.7`}
          strokeLinecap="round"
          className={color}
        />
        <text x="50" y="48" textAnchor="middle" className={`text-sm font-bold fill-current ${color}`} fontSize="16">{score}</text>
      </svg>
      <span className={`text-sm font-semibold ${color}`}>{label}</span>
      <span className="text-xs text-muted-foreground mt-0.5">Risk Score</span>
    </div>
  );
}

function PreflightDialog({
  open,
  onClose,
  claim,
  result,
  isLoading,
  onRunCheck,
  onAutoFix,
  isFixing,
  onSubmitClaim,
  isSubmitting,
}: {
  open: boolean;
  onClose: () => void;
  claim: BillingClaim | null;
  result: ClaimPreflightResult | null;
  isLoading: boolean;
  onRunCheck: () => void;
  onAutoFix: (issueCode: string, fixValue: string, field: string) => void;
  isFixing: Set<string>;
  onSubmitClaim: () => void;
  isSubmitting: boolean;
}) {
  if (!claim) return null;

  const issues = (result?.issues as PreflightIssue[]) || [];
  const checklist = (result?.checklist as PreflightCheckItem[]) || [];
  const riskScore = result?.riskScore ?? null;
  const approvalProbability = result?.approvalProbability ?? null;
  const recommendedActions = result?.recommendedActions ?? [];

  const criticalCount = issues.filter(i => i.severity === "critical").length;
  const warningCount = issues.filter(i => i.severity === "warning").length;
  const canSubmit = riskScore !== null && riskScore >= 70;

  const fieldMap: Record<string, string> = {
    MISSING_ICD10: "icd10Code",
    INVALID_ICD10: "icd10Code",
    MISSING_MODIFIER: "procedureCode",
    WRONG_CODE: "procedureCode",
  };

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="dialog-preflight">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-primary" />
            AI Claim Pre-Flight Check
          </DialogTitle>
          <DialogDescription>
            Claim {claim.claimNumber || `CLM-${claim.id}`} — {claim.procedureCode}
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <div className="space-y-3 py-4">
            <div className="flex items-center gap-3 text-muted-foreground">
              <Loader2 className="h-5 w-5 animate-spin text-primary" />
              <span>AI is analyzing your claim for denial triggers…</span>
            </div>
            {[1, 2, 3, 4].map(i => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : result ? (
          <div className="space-y-5">
            {/* Score + Approval Row */}
            <div className="grid grid-cols-3 gap-3">
              <RiskGauge score={riskScore!} />
              <div className="col-span-2 flex flex-col justify-center gap-3">
                <div className="flex items-center justify-between rounded-lg border p-3">
                  <div>
                    <p className="text-xs text-muted-foreground uppercase tracking-wide">Approval Probability</p>
                    <p className="text-2xl font-bold text-primary">{approvalProbability}%</p>
                  </div>
                  <TrendingUp className="h-8 w-8 text-primary/30" />
                </div>
                <div className="flex gap-2">
                  {criticalCount > 0 && (
                    <Badge className="bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">
                      <XCircle className="mr-1 h-3 w-3" />
                      {criticalCount} Critical
                    </Badge>
                  )}
                  {warningCount > 0 && (
                    <Badge className="bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400">
                      <AlertTriangle className="mr-1 h-3 w-3" />
                      {warningCount} Warning
                    </Badge>
                  )}
                  {criticalCount === 0 && warningCount === 0 && (
                    <Badge className="bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">
                      <CheckCircle2 className="mr-1 h-3 w-3" />
                      All Clear
                    </Badge>
                  )}
                </div>
              </div>
            </div>

            {/* Checklist */}
            {checklist.length > 0 && (
              <div>
                <p className="text-sm font-semibold mb-2 flex items-center gap-1.5">
                  <FileCheck className="h-4 w-4 text-muted-foreground" />
                  Pre-Submission Checklist
                </p>
                <div className="rounded-lg border divide-y">
                  {checklist.map((item, idx) => (
                    <div key={idx} className="flex items-center gap-3 px-3 py-2" data-testid={`checklist-item-${idx}`}>
                      {item.passed ? (
                        <CheckCircle2 className="h-4 w-4 shrink-0 text-green-500" />
                      ) : (
                        <XCircle className="h-4 w-4 shrink-0 text-red-500" />
                      )}
                      <span className={`text-sm ${item.passed ? "text-foreground" : "text-red-600 dark:text-red-400"}`}>
                        {item.label}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Issues */}
            {issues.length > 0 && (
              <div>
                <p className="text-sm font-semibold mb-2 flex items-center gap-1.5">
                  <AlertCircle className="h-4 w-4 text-muted-foreground" />
                  Denial Risk Issues
                </p>
                <div className="space-y-2">
                  {issues.map((issue, idx) => (
                    <div
                      key={idx}
                      className={`rounded-lg border p-3 ${
                        issue.severity === "critical"
                          ? "border-red-200 bg-red-50/50 dark:border-red-900 dark:bg-red-950/20"
                          : issue.severity === "warning"
                          ? "border-yellow-200 bg-yellow-50/50 dark:border-yellow-900 dark:bg-yellow-950/20"
                          : "border-green-200 bg-green-50/50 dark:border-green-900 dark:bg-green-950/20"
                      }`}
                      data-testid={`issue-item-${idx}`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-start gap-2 flex-1">
                          {issue.severity === "critical" ? (
                            <ShieldAlert className="h-4 w-4 shrink-0 mt-0.5 text-red-600" />
                          ) : issue.severity === "warning" ? (
                            <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5 text-yellow-600" />
                          ) : (
                            <Info className="h-4 w-4 shrink-0 mt-0.5 text-green-600" />
                          )}
                          <div>
                            <p className="text-sm font-medium">{issue.description}</p>
                            <p className="text-xs text-muted-foreground mt-0.5">{issue.suggestion}</p>
                          </div>
                        </div>
                        {issue.autoFixable && issue.fixValue && (
                          <Button
                            size="sm"
                            variant="outline"
                            className="shrink-0 h-7 text-xs"
                            disabled={isFixing.has(issue.code)}
                            onClick={() => {
                              const field = fieldMap[issue.code] || "icd10Code";
                              onAutoFix(issue.code, issue.fixValue!, field);
                            }}
                            data-testid={`button-autofix-${idx}`}
                          >
                            {isFixing.has(issue.code) ? (
                              <Loader2 className="h-3 w-3 animate-spin" />
                            ) : (
                              <Wrench className="h-3 w-3 mr-1" />
                            )}
                            Auto-Fix
                          </Button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Recommended Actions */}
            {recommendedActions.length > 0 && (
              <div className="rounded-lg border bg-muted/30 p-3">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Recommended Actions</p>
                <ul className="space-y-1">
                  {recommendedActions.map((action, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-sm">
                      <ChevronRight className="h-4 w-4 shrink-0 text-primary mt-0.5" />
                      {action}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Submit Gate */}
            <div className={`rounded-lg border p-4 ${canSubmit ? "border-green-200 bg-green-50/50 dark:border-green-900 dark:bg-green-950/20" : "border-red-200 bg-red-50/50 dark:border-red-900 dark:bg-red-950/20"}`}>
              {canSubmit ? (
                <div className="flex items-center gap-3">
                  <CheckCircle2 className="h-5 w-5 text-green-600 shrink-0" />
                  <div>
                    <p className="text-sm font-semibold text-green-700 dark:text-green-400">Claim is cleared for submission</p>
                    <p className="text-xs text-muted-foreground">Risk score {riskScore}/100 meets the minimum threshold of 70</p>
                  </div>
                </div>
              ) : (
                <div className="flex items-center gap-3">
                  <ShieldAlert className="h-5 w-5 text-red-600 shrink-0" />
                  <div>
                    <p className="text-sm font-semibold text-red-700 dark:text-red-400">Claim blocked — resolve issues before submitting</p>
                    <p className="text-xs text-muted-foreground">Risk score {riskScore}/100 is below the minimum threshold of 70</p>
                  </div>
                </div>
              )}
            </div>

            <div className="flex justify-between pt-1">
              <Button variant="outline" onClick={onRunCheck} data-testid="button-rerun-preflight">
                <RefreshCw className="mr-2 h-4 w-4" />
                Re-run Check
              </Button>
              <Button
                disabled={!canSubmit || isSubmitting}
                data-testid="button-submit-claim-gated"
                onClick={onSubmitClaim}
              >
                {isSubmitting ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Send className="mr-2 h-4 w-4" />
                )}
                Submit Claim
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-10 gap-4 text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
              <ShieldCheck className="h-8 w-8 text-primary" />
            </div>
            <div>
              <h3 className="text-base font-semibold">Run AI Pre-Flight Check</h3>
              <p className="text-sm text-muted-foreground mt-1 max-w-sm">
                Our AI will analyze this claim for coding errors, missing documentation, and denial triggers before you submit.
              </p>
            </div>
            <Button onClick={onRunCheck} data-testid="button-run-preflight">
              <Brain className="mr-2 h-4 w-4" />
              Analyze Claim
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

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

  // Pre-flight state
  const [preflightClaim, setPreflightClaim] = useState<BillingClaim | null>(null);
  const [preflightOpen, setPreflightOpen] = useState(false);
  const [preflightResult, setPreflightResult] = useState<ClaimPreflightResult | null>(null);
  const [preflightLoading, setPreflightLoading] = useState(false);
  const [fixingIssues, setFixingIssues] = useState<Set<string>>(new Set());
  // Inline detail panel and cached results per claim
  const [expandedClaimId, setExpandedClaimId] = useState<number | null>(null);
  const [preflightCache, setPreflightCache] = useState<Record<number, ClaimPreflightResult>>({});

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

  const { data: patients } = useQuery<{ id: number; firstName: string; lastName: string; dateOfBirth: string | null }[]>({
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
    onSuccess: (data) => {
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

  const autoFixMutation = useMutation({
    mutationFn: async ({ claimId, issueCode, fixValue, field }: { claimId: number; issueCode: string; fixValue: string; field: string }) => {
      const response = await apiRequest("PATCH", `/api/billing/claims/${claimId}/autofix`, { issueCode, fixValue, field });
      return response.json();
    },
    onSuccess: (data, vars) => {
      queryClient.invalidateQueries({ queryKey: ["/api/billing/claims"] });
      setFixingIssues(prev => { const next = new Set(prev); next.delete(vars.issueCode); return next; });
      toast({ title: "Auto-fix applied", description: `Issue ${vars.issueCode} has been resolved.` });
    },
    onError: (error: Error, vars) => {
      setFixingIssues(prev => { const next = new Set(prev); next.delete(vars.issueCode); return next; });
      toast({ title: "Auto-fix failed", description: error.message, variant: "destructive" });
    },
  });

  const submitClaimMutation = useMutation({
    mutationFn: async (claimId: number) => {
      const response = await apiRequest("PATCH", `/api/billing/claims/${claimId}`, {
        claimStatus: "submitted",
        submittedDate: new Date().toISOString().split("T")[0],
      });
      if (!response.ok) {
        const body = await response.json();
        throw new Error(body.message || "Failed to submit claim");
      }
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/billing/claims"] });
      queryClient.invalidateQueries({ queryKey: ["/api/billing/stats"] });
      toast({ title: "Claim submitted successfully" });
      setPreflightOpen(false);
      setPreflightClaim(null);
      setPreflightResult(null);
    },
    onError: (error: Error) => {
      toast({ title: "Submission blocked", description: error.message, variant: "destructive" });
    },
  });

  const handleOpenPreflight = async (claim: BillingClaim) => {
    setPreflightClaim(claim);
    setPreflightResult(preflightCache[claim.id] ?? null);
    setPreflightOpen(true);
    // Try to load existing result from server
    try {
      const response = await apiRequest("GET", `/api/billing/claims/${claim.id}/preflight`);
      if (response.ok) {
        const existing: ClaimPreflightResult = await response.json();
        setPreflightResult(existing);
        setPreflightCache(prev => ({ ...prev, [claim.id]: existing }));
      }
    } catch {
      // No existing result — will prompt user to run
    }
  };

  const handleExpandDetail = async (claimId: number) => {
    setExpandedClaimId(prev => (prev === claimId ? null : claimId));
    if (!preflightCache[claimId]) {
      try {
        const response = await apiRequest("GET", `/api/billing/claims/${claimId}/preflight`);
        if (response.ok) {
          const result: ClaimPreflightResult = await response.json();
          setPreflightCache(prev => ({ ...prev, [claimId]: result }));
        }
      } catch {
        // No result yet
      }
    }
  };

  const handleRunPreflight = async () => {
    if (!preflightClaim) return;
    setPreflightLoading(true);
    try {
      const response = await apiRequest("POST", `/api/billing/claims/${preflightClaim.id}/preflight`);
      const result: ClaimPreflightResult = await response.json();
      setPreflightResult(result);
      setPreflightCache(prev => ({ ...prev, [preflightClaim.id]: result }));
      toast({ title: "Pre-flight check complete", description: `Risk score: ${result.riskScore}/100` });
    } catch (err) {
      toast({ title: "Pre-flight check failed", description: "Please try again.", variant: "destructive" });
    } finally {
      setPreflightLoading(false);
    }
  };

  const handleAutoFix = (issueCode: string, fixValue: string, field: string) => {
    if (!preflightClaim) return;
    setFixingIssues(prev => new Set(prev).add(issueCode));
    autoFixMutation.mutate({ claimId: preflightClaim.id, issueCode, fixValue, field });
  };

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
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    const patientMap = new Map(
                      (patients ?? []).map((p) => [
                        p.id,
                        { name: `${p.firstName} ${p.lastName}`, dob: p.dateOfBirth ?? "" },
                      ]),
                    );
                    const rows = (filteredClaims ?? []).map((c) => {
                      const pt = patientMap.get(c.patientId);
                      return {
                        "Claim #": c.claimNumber ?? c.id,
                        "Patient Name": pt?.name ?? "",
                        "Date of Birth": pt?.dob ?? "",
                        "Procedure Code (CDT)": c.procedureCode ?? "",
                        "ICD-10": c.icd10Code ?? "",
                        Description: c.description ?? "",
                        "Service Date": c.serviceDate ? new Date(c.serviceDate).toLocaleDateString() : "",
                        "Charged ($)": c.chargedAmount ?? "",
                        "Allowed ($)": c.allowedAmount ?? "",
                        "Paid ($)": c.paidAmount ?? "",
                        "Patient Portion ($)": c.patientPortion ?? "",
                        Status: c.claimStatus ?? "",
                        "Submitted Date": c.submittedDate ? new Date(c.submittedDate).toLocaleDateString() : "",
                        "Paid Date": c.paidDate ? new Date(c.paidDate).toLocaleDateString() : "",
                        "Denial Reason": c.denialReason ?? "",
                      };
                    });
                    exportToCSV(rows, "Claims");
                  }}
                  data-testid="button-export-claims-csv"
                >
                  <Download className="mr-2 h-3.5 w-3.5" />
                  Export CSV
                </Button>
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
                      {filteredClaims.map((claim) => {
                        const cached = preflightCache[claim.id];
                        const isExpanded = expandedClaimId === claim.id;
                        const issues = (cached?.issues as PreflightIssue[]) || [];
                        const criticals = issues.filter(i => i.severity === "critical").length;
                        return (
                          <Fragment key={claim.id}>
                            <TableRow data-testid={`claim-row-${claim.id}`}>
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
                                <div className="flex flex-col gap-1">
                                  <Badge className={statusColors[claim.claimStatus] || ""}>
                                    {claim.claimStatus}
                                  </Badge>
                                  {cached && (
                                    <Badge
                                      className={
                                        cached.riskScore >= 80
                                          ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 text-xs"
                                          : cached.riskScore >= 60
                                          ? "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400 text-xs"
                                          : "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400 text-xs"
                                      }
                                      data-testid={`badge-preflight-score-${claim.id}`}
                                    >
                                      <ShieldCheck className="h-2.5 w-2.5 mr-1" />
                                      {cached.riskScore}/100
                                    </Badge>
                                  )}
                                </div>
                              </TableCell>
                              <TableCell className="text-right">
                                <div className="flex items-center justify-end gap-2">
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => handleOpenPreflight(claim)}
                                    data-testid={`button-preflight-${claim.id}`}
                                  >
                                    <ShieldCheck className="h-4 w-4 mr-1" />
                                    Pre-Flight
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => handleExpandDetail(claim.id)}
                                    data-testid={`button-view-claim-${claim.id}`}
                                  >
                                    <ArrowRight className={`h-4 w-4 transition-transform ${isExpanded ? "rotate-90" : ""}`} />
                                  </Button>
                                </div>
                              </TableCell>
                            </TableRow>
                            {isExpanded && (
                              <TableRow key={`detail-${claim.id}`} data-testid={`claim-detail-${claim.id}`}>
                                <TableCell colSpan={7} className="bg-muted/30 p-0">
                                  <div className="p-4 space-y-3">
                                    <div className="flex items-center justify-between">
                                      <p className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Claim Detail</p>
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        onClick={() => handleOpenPreflight(claim)}
                                        data-testid={`button-detail-preflight-${claim.id}`}
                                      >
                                        <Brain className="h-4 w-4 mr-1.5" />
                                        {cached ? "View Pre-Flight Results" : "Run Pre-Flight Check"}
                                      </Button>
                                    </div>
                                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                                      <div>
                                        <p className="text-xs text-muted-foreground">ICD-10 Code</p>
                                        <p className="font-medium">{claim.icd10Code || <span className="text-red-500">Missing</span>}</p>
                                      </div>
                                      <div>
                                        <p className="text-xs text-muted-foreground">Patient ID</p>
                                        <p className="font-medium">{claim.patientId}</p>
                                      </div>
                                      <div>
                                        <p className="text-xs text-muted-foreground">Allowed Amount</p>
                                        <p className="font-medium">{formatCurrency(claim.allowedAmount)}</p>
                                      </div>
                                      <div>
                                        <p className="text-xs text-muted-foreground">Patient Portion</p>
                                        <p className="font-medium">{formatCurrency(claim.patientPortion)}</p>
                                      </div>
                                    </div>
                                    {cached ? (
                                      <div className="flex items-center gap-3 rounded-lg border p-3 bg-background">
                                        <div className={`flex h-10 w-10 items-center justify-center rounded-full shrink-0 ${
                                          cached.riskScore >= 80 ? "bg-green-100 dark:bg-green-900/30" :
                                          cached.riskScore >= 60 ? "bg-yellow-100 dark:bg-yellow-900/30" :
                                          "bg-red-100 dark:bg-red-900/30"
                                        }`}>
                                          <ShieldCheck className={`h-5 w-5 ${
                                            cached.riskScore >= 80 ? "text-green-600" :
                                            cached.riskScore >= 60 ? "text-yellow-600" :
                                            "text-red-600"
                                          }`} />
                                        </div>
                                        <div className="flex-1">
                                          <p className="text-sm font-medium">
                                            Last Pre-Flight: Risk Score {cached.riskScore}/100 · {cached.approvalProbability}% approval probability
                                          </p>
                                          <p className="text-xs text-muted-foreground">
                                            {criticals > 0 ? `${criticals} critical issue${criticals > 1 ? "s" : ""} require attention` : "No critical issues found"} ·
                                            Checked {format(new Date(cached.checkedAt), "MMM d, yyyy")}
                                          </p>
                                        </div>
                                        {cached.riskScore < 70 && (
                                          <Badge className="bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400 shrink-0">
                                            Blocked
                                          </Badge>
                                        )}
                                        {cached.riskScore >= 70 && (
                                          <Badge className="bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 shrink-0">
                                            Cleared
                                          </Badge>
                                        )}
                                      </div>
                                    ) : (
                                      <p className="text-xs text-muted-foreground italic">No pre-flight check has been run for this claim.</p>
                                    )}
                                    {claim.denialReason && (
                                      <div className="rounded-lg border border-red-200 bg-red-50/50 dark:border-red-900 dark:bg-red-950/20 p-3">
                                        <p className="text-xs font-semibold text-red-700 dark:text-red-400 mb-1">Denial Reason</p>
                                        <p className="text-sm">{claim.denialReason}</p>
                                      </div>
                                    )}
                                  </div>
                                </TableCell>
                              </TableRow>
                            )}
                          </Fragment>
                        );
                      })}
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

      {/* New Authorization Dialog */}
      <Dialog open={showAuthDialog} onOpenChange={setShowAuthDialog}>
        <DialogContent data-testid="dialog-new-auth">
          <DialogHeader>
            <DialogTitle>Create Prior Authorization</DialogTitle>
            <DialogDescription>
              Submit a new prior authorization request for a full arch implant case
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 pt-2">
            <div className="space-y-2">
              <Label htmlFor="auth-patient">Patient</Label>
              <Select value={newAuthPatientId} onValueChange={setNewAuthPatientId}>
                <SelectTrigger id="auth-patient" data-testid="select-auth-patient">
                  <SelectValue placeholder="Select patient" />
                </SelectTrigger>
                <SelectContent>
                  {patients?.map((p) => (
                    <SelectItem key={p.id} value={String(p.id)}>
                      {p.firstName} {p.lastName}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="auth-type">Authorization Type</Label>
              <Select value={newAuthType} onValueChange={(v) => setNewAuthType(v as "medical" | "dental")}>
                <SelectTrigger id="auth-type" data-testid="select-auth-type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="medical">Medical Insurance</SelectItem>
                  <SelectItem value="dental">Dental Insurance</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => setShowAuthDialog(false)} data-testid="button-cancel-auth">
                Cancel
              </Button>
              <Button
                onClick={handleCreateAuth}
                disabled={createAuthMutation.isPending}
                data-testid="button-confirm-auth"
              >
                {createAuthMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Create Authorization
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* P2P Dialog */}
      <Dialog open={showP2PDialog} onOpenChange={setShowP2PDialog}>
        <DialogContent data-testid="dialog-p2p">
          <DialogHeader>
            <DialogTitle>Record P2P Outcome</DialogTitle>
            <DialogDescription>
              Document the result of the peer-to-peer review call
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 pt-2">
            <div className="space-y-2">
              <Label htmlFor="p2p-outcome">Outcome</Label>
              <Select value={p2pOutcome} onValueChange={setP2pOutcome}>
                <SelectTrigger id="p2p-outcome" data-testid="select-p2p-outcome">
                  <SelectValue placeholder="Select outcome" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="approved">Approved</SelectItem>
                  <SelectItem value="denied">Denied</SelectItem>
                  <SelectItem value="pending">Pending Further Review</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="p2p-notes">Notes</Label>
              <Textarea
                id="p2p-notes"
                value={p2pNotes}
                onChange={(e) => setP2pNotes(e.target.value)}
                placeholder="Document key points from the call..."
                className="min-h-[100px]"
                data-testid="textarea-p2p-notes"
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowP2PDialog(false)} data-testid="button-cancel-p2p">
                Cancel
              </Button>
              <Button
                onClick={handleP2PSubmit}
                disabled={!p2pOutcome || updateAuthMutation.isPending}
                data-testid="button-confirm-p2p"
              >
                {updateAuthMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Save Outcome
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Pre-Flight Check Dialog */}
      <PreflightDialog
        open={preflightOpen}
        onClose={() => {
          setPreflightOpen(false);
          setPreflightClaim(null);
          setPreflightResult(null);
        }}
        claim={preflightClaim}
        result={preflightResult}
        isLoading={preflightLoading}
        onRunCheck={handleRunPreflight}
        onAutoFix={handleAutoFix}
        isFixing={fixingIssues}
        onSubmitClaim={() => preflightClaim && submitClaimMutation.mutate(preflightClaim.id)}
        isSubmitting={submitClaimMutation.isPending}
      />
    </div>
  );
}
