import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ThemeToggle } from "@/components/theme-toggle";
import {
  Stethoscope,
  ArrowRight,
  Shield,
  Lock,
  Activity,
  Brain,
  FileText,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  TrendingUp,
  DollarSign,
  ClipboardList,
  Scale,
  Zap,
  BarChart3,
  Send,
  CreditCard,
  Gavel,
  UserCheck,
  Search,
  Layers,
} from "lucide-react";

const whyDifferent = [
  { icon: Layers, title: "Procedure Complexity", description: "Dental implant procedures involve multiple stages, providers, and code sets. A single All-on-4 case can require 15+ individual procedure codes billed across surgical, prosthetic, and laboratory phases." },
  { icon: Scale, title: "Medical vs Dental Insurance", description: "Unlike routine dental work, implant procedures can qualify for medical insurance coverage. Knowing when and how to bill medical versus dental can mean $10,000+ in additional reimbursement per case." },
  { icon: FileText, title: "Documentation Burden", description: "Insurers require extensive clinical narratives, radiographic evidence, treatment plans, and medical necessity letters. Without proper documentation, even correctly coded claims get denied." },
];

const workflowSteps = [
  { icon: UserCheck, title: "Patient Evaluation", description: "Document clinical findings, capture radiographs, and assess insurance eligibility for implant coverage." },
  { icon: Search, title: "Code Selection", description: "AI analyzes the treatment plan and suggests optimal CDT, CPT, and ICD-10 codes for maximum reimbursement." },
  { icon: FileText, title: "Pre-Authorization", description: "Generate and submit pre-authorization requests with AI-drafted medical necessity letters and supporting documentation." },
  { icon: Send, title: "Claim Submission", description: "Submit clean claims electronically with all required attachments and documentation for first-pass approval." },
  { icon: CreditCard, title: "Payment Posting", description: "Automated ERA processing posts payments, identifies underpayments, and reconciles accounts in real time." },
  { icon: Gavel, title: "Appeals", description: "AI-powered appeal engine generates targeted letters with clinical evidence and regulatory citations for denied claims." },
];

const procedures = [
  { name: "Single Implants", codes: "D6010, D6065, D6066", feeRange: "$3,000 - $6,000" },
  { name: "All-on-4", codes: "D6010 x4, D6114, D6056", feeRange: "$25,000 - $40,000" },
  { name: "All-on-6", codes: "D6010 x6, D6114, D6056", feeRange: "$30,000 - $50,000" },
  { name: "Bone Grafts", codes: "D7953, D7952, D4263", feeRange: "$500 - $3,500" },
  { name: "Sinus Lifts", codes: "D7951, D7952", feeRange: "$1,500 - $3,000" },
  { name: "Extractions", codes: "D7210, D7220, D7230, D7240", feeRange: "$150 - $650" },
];

const aiFeatures = [
  { icon: Brain, title: "Smart Coding Engine", description: "AI analyzes clinical documentation and suggests optimal CDT, CPT, and ICD-10 codes with 99.2% accuracy across all implant procedure types." },
  { icon: FileText, title: "Automated Letters", description: "Generate medical necessity letters, pre-authorization requests, and patient communications in under 2 minutes using AI." },
  { icon: Gavel, title: "Appeals Engine", description: "Intelligent denial analysis with AI-generated appeal letters that cite clinical evidence, payer policies, and regulatory requirements." },
  { icon: CreditCard, title: "ERA Processing", description: "Automated electronic remittance advice processing that posts payments, identifies underpayments, and flags discrepancies instantly." },
  { icon: BarChart3, title: "Predictive Analytics", description: "Revenue forecasting, denial risk scoring, and payer behavior analysis to optimize billing strategies before claims are submitted." },
];

