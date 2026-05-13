import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DollarSign, TrendingUp, CreditCard, Search, Plus, Calendar, CheckCircle, Clock, AlertCircle, ArrowUpRight, ArrowDownRight } from "lucide-react";
import { format, subDays } from "date-fns";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { useToast } from "@/hooks/use-toast";
import { apiRequest, queryClient } from "@/lib/queryClient";
import type { Patient, PaymentPosting, BillingClaim } from "@shared/schema";
import { PaymentModal } from "@/components/PaymentModal";

const paymentFormSchema = z.object({
  patientId: z.string().min(1, "Patient is required"),
  claimId: z.string().optional(),
  paymentDate: z.string().min(1, "Payment date is required"),
  paymentAmount: z.string().min(1, "Amount is required"),
  paymentMethod: z.string().min(1, "Payment method is required"),
  checkNumber: z.string().optional(),
  notes: z.string().optional(),
});

type PaymentFormData = z.infer<typeof paymentFormSchema>;

export default function PaymentsPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [dateFilter, setDateFilter] = useState("30");
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isPatientSelectOpen, setIsPatientSelectOpen] = useState(false);
  const [selectedPatientForCard, setSelectedPatientForCard] = useState<Patient | null>(null);
  const [patientPickerId, setPatientPickerId] = useState("");
  const { toast } = useToast();

  const { data: patients = [] } = useQuery<Patient[]>({
    queryKey: ["/api/patients"],
  });

  const { data: payments = [], isLoading } = useQuery<PaymentPosting[]>({
    queryKey: ["/api/era/postings"],
  });

  const { data: claims = [] } = useQuery<BillingClaim[]>({
    queryKey: ["/api/billing/claims"],
  });

  const form = useForm<PaymentFormData>({
    resolver: zodResolver(paymentFormSchema),
    defaultValues: {
      patientId: "",
      claimId: "",
      paymentDate: format(new Date(), "yyyy-MM-dd"),
      paymentAmount: "",
      paymentMethod: "",
      checkNumber: "",
      notes: "",
    },
  });

  const createPaymentMutation = useMutation({
    mutationFn: async (data: PaymentFormData) => {
      return apiRequest("/api/era/postings", {
        method: "POST",
        body: JSON.stringify({
          patientId: parseInt(data.patientId),
          claimId: data.claimId ? parseInt(data.claimId) : null,
          paymentDate: data.paymentDate,
          paymentAmount: data.paymentAmount,
          payerName: data.paymentMethod === "insurance" ? "Insurance" : "Patient",
          checkNumber: data.checkNumber || null,
          status: "posted",
        }),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/era/postings"] });
      toast({ title: "Payment recorded successfully" });
      setIsDialogOpen(false);
      form.reset();
    },
    onError: () => {
      toast({ title: "Failed to record payment", variant: "destructive" });
    },
  });

  const onSubmit = (data: PaymentFormData) => {
    createPaymentMutation.mutate(data);
  };

  const getPatientName = (patientId: number) => {
    const patient = patients.find((p) => p.id === patientId);
    return patient ? `${patient.firstName} ${patient.lastName}` : "Unknown";
  };

  // Calculate metrics
  const now = new Date();
  const filterDays = parseInt(dateFilter);
  const startDate = subDays(now, filterDays);
  
  const filteredPayments = payments.filter((p) => {
    const paymentDate = new Date(p.paymentDate);
    return paymentDate >= startDate;
  });

  const totalCollected = filteredPayments.reduce((sum, p) => sum + parseFloat(p.paymentAmount || "0"), 0);
  const insurancePayments = filteredPayments.filter(p => p.payerName?.toLowerCase().includes("insurance"));
  const patientPayments = filteredPayments.filter(p => !p.payerName?.toLowerCase().includes("insurance"));
  const insuranceTotal = insurancePayments.reduce((sum, p) => sum + parseFloat(p.paymentAmount || "0"), 0);
  const patientTotal = patientPayments.reduce((sum, p) => sum + parseFloat(p.paymentAmount || "0"), 0);

  // Previous period comparison
  const prevStartDate = subDays(startDate, filterDays);
  const prevPayments = payments.filter((p) => {
    const paymentDate = new Date(p.paymentDate);
    return paymentDate >= prevStartDate && paymentDate < startDate;
  });
  const prevTotal = prevPayments.reduce((sum, p) => sum + parseFloat(p.paymentAmount || "0"), 0);
  const percentChange = prevTotal > 0 ? ((totalCollected - prevTotal) / prevTotal) * 100 : 0;

  const searchFilteredPayments = filteredPayments.filter((payment) => {
    const patientName = getPatientName(payment.patientId);
    return (
      patientName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      payment.checkNumber?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      payment.payerName?.toLowerCase().includes(searchQuery.toLowerCase())
    );
  });

  return (
    <div className="flex-1 overflow-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-2" data-testid="text-page-title">
            <DollarSign className="h-8 w-8 text-primary" />
            Payment Tracking
          </h1>
          <p className="text-muted-foreground">Monitor collections and record patient payments</p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => { setPatientPickerId(""); setIsPatientSelectOpen(true); }}
            data-testid="button-collect-card-payment"
          >
            <CreditCard className="h-4 w-4 mr-2" />
            Collect Card Payment
          </Button>
        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
          <DialogTrigger asChild>
            <Button data-testid="button-record-payment">
              <Plus className="h-4 w-4 mr-2" />
              Record Payment
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Record Payment</DialogTitle>
              <DialogDescription>Enter payment details to record a new payment</DialogDescription>
            </DialogHeader>
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                <FormField
                  control={form.control}
                  name="patientId"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Patient</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl>
                          <SelectTrigger data-testid="select-patient">
                            <SelectValue placeholder="Select patient" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {patients.map((patient) => (
                            <SelectItem key={patient.id} value={patient.id.toString()}>
                              {patient.firstName} {patient.lastName}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <div className="grid grid-cols-2 gap-4">
                  <FormField
                    control={form.control}
                    name="paymentDate"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Payment Date</FormLabel>
                        <FormControl>
                          <Input type="date" {...field} data-testid="input-date" />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="paymentAmount"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Amount ($)</FormLabel>
                        <FormControl>
                          <Input type="number" step="0.01" placeholder="0.00" {...field} data-testid="input-amount" />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
                <FormField
                  control={form.control}
                  name="paymentMethod"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Payment Type</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl>
                          <SelectTrigger data-testid="select-method">
                            <SelectValue placeholder="Select type" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value="cash">Cash</SelectItem>
                          <SelectItem value="check">Check</SelectItem>
                          <SelectItem value="credit">Credit Card</SelectItem>
                          <SelectItem value="debit">Debit Card</SelectItem>
                          <SelectItem value="insurance">Insurance Payment</SelectItem>
                          <SelectItem value="financing">Financing</SelectItem>
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="checkNumber"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Check/Reference Number (Optional)</FormLabel>
                      <FormControl>
                        <Input placeholder="Check or reference number" {...field} data-testid="input-reference" />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <DialogFooter>
                  <Button type="submit" disabled={createPaymentMutation.isPending} data-testid="button-submit-payment">
                    {createPaymentMutation.isPending ? "Recording..." : "Record Payment"}
                  </Button>
                </DialogFooter>
              </form>
            </Form>
          </DialogContent>
        </Dialog>
        </div>
      </div>

      {/* Patient Select Dialog for Card Payment */}
      <Dialog open={isPatientSelectOpen} onOpenChange={setIsPatientSelectOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Select Patient</DialogTitle>
            <DialogDescription>Choose the patient to collect a card payment from</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <Select value={patientPickerId} onValueChange={setPatientPickerId}>
              <SelectTrigger data-testid="select-patient-for-card">
                <SelectValue placeholder="Search patients…" />
              </SelectTrigger>
              <SelectContent>
                {patients.map(p => (
                  <SelectItem key={p.id} value={String(p.id)}>
                    {p.firstName} {p.lastName}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <div className="flex gap-2">
              <Button variant="outline" className="flex-1" onClick={() => setIsPatientSelectOpen(false)}>
                Cancel
              </Button>
              <Button
                className="flex-1"
                disabled={!patientPickerId}
                onClick={() => {
                  const pt = patients.find(p => String(p.id) === patientPickerId) ?? null;
                  setSelectedPatientForCard(pt);
                  setIsPatientSelectOpen(false);
                }}
                data-testid="button-open-card-modal"
              >
                Continue
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Stripe Card Payment Modal */}
      {selectedPatientForCard && (
        <PaymentModal
          open={!!selectedPatientForCard}
          onClose={() => setSelectedPatientForCard(null)}
          patientId={selectedPatientForCard.id}
          patientName={`${selectedPatientForCard.firstName} ${selectedPatientForCard.lastName}`}
          receiptEmail={selectedPatientForCard.email || undefined}
        />
      )}

      {/* Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Total Collected</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold" data-testid="stat-total">
              ${totalCollected.toLocaleString("en-US", { minimumFractionDigits: 2 })}
            </div>
            <div className="flex items-center text-xs text-muted-foreground">
              {percentChange >= 0 ? (
                <ArrowUpRight className="h-3 w-3 text-green-500 mr-1" />
              ) : (
                <ArrowDownRight className="h-3 w-3 text-red-500 mr-1" />
              )}
              <span className={percentChange >= 0 ? "text-green-500" : "text-red-500"}>
                {Math.abs(percentChange).toFixed(1)}%
              </span>
              <span className="ml-1">vs previous period</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Insurance Payments</CardTitle>
            <CheckCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600" data-testid="stat-insurance">
              ${insuranceTotal.toLocaleString("en-US", { minimumFractionDigits: 2 })}
            </div>
            <p className="text-xs text-muted-foreground">{insurancePayments.length} payments</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Patient Payments</CardTitle>
            <CreditCard className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600" data-testid="stat-patient">
              ${patientTotal.toLocaleString("en-US", { minimumFractionDigits: 2 })}
            </div>
            <p className="text-xs text-muted-foreground">{patientPayments.length} payments</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Avg Payment</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold" data-testid="stat-avg">
              ${filteredPayments.length > 0 ? (totalCollected / filteredPayments.length).toLocaleString("en-US", { minimumFractionDigits: 2 }) : "0.00"}
            </div>
            <p className="text-xs text-muted-foreground">{filteredPayments.length} total payments</p>
          </CardContent>
        </Card>
      </div>

      {/* Payment History */}
      <Card>
        <CardHeader>
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <CardTitle>Payment History</CardTitle>
              <CardDescription>All recorded payments and collections</CardDescription>
            </div>
            <div className="flex gap-2">
              <div className="relative">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search payments..."
                  className="pl-8 w-48"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  data-testid="input-search"
                />
              </div>
              <Select value={dateFilter} onValueChange={setDateFilter}>
                <SelectTrigger className="w-32" data-testid="filter-date">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="7">Last 7 days</SelectItem>
                  <SelectItem value="30">Last 30 days</SelectItem>
                  <SelectItem value="90">Last 90 days</SelectItem>
                  <SelectItem value="365">Last year</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-center py-8 text-muted-foreground">Loading payments...</p>
          ) : searchFilteredPayments.length === 0 ? (
            <div className="text-center py-12">
              <DollarSign className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium mb-2">No Payments Found</h3>
              <p className="text-muted-foreground mb-4">Record your first payment to start tracking</p>
              <Button onClick={() => setIsDialogOpen(true)} data-testid="button-add-first">
                <Plus className="h-4 w-4 mr-2" />
                Record Payment
              </Button>
            </div>
          ) : (
            <div className="space-y-2">
              {searchFilteredPayments.map((payment) => (
                <div
                  key={payment.id}
                  className="flex items-center justify-between p-4 border rounded-lg hover-elevate"
                  data-testid={`payment-row-${payment.id}`}
                >
                  <div className="flex items-center gap-4">
                    <div className="p-2 rounded-full bg-green-100 dark:bg-green-900/30">
                      <DollarSign className="h-4 w-4 text-green-600" />
                    </div>
                    <div>
                      <p className="font-medium">{getPatientName(payment.patientId)}</p>
                      <p className="text-sm text-muted-foreground">
                        {payment.payerName || "Patient"} {payment.checkNumber && `• Check #${payment.checkNumber}`}
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="font-bold text-green-600">
                      +${parseFloat(payment.paymentAmount || "0").toLocaleString("en-US", { minimumFractionDigits: 2 })}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      {format(new Date(payment.paymentDate), "MMM d, yyyy")}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
