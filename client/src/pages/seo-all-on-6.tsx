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
  Sticker,
  HeartPulse,
  Scale,
  MessageSquare,
} from "lucide-react";

const comparisonData = [
  { feature: "Implants Per Arch", allon4: "4", allon6: "6" },
  { feature: "Bone Requirements", allon4: "Minimal (angled posts)", allon6: "Moderate to good bone density" },
  { feature: "Stability", allon4: "High", allon6: "Very high (additional support)" },
  { feature: "Cost Range", allon4: "$25,000 - $40,000", allon6: "$30,000 - $50,000" },
  { feature: "Typical CDT Codes", allon4: "D6010 x4, D6114", allon6: "D6010 x6, D6114, D6056 x6" },
  { feature: "Surgical Complexity", allon4: "Standard", allon6: "Higher (more implant sites)" },
];

const cdtCodes = [
  { code: "D6010", description: "Surgical placement of implant body: endosteal implant", fee: "$2,200", qty: "x6" },
  { code: "D6056", description: "Prefabricated abutment", fee: "$650", qty: "x6" },
  { code: "D6058", description: "Abutment supported porcelain/ceramic crown", fee: "$1,400", qty: "x6" },
  { code: "D6114", description: "Implant/abutment supported fixed denture (full arch)", fee: "$28,500", qty: "x1" },
  { code: "D7210", description: "Surgical removal of erupted tooth", fee: "$285", qty: "As needed" },
  { code: "D7953", description: "Bone replacement graft, first site", fee: "$875", qty: "As needed" },
  { code: "D6057", description: "Custom fabricated abutment", fee: "$950", qty: "As needed" },
];

const documentationReqs = [
  { icon: FileText, title: "Clinical Narrative", description: "Detailed clinical justification documenting the patient's condition, failed conservative treatments, and why 6 implants are necessary over 4." },
  { icon: HeartPulse, title: "Medical History", description: "Complete medical records demonstrating the impact of tooth loss on nutrition, speech, and overall health to support medical necessity." },
  { icon: ClipboardList, title: "Radiographic Evidence", description: "CBCT scans and panoramic radiographs showing bone density measurements, anatomical landmarks, and planned implant positions." },
  { icon: Sticker, title: "Treatment Plan Documentation", description: "Comprehensive treatment plan with phased approach, expected outcomes, and justification for the All-on-6 approach over alternatives." },
];

const faqItems = [
  { question: "Is All-on-6 more expensive to bill than All-on-4?", answer: "Yes, All-on-6 cases typically bill $5,000-$10,000 more due to the additional 2 implants (D6010), abutments (D6056), and associated components. However, some insurers prefer All-on-6 for patients with adequate bone, viewing the additional implants as reducing long-term failure risk. Full Arch CRM helps identify which cases benefit from the All-on-6 billing approach." },
  { question: "When should I bill medical insurance for All-on-6?", answer: "Medical insurance should be considered when the procedure addresses a medical condition such as trauma, oncology reconstruction, or severe functional impairment affecting nutrition. Full Arch CRM's Insurance Navigator identifies cases eligible for medical billing and generates the appropriate ICD-10 codes and medical necessity documentation." },
  { question: "What is the typical approval rate for All-on-6 pre-authorizations?", answer: "Industry-wide, All-on-6 pre-authorization approval rates average 58%, lower than All-on-4 at 62% due to the higher cost and additional documentation requirements. Practices using Full Arch CRM achieve 90% approval rates through AI-powered documentation, optimal code selection, and proactive payer engagement." },
];

