import fs from "node:fs";
import path from "node:path";
import type { ReactNode } from "react";
import Link from "next/link";
import {
  BookOpen,
  CheckCircle2,
  CircleDot,
  Clock3,
  FileText,
  PauseCircle,
  ShieldCheck,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { CatalogProposalReview } from "@/components/semantic/CatalogProposalReview";
import { cn } from "@/lib/utils";

type WorkbenchDoc = {
  key: string;
  title: string;
  description: string;
  filename: string;
  readiness: "ready" | "draft" | "deferred";
};

type RoadmapStatus = "done" | "current" | "planned" | "deferred";

type RoadmapItem = {
  id: string;
  title: string;
  status: RoadmapStatus;
  note: string;
  why: string;
  delivered: string;
  secondLayer: string[];
  linearRefs: string[];
};

const DOCS: WorkbenchDoc[] = [
  {
    key: "overview-ru",
    title: "Russian overview",
    description: "Plain-language Russian overview of the full mission and product value.",
    filename: "semantic-analytics-foundation-overview-ru.md",
    readiness: "ready",
  },
  {
    key: "questions",
    title: "Manager questions",
    description: "Prioritized doctor/operator and marketing director questions.",
    filename: "manager-analytics-questions-v1.md",
    readiness: "ready",
  },
  {
    key: "catalog",
    title: "Semantic catalog",
    description: "Governed terms, data classes, output posture, and ambiguities.",
    filename: "semantic-analytics-catalog-v1.md",
    readiness: "ready",
  },
  {
    key: "catalog-review",
    title: "Catalog review",
    description: "Human review workflow for proposed mappings and catalog learning.",
    filename: "semantic-catalog-proposal-review-v1.md",
    readiness: "ready",
  },
  {
    key: "query-spec",
    title: "Query spec",
    description: "Structured JSON request contract for UI, chat, and services.",
    filename: "structured-analytics-query-spec-v1.md",
    readiness: "ready",
  },
  {
    key: "policy",
    title: "Policy preflight",
    description: "Pre-execution data-class, row-level, PHI, billing, and audit rules.",
    filename: "analytics-policy-preflight-v1.md",
    readiness: "ready",
  },
  {
    key: "registry",
    title: "Query registry",
    description: "Allowlisted service-owned query metadata and discovery contract.",
    filename: "analytics-query-registry-v1.md",
    readiness: "ready",
  },
  {
    key: "read-models",
    title: "Read models",
    description: "Service-computed manager analytics read-model contracts.",
    filename: "manager-analytics-read-models-v1.md",
    readiness: "ready",
  },
  {
    key: "manager-chat",
    title: "Manager AI Chat",
    description: "Deterministic V1 chat planner and aggregate execution flow.",
    filename: "manager-ai-chat-v1.md",
    readiness: "ready",
  },
  {
    key: "unified-lifecycle",
    title: "Unified lifecycle",
    description: "Read-only person lifecycle foundation aligned to manager workflow needs.",
    filename: "unified-person-lifecycle-foundation-v1.md",
    readiness: "draft",
  },
  {
    key: "person-journey-registry",
    title: "Person journey registry",
    description: "Governed field and event registry for person-linked analytics.",
    filename: "person-journey-field-event-registry-v1.md",
    readiness: "draft",
  },
  {
    key: "exports",
    title: "Exports",
    description: "CSV-only aggregate export and saved-report definition policy.",
    filename: "exports-and-saved-reports-v1.md",
    readiness: "ready",
  },
  {
    key: "agent",
    title: "Data Intelligence Agent",
    description: "Read-only local tooling boundary, samples, masking, and gap briefs.",
    filename: "data-intelligence-agent-contract-v1.md",
    readiness: "ready",
  },
];

function bundledDocDir() {
  return path.resolve(process.cwd(), "content/semantic-analytics");
}

const ROADMAP_STATUS_META: Record<
  RoadmapStatus,
  {
    label: string;
    icon: typeof CheckCircle2;
    className: string;
  }
> = {
  done: {
    label: "Сделано",
    icon: CheckCircle2,
    className: "border-emerald-500/40 bg-emerald-500/10 text-emerald-700",
  },
  current: {
    label: "Сейчас",
    icon: CircleDot,
    className: "border-blue-500/40 bg-blue-500/10 text-blue-700",
  },
  planned: {
    label: "Будем делать",
    icon: Clock3,
    className: "border-amber-500/40 bg-amber-500/10 text-amber-700",
  },
  deferred: {
    label: "Отложено",
    icon: PauseCircle,
    className: "border-slate-400/50 bg-slate-100 text-slate-700",
  },
};

const MISSION_ROADMAP: RoadmapItem[] = [
  {
    id: "1",
    title: "Manager Analytics Questions V1",
    status: "done",
    note: "30 стартовых вопросов зафиксированы и сгруппированы.",
    why: "Это исходный бизнес-список вопросов, от которого зависят catalog terms, read models, dashboard panels, chat intents and reports.",
    delivered: "Questions grouped by workflow, priority, expected output shape, ambiguity and manager role.",
    secondLayer: [
      "Connect every question to production usage evidence and owner feedback.",
      "Add new questions from real manager chat, reports and dashboard usage.",
      "Split questions that need row-level worklists from aggregate-only questions.",
    ],
    linearRefs: ["ENG-272", "ENG-331"],
  },
  {
    id: "2",
    title: "Semantic Analytics Catalog V1",
    status: "done",
    note: "Первые terms, definitions, data classes, rules and review status описаны.",
    why: "Catalog keeps business meaning stable so dashboard, chat, reports and agents do not invent different definitions for the same metric.",
    delivered: "Initial governed terms, synonyms, data classes, output posture, ambiguity notes and review status.",
    secondLayer: [
      "Move more terms from documentation into approved catalog versions.",
      "Detect conflicts when new approved mappings change existing business meaning.",
      "Keep catalog changes linked to questions, read models, reports and agent tools.",
    ],
    linearRefs: ["ENG-273", "ENG-313", "ENG-332", "ENG-319", "ENG-320"],
  },
  {
    id: "2A",
    title: "Semantic Catalog Proposal Review V1",
    status: "done",
    note: "Persisted proposals, human review, approved versions, audit, API contracts and production UI deployed.",
    why: "Business meaning must be reviewed by a human before it can change production metrics or downstream AI answers.",
    delivered: "Persisted proposals, approve/reject/unresolved flows, approved versions, audit metadata, API contracts and production UI.",
    secondLayer: [
      "Let Data Intelligence Agent create review-only proposals from profiling and gap briefs.",
      "Add stronger impact preview before approval.",
      "Ensure all downstream consumers use approved versions only.",
      "Run final production verification for proposal-to-approved-catalog flow.",
    ],
    linearRefs: ["ENG-313", "ENG-314", "ENG-315", "ENG-316", "ENG-317", "ENG-330", "ENG-318", "ENG-319", "ENG-320", "ENG-321"],
  },
  {
    id: "2B",
    title: "Semantic Catalog Follow-up Handoff",
    status: "done",
    note: "Second-layer hardening has moved into the new Semantic Analytics Execution Layer V1 mission.",
    why: "This keeps Foundation V1 closed while preserving the next safety work as an owned Linear mission.",
    delivered: "ENG-318, ENG-319, ENG-320 and ENG-321 now live under ENG-330 in the Execution Layer V1 project.",
    secondLayer: [
      "ENG-318: ingest Data Intelligence Agent proposals into the review queue.",
      "ENG-319: show known, likely and unknown impact across registry/read models/dashboard/chat/reports.",
      "ENG-320: make approved catalog versions the only downstream catalog source.",
      "ENG-321: verify the full flow in production review.",
    ],
    linearRefs: ["ENG-330", "ENG-318", "ENG-319", "ENG-320", "ENG-321"],
  },
  {
    id: "11",
    title: "Semantic Analytics Execution Layer V1",
    status: "current",
    note: "Active second-layer mission: catalog execution safety, runtime surfaces, and production verification.",
    why: "The foundation is complete; the next value is making approved catalog, policy, services, chat, reports and agent tools work together at runtime.",
    delivered: "Linear project and mission control are created, with ENG-330 as parent and ENG-318 through ENG-338 as tracked execution tasks.",
    secondLayer: [
      "Slice 1: catalog execution safety through proposal ingestion, impact preview, approved consumption and verification.",
      "Slice 2: runtime surfaces for question usage evidence, query validation, policy gates, metadata, manager chat, saved reports and workbench signals.",
      "Deferred scope remains explicit: row-level exports, XLSX, scheduled reports and full LLM planner.",
    ],
    linearRefs: ["ENG-330", "ENG-331", "ENG-332", "ENG-333", "ENG-334", "ENG-335", "ENG-336", "ENG-337", "ENG-338"],
  },
  {
    id: "12",
    title: "Unified Person Lifecycle Foundation V1",
    status: "planned",
    note: "Strategy handoff drafted for a read-only person lifecycle layer over existing Salesforce, CareStack and financial evidence.",
    why: "The manager profile spec confirms the next layer: one human operational view, but implemented through identity, source links, projections, semantic terms, read models and context packs.",
    delivered: "Planning artifact, candidate mission, Orchestrator handoff and workbench documentation are drafted with readiness set to needs decision.",
    secondLayer: [
      "Audit existing evidence coverage before claiming lifecycle or revenue completeness.",
      "Define source-of-truth precedence and lifecycle stage taxonomy before implementation.",
      "Keep Manager Chat V2 registry-driven and defer write-back until read-only contracts stabilize.",
    ],
    linearRefs: ["candidate mission"],
  },
  {
    id: "13",
    title: "Person Journey Field/Event Registry V1",
    status: "current",
    note: "New person-linked fields and timeline events are being mapped before analytics or agents treat them as business truth.",
    why: "Lead.extra, Salesforce Contact/Account/Opportunity/OpportunityHistory, tasks, calls and timeline events can add person meaning over time; they need governed source, data-class and catalog posture.",
    delivered: "Draft registry captures attribution, conversion linkage, opportunity events, blocked debug fields, production-vs-branch state and downstream usage rules.",
    secondLayer: [
      "Turn registry entries into Data Intelligence review-only proposals.",
      "Promote reviewed entries into Semantic Catalog approved versions.",
      "Bind approved entries to Query Registry/read-model metadata before manager answers or charts use them.",
      "Keep frontend enum support separate from backend deployment readiness.",
    ],
    linearRefs: ["ENG-386", "ENG-385", "ENG-371"],
  },
  {
    id: "3",
    title: "Structured Analytics Query Spec",
    status: "done",
    note: "JSON contract и запрет raw SQL описаны.",
    why: "UI, chat and agents need a constrained request language so no surface sends raw SQL or bypasses policy.",
    delivered: "Structured intents, filters, dimensions, metrics, output levels and export request posture.",
    secondLayer: [
      "Expand spec coverage as new manager questions and row-level worklists are approved.",
      "Add validation examples for manager chat and agent-generated specs.",
      "Version spec changes when output shapes or allowed intents change.",
    ],
    linearRefs: ["ENG-274", "ENG-333"],
  },
  {
    id: "4",
    title: "Analytics Policy Preflight",
    status: "done",
    note: "Role, data-class, PHI, billing, row-level, export and audit checks описаны.",
    why: "Every analytics request must be allowed, denied or clarified before any service executes it.",
    delivered: "Pre-execution posture for role, data class, PHI, billing-sensitive, row-level, export and audit rules.",
    secondLayer: [
      "Turn more policy decisions from documented posture into executable gates as new surfaces ship.",
      "Add row-level field allowlists before row-level worklists or exports.",
      "Add policy test cases for manager chat and Data Intelligence Agent tools.",
    ],
    linearRefs: ["ENG-275", "ENG-334"],
  },
  {
    id: "5",
    title: "Analytics Services And Query Registry V1",
    status: "done",
    note: "Approved query ids, service-owned execution and registry metadata есть.",
    why: "Dashboard, chat, reports and agents must call approved services instead of repositories, SQL or copied frontend calculations.",
    delivered: "Allowlisted query ids, service-owned execution paths, registry metadata and data-class posture.",
    secondLayer: [
      "Tie registry entries to approved catalog versions and affected manager questions.",
      "Add registry metadata for impact preview and downstream consumption checks.",
      "Expand query coverage only when policy and read-model contracts are stable.",
    ],
    linearRefs: ["ENG-276", "ENG-277", "ENG-335", "ENG-319", "ENG-320"],
  },
  {
    id: "6",
    title: "Manager Analytics Read Models V1",
    status: "done",
    note: "Read models подключены к Project Manager dashboard на real backend data.",
    why: "Managers need stable aggregate contracts that can be reused by dashboard, chat and reports without rebuilding metrics in each UI.",
    delivered: "Lead conversion, paid leads, consultation follow-up and treatment revenue read models on real backend data.",
    secondLayer: [
      "Add approved catalog consumption to read-model metadata.",
      "Add impact preview links from terms to read models.",
      "Define first row-level worklists after allowlists and audit rules are ready.",
    ],
    linearRefs: ["ENG-278", "ENG-335", "ENG-319", "ENG-320"],
  },
  {
    id: "7",
    title: "Data Intelligence Agent V1",
    status: "done",
    note: "Read-only local tooling, masking, samples, mappings and gap briefs готовы.",
    why: "The internal agent should find data quality gaps and mapping candidates without direct DB access or write authority.",
    delivered: "Read-only local tooling boundary, masking, sample posture, mapping and gap-brief contracts.",
    secondLayer: [
      "Connect agent outputs to catalog proposal ingestion.",
      "Add OpenAI-powered semantic proposal generation only inside approved tools and audit boundaries.",
      "Keep agent suggestions review-only; never auto-approve catalog meaning.",
    ],
    linearRefs: ["ENG-279", "ENG-286", "ENG-295", "ENG-318"],
  },
  {
    id: "8",
    title: "Manager AI Chat V1",
    status: "done",
    note: "Deterministic planner flow, approved query specs, catalog terms, policy preflight and aggregate execution path are defined.",
    why: "Manager chat should explain approved analytics results, not create new metric definitions or execute SQL.",
    delivered: "Deterministic planner flow, query spec, policy preflight and aggregate execution contract.",
    secondLayer: [
      "Add full LLM planner after approved catalog consumption and policy tests are stronger.",
      "Add clarification behavior for ambiguous questions.",
      "Audit chat planning, query execution and answer explanation.",
    ],
    linearRefs: ["ENG-280", "ENG-336", "ENG-320", "later"],
  },
  {
    id: "9",
    title: "Exports And Saved Reports V1",
    status: "done",
    note: "CSV-only aggregate export and saved-report definition policy are defined; scheduled reports and XLSX remain deferred.",
    why: "Reports must use the same definitions as dashboard/chat and exports must not become an uncontrolled data leak.",
    delivered: "CSV-only aggregate export posture and saved-report definition policy.",
    secondLayer: [
      "Persist saved report definitions against approved query specs.",
      "Add scheduled reports only after audit, owner and delivery policy are ready.",
      "Add XLSX and row-level exports only after field allowlists and export policy are stable.",
    ],
    linearRefs: ["ENG-281", "ENG-337", "later"],
  },
  {
    id: "10",
    title: "Semantic Analytics Workbench V1",
    status: "done",
    note: "Internal docs page exists and renders the mission plan from repo artifacts.",
    why: "The team needs one visible place to understand what exists, why it exists, what remains and which Linear tasks own the second layer.",
    delivered: "Internal documentation page, roadmap status, production-bundled docs and catalog review UI entry point.",
    secondLayer: [
      "Keep every done section paired with explicit not-done-yet notes.",
      "Show Linear follow-ups for second-layer work instead of losing them in chat history.",
      "Add richer verification/readiness signals when Orchestrator runtime state is connected.",
    ],
    linearRefs: ["ENG-282", "ENG-338"],
  },
  {
    id: "later",
    title: "Row-level exports, XLSX, scheduled reports, full LLM planner",
    status: "deferred",
    note: "Deferred until field allowlists, export policy, audit and access rules are stable.",
    why: "These are high-leverage surfaces, but they can expose sensitive row-level data or let AI shape metrics before the guardrails are complete.",
    delivered: "Deferred scope is visible and intentionally not mixed into V1 completion claims.",
    secondLayer: [
      "Define row-level field allowlists.",
      "Implement XLSX and scheduled reports with export audit.",
      "Promote full LLM planner only after policy, catalog and approved query execution are production-safe.",
    ],
    linearRefs: ["candidate missions"],
  },
];

function missionDir() {
  return path.resolve(
    process.cwd(),
    "../..",
    ".agents/orchestration/semantic-context-analytics-foundation",
  );
}

function readDoc(filename: string) {
  const candidates = [
    path.join(bundledDocDir(), filename),
    path.join(missionDir(), filename),
  ];

  for (const filePath of candidates) {
    try {
      return {
        exists: true,
        path: filePath,
        content: fs.readFileSync(filePath, "utf8"),
      };
    } catch {
      // Try the next candidate. Production images carry the bundled docs;
      // local checkouts may still read the mission artifacts directly.
    }
  }

  return {
    exists: false,
    path: candidates[0] ?? filename,
    content: "Source artifact is not available in this runtime.",
  };
}

function extractHeadings(markdown: string) {
  return markdown
    .split("\n")
    .filter((line) => line.startsWith("## ") || line.startsWith("### "))
    .slice(0, 18)
    .map((line) => line.replace(/^#+\s*/, ""));
}

function RoadmapBadge({ status }: { status: RoadmapStatus }) {
  const meta = ROADMAP_STATUS_META[status];
  const Icon = meta.icon;

  return (
    <Badge variant="outline" className={cn("gap-1", meta.className)}>
      <Icon className="h-3.5 w-3.5" />
      {meta.label}
    </Badge>
  );
}

function RoadmapDetail({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="space-y-1">
      <div className="text-[11px] font-semibold uppercase text-muted-foreground">
        {label}
      </div>
      {children}
    </div>
  );
}

function MissionRoadmapSummary() {
  return (
    <section className="space-y-3 rounded-md border bg-muted/20 p-4">
      <div className="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h2 className="text-sm font-semibold">Статус плана</h2>
          <p className="mt-1 max-w-3xl text-xs leading-5 text-muted-foreground">
            Foundation V1 закрыт. Этот блок показывает, что дал первый слой,
            что вынесено во второй слой и где новая active mission живет в
            Linear.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {(["done", "current", "planned", "deferred"] as RoadmapStatus[]).map(
            (status) => (
              <RoadmapBadge key={status} status={status} />
            ),
          )}
        </div>
      </div>
      <div className="grid gap-3">
        {MISSION_ROADMAP.map((item) => (
          <div
            key={item.id}
            className="rounded-md border bg-background/70 p-3"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="text-sm font-medium">
                {item.id}. {item.title}
              </div>
              <RoadmapBadge status={item.status} />
            </div>
            <p className="mt-2 text-xs leading-5 text-muted-foreground">
              {item.note}
            </p>
            <div className="mt-3 grid gap-3 lg:grid-cols-2">
              <RoadmapDetail label="Зачем это нужно">
                <p className="text-xs leading-5 text-muted-foreground">
                  {item.why}
                </p>
              </RoadmapDetail>
              <RoadmapDetail label="Что дал V1">
                <p className="text-xs leading-5 text-muted-foreground">
                  {item.delivered}
                </p>
              </RoadmapDetail>
              <RoadmapDetail label="Что осталось вторым слоем">
                <ul className="space-y-1 text-xs leading-5 text-muted-foreground">
                  {item.secondLayer.map((entry) => (
                    <li key={entry}>- {entry}</li>
                  ))}
                </ul>
              </RoadmapDetail>
              <RoadmapDetail label="Linear память">
                <div className="flex flex-wrap gap-1.5">
                  {item.linearRefs.map((ref) => (
                    <Badge key={ref} variant="outline" className="text-[11px]">
                      {ref}
                    </Badge>
                  ))}
                </div>
              </RoadmapDetail>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

export default function SemanticAnalyticsWorkbenchPage({
  searchParams,
}: {
  searchParams?: { doc?: string };
}) {
  const selectedKey = searchParams?.doc ?? "questions";
  const fallbackDoc = DOCS[0];
  if (!fallbackDoc) {
    throw new Error("Semantic analytics workbench has no configured docs.");
  }
  const selected = DOCS.find((doc) => doc.key === selectedKey) ?? fallbackDoc;
  const source = readDoc(selected.filename);
  const headings = extractHeadings(source.content);

  return (
    <div className="space-y-5 p-8">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <BookOpen className="h-5 w-5 text-primary" />
            <h1 className="text-2xl font-semibold tracking-tight">
              Semantic Analytics
            </h1>
          </div>
          <p className="max-w-3xl text-sm text-muted-foreground">
            Internal workbench for manager questions, governed semantic terms,
            catalog review workflow, query specs, policy posture, registry
            metadata, read models, and Data Intelligence Agent boundaries.
          </p>
        </div>
        <div className="flex flex-col gap-2 sm:items-end">
          <div className="flex flex-wrap gap-2">
            <Badge variant="outline" className="gap-1 border-green-500/40 bg-green-500/10">
              <CheckCircle2 className="h-3.5 w-3.5" />
              Row-level allowed
            </Badge>
            <Badge variant="outline" className="gap-1">
              <ShieldCheck className="h-3.5 w-3.5" />
              Docs + persisted review
            </Badge>
          </div>
          <Button asChild size="sm" className="w-fit">
            <Link href="/dev/semantic-analytics?doc=overview-ru">
              Открыть русское описание
            </Link>
          </Button>
        </div>
      </header>

      <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
        <aside className="space-y-3">
          {DOCS.map((doc) => {
            const active = doc.key === selected.key;
            return (
              <Link
                key={doc.key}
                href={`/dev/semantic-analytics?doc=${doc.key}`}
                className={cn(
                  "block rounded-md border bg-card p-3 transition-colors hover:bg-accent",
                  active && "border-primary bg-primary/5",
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <FileText className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm font-medium">{doc.title}</span>
                  </div>
                  <Badge variant={doc.readiness === "ready" ? "default" : "outline"}>
                    {doc.readiness}
                  </Badge>
                </div>
                <p className="mt-2 text-xs leading-5 text-muted-foreground">
                  {doc.description}
                </p>
              </Link>
            );
          })}
        </aside>

        <main className="space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <CardTitle>{selected.title}</CardTitle>
                  <CardDescription>{selected.description}</CardDescription>
                </div>
                <Button asChild variant="outline" size="sm">
                  <Link href={`/dev/semantic-analytics?doc=${selected.key}`}>
                    {selected.filename}
                  </Link>
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline">ops</Badge>
                <Badge variant="outline">identity</Badge>
                <Badge variant="outline">billing</Badge>
                <Badge variant="outline">PHI-adjacent</Badge>
                <Badge variant="outline">integration metadata</Badge>
                <Badge variant="outline">aggregate CSV</Badge>
              </div>

              {selected.key === "overview-ru" && <MissionRoadmapSummary />}
              {selected.key === "catalog-review" && <CatalogProposalReview />}

              {headings.length > 0 && (
                <div className="rounded-md border bg-muted/30 p-3">
                  <div className="mb-2 text-xs font-semibold uppercase text-muted-foreground">
                    Document outline
                  </div>
                  <div className="grid gap-1 md:grid-cols-2">
                    {headings.map((heading) => (
                      <div key={heading} className="text-xs text-muted-foreground">
                        {heading}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <pre className="max-h-[calc(100vh-360px)] overflow-auto rounded-md border bg-background p-4 whitespace-pre-wrap text-xs leading-6">
                {source.content}
              </pre>
            </CardContent>
          </Card>
        </main>
      </div>
    </div>
  );
}
