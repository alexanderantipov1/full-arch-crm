import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "wouter";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
  RefreshCw,
  Send,
  Brain,
} from "lucide-react";
import { format } from "date-fns";
import type { BillingClaim, TreatmentPlan } from "@shared/schema";

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
  approved: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
  paid: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
  denied: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
  appealed: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400",
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

  const { data: stats, isLoading: statsLoading } = useQuery<BillingStats>({
    queryKey: ["/api/billing/stats"],
  });

  const { data: claims, isLoading: claimsLoading } = useQuery<BillingClaim[]>({
    queryKey: ["/api/billing/claims"],
  });

  const { data: pendingAuths, isLoading: authsLoading } = useQuery<TreatmentPlan[]>({
    queryKey: ["/api/treatment-plans", { priorAuthStatus: "pending" }],
  });

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
          <TabsTrigger value="prior-auth" data-testid="tab-prior-auth">Prior Authorizations</TabsTrigger>
          <TabsTrigger value="denials" data-testid="tab-denials">Denials & Appeals</TabsTrigger>
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
                            <Button variant="ghost" size="sm">
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
          <Card>
            <CardHeader>
              <CardTitle>Prior Authorization Requests</CardTitle>
              <CardDescription>
                Track and manage insurance pre-authorizations for full arch implant cases
              </CardDescription>
            </CardHeader>
            <CardContent>
              {authsLoading ? (
                <div className="space-y-3">
                  {[1, 2, 3].map((i) => (
                    <Skeleton key={i} className="h-20 w-full" />
                  ))}
                </div>
              ) : pendingAuths && pendingAuths.length > 0 ? (
                <div className="space-y-4">
                  {pendingAuths.map((plan) => (
                    <div
                      key={plan.id}
                      className="flex items-center justify-between rounded-lg border p-4 hover-elevate"
                    >
                      <div className="flex items-center gap-4">
                        <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-yellow-100 dark:bg-yellow-900/30">
                          <Clock className="h-6 w-6 text-yellow-600" />
                        </div>
                        <div>
                          <p className="font-medium">{plan.planName}</p>
                          <p className="text-sm text-muted-foreground">
                            {plan.diagnosis} - Est. {formatCurrency(plan.totalCost)}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <Badge variant="outline">
                          <AlertCircle className="mr-1 h-3 w-3" />
                          Auth Pending
                        </Badge>
                        <Button size="sm">Submit Auth</Button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <CheckCircle2 className="mb-3 h-10 w-10 text-green-500" />
                  <h3 className="text-lg font-semibold">All caught up!</h3>
                  <p className="text-sm text-muted-foreground">
                    No pending prior authorizations
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="denials" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Claim Denials</CardTitle>
                  <CardDescription>
                    Review denied claims and use AI to generate appeals
                  </CardDescription>
                </div>
                <Button variant="outline">
                  <Brain className="mr-2 h-4 w-4" />
                  AI Auto-Appeal
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-100 dark:bg-green-900/30">
                  <CheckCircle2 className="h-8 w-8 text-green-600" />
                </div>
                <h3 className="mb-2 text-lg font-semibold">No denied claims</h3>
                <p className="max-w-sm text-sm text-muted-foreground">
                  All your claims are either approved, pending, or paid
                </p>
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
    </div>
  );
}
