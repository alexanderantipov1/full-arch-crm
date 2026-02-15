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
  AlertTriangle,
  ClipboardCheck,
  TrendingUp,
  Search,
  Gavel,
  DollarSign,
  Calculator,
  MessageSquare,
} from "lucide-react";

const cdtCodes = [
  { code: "D6010", description: "Surgical placement of implant body: endosteal implant", fee: "$2,200" },
  { code: "D6056", description: "Prefabricated abutment", fee: "$650" },
  { code: "D6058", description: "Abutment supported porcelain/ceramic crown", fee: "$1,400" },
  { code: "D6114", description: "Implant/abutment supported fixed denture (full arch)", fee: "$28,500" },
  { code: "D7210", description: "Surgical removal of erupted tooth requiring elevation", fee: "$285" },
  { code: "D7953", description: "Bone replacement graft, first site in quadrant", fee: "$875" },
];

const challenges = [
  { icon: AlertTriangle, title: "Pre-Authorization Denials", description: "Over 38% of All-on-4 pre-authorizations are denied on first submission due to insufficient documentation or incorrect coding sequences." },
  { icon: Search, title: "Incorrect Coding", description: "Complex multi-code procedures lead to coding errors that delay reimbursement and trigger audits. Cross-coding between CDT and CPT is especially error-prone." },
  { icon: ClipboardCheck, title: "Medical vs Dental Confusion", description: "Determining when to bill medical insurance versus dental insurance for implant procedures creates billing bottlenecks and lost revenue." },
  { icon: FileText, title: "Documentation Requirements", description: "Insurers require extensive clinical narratives, radiographs, and medical necessity letters that consume hours of staff time per case." },
  { icon: Gavel, title: "Appeal Management", description: "Managing denied claims through multiple appeal levels requires tracking deadlines, gathering additional documentation, and crafting persuasive arguments." },
];

const aiFeatures = [
  { icon: FileText, title: "Medical Necessity Letter Generation", description: "AI drafts comprehensive medical necessity letters in under 2 minutes, citing clinical evidence and payer-specific requirements." },
  { icon: Brain, title: "Code Cross-Referencing", description: "Automatically cross-references CDT, CPT, and ICD-10 codes to identify the optimal billing path for each All-on-4 case." },
  { icon: TrendingUp, title: "Real-Time Claim Tracking", description: "Monitor every claim from submission to payment with automated alerts for denials, requests for information, and payment posting." },
  { icon: Gavel, title: "Denial Appeal Automation", description: "AI analyzes denial reasons and generates targeted appeal letters with supporting clinical evidence and regulatory citations." },
];

const faqItems = [
  { question: "Does dental insurance cover All-on-4 procedures?", answer: "Coverage varies significantly by plan. Most dental PPO plans cover individual implants (D6010) and some prosthetic components, but full-arch restorations may require medical insurance billing. Full Arch CRM analyzes each patient's benefits to identify the optimal billing strategy, often splitting between medical and dental for maximum reimbursement." },
  { question: "How do I bill medical insurance for All-on-4?", answer: "Medical insurance can cover All-on-4 when procedures are deemed medically necessary (e.g., trauma, cancer reconstruction, severe bone loss affecting nutrition). Full Arch CRM generates ICD-10 codes and medical necessity documentation that supports medical billing pathways, helping practices capture an additional $8,000-$15,000 per case." },
  { question: "What is the typical reimbursement timeline for All-on-4 claims?", answer: "Dental claims typically process in 14-30 days, while medical claims may take 30-60 days. Pre-authorization adds 5-15 days. With Full Arch CRM's automated submission and tracking, practices see 23% faster reimbursement timelines compared to manual billing workflows." },
];

