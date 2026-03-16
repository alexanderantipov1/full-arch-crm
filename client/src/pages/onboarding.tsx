import { useState, useEffect } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { apiRequest, queryClient } from "@/lib/queryClient";
import { useLocation } from "wouter";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import {
  Building2,
  User,
  CreditCard,
  Users,
  CheckCircle2,
  ArrowRight,
  ArrowLeft,
  Stethoscope,
  Phone,
  Mail,
  MapPin,
  Globe,
  Shield,
  FileText,
  ChevronRight,
  Sparkles,
  Loader2,
  Star,
  ChevronDown,
} from "lucide-react";
import type { PracticeSettings } from "@shared/schema";

const STEPS = [
  { id: 0, title: "Welcome", icon: Building2, description: "Let's get started" },
  { id: 1, title: "Practice Info", icon: Building2, description: "Your practice details" },
  { id: 2, title: "Provider Profile", icon: User, description: "Your credentials" },
  { id: 3, title: "Billing Setup", icon: CreditCard, description: "Billing preferences" },
  { id: 4, title: "Team", icon: Users, description: "Invite your team" },
  { id: 5, title: "Complete", icon: CheckCircle2, description: "You're all set" },
];

const SPECIALTIES = [
  "Prosthodontics",
  "Oral & Maxillofacial Surgery",
  "Periodontics",
  "General Dentistry",
  "Implant Dentistry",
  "Cosmetic Dentistry",
];

const SPECIALTY_OPTIONS = [
  { value: "Oral & Maxillofacial Surgeon", label: "Oral & Maxillofacial Surgery", emoji: "🦷", desc: "Extractions, implants, jaw surgery" },
  { value: "Orthodontist", label: "Orthodontics", emoji: "😁", desc: "Braces, aligners, retention" },
  { value: "Endodontist", label: "Endodontics", emoji: "🔬", desc: "Root canals, pulp therapy" },
  { value: "Periodontist", label: "Periodontics", emoji: "📊", desc: "Gum disease, perio surgery" },
  { value: "Pediatric Dentist", label: "Pediatric Dentistry", emoji: "👶", desc: "Children's dental care" },
  { value: "Prosthodontist", label: "Prosthodontics", emoji: "👑", desc: "Crowns, bridges, full arch restorations" },
  { value: "Implant Specialist", label: "Dental Implant Specialist", emoji: "🏆", desc: "All-on-4, All-on-6, implants" },
  { value: "Multi-Specialty Group / DSO", label: "Multi-Specialty / DSO", emoji: "🏢", desc: "Group practice or DSO" },
];

const PAYER_OPTIONS = [
  "Delta Dental",
  "Cigna",
  "MetLife",
  "Aetna",
  "UnitedHealthcare",
  "Guardian",
  "Humana",
  "BCBS",
  "Medicare",
  "Medicaid",
];

