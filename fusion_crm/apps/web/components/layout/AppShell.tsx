"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  BarChart2,
  BriefcaseBusiness,
  LineChart,
  LayoutDashboard,
  Plug,
  Users,
  FileSearch,
  Workflow,
  LogOut,
  Search,
  Settings,
  Send,
  FileText,
  ShieldOff,
  Code2,
  ChevronRight,
  CreditCard,
  DatabaseZap,
  Bot,
  ListTree,
  GitBranch,
  GitMerge,
  Megaphone,
  GitFork,
  TrendingUp,
  PhoneCall,
  DollarSign,
  Grid2x2,
  Route,
  Store,
  Target,
  AlertTriangle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { useLogout, useSession } from "@/lib/api/hooks/useAuth";
import { useIngestHealth } from "@/lib/api/hooks/useIngestHealth";
import { PeopleSearchDialog } from "@/components/people/PeopleSearchDialog";

const devSectionItems = [
  { href: "/integrations", label: "Integrations", icon: Plug },
  { href: "/integrations/carestack", label: "CareStack inspector", icon: Plug },
  { href: "/persons", label: "Persons", icon: Users },
  { href: "/people/search", label: "Find a person", icon: Search },
];

const outreachItems = [
  { href: "/outreach/campaigns", label: "Campaigns", icon: Send },
  { href: "/outreach/templates", label: "Templates", icon: FileText },
  { href: "/outreach/suppressions", label: "Suppressions", icon: ShieldOff },
];

// Legacy analytics dashboards (ENG-468) — the non-RIAP pages that pre-date the
// Revenue Intelligence platform. Stay under the flat "Analytics" header.
const analyticsItems = [
  { href: "/analytics/marketing", label: "Marketing", icon: Megaphone },
  { href: "/analytics/seo", label: "SEO", icon: Search },
  { href: "/analytics/sales", label: "Sales", icon: TrendingUp },
  { href: "/analytics/calls", label: "Calls", icon: PhoneCall },
];

// Analytics PRO — Revenue Intelligence Analytics Platform V1 (ENG-504): the 14
// market.md pages, grouped under their own collapsible section (ENG-579).
const analyticsProItems = [
  { href: "/analytics/executive", label: "Executive", icon: LayoutDashboard },
  {
    href: "/analytics/marketing-performance",
    label: "Marketing performance",
    icon: Target,
  },
  { href: "/analytics/funnel", label: "Full funnel", icon: GitFork },
  { href: "/analytics/revenue", label: "Revenue", icon: DollarSign },
  { href: "/analytics/cohort", label: "Cohort", icon: Grid2x2 },
  {
    href: "/analytics/patient-journey",
    label: "Patient journey",
    icon: Route,
  },
  { href: "/analytics/caller", label: "Caller perf.", icon: PhoneCall },
  { href: "/analytics/coordinator", label: "Coordinator perf.", icon: Users },
  { href: "/analytics/doctor", label: "Doctor perf.", icon: BriefcaseBusiness },
  { href: "/analytics/cost", label: "Cost intelligence", icon: BarChart2 },
  {
    href: "/analytics/bottlenecks",
    label: "Bottlenecks",
    icon: AlertTriangle,
  },
  { href: "/analytics/vendor", label: "Vendor perf.", icon: Store },
  { href: "/analytics/attribution", label: "Attribution", icon: GitMerge },
  {
    href: "/analytics/revenue-influence",
    label: "Rev. influence",
    icon: BarChart2,
  },
];

const devToolItems = [
  { href: "/dev/inspector", label: "Inspector", icon: FileSearch },
  { href: "/dev/graph", label: "Graph", icon: Workflow },
  { href: "/dev/semantic-analytics", label: "Semantic analytics", icon: FileText },
  { href: "/dev/data-intelligence", label: "Data intelligence", icon: DatabaseZap },
  { href: "/dev/agent-runtime", label: "Agent runtime", icon: Bot },
  { href: "/dev/lead-sources", label: "Lead sources", icon: ListTree },
];

