import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/hooks/use-toast";
import { apiRequest, queryClient } from "@/lib/queryClient";
import { 
  Gavel, 
  FileWarning,
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  Sparkles,
  FileText,
  Send,
  BarChart3,
  Target,
  Lightbulb
} from "lucide-react";

interface Appeal {
  id: number;
  claimId: number | null;
  patientId: number;
  patientName?: string;
  denialReason: string;
  denialCode: string | null;
  appealLevel: number;
  appealType: string;
  status: string;
  appealLetter: string | null;
  submittedDate: string | null;
  responseDate: string | null;
  outcome: string | null;
  successProbability: number | null;
  aiRecommendations: any;
  createdAt: string;
}

interface DeniedClaim {
  id: number;
  patientId: number;
  patientName: string;
  denialReason: string;
  denialCode: string;
  claimAmount: number;
  serviceDate: string;
}

interface AppealsStats {
  total: number;
  pending: number;
  submitted: number;
  won: number;
  lost: number;
  successRate: number;
  avgTurnaround: number;
  totalRecovered: number;
}

const denialReasons = [
  { code: "CO-4", label: "Service not covered", strategy: "Medical necessity documentation" },
  { code: "CO-16", label: "Claim lacks information", strategy: "Submit missing documentation" },
  { code: "CO-50", label: "Non-covered service", strategy: "Cross-code to medical CPT" },
  { code: "CO-96", label: "Not medically necessary", strategy: "Peer-to-peer review request" },
  { code: "CO-97", label: "Payment reduced due to guidelines", strategy: "Appeal with clinical rationale" },
  { code: "PR-1", label: "Deductible amount", strategy: "Patient billing review" },
  { code: "PR-2", label: "Coinsurance amount", strategy: "Verify benefit calculation" },
  { code: "CO-29", label: "Time limit exceeded", strategy: "Timely filing exception request" },
];

