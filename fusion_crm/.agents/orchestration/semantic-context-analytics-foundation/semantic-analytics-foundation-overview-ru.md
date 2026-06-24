# Semantic Context And Analytics Foundation — русское описание

## Коротко

Мы построили первый слой общего аналитического фундамента для Fusion CRM.

Цель этого фундамента — чтобы dashboard, manager AI chat, внутренний Data
Intelligence Agent, отчеты и будущие workflow-функции использовали одни и те
же бизнес-термины, правила доступа, сервисы и read models.

Без такого слоя каждая поверхность начинает считать метрики по-своему:
dashboard считает одно, чат объясняет другое, агент видит третье, а отчеты
расходятся с продуктом. Эта миссия нужна, чтобы такого не было.

## Что мы хотели получить

Изначальная идея была такой:

```text
facts -> semantic terms -> query specs -> policy -> services -> read models -> dashboard/chatbot/agent
```

То есть мы не начинаем с красивого графика на dashboard. Мы сначала фиксируем:

- какие вопросы реально задают менеджеры, доктор, оператор и маркетинг;
- какие бизнес-термины стоят за этими вопросами;
- какие данные разрешено использовать;
- где aggregate-only, а где когда-нибудь можно row-level;
- какие backend services отвечают за расчет;
- какие read models можно показывать в UI, chat и reports.

## Почему это важно

Fusion CRM собирает данные из Salesforce и CareStack. Эти данные приходят как
сырые provider payloads, события, связи, appointments, leads, treatments,
payments и operational tasks.

Сырые данные сами по себе еще не являются бизнес-правдой. Например:

- `LeadSource = Facebook` в Salesforce;
- appointment в CareStack;
- invoice или payment transaction;
- consultation completed;
- patient linked to source record.

Это evidence. Чтобы использовать это в аналитике, нужно определить, что это
значит для бизнеса.

## Разница между context facts и analytics catalog

Это важная архитектурная граница.

### Context facts

`context_fact` — это нормализованный факт о человеке, событии или связи.

Примеры:

- Person X has evidence of appointment completed.
- Person X has payment evidence.
- Lead came from Salesforce source Y.
- Person X is linked to CareStack patient record.

Это факты. Они ближе к timeline, identity, provenance и workflow context.

### Analytics catalog

`analytics catalog` — это бизнес-термины и метрики поверх фактов.

Примеры:

- `paid_lead` = lead with payment evidence within attribution window.
- `converted_to_consultation` = lead linked to completed consultation.
- `facebook_source` = raw sources mapped to paid_social/facebook.
- `treatment_revenue` = aggregate revenue evidence from approved billing events.

Это уже не один факт, а правило интерпретации данных.

## Что мы сделали в этой миссии

### 1. Manager Analytics Questions V1

Мы зафиксировали стартовый набор реальных manager questions.

Это вопросы, которые важны для:

- доктора;
- операционного директора;
- директора маркетинга;
- project manager;
- internal analytics/data intelligence workflow.

Примеры классов вопросов:

- какие источники лидов дают оплату;
- где лиды доходят до consultation;
- где много no-show;
- какие follow-up tasks просрочены;
- где есть treatment/payment evidence;
- какие источники и locations требуют внимания.

Зачем это нужно: вопросы определяют, какие semantic terms и read models нужны
первыми. Без вопросов легко построить абстрактную аналитику, которая не
помогает управлять клиникой.

### 2. Semantic Analytics Catalog V1

Мы описали первые бизнес-термины:

- `lead_source`;
- `paid_lead`;
- `consultation_scheduled`;
- `consultation_completed`;
- `consultation_no_show`;
- `payment_received`;
- `revenue_evidence`;
- `stale_followup`;
- `carestack_linked`;
- и другие.

Для терминов описаны:

- смысл;
- synonyms;
- source references;
- data classes;
- allowed outputs;
- row-level/aggregate posture;
- ambiguity notes;
- review status.

Зачем это нужно: LLM, dashboard и reports не должны сами придумывать, что
означает `paid lead` или `converted`.

### 3. Structured Analytics Query Spec

Мы описали structured JSON contract для аналитических запросов.

Идея: UI, chat или agent не передают raw SQL. Они передают ограниченный query
spec:

- query id;
- filters;
- output level;
- dimensions;
- metrics;
- params.

Зачем это нужно: LLM не должен писать SQL. Он может только выбрать approved
query и заполнить разрешенные параметры.

