import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table, TableHeader, TableRow, TableHead, TableBody, TableCell,
} from "@/components/ui/table";
import {
  Check, Building2, Users, CreditCard, BarChart3, Star, Zap,
  ChevronRight, ChevronLeft, Rocket, Globe, Bot, Shield, Headphones,
  ArrowRight, DollarSign, TrendingUp, MessageSquare, Phone, FileText, Activity,
} from "lucide-react";

interface Plan {
  id: string;
  name: string;
  price: number;
  tagline: string;
  features: string[];
  highlight: boolean;
  cta: string;
  badge?: string;
}

const PLANS: Plan[] = [
  {
    id: "starter",
    name: "Starter",
    price: 297,
    tagline: "Solo practice essentials",
    features: [
      "1 location",
      "Up to 5 users",
      "Patient CRM",
      "Appointment scheduling",
      "Digital charting",
      "Basic insurance claims",
      "SMS reminders (500/mo)",
      "Email support",
      "DentBot AI assistant",
    ],
    highlight: false,
    cta: "Start Free Trial",
  },
  {
    id: "growth",
    name: "Growth",
    price: 497,
    tagline: "For practices ready to scale",
    features: [
      "1-3 locations",
      "Up to 15 users",
      "Everything in Starter plus:",
      "AI phone receptionist",
      "Smart scheduling",
      "Auto insurance verification",
      "SMS collections",
      "Automated recall",
      "AI treatment presentations",
      "Review generation",
      "Google Ads integration",
      "Analytics dashboard",
      "Priority support",
    ],
    highlight: true,
    cta: "Start Free Trial",
    badge: "Most Popular",
  },
  {
    id: "enterprise",
    name: "Enterprise",
    price: 997,
    tagline: "DSO & multi-location powerhouse",
    features: [
      "Unlimited locations",
      "Unlimited users",
      "Everything in Growth plus:",
      "Multi-location dashboard",
      "Provider scorecards",
      "Custom AI workflows",
      "EDI claims clearinghouse",
      "API access",
      "HIPAA BAA",
      "Custom onboarding (60-day)",
      "Dedicated success manager",
      "White-label option",
      "SLA 99.9%",
    ],
    highlight: false,
    cta: "Contact Sales",
  },
];

interface OnboardStep {
  id: number;
  title: string;
  icon: typeof Building2;
  fields: string[];
}

const ONBOARD_STEPS: OnboardStep[] = [
  { id: 1, title: "Practice Info", icon: Building2, fields: ["Practice Name", "Number of Locations", "Number of Operatories", "Current PMS", "Specialty Focus"] },
  { id: 2, title: "Team Setup", icon: Users, fields: ["Owner Name", "Owner Email", "Number of Providers", "Number of Staff", "Office Manager Name & Email"] },
  { id: 3, title: "Integrations", icon: Globe, fields: ["Current PMS", "Phone System", "Payment Processor", "Insurance Clearinghouse", "Email Provider"] },
  { id: 4, title: "AI Configuration", icon: Bot, fields: ["Enable AI Phone Receptionist?", "Enable SMS Collections?", "Enable Auto Review Requests?", "Enable Recall Campaigns?", "AI Personality Tone"] },
  { id: 5, title: "Go Live", icon: Rocket, fields: ["Import Patient Data", "Set Business Hours", "Configure Appointment Types", "Add Insurance Plans", "Invite Team Members"] },
];

interface Tenant {
  id: number;
  name: string;
  plan: "starter" | "growth" | "enterprise";
  locations: number;
  users: number;
  mrr: number;
  patients: number;
  status: "active" | "trial" | "churned";
  joined: string;
  lastActive: string;
  usage: { sms: number; calls_ai: number; claims: number; reviews: number };
}