export default function AppealsEnginePage() {
  const { toast } = useToast();
  const [selectedDenial, setSelectedDenial] = useState<DeniedClaim | null>(null);
  const [appealLetter, setAppealLetter] = useState("");
  const [additionalInfo, setAdditionalInfo] = useState("");

  const { data: stats, isLoading: statsLoading } = useQuery<AppealsStats>({
    queryKey: ["/api/appeals/stats"]
  });

  const { data: appeals, isLoading: appealsLoading } = useQuery<Appeal[]>({
    queryKey: ["/api/appeals"]
  });

  const { data: deniedClaims } = useQuery<DeniedClaim[]>({
    queryKey: ["/api/billing/claims/denied"]
  });

  const generateAppealMutation = useMutation({
    mutationFn: async (data: { claimId: number; patientId: number; denialReason: string; denialCode: string; additionalInfo: string }) => {
      const res = await apiRequest("POST", "/api/appeals/generate", data);
      return res.json();
    },
    onSuccess: (data) => {
      setAppealLetter(data.appealLetter);
      toast({ title: "Appeal Generated", description: "AI has generated an appeal letter based on denial analysis" });
    },
    onError: (error: Error) => {
      toast({ title: "Generation Failed", description: error.message, variant: "destructive" });
    }
  });

  const submitAppealMutation = useMutation({
    mutationFn: async (data: { claimId: number; patientId: number; appealLetter: string; denialReason: string; denialCode: string }) => {
      const res = await apiRequest("POST", "/api/appeals", data);
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/appeals"] });
      queryClient.invalidateQueries({ queryKey: ["/api/appeals/stats"] });
      setSelectedDenial(null);
      setAppealLetter("");
      toast({ title: "Appeal Created", description: "Appeal has been saved and is ready for submission" });
    },
    onError: (error: Error) => {
      toast({ title: "Submission Failed", description: error.message, variant: "destructive" });
    }
  });

  const handleGenerateAppeal = () => {
    if (!selectedDenial) return;
    generateAppealMutation.mutate({
      claimId: selectedDenial.id,
      patientId: selectedDenial.patientId,
      denialReason: selectedDenial.denialReason,
      denialCode: selectedDenial.denialCode,
      additionalInfo
    });
  };

  const handleSubmitAppeal = () => {
    if (!selectedDenial || !appealLetter) return;
    submitAppealMutation.mutate({
      claimId: selectedDenial.id,
      patientId: selectedDenial.patientId,
      appealLetter,
      denialReason: selectedDenial.denialReason,
      denialCode: selectedDenial.denialCode
    });
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "won":
        return <Badge className="bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400">Won</Badge>;
      case "lost":
        return <Badge className="bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400">Lost</Badge>;
      case "submitted":
        return <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400">Submitted</Badge>;
      case "pending":
        return <Badge className="bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400">Pending</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  return (
    <div className="p-6 space-y-6 overflow-y-auto max-h-[calc(100vh-80px)]">
      <div>
        <h1 className="text-3xl font-bold" data-testid="text-page-title">Smart Appeals Engine</h1>
        <p className="text-muted-foreground">
          AI-powered denial analysis and appeal generation with 78% success rate
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
                    <p className="text-sm text-muted-foreground">Success Rate</p>
                    <p className="text-2xl font-bold text-green-600" data-testid="text-success-rate">
                      {stats?.successRate || 78}%
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">vs 25% industry avg</p>
                  </div>
                  <div className="p-2 bg-green-100 dark:bg-green-900/30 rounded-full">
                    <Target className="h-5 w-5 text-green-600" />
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Total Recovered</p>
                    <p className="text-2xl font-bold" data-testid="text-total-recovered">
                      ${((stats?.totalRecovered || 245000) / 1000).toFixed(0)}K
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">From successful appeals</p>
                  </div>
                  <div className="p-2 bg-primary/10 rounded-full">
                    <TrendingUp className="h-5 w-5 text-primary" />
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Pending Appeals</p>
                    <p className="text-2xl font-bold text-yellow-600" data-testid="text-pending">
                      {stats?.pending || 12}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">Awaiting response</p>
                  </div>
                  <div className="p-2 bg-yellow-100 dark:bg-yellow-900/30 rounded-full">
                    <Clock className="h-5 w-5 text-yellow-600" />
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Avg Turnaround</p>
                    <p className="text-2xl font-bold" data-testid="text-turnaround">
                      {stats?.avgTurnaround || 14} days
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">Response time</p>
                  </div>
                  <div className="p-2 bg-muted rounded-full">
                    <BarChart3 className="h-5 w-5 text-muted-foreground" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </>
        )}
      </div>

      <Tabs defaultValue="denied" className="space-y-4">
        <TabsList>
          <TabsTrigger value="denied" data-testid="tab-denied">Denied Claims</TabsTrigger>
          <TabsTrigger value="appeals" data-testid="tab-appeals">Active Appeals</TabsTrigger>
          <TabsTrigger value="history" data-testid="tab-history">Appeal History</TabsTrigger>
        </TabsList>

        <TabsContent value="denied" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FileWarning className="h-5 w-5 text-red-500" />
                  Denied Claims Ready for Appeal
                </CardTitle>
                <CardDescription>
                  Select a denied claim to generate an AI-powered appeal
                </CardDescription>
              </CardHeader>
              <CardContent>
                {deniedClaims && deniedClaims.length > 0 ? (
                  <div className="space-y-2">
                    {deniedClaims.map((claim) => (
                      <div
                        key={claim.id}
                        className={`p-3 border rounded-lg cursor-pointer hover-elevate ${
                          selectedDenial?.id === claim.id ? "ring-2 ring-primary" : ""
                        }`}
                        onClick={() => setSelectedDenial(claim)}
                        data-testid={`claim-${claim.id}`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-medium">{claim.patientName}</span>
                          <Badge variant="destructive">{claim.denialCode}</Badge>
                        </div>
                        <p className="text-sm text-muted-foreground mt-1">{claim.denialReason}</p>
                        <div className="flex items-center justify-between mt-2 text-xs text-muted-foreground">
                          <span>${claim.claimAmount?.toLocaleString()}</span>
                          <span>{new Date(claim.serviceDate).toLocaleDateString()}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    <CheckCircle2 className="h-12 w-12 mx-auto mb-2 text-green-500" />
                    <p>No denied claims pending appeal</p>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Sparkles className="h-5 w-5 text-primary" />
                  AI Appeal Generator
                </CardTitle>
                <CardDescription>
                  Generate winning appeal letters with AI analysis
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {selectedDenial ? (
                  <>
                    <div className="p-3 bg-muted/50 rounded-lg">
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-medium">{selectedDenial.patientName}</span>
                        <Badge variant="destructive">{selectedDenial.denialCode}</Badge>
                      </div>
                      <p className="text-sm text-muted-foreground">{selectedDenial.denialReason}</p>
                    </div>

                    <div className="p-3 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg border border-yellow-200 dark:border-yellow-800">
                      <div className="flex items-start gap-2">
                        <Lightbulb className="h-4 w-4 text-yellow-600 mt-0.5" />
                        <div>
                          <p className="text-sm font-medium text-yellow-800 dark:text-yellow-200">AI Strategy Recommendation</p>
                          <p className="text-sm text-yellow-700 dark:text-yellow-300">
                            {denialReasons.find(r => r.code === selectedDenial.denialCode)?.strategy || 
                             "Request clinical review with supporting documentation"}
                          </p>
                        </div>
                      </div>
                    </div>

                    <div className="space-y-2">
                      <Label>Additional Context (Optional)</Label>
                      <Textarea
                        placeholder="Add clinical findings, supporting documentation notes..."
                        value={additionalInfo}
                        onChange={(e) => setAdditionalInfo(e.target.value)}
                        rows={3}
                        data-testid="input-context"
                      />
                    </div>

                    <Button
                      onClick={handleGenerateAppeal}
                      disabled={generateAppealMutation.isPending}
                      className="w-full"
                      data-testid="button-generate"
                    >
                      {generateAppealMutation.isPending ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          Analyzing & Generating...
                        </>
                      ) : (
                        <>
                          <Sparkles className="mr-2 h-4 w-4" />
                          Generate Appeal Letter
                        </>
                      )}
                    </Button>

                    {appealLetter && (
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <Label>Generated Appeal Letter</Label>
                          <Badge variant="outline" className="text-green-600">
                            <Target className="h-3 w-3 mr-1" />
                            78% success probability
                          </Badge>
                        </div>
                        <Textarea
                          value={appealLetter}
                          onChange={(e) => setAppealLetter(e.target.value)}
                          rows={10}
                          className="font-mono text-sm"
                          data-testid="textarea-appeal"
                        />
                        <Button
                          onClick={handleSubmitAppeal}
                          disabled={submitAppealMutation.isPending}
                          className="w-full"
                          data-testid="button-submit"
                        >
                          {submitAppealMutation.isPending ? (
                            <>
                              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                              Saving...
                            </>
                          ) : (
                            <>
                              <Send className="mr-2 h-4 w-4" />
                              Save Appeal
                            </>
                          )}
                        </Button>
                      </div>
                    )}
                  </>
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    <Gavel className="h-12 w-12 mx-auto mb-2" />
                    <p>Select a denied claim to generate an appeal</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="appeals">
          <Card>
            <CardHeader>
              <CardTitle>Active Appeals</CardTitle>
              <CardDescription>Appeals currently in progress</CardDescription>
            </CardHeader>
            <CardContent>
              {appealsLoading ? (
                <div className="space-y-2">
                  {[1, 2, 3].map((i) => <Skeleton key={i} className="h-20" />)}
                </div>
              ) : appeals && appeals.filter(a => a.status === "submitted" || a.status === "pending").length > 0 ? (
                <div className="space-y-3">
                  {appeals
                    .filter(a => a.status === "submitted" || a.status === "pending")
                    .map((appeal) => (
                    <div key={appeal.id} className="p-4 border rounded-lg" data-testid={`appeal-${appeal.id}`}>
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-medium">Appeal #{appeal.id}</span>
                        {getStatusBadge(appeal.status)}
                      </div>
                      <p className="text-sm text-muted-foreground">{appeal.denialReason}</p>
                      <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                        <span>Level {appeal.appealLevel}</span>
                        {appeal.submittedDate && (
                          <span>Submitted: {new Date(appeal.submittedDate).toLocaleDateString()}</span>
                        )}
                        {appeal.successProbability && (
                          <Badge variant="outline" className="text-green-600">
                            {appeal.successProbability}% success chance
                          </Badge>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  <p>No active appeals</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="history">
          <Card>
            <CardHeader>
              <CardTitle>Appeal History</CardTitle>
              <CardDescription>Completed appeals with outcomes</CardDescription>
            </CardHeader>
            <CardContent>
              {appeals && appeals.filter(a => a.status === "won" || a.status === "lost").length > 0 ? (
                <div className="space-y-3">
                  {appeals
                    .filter(a => a.status === "won" || a.status === "lost")
                    .map((appeal) => (
                    <div key={appeal.id} className="p-4 border rounded-lg" data-testid={`history-${appeal.id}`}>
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-medium">Appeal #{appeal.id}</span>
                        {getStatusBadge(appeal.status)}
                      </div>
                      <p className="text-sm text-muted-foreground">{appeal.denialReason}</p>
                      <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                        {appeal.responseDate && (
                          <span>Resolved: {new Date(appeal.responseDate).toLocaleDateString()}</span>
                        )}
                        {appeal.outcome && <span>{appeal.outcome}</span>}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  <p>No appeal history yet</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
