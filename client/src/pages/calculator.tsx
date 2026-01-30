import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { apiRequest } from "@/lib/queryClient";
import { 
  Calculator, 
  DollarSign, 
  TrendingUp,
  AlertCircle,
  CheckCircle2,
  Loader2,
  ArrowRight,
  Percent,
  PiggyBank
} from "lucide-react";

interface CalculationResult {
  treatmentCost: number;
  deductibleApplied: number;
  insuranceCoverage: number;
  patientResponsibility: number;
  coveragePercentage: number;
  remainingAnnualBenefits: number | null;
  medicalCrossCodePotential: {
    estimatedCoverage: number;
    patientResponsibility: number;
    potentialSavings: number;
  } | null;
  breakdown: {
    totalCost: number;
    lessDeductible: number;
    amountCovered: number;
    insurancePays: number;
    youPay: number;
  };
}

const treatmentPresets = [
  { name: "All-on-4 (Single Arch)", cost: 28500 },
  { name: "All-on-4 (Both Arches)", cost: 52000 },
  { name: "All-on-6 (Single Arch)", cost: 35000 },
  { name: "All-on-6 (Both Arches)", cost: 65000 },
  { name: "Single Implant with Crown", cost: 4250 },
  { name: "Bone Graft (Per Site)", cost: 875 },
  { name: "Sinus Lift", cost: 2100 },
];