### 4. Analytics Policy Preflight

Мы описали слой preflight policy.

Он нужен до выполнения запроса, чтобы проверить:

- role/access;
- data classes;
- PHI;
- billing-sensitive data;
- row-level vs aggregate;
- export policy;
- audit requirements.

Зачем это нужно: безопасность должна быть частью контракта, а не промптом в
чате.

### 5. Analytics Services And Query Registry V1

Мы добавили allowlisted analytics tools and registry.

Поддержанные query ids:

- `lead_source_profile.v1`;
- `lead_conversion_funnel.v1`;
- `paid_leads_by_source.v1`;
- `consultation_followup_worklist.v1`;
- `treatment_revenue_evidence.v1`.

Каждый query id связан с service-owned backend execution path.

Зачем это нужно: dashboard, chat и agents вызывают approved tools/services, а
не repositories, database или SQL напрямую.

### 6. Manager Analytics Read Models V1

Мы подключили первые read models:

- `lead_conversion`;
- `paid_leads`;
- `consultation_followup`;
- `treatment_revenue`.

Они aggregate-only в V1.

Зачем это нужно: dashboard и manager chat должны получать стабильные
read-model contracts, а не собирать метрики на фронте из случайных полей.

### 7. Data Intelligence Agent V1

Мы описали роль Data Intelligence Agent.

Он нужен для:

- source profiling;
- mapping suggestions;
- gap briefs;
- semantic catalog improvements;
- finding missing mappings and data quality issues.

Важное ограничение: agent не получает прямой database access. Он должен
работать через approved read-only tools, masks, limits and audit boundaries.

### 8. Manager AI Chat V1

Мы описали manager chat flow:

```text
question -> planner -> query spec -> policy preflight -> approved service -> result explanation -> audit
```

В V1 planner deterministic. Future LLM planner можно добавить позже, но он
все равно должен выдавать structured query spec and pass policy preflight.

Зачем это нужно: manager chat должен объяснять approved analytics results, а
не фантазировать метрики.

### 9. Exports And Saved Reports V1

Мы приняли V1-ограничение:

- CSV exports only;
- aggregate results only;
- saved report definitions only;
- no XLSX yet;
- no scheduled reports yet;
- no row-level export;
- audit required.

Зачем это нужно: export — это рискованная поверхность. Сначала aggregate CSV,
потом можно расширять.

### 10. Semantic Analytics Workbench V1

Мы добавили страницу:

```text
/dev/semantic-analytics
```

Она читает mission documentation прямо из frontend. Это сделано, чтобы можно
было открыть интерфейс и посмотреть:

- questions;
- catalog;
- query spec;
- policy;
- registry;
- read models;
- manager chat;
- exports;
- Data Intelligence Agent contract.

Теперь документация не спрятана только в repo. Ее можно читать с фронта.

## Что уже видно в продукте

Мы подключили semantic analytics foundation к Project Manager dashboard.

Страница:

```text
/project-manager
```

Теперь показывает блок `Semantic analytics`, где видны approved read models:

- Lead source profile;
- Lead conversion;
- Paid leads;
- Consultation follow-up;
- Treatment revenue.

Для каждого read model видно:

- query id;
- metrics;
- data classes;
- CSV availability;
- link to documentation.

Это уже реальные данные через local FastAPI backend, не MSW mock.

## Что не сделано намеренно и остается вторым слоем

Мы не считаем `done` словом "больше никогда не трогать". В этой миссии `done`
означает: V1-основание есть, production-safe contract зафиксирован, а
углубление записано отдельно и не потеряно.

Статус на сейчас: `Semantic Context And Analytics Foundation` закрыт как V1
baseline. Второй слой вынесен в новую Linear mission:
`Semantic Analytics Execution Layer V1`.

Mission control: `ENG-330`.

### Manager Analytics Questions V1

V1 дал стартовый список вопросов и приоритетов.

Второй слой:

- связывать каждый вопрос с реальным usage evidence из dashboard, reports and
  manager chat;
- добавлять новые вопросы из работы клиники;
- разделять aggregate questions and row-level worklist questions.

Linear memory: `ENG-272`, `ENG-331`.

### Semantic Analytics Catalog V1

V1 дал первые business terms, data classes, allowed outputs and review status.

Второй слой:

- переносить больше терминов из документов в approved catalog versions;
- проверять conflict detection, когда новый mapping меняет старый смысл;
- связывать catalog terms с questions, query registry, read models, reports and
  agent tools.

