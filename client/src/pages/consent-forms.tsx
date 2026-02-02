import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { FileText, Plus, Search, CheckCircle, Clock, User, Calendar, FileSignature } from "lucide-react";
import { format } from "date-fns";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { useToast } from "@/hooks/use-toast";
import { apiRequest, queryClient } from "@/lib/queryClient";
import type { Patient, ConsentForm } from "@shared/schema";

const consentFormSchema = z.object({
  patientId: z.string().min(1, "Patient is required"),
  formType: z.string().min(1, "Form type is required"),
  content: z.string().min(1, "Content is required"),
});

type ConsentFormData = z.infer<typeof consentFormSchema>;

const consentFormTypes = [
  { value: "general_treatment", label: "General Treatment Consent" },
  { value: "implant_surgery", label: "Implant Surgery Consent" },
  { value: "sedation", label: "Sedation/Anesthesia Consent" },
  { value: "hipaa_privacy", label: "HIPAA Privacy Notice" },
  { value: "financial_agreement", label: "Financial Agreement" },
  { value: "photo_release", label: "Photo/Video Release" },
  { value: "bone_graft", label: "Bone Graft Consent" },
  { value: "extraction", label: "Extraction Consent" },
];

const formTemplates: Record<string, string> = {
  general_treatment: `CONSENT FOR DENTAL TREATMENT

I, the undersigned, hereby consent to the performance of dental treatment and procedures as explained to me by my dentist.

I understand that:
1. The treatment plan has been explained to me
2. Alternative treatments have been discussed
3. Risks and benefits have been outlined
4. I have had the opportunity to ask questions

I authorize the dental team to perform the recommended treatment.`,

  implant_surgery: `INFORMED CONSENT FOR DENTAL IMPLANT SURGERY

I understand that I am undergoing dental implant surgery, which involves:
- Surgical placement of titanium implant(s) into the jawbone
- A healing period of 3-6 months for osseointegration
- Possible need for bone grafting procedures
- Attachment of prosthetic teeth to the implant(s)

RISKS include but are not limited to:
- Infection, bleeding, swelling
- Nerve damage causing numbness
- Implant failure requiring removal
- Sinus complications (upper jaw)
- Need for additional procedures

I have been informed of all risks and benefits and consent to this procedure.`,

  sedation: `CONSENT FOR SEDATION/ANESTHESIA

I consent to the administration of sedation/anesthesia as deemed appropriate for my dental procedure.

I confirm that:
- I have disclosed my complete medical history
- I have followed pre-operative instructions
- I have arranged for transportation after the procedure
- I understand the risks of sedation

I authorize the administration of sedation as medically indicated.`,

  hipaa_privacy: `HIPAA PRIVACY NOTICE ACKNOWLEDGMENT

I acknowledge that I have received and reviewed the Notice of Privacy Practices which describes how my health information may be used and disclosed.

I understand my rights regarding my protected health information (PHI) and how to exercise those rights.`,

  financial_agreement: `FINANCIAL AGREEMENT AND PAYMENT POLICY

I understand and agree to the following financial policies:
- Payment is due at the time of service unless other arrangements are made
- I am responsible for charges not covered by insurance
- A finance charge may apply to past-due balances
- I authorize release of information to my insurance company

I accept financial responsibility for all charges.`,

  photo_release: `PHOTO AND VIDEO RELEASE

I grant permission to use photographs, videos, and other images of my dental treatment for:
- Educational purposes
- Marketing materials
- Before/after documentation
- Professional presentations

I understand I may withdraw this consent at any time in writing.`,
};

