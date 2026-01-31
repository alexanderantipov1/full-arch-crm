import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/hooks/use-toast";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { apiRequest, queryClient } from "@/lib/queryClient";
import { Package, Plus, DollarSign, Clock, Shield, Sparkles } from "lucide-react";
import type { TreatmentPackage } from "@shared/schema";

const packageFormSchema = z.object({
  name: z.string().min(1, "Package name is required"),
  description: z.string().optional(),
  procedureType: z.string().min(1, "Procedure type is required"),
  archType: z.string().min(1, "Arch type is required"),
  prosthesisType: z.string().min(1, "Prosthesis type is required"),
  materialType: z.string().min(1, "Material type is required"),
  basePrice: z.string().min(1, "Base price is required"),
  implantCount: z.string().min(1, "Implant count is required"),
  warrantyYears: z.string().optional(),
  estimatedDuration: z.string().optional(),
});

type PackageFormData = z.infer<typeof packageFormSchema>;

const procedureTypes = [
  { value: "all_on_4", label: "All-on-4" },
  { value: "all_on_6", label: "All-on-6" },
  { value: "all_on_x", label: "All-on-X (Custom)" },
];

const archTypes = [
  { value: "upper", label: "Upper Arch" },
  { value: "lower", label: "Lower Arch" },
  { value: "both", label: "Both Arches" },
];

const prosthesisTypes = [
  { value: "fp1", label: "FP-1 (Fixed Prosthesis Type 1)" },
  { value: "fp2", label: "FP-2 (Fixed Prosthesis Type 2)" },
  { value: "fp3", label: "FP-3 (Fixed Prosthesis Type 3)" },
  { value: "hybrid", label: "Hybrid Prosthesis" },
];

const materialTypes = [
  { value: "solid_zirconia", label: "Solid Zirconia" },
  { value: "titanium_bar_zirconia", label: "Titanium Bar + Zirconia" },
  { value: "titanium_bar_acrylic", label: "Titanium Bar + Acrylic" },
  { value: "pmma_temp", label: "PMMA (Temporary)" },
  { value: "peek", label: "PEEK Framework" },
];

const formatCurrency = (amount: string | number | null) => {
  if (!amount) return "$0";
  const num = typeof amount === "string" ? parseFloat(amount) : amount;
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(num);
};

