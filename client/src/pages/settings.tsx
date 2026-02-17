import { useState, useEffect } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { apiRequest, queryClient } from "@/lib/queryClient";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Settings, Building2, Shield, Bell, Database, User, CreditCard, Save } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { useToast } from "@/hooks/use-toast";
import type { PracticeSettings } from "@shared/schema";

export default function SettingsPage() {
  const { user } = useAuth();
  const { toast } = useToast();

  const { data: settings, isLoading } = useQuery<PracticeSettings>({
    queryKey: ["/api/practice-settings"],
  });

  const [practiceName, setPracticeName] = useState("");
  const [practicePhone, setPracticePhone] = useState("");
  const [practiceEmail, setPracticeEmail] = useState("");
  const [address, setAddress] = useState("");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [zipCode, setZipCode] = useState("");
  const [npiNumber, setNpiNumber] = useState("");
  const [taxId, setTaxId] = useState("");
  const [website, setWebsite] = useState("");
  const [providerName, setProviderName] = useState("");
  const [providerTitle, setProviderTitle] = useState("");
  const [providerLicense, setProviderLicense] = useState("");
  const [providerSpecialty, setProviderSpecialty] = useState("");
  const [providerNpi, setProviderNpi] = useState("");
  const [billingContactName, setBillingContactName] = useState("");
  const [billingContactEmail, setBillingContactEmail] = useState("");
  const [defaultBillingType, setDefaultBillingType] = useState("medical");

  useEffect(() => {
    if (settings) {
      setPracticeName(settings.practiceName || "");
      setPracticePhone(settings.phone || "");
      setPracticeEmail(settings.email || "");
      setAddress(settings.address || "");
      setCity(settings.city || "");
      setState(settings.state || "");
      setZipCode(settings.zipCode || "");
      setNpiNumber(settings.npiNumber || "");
      setTaxId(settings.taxId || "");
      setWebsite(settings.website || "");
      setProviderName(settings.providerName || "");
      setProviderTitle(settings.providerTitle || "");
      setProviderLicense(settings.providerLicense || "");
      setProviderSpecialty(settings.providerSpecialty || "");
      setProviderNpi(settings.providerNpi || "");
      setBillingContactName(settings.billingContactName || "");
      setBillingContactEmail(settings.billingContactEmail || "");
      setDefaultBillingType(settings.defaultBillingType || "medical");
    }
  }, [settings]);

  const saveMutation = useMutation({
    mutationFn: async (data: any) => {
      const res = await apiRequest("PATCH", "/api/practice-settings", data);
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/practice-settings"] });
      toast({ title: "Settings saved successfully" });
    },
    onError: () => {
      toast({ title: "Failed to save settings", variant: "destructive" });
    },
  });

  const handleSavePractice = () => {
    saveMutation.mutate({
      practiceName,
      phone: practicePhone,
      email: practiceEmail,
      address,
      city,
      state,
      zipCode,
      npiNumber,
      taxId,
      website,
    });
  };

  const handleSaveProvider = () => {
    saveMutation.mutate({
      providerName,
      providerTitle,
      providerLicense,
      providerSpecialty,
      providerNpi,
    });
  };

  const handleSaveBilling = () => {
    saveMutation.mutate({
      billingContactName,
      billingContactEmail,
      defaultBillingType,
    });
  };

  return (
    <div className="space-y-6" data-testid="settings-page">
      <div>
        <h1 className="text-3xl font-bold flex items-center gap-2" data-testid="text-page-title">
          <Settings className="h-8 w-8 text-primary" />
          Settings
        </h1>
        <p className="text-muted-foreground">Manage your practice and application settings</p>
      </div>

      <div className="grid gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Building2 className="h-5 w-5" />
              Practice Information
            </CardTitle>
            <CardDescription>Basic information about your dental practice</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Practice Name</Label>
                <Input value={practiceName} onChange={(e) => setPracticeName(e.target.value)} placeholder="Practice name" data-testid="input-practice-name" />
              </div>
              <div className="space-y-2">
                <Label>Phone</Label>
                <Input value={practicePhone} onChange={(e) => setPracticePhone(e.target.value)} placeholder="(555) 123-4567" data-testid="input-phone" />
              </div>
              <div className="space-y-2">
                <Label>Email</Label>
                <Input value={practiceEmail} onChange={(e) => setPracticeEmail(e.target.value)} placeholder="info@practice.com" data-testid="input-email" />
              </div>
              <div className="space-y-2">
                <Label>Website</Label>
                <Input value={website} onChange={(e) => setWebsite(e.target.value)} placeholder="www.practice.com" data-testid="input-website" />
              </div>
              <div className="md:col-span-2 space-y-2">
                <Label>Address</Label>
                <Input value={address} onChange={(e) => setAddress(e.target.value)} placeholder="Street address" data-testid="input-address" />
              </div>
              <div className="space-y-2">
                <Label>City</Label>
                <Input value={city} onChange={(e) => setCity(e.target.value)} placeholder="City" data-testid="input-city" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>State</Label>
                  <Input value={state} onChange={(e) => setState(e.target.value)} placeholder="CA" data-testid="input-state" />
                </div>
                <div className="space-y-2">
                  <Label>ZIP</Label>
                  <Input value={zipCode} onChange={(e) => setZipCode(e.target.value)} placeholder="90210" data-testid="input-zip" />
                </div>
              </div>
              <div className="space-y-2">
                <Label>Practice NPI</Label>
                <Input value={npiNumber} onChange={(e) => setNpiNumber(e.target.value)} placeholder="1234567890" data-testid="input-npi" />
              </div>
              <div className="space-y-2">
                <Label>Tax ID (EIN)</Label>
                <Input value={taxId} onChange={(e) => setTaxId(e.target.value)} placeholder="12-3456789" data-testid="input-tax-id" />
              </div>
            </div>
            <Button onClick={handleSavePractice} disabled={saveMutation.isPending} data-testid="button-save-practice">
              <Save className="w-4 h-4 mr-2" />
              {saveMutation.isPending ? "Saving..." : "Save Practice Info"}
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <User className="h-5 w-5" />
              Provider Profile
            </CardTitle>
            <CardDescription>Your professional credentials and specialty</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Provider Name</Label>
                <Input value={providerName} onChange={(e) => setProviderName(e.target.value)} placeholder="Dr. Jane Smith" data-testid="input-provider-name" />
              </div>
              <div className="space-y-2">
                <Label>Title / Degree</Label>
                <Select value={providerTitle} onValueChange={setProviderTitle}>
                  <SelectTrigger data-testid="select-provider-title">
                    <SelectValue placeholder="Select title" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="DDS">DDS</SelectItem>
                    <SelectItem value="DMD">DMD</SelectItem>
                    <SelectItem value="MD">MD</SelectItem>
                    <SelectItem value="DO">DO</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Specialty</Label>
                <Input value={providerSpecialty} onChange={(e) => setProviderSpecialty(e.target.value)} placeholder="Implant Dentistry" data-testid="input-provider-specialty" />
              </div>
              <div className="space-y-2">
                <Label>License Number</Label>
                <Input value={providerLicense} onChange={(e) => setProviderLicense(e.target.value)} placeholder="State license" data-testid="input-provider-license" />
              </div>
              <div className="space-y-2">
                <Label>Provider NPI</Label>
                <Input value={providerNpi} onChange={(e) => setProviderNpi(e.target.value)} placeholder="Individual NPI" data-testid="input-provider-npi" />
              </div>
            </div>
            <Button onClick={handleSaveProvider} disabled={saveMutation.isPending} data-testid="button-save-provider">
              <Save className="w-4 h-4 mr-2" />
              {saveMutation.isPending ? "Saving..." : "Save Provider Info"}
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <CreditCard className="h-5 w-5" />
              Billing Configuration
            </CardTitle>
            <CardDescription>Default billing preferences</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Billing Contact</Label>
                <Input value={billingContactName} onChange={(e) => setBillingContactName(e.target.value)} placeholder="Billing manager" data-testid="input-billing-contact" />
              </div>
              <div className="space-y-2">
                <Label>Billing Email</Label>
                <Input value={billingContactEmail} onChange={(e) => setBillingContactEmail(e.target.value)} placeholder="billing@practice.com" data-testid="input-billing-email" />
              </div>
              <div className="space-y-2">
                <Label>Default Billing Approach</Label>
                <Select value={defaultBillingType} onValueChange={setDefaultBillingType}>
                  <SelectTrigger data-testid="select-billing-type">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="medical">Medical Billing</SelectItem>
                    <SelectItem value="dental">Dental Billing</SelectItem>
                    <SelectItem value="dual">Dual Medical + Dental</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <Button onClick={handleSaveBilling} disabled={saveMutation.isPending} data-testid="button-save-billing">
              <Save className="w-4 h-4 mr-2" />
              {saveMutation.isPending ? "Saving..." : "Save Billing Settings"}
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Shield className="h-5 w-5" />
              HIPAA Compliance
            </CardTitle>
            <CardDescription>Security and compliance settings</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div>
                <p className="font-medium">Session Timeout</p>
                <p className="text-sm text-muted-foreground">Auto-logout after 15 minutes of inactivity</p>
              </div>
              <Switch defaultChecked disabled data-testid="switch-session-timeout" />
            </div>
            <Separator />
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div>
                <p className="font-medium">Audit Logging</p>
                <p className="text-sm text-muted-foreground">Track all PHI access for compliance</p>
              </div>
              <Switch defaultChecked disabled data-testid="switch-audit-logging" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="h-5 w-5" />
              Account
            </CardTitle>
            <CardDescription>Your account information</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div>
                <p className="font-medium">Logged in as</p>
                <p className="text-sm text-muted-foreground" data-testid="text-user-email">{user?.email || "Unknown user"}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