const faqItems = [
  { question: "What types of dental implant procedures does Full Arch CRM support?", answer: "Full Arch CRM supports the complete spectrum of implant procedures including single implants, All-on-4, All-on-6, bone grafting, sinus lifts, extractions, immediate load protocols, and staged implant workflows. Our AI coding engine covers all relevant CDT, CPT, and ICD-10 codes for each procedure type." },
  { question: "Can I bill both medical and dental insurance for implant procedures?", answer: "Yes, many implant cases qualify for dual billing. Medical insurance may cover portions related to trauma, cancer reconstruction, congenital defects, or functional impairment. Full Arch CRM's Insurance Navigator identifies which components can be billed to medical versus dental insurance, potentially adding $8,000-$15,000 in reimbursement per case." },
  { question: "How does the AI coding engine improve billing accuracy?", answer: "Our AI analyzes clinical notes, treatment plans, and radiographic findings to suggest optimal procedure codes. It cross-references CDT codes with CPT and ICD-10 codes, checks for bundling conflicts, and verifies payer-specific requirements. This results in 99.2% first-pass coding accuracy and 34% fewer denials compared to manual coding." },
  { question: "What is the implementation timeline for Full Arch CRM?", answer: "Most practices are fully operational within 1-2 weeks. We support data import from major practice management systems (Dentrix, Eaglesoft, Open Dental), and our onboarding team handles data migration. The AI coding engine begins learning your practice patterns immediately and reaches peak accuracy within 30 days." },
];