export default function OnboardingPage() {
  const [, setLocation] = useLocation();
  const { toast } = useToast();
  const [step, setStep] = useState(0);

  const [practiceName, setPracticeName] = useState("");
  const [practiceType, setPracticeType] = useState("dental_implant");
  const [address, setAddress] = useState("");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [zipCode, setZipCode] = useState("");
  const [practicePhone, setPracticePhone] = useState("");
  const [practiceEmail, setPracticeEmail] = useState("");
  const [website, setWebsite] = useState("");
  const [npiNumber, setNpiNumber] = useState("");
  const [taxId, setTaxId] = useState("");

  const [specialtyCategory, setSpecialtyCategory] = useState<"" | "general" | "specialist">("");
  const [selectedSpecialtyOption, setSelectedSpecialtyOption] = useState("");
  const [aiRecommendations, setAiRecommendations] = useState<{ welcome: string; modules: { title: string; url: string; reason: string }[] } | null>(null);
  const [aiLoading, setAiLoading] = useState(false);

  const [providerName, setProviderName] = useState("");
  const [providerTitle, setProviderTitle] = useState("DDS");
  const [providerLicense, setProviderLicense] = useState("");
  const [providerSpecialty, setProviderSpecialty] = useState("");
  const [providerNpi, setProviderNpi] = useState("");

  const [billingContactName, setBillingContactName] = useState("");
  const [billingContactEmail, setBillingContactEmail] = useState("");
  const [billingContactPhone, setBillingContactPhone] = useState("");
  const [defaultBillingType, setDefaultBillingType] = useState("medical");
  const [selectedPayers, setSelectedPayers] = useState<string[]>([]);

  const { data: existingSettings } = useQuery<PracticeSettings>({
    queryKey: ["/api/practice-settings"],
  });

  useEffect(() => {
    if (existingSettings) {
      if (existingSettings.onboardingStep && existingSettings.onboardingStep > 0) {
        setStep(existingSettings.onboardingStep);
      }
      setPracticeName(existingSettings.practiceName || "");
      setPracticeType(existingSettings.practiceType || "dental_implant");
      setAddress(existingSettings.address || "");
      setCity(existingSettings.city || "");
      setState(existingSettings.state || "");
      setZipCode(existingSettings.zipCode || "");
      setPracticePhone(existingSettings.phone || "");
      setPracticeEmail(existingSettings.email || "");
      setWebsite(existingSettings.website || "");
      setNpiNumber(existingSettings.npiNumber || "");
      setTaxId(existingSettings.taxId || "");
      setProviderName(existingSettings.providerName || "");
      setProviderTitle(existingSettings.providerTitle || "DDS");
      setProviderLicense(existingSettings.providerLicense || "");
      setProviderSpecialty(existingSettings.providerSpecialty || "");
      setProviderNpi(existingSettings.providerNpi || "");
      setBillingContactName(existingSettings.billingContactName || "");
      setBillingContactEmail(existingSettings.billingContactEmail || "");
      setBillingContactPhone(existingSettings.billingContactPhone || "");
      setDefaultBillingType(existingSettings.defaultBillingType || "medical");
      setSelectedPayers(existingSettings.primaryPayers || []);
    }
  }, [existingSettings]);

  const saveMutation = useMutation({
    mutationFn: async (data: any) => {
      const res = await apiRequest("POST", "/api/practice-settings", data);
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/practice-settings"] });
      queryClient.invalidateQueries({ queryKey: ["/api/onboarding/status"] });
    },
  });

  const completeMutation = useMutation({
    mutationFn: async () => {
      const res = await apiRequest("POST", "/api/onboarding/complete", {});
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/onboarding/status"] });
      queryClient.invalidateQueries({ queryKey: ["/api/practice-settings"] });
      toast({ title: "Practice setup complete!" });
      setLocation("/");
    },
  });

  const fetchSpecialtyRecommendations = async (specialty: string) => {
    setAiLoading(true);
    try {
      const res = await fetch("/api/ai/specialty-recommendations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ specialty }),
      });
      const data = await res.json();
      setAiRecommendations(data);
      localStorage.setItem("specialty_recommendations", JSON.stringify(data));
    } catch {
      // silently fail
    } finally {
      setAiLoading(false);
    }
  };

  const saveStepAndAdvance = async (nextStep: number) => {
    const data: any = { onboardingStep: nextStep };

    if (step === 0 && (specialtyCategory === "general" || selectedSpecialtyOption)) {
      const specialty = specialtyCategory === "general" ? "General Dentist" : selectedSpecialtyOption;
      data.providerSpecialty = specialty;
      data.practiceType = specialtyCategory === "general" ? "general" : "dental_implant";
    }

    if (step === 1) {
      data.practiceName = practiceName;
      data.practiceType = practiceType;
      data.address = address;
      data.city = city;
      data.state = state;
      data.zipCode = zipCode;
      data.phone = practicePhone;
      data.email = practiceEmail;
      data.website = website;
      data.npiNumber = npiNumber;
      data.taxId = taxId;
    } else if (step === 2) {
      data.providerName = providerName;
      data.providerTitle = providerTitle;
      data.providerLicense = providerLicense;
      data.providerSpecialty = providerSpecialty;
      data.providerNpi = providerNpi;
    } else if (step === 3) {
      data.billingContactName = billingContactName;
      data.billingContactEmail = billingContactEmail;
      data.billingContactPhone = billingContactPhone;
      data.defaultBillingType = defaultBillingType;
      data.primaryPayers = selectedPayers;
    }

    if (step >= 0 && step <= 3) {
      try {
        await saveMutation.mutateAsync(data);
      } catch {
        toast({ title: "Failed to save. Please try again.", variant: "destructive" });
        return;
      }
    }

    setStep(nextStep);
  };

  const togglePayer = (payer: string) => {
    setSelectedPayers((prev) =>
      prev.includes(payer) ? prev.filter((p) => p !== payer) : [...prev, payer]
    );
  };

  return (
    <div className="min-h-screen bg-background flex flex-col" data-testid="onboarding-page">
      <div className="flex-1 flex flex-col items-center justify-center p-4 sm:p-8">
        {step > 0 && step < 5 && (
          <div className="w-full max-w-2xl mb-8">
            <div className="flex items-center justify-between mb-2">
              {STEPS.slice(1, 5).map((s) => (
                <div key={s.id} className="flex items-center gap-1 flex-1">
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium transition-colors ${
                      s.id <= step
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted text-muted-foreground"
                    }`}
                  >
                    {s.id < step ? <CheckCircle2 className="w-4 h-4" /> : s.id}
                  </div>
                  <span className="text-xs text-muted-foreground hidden sm:block">{s.title}</span>
                  {s.id < 4 && <div className={`flex-1 h-0.5 mx-2 ${s.id < step ? "bg-primary" : "bg-muted"}`} />}
                </div>
              ))}
            </div>
          </div>
        )}

        <Card className="w-full max-w-2xl">
          <CardContent className="p-6 sm:p-8">
            {step === 0 && (
              <div className="space-y-6" data-testid="step-welcome">
                <div className="text-center space-y-2">
                  <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mx-auto">
                    <Stethoscope className="w-8 h-8 text-primary" />
                  </div>
                  <h1 className="text-2xl sm:text-3xl font-bold">Welcome, Doctor!</h1>
                  <p className="text-muted-foreground text-sm sm:text-base max-w-md mx-auto">
                    Tell us about your practice so we can personalize your platform with AI.
                  </p>
                </div>

                {/* Category selection */}
                {!specialtyCategory && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
                    <button
                      onClick={() => {
                        setSpecialtyCategory("general");
                        setSelectedSpecialtyOption("");
                        fetchSpecialtyRecommendations("General Dentist");
                      }}
                      className="group rounded-xl border-2 border-border hover:border-primary p-6 text-left transition-all"
                      data-testid="btn-general-dentist"
                    >
                      <div className="text-3xl mb-2">🦷</div>
                      <div className="font-semibold text-base">General Dentist</div>
                      <div className="text-xs text-muted-foreground mt-1">Comprehensive family & general dental care</div>
                    </button>
                    <button
                      onClick={() => setSpecialtyCategory("specialist")}
                      className="group rounded-xl border-2 border-border hover:border-primary p-6 text-left transition-all"
                      data-testid="btn-specialist"
                    >
                      <div className="text-3xl mb-2">⚕️</div>
                      <div className="font-semibold text-base">Specialist</div>
                      <div className="text-xs text-muted-foreground mt-1">Select your specialty for a tailored experience</div>
                      <div className="flex items-center gap-1 mt-2 text-primary text-xs font-medium">
                        Choose specialty <ChevronDown className="h-3 w-3" />
                      </div>
                    </button>
                  </div>
                )}

                {/* Specialist sub-selection */}
                {specialtyCategory === "specialist" && !selectedSpecialtyOption && (
                  <div className="space-y-3">
                    <div className="flex items-center gap-2">
                      <button onClick={() => setSpecialtyCategory("")} className="text-xs text-muted-foreground hover:text-foreground">← Back</button>
                      <p className="text-sm font-medium">Select your specialty:</p>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                      {SPECIALTY_OPTIONS.map(opt => (
                        <button
                          key={opt.value}
                          onClick={() => {
                            setSelectedSpecialtyOption(opt.value);
                            fetchSpecialtyRecommendations(opt.value);
                          }}
                          className="flex items-start gap-3 rounded-lg border border-border hover:border-primary p-3 text-left transition-all"
                          data-testid={`specialty-${opt.value.replace(/[^a-z]/gi, "-").toLowerCase()}`}
                        >
                          <span className="text-xl shrink-0">{opt.emoji}</span>
                          <div>
                            <div className="font-medium text-sm">{opt.label}</div>
                            <div className="text-[11px] text-muted-foreground">{opt.desc}</div>
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* AI Recommendation Card */}
                {(specialtyCategory === "general" || selectedSpecialtyOption) && (
                  <div className="space-y-4">
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <button onClick={() => { setSpecialtyCategory(""); setSelectedSpecialtyOption(""); setAiRecommendations(null); }} className="hover:text-foreground">← Change</button>
                      <span>·</span>
                      <span className="font-medium text-foreground">
                        {specialtyCategory === "general" ? "🦷 General Dentist" : SPECIALTY_OPTIONS.find(o => o.value === selectedSpecialtyOption)?.emoji + " " + selectedSpecialtyOption}
                      </span>
                    </div>

                    <div className="rounded-xl border border-primary/30 bg-primary/5 p-4 space-y-3">
                      <div className="flex items-start gap-2">
                        <Sparkles className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                        <div>
                          {aiLoading ? (
                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                              <Loader2 className="h-3.5 w-3.5 animate-spin" /> AI is personalizing your platform…
                            </div>
                          ) : aiRecommendations ? (
                            <>
                              <p className="text-sm font-medium">{aiRecommendations.welcome}</p>
                              {aiRecommendations.modules.length > 0 && (
                                <div className="mt-3">
                                  <p className="text-xs text-muted-foreground mb-2 font-medium uppercase tracking-wider">Your recommended modules</p>
                                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5">
                                    {aiRecommendations.modules.slice(0, 6).map(m => (
                                      <div key={m.url} className="bg-background rounded-lg border px-2.5 py-1.5">
                                        <div className="font-medium text-xs">{m.title}</div>
                                        <div className="text-[10px] text-muted-foreground line-clamp-1">{m.reason}</div>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </>
                          ) : (
                            <p className="text-sm text-muted-foreground">Your platform is being personalized…</p>
                          )}
                        </div>
                      </div>
                    </div>

                    <Button
                      size="lg"
                      className="w-full"
                      onClick={() => saveStepAndAdvance(1)}
                      disabled={saveMutation.isPending || aiLoading}
                      data-testid="button-get-started"
                    >
                      {saveMutation.isPending ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                      Continue Setup
                      <ArrowRight className="w-4 h-4 ml-2" />
                    </Button>
                  </div>
                )}
              </div>
            )}

            {step === 1 && (
              <div className="space-y-6" data-testid="step-practice-info">
                <div className="space-y-1">
                  <h2 className="text-xl font-semibold flex items-center gap-2">
                    <Building2 className="w-5 h-5 text-primary" />
                    Practice Information
                  </h2>
                  <p className="text-sm text-muted-foreground">Tell us about your dental practice</p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="sm:col-span-2 space-y-1.5">
                    <label className="text-sm font-medium">Practice Name *</label>
                    <Input
                      value={practiceName}
                      onChange={(e) => setPracticeName(e.target.value)}
                      placeholder="e.g., Advanced Dental Implant Center"
                      data-testid="input-practice-name"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium">Practice Type</label>
                    <Select value={practiceType} onValueChange={setPracticeType}>
                      <SelectTrigger data-testid="select-practice-type">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="dental_implant">Dental Implant Center</SelectItem>
                        <SelectItem value="oral_surgery">Oral Surgery Practice</SelectItem>
                        <SelectItem value="prosthodontics">Prosthodontics Practice</SelectItem>
                        <SelectItem value="general">General Dental Practice</SelectItem>
                        <SelectItem value="multi_specialty">Multi-Specialty Group</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium flex items-center gap-1">
                      <Phone className="w-3.5 h-3.5" /> Phone
                    </label>
                    <Input
                      value={practicePhone}
                      onChange={(e) => setPracticePhone(e.target.value)}
                      placeholder="(555) 123-4567"
                      data-testid="input-practice-phone"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium flex items-center gap-1">
                      <Mail className="w-3.5 h-3.5" /> Email
                    </label>
                    <Input
                      value={practiceEmail}
                      onChange={(e) => setPracticeEmail(e.target.value)}
                      placeholder="office@practice.com"
                      data-testid="input-practice-email"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium flex items-center gap-1">
                      <Globe className="w-3.5 h-3.5" /> Website
                    </label>
                    <Input
                      value={website}
                      onChange={(e) => setWebsite(e.target.value)}
                      placeholder="www.practice.com"
                      data-testid="input-website"
                    />
                  </div>
                  <div className="sm:col-span-2 space-y-1.5">
                    <label className="text-sm font-medium flex items-center gap-1">
                      <MapPin className="w-3.5 h-3.5" /> Street Address
                    </label>
                    <Input
                      value={address}
                      onChange={(e) => setAddress(e.target.value)}
                      placeholder="123 Main Street, Suite 100"
                      data-testid="input-address"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium">City</label>
                    <Input value={city} onChange={(e) => setCity(e.target.value)} placeholder="City" data-testid="input-city" />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <label className="text-sm font-medium">State</label>
                      <Input value={state} onChange={(e) => setState(e.target.value)} placeholder="CA" data-testid="input-state" />
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-sm font-medium">ZIP</label>
                      <Input value={zipCode} onChange={(e) => setZipCode(e.target.value)} placeholder="90210" data-testid="input-zip" />
                    </div>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium flex items-center gap-1">
                      <Shield className="w-3.5 h-3.5" /> Practice NPI
                    </label>
                    <Input
                      value={npiNumber}
                      onChange={(e) => setNpiNumber(e.target.value)}
                      placeholder="1234567890"
                      data-testid="input-npi"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium flex items-center gap-1">
                      <FileText className="w-3.5 h-3.5" /> Tax ID (EIN)
                    </label>
                    <Input
                      value={taxId}
                      onChange={(e) => setTaxId(e.target.value)}
                      placeholder="12-3456789"
                      data-testid="input-tax-id"
                    />
                  </div>
                </div>
              </div>
            )}

            {step === 2 && (
              <div className="space-y-6" data-testid="step-provider-profile">
                <div className="space-y-1">
                  <h2 className="text-xl font-semibold flex items-center gap-2">
                    <User className="w-5 h-5 text-primary" />
                    Provider Profile
                  </h2>
                  <p className="text-sm text-muted-foreground">Your professional credentials and specialty</p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="sm:col-span-2 space-y-1.5">
                    <label className="text-sm font-medium">Full Name *</label>
                    <Input
                      value={providerName}
                      onChange={(e) => setProviderName(e.target.value)}
                      placeholder="Dr. Jane Smith"
                      data-testid="input-provider-name"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium">Title / Degree</label>
                    <Select value={providerTitle} onValueChange={setProviderTitle}>
                      <SelectTrigger data-testid="select-provider-title">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="DDS">DDS - Doctor of Dental Surgery</SelectItem>
                        <SelectItem value="DMD">DMD - Doctor of Dental Medicine</SelectItem>
                        <SelectItem value="MD">MD - Medical Doctor</SelectItem>
                        <SelectItem value="DO">DO - Doctor of Osteopathic Medicine</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium">Specialty</label>
                    <Select value={providerSpecialty} onValueChange={setProviderSpecialty}>
                      <SelectTrigger data-testid="select-provider-specialty">
                        <SelectValue placeholder="Select specialty" />
                      </SelectTrigger>
                      <SelectContent>
                        {SPECIALTIES.map((s) => (
                          <SelectItem key={s} value={s}>{s}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium">License Number</label>
                    <Input
                      value={providerLicense}
                      onChange={(e) => setProviderLicense(e.target.value)}
                      placeholder="State license number"
                      data-testid="input-provider-license"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium">Provider NPI</label>
                    <Input
                      value={providerNpi}
                      onChange={(e) => setProviderNpi(e.target.value)}
                      placeholder="Individual NPI"
                      data-testid="input-provider-npi"
                    />
                  </div>
                </div>
              </div>
            )}

            {step === 3 && (
              <div className="space-y-6" data-testid="step-billing-setup">
                <div className="space-y-1">
                  <h2 className="text-xl font-semibold flex items-center gap-2">
                    <CreditCard className="w-5 h-5 text-primary" />
                    Billing Setup
                  </h2>
                  <p className="text-sm text-muted-foreground">Configure your billing preferences and primary payers</p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium">Billing Contact Name</label>
                    <Input
                      value={billingContactName}
                      onChange={(e) => setBillingContactName(e.target.value)}
                      placeholder="Billing manager name"
                      data-testid="input-billing-contact-name"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium">Billing Contact Email</label>
                    <Input
                      value={billingContactEmail}
                      onChange={(e) => setBillingContactEmail(e.target.value)}
                      placeholder="billing@practice.com"
                      data-testid="input-billing-contact-email"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium">Billing Contact Phone</label>
                    <Input
                      value={billingContactPhone}
                      onChange={(e) => setBillingContactPhone(e.target.value)}
                      placeholder="(555) 123-4567"
                      data-testid="input-billing-contact-phone"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium">Default Billing Approach</label>
                    <Select value={defaultBillingType} onValueChange={setDefaultBillingType}>
                      <SelectTrigger data-testid="select-billing-type">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="medical">Medical Billing (Recommended for Implants)</SelectItem>
                        <SelectItem value="dental">Dental Billing</SelectItem>
                        <SelectItem value="dual">Dual Medical + Dental</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="space-y-3">
                  <label className="text-sm font-medium">Primary Insurance Payers</label>
                  <p className="text-xs text-muted-foreground">Select the insurance companies you work with most often</p>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                    {PAYER_OPTIONS.map((payer) => (
                      <Button
                        key={payer}
                        variant={selectedPayers.includes(payer) ? "default" : "outline"}
                        size="sm"
                        onClick={() => togglePayer(payer)}
                        className="justify-start"
                        data-testid={`button-payer-${payer.toLowerCase().replace(/\s+/g, "-")}`}
                      >
                        {selectedPayers.includes(payer) && <CheckCircle2 className="w-3.5 h-3.5 mr-1.5" />}
                        {payer}
                      </Button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {step === 4 && (
              <div className="space-y-6" data-testid="step-team">
                <div className="space-y-1">
                  <h2 className="text-xl font-semibold flex items-center gap-2">
                    <Users className="w-5 h-5 text-primary" />
                    Team Members
                  </h2>
                  <p className="text-sm text-muted-foreground">Invite your staff to join the platform</p>
                </div>

                <div className="bg-muted/50 rounded-md p-6 text-center space-y-3">
                  <Users className="w-12 h-12 text-muted-foreground mx-auto" />
                  <p className="text-sm text-muted-foreground">
                    Team members can sign in with their own accounts after you complete setup. You can manage team roles and permissions from the Administration section.
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Each team member will get their own login and can be assigned specific roles (Front Desk, Billing Specialist, Clinical Staff, etc.)
                  </p>
                </div>
              </div>
            )}

            {step === 5 && (
              <div className="text-center space-y-6" data-testid="step-complete">
                <div className="w-20 h-20 bg-green-500/10 rounded-full flex items-center justify-center mx-auto">
                  <CheckCircle2 className="w-10 h-10 text-green-500" />
                </div>
                <div className="space-y-2">
                  <h2 className="text-2xl font-bold">You're All Set!</h2>
                  <p className="text-muted-foreground max-w-md mx-auto">
                    Your practice is ready to go. You can start adding patients, creating treatment plans, and managing billing right away.
                  </p>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
                  <div className="p-3 rounded-md bg-muted/50 text-left">
                    <div className="flex items-center gap-2 mb-1">
                      <ChevronRight className="w-4 h-4 text-primary" />
                      <span className="text-sm font-medium">Add Patients</span>
                    </div>
                    <p className="text-xs text-muted-foreground">Start building your patient records</p>
                  </div>
                  <div className="p-3 rounded-md bg-muted/50 text-left">
                    <div className="flex items-center gap-2 mb-1">
                      <ChevronRight className="w-4 h-4 text-primary" />
                      <span className="text-sm font-medium">Treatment Plans</span>
                    </div>
                    <p className="text-xs text-muted-foreground">Create All-on-4/6 treatment plans</p>
                  </div>
                  <div className="p-3 rounded-md bg-muted/50 text-left">
                    <div className="flex items-center gap-2 mb-1">
                      <ChevronRight className="w-4 h-4 text-primary" />
                      <span className="text-sm font-medium">Submit Claims</span>
                    </div>
                    <p className="text-xs text-muted-foreground">Start billing insurance payers</p>
                  </div>
                </div>
                <Button
                  size="lg"
                  className="mt-4"
                  onClick={() => completeMutation.mutate()}
                  disabled={completeMutation.isPending}
                  data-testid="button-go-to-dashboard"
                >
                  {completeMutation.isPending ? "Finishing..." : "Go to Dashboard"}
                  <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              </div>
            )}

            {step > 0 && step < 5 && (
              <div className="flex items-center justify-between pt-6 mt-6 border-t gap-2">
                <Button
                  variant="outline"
                  onClick={() => setStep(step - 1)}
                  data-testid="button-back"
                >
                  <ArrowLeft className="w-4 h-4 mr-2" />
                  Back
                </Button>
                <div className="flex items-center gap-2">
                  {step === 4 && (
                    <Button
                      variant="ghost"
                      onClick={() => saveStepAndAdvance(5)}
                      data-testid="button-skip"
                    >
                      Skip
                    </Button>
                  )}
                  <Button
                    onClick={() => saveStepAndAdvance(step + 1)}
                    disabled={step === 1 && !practiceName}
                    data-testid="button-next"
                  >
                    {saveMutation.isPending ? "Saving..." : step === 4 ? "Finish" : "Continue"}
                    <ArrowRight className="w-4 h-4 ml-2" />
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {step === 0 && (
          <p className="text-xs text-muted-foreground mt-6 text-center max-w-md">
            HIPAA-compliant platform. All data is encrypted and stored securely. You can update your practice settings at any time from the Administration menu.
          </p>
        )}
      </div>
    </div>
  );
}