Linear memory: `ENG-273`, `ENG-313`, `ENG-332`, `ENG-319`, `ENG-320`.

### Semantic Catalog Proposal Review V1

V1 дал persisted proposals, human review, approved versions, audit, API
contracts and production UI.

Второй слой:

- `ENG-318`: Data Intelligence Agent создает review-only proposals из profiling
  and gap briefs;
- `ENG-319`: impact preview показывает affected questions, registry entries,
  read models, dashboard panels, chat answers, reports and exports;
- `ENG-320`: downstream services consume approved catalog versions only;
- `ENG-321`: final production verification for proposal -> approval -> version
  -> audit -> downstream read.

Это не было включено в V1, потому что agent layer and downstream consumption
guardrails нужно подключать после того, как human review storage уже существует.

Linear mission memory: `ENG-330`, `ENG-318`, `ENG-319`, `ENG-320`, `ENG-321`.

### Structured Analytics Query Spec

V1 дал JSON contract and raw SQL prohibition.

Второй слой:

- расширять intents только вместе с approved policy and service execution;
- добавлять validation examples for manager chat and agents;
- version query specs when output shapes change.

Linear memory: `ENG-274`, `ENG-333`.

### Analytics Policy Preflight

V1 дал allow/deny/clarify posture for role, data class, PHI, billing,
row-level, export and audit.

Второй слой:

- превращать documented policy в executable gates по мере появления новых
  surfaces;
- определить row-level field allowlists;
- добавить policy tests для manager chat and Data Intelligence Agent tools.

Linear memory: `ENG-275`, `ENG-334`.

### Analytics Services And Query Registry V1

V1 дал approved query ids and service-owned execution.

Второй слой:

- связать registry entries с approved catalog versions;
- добавить metadata для impact preview;
- расширять query coverage только после stable policy/read-model contracts.

Linear memory: `ENG-276`, `ENG-277`, `ENG-335`, `ENG-319`, `ENG-320`.

### Manager Analytics Read Models V1

V1 дал aggregate read models на реальных backend data.

Второй слой:

- добавить approved catalog consumption в read-model metadata;
- связать read models with impact preview;
- проектировать первые row-level worklists только после allowlists and audit
  rules.

Linear memory: `ENG-278`, `ENG-335`, `ENG-319`, `ENG-320`.

### Data Intelligence Agent V1

V1 дал safe read-only local tooling boundary, masking, samples, mappings and
gap briefs.

Второй слой:

- подключить agent outputs к catalog proposal ingestion;
- добавить OpenAI-powered semantic proposal generation only through approved
  tools/API;
- сохранить правило: agent proposes, human approves.

Linear memory: `ENG-279`, `ENG-286`, `ENG-295`, `ENG-318`.

### Manager AI Chat V1

V1 дал deterministic planner flow over approved query specs, catalog terms,
policy preflight and aggregate service execution.

Второй слой:

- добавить full LLM planner только после approved catalog consumption path;
- добавить clarification behavior для ambiguous questions;
- audit planner, query execution and final explanation.

Linear memory: `ENG-280`, `ENG-336`, `ENG-320`, future LLM planner mission.

### Exports And Saved Reports V1

V1 дал CSV-only aggregate export posture and saved-report definition policy.

Второй слой:

- persisted saved report definitions;
- scheduled reports;
- XLSX;
- row-level exports only after field allowlists and export policy are stable.

Linear memory: `ENG-281`, `ENG-337`, future export/reporting missions.

### Semantic Analytics Workbench V1

V1 дал internal page where docs, roadmap, catalog review and plan status are
visible in product.

Второй слой:

- keep every completed section paired with explicit second-layer notes;
- show Linear follow-ups beside the product plan;
- add runtime/verification signals when Orchestrator state is connected.

Linear memory: `ENG-282`, `ENG-338`.

### Semantic Analytics Execution Layer V1

Это текущая active mission второго слоя.

Она не переоткрывает foundation. Она берет готовый foundation и делает
runtime execution layer:

- approved catalog versions become downstream source of truth;
- Data Intelligence Agent создает review-only proposals;
- impact preview показывает affected questions, registry entries, read models,
  dashboard panels, chat answers, reports and exports before approval;
- manager chat and saved reports execute through approved query specs, policy
  preflight, services and read models;