export default function DentalImplantBillingPage() {
  const [openFaq, setOpenFaq] = useState<number | null>(null);

  useEffect(() => {
    document.title = "Dental Implant Billing Software | Medical Billing for Implants | Full Arch CRM";
    const meta = document.querySelector('meta[name="description"]');
    const content = "Complete dental implant billing platform with AI-powered CDT/CPT coding, medical necessity letters, claims management, and predictive analytics. Support for All-on-4, All-on-6, and all implant procedures.";
    if (meta) {
      meta.setAttribute("content", content);
    } else {
      const newMeta = document.createElement("meta");
      newMeta.name = "description";
      newMeta.content = content;
      document.head.appendChild(newMeta);
    }
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
            <a href="/about" className="text-sm text-muted-foreground transition-colors hover:text-foreground" data-testid="link-about">About</a>
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
        <section className="container mx-auto px-4 py-20 lg:py-28">
          <div className="mx-auto max-w-4xl text-center">
            <Badge variant="secondary" className="mb-6 gap-2" data-testid="badge-hipaa">
              <Shield className="h-3.5 w-3.5" />
              HIPAA Compliant
            </Badge>
            <h1 className="mb-6 text-4xl font-bold tracking-tight sm:text-5xl lg:text-6xl">
              The Complete <span className="text-primary">Dental Implant Billing Platform</span>
            </h1>
            <p className="mx-auto mb-10 max-w-2xl text-lg text-muted-foreground">
              From single implants to full-arch restorations, manage every aspect of dental implant billing with AI-powered coding, automated claims, and intelligent analytics.
            </p>
            <div className="flex flex-col items-center justify-center gap-4 sm:flex-row">
              <Button size="lg" asChild className="gap-2" data-testid="button-hero-cta">
                <a href="/api/login">
                  Start Free Trial
                  <ArrowRight className="h-4 w-4" />
                </a>
              </Button>
              <Button size="lg" variant="outline" asChild className="gap-2" data-testid="button-hero-pricing">
                <a href="/#pricing">View Pricing</a>
              </Button>
            </div>
          </div>
        </section>

        <section className="border-y bg-muted/30 py-20">
          <div className="container mx-auto px-4">
            <h2 className="mb-4 text-center text-3xl font-bold sm:text-4xl">Why Dental Implant Billing Is Different</h2>
            <p className="mb-10 text-center text-muted-foreground">Implant billing is fundamentally more complex than routine dental procedures. Here is why.</p>
            <div className="mx-auto grid max-w-5xl gap-6 md:grid-cols-3">
              {whyDifferent.map((item) => (
                <Card key={item.title} data-testid={`card-why-${item.title.toLowerCase().replace(/\s+/g, "-")}`}>
                  <CardContent className="p-6">
                    <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10">
                      <item.icon className="h-6 w-6 text-primary" />
                    </div>
                    <h3 className="mb-2 text-lg font-semibold">{item.title}</h3>
                    <p className="text-sm text-muted-foreground">{item.description}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>

        <section className="py-20">
          <div className="container mx-auto px-4">
            <h2 className="mb-4 text-center text-3xl font-bold sm:text-4xl">Complete Billing Workflow</h2>
            <p className="mb-10 text-center text-muted-foreground">A streamlined 6-step process from evaluation to payment, powered by AI at every stage.</p>
            <div className="mx-auto grid max-w-5xl gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {workflowSteps.map((step, index) => (
                <Card key={step.title} className="hover-elevate" data-testid={`card-step-${index + 1}`}>
                  <CardContent className="p-6">
                    <div className="mb-3 flex items-center gap-3">
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-bold text-primary-foreground">
                        {index + 1}
                      </div>
                      <step.icon className="h-5 w-5 text-primary" />
                    </div>
                    <h3 className="mb-2 text-lg font-semibold">{step.title}</h3>
                    <p className="text-sm text-muted-foreground">{step.description}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>

        <section className="border-y bg-muted/30 py-20">
          <div className="container mx-auto px-4">
            <h2 className="mb-8 text-center text-3xl font-bold sm:text-4xl">Supported Procedures</h2>
            <p className="mb-8 text-center text-muted-foreground">Full Arch CRM covers every implant-related procedure type with intelligent coding support.</p>
            <div className="mx-auto max-w-4xl overflow-x-auto">
              <Card>
                <CardContent className="p-0">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b bg-muted/50">
                        <th className="px-4 py-3 text-left font-semibold">Procedure</th>
                        <th className="px-4 py-3 text-left font-semibold">Common CDT Codes</th>
                        <th className="px-4 py-3 text-right font-semibold">Typical Fee Range</th>
                      </tr>
                    </thead>
                    <tbody>
                      {procedures.map((proc) => (
                        <tr key={proc.name} className="border-b last:border-0" data-testid={`row-proc-${proc.name.toLowerCase().replace(/\s+/g, "-")}`}>
                          <td className="px-4 py-3 font-medium">{proc.name}</td>
                          <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{proc.codes}</td>
                          <td className="px-4 py-3 text-right font-semibold">{proc.feeRange}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </CardContent>
              </Card>
            </div>
          </div>
        </section>

        <section className="py-20">
          <div className="container mx-auto px-4">
            <h2 className="mb-4 text-center text-3xl font-bold sm:text-4xl">Insurance Navigator</h2>
            <p className="mb-10 text-center text-muted-foreground">Determine the optimal billing path for every implant case to maximize reimbursement.</p>
            <div className="mx-auto grid max-w-5xl gap-6 md:grid-cols-2">
              <Card>
                <CardContent className="p-6">
                  <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10">
                    <Scale className="h-6 w-6 text-primary" />
                  </div>
                  <h3 className="mb-3 text-lg font-semibold">Medical Billing Path</h3>
                  <p className="mb-4 text-sm text-muted-foreground">For cases with medical necessity documentation:</p>
                  <ul className="space-y-2">
                    <li className="flex items-start gap-2 text-sm text-muted-foreground">
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                      <span>Trauma and accident reconstruction</span>
                    </li>
                    <li className="flex items-start gap-2 text-sm text-muted-foreground">
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                      <span>Oncology-related reconstruction</span>
                    </li>
                    <li className="flex items-start gap-2 text-sm text-muted-foreground">
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                      <span>Congenital or developmental defects</span>
                    </li>
                    <li className="flex items-start gap-2 text-sm text-muted-foreground">
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                      <span>CPT + ICD-10 code sets required</span>
                    </li>
                  </ul>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-6">
                  <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10">
                    <DollarSign className="h-6 w-6 text-primary" />
                  </div>
                  <h3 className="mb-3 text-lg font-semibold">Dental Billing Path</h3>
                  <p className="mb-4 text-sm text-muted-foreground">For standard implant procedures and restorations:</p>
                  <ul className="space-y-2">
                    <li className="flex items-start gap-2 text-sm text-muted-foreground">
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                      <span>Periodontal disease-related implants</span>
                    </li>
                    <li className="flex items-start gap-2 text-sm text-muted-foreground">
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                      <span>Elective implant restorations</span>
                    </li>
                    <li className="flex items-start gap-2 text-sm text-muted-foreground">
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                      <span>Full-arch prosthetic upgrades</span>
                    </li>
                    <li className="flex items-start gap-2 text-sm text-muted-foreground">
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                      <span>CDT code sets with narratives</span>
                    </li>
                  </ul>
                </CardContent>
              </Card>
            </div>
          </div>
        </section>

        <section className="border-y bg-muted/30 py-20">
          <div className="container mx-auto px-4">
            <h2 className="mb-4 text-center text-3xl font-bold sm:text-4xl">AI Features for Implant Billing</h2>
            <p className="mb-10 text-center text-muted-foreground">Intelligent tools that automate the most time-consuming aspects of dental implant billing.</p>
            <div className="mx-auto grid max-w-5xl gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {aiFeatures.map((f) => (
                <Card key={f.title} className="hover-elevate" data-testid={`card-ai-${f.title.toLowerCase().replace(/\s+/g, "-")}`}>
                  <CardContent className="p-6">
                    <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10">
                      <f.icon className="h-6 w-6 text-primary" />
                    </div>
                    <h3 className="mb-2 text-lg font-semibold">{f.title}</h3>
                    <p className="text-sm text-muted-foreground">{f.description}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>

        <section className="py-16">
          <div className="container mx-auto px-4 text-center">
            <DollarSign className="mx-auto mb-4 h-10 w-10 text-primary" />
            <h2 className="mb-4 text-3xl font-bold">Transparent Pricing</h2>
            <p className="mx-auto mb-6 max-w-xl text-muted-foreground">
              Plans designed for practices of every size. All plans include a 30-day free trial with full access to AI-powered billing tools.
            </p>
            <Button size="lg" variant="outline" asChild className="gap-2" data-testid="button-view-pricing">
              <a href="/#pricing">
                View Pricing Plans
                <ArrowRight className="h-4 w-4" />
              </a>
            </Button>
          </div>
        </section>

        <section className="bg-primary py-16 text-primary-foreground">
          <div className="container mx-auto px-4 text-center">
            <h2 className="mb-4 text-3xl font-bold">Transform Your Dental Implant Billing</h2>
            <p className="mx-auto mb-8 max-w-xl opacity-90">
              Join thousands of practices that have increased collections by 32% with AI-powered implant billing.
            </p>
            <Button size="lg" variant="secondary" asChild className="gap-2" data-testid="button-cta-start">
              <a href="/api/login">
                Start Your Free Trial
                <ArrowRight className="h-4 w-4" />
              </a>
            </Button>
          </div>
        </section>

        <section className="py-20">
          <div className="container mx-auto px-4">
            <h2 className="mb-4 text-center text-3xl font-bold sm:text-4xl">Frequently Asked Questions</h2>
            <p className="mb-8 text-center text-muted-foreground">Everything you need to know about dental implant billing software.</p>
            <div className="mx-auto max-w-3xl space-y-3">
              {faqItems.map((item, index) => (
                <Card key={index} data-testid={`faq-item-${index}`}>
                  <CardContent className="p-0">
                    <button
                      className="flex w-full items-center justify-between gap-4 p-4 text-left"
                      onClick={() => setOpenFaq(openFaq === index ? null : index)}
                      data-testid={`button-faq-${index}`}
                    >
                      <span className="font-medium">{item.question}</span>
                      {openFaq === index ? (
                        <ChevronUp className="h-5 w-5 shrink-0 text-muted-foreground" />
                      ) : (
                        <ChevronDown className="h-5 w-5 shrink-0 text-muted-foreground" />
                      )}
                    </button>
                    {openFaq === index && (
                      <div className="border-t px-4 pb-4 pt-3">
                        <p className="text-sm text-muted-foreground">{item.answer}</p>
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t py-8">
        <div className="container mx-auto px-4">
          <div className="flex flex-col items-center justify-between gap-4 sm:flex-row">
            <div className="flex items-center gap-2">
              <Stethoscope className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">Full Arch CRM</span>
            </div>
            <p className="text-xs text-muted-foreground">
              &copy; {new Date().getFullYear()} Full Arch CRM. All rights reserved.
            </p>
          </div>
          <div className="mt-4 flex flex-wrap items-center justify-center gap-2 text-xs text-muted-foreground">
            <div className="flex items-center gap-1">
              <Lock className="h-3 w-3" />
              <span>SOC 2 Type II</span>
            </div>
            <span>|</span>
            <div className="flex items-center gap-1">
              <Shield className="h-3 w-3" />
              <span>HIPAA Compliant</span>
            </div>
            <span>|</span>
            <div className="flex items-center gap-1">
              <Activity className="h-3 w-3" />
              <span>99.9% Uptime</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
