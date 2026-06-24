import {
  AlertTriangle,
  BookOpenText,
  CheckCircle2,
  ClipboardList,
  DatabaseZap,
  FileSearch,
  GitBranch,
  ListChecks,
  LockKeyhole,
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

const sections = [
  {
    title: "Что мы создаем",
    icon: DatabaseZap,
    body: [
      "Data Intelligence Agent Local Tooling — это внутренний безопасный слой инструментов для исследования реальных локальных данных.",
      "Это не SQL-консоль и не production chat для менеджера. Это набор approved tools, через которые агент и команда смогут понимать, что реально есть в данных.",
      "Главная цель: быстрее находить data gaps, source mappings, linkage gaps и evidence coverage, чтобы semantic catalog, dashboards, reports и manager AI chat строились на фактах, а не на догадках.",
    ],
  },
  {
    title: "Как это будет работать",
    icon: GitBranch,
    body: [
      "Поток будет таким: агент -> packages.tools -> service layer -> repository -> database.",
      "Агент не получает прямой доступ к базе, не пишет SQL и не видит секреты. Он вызывает только зарегистрированные tools с понятными параметрами.",
      "Каждый tool сам применяет allowlist, row caps, masking, data-class checks и audit/logging.",
    ],
  },
  {
    title: "Что можно будет смотреть",
    icon: FileSearch,
    body: [
      "Список approved datasets и query registry entries.",
      "Профили полей: null rate, top values, coverage, data class, source system.",
      "Linkage coverage: Salesforce lead -> person_uid -> CareStack patient.",
      "Evidence coverage: consultation, treatment, payment, lead source, owner, location, campaign.",
      "Маленькие masked samples: по умолчанию 25 строк, максимум 100.",
    ],
  },
  {
    title: "Что будет запрещено",
    icon: ShieldCheck,
    body: [
      "Raw SQL от агента, UI, dashboard, chat или LLM planner.",
      "Direct database access агентом.",
      "Raw provider payload output как обычный результат.",
      "PHI output в V1.",
      "Full table dumps, uncapped samples, exports, XLSX и scheduled reports в этой миссии.",
    ],
  },
  {
    title: "Какие результаты получим",
    icon: ListChecks,
    body: [
      "Field profile: какие значения реально встречаются в поле и насколько оно заполнено.",
      "Linkage brief: где теряются связи между Salesforce, Fusion person и CareStack.",
      "Evidence coverage brief: хватает ли данных, чтобы считать paid lead, consultation completed, payment received или treatment accepted.",
      "Semantic mapping proposal: например, какие raw source values нужно свести в paid_social/facebook.",
      "Gap brief: готовая формулировка проблемы, которую можно превратить в Linear issue.",
    ],
  },
  {
    title: "Почему это первый шаг",
    icon: BookOpenText,
    body: [
      "Перед тем как делать умный manager chat или новые dashboards, нужно понимать реальные данные.",
      "Эта страница фиксирует замысел: сначала безопасный tool layer, потом UI workbench, потом agent/chat поверх тех же approved tools.",
      "Так мы сохраняем одно правило: facts -> semantic terms -> query specs -> policy -> services -> read models -> dashboard/chat/agent.",
    ],
  },
];

const linearItems = [
  ["ENG-286", "Data Intelligence Agent Local Tooling V1"],
  ["ENG-287", "DIA-01 Mission Setup And Linear Sync"],
  ["ENG-288", "DIA-02 Tool Policy And Allowlist"],
  ["ENG-289", "DIA-03 Data Intelligence Service Contract"],
  ["ENG-290", "DIA-04 Query Registry And Dataset Discovery Tool"],
  ["ENG-291", "DIA-05 Field Profile Tool"],
  ["ENG-292", "DIA-06 Linkage And Source Coverage Tool"],
  ["ENG-293", "DIA-07 Evidence Coverage Tool"],
  ["ENG-294", "DIA-08 Bounded Masked Sample Tool"],
  ["ENG-295", "DIA-09 Semantic Mapping Proposal Generator"],
  ["ENG-296", "DIA-10 Gap Brief Writer"],
  ["ENG-297", "DIA-11 Audit And Tool Call Logging"],
  ["ENG-298", "DIA-12 Local Workbench Visibility"],
  ["ENG-299", "DIA-13 Verification And Production Review"],
];

const implementedSlice = [
  "packages.data_intelligence service contract and executable V1 policy",
  "data_intelligence_discover tool for approved datasets, fields, masks, and limits",
  "data_intelligence_preflight tool for allow/deny checks before execution",
  "data_intelligence_profile_field tool for service-owned aggregate field profiles with row count, null count, null rate, and top values",
  "data_intelligence_linkage_coverage tool for Salesforce to Fusion person to CareStack patient coverage with bounded masked examples",
  "data_intelligence_evidence_coverage tool for source, campaign, owner, location, consultation, treatment, invoice, and payment evidence coverage",
  "data_intelligence_bounded_sample tool for capped masked samples across identity linkage, leads, consultations, and billing evidence",
  "data_intelligence_semantic_mapping_proposal tool for review-only source and campaign mapping candidates",
  "data_intelligence_person_journey_proposals tool for review-only field/event registry proposal drafts",
  "person journey coverage metadata for lead attribution, contact/account linkage, opportunity stages, sale outcomes, treatment, and billing revenue posture",
  "AnalyticsCatalogReviewService ingestion path for persisting eligible person-journey drafts as proposed review rows",
  "data_intelligence_gap_brief tool for non-sensitive evidence, linkage, and semantic mapping gap summaries",
  "standardized audit metadata for DIA success and denial paths: decisions, datasets, fields, data classes, masks, limits, and result posture",
  "tests for denied PHI, raw payloads, exports, writes, unknown fields, and uncapped samples",
];

const workbenchStatus = [
  {
    label: "Policy",
    value: "Active",
    detail: "Executable allowlist, caps, masks, and denial rules are in `packages.data_intelligence`.",
  },
  {
    label: "Tool registry",
    value: "Active",
    detail: "DIA tools are registered in `packages.tools.registry`; no raw SQL parameter exists.",
  },
  {
    label: "Data path",
    value: "Service-owned",
    detail: "Tools call service methods; agents and workbench code do not call repositories.",
  },
  {
    label: "UI posture",
    value: "Internal docs",
    detail: "This page is internal/IAP protected and does not depend on MSW or frontend mock data.",
  },
];

const approvedDatasets = [
  {
    id: "lead_source_profile",
    title: "Lead Source Profile",
    classes: ["ops", "integration_metadata"],
    actions: ["discover", "preflight", "profile", "evidence", "sample", "mapping", "gap brief"],
    fields: "lead_source, source_provider, campaign, owner_id, lead_status, created_at, location_id",
  },
  {
    id: "identity_linkage",
    title: "Identity Linkage Coverage",
    classes: ["identity", "integration_metadata"],
    actions: ["discover", "preflight", "linkage", "sample", "gap brief"],
    fields: "person_uid, salesforce_lead_id, carestack_patient_id, linkage_status, source_provider",
  },
  {
    id: "consultation_followup",
    title: "Consultation Follow-up Evidence",
    classes: ["ops", "integration_metadata"],
    actions: ["discover", "preflight", "profile", "evidence", "sample", "gap brief"],
    fields: "consultation_status, scheduled_at, last_followup_at, owner_id, location_id",
  },
  {
    id: "treatment_revenue",
    title: "Treatment Revenue Evidence",
    classes: ["billing", "integration_metadata", "ops"],
    actions: ["discover", "preflight", "profile", "evidence", "sample", "gap brief"],
    fields: "payment_amount_bucket, payment_date, payment_kind, treatment_status, location_id",
  },
];

const toolCatalog = [
  {
    name: "data_intelligence_discover",
    output: "Policy and dataset metadata",
    posture: "No database read",
  },
  {
    name: "data_intelligence_preflight",
    output: "Allow, deny, or clarification posture",
    posture: "No database read",
  },
  {
    name: "data_intelligence_profile_field",
    output: "Aggregate row count, null rate, and top values",
    posture: "Aggregate only",
  },
  {
    name: "data_intelligence_linkage_coverage",
    output: "Linkage rates plus bounded masked examples",
    posture: "Masked sample",
  },
  {
    name: "data_intelligence_evidence_coverage",
    output: "Evidence coverage across source, consultation, treatment, and billing",
    posture: "Aggregate only",
  },
  {
    name: "data_intelligence_bounded_sample",
    output: "Capped masked rows for approved datasets",
    posture: "25 default, 100 hard cap",
  },
  {
    name: "data_intelligence_semantic_mapping_proposal",
    output: "Review-only semantic source mapping candidates",
    posture: "No catalog mutation",
  },
  {
    name: "data_intelligence_person_journey_proposals",
    output: "Review-only person journey field/event/state proposal drafts",
    posture: "Lead-to-sale coverage, blocked/internal/deferred entries fail closed",
  },
  {
    name: "catalog_review_person_journey_ingestion",
    output: "Persist eligible drafts as Semantic Catalog proposed review rows",
    posture: "No auto-approval",
  },
  {
    name: "data_intelligence_gap_brief",
    output: "Non-sensitive findings and recommended Linear follow-up titles",
    posture: "Planning summary",
  },
];

const runbookSteps = [
  "Start with `data_intelligence_discover` to confirm datasets, fields, masks, and limits.",
  "Use `data_intelligence_preflight` before execution when the requested action or fields are uncertain.",
  "Run profile, linkage, evidence, sample, mapping, person-journey proposal, or gap-brief tools only through the backend tool path.",
  "Attach result summaries to Linear or mission runtime files; do not paste PHI, raw payloads, or full row dumps.",
  "Open implementation follow-ups only after a human reviews mapping proposals and gap brief recommendations.",
];

const usageExamples = [
  {
    title: "1. Обычным языком",
    description:
      "Пользователь или агент формулирует задачу обычным языком. Planner не выполняет SQL, а переводит намерение в approved action с параметрами. Если данных или разрешений не хватает, он просит уточнение.",
    example: `User:
  Покажи, какие lead sources чаще всего встречаются
  и сколько из них пустые.

Planner converts to:
  action: profile_field
  dataset_id: lead_source_profile
  field: lead_source
  top_limit: 50

Tool returns:
  field profile or clarification`,
  },
  {
    title: "2. Из Dev UI",
    description:
      "Оператор или разработчик открывает эту страницу, может ввести вопрос обычным языком или выбрать действие кнопкой. UI не пишет SQL, а отправляет намерение или структурированный request в backend.",
    example: `Action: Profile field
Dataset: lead_source_profile
Field: lead_source
Limit: 50

Result:
- row count
- null rate
- top values
- data class
- warnings`,
  },
  {
    title: "3. Из внутреннего агентного tool call",
    description:
      "Codex/Claude или будущий внутренний агент вызывает только зарегистрированный tool. Tool принимает JSON-friendly параметры, сам применяет policy и вызывает service layer.",
    example: `tool: data_intelligence_preflight
params:
  action: field_profile
  dataset_id: lead_source_profile
  fields: [lead_source]
  top_limit: 50
  output_level: aggregate

Forbidden:
  sql: SELECT ...`,
  },
  {
    title: "4. Из Orchestrator worker задачи",
    description:
      "Worker получает Linear issue, например про source mappings. Вместо ручного SQL он просит approved tool построить profile или gap brief и прикладывает результат к отчету.",
    example: `Linear: ENG-295 Semantic Mapping Proposal Generator
Worker asks:
  tool: data_intelligence_semantic_mapping_proposal
  top_limit: 50

Output:
  paid_social/facebook, paid_search/google, referral, unknown/unmapped candidates
  no catalog mutation`,
  },
  {
    title: "5. Через будущий backend endpoint для UI",
    description:
      "Когда появятся backend endpoints для workbench, UI будет дергать API, а API будет вызывать те же service-owned tools. Это даст кнопки без прямого доступа frontend к базе.",
    example: `POST /api/dev/data-intelligence/profile-field
{
  "dataset_id": "lead_source_profile",
  "field": "lead_source",
  "top_limit": 50
}

API -> service -> repository -> database`,
  },
  {
    title: "6. Для person journey registry",
    description:
      "Когда появляются новые Salesforce/CareStack/person timeline поля или events, tool превращает structured registry в review-only proposals. Blocked/internal/deferred entries видны ревьюеру, но не становятся executable analytics.",
    example: `tool: data_intelligence_person_journey_proposals
params:
  statuses: [approved_candidate, review_only]

Output:
  Semantic Catalog proposal drafts
  executable: false
  approval_allowed: false
  no catalog mutation`,
  },
  {
    title: "7. Для gap brief",
    description:
      "Когда мы видим проблему в данных, инструмент сможет сформировать краткий brief: что сломано, какие вопросы затронуты, насколько критично и какую Linear-задачу открыть.",
    example: `Gap:
  many paid leads have missing source mapping

Tool:
  data_intelligence_gap_brief

Affected questions:
  Q02, Q05, Q16, Q17, Q20

Recommended Linear:
  Add source mapping for unmapped paid lead campaign values`,
  },
];

export default function DataIntelligencePage() {
  return (
    <div className="space-y-5 p-8">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <DatabaseZap className="h-5 w-5 text-primary" />
            <h1 className="text-2xl font-semibold tracking-tight">
              Data Intelligence
            </h1>
          </div>
          <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
            Русское описание внутреннего Data Intelligence Agent tooling:
            что создаем, как это будет работать, какие данные можно будет
            исследовать и какие ограничения защищают систему.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant="outline" className="gap-1">
            <ShieldCheck className="h-3.5 w-3.5" />
            Internal/IAP protected
          </Badge>
          <Badge variant="outline" className="gap-1">
            <DatabaseZap className="h-3.5 w-3.5" />
            No raw SQL
          </Badge>
          <Badge variant="outline" className="gap-1">
            <AlertTriangle className="h-3.5 w-3.5" />
            PHI denied V1
          </Badge>
        </div>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Коротко</CardTitle>
          <CardDescription>
            Это документационная страница и статус первого backend slice.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm leading-6">
          <p>
            Мы создаем не отдельного “бота с доступом к базе”, а безопасный
            backend tool layer. Через него внутренний агент сможет задавать
            строго разрешенные вопросы к данным: какие поля заполнены, какие
            значения встречаются, где нет связей, где не хватает evidence для
            метрик.
          </p>
          <p>
            Интерфейс будет оболочкой поверх этих tools. Сначала здесь будет
            документация и статус миссии, затем появятся действия вроде
            “Profile field”, “Check linkage”, “Evidence coverage”, “Masked
            sample”, “Generate gap brief”.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Что уже появилось в первом slice</CardTitle>
          <CardDescription>
            Это foundation для следующих действий, еще не полноценная
            профилировка данных.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2 text-sm leading-6 text-muted-foreground">
            {implementedSlice.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {workbenchStatus.map((item) => (
          <Card key={item.label}>
            <CardHeader className="space-y-2">
              <div className="flex items-center justify-between gap-3">
                <CardTitle className="text-sm">{item.label}</CardTitle>
                <Badge variant="outline">{item.value}</Badge>
              </div>
              <CardDescription className="leading-5">
                {item.detail}
              </CardDescription>
            </CardHeader>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <ClipboardList className="h-4 w-4 text-primary" />
            <CardTitle>Workbench status</CardTitle>
          </div>
          <CardDescription>
            Local/dev поверхность показывает, какие datasets и tools уже
            разрешены. Она не дергает mock API и не показывает выдуманные
            результаты.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 lg:grid-cols-2">
          {approvedDatasets.map((dataset) => (
            <div key={dataset.id} className="rounded-md border bg-muted/20 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline">{dataset.id}</Badge>
                <h2 className="text-sm font-semibold">{dataset.title}</h2>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {dataset.classes.map((dataClass) => (
                  <Badge key={dataClass} variant="secondary">
                    {dataClass}
                  </Badge>
                ))}
              </div>
              <p className="mt-3 text-sm leading-6 text-muted-foreground">
                Fields: {dataset.fields}
              </p>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                Actions: {dataset.actions.join(", ")}
              </p>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-primary" />
            <CardTitle>Registered tools</CardTitle>
          </div>
          <CardDescription>
            Это фактический allowlisted tool surface для Data Intelligence V1.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 lg:grid-cols-2">
            {toolCatalog.map((tool) => (
              <div
                key={tool.name}
                className="grid gap-2 rounded-md border bg-muted/20 p-4"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <code className="text-xs font-semibold">{tool.name}</code>
                  <Badge variant="outline">{tool.posture}</Badge>
                </div>
                <p className="text-sm leading-6 text-muted-foreground">
                  {tool.output}
                </p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Audit contract</CardTitle>
          <CardDescription>
            Каждый Data Intelligence tool call пишет audit metadata для
            успешных и отклоненных запросов.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
          <p>
            В audit row сохраняются: tool name, decision, action, datasets,
            fields, data classes, masks, output level, row limit, top limit,
            result posture и hard-deny flags для SQL, raw payload, PHI,
            export и write-действий.
          </p>
          <p>
            В audit metadata не должны попадать PHI, raw provider payloads,
            emails, телефоны, имена пациентов, секреты, SQL text или полный
            row output. Audit нужен, чтобы объяснить кто запускал инструмент,
            с какими ограничениями и почему запрос был разрешен или отклонен.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <LockKeyhole className="h-4 w-4 text-primary" />
            <CardTitle>Operator runbook</CardTitle>
          </div>
          <CardDescription>
            Как использовать workbench и tools без нарушения архитектурных
            границ.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ol className="space-y-2 text-sm leading-6 text-muted-foreground">
            {runbookSteps.map((step, index) => (
              <li key={step}>
                {index + 1}. {step}
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Как будет вызываться и запускаться</CardTitle>
          <CardDescription>
            Планируемые способы использования после реализации backend tools.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm leading-6 text-muted-foreground">
            На первом этапе это будет обычный язык на входе, но не свободный
            SQL-доступ к базе. Пользователь или агент пишет, что хочет
            понять, planner переводит запрос в approved action, а backend
            проверяет policy, лимиты, masks и audit. Если запрос опасный,
            слишком широкий или данных не хватает, tool возвращает deny или
            clarification вместо результата.
          </p>
          <div className="grid gap-4 lg:grid-cols-2">
            {usageExamples.map((item) => (
              <div key={item.title} className="rounded-md border bg-muted/20 p-4">
                <h2 className="text-sm font-semibold">{item.title}</h2>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  {item.description}
                </p>
                <pre className="mt-3 overflow-auto rounded-md border bg-background p-3 text-xs leading-5">
                  {item.example}
                </pre>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        {sections.map((section) => {
          const Icon = section.icon;
          return (
            <Card key={section.title}>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Icon className="h-4 w-4 text-primary" />
                  <CardTitle className="text-base">{section.title}</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2 text-sm leading-6 text-muted-foreground">
                  {section.body.map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Linear mission tree</CardTitle>
          <CardDescription>
            Все задачи идут под существующим umbrella Semantic Context And
            Analytics Foundation.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-2 md:grid-cols-2">
            {linearItems.map(([id, title]) => (
              <div
                key={id}
                className="flex items-start gap-2 rounded-md border bg-muted/20 p-3"
              >
                <Badge variant={id === "ENG-286" ? "default" : "outline"}>
                  {id}
                </Badge>
                <div className="text-sm leading-5">{title}</div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
