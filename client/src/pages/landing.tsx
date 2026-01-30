import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ThemeToggle } from "@/components/theme-toggle";
import {
  Shield,
  Users,
  Brain,
  Calendar,
  FileText,
  DollarSign,
  CheckCircle2,
  Stethoscope,
  ArrowRight,
} from "lucide-react";

const features = [
  {
    icon: Shield,
    title: "HIPAA Compliant",
    description: "Secure patient data with enterprise-grade encryption and access controls.",
  },
  {
    icon: Brain,
    title: "AI-Powered Diagnosis",
    description: "Get intelligent treatment recommendations based on patient history and imaging.",
  },
  {
    icon: Users,
    title: "Complete Patient Records",
    description: "Medical history, dental info, implant records, and imaging in one place.",
  },
  {
    icon: Calendar,
    title: "Smart Scheduling",
    description: "Manage appointments, surgery schedules, and follow-ups efficiently.",
  },
  {
    icon: FileText,
    title: "Treatment Planning",
    description: "Create comprehensive plans with cost estimates and insurance coverage.",
  },
  {
    icon: DollarSign,
    title: "Billing & Insurance",
    description: "ICD-10 coding, prior authorizations, and automated claims management.",
  },
];

const benefits = [
  "Full arch implant treatment planning (All-on-4, All-on-6)",
  "Medical necessity letter generation with AI",
  "Automated insurance pre-authorization workflow",
  "Denial management with AI-powered appeals",
  "CDT/ICD-10 coding assistance",
  "Surgery documentation and op reports",
];

export default function Landing() {
  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container mx-auto flex h-16 items-center justify-between px-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <Stethoscope className="h-5 w-5" />
            </div>
            <span className="text-xl font-semibold">Full Arch CRM</span>
          </div>
          <div className="flex items-center gap-4">
            <ThemeToggle />
            <Button asChild data-testid="button-login">
              <a href="/api/login">Sign In</a>
            </Button>
          </div>
        </div>
      </header>

      <main>
        <section className="container mx-auto px-4 py-20 lg:py-32">
          <div className="mx-auto max-w-4xl text-center">
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border bg-muted/50 px-4 py-1.5 text-sm">
              <Shield className="h-4 w-4 text-primary" />
              <span>HIPAA Compliant Platform</span>
            </div>
            <h1 className="mb-6 text-4xl font-bold tracking-tight sm:text-5xl lg:text-6xl">
              Complete Practice Management for{" "}
              <span className="text-primary">Full Arch Dental Implants</span>
            </h1>
            <p className="mx-auto mb-10 max-w-2xl text-lg text-muted-foreground">
              Streamline your dental implant practice with AI-powered diagnosis, comprehensive
              patient records, treatment planning, and automated insurance management.
            </p>
            <div className="flex flex-col items-center justify-center gap-4 sm:flex-row">
              <Button size="lg" asChild className="gap-2" data-testid="button-get-started">
                <a href="/api/login">
                  Get Started
                  <ArrowRight className="h-4 w-4" />
                </a>
              </Button>
              <Button size="lg" variant="outline" data-testid="button-learn-more">
                Learn More
              </Button>
            </div>
          </div>
        </section>

        <section className="border-y bg-muted/30 py-20">
          <div className="container mx-auto px-4">
            <div className="mb-12 text-center">
              <h2 className="mb-4 text-3xl font-bold">Everything You Need</h2>
              <p className="mx-auto max-w-2xl text-muted-foreground">
                Designed specifically for dental implant practices, our platform covers every
                aspect of patient care and practice management.
              </p>
            </div>
            <div className="mx-auto grid max-w-6xl gap-6 md:grid-cols-2 lg:grid-cols-3">
              {features.map((feature) => (
                <Card key={feature.title} className="hover-elevate transition-all duration-200">
                  <CardContent className="p-6">
                    <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10">
                      <feature.icon className="h-6 w-6 text-primary" />
                    </div>
                    <h3 className="mb-2 text-lg font-semibold">{feature.title}</h3>
                    <p className="text-sm text-muted-foreground">{feature.description}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>

        <section className="py-20">
          <div className="container mx-auto px-4">
            <div className="mx-auto grid max-w-6xl items-center gap-12 lg:grid-cols-2">
              <div>
                <h2 className="mb-6 text-3xl font-bold">
                  Specialized for Full Arch Dental Implants
                </h2>
                <p className="mb-8 text-muted-foreground">
                  Our platform is built from the ground up for dental implant practices,
                  incorporating industry-standard protocols and workflows.
                </p>
                <ul className="space-y-4">
                  {benefits.map((benefit) => (
                    <li key={benefit} className="flex items-start gap-3">
                      <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-accent" />
                      <span>{benefit}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div className="relative">
                <div className="aspect-square rounded-2xl bg-gradient-to-br from-primary/20 via-primary/10 to-accent/20 p-8">
                  <div className="flex h-full flex-col items-center justify-center gap-4 rounded-xl border bg-card p-8 text-center shadow-lg">
                    <Brain className="h-16 w-16 text-primary" />
                    <h3 className="text-xl font-semibold">AI-Assisted Diagnosis</h3>
                    <p className="text-sm text-muted-foreground">
                      Leverage artificial intelligence to analyze patient data and provide
                      treatment recommendations
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="border-t bg-primary py-16 text-primary-foreground">
          <div className="container mx-auto px-4 text-center">
            <h2 className="mb-4 text-3xl font-bold">Ready to Transform Your Practice?</h2>
            <p className="mx-auto mb-8 max-w-xl opacity-90">
              Join dental implant practices that trust Full Arch CRM for their patient management needs.
            </p>
            <Button
              size="lg"
              variant="secondary"
              asChild
              className="gap-2"
              data-testid="button-start-free"
            >
              <a href="/api/login">
                Start Free Today
                <ArrowRight className="h-4 w-4" />
              </a>
            </Button>
          </div>
        </section>
      </main>

      <footer className="border-t py-8">
        <div className="container mx-auto flex flex-col items-center justify-between gap-4 px-4 text-sm text-muted-foreground sm:flex-row">
          <div className="flex items-center gap-2">
            <Stethoscope className="h-4 w-4" />
            <span>Full Arch CRM</span>
          </div>
          <p>&copy; {new Date().getFullYear()} Full Arch CRM. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}
