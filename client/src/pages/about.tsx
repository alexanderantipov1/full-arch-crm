import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ThemeToggle } from "@/components/theme-toggle";
import {
  Stethoscope, Shield, CheckCircle, X, Lock, Users, Brain, BarChart3,
  Zap, Building2, Award, ArrowRight, Target, Layers, Globe, Activity,
  Clock, Server, Wifi, Heart,
} from "lucide-react";

const platformFeatures = [
  { icon: Target, title: "Command Center", description: "Executive dashboard with real-time practice metrics" },
  { icon: Layers, title: "12-Phase Patient Journey", description: "From first contact through warranty management" },
  { icon: Brain, title: "AI Coding Engine", description: "99.2% accuracy CDT/CPT/ICD-10 cross-coding" },
  { icon: Zap, title: "Smart Appeals", description: "78% success rate on denied claim appeals" },
  { icon: BarChart3, title: "Predictive Analytics", description: "Revenue forecasting and at-risk claim identification" },
  { icon: Activity, title: "Practice Growth OS", description: "AI C-Suite advisors for business strategy" },
  { icon: Building2, title: "Multi-Location Support", description: "Centralized management for practice groups" },
  { icon: Shield, title: "HIPAA Compliance", description: "SOC 2 certified with complete audit trails" },
];

const comparisonRows = [
  { feature: "AI-Powered Coding", us: "yes", pms: "no", manual: "no" },
  { feature: "Implant-Specific Workflows", us: "yes", pms: "partial", manual: "no" },
  { feature: "Medical Necessity Letters", us: "yes", pms: "no", manual: "no" },
  { feature: "Automated Appeals", us: "yes", pms: "no", manual: "no" },
  { feature: "Predictive Analytics", us: "yes", pms: "no", manual: "no" },
  { feature: "12-Phase Patient Journey", us: "yes", pms: "no", manual: "no" },
  { feature: "Multi-Location Dashboard", us: "yes", pms: "yes", manual: "no" },
  { feature: "HIPAA Audit Logging", us: "yes", pms: "partial", manual: "no" },
  { feature: "Training Center", us: "yes", pms: "no", manual: "no" },
  { feature: "Real-Time ERA Processing", us: "yes", pms: "partial", manual: "no" },
];

const integrations = [
  { icon: Server, name: "Practice Management Systems" },
  { icon: Activity, name: "Digital Imaging (CBCT, Pano)" },
  { icon: Shield, name: "Insurance Clearinghouses" },
  { icon: Zap, name: "Payment Processors" },
  { icon: Layers, name: "Lab Management" },
  { icon: Heart, name: "E-Prescribing" },
  { icon: Users, name: "Patient Communication" },
  { icon: BarChart3, name: "Accounting Software" },
  { icon: Globe, name: "Cloud Storage" },
  { icon: Wifi, name: "Telehealth Platforms" },
  { icon: Target, name: "Marketing Tools" },
  { icon: Building2, name: "HR & Payroll" },
];

const teamMembers = [
  { initials: "AR", name: "Dr. Alex Rivera", title: "CEO & Co-Founder", bio: "Former oral surgeon with 15 years of implant experience" },
  { initials: "SC", name: "Sarah Chen", title: "CTO", bio: "Previously led engineering at a healthcare SaaS unicorn" },
  { initials: "JP", name: "Dr. James Park", title: "Chief Dental Officer", bio: "Board-certified prosthodontist and billing expert" },
  { initials: "MS", name: "Maria Santos", title: "VP of Customer Success", bio: "10+ years in dental practice consulting" },
];

const certifications = [
  { icon: Shield, label: "SOC 2 Type II" },
  { icon: CheckCircle, label: "HIPAA Compliant" },
  { icon: Lock, label: "PCI DSS" },
  { icon: Clock, label: "99.9% Uptime SLA" },
  { icon: Award, label: "BAA Available" },
  { icon: Lock, label: "256-bit Encryption" },
];

function StatusCell({ value }: { value: string }) {
  if (value === "yes") return <CheckCircle className="mx-auto h-5 w-5 text-primary" />;
  if (value === "no") return <X className="mx-auto h-5 w-5 text-muted-foreground/40" />;
  return <span className="text-xs text-muted-foreground">Partial</span>;
}