- verification proves that agents, chat, dashboard, reports and exports do not
  bypass policy or raw SQL constraints.

Linear memory:

- `ENG-330`: mission control;
- `ENG-318`: Data Intelligence proposal ingestion;
- `ENG-319`: impact preview from registry and read models;
- `ENG-320`: approved catalog consumption path;
- `ENG-321`: final verification and production review;
- `ENG-331`: manager question usage evidence;
- `ENG-332`: catalog version expansion and conflict detection;
- `ENG-333`: structured query spec runtime validation;
- `ENG-334`: policy preflight executable gates;
- `ENG-335`: registry and read-model catalog metadata;
- `ENG-336`: manager AI chat runtime;
- `ENG-337`: saved reports runtime;
- `ENG-338`: workbench runtime signals.

### Deferred surfaces

Deferred does not mean abandoned. It means intentionally waiting for stronger
field allowlists, export policy, audit and access rules.

Still deferred:

- row-level worklists;
- row-level export;
- scheduled reports;
- XLSX;
- full LLM planner;
- production agent automation beyond review-only proposals.

## Row-level vs aggregate простыми словами

Aggregate — это сводка:

- 2,584 leads;
- 2,288 paid leads;
- 656 open followups;
- $38,178 collected.

Row-level — это список конкретных людей/записей:

- John Smith, lead source Facebook, consultation scheduled;
- Jane Doe, overdue follow-up;
- конкретный patient/payment/treatment-linked row.

Сейчас для внутренних пользователей row-level conceptually allowed, потому что
мы не моделируем пользователей без доступа. Но V1 read models and exports
остаются aggregate-only. Это снижает риск и упрощает первый production-safe
слой.

## Почему raw SQL запрещен

Raw SQL от LLM, dashboard, chat или agents запрещен.

Причины:

- SQL может обойти policy;
- SQL может случайно достать PHI или raw payload;
- SQL трудно audit-ить как бизнес-операцию;
- SQL ломает ownership между route/service/repository layers;
- SQL дает LLM слишком много власти над данными.

Правильный путь:

```text
UI/chat/agent -> query spec -> policy preflight -> registry -> service -> repository
```

## Почему raw provider payload нельзя показывать как обычный output

Salesforce and CareStack payloads могут содержать лишние, нестабильные или
чувствительные поля.

Они остаются evidence storage. В dashboard/chat/agent output должны попадать
только reviewed fields, normalized facts, semantic terms and service-owned
read models.

## Что это дает бизнесу

Для доктора:

- видеть treatment/payment evidence;
- понимать revenue signals;
- видеть operational bottlenecks;
- видеть follow-up workload.

Для маркетинга:

- понимать paid leads;
- сравнивать sources;
- видеть conversion funnel;
- отделять Facebook/Google/paid/social sources от unknown.

Для операционной команды:

- видеть stale followups;
- видеть consultation flow;
- видеть no-show and completion patterns;
- видеть data quality gaps.

Для будущего AI:

- chat отвечает через approved analytics;
- agent анализирует gaps through tools;
- reports use the same definitions as dashboard;
- metrics do not drift between product surfaces.

## Итог

Да, это один фундамент.

Мы строим его слоями:

```text
facts
-> semantic terms
-> query specs
-> policy
-> services
-> read models
-> dashboard/chatbot/agent
```

Первый практический шаг был правильным: зафиксировать manager questions,
потому что именно они определяют, какие semantic terms, services and read
models нужны первыми.

Сейчас мы уже сделали больше, чем только planning: первые read models
подключены к Project Manager dashboard и отображаются на реальных данных.

## Следующий правильный шаг

Следующий слой уже вынесен в новую mission:
`Semantic Analytics Execution Layer V1`.

Правильный порядок внутри этой mission:

1. `ENG-318`: Data Intelligence proposal ingestion.
2. `ENG-319`: impact preview from registry and read models.
3. `ENG-320`: approved catalog consumption path.
4. `ENG-332`: catalog version expansion and conflict detection.
5. `ENG-335`: registry/read-model catalog metadata.
6. `ENG-333` and `ENG-334`: query validation and policy gates.
7. `ENG-336`: manager AI chat runtime.
8. `ENG-337`: saved reports runtime.
9. `ENG-321`: final production verification.
10. `ENG-338`: keep workbench status and runtime signals aligned.

Главное правило остается тем же: новые поверхности должны использовать общий
semantic analytics foundation, а не создавать свои отдельные определения.
