import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ThemeToggle } from "@/components/theme-toggle";
import {
  Shield,
  Brain,
  Users,
  Calendar,
  FileText,
  DollarSign,
  CheckCircle2,
  Stethoscope,
  ArrowRight,
  Star,
  Zap,
  BarChart3,
  Clock,
  Lock,
  TrendingUp,
  MessageSquare,
  ChevronDown,
  ChevronUp,
  Activity,
  Target,
  Award,
  Layers,
} from "lucide-react";

const features = [
  {
    icon: Brain,
    title: "AI-Powered Coding Engine",
    description:
      "Intelligent CDT to CPT/ICD-10 cross-coding with 99.2% accuracy. Reduce coding errors and maximize reimbursements automatically.",
  },
  {
    icon: FileText,
    title: "Smart Claims Management",
    description:
      "Automated claim submission, real-time tracking, and intelligent denial management to keep your revenue flowing.",
  },
  {
    icon: MessageSquare,
    title: "Medical Necessity Letters",
    description:
      "AI-generated documentation for insurance approvals. Transform 45-minute tasks into 2-minute automated workflows.",
  },
  {
    icon: BarChart3,
    title: "Predictive Analytics",
    description:
      "Revenue forecasting, risk identification, and performance benchmarks to make data-driven practice decisions.",
  },
  {
    icon: Layers,
    title: "12-Phase Patient Journey",
    description:
      "Complete workflow management from initial lead capture through treatment, billing, and long-term warranty tracking.",
  },
  {
    icon: Shield,
    title: "HIPAA Compliant",
    description:
      "Enterprise-grade security with AES-256 encryption, complete audit trails, and role-based access controls.",
  },
];

const testimonials = [
  {
    quote:
      "Full Arch CRM transformed our billing workflow. We went from 62% to 94% claim approval rate in just 3 months. The AI coding suggestions alone save us 15 hours per week.",
    name: "Dr. Sarah Mitchell",
    title: "Oral Surgeon",
    location: "Austin, TX",
    initials: "SM",
  },
  {
    quote:
      "The medical necessity letter generator is incredible. What used to take 45 minutes now takes 2 minutes with AI, and our approval rates have never been higher.",
    name: "Dr. James Park",
    title: "Prosthodontist",
    location: "Seattle, WA",
    initials: "JP",
  },
  {
    quote:
      "We've recovered over $340K in denied claims using the Smart Appeals Engine. The ROI was immediate - this platform pays for itself within the first month.",
    name: "Dr. Maria Santos",
    title: "Implant Practice Owner",
    location: "Miami, FL",
    initials: "MS",
  },
];

const pricingTiers = [
  {
    name: "Starter",
    price: "$299",
    description: "Perfect for solo practitioners getting started with AI billing",
    features: [
      "Up to 50 patients",
      "AI coding engine",
      "Claims management",
      "1 provider",
      "Email support",
    ],
    cta: "Start Free Trial",
    popular: false,
  },
  {
    name: "Professional",
    price: "$599",
    description: "For growing practices that need advanced tools",
    features: [
      "Up to 200 patients",
      "Everything in Starter",
      "Medical necessity letters",
      "Appeals engine",
      "Predictive analytics",
      "5 providers",
      "Priority support",
    ],
    cta: "Start Free Trial",
    popular: true,
  },
  {
    name: "Enterprise",
    price: "$999",
    description: "For multi-location practices and DSOs",
    features: [
      "Unlimited patients",
      "Everything in Professional",
      "Multi-location support",
      "Custom integrations",
      "Dedicated success manager",
      "API access",
      "SLA guarantee",
    ],
    cta: "Contact Sales",
    popular: false,
  },
];

const steps = [
  {
    icon: Target,
    title: "Connect Your Practice",
    description: "Import patient data and configure your billing preferences in minutes.",
  },
  {
    icon: Brain,
    title: "AI Codes Your Claims",
    description: "Our AI engine suggests optimal CDT/CPT/ICD-10 codes for every procedure.",
  },
  {
    icon: Zap,
    title: "Submit & Track",
    description: "Automated claim submission with real-time status tracking and alerts.",
  },
  {
    icon: TrendingUp,
    title: "Maximize Revenue",
    description: "AI-powered appeals and analytics to boost collections and reduce denials.",
  },
];