export default function AllOn4Page() {
  const [openFaq, setOpenFaq] = useState<number | null>(null);

  useEffect(() => {
    document.title = "All-on-4 Dental Implant Billing Software | Full Arch CRM";
    const meta = document.querySelector('meta[name="description"]');
    if (meta) {
      meta.setAttribute("content", "Streamline All-on-4 dental implant billing with AI-powered CDT coding, insurance pre-authorization, and claims management. 99.2% coding accuracy.");
    } else {
      const newMeta = document.createElement("meta");
      newMeta.name = "description";
      newMeta.content = "Streamline All-on-4 dental implant billing with AI-powered CDT coding, insurance pre-authorization, and claims management. 99.2% coding accuracy.";
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
              All-on-4 Dental Implant Billing <span className="text-primary">Made Simple</span>
            </h1>
            <p className="mx-auto mb-10 max-w-2xl text-lg text-muted-foreground">
              Maximize reimbursements for All-on-4 cases with AI-powered CDT coding, automated pre-authorizations, and intelligent claims management. Stop leaving money on the table.
            </p>
            <Button size="lg" asChild className="gap-2" data-testid="button-hero-cta">
              <a href="/api/login">
                Start Free Trial
                <ArrowRight className="h-4 w-4" />
              </a>
            </Button>
          </div>
        </section>

        <section className="border-y bg-muted/30 py-16">
          <div className="container mx-auto px-4">
            <div className="mx-auto max-w-4xl">
              <h2 className="mb-6 text-center text-3xl font-bold sm:text-4xl">What is All-on-4?</h2>
              <p className="mb-8 text-center text-muted-foreground">
                All-on-4 is a full-arch dental restoration technique that uses four strategically placed implants to support a complete set of fixed teeth. It provides a permanent solution for edentulous patients or those with failing dentition.
              </p>
              <div className="grid gap-4 sm:grid-cols-3">
                <Card>
                  <CardContent className="p-6 text-center">
                    <DollarSign className="mx-auto mb-3 h-8 w-8 text-primary" />
                    <p className="text-2xl font-bold">$25K - $40K</p>
                    <p className="text-sm text-muted-foreground">Average Case Value</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-6 text-center">
                    <Activity className="mx-auto mb-3 h-8 w-8 text-primary" />
                    <p className="text-2xl font-bold">4 Implants</p>
                    <p className="text-sm text-muted-foreground">Per Arch</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-6 text-center">
                    <CheckCircle2 className="mx-auto mb-3 h-8 w-8 text-primary" />
                    <p className="text-2xl font-bold">Same Day</p>
                    <p className="text-sm text-muted-foreground">Temporary Prosthesis</p>
                  </CardContent>
                </Card>
              </div>
            </div>
          </div>
        </section>

        <section className="py-20">
          <div className="container mx-auto px-4">
            <h2 className="mb-8 text-center text-3xl font-bold sm:text-4xl">Common CDT Codes for All-on-4</h2>
            <p className="mb-8 text-center text-muted-foreground">Key procedure codes and typical fee ranges for All-on-4 billing.</p>
            <div className="mx-auto max-w-4xl overflow-x-auto">
              <Card>
                <CardContent className="p-0">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b bg-muted/50">
                        <th className="px-4 py-3 text-left font-semibold">CDT Code</th>
                        <th className="px-4 py-3 text-left font-semibold">Description</th>
                        <th className="px-4 py-3 text-right font-semibold">Typical Fee</th>
                      </tr>
                    </thead>
                    <tbody>
                      {cdtCodes.map((item) => (
                        <tr key={item.code} className="border-b last:border-0" data-testid={`row-cdt-${item.code}`}>
                          <td className="px-4 py-3 font-mono font-medium text-primary">{item.code}</td>
                          <td className="px-4 py-3 text-muted-foreground">{item.description}</td>
                          <td className="px-4 py-3 text-right font-semibold">{item.fee}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </CardContent>
              </Card>
            </div>
          </div>
        </section>

        <section className="border-y bg-muted/30 py-20">
          <div className="container mx-auto px-4">
            <h2 className="mb-4 text-center text-3xl font-bold sm:text-4xl">Billing Challenges We Solve</h2>
            <p className="mb-10 text-center text-muted-foreground">All-on-4 billing is complex. Here are the top challenges practices face and how we address them.</p>
            <div className="mx-auto grid max-w-5xl gap-6 md:grid-cols-2 lg:grid-cols-3">
              {challenges.map((c) => (
                <Card key={c.title} data-testid={`card-challenge-${c.title.toLowerCase().replace(/\s+/g, "-")}`}>
                  <CardContent className="p-6">
                    <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10">
                      <c.icon className="h-6 w-6 text-primary" />
                    </div>
                    <h3 className="mb-2 text-lg font-semibold">{c.title}</h3>
                    <p className="text-sm text-muted-foreground">{c.description}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>

        <section className="py-20">
          <div className="container mx-auto px-4">
            <h2 className="mb-4 text-center text-3xl font-bold sm:text-4xl">AI-Powered Features for All-on-4</h2>
            <p className="mb-10 text-center text-muted-foreground">Purpose-built AI tools designed specifically for full-arch implant billing workflows.</p>
            <div className="mx-auto grid max-w-5xl gap-6 sm:grid-cols-2">
              {aiFeatures.map((f) => (
                <Card key={f.title} className="hover-elevate" data-testid={`card-feature-${f.title.toLowerCase().replace(/\s+/g, "-")}`}>
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

        <section className="border-y bg-muted/30 py-20">
          <div className="container mx-auto px-4">
            <div className="mx-auto max-w-3xl text-center">
              <Calculator className="mx-auto mb-4 h-10 w-10 text-primary" />
              <h2 className="mb-6 text-3xl font-bold sm:text-4xl">ROI Calculator</h2>
              <div className="grid gap-4 sm:grid-cols-3">
                <Card>
                  <CardContent className="p-6 text-center">
                    <p className="text-sm text-muted-foreground">Average All-on-4 Case</p>
                    <p className="mt-2 text-3xl font-bold">$32,000</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-6 text-center">
                    <p className="text-sm text-muted-foreground">Full Arch CRM Approval Rate</p>
                    <p className="mt-2 text-3xl font-bold text-primary">94%</p>
                    <p className="mt-1 text-xs text-muted-foreground">vs industry 62%</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-6 text-center">
                    <p className="text-sm text-muted-foreground">Additional Collections / Case</p>
                    <p className="mt-2 text-3xl font-bold text-primary">~$10,240</p>
                  </CardContent>
                </Card>
              </div>
              <p className="mt-6 text-sm text-muted-foreground">Based on average data from 2,400+ practices using Full Arch CRM.</p>
            </div>
          </div>
        </section>

        <section className="bg-primary py-16 text-primary-foreground">
          <div className="container mx-auto px-4 text-center">
            <h2 className="mb-4 text-3xl font-bold">Start Billing All-on-4 Cases Smarter</h2>
            <p className="mx-auto mb-8 max-w-xl opacity-90">
              Join thousands of practices maximizing their All-on-4 reimbursements with AI-powered billing tools.
            </p>
            <Button size="lg" variant="secondary" asChild className="gap-2" data-testid="button-cta-start">
              <a href="/api/login">
                Get Started Now
                <ArrowRight className="h-4 w-4" />
              </a>
            </Button>
          </div>
        </section>

        <section className="py-20">
          <div className="container mx-auto px-4">
            <h2 className="mb-4 text-center text-3xl font-bold sm:text-4xl">Frequently Asked Questions</h2>
            <p className="mb-8 text-center text-muted-foreground">Common questions about All-on-4 billing and insurance coverage.</p>
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