export default function AboutPage() {
  useEffect(() => {
    document.title = "About Full Arch CRM | AI-Powered Dental Implant Practice Management";
  }, []);

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container mx-auto flex h-16 items-center justify-between gap-4 px-4">
          <a href="/" className="flex items-center gap-3" data-testid="link-home">
            <div className="flex h-9 w-9 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <Stethoscope className="h-5 w-5" />
            </div>
            <span className="text-xl font-semibold">Full Arch CRM</span>
          </a>
          <nav className="hidden items-center gap-6 md:flex">
            <a href="/#features" className="text-sm text-muted-foreground transition-colors hover:text-foreground" data-testid="link-features">Features</a>
            <a href="/#pricing" className="text-sm text-muted-foreground transition-colors hover:text-foreground" data-testid="link-pricing">Pricing</a>
            <a href="/about" className="text-sm font-medium text-foreground" data-testid="link-about">About</a>
          </nav>
          <div className="flex items-center gap-4">
            <ThemeToggle />
            <Button asChild data-testid="button-login">
              <a href="/api/login">Sign In</a>
            </Button>
          </div>
        </div>
      </header>

      <main>
        <section className="relative overflow-hidden py-20 lg:py-28">
          <div className="absolute inset-0 bg-gradient-to-br from-primary/10 via-transparent to-primary/5" />
          <div className="container relative mx-auto px-4 text-center">
            <h1 className="mb-6 text-4xl font-bold tracking-tight sm:text-5xl">
              Built by Dental Professionals, for Dental Professionals
            </h1>
            <p className="mx-auto max-w-2xl text-lg text-muted-foreground">
              Full Arch CRM was created to solve the #1 challenge in implant dentistry: getting paid for the complex procedures you perform.
            </p>
          </div>
        </section>

        <section className="border-y bg-muted/30 py-20">
          <div className="container mx-auto px-4">
            <div className="mx-auto max-w-3xl text-center">
              <Badge variant="secondary" className="mb-4 gap-2"><Heart className="h-3.5 w-3.5" />Our Mission</Badge>
              <p className="mb-12 text-lg text-muted-foreground">
                To help every dental implant practice maximize their revenue through intelligent billing, streamlined workflows, and AI-powered decision support.
              </p>
            </div>
            <div className="mx-auto grid max-w-4xl grid-cols-2 gap-6 sm:grid-cols-4">
              {[
                { value: "2023", label: "Founded" },
                { value: "500+", label: "Practices" },
                { value: "50+", label: "Team Members" },
                { value: "$847M", label: "Claims Processed" },
              ].map((stat) => (
                <Card key={stat.label} className="text-center">
                  <CardContent className="p-6">
                    <p className="text-3xl font-bold" data-testid={`stat-${stat.label.toLowerCase().replace(/\s+/g, "-")}`}>{stat.value}</p>
                    <p className="text-sm text-muted-foreground">{stat.label}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>

        <section className="py-20">
          <div className="container mx-auto px-4">
            <div className="mb-12 text-center">
              <Badge variant="secondary" className="mb-4 gap-2"><Zap className="h-3.5 w-3.5" />Platform</Badge>
              <h2 className="mb-4 text-3xl font-bold sm:text-4xl">Platform Features</h2>
              <p className="mx-auto max-w-2xl text-muted-foreground">Purpose-built for dental implant practices with advanced AI capabilities.</p>
            </div>
            <div className="mx-auto grid max-w-5xl gap-6 md:grid-cols-2">
              {platformFeatures.map((f) => (
                <Card key={f.title} className="hover-elevate" data-testid={`card-feature-${f.title.toLowerCase().replace(/\s+/g, "-")}`}>
                  <CardContent className="flex items-start gap-4 p-6">
                    <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                      <f.icon className="h-6 w-6 text-primary" />
                    </div>
                    <div>
                      <h3 className="mb-1 font-semibold">{f.title}</h3>
                      <p className="text-sm text-muted-foreground">{f.description}</p>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>

        <section className="border-y bg-muted/30 py-20">
          <div className="container mx-auto px-4">
            <div className="mb-12 text-center">
              <Badge variant="secondary" className="mb-4 gap-2"><BarChart3 className="h-3.5 w-3.5" />Comparison</Badge>
              <h2 className="mb-4 text-3xl font-bold sm:text-4xl">How We Compare</h2>
            </div>
            <div className="mx-auto max-w-4xl overflow-x-auto">
              <table className="w-full text-sm" data-testid="table-comparison">
                <thead>
                  <tr className="border-b">
                    <th className="py-3 pr-4 text-left font-semibold">Feature</th>
                    <th className="px-4 py-3 text-center font-semibold text-primary">Full Arch CRM</th>
                    <th className="px-4 py-3 text-center font-semibold">Generic PMS</th>
                    <th className="px-4 py-3 text-center font-semibold">Manual Billing</th>
                  </tr>
                </thead>
                <tbody>
                  {comparisonRows.map((row) => (
                    <tr key={row.feature} className="border-b last:border-0">
                      <td className="py-3 pr-4">{row.feature}</td>
                      <td className="px-4 py-3 text-center"><StatusCell value={row.us} /></td>
                      <td className="px-4 py-3 text-center"><StatusCell value={row.pms} /></td>
                      <td className="px-4 py-3 text-center"><StatusCell value={row.manual} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <section className="py-20">
          <div className="container mx-auto px-4">
            <div className="mb-12 text-center">
              <Badge variant="secondary" className="mb-4 gap-2"><Globe className="h-3.5 w-3.5" />Integrations</Badge>
              <h2 className="mb-4 text-3xl font-bold sm:text-4xl">Connects With Your Existing Tools</h2>
            </div>
            <div className="mx-auto grid max-w-5xl grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
              {integrations.map((item) => (
                <Card key={item.name} data-testid={`card-integration-${item.name.toLowerCase().replace(/[\s(),/]+/g, "-")}`}>
                  <CardContent className="flex flex-col items-center gap-3 p-5 text-center">
                    <item.icon className="h-8 w-8 text-primary" />
                    <p className="text-sm font-medium">{item.name}</p>
                    <Badge variant="secondary" className="gap-1 text-xs">
                      <CheckCircle className="h-3 w-3" />Connected
                    </Badge>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>

        <section className="border-y bg-muted/30 py-20">
          <div className="container mx-auto px-4">
            <div className="mb-12 text-center">
              <Badge variant="secondary" className="mb-4 gap-2"><Users className="h-3.5 w-3.5" />Team</Badge>
              <h2 className="mb-4 text-3xl font-bold sm:text-4xl">Leadership Team</h2>
            </div>
            <div className="mx-auto grid max-w-4xl gap-6 sm:grid-cols-2 lg:grid-cols-4">
              {teamMembers.map((member) => (
                <Card key={member.name} data-testid={`card-team-${member.initials.toLowerCase()}`}>
                  <CardContent className="flex flex-col items-center gap-3 p-6 text-center">
                    <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary text-lg font-semibold text-primary-foreground">
                      {member.initials}
                    </div>
                    <div>
                      <p className="font-semibold">{member.name}</p>
                      <p className="text-sm text-primary">{member.title}</p>
                    </div>
                    <p className="text-xs text-muted-foreground">{member.bio}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>

        <section className="py-16">
          <div className="container mx-auto px-4">
            <div className="mb-10 text-center">
              <Badge variant="secondary" className="mb-4 gap-2"><Lock className="h-3.5 w-3.5" />Security</Badge>
              <h2 className="mb-4 text-3xl font-bold sm:text-4xl">Trust & Compliance</h2>
            </div>
            <div className="mx-auto grid max-w-4xl grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
              {certifications.map((cert) => (
                <Card key={cert.label} data-testid={`card-cert-${cert.label.toLowerCase().replace(/\s+/g, "-")}`}>
                  <CardContent className="flex flex-col items-center gap-2 p-4 text-center">
                    <cert.icon className="h-6 w-6 text-primary" />
                    <p className="text-xs font-medium">{cert.label}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>

        <section className="bg-primary py-16 text-primary-foreground">
          <div className="container mx-auto px-4 text-center">
            <h2 className="mb-4 text-3xl font-bold">Ready to Transform Your Practice?</h2>
            <p className="mx-auto mb-8 max-w-xl opacity-90">
              Join 500+ dental implant practices already using Full Arch CRM
            </p>
            <div className="flex flex-col items-center justify-center gap-4 sm:flex-row">
              <Button size="lg" variant="secondary" asChild className="gap-2" data-testid="button-cta-trial">
                <a href="/api/login">
                  Start Free Trial
                  <ArrowRight className="h-4 w-4" />
                </a>
              </Button>
              <Button size="lg" variant="outline" className="gap-2 border-primary-foreground/30 bg-primary-foreground/10 text-primary-foreground" data-testid="button-cta-demo">
                Schedule a Demo
              </Button>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t py-10">
        <div className="container mx-auto px-4">
          <div className="flex flex-col items-center gap-4 text-center">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-md bg-primary text-primary-foreground">
                <Stethoscope className="h-5 w-5" />
              </div>
              <span className="text-lg font-semibold">Full Arch CRM</span>
            </div>
            <p className="text-sm text-muted-foreground">
              &copy; {new Date().getFullYear()} Full Arch CRM. All rights reserved.
            </p>
            <div className="flex flex-wrap items-center justify-center gap-3">
              <Badge variant="secondary" className="gap-1 text-xs">
                <Shield className="h-3 w-3" />HIPAA Compliant
              </Badge>
              <Badge variant="secondary" className="gap-1 text-xs">
                <Lock className="h-3 w-3" />SOC 2 Certified
              </Badge>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}