const TENANTS: Tenant[] = [
  { id: 1, name: "Auburn Dental Group", plan: "growth", locations: 1, users: 8, mrr: 497, patients: 3105, status: "active", joined: "2025-11-15", lastActive: "2026-02-11", usage: { sms: 847, calls_ai: 142, claims: 187, reviews: 12 } },
  { id: 2, name: "Park Family Dentistry", plan: "growth", locations: 1, users: 6, mrr: 497, patients: 2340, status: "active", joined: "2025-12-01", lastActive: "2026-02-11", usage: { sms: 612, calls_ai: 98, claims: 143, reviews: 18 } },
  { id: 3, name: "Johnson Implant Center", plan: "enterprise", locations: 2, users: 14, mrr: 997, patients: 4820, status: "active", joined: "2025-10-20", lastActive: "2026-02-11", usage: { sms: 1420, calls_ai: 234, claims: 312, reviews: 24 } },
  { id: 4, name: "Bright Smiles DSO", plan: "enterprise", locations: 4, users: 32, mrr: 997, patients: 12400, status: "active", joined: "2025-09-05", lastActive: "2026-02-10", usage: { sms: 4200, calls_ai: 580, claims: 890, reviews: 67 } },
  { id: 5, name: "Sierra Dental Care", plan: "starter", locations: 1, users: 3, mrr: 297, patients: 890, status: "active", joined: "2026-01-10", lastActive: "2026-02-11", usage: { sms: 234, calls_ai: 0, claims: 56, reviews: 4 } },
  { id: 6, name: "Dr. Kim Solo Practice", plan: "starter", locations: 1, users: 2, mrr: 297, patients: 620, status: "trial", joined: "2026-02-01", lastActive: "2026-02-09", usage: { sms: 45, calls_ai: 0, claims: 12, reviews: 1 } },
  { id: 7, name: "Valley Oral Surgery", plan: "growth", locations: 1, users: 7, mrr: 497, patients: 1870, status: "active", joined: "2025-12-15", lastActive: "2026-02-11", usage: { sms: 510, calls_ai: 112, claims: 178, reviews: 9 } },
  { id: 8, name: "Smile Design Studio", plan: "growth", locations: 2, users: 11, mrr: 497, patients: 3400, status: "churned", joined: "2025-08-20", lastActive: "2026-01-15", usage: { sms: 0, calls_ai: 0, claims: 0, reviews: 0 } },
];

const TOTAL_MRR = TENANTS.reduce((sum, t) => sum + t.mrr, 0);
const TOTAL_PATIENTS = TENANTS.reduce((sum, t) => sum + t.patients, 0);
const ACTIVE_PRACTICES = TENANTS.filter((t) => t.status === "active").length;

const planBadgeVariant = (plan: string) => {
  if (plan === "growth") return "default" as const;
  if (plan === "enterprise") return "secondary" as const;
  return "outline" as const;
};

const statusBadgeClass = (status: string) => {
  if (status === "active") return "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 no-default-hover-elevate no-default-active-elevate";
  if (status === "trial") return "bg-blue-500/10 text-blue-600 dark:text-blue-400 no-default-hover-elevate no-default-active-elevate";
  return "bg-red-500/10 text-red-600 dark:text-red-400 no-default-hover-elevate no-default-active-elevate";
};

