import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/hooks/use-toast";
import { apiRequest, queryClient } from "@/lib/queryClient";
import { 
  DollarSign, 
  FileCheck,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  ArrowRight,
  TrendingUp,
  Receipt,
  Zap,
  RefreshCw,
  Download,
} from "lucide-react";
import { exportToCSV } from "@/lib/export";

interface PaymentPosting {
  id: number;
  claimId: number | null;
  patientId: number | null;
  patientName?: string;
  paymentDate: string;
  payerName: string;
  checkNumber: string | null;
  paymentAmount: string;
  adjustmentAmount: string | null;
  patientResponsibility: string | null;
  postingStatus: string;
  varianceFlag: boolean;
  varianceReason: string | null;
  autoPosted: boolean;
}

interface ERAStats {
  pendingCount: number;
  postedToday: number;
  totalPosted: number;
  varianceCount: number;
  autoPostRate: number;
  avgProcessingTime: string;
}

interface UnmatchedERA {
  id: number;
  payerName: string;
  checkNumber: string;
  totalAmount: number;
  receivedDate: string;
  lineItems: number;
}

export default function ERAProcessingPage() {
  const { toast } = useToast();
  const [selectedPosting, setSelectedPosting] = useState<PaymentPosting | null>(null);

  const { data: stats, isLoading: statsLoading } = useQuery<ERAStats>({
    queryKey: ["/api/era/stats"]
  });

  const { data: pendingPostings, isLoading: postingsLoading } = useQuery<PaymentPosting[]>({
    queryKey: ["/api/era/pending"]
  });

  const { data: recentPostings } = useQuery<PaymentPosting[]>({
    queryKey: ["/api/era/recent"]
  });

  const { data: variancePostings } = useQuery<PaymentPosting[]>({
    queryKey: ["/api/era/variances"]
  });

  const autoPostMutation = useMutation({
    mutationFn: async (postingId: number) => {
      const res = await apiRequest("POST", `/api/era/${postingId}/post`, {});
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/era/pending"] });
      queryClient.invalidateQueries({ queryKey: ["/api/era/recent"] });
      queryClient.invalidateQueries({ queryKey: ["/api/era/stats"] });
      queryClient.invalidateQueries({ queryKey: ["/api/era/variances"] });
      toast({ title: "Payment Posted", description: "Payment has been automatically posted to the account" });
    },
    onError: (error: Error) => {
      toast({ title: "Posting Failed", description: error.message, variant: "destructive" });
    }
  });

  const autoPostAllMutation = useMutation({
    mutationFn: async () => {
      const res = await apiRequest("POST", "/api/era/auto-post-all", {});
      return res.json();
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["/api/era/pending"] });
      queryClient.invalidateQueries({ queryKey: ["/api/era/recent"] });
      queryClient.invalidateQueries({ queryKey: ["/api/era/stats"] });
      queryClient.invalidateQueries({ queryKey: ["/api/era/variances"] });
      toast({ title: "Batch Posted", description: `${data.posted} payments posted automatically` });
    },
    onError: (error: Error) => {
      toast({ title: "Batch Posting Failed", description: error.message, variant: "destructive" });
    }
  });

  const formatCurrency = (amount: string | number) => {
    const num = typeof amount === "string" ? parseFloat(amount) : amount;
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD"
    }).format(num);
  };

  return (
    <div className="p-6 space-y-6 overflow-y-auto max-h-[calc(100vh-80px)]">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold" data-testid="text-page-title">ERA Processing</h1>
          <p className="text-muted-foreground">
            Automated payment posting with variance detection
          </p>
        </div>
        <Button
          variant="outline"
          onClick={() => {
            const allPostings = [
              ...(pendingPostings ?? []),
              ...(recentPostings ?? []),
              ...(variancePostings ?? []),
            ];
            const rows = allPostings.map((p) => ({
              ID: p.id,
              "Payer Name": p.payerName,
              "Check #": p.checkNumber ?? "",
              "Patient Name": p.patientName ?? "",
              "Payment Date": new Date(p.paymentDate).toLocaleDateString(),
              "Payment Amount ($)": p.paymentAmount,
              "Adjustment Amount ($)": p.adjustmentAmount ?? "",
              "Patient Responsibility ($)": p.patientResponsibility ?? "",
              "Posting Status": p.postingStatus,
              "Auto Posted": p.autoPosted ? "Yes" : "No",
              Variance: p.varianceFlag ? "Yes" : "No",
              "Variance Reason": p.varianceReason ?? "",
            }));
            exportToCSV(rows, "ERA");
          }}
          data-testid="button-export-era-csv"
        >
          <Download className="mr-2 h-4 w-4" />
          Export CSV
        </Button>
        <Button 
          onClick={() => autoPostAllMutation.mutate()}
          disabled={autoPostAllMutation.isPending}
          data-testid="button-auto-post-all"
        >
          {autoPostAllMutation.isPending ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Processing...
            </>
          ) : (
            <>
              <Zap className="mr-2 h-4 w-4" />
              Auto-Post All
            </>
          )}
        </Button>
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
                    <p className="text-sm text-muted-foreground">Pending Postings</p>
                    <p className="text-2xl font-bold text-yellow-600" data-testid="text-pending">
                      {stats?.pendingCount || 0}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">Ready to post</p>
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
                    <p className="text-sm text-muted-foreground">Posted Today</p>
                    <p className="text-2xl font-bold text-green-600" data-testid="text-posted-today">
                      {stats?.postedToday || 0}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">Successful postings</p>
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
                    <p className="text-sm text-muted-foreground">Auto-Post Rate</p>
                    <p className="text-2xl font-bold" data-testid="text-auto-rate">
                      {stats?.autoPostRate || 94}%
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">Automation success</p>
                  </div>
                  <div className="p-2 bg-primary/10 rounded-full">
                    <Zap className="h-5 w-5 text-primary" />
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Variances</p>
                    <p className="text-2xl font-bold text-red-600" data-testid="text-variances">
                      {stats?.varianceCount || 0}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">Require review</p>
                  </div>
                  <div className="p-2 bg-red-100 dark:bg-red-900/30 rounded-full">
                    <AlertTriangle className="h-5 w-5 text-red-600" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </>
        )}
      </div>

      <Tabs defaultValue="pending" className="space-y-4">
        <TabsList>
          <TabsTrigger value="pending" data-testid="tab-pending">
            Pending ({pendingPostings?.length || 0})
          </TabsTrigger>
          <TabsTrigger value="variances" data-testid="tab-variances">
            Variances ({variancePostings?.length || 0})
          </TabsTrigger>
          <TabsTrigger value="recent" data-testid="tab-recent">
            Recent Postings
          </TabsTrigger>
        </TabsList>

        <TabsContent value="pending">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Receipt className="h-5 w-5" />
                Pending Payment Postings
              </CardTitle>
              <CardDescription>
                Payments ready for automatic or manual posting
              </CardDescription>
            </CardHeader>
            <CardContent>
              {postingsLoading ? (
                <div className="space-y-2">
                  {[1, 2, 3].map((i) => <Skeleton key={i} className="h-20" />)}
                </div>
              ) : pendingPostings && pendingPostings.length > 0 ? (
                <div className="space-y-3">
                  {pendingPostings.map((posting) => (
                    <div 
                      key={posting.id} 
                      className="p-4 border rounded-lg flex items-center justify-between"
                      data-testid={`posting-${posting.id}`}
                    >
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-medium">{posting.payerName}</span>
                          {posting.checkNumber && (
                            <Badge variant="outline">Check #{posting.checkNumber}</Badge>
                          )}
                        </div>
                        <div className="flex items-center gap-4 text-sm text-muted-foreground">
                          <span>{posting.patientName}</span>
                          <span>{new Date(posting.paymentDate).toLocaleDateString()}</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                        <div className="text-right">
                          <p className="font-bold text-green-600">{formatCurrency(posting.paymentAmount)}</p>
                          {posting.adjustmentAmount && parseFloat(posting.adjustmentAmount) > 0 && (
                            <p className="text-xs text-muted-foreground">
                              Adj: {formatCurrency(posting.adjustmentAmount)}
                            </p>
                          )}
                        </div>
                        <Button
                          size="sm"
                          onClick={() => autoPostMutation.mutate(posting.id)}
                          disabled={autoPostMutation.isPending}
                          data-testid={`button-post-${posting.id}`}
                        >
                          {autoPostMutation.isPending ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <>
                              <CheckCircle2 className="h-4 w-4 mr-1" />
                              Post
                            </>
                          )}
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  <CheckCircle2 className="h-12 w-12 mx-auto mb-2 text-green-500" />
                  <p>All payments have been posted</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="variances">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-red-500" />
                Payment Variances
              </CardTitle>
              <CardDescription>
                Payments with discrepancies requiring manual review
              </CardDescription>
            </CardHeader>
            <CardContent>
              {variancePostings && variancePostings.length > 0 ? (
                <div className="space-y-3">
                  {variancePostings.map((posting) => (
                    <div 
                      key={posting.id} 
                      className="p-4 border border-red-200 dark:border-red-800 rounded-lg bg-red-50/50 dark:bg-red-900/10"
                      data-testid={`variance-${posting.id}`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{posting.payerName}</span>
                          <Badge variant="destructive">Variance</Badge>
                        </div>
                        <span className="font-bold">{formatCurrency(posting.paymentAmount)}</span>
                      </div>
                      <p className="text-sm text-red-600 dark:text-red-400 mb-2">
                        {posting.varianceReason || "Payment amount differs from expected"}
                      </p>
                      <div className="flex items-center gap-2">
                        <Button size="sm" variant="outline" data-testid={`button-review-${posting.id}`}>
                          Review
                        </Button>
                        <Button size="sm" variant="outline" data-testid={`button-override-${posting.id}`}>
                          Override & Post
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  <CheckCircle2 className="h-12 w-12 mx-auto mb-2 text-green-500" />
                  <p>No variances detected</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="recent">
          <Card>
            <CardHeader>
              <CardTitle>Recent Postings</CardTitle>
              <CardDescription>Successfully posted payments</CardDescription>
            </CardHeader>
            <CardContent>
              {recentPostings && recentPostings.length > 0 ? (
                <div className="space-y-3">
                  {recentPostings.map((posting) => (
                    <div 
                      key={posting.id} 
                      className="p-4 border rounded-lg flex items-center justify-between"
                      data-testid={`recent-${posting.id}`}
                    >
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-medium">{posting.payerName}</span>
                          <Badge className="bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400">
                            Posted
                          </Badge>
                          {posting.autoPosted && (
                            <Badge variant="outline" className="text-xs">
                              <Zap className="h-3 w-3 mr-1" />
                              Auto
                            </Badge>
                          )}
                        </div>
                        <div className="flex items-center gap-4 text-sm text-muted-foreground">
                          <span>{posting.patientName}</span>
                          <span>{new Date(posting.paymentDate).toLocaleDateString()}</span>
                        </div>
                      </div>
                      <p className="font-bold text-green-600">{formatCurrency(posting.paymentAmount)}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  <p>No recent postings</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