const faqItems = [
  {
    question: "Is Full Arch CRM HIPAA compliant?",
    answer:
      "Yes. Full Arch CRM is fully HIPAA compliant with enterprise-grade AES-256 encryption, comprehensive audit logging, role-based access controls, and automatic session management. We maintain a signed Business Associate Agreement (BAA) with every customer and undergo regular third-party security audits.",
  },
  {
    question: "How does the AI coding engine work?",
    answer:
      "Our AI analyzes procedure documentation, clinical notes, and imaging reports to suggest optimal CDT, CPT, and ICD-10 codes. The engine cross-references dental and medical codes to maximize insurance reimbursements, achieving 99.2% coding accuracy across thousands of claims processed monthly.",
  },
  {
    question: "Can I import my existing patient data?",
    answer:
      "Yes, we support CSV and Excel import as well as direct integrations with major practice management systems including Dentrix, Eaglesoft, Open Dental, and more. Our onboarding team will assist with data migration to ensure a smooth transition.",
  },
  {
    question: "What's the average ROI?",
    answer:
      "Practices typically see a 32% increase in collections within the first 90 days. The AI coding engine alone recovers an average of $12,000 per month in previously missed reimbursements. Most practices report that the platform pays for itself within the first month.",
  },
  {
    question: "Do you offer training?",
    answer:
      "Yes, our Training Center includes interactive onboarding modules, video tutorials, live webinars, and a comprehensive knowledge base. Enterprise plans include dedicated training sessions and a success manager to ensure your team is fully up to speed.",
  },
  {
    question: "Can I cancel anytime?",
    answer:
      "Yes, there are no long-term contracts. You can cancel your subscription at any time from your account settings. We also offer a 30-day money-back guarantee so you can try Full Arch CRM risk-free.",
  },
];

const footerLinks = {
  Product: [
    { label: "Features", href: "#features" },
    { label: "Pricing", href: "#pricing" },
    { label: "About", href: "/about" },
    { label: "Demo", href: "#" },
  ],
  Resources: [
    { label: "Blog", href: "#" },
    { label: "Case Studies", href: "#" },
    { label: "Documentation", href: "#" },
    { label: "API", href: "#" },
  ],
  Company: [
    { label: "About", href: "/about" },
    { label: "Careers", href: "#" },
    { label: "Contact", href: "#" },
    { label: "Press", href: "#" },
  ],
  Legal: [
    { label: "Privacy Policy", href: "#" },
    { label: "Terms of Service", href: "#" },
    { label: "HIPAA Compliance", href: "#" },
    { label: "BAA", href: "#" },
  ],
};

const metrics = [
  { icon: Users, value: "2,400+", label: "Practices" },
  { icon: Target, value: "99.2%", label: "Accuracy" },
  { icon: DollarSign, value: "$847M", label: "Processed" },
  { icon: Activity, value: "98%", label: "Uptime" },
];

