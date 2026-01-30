import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/hooks/use-toast";
import { queryClient, apiRequest } from "@/lib/queryClient";
import { 
  Plus, 
  Users, 
  Building2, 
  Mail, 
  Phone, 
  FileText, 
  Send, 
  Clock,
  CheckCircle2,
  Loader2,
  Search,
  UserCheck,
  Stethoscope,
  Smile,
  Building
} from "lucide-react";
import type { ReferringProvider, CareReport, Patient } from "@shared/schema";

export default function ProvidersPage() {
  const { toast } = useToast();
  const [showProviderDialog, setShowProviderDialog] = useState(false);
  const [showReportDialog, setShowReportDialog] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<ReferringProvider | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  
  const [providerForm, setProviderForm] = useState({
    providerType: "dentist",
    firstName: "",
    lastName: "",
    practiceName: "",
    specialty: "",
    email: "",
    phone: "",
    fax: "",
    address: "",
    npi: "",
    notes: ""
  });
  
  const [reportForm, setReportForm] = useState({
    patientId: 0,
    recipientProviderId: 0,
    reportType: "treatment_update",
    reportDate: new Date().toISOString().split('T')[0],
    summary: "",
    treatmentProvided: "",
    currentStatus: "",
    recommendedFollowUp: ""
  });

  const { data: providers = [], isLoading: loadingProviders } = useQuery<ReferringProvider[]>({
    queryKey: ["/api/referring-providers"]
  });

  const { data: patients = [] } = useQuery<Patient[]>({
    queryKey: ["/api/patients"]
  });

  const createProviderMutation = useMutation({
    mutationFn: async (data: typeof providerForm) => {
      const res = await apiRequest("POST", "/api/referring-providers", data);
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/referring-providers"] });
      setShowProviderDialog(false);
      resetProviderForm();
      toast({ title: "Provider added successfully" });
    },
    onError: (error: Error) => {
      toast({ title: "Error", description: error.message, variant: "destructive" });
    }
  });

  const updateProviderMutation = useMutation({
    mutationFn: async ({ id, data }: { id: number; data: Partial<typeof providerForm> }) => {
      const res = await apiRequest("PATCH", `/api/referring-providers/${id}`, data);
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/referring-providers"] });
      setShowProviderDialog(false);
      setSelectedProvider(null);
      resetProviderForm();
      toast({ title: "Provider updated successfully" });
    },
    onError: (error: Error) => {
      toast({ title: "Error", description: error.message, variant: "destructive" });
    }
  });

  const createReportMutation = useMutation({
    mutationFn: async (data: typeof reportForm) => {
      const res = await apiRequest("POST", "/api/care-reports", data);
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/care-reports"] });
      setShowReportDialog(false);
      resetReportForm();
      toast({ title: "Care report created successfully" });
    },
    onError: (error: Error) => {
      toast({ title: "Error", description: error.message, variant: "destructive" });
    }
  });

  const resetProviderForm = () => {
    setProviderForm({
      providerType: "dentist",
      firstName: "",
      lastName: "",
      practiceName: "",
      specialty: "",
      email: "",
      phone: "",
      fax: "",
      address: "",
      npi: "",
      notes: ""
    });
  };

  const resetReportForm = () => {
    setReportForm({
      patientId: 0,
      recipientProviderId: 0,
      reportType: "treatment_update",
      reportDate: new Date().toISOString().split('T')[0],
      summary: "",
      treatmentProvided: "",
      currentStatus: "",
      recommendedFollowUp: ""
    });
  };

  const handleEditProvider = (provider: ReferringProvider) => {
    setSelectedProvider(provider);
    setProviderForm({
      providerType: provider.providerType || "dentist",
      firstName: provider.firstName || "",
      lastName: provider.lastName || "",
      practiceName: provider.practiceName || "",
      specialty: provider.specialty || "",
      email: provider.email || "",
      phone: provider.phone || "",
      fax: provider.fax || "",
      address: provider.address || "",
      npi: provider.npi || "",
      notes: provider.notes || ""
    });
    setShowProviderDialog(true);
  };

  const handleSaveProvider = () => {
    if (selectedProvider) {
      updateProviderMutation.mutate({ id: selectedProvider.id, data: providerForm });
    } else {
      createProviderMutation.mutate(providerForm);
    }
  };

  const filteredProviders = providers.filter(p => {
    const search = searchQuery.toLowerCase();
    return (
      p.firstName.toLowerCase().includes(search) ||
      p.lastName.toLowerCase().includes(search) ||
      (p.practiceName?.toLowerCase().includes(search) ?? false) ||
      (p.specialty?.toLowerCase().includes(search) ?? false)
    );
  });

  const dentists = filteredProviders.filter(p => p.providerType === "dentist");
  const orthodontists = filteredProviders.filter(p => p.providerType === "orthodontist");
  const physicians = filteredProviders.filter(p => p.providerType === "physician");

  const getProviderIcon = (type: string) => {
    switch (type) {
      case "dentist": return <Smile className="h-5 w-5 text-primary" />;
      case "orthodontist": return <Building className="h-5 w-5 text-blue-500" />;
      case "physician": return <Stethoscope className="h-5 w-5 text-green-500" />;
      default: return <UserCheck className="h-5 w-5" />;
    }
  };

  if (loadingProviders) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 overflow-y-auto max-h-[calc(100vh-80px)]">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold" data-testid="text-page-title">Provider Portal</h1>
          <p className="text-muted-foreground">
            Manage referring providers and send continuity of care reports
          </p>
        </div>
        <div className="flex gap-3">
          <Button 
            variant="outline"
            onClick={() => setShowReportDialog(true)}
            data-testid="button-new-report"
          >
            <FileText className="mr-2 h-4 w-4" />
            Send Care Report
          </Button>
          <Button 
            onClick={() => {
              setSelectedProvider(null);
              resetProviderForm();
              setShowProviderDialog(true);
            }}
            data-testid="button-add-provider"
          >
            <Plus className="mr-2 h-4 w-4" />
            Add Provider
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-primary/10 rounded-full">
                <Smile className="h-6 w-6 text-primary" />
              </div>
              <div>
                <p className="text-2xl font-bold" data-testid="text-dentist-count">{dentists.length}</p>
                <p className="text-sm text-muted-foreground">Referring Dentists</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-blue-500/10 rounded-full">
                <Building className="h-6 w-6 text-blue-500" />
              </div>
              <div>
                <p className="text-2xl font-bold" data-testid="text-ortho-count">{orthodontists.length}</p>
                <p className="text-sm text-muted-foreground">Orthodontists</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-green-500/10 rounded-full">
                <Stethoscope className="h-6 w-6 text-green-500" />
              </div>
              <div>
                <p className="text-2xl font-bold" data-testid="text-physician-count">{physicians.length}</p>
                <p className="text-sm text-muted-foreground">Physicians</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Referring Providers</CardTitle>
              <CardDescription>
                Manage referring dentists, orthodontists, and physicians
              </CardDescription>
            </div>
            <div className="relative w-64">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search providers..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
                data-testid="input-search-providers"
              />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="all" className="w-full">
            <TabsList data-testid="tabs-provider-type">
              <TabsTrigger value="all" data-testid="tab-all">All ({filteredProviders.length})</TabsTrigger>
              <TabsTrigger value="dentist" data-testid="tab-dentists">Dentists ({dentists.length})</TabsTrigger>
              <TabsTrigger value="orthodontist" data-testid="tab-orthodontists">Orthodontists ({orthodontists.length})</TabsTrigger>
              <TabsTrigger value="physician" data-testid="tab-physicians">Physicians ({physicians.length})</TabsTrigger>
            </TabsList>
            
            <TabsContent value="all" className="mt-4">
              <ProviderList 
                providers={filteredProviders} 
                onEdit={handleEditProvider}
                getProviderIcon={getProviderIcon}
              />
            </TabsContent>
            <TabsContent value="dentist" className="mt-4">
              <ProviderList 
                providers={dentists} 
                onEdit={handleEditProvider}
                getProviderIcon={getProviderIcon}
              />
            </TabsContent>
            <TabsContent value="orthodontist" className="mt-4">
              <ProviderList 
                providers={orthodontists} 
                onEdit={handleEditProvider}
                getProviderIcon={getProviderIcon}
              />
            </TabsContent>
            <TabsContent value="physician" className="mt-4">
              <ProviderList 
                providers={physicians} 
                onEdit={handleEditProvider}
                getProviderIcon={getProviderIcon}
              />
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      <Dialog open={showProviderDialog} onOpenChange={setShowProviderDialog}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{selectedProvider ? "Edit Provider" : "Add Referring Provider"}</DialogTitle>
            <DialogDescription>
              {selectedProvider ? "Update provider information" : "Add a new referring provider to your network"}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Provider Type</Label>
                <Select
                  value={providerForm.providerType}
                  onValueChange={(value) => setProviderForm(prev => ({ ...prev, providerType: value }))}
                >
                  <SelectTrigger data-testid="select-provider-type">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="dentist">General Dentist</SelectItem>
                    <SelectItem value="orthodontist">Orthodontist</SelectItem>
                    <SelectItem value="physician">Physician</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Specialty</Label>
                <Input
                  value={providerForm.specialty}
                  onChange={(e) => setProviderForm(prev => ({ ...prev, specialty: e.target.value }))}
                  placeholder="e.g., Prosthodontist, Periodontist"
                  data-testid="input-specialty"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>First Name *</Label>
                <Input
                  value={providerForm.firstName}
                  onChange={(e) => setProviderForm(prev => ({ ...prev, firstName: e.target.value }))}
                  data-testid="input-first-name"
                />
              </div>
              <div className="space-y-2">
                <Label>Last Name *</Label>
                <Input
                  value={providerForm.lastName}
                  onChange={(e) => setProviderForm(prev => ({ ...prev, lastName: e.target.value }))}
                  data-testid="input-last-name"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label>Practice Name</Label>
              <Input
                value={providerForm.practiceName}
                onChange={(e) => setProviderForm(prev => ({ ...prev, practiceName: e.target.value }))}
                placeholder="e.g., Bright Smiles Dental"
                data-testid="input-practice-name"
              />
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label>Email</Label>
                <Input
                  type="email"
                  value={providerForm.email}
                  onChange={(e) => setProviderForm(prev => ({ ...prev, email: e.target.value }))}
                  data-testid="input-email"
                />
              </div>
              <div className="space-y-2">
                <Label>Phone</Label>
                <Input
                  value={providerForm.phone}
                  onChange={(e) => setProviderForm(prev => ({ ...prev, phone: e.target.value }))}
                  data-testid="input-phone"
                />
              </div>
              <div className="space-y-2">
                <Label>Fax</Label>
                <Input
                  value={providerForm.fax}
                  onChange={(e) => setProviderForm(prev => ({ ...prev, fax: e.target.value }))}
                  data-testid="input-fax"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label>Address</Label>
              <Input
                value={providerForm.address}
                onChange={(e) => setProviderForm(prev => ({ ...prev, address: e.target.value }))}
                placeholder="Full address"
                data-testid="input-address"
              />
            </div>
            <div className="space-y-2">
              <Label>NPI Number</Label>
              <Input
                value={providerForm.npi}
                onChange={(e) => setProviderForm(prev => ({ ...prev, npi: e.target.value }))}
                placeholder="10-digit NPI"
                data-testid="input-npi"
              />
            </div>
            <div className="space-y-2">
              <Label>Notes</Label>
              <Textarea
                value={providerForm.notes}
                onChange={(e) => setProviderForm(prev => ({ ...prev, notes: e.target.value }))}
                placeholder="Additional notes about this provider"
                data-testid="input-notes"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowProviderDialog(false)} data-testid="button-cancel-provider">
              Cancel
            </Button>
            <Button 
              onClick={handleSaveProvider}
              disabled={!providerForm.firstName || !providerForm.lastName || createProviderMutation.isPending || updateProviderMutation.isPending}
              data-testid="button-save-provider"
            >
              {(createProviderMutation.isPending || updateProviderMutation.isPending) && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              {selectedProvider ? "Update Provider" : "Add Provider"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={showReportDialog} onOpenChange={setShowReportDialog}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Send Continuity of Care Report</DialogTitle>
            <DialogDescription>
              Generate and send a care report to a referring provider
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Patient *</Label>
                <Select
                  value={reportForm.patientId.toString()}
                  onValueChange={(value) => setReportForm(prev => ({ ...prev, patientId: parseInt(value) }))}
                >
                  <SelectTrigger data-testid="select-report-patient">
                    <SelectValue placeholder="Select patient" />
                  </SelectTrigger>
                  <SelectContent>
                    {patients.map((patient) => (
                      <SelectItem key={patient.id} value={patient.id.toString()}>
                        {patient.firstName} {patient.lastName}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Recipient Provider *</Label>
                <Select
                  value={reportForm.recipientProviderId.toString()}
                  onValueChange={(value) => setReportForm(prev => ({ ...prev, recipientProviderId: parseInt(value) }))}
                >
                  <SelectTrigger data-testid="select-report-provider">
                    <SelectValue placeholder="Select provider" />
                  </SelectTrigger>
                  <SelectContent>
                    {providers.map((provider) => (
                      <SelectItem key={provider.id} value={provider.id.toString()}>
                        Dr. {provider.firstName} {provider.lastName} - {provider.practiceName || provider.specialty}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Report Type *</Label>
                <Select
                  value={reportForm.reportType}
                  onValueChange={(value) => setReportForm(prev => ({ ...prev, reportType: value }))}
                >
                  <SelectTrigger data-testid="select-report-type">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="treatment_update">Treatment Update</SelectItem>
                    <SelectItem value="surgery_complete">Surgery Complete</SelectItem>
                    <SelectItem value="final_restoration">Final Restoration</SelectItem>
                    <SelectItem value="follow_up">Follow-Up Summary</SelectItem>
                    <SelectItem value="referral_response">Referral Response</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Report Date *</Label>
                <Input
                  type="date"
                  value={reportForm.reportDate}
                  onChange={(e) => setReportForm(prev => ({ ...prev, reportDate: e.target.value }))}
                  data-testid="input-report-date"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label>Summary *</Label>
              <Textarea
                value={reportForm.summary}
                onChange={(e) => setReportForm(prev => ({ ...prev, summary: e.target.value }))}
                placeholder="Brief summary of the patient's current status (required)"
                data-testid="input-report-summary"
              />
            </div>
            <div className="space-y-2">
              <Label>Treatment Provided</Label>
              <Textarea
                value={reportForm.treatmentProvided}
                onChange={(e) => setReportForm(prev => ({ ...prev, treatmentProvided: e.target.value }))}
                placeholder="Describe the treatment provided"
                data-testid="input-treatment-provided"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Current Status</Label>
                <Input
                  value={reportForm.currentStatus}
                  onChange={(e) => setReportForm(prev => ({ ...prev, currentStatus: e.target.value }))}
                  placeholder="e.g., Healing well, Ready for restoration"
                  data-testid="input-current-status"
                />
              </div>
              <div className="space-y-2">
                <Label>Recommended Follow-Up</Label>
                <Input
                  value={reportForm.recommendedFollowUp}
                  onChange={(e) => setReportForm(prev => ({ ...prev, recommendedFollowUp: e.target.value }))}
                  placeholder="e.g., Hygiene visits q3 months"
                  data-testid="input-follow-up"
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowReportDialog(false)} data-testid="button-cancel-report">
              Cancel
            </Button>
            <Button 
              onClick={() => createReportMutation.mutate(reportForm)}
              disabled={
                !reportForm.patientId || 
                !reportForm.recipientProviderId || 
                !reportForm.reportDate ||
                !reportForm.reportType ||
                !reportForm.summary.trim() ||
                createReportMutation.isPending
              }
              data-testid="button-send-report"
            >
              {createReportMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              <Send className="mr-2 h-4 w-4" />
              Send Report
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function ProviderList({ 
  providers, 
  onEdit,
  getProviderIcon
}: { 
  providers: ReferringProvider[]; 
  onEdit: (p: ReferringProvider) => void;
  getProviderIcon: (type: string) => JSX.Element;
}) {
  if (providers.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground" data-testid="text-no-providers">
        <Users className="h-12 w-12 mx-auto mb-4 opacity-50" />
        <p>No providers found</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {providers.map((provider) => (
        <div 
          key={provider.id} 
          className="flex items-center justify-between p-4 border rounded-lg"
          data-testid={`card-provider-${provider.id}`}
        >
          <div className="flex items-center gap-4">
            {getProviderIcon(provider.providerType)}
            <div>
              <div className="flex items-center gap-2">
                <p className="font-medium" data-testid={`text-provider-name-${provider.id}`}>
                  Dr. {provider.firstName} {provider.lastName}
                </p>
                <Badge variant="outline" className="text-xs">
                  {provider.providerType}
                </Badge>
              </div>
              <div className="flex items-center gap-4 text-sm text-muted-foreground">
                {provider.practiceName && (
                  <span className="flex items-center gap-1">
                    <Building2 className="h-3 w-3" />
                    {provider.practiceName}
                  </span>
                )}
                {provider.specialty && (
                  <span>{provider.specialty}</span>
                )}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-4 text-sm text-muted-foreground">
              {provider.email && (
                <span className="flex items-center gap-1" data-testid={`text-provider-email-${provider.id}`}>
                  <Mail className="h-3 w-3" />
                  {provider.email}
                </span>
              )}
              {provider.phone && (
                <span className="flex items-center gap-1" data-testid={`text-provider-phone-${provider.id}`}>
                  <Phone className="h-3 w-3" />
                  {provider.phone}
                </span>
              )}
            </div>
            <Button 
              variant="outline" 
              size="sm"
              onClick={() => onEdit(provider)}
              data-testid={`button-edit-provider-${provider.id}`}
            >
              Edit
            </Button>
          </div>
        </div>
      ))}
    </div>
  );
}