const allDevHrefs = [
  ...devSectionItems.map((i) => i.href),
  ...outreachItems.map((i) => i.href),
  ...devToolItems.map((i) => i.href),
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const session = useSession();
  const logout = useLogout();
  const showDevTools = true;
  const ingestHealth = useIngestHealth();

  const isDevRoute = allDevHrefs.some(
    (href) => pathname === href || pathname.startsWith(`${href}/`),
  );
  const [devOpen, setDevOpen] = useState(isDevRoute);

  const isAnalyticsProRoute = analyticsProItems.some(
    (item) => pathname === item.href || pathname.startsWith(`${item.href}/`),
  );
  const [analyticsProOpen, setAnalyticsProOpen] = useState(isAnalyticsProRoute);
  const [searchOpen, setSearchOpen] = useState(false);
  const [shortcutLabel, setShortcutLabel] = useState("Ctrl K");

  // Cmd+K / Ctrl+K opens the global people search dialog from anywhere.
  useEffect(() => {
    if (navigator.platform.toLowerCase().includes("mac")) {
      setShortcutLabel("⌘K");
    }

    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSearchOpen((v) => !v);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  async function onLogout() {
    await logout.mutateAsync();
    router.push("/login");
  }

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-60 flex-col border-r bg-muted/40">
        <div className="flex items-center gap-2 px-5 py-5">
          <div className="h-8 w-8 rounded-md bg-primary" />
          <div>
            <div className="text-sm font-semibold">Fusion CRM</div>
            <div className="text-xs text-muted-foreground">Staff console</div>
          </div>
        </div>
        <div className="px-3 pb-2">
          <button
            type="button"
            onClick={() => setSearchOpen(true)}
            className="flex w-full items-center gap-2 rounded-md border bg-background px-3 py-2 text-left text-xs text-muted-foreground transition-colors hover:bg-accent"
            aria-label="Open people search (Cmd+K)"
          >
            <Search className="h-3.5 w-3.5" />
            <span className="flex-1">Find a person…</span>
            <kbd className="rounded border bg-muted px-1 font-mono text-[10px]">
              {shortcutLabel}
            </kbd>
          </button>
        </div>
        <nav className="flex-1 space-y-1 px-3 py-2">
          <Link
            href="/dashboard"
            className={cn(
              "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
              pathname === "/dashboard" || pathname.startsWith("/dashboard/")
                ? "bg-primary/10 text-primary"
                : "text-muted-foreground hover:bg-accent hover:text-foreground",
            )}
          >
            <LayoutDashboard className="h-4 w-4" />
            Dashboard
          </Link>

          <Link
            href="/project-manager"
            className={cn(
              "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
              pathname === "/project-manager"
                ? "bg-primary/10 text-primary"
                : "text-muted-foreground hover:bg-accent hover:text-foreground",
            )}
          >
            <BriefcaseBusiness className="h-4 w-4" />
            Project Manager
          </Link>

          <Link
            href="/project-manager/leads"
            className={cn(
              "ml-5 flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
              pathname === "/project-manager/leads" ||
                pathname.startsWith("/project-manager/leads/")
                ? "bg-primary/10 text-primary"
                : "text-muted-foreground hover:bg-accent hover:text-foreground",
            )}
          >
            <Users className="h-4 w-4" />
            Leads
          </Link>

          <Link
            href="/project-manager/payments"
            className={cn(
              "ml-5 flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
              pathname === "/project-manager/payments" ||
                pathname.startsWith("/project-manager/payments/")
                ? "bg-primary/10 text-primary"
                : "text-muted-foreground hover:bg-accent hover:text-foreground",
            )}
          >
            <CreditCard className="h-4 w-4" />
            Payments
          </Link>

          <Link
            href="/project-manager/attribution"
            className={cn(
              "ml-5 flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
              pathname === "/project-manager/attribution" ||
                pathname.startsWith("/project-manager/attribution/")
                ? "bg-primary/10 text-primary"
                : "text-muted-foreground hover:bg-accent hover:text-foreground",
            )}
          >
            <GitBranch className="h-4 w-4" />
            Attribution
          </Link>

          {/* Analytics section — dashboards (ENG-468) */}
          <div className="pt-2">
            <div className="px-3 pb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Analytics
            </div>
            {analyticsItems.map((item) => {
              const active =
                pathname === item.href || pathname.startsWith(`${item.href}/`);
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                    active
                      ? "bg-primary/10 text-primary"
                      : "text-muted-foreground hover:bg-accent hover:text-foreground",
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {item.label}
                </Link>
              );
            })}
          </div>

          {/* Analytics PRO — Revenue Intelligence platform (ENG-504), collapsible */}
          <div className="pt-2">
            <button
              type="button"
              onClick={() => setAnalyticsProOpen((v) => !v)}
              className={cn(
                "flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isAnalyticsProRoute
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground",
              )}
            >
              <LineChart className="h-4 w-4" />
              <span className="flex-1 text-left">Analytics PRO</span>
              <ChevronRight
                className={cn(
                  "h-3.5 w-3.5 transition-transform duration-200",
                  analyticsProOpen && "rotate-90",
                )}
              />
            </button>

            {analyticsProOpen && (
              <div className="ml-2 space-y-0.5 border-l pl-2 pt-1">
                {analyticsProItems.map((item) => {
                  const active =
                    pathname === item.href ||
                    pathname.startsWith(`${item.href}/`);
                  const Icon = item.icon;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={cn(
                        "flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                        active
                          ? "bg-primary/10 text-primary"
                          : "text-muted-foreground hover:bg-accent hover:text-foreground",
                      )}
                    >
                      <Icon className="h-4 w-4" />
                      {item.label}
                    </Link>
                  );
                })}
              </div>
            )}
          </div>

          {/* Dev section — collapsible */}
          <div className="pt-2">
            <button
              type="button"
              onClick={() => setDevOpen((v) => !v)}
              className={cn(
                "flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isDevRoute
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground",
              )}
            >
              <Code2 className="h-4 w-4" />
              <span className="flex-1 text-left">Dev</span>
              {ingestHealth.data && (
                <span
                  title={`Ingest: ${ingestHealth.data.status}`}
                  className={cn(
                    "h-2 w-2 rounded-full",
                    ingestHealth.data.status === "ok" && "bg-green-500",
                    ingestHealth.data.status === "stale" && "bg-yellow-500",
                    ingestHealth.data.status === "failed" && "bg-red-500",
                    ingestHealth.data.status === "unknown" && "bg-gray-400",
                  )}
                />
              )}
              <ChevronRight
                className={cn(
                  "h-3.5 w-3.5 transition-transform duration-200",
                  devOpen && "rotate-90",
                )}
              />
            </button>

            {devOpen && (
              <div className="ml-2 space-y-0.5 border-l pl-2 pt-1">
                {devSectionItems.map((item) => {
                  const active =
                    pathname === item.href ||
                    pathname.startsWith(`${item.href}/`);
                  const Icon = item.icon;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={cn(
                        "flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                        active
                          ? "bg-primary/10 text-primary"
                          : "text-muted-foreground hover:bg-accent hover:text-foreground",
                      )}
                    >
                      <Icon className="h-4 w-4" />
                      {item.label}
                    </Link>
                  );
                })}

                <div className="pt-2">
                  <div className="px-3 pb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    Outreach
                  </div>
                  {outreachItems.map((item) => {
                    const active =
                      pathname === item.href ||
                      pathname.startsWith(`${item.href}/`);
                    const Icon = item.icon;
                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        className={cn(
                          "flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                          active
                            ? "bg-primary/10 text-primary"
                            : "text-muted-foreground hover:bg-accent hover:text-foreground",
                        )}
                      >
                        <Icon className="h-4 w-4" />
                        {item.label}
                      </Link>
                    );
                  })}
                </div>

                {showDevTools && (
                  <div className="pt-2">
                    <div className="px-3 pb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      Tools
                    </div>
                    {devToolItems.map((item) => {
                      const active = pathname.startsWith(item.href);
                      const Icon = item.icon;
                      return (
                        <Link
                          key={item.href}
                          href={item.href}
                          className={cn(
                            "flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                            active
                              ? "bg-primary/10 text-primary"
                              : "text-muted-foreground hover:bg-accent hover:text-foreground",
                          )}
                        >
                          <Icon className="h-4 w-4" />
                          {item.label}
                        </Link>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
          </div>
        </nav>
        <div className="border-t px-3 py-3 space-y-1">
          <Link
            href="/settings/tenant"
            className={cn(
              "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
              pathname.startsWith("/settings")
                ? "bg-primary/10 text-primary"
                : "text-muted-foreground hover:bg-accent hover:text-foreground",
            )}
          >
            <Settings className="h-4 w-4" />
            Settings
          </Link>
          <div className="px-2 py-1 text-xs text-muted-foreground">
            {session.data?.email ?? "—"}
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-start gap-2"
            onClick={onLogout}
          >
            <LogOut className="h-4 w-4" />
            Sign out
          </Button>
        </div>
      </aside>
      <main className="flex-1 overflow-auto">{children}</main>

      <PeopleSearchDialog
        open={searchOpen}
        onClose={() => setSearchOpen(false)}
      />
    </div>
  );
}