export default function Landing() {
  const [openFaq, setOpenFaq] = useState<number | null>(null);

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container mx-auto flex h-16 items-center justify-between gap-4 px-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <Stethoscope className="h-5 w-5" />
            </div>
            <span className="text-xl font-semibold">Full Arch CRM</span>
          </div>
          <nav className="hidden items-center gap-6 md:flex">
            <a
              href="#features"
              className="text-sm text-muted-foreground transition-colors hover:text-foreground"
              data-testid="link-features"
            >
              Features
            </a>
            <a
              href="#pricing"
              className="text-sm text-muted-foreground transition-colors hover:text-foreground"
              data-testid="link-pricing"
            >
              Pricing
            </a>
            <a
              href="/about"
              className="text-sm text-muted-foreground transition-colors hover:text-foreground"
              data-testid="link-about"
            >
              About
            </a>
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
        <section className="container mx-auto px-4 py-20 lg:py-32">
          <div className="mx-auto max-w-4xl text-center">
            <Badge variant="secondary" className="mb-6 gap-2" data-testid="badge-hipaa">
              <Shield className="h-3.5 w-3.5" />
              HIPAA Compliant
            </Badge>
            <h1 className="mb-6 text-4xl font-bold tracking-tight sm:text-5xl lg:text-6xl">
              The #1 AI-Powered Platform for{" "}
              <span className="text-primary">Full Arch Dental Implant Billing</span>
            </h1>
            <p className="mx-auto mb-10 max-w-2xl text-lg text-muted-foreground">
              Streamline medical billing, maximize insurance reimbursements, and grow your implant
              practice with AI-powered coding, claims management, and practice analytics.
            </p>
            <div className="flex flex-col items-center justify-center gap-4 sm:flex-row">
              <Button size="lg" asChild className="gap-2" data-testid="button-start-trial">
                <a href="/api/login">
                  Start Free Trial
                  <ArrowRight className="h-4 w-4" />
                </a>
              </Button>
              <Button
                size="lg"
                variant="outline"
                className="gap-2"
                data-testid="button-watch-demo"
                onClick={() =>
                  document.getElementById("how-it-works")?.scrollIntoView({ behavior: "smooth" })
                }
              >
                <Calendar className="h-4 w-4" />
                Watch Demo
              </Button>
            </div>
            <div className="mt-16 border-t pt-8">
              <p className="mb-6 text-sm text-muted-foreground">
                Trusted by 500+ implant practices nationwide
              </p>
              <div className="grid grid-cols-2 gap-6 sm:grid-cols-4">
                <div className="text-center">
                  <p className="text-2xl font-bold">99.2%</p>
                  <p className="text-sm text-muted-foreground">Coding Accuracy</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold">$2.4M+</p>
                  <p className="text-sm text-muted-foreground">Claims Processed</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold">78%</p>
                  <p className="text-sm text-muted-foreground">Appeal Success Rate</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold">4.9/5</p>
                  <p className="text-sm text-muted-foreground">Rating</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="border-y bg-muted/30 py-16">
          <div className="container mx-auto px-4">
            <div className="mx-auto grid max-w-4xl grid-cols-2 gap-8 sm:grid-cols-4">
              {metrics.map((metric) => (
                <Card key={metric.label} className="text-center">
                  <CardContent className="flex flex-col items-center gap-2 p-6">
                    <metric.icon className="h-6 w-6 text-primary" />
                    <p className="text-3xl font-bold" data-testid={`metric-${metric.label.toLowerCase()}`}>
                      {metric.value}
                    </p>
                    <p className="text-sm text-muted-foreground">{metric.label}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>

        <section id="features" className="py-20">
          <div className="container mx-auto px-4">
            <div className="mb-12 text-center">
              <Badge variant="secondary" className="mb-4 gap-2">
                <Zap className="h-3.5 w-3.5" />
                Features
              </Badge>
              <h2 className="mb-4 text-3xl font-bold sm:text-4xl">
                Everything You Need to Maximize Revenue
              </h2>
              <p className="mx-auto max-w-2xl text-muted-foreground">
                Purpose-built tools for full arch dental implant billing, from AI-powered coding to
                predictive analytics.
              </p>
            </div>
            <div className="mx-auto grid max-w-6xl gap-6 md:grid-cols-2 lg:grid-cols-3">
              {features.map((feature) => (
                <Card
                  key={feature.title}
                  className="hover-elevate transition-all duration-200"
                  data-testid={`card-feature-${feature.title.toLowerCase().replace(/\s+/g, "-")}`}
                >
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

        <section className="border-y bg-muted/30 py-20">
          <div className="container mx-auto px-4">
            <div className="mb-12 text-center">
              <Badge variant="secondary" className="mb-4 gap-2">
                <Star className="h-3.5 w-3.5" />
                Testimonials
              </Badge>
              <h2 className="mb-4 text-3xl font-bold sm:text-4xl">
                Trusted by Leading Implant Practices
              </h2>
              <p className="mx-auto max-w-2xl text-muted-foreground">
                See how Full Arch CRM is helping dental professionals transform their billing
                workflows and increase revenue.
              </p>
            </div>
            <div className="mx-auto grid max-w-6xl gap-6 md:grid-cols-3">
              {testimonials.map((t) => (
                <Card key={t.name} data-testid={`card-testimonial-${t.initials.toLowerCase()}`}>
                  <CardContent className="flex flex-col gap-4 p-6">
                    <div className="flex gap-1">
                      {[...Array(5)].map((_, i) => (
                        <Star
                          key={i}
                          className="h-4 w-4 fill-yellow-400 text-yellow-400"
                        />
                      ))}
                    </div>
                    <p className="flex-1 text-sm text-muted-foreground">"{t.quote}"</p>
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
                        {t.initials}
                      </div>
                      <div>
                        <p className="text-sm font-semibold">{t.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {t.title}, {t.location}
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>

        <section id="pricing" className="py-20">
          <div className="container mx-auto px-4">
            <div className="mb-12 text-center">
              <Badge variant="secondary" className="mb-4 gap-2">
                <DollarSign className="h-3.5 w-3.5" />
                Pricing
              </Badge>
              <h2 className="mb-4 text-3xl font-bold sm:text-4xl">
                Simple, Transparent Pricing
              </h2>
              <p className="mx-auto max-w-2xl text-muted-foreground">
                Choose the plan that fits your practice. All plans include a 30-day free trial.
              </p>
            </div>
            <div className="mx-auto grid max-w-5xl gap-6 md:grid-cols-3">
              {pricingTiers.map((tier) => (
                <Card
                  key={tier.name}
                  className={`relative flex flex-col ${tier.popular ? "border-primary shadow-lg" : ""}`}
                  data-testid={`card-pricing-${tier.name.toLowerCase()}`}
                >
                  {tier.popular && (
                    <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                      <Badge data-testid="badge-most-popular">
                        <Award className="mr-1 h-3 w-3" />
                        Most Popular
                      </Badge>
                    </div>
                  )}
                  <CardContent className="flex flex-1 flex-col p-6">
                    <h3 className="text-lg font-semibold">{tier.name}</h3>
                    <p className="mt-1 text-sm text-muted-foreground">{tier.description}</p>
                    <div className="my-6">
                      <span className="text-4xl font-bold">{tier.price}</span>
                      <span className="text-muted-foreground">/mo</span>
                    </div>
                    <ul className="mb-8 flex-1 space-y-3">
                      {tier.features.map((f) => (
                        <li key={f} className="flex items-start gap-2 text-sm">
                          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                          <span>{f}</span>
                        </li>
                      ))}
                    </ul>
                    <Button
                      asChild
                      variant={tier.popular ? "default" : "outline"}
                      className="w-full"
                      data-testid={`button-pricing-${tier.name.toLowerCase()}`}
                    >
                      <a href="/api/login">{tier.cta}</a>
                    </Button>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>

        <section id="how-it-works" className="border-y bg-muted/30 py-20">
          <div className="container mx-auto px-4">
            <div className="mb-12 text-center">
              <Badge variant="secondary" className="mb-4 gap-2">
                <Clock className="h-3.5 w-3.5" />
                How It Works
              </Badge>
              <h2 className="mb-4 text-3xl font-bold sm:text-4xl">
                Up and Running in Minutes
              </h2>
              <p className="mx-auto max-w-2xl text-muted-foreground">
                Four simple steps to transform your dental implant billing workflow.
              </p>
            </div>
            <div className="mx-auto grid max-w-5xl gap-8 sm:grid-cols-2 lg:grid-cols-4">
              {steps.map((step, index) => (
                <div key={step.title} className="text-center" data-testid={`step-${index + 1}`}>
                  <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-primary text-xl font-bold text-primary-foreground">
                    {index + 1}
                  </div>
                  <h3 className="mb-2 text-lg font-semibold">{step.title}</h3>
                  <p className="text-sm text-muted-foreground">{step.description}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="faq" className="py-20">
          <div className="container mx-auto px-4">
            <div className="mb-12 text-center">
              <Badge variant="secondary" className="mb-4 gap-2">
                <MessageSquare className="h-3.5 w-3.5" />
                FAQ
              </Badge>
              <h2 className="mb-4 text-3xl font-bold sm:text-4xl">
                Frequently Asked Questions
              </h2>
              <p className="mx-auto max-w-2xl text-muted-foreground">
                Got questions? We have answers. If you don't see what you're looking for, reach out
                to our team.
              </p>
            </div>
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

        <section className="bg-primary py-16 text-primary-foreground">
          <div className="container mx-auto px-4 text-center">
            <h2 className="mb-4 text-3xl font-bold">
              Ready to Transform Your Implant Practice Billing?
            </h2>
            <p className="mx-auto mb-8 max-w-xl opacity-90">
              Join 500+ practices that have increased their collections by an average of 32%.
            </p>
            <div className="flex flex-col items-center justify-center gap-4 sm:flex-row">
              <Button
                size="lg"
                variant="secondary"
                asChild
                className="gap-2"
                data-testid="button-cta-start-trial"
              >
                <a href="/api/login">
                  Start Free Trial
                  <ArrowRight className="h-4 w-4" />
                </a>
              </Button>
              <Button
                size="lg"
                variant="outline"
                className="gap-2 border-primary-foreground/30 text-primary-foreground backdrop-blur"
                data-testid="button-cta-schedule-demo"
              >
                Schedule a Demo
              </Button>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t py-12">
        <div className="container mx-auto px-4">
          <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
            {Object.entries(footerLinks).map(([category, links]) => (
              <div key={category}>
                <h4 className="mb-4 text-sm font-semibold">{category}</h4>
                <ul className="space-y-2">
                  {links.map((link) => (
                    <li key={link.label}>
                      <a
                        href={link.href}
                        className="text-sm text-muted-foreground transition-colors hover:text-foreground"
                        data-testid={`link-footer-${link.label.toLowerCase().replace(/\s+/g, "-")}`}
                      >
                        {link.label}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
          <div className="mt-12 flex flex-col items-center justify-between gap-4 border-t pt-8 sm:flex-row">
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
              <span>SOC 2 Type II Certified</span>
            </div>
            <span>|</span>
            <div className="flex items-center gap-1">
              <Shield className="h-3 w-3" />
              <span>HIPAA Compliant</span>
            </div>
            <span>|</span>
            <div className="flex items-center gap-1">
              <Activity className="h-3 w-3" />
              <span>99.9% Uptime SLA</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