export default function TreatmentPackagesPage() {
  const { toast } = useToast();
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);

  const { data: packages = [], isLoading } = useQuery<TreatmentPackage[]>({
    queryKey: ["/api/packages"],
  });

  const form = useForm<PackageFormData>({
    resolver: zodResolver(packageFormSchema),
    defaultValues: {
      name: "",
      description: "",
      procedureType: "",
      archType: "",
      prosthesisType: "",
      materialType: "",
      basePrice: "",
      implantCount: "",
      warrantyYears: "5",
      estimatedDuration: "",
    },
  });

  const createPackageMutation = useMutation({
    mutationFn: async (data: PackageFormData) => {
      const res = await apiRequest("POST", "/api/packages", {
        ...data,
        basePrice: data.basePrice,
        implantCount: parseInt(data.implantCount),
        warrantyYears: data.warrantyYears ? parseInt(data.warrantyYears) : 5,
      });
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/packages"] });
      setIsAddDialogOpen(false);
      form.reset();
      toast({ title: "Package Created", description: "Treatment package has been added" });
    },
    onError: (error: Error) => {
      toast({ title: "Error", description: error.message, variant: "destructive" });
    },
  });

  const onSubmit = (data: PackageFormData) => {
    createPackageMutation.mutate(data);
  };

  const getMaterialColor = (material: string) => {
    switch (material) {
      case "solid_zirconia": return "bg-white text-gray-800 border border-gray-300";
      case "titanium_bar_zirconia": return "bg-blue-100 text-blue-800";
      case "titanium_bar_acrylic": return "bg-amber-100 text-amber-800";
      case "pmma_temp": return "bg-purple-100 text-purple-800";
      case "peek": return "bg-green-100 text-green-800";
      default: return "bg-gray-100 text-gray-800";
    }
  };

  return (
    <div className="flex-1 overflow-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold" data-testid="text-page-title">Treatment Packages</h1>
          <p className="text-muted-foreground">Pre-configured full arch treatment plans with fixed pricing</p>
        </div>
        <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
          <DialogTrigger asChild>
            <Button data-testid="button-add-package">
              <Plus className="w-4 h-4 mr-2" />
              Add Package
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>Create Treatment Package</DialogTitle>
              <DialogDescription>Configure a new pre-priced treatment option</DialogDescription>
            </DialogHeader>
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                <FormField
                  control={form.control}
                  name="name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Package Name</FormLabel>
                      <FormControl>
                        <Input {...field} placeholder="e.g., Premium All-on-4 Upper" data-testid="input-name" />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="description"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Description</FormLabel>
                      <FormControl>
                        <Textarea {...field} placeholder="Package details and included services..." data-testid="input-description" />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <div className="grid grid-cols-2 gap-4">
                  <FormField
                    control={form.control}
                    name="procedureType"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Procedure Type</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger data-testid="select-procedure">
                              <SelectValue placeholder="Select procedure" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {procedureTypes.map((opt) => (
                              <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="archType"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Arch</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger data-testid="select-arch">
                              <SelectValue placeholder="Select arch" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {archTypes.map((opt) => (
                              <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <FormField
                    control={form.control}
                    name="prosthesisType"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Prosthesis Type</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger data-testid="select-prosthesis">
                              <SelectValue placeholder="Select type" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {prosthesisTypes.map((opt) => (
                              <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="materialType"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Material</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger data-testid="select-material">
                              <SelectValue placeholder="Select material" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {materialTypes.map((opt) => (
                              <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
                <div className="grid grid-cols-3 gap-4">
                  <FormField
                    control={form.control}
                    name="basePrice"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Base Price ($)</FormLabel>
                        <FormControl>
                          <Input {...field} type="number" placeholder="25000" data-testid="input-price" />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="implantCount"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Implants</FormLabel>
                        <FormControl>
                          <Input {...field} type="number" placeholder="4" data-testid="input-implants" />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="warrantyYears"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Warranty (Years)</FormLabel>
                        <FormControl>
                          <Input {...field} type="number" placeholder="5" data-testid="input-warranty" />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
                <FormField
                  control={form.control}
                  name="estimatedDuration"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Estimated Duration</FormLabel>
                      <FormControl>
                        <Input {...field} placeholder="e.g., 4-6 months" data-testid="input-duration" />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <div className="flex justify-end gap-2">
                  <Button type="button" variant="outline" onClick={() => setIsAddDialogOpen(false)}>
                    Cancel
                  </Button>
                  <Button type="submit" disabled={createPackageMutation.isPending} data-testid="button-submit-package">
                    {createPackageMutation.isPending ? "Creating..." : "Create Package"}
                  </Button>
                </div>
              </form>
            </Form>
          </DialogContent>
        </Dialog>
      </div>

      {isLoading ? (
        <div className="text-center py-8 text-muted-foreground">Loading packages...</div>
      ) : packages.length === 0 ? (
        <Card className="text-center py-12">
          <CardContent>
            <Package className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium mb-2">No Treatment Packages</h3>
            <p className="text-muted-foreground mb-4">Create pre-configured treatment options with fixed pricing</p>
            <Button onClick={() => setIsAddDialogOpen(true)} data-testid="button-add-first-package">
              <Plus className="w-4 h-4 mr-2" />
              Create First Package
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {packages.map((pkg) => (
            <Card key={pkg.id} className="hover-elevate" data-testid={`package-card-${pkg.id}`}>
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div>
                    <CardTitle className="text-xl">{pkg.name}</CardTitle>
                    <CardDescription>{pkg.description}</CardDescription>
                  </div>
                  <Badge className={getMaterialColor(pkg.materialType)}>
                    {pkg.materialType.replace(/_/g, " ").replace(/\b\w/g, (l: string) => l.toUpperCase())}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-3xl font-bold text-primary" data-testid={`price-${pkg.id}`}>
                    {formatCurrency(pkg.basePrice)}
                  </span>
                  <Badge variant="outline">
                    {pkg.procedureType.replace(/_/g, "-").toUpperCase()} {pkg.archType.replace(/\b\w/g, (l: string) => l.toUpperCase())}
                  </Badge>
                </div>

                <div className="space-y-2 text-sm">
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <Sparkles className="w-4 h-4" />
                    <span>{pkg.prosthesisType.toUpperCase()} Prosthesis</span>
                  </div>
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <DollarSign className="w-4 h-4" />
                    <span>{pkg.implantCount} Implants Included</span>
                  </div>
                  {pkg.estimatedDuration && (
                    <div className="flex items-center gap-2 text-muted-foreground">
                      <Clock className="w-4 h-4" />
                      <span>{pkg.estimatedDuration}</span>
                    </div>
                  )}
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <Shield className="w-4 h-4" />
                    <span>{pkg.warrantyYears} Year Warranty</span>
                  </div>
                </div>

                <Button className="w-full" variant="outline" data-testid={`button-select-${pkg.id}`}>
                  Select Package
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Prosthesis Types Guide</CardTitle>
          <CardDescription>Understanding the different full arch prosthesis options</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 border rounded-lg">
              <h4 className="font-semibold mb-2">FP-1 (Fixed Type 1)</h4>
              <p className="text-sm text-muted-foreground">
                Most natural appearance. Individual crowns on implants. No visible acrylic. Best for patients with adequate bone and gum tissue.
              </p>
            </div>
            <div className="p-4 border rounded-lg">
              <h4 className="font-semibold mb-2">FP-2 (Fixed Type 2)</h4>
              <p className="text-sm text-muted-foreground">
                Crowns with pink gingival portion. Ideal for moderate tissue loss. Good blend of aesthetics and functionality.
              </p>
            </div>
            <div className="p-4 border rounded-lg">
              <h4 className="font-semibold mb-2">FP-3 (Fixed Type 3)</h4>
              <p className="text-sm text-muted-foreground">
                Full denture-like prosthesis. Maximum tissue replacement. Best for significant bone and tissue loss. Most common for All-on-4.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
