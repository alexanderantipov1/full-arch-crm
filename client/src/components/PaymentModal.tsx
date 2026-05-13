import { useState, useEffect, useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { loadStripe } from "@stripe/stripe-js";
import { Elements, CardElement, useStripe, useElements } from "@stripe/react-stripe-js";
import { apiRequest } from "@/lib/queryClient";
import { useToast } from "@/hooks/use-toast";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  CreditCard, Lock, CheckCircle2, AlertCircle, Loader2,
  FlaskConical, ArrowRight,
} from "lucide-react";

interface SuccessRecord {
  id: number;
  stripePaymentIntentId: string;
  amount: number;
  currency: string;
  status: string;
  description: string | null;
  testMode: boolean;
  isSimulated: boolean;
}

interface StripeConfig {
  publishableKey: string | null;
  testMode: boolean;
  configured: boolean;
}

interface PaymentIntentData {
  clientSecret: string;
  paymentIntentId: string;
  testMode: boolean;
  simulated: boolean;
}

export interface PaymentModalProps {
  open: boolean;
  onClose: () => void;
  patientId: number;
  patientName: string;
  defaultAmount?: number;
  claimId?: number;
  receiptEmail?: string;
}

type Step = "amount" | "card" | "simulated-confirm" | "processing" | "success" | "error";

/* ─── Inner Stripe Card Form ────────────────────────────────────────────── */
function CardForm({
  intentData, amount, description, patientId, patientName,
  receiptEmail, claimId, isTestMode, onSuccess, onError, onBack,
}: {
  intentData: PaymentIntentData;
  amount: number;
  description: string;
  patientId: number;
  patientName: string;
  receiptEmail?: string;
  claimId?: number;
  isTestMode: boolean;
  onSuccess: (record: any) => void;
  onError: (msg: string) => void;
  onBack: () => void;
}) {
  const stripe = useStripe();
  const elements = useElements();
  const [cardName, setCardName] = useState(patientName);
  const [isProcessing, setIsProcessing] = useState(false);

  const confirmMutation = useMutation({
    mutationFn: (data: object) =>
      apiRequest("POST", "/api/payments/confirm", data).then(r => r.json()),
  });

  async function handlePay(e: React.FormEvent) {
    e.preventDefault();
    if (!stripe || !elements) return;
    setIsProcessing(true);

    const card = elements.getElement(CardElement);
    if (!card) {
      onError("Card input not ready — please refresh and try again.");
      setIsProcessing(false);
      return;
    }

    const { error, paymentIntent } = await stripe.confirmCardPayment(intentData.clientSecret, {
      payment_method: { card, billing_details: { name: cardName || patientName } },
    });

    if (error) {
      onError(error.message || "Card was declined.");
      setIsProcessing(false);
      return;
    }

    if (paymentIntent?.status !== "succeeded") {
      onError(`Payment status: ${paymentIntent?.status ?? "unknown"}. Please try again.`);
      setIsProcessing(false);
      return;
    }

    try {
      const record = await confirmMutation.mutateAsync({
        paymentIntentId: paymentIntent.id,
        patientId,
        amount,
        description,
        patientName,
        receiptEmail,
        claimId,
        simulated: false,
      });
      onSuccess(record);
    } catch (err: any) {
      onError(err?.message || "Payment processed but confirmation failed. Contact support.");
    }
    setIsProcessing(false);
  }

  return (
    <form onSubmit={handlePay} className="space-y-4" data-testid="stripe-card-form">
      {isTestMode && (
        <div className="flex items-center gap-2 rounded-lg border border-amber-300/60 bg-amber-50/60 dark:bg-amber-950/20 dark:border-amber-700/40 px-3 py-2 text-xs text-amber-700 dark:text-amber-400">
          <FlaskConical className="h-3.5 w-3.5 shrink-0" />
          <span><strong>TEST MODE</strong> — Use card 4242 4242 4242 4242, any future expiry, any CVC.</span>
        </div>
      )}

      <div>
        <Label htmlFor="card-holder-name">Name on Card</Label>
        <Input
          id="card-holder-name"
          placeholder={patientName}
          className="mt-1"
          value={cardName}
          onChange={e => setCardName(e.target.value)}
          data-testid="input-card-name"
        />
      </div>

      <div>
        <Label>Card Details</Label>
        <div
          className="mt-1 rounded-md border border-input bg-background px-3 py-3"
          data-testid="stripe-card-element-container"
        >
          <CardElement
            options={{
              style: {
                base: {
                  fontSize: "14px",
                  color: "#374151",
                  fontFamily: "ui-sans-serif, system-ui, sans-serif",
                  "::placeholder": { color: "#9ca3af" },
                },
                invalid: { color: "#ef4444" },
              },
            }}
          />
        </div>
        <p className="text-[11px] text-muted-foreground mt-1 flex items-center gap-1">
          <Lock className="h-3 w-3" />
          Encrypted &amp; processed securely by Stripe — card data never touches our servers
        </p>
      </div>

      <div className="rounded-lg bg-muted/50 px-4 py-3 flex items-center justify-between">
        <span className="text-sm text-muted-foreground">Total to charge</span>
        <span className="text-lg font-bold font-mono text-primary">${amount.toFixed(2)}</span>
      </div>

      <div className="flex gap-2 pt-1">
        <Button
          type="button"
          variant="outline"
          className="flex-1"
          onClick={onBack}
          disabled={isProcessing}
          data-testid="button-back-to-amount"
        >
          Back
        </Button>
        <Button
          type="submit"
          className="flex-1 gap-2"
          disabled={!stripe || !elements || isProcessing}
          data-testid="button-submit-payment"
        >
          {isProcessing
            ? <><Loader2 className="h-4 w-4 animate-spin" />Processing…</>
            : <><Lock className="h-4 w-4" />Pay ${amount.toFixed(2)}</>}
        </Button>
      </div>
    </form>
  );
}