export default function CalculatorPage() {
  const { toast } = useToast();
  const [formData, setFormData] = useState({
    treatmentCost: 28500,
    insuranceType: "dental",
    coveragePercentage: 50,
    deductible: 100,
    deductibleMet: 0,
    annualMaximum: 2000,
    usedBenefits: 0,
    medicalCrossCode: false
  });
  const [result, setResult] = useState<CalculationResult | null>(null);

  const calculateMutation = useMutation({
    mutationFn: async (data: typeof formData) => {
      const res = await apiRequest("POST", "/api/calculator/patient-responsibility", data);
      return res.json();
    },
    onSuccess: (data) => {
      setResult(data);
    },
    onError: (error: Error) => {
      toast({ title: "Error", description: error.message, variant: "destructive" });
    }
  });

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(amount);
  };

  const handlePresetSelect = (cost: number) => {
    setFormData(prev => ({ ...prev, treatmentCost: cost }));
  };

  return (
    <div className="p-6 space-y-6 overflow-y-auto max-h-[calc(100vh-80px)]">
      <div>
        <h1 className="text-3xl font-bold" data-testid="text-page-title">Patient Responsibility Calculator</h1>
        <p className="text-muted-foreground">
          Calculate estimated out-of-pocket costs for full arch implant procedures
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Calculator className="h-5 w-5" />
                Treatment & Insurance Details
              </CardTitle>
              <CardDescription>
                Enter treatment cost and insurance information to calculate patient responsibility
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-3">
                <Label>Quick Select Treatment</Label>
                <div className="grid grid-cols-2 gap-2">
                  {treatmentPresets.map((preset) => (
                    <Button
                      key={preset.name}
                      variant={formData.treatmentCost === preset.cost ? "default" : "outline"}
                      size="sm"
                      onClick={() => handlePresetSelect(preset.cost)}
                      className="justify-start text-left"
                      data-testid={`button-preset-${preset.cost}`}
                    >
                      <span className="truncate">{preset.name} - {formatCurrency(preset.cost)}</span>
                    </Button>
                  ))}
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="treatmentCost">Total Treatment Cost</Label>
                <div className="relative">
                  <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="treatmentCost"
                    type="number"
                    value={formData.treatmentCost}
                    onChange={(e) => setFormData(prev => ({ ...prev, treatmentCost: parseFloat(e.target.value) || 0 }))}
                    className="pl-9"
                    data-testid="input-treatment-cost"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label>Insurance Type</Label>
                <Select
                  value={formData.insuranceType}
                  onValueChange={(value) => setFormData(prev => ({ ...prev, insuranceType: value }))}
                >
                  <SelectTrigger data-testid="select-insurance-type">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="dental">Dental Insurance</SelectItem>
                    <SelectItem value="medical">Medical Insurance</SelectItem>
                    <SelectItem value="dual">Dual Coverage (Medical + Dental)</SelectItem>
                    <SelectItem value="none">No Insurance</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="coveragePercentage">Coverage %</Label>
                  <div className="relative">
                    <Input
                      id="coveragePercentage"
                      type="number"
                      min="0"
                      max="100"
                      value={formData.coveragePercentage}
                      onChange={(e) => setFormData(prev => ({ ...prev, coveragePercentage: parseInt(e.target.value) || 0 }))}
                      data-testid="input-coverage-percentage"
                    />
                    <Percent className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="deductible">Annual Deductible</Label>
                  <div className="relative">
                    <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      id="deductible"
                      type="number"
                      value={formData.deductible}
                      onChange={(e) => setFormData(prev => ({ ...prev, deductible: parseFloat(e.target.value) || 0 }))}
                      className="pl-9"
                      data-testid="input-deductible"
                    />
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="deductibleMet">Deductible Already Met</Label>
                  <div className="relative">
                    <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      id="deductibleMet"
                      type="number"
                      value={formData.deductibleMet}
                      onChange={(e) => setFormData(prev => ({ ...prev, deductibleMet: parseFloat(e.target.value) || 0 }))}
                      className="pl-9"
                      data-testid="input-deductible-met"
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="annualMaximum">Annual Maximum</Label>
                  <div className="relative">
                    <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      id="annualMaximum"
                      type="number"
                      value={formData.annualMaximum}
                      onChange={(e) => setFormData(prev => ({ ...prev, annualMaximum: parseFloat(e.target.value) || 0 }))}
                      className="pl-9"
                      data-testid="input-annual-maximum"
                    />
                  </div>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="usedBenefits">Benefits Already Used This Year</Label>
                <div className="relative">
                  <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="usedBenefits"
                    type="number"
                    value={formData.usedBenefits}
                    onChange={(e) => setFormData(prev => ({ ...prev, usedBenefits: parseFloat(e.target.value) || 0 }))}
                    className="pl-9"
                    data-testid="input-used-benefits"
                  />
                </div>
              </div>

              <div className="flex items-center justify-between p-4 border rounded-lg bg-muted/30">
                <div className="space-y-0.5">
                  <Label htmlFor="medicalCrossCode" className="font-medium">Include Medical Cross-Coding Analysis</Label>
                  <p className="text-sm text-muted-foreground">
                    Calculate potential savings from medical insurance billing
                  </p>
                </div>
                <Switch
                  id="medicalCrossCode"
                  checked={formData.medicalCrossCode}
                  onCheckedChange={(checked) => setFormData(prev => ({ ...prev, medicalCrossCode: checked }))}
                  data-testid="switch-medical-cross-code"
                />
              </div>

              <Button
                onClick={() => calculateMutation.mutate(formData)}
                disabled={calculateMutation.isPending}
                className="w-full"
                size="lg"
                data-testid="button-calculate"
              >
                {calculateMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                <Calculator className="mr-2 h-4 w-4" />
                Calculate Patient Responsibility
              </Button>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          {result ? (
            <>
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2">
                    <DollarSign className="h-5 w-5 text-primary" />
                    Cost Breakdown
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-3">
                    <div className="flex items-center justify-between py-2 border-b">
                      <span className="text-muted-foreground">Total Treatment Cost</span>
                      <span className="font-semibold" data-testid="text-total-cost">{formatCurrency(result.breakdown.totalCost)}</span>
                    </div>
                    <div className="flex items-center justify-between py-2 border-b">
                      <span className="text-muted-foreground">Less: Deductible Applied</span>
                      <span className="text-red-600" data-testid="text-deductible">-{formatCurrency(result.breakdown.lessDeductible)}</span>
                    </div>
                    <div className="flex items-center justify-between py-2 border-b">
                      <span className="text-muted-foreground">Amount Subject to Coverage</span>
                      <span data-testid="text-covered-amount">{formatCurrency(result.breakdown.amountCovered)}</span>
                    </div>
                    <div className="flex items-center justify-between py-2 border-b">
                      <span className="text-muted-foreground">Insurance Pays ({result.coveragePercentage}%)</span>
                      <span className="text-green-600" data-testid="text-insurance-pays">-{formatCurrency(result.breakdown.insurancePays)}</span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between p-4 bg-primary/10 rounded-lg">
                    <span className="font-semibold text-lg">Patient Responsibility</span>
                    <span className="text-2xl font-bold text-primary" data-testid="text-patient-responsibility">
                      {formatCurrency(result.breakdown.youPay)}
                    </span>
                  </div>

                  {result.remainingAnnualBenefits !== null && (
                    <div className="flex items-center gap-2 p-3 border rounded-lg bg-muted/30">
                      <AlertCircle className="h-4 w-4 text-yellow-500" />
                      <span className="text-sm">
                        Remaining annual benefits after this treatment: <strong>{formatCurrency(result.remainingAnnualBenefits)}</strong>
                      </span>
                    </div>
                  )}
                </CardContent>
              </Card>

              {result.medicalCrossCodePotential && (
                <Card className="border-green-200 dark:border-green-900">
                  <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2 text-green-700 dark:text-green-400">
                      <TrendingUp className="h-5 w-5" />
                      Medical Cross-Coding Opportunity
                    </CardTitle>
                    <CardDescription>
                      Potential savings by billing to medical insurance for functional/medical necessity
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="grid grid-cols-3 gap-4 text-center">
                      <div className="p-3 bg-muted/30 rounded-lg">
                        <p className="text-sm text-muted-foreground">Medical Coverage</p>
                        <p className="text-xl font-bold text-green-600" data-testid="text-medical-coverage">
                          {formatCurrency(result.medicalCrossCodePotential.estimatedCoverage)}
                        </p>
                      </div>
                      <div className="p-3 bg-muted/30 rounded-lg">
                        <p className="text-sm text-muted-foreground">Patient Pays</p>
                        <p className="text-xl font-bold" data-testid="text-medical-patient-pays">
                          {formatCurrency(result.medicalCrossCodePotential.patientResponsibility)}
                        </p>
                      </div>
                      <div className="p-3 bg-green-100 dark:bg-green-900/30 rounded-lg">
                        <p className="text-sm text-muted-foreground">Savings</p>
                        <p className="text-xl font-bold text-green-600" data-testid="text-medical-savings">
                          {formatCurrency(result.medicalCrossCodePotential.potentialSavings)}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 p-3 border rounded-lg">
                      <CheckCircle2 className="h-4 w-4 text-green-500" />
                      <span className="text-sm">
                        Use the Coding Engine to find appropriate CPT and ICD-10 codes for medical billing
                      </span>
                    </div>
                  </CardContent>
                </Card>
              )}

              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2">
                    <PiggyBank className="h-5 w-5" />
                    Payment Options
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex items-center justify-between p-3 border rounded-lg">
                    <div>
                      <p className="font-medium">Pay in Full</p>
                      <p className="text-sm text-muted-foreground">5% courtesy discount</p>
                    </div>
                    <p className="font-semibold text-green-600">
                      {formatCurrency(result.breakdown.youPay * 0.95)}
                    </p>
                  </div>
                  <div className="flex items-center justify-between p-3 border rounded-lg">
                    <div>
                      <p className="font-medium">12-Month Financing</p>
                      <p className="text-sm text-muted-foreground">0% APR available</p>
                    </div>
                    <p className="font-semibold">
                      {formatCurrency(result.breakdown.youPay / 12)}/mo
                    </p>
                  </div>
                  <div className="flex items-center justify-between p-3 border rounded-lg">
                    <div>
                      <p className="font-medium">24-Month Financing</p>
                      <p className="text-sm text-muted-foreground">Low interest rate</p>
                    </div>
                    <p className="font-semibold">
                      {formatCurrency(result.breakdown.youPay / 24)}/mo
                    </p>
                  </div>
                </CardContent>
              </Card>
            </>
          ) : (
            <Card className="h-full flex items-center justify-center min-h-[400px]">
              <CardContent className="text-center space-y-4">
                <div className="p-4 bg-muted/30 rounded-full w-fit mx-auto">
                  <Calculator className="h-12 w-12 text-muted-foreground" />
                </div>
                <div>
                  <h3 className="font-semibold text-lg">Enter Treatment Details</h3>
                  <p className="text-muted-foreground text-sm max-w-xs mx-auto">
                    Fill in the treatment cost and insurance information to see the patient responsibility breakdown
                  </p>
                </div>
                <ArrowRight className="h-6 w-6 text-muted-foreground mx-auto animate-pulse" />
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
