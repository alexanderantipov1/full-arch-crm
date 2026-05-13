import { useState, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/lib/queryClient";
import { useToast } from "@/hooks/use-toast";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { CreditCard, Lock, CheckCircle2, AlertCircle, Loader2, FlaskConical } from "lucide-react";

interface StripeConfig {
  publishableKey: string | null;
  testMode: boolean;
  configured: boolean;
}

interface PaymentIntent {
  clientSecret: string;
  paymentIntentId: string;
  testMode: boolean;
  simulated: boolean;
}

interface PaymentModalProps {
  open: boolean;
  onClose: () => void;
  patientId: number;
  patientName: string;
  defaultAmount?: number;
  claimId?: number;
  receiptEmail?: string;
}

function formatCardNumber(value: string) {
  return value.replace(/\D/g, "").slice(0, 16).replace(/(\d{4})(?=\d)/g, "$1 ");
}
function formatExpiry(value: string) {
  const digits = value.replace(/\D/g, "").slice(0, 4);
  if (digits.length >= 3) return digits.slice(0, 2) + "/" + digits.slice(2);
  return digits;
}

type Step = "form" | "processing" | "success" | "error";

export function PaymentModal({ open, onClose, patientId, patientName, defaultAmount, claimId, receiptEmail }: PaymentModalProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const [step, setStep] = useState<Step>("form");
  const [amount, setAmount] = useState(defaultAmount ? String(defaultAmount) : "");
  const [description, setDescription] = useState("");
  const [email, setEmail] = useState(receiptEmail || "");
  const [cardNumber, setCardNumber] = useState("");
  const [expiry, setExpiry] = useState("");
  const [cvc, setCvc] = useState("");
  const [cardName, setCardName] = useState("");
  const [successRecord, setSuccessRecord] = useState<any>(null);
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    if (open) {
      setStep("form");
      setAmount(defaultAmount ? String(defaultAmount) : "");
      setDescription("");
      setEmail(receiptEmail || "");
      setCardNumber("");
      setExpiry("");
      setCvc("");
      setCardName("");
      setSuccessRecord(null);
      setErrorMsg("");
    }
  }, [open, defaultAmount, receiptEmail]);

  const { data: config } = useQuery<StripeConfig>({
    queryKey: ["/api/payments/config"],
    enabled: open,
  });

  const createIntentMutation = useMutation({
    mutationFn: (data: object) => apiRequest("POST", "/api/payments/create-intent", data).then(r => r.json()),
  });

  const confirmMutation = useMutation({
    mutationFn: (data: object) => apiRequest("POST", "/api/payments/confirm", data).then(r => r.json()),
  });

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!amount || parseFloat(amount) <= 0) {
      toast({ title: "Enter a valid amount", variant: "destructive" });
      return;
    }

    setStep("processing");

    try {
      const intent: PaymentIntent = await createIntentMutation.mutateAsync({
        amount: parseFloat(amount),
        description: description || `Dental payment — ${patientName}`,
        patientId,
        patientName,
        receiptEmail: email || undefined,
      });

      const record = await confirmMutation.mutateAsync({
        paymentIntentId: intent.paymentIntentId,
        patientId,
        amount: parseFloat(amount),
        description: description || `Dental payment — ${patientName}`,
        patientName,
        receiptEmail: email || undefined,
        claimId: claimId || undefined,
        simulated: intent.simulated,
      });

      setSuccessRecord(record);
      setStep("success");

      queryClient.invalidateQueries({ queryKey: ["/api/payments/history"] });
      queryClient.invalidateQueries({ queryKey: ["/api/payments/history", patientId] });

      toast({
        title: "Payment collected",
        description: `$${parseFloat(amount).toFixed(2)} recorded for ${patientName}`,
      });
    } catch (err: any) {
      setErrorMsg(err?.message || "Payment failed. Please try again.");
      setStep("error");
    }
  }

  const amountNum = parseFloat(amount) || 0;
  const isTestMode = config?.testMode !== false;

  return (
    <Dialog open={open} onOpenChange={v => { if (!v) onClose(); }}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <CreditCard className="h-5 w-5 text-primary" />
            Collect Payment
          </DialogTitle>
          <DialogDescription>
            {patientName} — Secure card collection
          </DialogDescription>
        </DialogHeader>

        {isTestMode && (
          <div className="flex items-center gap-2 rounded-lg border border-amber-300/60 bg-amber-50/60 dark:bg-amber-950/20 dark:border-amber-700/40 px-3 py-2 text-xs text-amber-700 dark:text-amber-400">
            <FlaskConical className="h-3.5 w-3.5 shrink-0" />
            <span><strong>TEST MODE</strong> — No real charges. Use card 4242 4242 4242 4242.</span>
          </div>
        )}

        {step === "form" && (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2">
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
                  />
                </div>
              </div>
              <div className="col-span-2">
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
              <div className="col-span-2">
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
            </div>

            <Separator />

            <div className="space-y-3">
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <Lock className="h-3 w-3" />
                <span>Card details (encrypted)</span>
              </div>
              <div>
                <Label htmlFor="card-name">Name on Card</Label>
                <Input
                  id="card-name"
                  placeholder="Jane Smith"
                  className="mt-1"
                  value={cardName}
                  onChange={e => setCardName(e.target.value)}
                  data-testid="input-card-name"
                />
              </div>
              <div>
                <Label htmlFor="card-number">Card Number</Label>
                <div className="relative mt-1">
                  <Input
                    id="card-number"
                    placeholder="4242 4242 4242 4242"
                    value={cardNumber}
                    onChange={e => setCardNumber(formatCardNumber(e.target.value))}
                    maxLength={19}
                    className="font-mono pr-10"
                    data-testid="input-card-number"
                  />
                  <CreditCard className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label htmlFor="card-expiry">Expiry</Label>
                  <Input
                    id="card-expiry"
                    placeholder="MM/YY"
                    value={expiry}
                    onChange={e => setExpiry(formatExpiry(e.target.value))}
                    maxLength={5}
                    className="mt-1 font-mono"
                    data-testid="input-card-expiry"
                  />
                </div>
                <div>
                  <Label htmlFor="card-cvc">CVC</Label>
                  <Input
                    id="card-cvc"
                    placeholder="123"
                    value={cvc}
                    onChange={e => setCvc(e.target.value.replace(/\D/g, "").slice(0, 4))}
                    maxLength={4}
                    className="mt-1 font-mono"
                    data-testid="input-card-cvc"
                  />
                </div>
              </div>
            </div>

            {amountNum > 0 && (
              <div className="rounded-lg bg-muted/50 px-4 py-3 flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Total to collect</span>
                <span className="text-lg font-bold font-mono text-primary">
                  ${amountNum.toFixed(2)}
                </span>
              </div>
            )}

            <div className="flex gap-2 pt-1">
              <Button type="button" variant="outline" className="flex-1" onClick={onClose} data-testid="button-cancel-payment">
                Cancel
              </Button>
              <Button
                type="submit"
                className="flex-1 gap-2"
                disabled={!amount || parseFloat(amount) <= 0}
                data-testid="button-submit-payment"
              >
                <Lock className="h-4 w-4" />
                Charge ${amountNum > 0 ? amountNum.toFixed(2) : "0.00"}
              </Button>
            </div>
          </form>
        )}

        {step === "processing" && (
          <div className="flex flex-col items-center py-10 gap-4">
            <Loader2 className="h-10 w-10 animate-spin text-primary" />
            <p className="text-sm font-medium">Processing payment…</p>
            <p className="text-xs text-muted-foreground">Please wait, do not close this window</p>
          </div>
        )}

        {step === "success" && successRecord && (
          <div className="flex flex-col items-center py-6 gap-4">
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
                <span className="font-mono">{successRecord.stripePaymentIntentId?.slice(-12)}</span>
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
                  <span className="max-w-[200px] text-right truncate">{successRecord.description}</span>
                </div>
              )}
              {successRecord.testMode && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Mode</span>
                  <Badge variant="outline" className="text-[10px] border-amber-400/50 text-amber-600 h-4">TEST</Badge>
                </div>
              )}
            </div>

            <Button className="w-full" onClick={onClose} data-testid="button-payment-done">
              Done
            </Button>
          </div>
        )}

        {step === "error" && (
          <div className="flex flex-col items-center py-6 gap-4">
            <div className="w-16 h-16 rounded-full bg-destructive/10 flex items-center justify-center">
              <AlertCircle className="h-9 w-9 text-destructive" />
            </div>
            <div className="text-center">
              <div className="text-base font-semibold">Payment Failed</div>
              <div className="text-sm text-muted-foreground mt-1">{errorMsg}</div>
            </div>
            <div className="flex gap-2 w-full">
              <Button variant="outline" className="flex-1" onClick={onClose}>Close</Button>
              <Button className="flex-1" onClick={() => setStep("form")} data-testid="button-retry-payment">Try Again</Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