export default function SaasAdmin() {
  const [wizardStep, setWizardStep] = useState(1);
  const [selectedTenant, setSelectedTenant] = useState<Tenant | null>(null);

  const currentStep = ONBOARD_STEPS[wizardStep - 1];

  return (
    <div className="space-y-5" data-testid="saas-admin">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight" data-testid="text-page-title">SaaS Admin</h1>
        <p className="text-sm text-muted-foreground">Platform management, pricing, and tenant administration</p>
      </div>

      <Tabs defaultValue="pricing" data-testid="saas-admin-tabs">
        <TabsList data-testid="saas-admin-tabs-list">
          <TabsTrigger value="pricing" data-testid="tab-pricing">
            <CreditCard className="h-3.5 w-3.5 mr-1.5" />Pricing
          </TabsTrigger>
          <TabsTrigger value="onboarding" data-testid="tab-onboarding">
            <Rocket className="h-3.5 w-3.5 mr-1.5" />Onboarding
          </TabsTrigger>
          <TabsTrigger value="admin" data-testid="tab-admin">
            <BarChart3 className="h-3.5 w-3.5 mr-1.5" />Admin Dashboard
          </TabsTrigger>
        </TabsList>

        {/* ══════ TAB 1: PRICING ══════ */}
        <TabsContent value="pricing" className="mt-6 space-y-6">
          <div className="text-center space-y-2">
            <h2 className="text-3xl font-extrabold tracking-tight" data-testid="text-pricing-title">Simple Pricing</h2>
            <p className="text-muted-foreground">One platform. Three tiers. No surprises.</p>
          </div>

          <div className="grid gap-6 md:grid-cols-3 max-w-5xl mx-auto">
            {PLANS.map((plan) => (
              <Card
                key={plan.id}
                className={`relative flex flex-col ${plan.highlight ? "ring-2 ring-primary" : ""}`}
                data-testid={`card-plan-${plan.id}`}
              >
                {plan.badge && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 z-10">
                    <Badge data-testid="badge-most-popular">{plan.badge}</Badge>
                  </div>
                )}
                <CardHeader className="pb-2">
                  <div className="text-xs font-bold tracking-widest uppercase text-muted-foreground">{plan.name}</div>
                  <div className="flex items-baseline gap-1 mt-1">
                    <span className="text-4xl font-extrabold tracking-tight">${plan.price}</span>
                    <span className="text-muted-foreground text-sm">/mo</span>
                  </div>
                  <p className="text-sm text-muted-foreground italic mt-1">{plan.tagline}</p>
                </CardHeader>
                <CardContent className="flex-1 flex flex-col gap-4">
                  <Button
                    className="w-full"
                    variant={plan.highlight ? "default" : "outline"}
                    data-testid={`button-cta-${plan.id}`}
                  >
                    {plan.cta}
                    <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
                  </Button>
                  <div className="space-y-2.5">
                    {plan.features.map((feature, i) => {
                      const isEverything = feature.includes("Everything in");
                      return (
                        <div
                          key={i}
                          className={`flex items-start gap-2 text-sm ${isEverything ? "font-semibold text-foreground" : "text-muted-foreground"}`}
                        >
                          {!isEverything && <Check className="h-4 w-4 text-emerald-500 flex-shrink-0 mt-0.5" />}
                          <span>{feature}</span>
                        </div>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* ══════ TAB 2: ONBOARDING ══════ */}
        <TabsContent value="onboarding" className="mt-6 space-y-6">
          <div className="flex items-center justify-center gap-0 max-w-xl mx-auto">
            {ONBOARD_STEPS.map((step, i) => (
              <div key={step.id} className="flex items-center flex-1">
                <div className="flex flex-col items-center gap-1.5 flex-shrink-0">
                  <button
                    onClick={() => setWizardStep(step.id)}
                    className={`w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold transition-colors ${
                      wizardStep > step.id
                        ? "bg-primary text-primary-foreground"
                        : wizardStep === step.id
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted text-muted-foreground"
                    }`}
                    data-testid={`step-indicator-${step.id}`}
                  >
                    {wizardStep > step.id ? <Check className="h-4 w-4" /> : step.id}
                  </button>
                  <span className={`text-[10px] font-semibold ${wizardStep >= step.id ? "text-foreground" : "text-muted-foreground"}`}>
                    {step.title}
                  </span>
                </div>
                {i < ONBOARD_STEPS.length - 1 && (
                  <div className={`flex-1 h-0.5 mx-2 mb-5 transition-colors ${wizardStep > step.id ? "bg-primary" : "bg-muted"}`} />
                )}
              </div>
            ))}
          </div>

          <Card className="max-w-lg mx-auto">
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                  <currentStep.icon className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <CardTitle className="text-lg">Step {wizardStep}: {currentStep.title}</CardTitle>
                  <p className="text-sm text-muted-foreground">
                    {wizardStep === 1 && "Tell us about your practice."}
                    {wizardStep === 2 && "Set up your team accounts."}
                    {wizardStep === 3 && "Connect your existing tools."}
                    {wizardStep === 4 && "Choose which AI automations to activate."}
                    {wizardStep === 5 && "Final setup before going live."}
                  </p>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {currentStep.fields.map((field, i) => (
                <div key={i} className="space-y-1.5">
                  <Label className="text-sm font-medium">{field}</Label>
                  {field.includes("?") ? (
                    <div className="flex gap-2">
                      <Button variant="outline" className="flex-1" data-testid={`button-yes-${i}`}>
                        <Check className="h-3.5 w-3.5 mr-1.5" />Yes
                      </Button>
                      <Button variant="outline" className="flex-1" data-testid={`button-no-${i}`}>No</Button>
                    </div>
                  ) : (
                    <Input placeholder={field} data-testid={`input-${field.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`} />
                  )}
                </div>
              ))}

              <div className="flex justify-between gap-2 pt-4">
                <Button
                  variant="outline"
                  onClick={() => setWizardStep(Math.max(1, wizardStep - 1))}
                  disabled={wizardStep === 1}
                  data-testid="button-wizard-back"
                >
                  <ChevronLeft className="h-4 w-4 mr-1" />Back
                </Button>
                {wizardStep < 5 ? (
                  <Button
                    onClick={() => setWizardStep(Math.min(5, wizardStep + 1))}
                    data-testid="button-wizard-next"
                  >
                    Next<ChevronRight className="h-4 w-4 ml-1" />
                  </Button>
                ) : (
                  <Button data-testid="button-launch-practice">
                    <Rocket className="h-4 w-4 mr-1.5" />Launch Practice
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ══════ TAB 3: ADMIN DASHBOARD ══════ */}
        <TabsContent value="admin" className="mt-6 space-y-6">
          <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
            <Card data-testid="kpi-total-tenants">
              <CardContent className="p-4">
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <div className="text-xs font-semibold tracking-wider uppercase text-muted-foreground">Total Tenants</div>
                  <Building2 className="h-4 w-4 text-muted-foreground" />
                </div>
                <div className="text-2xl font-extrabold mt-1">{TENANTS.length}</div>
              </CardContent>
            </Card>
            <Card data-testid="kpi-total-mrr">
              <CardContent className="p-4">
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <div className="text-xs font-semibold tracking-wider uppercase text-muted-foreground">Total MRR</div>
                  <DollarSign className="h-4 w-4 text-muted-foreground" />
                </div>
                <div className="text-2xl font-extrabold mt-1">${TOTAL_MRR.toLocaleString()}</div>
              </CardContent>
            </Card>
            <Card data-testid="kpi-active-practices">
              <CardContent className="p-4">
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <div className="text-xs font-semibold tracking-wider uppercase text-muted-foreground">Active Practices</div>
                  <Activity className="h-4 w-4 text-muted-foreground" />
                </div>
                <div className="text-2xl font-extrabold mt-1">{ACTIVE_PRACTICES}</div>
              </CardContent>
            </Card>
            <Card data-testid="kpi-total-patients">
              <CardContent className="p-4">
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <div className="text-xs font-semibold tracking-wider uppercase text-muted-foreground">Total Patients</div>
                  <Users className="h-4 w-4 text-muted-foreground" />
                </div>
                <div className="text-2xl font-extrabold mt-1">{TOTAL_PATIENTS.toLocaleString()}</div>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Tenant Management</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Practice Name</TableHead>
                    <TableHead>Plan</TableHead>
                    <TableHead className="text-center">Locations</TableHead>
                    <TableHead className="text-center">Users</TableHead>
                    <TableHead className="text-right">MRR</TableHead>
                    <TableHead className="text-right">Patients</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Joined</TableHead>
                    <TableHead>Last Active</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {TENANTS.map((tenant) => (
                    <TableRow
                      key={tenant.id}
                      className="cursor-pointer hover-elevate"
                      onClick={() => setSelectedTenant(selectedTenant?.id === tenant.id ? null : tenant)}
                      data-testid={`row-tenant-${tenant.id}`}
                    >
                      <TableCell className="font-medium">{tenant.name}</TableCell>
                      <TableCell>
                        <Badge variant={planBadgeVariant(tenant.plan)} className="capitalize text-[10px]">
                          {tenant.plan}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-center">{tenant.locations}</TableCell>
                      <TableCell className="text-center">{tenant.users}</TableCell>
                      <TableCell className="text-right font-medium">${tenant.mrr}</TableCell>
                      <TableCell className="text-right">{tenant.patients.toLocaleString()}</TableCell>
                      <TableCell>
                        <Badge variant="outline" className={`capitalize text-[10px] ${statusBadgeClass(tenant.status)}`}>
                          {tenant.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-muted-foreground text-sm">{tenant.joined}</TableCell>
                      <TableCell className="text-muted-foreground text-sm">{tenant.lastActive}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          {selectedTenant && (
            <Card data-testid={`detail-panel-${selectedTenant.id}`}>
              <CardHeader>
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <CardTitle className="text-base">{selectedTenant.name} - Usage Metrics</CardTitle>
                  <Badge variant={planBadgeVariant(selectedTenant.plan)} className="capitalize text-[10px]">
                    {selectedTenant.plan}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
                  <div className="flex items-center gap-3 rounded-lg border p-3">
                    <MessageSquare className="h-5 w-5 text-muted-foreground flex-shrink-0" />
                    <div>
                      <div className="text-xs text-muted-foreground">SMS Sent</div>
                      <div className="text-lg font-bold" data-testid="metric-sms">{selectedTenant.usage.sms.toLocaleString()}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 rounded-lg border p-3">
                    <Phone className="h-5 w-5 text-muted-foreground flex-shrink-0" />
                    <div>
                      <div className="text-xs text-muted-foreground">AI Calls</div>
                      <div className="text-lg font-bold" data-testid="metric-ai-calls">{selectedTenant.usage.calls_ai.toLocaleString()}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 rounded-lg border p-3">
                    <FileText className="h-5 w-5 text-muted-foreground flex-shrink-0" />
                    <div>
                      <div className="text-xs text-muted-foreground">Claims Processed</div>
                      <div className="text-lg font-bold" data-testid="metric-claims">{selectedTenant.usage.claims.toLocaleString()}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 rounded-lg border p-3">
                    <Star className="h-5 w-5 text-muted-foreground flex-shrink-0" />
                    <div>
                      <div className="text-xs text-muted-foreground">Reviews Generated</div>
                      <div className="text-lg font-bold" data-testid="metric-reviews">{selectedTenant.usage.reviews.toLocaleString()}</div>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