export default function AllOn6Page() {
  const [openFaq, setOpenFaq] = useState<number | null>(null);

  useEffect(() => {
    document.title = "All-on-6 Dental Implant Billing Software | Full Arch CRM";
    const meta = document.querySelector('meta[name="description"]');
    const content = "Manage All-on-6 dental implant billing with AI-powered coding, insurance pre-authorization, and medical vs dental billing strategies. 32% higher approval rates.";
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
              All-on-6 Dental Implant <span className="text-primary">Billing & Insurance Management</span>
            </h1>
            <p className="mx-auto mb-10 max-w-2xl text-lg text-muted-foreground">
              Navigate the complexities of All-on-6 billing with AI-powered tools that optimize coding, streamline pre-authorizations, and maximize insurance reimbursements.
            </p>
            <Button size="lg" asChild className="gap-2" data-testid="button-hero-cta">
              <a href="/api/login">
                Start Free Trial
                <ArrowRight className="h-4 w-4" />
              </a>
            </Button>
          </div>
        </section>

        <section className="border-y bg-muted/30 py-20">
          <div className="container mx-auto px-4">
            <h2 className="mb-4 text-center text-3xl font-bold sm:text-4xl">All-on-6 vs All-on-4 Comparison</h2>
            <p className="mb-8 text-center text-muted-foreground">Understanding the billing differences between these two full-arch restoration approaches.</p>
            <div className="mx-auto max-w-4xl overflow-x-auto">
              <Card>
                <CardContent className="p-0">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b bg-muted/50">
                        <th className="px-4 py-3 text-left font-semibold">Feature</th>
                        <th className="px-4 py-3 text-center font-semibold">All-on-4</th>
                        <th className="px-4 py-3 text-center font-semibold">All-on-6</th>
                      </tr>
                    </thead>
                    <tbody>
                      {comparisonData.map((row) => (
                        <tr key={row.feature} className="border-b last:border-0" data-testid={`row-compare-${row.feature.toLowerCase().replace(/\s+/g, "-")}`}>
                          <td className="px-4 py-3 font-medium">{row.feature}</td>
                          <td className="px-4 py-3 text-center text-muted-foreground">{row.allon4}</td>
                          <td className="px-4 py-3 text-center text-muted-foreground">{row.allon6}</td>
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
            <h2 className="mb-8 text-center text-3xl font-bold sm:text-4xl">CDT Codes for All-on-6 Procedures</h2>
            <p className="mb-8 text-center text-muted-foreground">Key procedure codes with quantities and fee ranges specific to All-on-6 cases.</p>
            <div className="mx-auto max-w-4xl overflow-x-auto">
              <Card>
                <CardContent className="p-0">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b bg-muted/50">
                        <th className="px-4 py-3 text-left font-semibold">CDT Code</th>
                        <th className="px-4 py-3 text-left font-semibold">Description</th>
                        <th className="px-4 py-3 text-center font-semibold">Qty</th>
                        <th className="px-4 py-3 text-right font-semibold">Fee (each)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {cdtCodes.map((item) => (
                        <tr key={item.code + item.qty} className="border-b last:border-0" data-testid={`row-cdt-${item.code}`}>
                          <td className="px-4 py-3 font-mono font-medium text-primary">{item.code}</td>
                          <td className="px-4 py-3 text-muted-foreground">{item.description}</td>
                          <td className="px-4 py-3 text-center">{item.qty}</td>
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
            <h2 className="mb-4 text-center text-3xl font-bold sm:text-4xl">Insurance Strategy for All-on-6</h2>
            <p className="mb-10 text-center text-muted-foreground">Choosing the right billing path can mean thousands in additional reimbursement per case.</p>
            <div className="mx-auto grid max-w-5xl gap-6 md:grid-cols-2">
              <Card>
                <CardContent className="p-6">
                  <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10">
                    <Scale className="h-6 w-6 text-primary" />
                  </div>
                  <h3 className="mb-3 text-lg font-semibold">Medical Billing Path</h3>
                  <ul className="space-y-2">
                    <li className="flex items-start gap-2 text-sm text-muted-foreground">
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                      <span>Trauma or accident-related tooth loss</span>
                    </li>
                    <li className="flex items-start gap-2 text-sm text-muted-foreground">
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                      <span>Cancer reconstruction following tumor removal</span>
                    </li>
                    <li className="flex items-start gap-2 text-sm text-muted-foreground">
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                      <span>Congenital defects affecting jaw structure</span>
                    </li>
                    <li className="flex items-start gap-2 text-sm text-muted-foreground">
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                      <span>Severe malnutrition due to inability to chew</span>
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
                  <ul className="space-y-2">
                    <li className="flex items-start gap-2 text-sm text-muted-foreground">
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                      <span>Standard edentulism or failing dentition</span>
                    </li>
                    <li className="flex items-start gap-2 text-sm text-muted-foreground">
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                      <span>Elective full-arch restoration</span>
                    </li>
                    <li className="flex items-start gap-2 text-sm text-muted-foreground">
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                      <span>Periodontal disease-related tooth loss</span>
                    </li>
                    <li className="flex items-start gap-2 text-sm text-muted-foreground">
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                      <span>Upgrade from removable prosthesis</span>
                    </li>
                  </ul>
                </CardContent>
              </Card>
            </div>
          </div>
        </section>

        <section className="py-20">
          <div className="container mx-auto px-4">
            <h2 className="mb-4 text-center text-3xl font-bold sm:text-4xl">Case Documentation Requirements</h2>
            <p className="mb-10 text-center text-muted-foreground">Comprehensive documentation is the key to All-on-6 claim approvals. Full Arch CRM automates and organizes every requirement.</p>
            <div className="mx-auto grid max-w-5xl gap-6 sm:grid-cols-2">
              {documentationReqs.map((req) => (
                <Card key={req.title} className="hover-elevate" data-testid={`card-doc-${req.title.toLowerCase().replace(/\s+/g, "-")}`}>
                  <CardContent className="p-6">
                    <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10">
                      <req.icon className="h-6 w-6 text-primary" />
                    </div>
                    <h3 className="mb-2 text-lg font-semibold">{req.title}</h3>
                    <p className="text-sm text-muted-foreground">{req.description}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>

        <section className="border-y bg-muted/30 py-16">
          <div className="container mx-auto px-4">
            <div className="mx-auto max-w-3xl text-center">
              <TrendingUp className="mx-auto mb-4 h-10 w-10 text-primary" />
              <h2 className="mb-4 text-3xl font-bold sm:text-4xl">Proven Results for All-on-6</h2>
              <p className="mb-8 text-lg text-muted-foreground">
                Practices using Full Arch CRM see <span className="font-bold text-foreground">32% higher approval rates</span> for All-on-6 cases compared to industry averages.
              </p>
              <div className="grid gap-4 sm:grid-cols-3">
                <Card>
                  <CardContent className="p-6 text-center">
                    <p className="text-3xl font-bold text-primary">90%</p>
                    <p className="mt-1 text-sm text-muted-foreground">Approval Rate</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-6 text-center">
                    <p className="text-3xl font-bold text-primary">23%</p>
                    <p className="mt-1 text-sm text-muted-foreground">Faster Reimbursement</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-6 text-center">
                    <p className="text-3xl font-bold text-primary">$12K</p>
                    <p className="mt-1 text-sm text-muted-foreground">Avg Additional Revenue / Case</p>
                  </CardContent>
                </Card>
              </div>
            </div>
          </div>
        </section>

        <section className="bg-primary py-16 text-primary-foreground">
          <div className="container mx-auto px-4 text-center">
            <h2 className="mb-4 text-3xl font-bold">Maximize Your All-on-6 Collections</h2>
            <p className="mx-auto mb-8 max-w-xl opacity-90">
              Stop losing revenue on complex All-on-6 cases. Let AI handle the billing complexity while you focus on patient care.
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
            <p className="mb-8 text-center text-muted-foreground">Common questions about All-on-6 billing and insurance management.</p>
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