/* ─── Main PaymentModal ─────────────────────────────────────────────────── */
export function PaymentModal({
  open, onClose, patientId, patientName, defaultAmount, claimId, receiptEmail,
}: PaymentModalProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const [step, setStep] = useState<Step>("amount");
  const [amount, setAmount] = useState(defaultAmount ? String(defaultAmount) : "");
  const [description, setDescription] = useState("");
  const [email, setEmail] = useState(receiptEmail || "");
  const [intentData, setIntentData] = useState<PaymentIntentData | null>(null);
  const [successRecord, setSuccessRecord] = useState<SuccessRecord | null>(null);
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    if (open) {
      setStep("amount");
      setAmount(defaultAmount ? String(defaultAmount) : "");
      setDescription("");
      setEmail(receiptEmail || "");
      setIntentData(null);
      setSuccessRecord(null);
      setErrorMsg("");
    }
  }, [open, defaultAmount, receiptEmail]);

  const { data: config } = useQuery<StripeConfig>({
    queryKey: ["/api/payments/config"],
    enabled: open,
  });

  const stripePromise = useMemo(() => {
    if (config?.publishableKey) return loadStripe(config.publishableKey);
    return null;
  }, [config?.publishableKey]);

  const createIntentMutation = useMutation({
    mutationFn: (data: object) =>
      apiRequest("POST", "/api/payments/create-intent", data).then(r => r.json()),
  });

  const simulatedConfirmMutation = useMutation({
    mutationFn: (data: object) =>
      apiRequest("POST", "/api/payments/confirm", data).then(r => r.json()),
  });

  async function handleAmountContinue(e: React.FormEvent) {
    e.preventDefault();
    const amountNum = parseFloat(amount);
    if (!amountNum || amountNum < 0.5) {
      toast({ title: "Enter a valid amount (minimum $0.50)", variant: "destructive" });
      return;
    }

    try {
      const intent: PaymentIntentData = await createIntentMutation.mutateAsync({
        amount: amountNum,
        description: description || `Dental payment — ${patientName}`,
        patientId,
        patientName,
        receiptEmail: email || undefined,
      });
      setIntentData(intent);
      setStep(intent.simulated ? "simulated-confirm" : "card");
    } catch (err: any) {
      toast({ title: err?.message || "Failed to initialize payment", variant: "destructive" });
    }
  }

  async function handleSimulatedConfirm() {
    if (!intentData) return;
    setStep("processing");
    try {
      const record = await simulatedConfirmMutation.mutateAsync({
        paymentIntentId: intentData.paymentIntentId,
        patientId,
        amount: parseFloat(amount),
        description: description || `Dental payment — ${patientName}`,
        patientName,
        receiptEmail: email || undefined,
        claimId,
        simulated: true,
      });
      handleSuccess(record);
    } catch (err: any) {
      handleError(err?.message || "Simulated payment failed");
    }
  }

  function handleSuccess(record: any) {
    setSuccessRecord(record);
    setStep("success");
    queryClient.invalidateQueries({ queryKey: ["/api/payments/history"] });
    queryClient.invalidateQueries({ queryKey: ["/api/payments/history", patientId] });
    queryClient.invalidateQueries({ queryKey: ["/api/era/postings"] });
    toast({
      title: "Payment collected",
      description: `$${parseFloat(amount).toFixed(2)} recorded for ${patientName}`,
    });
  }

  function handleError(msg: string) {
    setErrorMsg(msg);
    setStep("error");
  }

  const amountNum = parseFloat(amount) || 0;
  const isTestMode = config?.testMode !== false;
  const descFinal = description || `Dental payment — ${patientName}`;

  return (
    <Dialog open={open} onOpenChange={v => { if (!v) onClose(); }}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <CreditCard className="h-5 w-5 text-primary" />
            Collect Payment
          </DialogTitle>
          <DialogDescription>
            {patientName} — Secure Stripe card collection
          </DialogDescription>
        </DialogHeader>

        {/* ── Step 1: Amount & Details ── */}
        {step === "amount" && (
          <form onSubmit={handleAmountContinue} className="space-y-4" data-testid="payment-amount-form">
            {isTestMode && config?.configured === false && (
              <div className="flex items-start gap-2 rounded-lg border border-amber-300/60 bg-amber-50/60 dark:bg-amber-950/20 dark:border-amber-700/40 px-3 py-2 text-xs text-amber-700 dark:text-amber-400">
                <FlaskConical className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                <span>
                  <strong>SIMULATED MODE</strong> — Stripe is not configured. Payments will be recorded
                  without a real charge. Add STRIPE_SECRET_KEY to enable live processing.
                </span>
              </div>
            )}

            <div>
              <Label htmlFor="pay-amount">Amount (USD) *</Label>
              <div className="relative mt-1">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground text-sm">$</span>
                <Input
                  id="pay-amount"
                  type="number"
                  step="0.01"
                  min="0.50"
                  placeholder="0.00"
                  className="pl-7"
                  value={amount}
                  onChange={e => setAmount(e.target.value)}
                  data-testid="input-payment-amount"
                  required
                  autoFocus
                />
              </div>
            </div>

            <div>
              <Label htmlFor="pay-description">Description</Label>
              <Input
                id="pay-description"
                placeholder="e.g. Down payment — All-on-4"
                className="mt-1"
                value={description}
                onChange={e => setDescription(e.target.value)}
                data-testid="input-payment-description"
              />
            </div>

            <div>
              <Label htmlFor="pay-email">Receipt Email</Label>
              <Input
                id="pay-email"
                type="email"
                placeholder="patient@email.com"
                className="mt-1"
                value={email}
                onChange={e => setEmail(e.target.value)}
                data-testid="input-payment-email"
              />
            </div>

            {amountNum > 0 && (
              <div className="rounded-lg bg-muted/50 px-4 py-3 flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Amount to collect</span>
                <span className="text-lg font-bold font-mono text-primary">${amountNum.toFixed(2)}</span>
              </div>
            )}

            <div className="flex gap-2 pt-1">
              <Button
                type="button"
                variant="outline"
                className="flex-1"
                onClick={onClose}
                data-testid="button-cancel-payment"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                className="flex-1 gap-2"
                disabled={!amount || amountNum < 0.5 || createIntentMutation.isPending}
                data-testid="button-payment-continue"
              >
                {createIntentMutation.isPending
                  ? <><Loader2 className="h-4 w-4 animate-spin" />Preparing…</>
                  : <><ArrowRight className="h-4 w-4" />Continue</>}
              </Button>
            </div>
          </form>
        )}

        {/* ── Step 2a: Real Stripe Card Entry ── */}
        {step === "card" && intentData && stripePromise && (
          <Elements stripe={stripePromise} options={{ clientSecret: intentData.clientSecret }}>
            <CardForm
              intentData={intentData}
              amount={amountNum}
              description={descFinal}
              patientId={patientId}
              patientName={patientName}
              receiptEmail={email || undefined}
              claimId={claimId}
              isTestMode={isTestMode}
              onSuccess={handleSuccess}
              onError={handleError}
              onBack={() => setStep("amount")}
            />
          </Elements>
        )}

        {/* ── Step 2b: Simulated Confirmation ── */}
        {step === "simulated-confirm" && intentData && (
          <div className="space-y-4" data-testid="simulated-confirm-step">
            <div className="flex items-start gap-3 rounded-lg border border-amber-300/60 bg-amber-50/60 dark:bg-amber-950/20 px-4 py-3 text-sm text-amber-700 dark:text-amber-400">
              <FlaskConical className="h-4 w-4 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Simulated Payment</p>
                <p className="text-xs mt-0.5">
                  No Stripe keys are configured. This will record a simulated payment with no real charge.
                </p>
              </div>
            </div>

            <div className="rounded-lg border bg-muted/30 p-4 space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Patient</span>
                <span className="font-medium">{patientName}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Amount</span>
                <span className="font-bold text-primary">${amountNum.toFixed(2)}</span>
              </div>
              {description && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Description</span>
                  <span className="max-w-[200px] text-right truncate">{description}</span>
                </div>
              )}
            </div>

            <div className="flex gap-2 pt-1">
              <Button
                type="button"
                variant="outline"
                className="flex-1"
                onClick={() => setStep("amount")}
                data-testid="button-back-simulated"
              >
                Back
              </Button>
              <Button
                className="flex-1 gap-2"
                onClick={handleSimulatedConfirm}
                disabled={simulatedConfirmMutation.isPending}
                data-testid="button-confirm-simulated"
              >
                {simulatedConfirmMutation.isPending
                  ? <><Loader2 className="h-4 w-4 animate-spin" />Recording…</>
                  : <>Confirm Simulated Payment</>}
              </Button>
            </div>
          </div>
        )}

        {/* ── Processing Spinner ── */}
        {step === "processing" && (
          <div className="flex flex-col items-center py-10 gap-4" data-testid="processing-step">
            <Loader2 className="h-10 w-10 animate-spin text-primary" />
            <p className="text-sm font-medium">Processing payment…</p>
            <p className="text-xs text-muted-foreground">Please wait, do not close this window</p>
          </div>
        )}

        {/* ── Success ── */}
        {step === "success" && successRecord && (
          <div className="flex flex-col items-center py-6 gap-4" data-testid="payment-success">
            <div className="w-16 h-16 rounded-full bg-emerald-100 dark:bg-emerald-950/40 flex items-center justify-center">
              <CheckCircle2 className="h-9 w-9 text-emerald-600 dark:text-emerald-400" />
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400">
                ${(successRecord.amount / 100).toFixed(2)}
              </div>
              <div className="text-sm font-medium mt-1">Payment Collected</div>
              <div className="text-xs text-muted-foreground mt-1">{patientName}</div>
            </div>

            <div className="w-full rounded-lg border bg-muted/30 p-3 space-y-1.5 text-xs">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Receipt ID</span>
                <span className="font-mono">{successRecord.stripePaymentIntentId?.slice(-14)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Status</span>
                <Badge variant="outline" className="text-[10px] border-emerald-400/50 text-emerald-600 dark:text-emerald-400 h-4">
                  {successRecord.status}
                </Badge>
              </div>
              {successRecord.description && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Description</span>
                  <span className="max-w-[180px] text-right truncate">{successRecord.description}</span>
                </div>
              )}
              {successRecord.testMode && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Mode</span>
                  <Badge variant="outline" className="text-[10px] border-amber-400/50 text-amber-600 h-4">
                    {successRecord.isSimulated ? "SIMULATED" : "TEST"}
                  </Badge>
                </div>
              )}
            </div>

            <Button className="w-full" onClick={onClose} data-testid="button-payment-done">
              Done
            </Button>
          </div>
        )}

        {/* ── Error ── */}
        {step === "error" && (
          <div className="flex flex-col items-center py-6 gap-4" data-testid="payment-error">
            <div className="w-16 h-16 rounded-full bg-destructive/10 flex items-center justify-center">
              <AlertCircle className="h-9 w-9 text-destructive" />
            </div>
            <div className="text-center">
              <div className="text-base font-semibold">Payment Failed</div>
              <div className="text-sm text-muted-foreground mt-1 max-w-[280px]">{errorMsg}</div>
            </div>
            <div className="flex gap-2 w-full">
              <Button variant="outline" className="flex-1" onClick={onClose} data-testid="button-close-error">
                Close
              </Button>
              <Button className="flex-1" onClick={() => setStep("amount")} data-testid="button-retry-payment">
                Try Again
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