export default function ConsentFormsPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const { toast } = useToast();

  const { data: patients = [] } = useQuery<Patient[]>({
    queryKey: ["/api/patients"],
  });

  const { data: consentForms = [], isLoading } = useQuery<ConsentForm[]>({
    queryKey: ["/api/consent-forms"],
  });

  const form = useForm<ConsentFormData>({
    resolver: zodResolver(consentFormSchema),
    defaultValues: {
      patientId: "",
      formType: "",
      content: "",
    },
  });

  const watchFormType = form.watch("formType");

  const handleFormTypeChange = (value: string) => {
    form.setValue("formType", value);
    if (formTemplates[value]) {
      form.setValue("content", formTemplates[value]);
    }
  };

  const createConsentMutation = useMutation({
    mutationFn: async (data: ConsentFormData) => {
      return apiRequest("/api/consent-forms", {
        method: "POST",
        body: JSON.stringify({
          patientId: parseInt(data.patientId),
          formType: data.formType,
          content: data.content,
          status: "pending",
        }),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/consent-forms"] });
      toast({ title: "Consent form created successfully" });
      setIsDialogOpen(false);
      form.reset();
    },
    onError: () => {
      toast({ title: "Failed to create consent form", variant: "destructive" });
    },
  });

  const signConsentMutation = useMutation({
    mutationFn: async (id: number) => {
      return apiRequest(`/api/consent-forms/${id}/sign`, {
        method: "POST",
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/consent-forms"] });
      toast({ title: "Consent form signed successfully" });
    },
    onError: () => {
      toast({ title: "Failed to sign consent form", variant: "destructive" });
    },
  });

  const onSubmit = (data: ConsentFormData) => {
    createConsentMutation.mutate(data);
  };

  const getPatientName = (patientId: number) => {
    const patient = patients.find((p) => p.id === patientId);
    return patient ? `${patient.firstName} ${patient.lastName}` : "Unknown";
  };

  const getFormTypeLabel = (type: string) => {
    return consentFormTypes.find(t => t.value === type)?.label || type;
  };

  const filteredForms = consentForms.filter((form) => {
    const patientName = getPatientName(form.patientId);
    const matchesSearch = 
      patientName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      form.formType.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === "all" || form.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const pendingCount = consentForms.filter(f => f.status === "pending").length;
  const signedCount = consentForms.filter(f => f.status === "signed").length;

  return (
    <div className="flex-1 overflow-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-2" data-testid="text-page-title">
            <FileSignature className="h-8 w-8 text-primary" />
            Digital Consent Forms
          </h1>
          <p className="text-muted-foreground">Manage patient consent forms and signatures</p>
        </div>
        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
          <DialogTrigger asChild>
            <Button data-testid="button-create-consent">
              <Plus className="h-4 w-4 mr-2" />
              Create Consent Form
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Create Consent Form</DialogTitle>
              <DialogDescription>Select a form type and customize the content</DialogDescription>
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
                <FormField
                  control={form.control}
                  name="formType"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Form Type</FormLabel>
                      <Select onValueChange={handleFormTypeChange} value={field.value}>
                        <FormControl>
                          <SelectTrigger data-testid="select-form-type">
                            <SelectValue placeholder="Select form type" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {consentFormTypes.map((type) => (
                            <SelectItem key={type.value} value={type.value}>
                              {type.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="content"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Form Content</FormLabel>
                      <FormControl>
                        <Textarea
                          {...field}
                          rows={12}
                          placeholder="Form content will appear here..."
                          data-testid="textarea-content"
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <DialogFooter>
                  <Button type="submit" disabled={createConsentMutation.isPending} data-testid="button-submit-consent">
                    {createConsentMutation.isPending ? "Creating..." : "Create Form"}
                  </Button>
                </DialogFooter>
              </form>
            </Form>
          </DialogContent>
        </Dialog>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Total Forms</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold" data-testid="stat-total">{consentForms.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Pending Signature</CardTitle>
            <Clock className="h-4 w-4 text-amber-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-amber-600" data-testid="stat-pending">{pendingCount}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 gap-2">
            <CardTitle className="text-sm font-medium">Signed</CardTitle>
            <CheckCircle className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600" data-testid="stat-signed">{signedCount}</div>
          </CardContent>
        </Card>
      </div>

      {/* Forms List */}
      <Card>
        <CardHeader>
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <CardTitle>All Consent Forms</CardTitle>
              <CardDescription>View and manage patient consent documents</CardDescription>
            </div>
            <div className="flex gap-2">
              <div className="relative">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search forms..."
                  className="pl-8 w-48"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  data-testid="input-search"
                />
              </div>
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-32" data-testid="filter-status">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Status</SelectItem>
                  <SelectItem value="pending">Pending</SelectItem>
                  <SelectItem value="signed">Signed</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-center py-8 text-muted-foreground">Loading consent forms...</p>
          ) : filteredForms.length === 0 ? (
            <div className="text-center py-12">
              <FileSignature className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium mb-2">No Consent Forms</h3>
              <p className="text-muted-foreground mb-4">Create consent forms for your patients</p>
              <Button onClick={() => setIsDialogOpen(true)} data-testid="button-add-first">
                <Plus className="h-4 w-4 mr-2" />
                Create First Form
              </Button>
            </div>
          ) : (
            <div className="space-y-2">
              {filteredForms.map((consentForm) => (
                <div
                  key={consentForm.id}
                  className="flex items-center justify-between p-4 border rounded-lg hover-elevate"
                  data-testid={`consent-row-${consentForm.id}`}
                >
                  <div className="flex items-center gap-4">
                    <div className={`p-2 rounded-full ${consentForm.status === "signed" ? "bg-green-100 dark:bg-green-900/30" : "bg-amber-100 dark:bg-amber-900/30"}`}>
                      {consentForm.status === "signed" ? (
                        <CheckCircle className="h-4 w-4 text-green-600" />
                      ) : (
                        <Clock className="h-4 w-4 text-amber-600" />
                      )}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{getPatientName(consentForm.patientId)}</span>
                        <Badge variant={consentForm.status === "signed" ? "default" : "secondary"}>
                          {consentForm.status}
                        </Badge>
                      </div>
                      <p className="text-sm text-muted-foreground">{getFormTypeLabel(consentForm.formType)}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="text-right text-sm text-muted-foreground">
                      <p>{format(new Date(consentForm.createdAt), "MMM d, yyyy")}</p>
                      {consentForm.signedAt && (
                        <p className="text-green-600">Signed: {format(new Date(consentForm.signedAt), "MMM d")}</p>
                      )}
                    </div>
                    {consentForm.status === "pending" && (
                      <Button
                        size="sm"
                        onClick={() => signConsentMutation.mutate(consentForm.id)}
                        disabled={signConsentMutation.isPending}
                        data-testid={`button-sign-${consentForm.id}`}
                      >
                        Mark Signed
                      </Button>
                    )}
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
