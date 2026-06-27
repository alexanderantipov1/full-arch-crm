# AGENTS.md — Full-Arch CRM Knowledge Wiki Schema

> **Location in repo:** `server/simulation/wiki/AGENTS.md`
>
> This file is the schema and operational contract for the Full-Arch CRM LLM-maintained wiki.
> It is the configuration document that every agent reads before touching any wiki page.
> Modeled on the [Karpathy LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).

---

## Purpose

The wiki is a **persistent, compounding knowledge base** maintained entirely by the simulation agents.
It sits between raw episode data and agent decisions. Instead of re-deriving intelligence from
database queries on every decision, agents:

1. Write compiled knowledge into the wiki after each meaningful event
2. Read the wiki before making decisions (replaces raw DB lookups for intelligence)
3. Periodically lint the wiki for contradictions, stale pages, and orphan nodes

The wiki grows richer with every patient visit, claim resolution, and simulation loop.
No agent writes to it for the sake of writing — every page must earn its existence by being
cited in at least one agent decision within 30 days, or it is flagged as orphan.

---

## Directory Layout

```
server/simulation/wiki/
├── AGENTS.md                  ← this file (schema + operational contract)
├── index.md                   ← catalog of all pages (updated on every ingest)
├── log.md                     ← append-only chronological event log
│
├── patients/                  ← per-profile treatment intelligence
│   ├── _template.md
│   ├── implant-consult.md
│   ├── recall-overdue.md
│   ├── treatment-decline.md
│   ├── new-patient.md
│   ├── emergency.md
│   ├── financial-barrier.md
│   ├── dso-referral.md
│   └── insurance-issue.md
│
├── clinical/                  ← CDT code and procedure intelligence
│   ├── _template.md
│   ├── D6010-implant-body.md
│   ├── D4341-periodontal-scaling.md
│   ├── D2740-ceramic-crown.md
│   └── [cdt-code]-[short-name].md
│
├── insurance/                 ← payer behavior, denial patterns, appeal scripts
│   ├── _template.md
│   ├── ppo-general.md
│   ├── hmo-general.md
│   ├── medicaid-general.md
│   ├── medicare-general.md
│   ├── [payer-slug].md
│   └── appeals/
│       ├── _template.md
│       └── [payer-slug]-[cdt-code].md
│
├── dso/                       ← DSO / multi-location performance intelligence
│   ├── _template.md
│   ├── network-overview.md
│   └── [location-slug].md
│
├── agents/                    ← per-agent self-improvement logs and hypotheses
│   ├── _template.md
│   ├── PatientAcquisition.md
│   ├── RecallAgent.md
│   ├── TreatmentPlanAgent.md
│   ├── InsuranceAgent.md
│   ├── SchedulingAgent.md
│   └── FinancialCounselorAgent.md
│
└── competitors/               ← competitor intelligence
    ├── _template.md
    ├── asha-dental.md
    └── [competitor-slug].md
```

---

## Page Frontmatter Standard

Every wiki page **must** begin with a YAML frontmatter block. Agents use this for indexing,
linting, and Dataview-style queries without reading the full page body.

```yaml
---
title: "D6010 — Implant Body (Endosteal)"
category: clinical           # patients | clinical | insurance | dso | agents | competitors
cdt_code: D6010              # (clinical pages only)
payer: null                  # (insurance pages only)
location_id: null            # (dso pages only)
agent_name: null             # (agents pages only)
confidence: medium           # low | medium | high
last_updated: 2026-06-26
source_events:
  - ep-1719441234-PatientAcquisition-42   # episode IDs that informed this page
  - claim-2026-06-15-BCBS-D6010
source_count: 14             # total events ever used to build this page
cited_by:                    # pages that link here (maintained by lint pass)
  - insurance/ppo-general.md
  - agents/InsuranceAgent.md
tags: [implant, high-value, ppo-favorable]
---
```

---

## Page Format Templates

### `patients/_template.md`

```markdown
---
title: "[Scenario Name] — Patient Profile"
category: patients
confidence: low
last_updated: YYYY-MM-DD
source_count: 0
cited_by: []
tags: []
---

# [Scenario Name]

## Profile Summary
One-paragraph description of the patient archetype. Age range, typical presentation,
entry point into the practice, financial profile.

## Treatment Patterns
What procedures are typically needed. CDT codes. Average treatment value range.

| Procedure    | CDT   | Avg Value | Acceptance Rate |
|--------------|-------|-----------|-----------------|
| [name]       | DXXXX | $X,XXX    | XX%             |

## Conversion Intelligence
What drives acceptance vs. decline for this profile.

- **Converts when:** [conditions]
- **Declines when:** [conditions]
- **Best agent:** [AgentName] — see [[agents/AgentName.md]]
- **Best scenario fit score:** XX/100

## Insurance Patterns
Which payers this profile typically carries. Approval rates by payer.

See: [[insurance/[payer-slug].md]]

## Communication Intelligence
Effective messaging approaches for this profile. Tone, channel, timing.

## Complications & Edge Cases
Known failure modes. What the SelfCheckAgent has flagged for this profile.

## Cross-References
- [[clinical/[cdt-code]-[name].md]]
- [[insurance/[payer-slug].md]]
- [[agents/[AgentName].md]]
```

---

### `clinical/_template.md`

```markdown
---
title: "[CDT Code] — [Procedure Name]"
category: clinical
cdt_code: DXXXX
confidence: low
last_updated: YYYY-MM-DD
source_count: 0
cited_by: []
tags: []
---

# [CDT Code] — [Procedure Name]

## Procedure Summary
Clinical description. What it treats, when it's indicated, typical chair time.

## Success Rate Data

| Insurance Type | Approval Rate | Avg Reimbursement | Common Denial Reason |
|----------------|---------------|-------------------|----------------------|
| PPO            | XX%           | $X,XXX            | [reason]             |
| HMO            | XX%           | $X,XXX            | [reason]             |
| Medicaid       | XX%           | $X,XXX            | [reason]             |
| Medicare       | XX%           | $X,XXX            | [reason]             |
| Self-pay       | N/A           | $X,XXX (list)     | N/A                  |

## Complication Patterns
Known clinical complications observed in simulation outcomes. Frequency.

## Pairing Intelligence
What procedures are commonly treatment-planned alongside this one.
Revenue lift from presenting as a bundle vs. standalone.

| Paired With   | CDT   | Bundle Acceptance Lift |
|---------------|-------|------------------------|
| [name]        | DXXXX | +XX%                   |

## Documentation Requirements
What supporting documentation maximizes approval rates.
What is missing in claims that get denied.

## Evolution Log
Hypotheses that changed how agents present/price/document this procedure.

## Cross-References
- [[patients/[scenario].md]]
- [[insurance/[payer-slug].md]]
```

---

### `insurance/_template.md`

```markdown
---
title: "[Payer Name] — Insurance Intelligence"
category: insurance
payer: [payer-slug]
confidence: low
last_updated: YYYY-MM-DD
source_count: 0
cited_by: []
tags: []
---

# [Payer Name]

## Payer Overview
Plan types offered (PPO/HMO/Medicaid/Medicare). Network characteristics.
Common employer groups or demographics that carry this payer.

## Approval Patterns

### High-Approval Procedures
Procedures where this payer approves at >80% with minimal friction.

| CDT   | Procedure         | Approval Rate | Notes                   |
|-------|-------------------|---------------|-------------------------|
| DXXXX | [name]            | XX%           | [key documentation tip] |

### Low-Approval / High-Denial Procedures
Procedures requiring extra documentation or that are frequently denied.

| CDT   | Procedure   | Denial Rate | Primary Denial Reason | Appeal Success Rate |
|-------|-------------|-------------|----------------------|---------------------|
| DXXXX | [name]      | XX%         | [reason]             | XX%                 |

## Denial Pattern Analysis

### Top 5 Denial Reasons (ranked by frequency)
1. [Reason] — XX% of denials
2. [Reason] — XX% of denials
3. [Reason] — XX% of denials
4. [Reason] — XX% of denials
5. [Reason] — XX% of denials

## Successful Appeal Strategies

For appeal templates see: [[insurance/appeals/[payer-slug]-[cdt-code].md]]

| Denial Reason       | Appeal Strategy                    | Success Rate | Notes                |
|---------------------|------------------------------------|--------------|----------------------|
| [reason]            | [strategy summary]                 | XX%          | [supporting docs]    |

## Pre-Authorization Requirements
Which procedures require pre-auth. Typical turnaround time. Approval rates with vs. without.

## Billing Intelligence
How this payer counts frequencies, processes bundled codes, handles downcoding.
Notes on EOB reading patterns observed from `server/rcm/eob-service.ts`.

## Network Notes
In-network vs. out-of-network reimbursement delta. Whether this payer
participates in fee schedules relevant to the practice.

## Cross-References
- [[clinical/[cdt-code]-[name].md]]
- [[agents/InsuranceAgent.md]]
```

---

### `insurance/appeals/_template.md`

```markdown
---
title: "Appeal Script — [Payer] — [CDT Code]"
category: insurance
payer: [payer-slug]
cdt_code: DXXXX
confidence: low
last_updated: YYYY-MM-DD
source_count: 0
cited_by: []
tags: [appeal]
---

# Appeal Script: [Payer] / [CDT Code] — [Procedure Name]

## Denial Context
Typical denial reason this script addresses. Frequency. Financial impact.

## Required Supporting Documentation
- [ ] [Document 1]
- [ ] [Document 2]
- [ ] [Clinical notes requirement]

## Letter Template

```
[Date]

Re: Appeal for Denied Claim — Patient ID: [PATIENT_ID]
    Procedure: [CDT Code] — [Procedure Name]
    Claim #: [CLAIM_NUMBER]
    Date of Service: [DOS]

Dear [Payer Name] Appeals Department,

We are writing to appeal the denial of the above-referenced claim.

**Medical Necessity Justification:**
[Insert clinical justification — reference ADA guidelines, clinical findings]

**Documentation Enclosed:**
1. [Document list]

**Requested Resolution:**
Reversal of denial and processing for payment at [in-network/out-of-network] rate.

Sincerely,
[Provider Name, NPI]
```

## Success Rate History
| Date       | Outcome  | Notes                          |
|------------|----------|--------------------------------|
| YYYY-MM-DD | Approved | [what made this one succeed]   |
| YYYY-MM-DD | Denied   | [why it failed]                |

## Evolution Notes
Improvements the InsuranceAgent has made to this template based on outcomes.
```

---

### `dso/_template.md`

```markdown
---
title: "[Location Name] — DSO Performance"
category: dso
location_id: [location-uuid]
confidence: low
last_updated: YYYY-MM-DD
source_count: 0
cited_by: []
tags: []
---

# [Location Name]

## Location Overview
Address, provider count, specialty mix, patient volume tier.

## Performance Scorecard

| Metric                       | This Location | Network Avg | Trend     |
|------------------------------|---------------|-------------|-----------|
| Avg simulation score         | XX/100        | XX/100      | ↑/↓/→     |
| Conversion rate              | XX%           | XX%         | ↑/↓/→     |
| Avg revenue per episode      | $X,XXX        | $X,XXX      | ↑/↓/→     |
| Insurance approval rate      | XX%           | XX%         | ↑/↓/→     |
| Recall success rate          | XX%           | XX%         | ↑/↓/→     |
| Treatment plan acceptance    | XX%           | XX%         | ↑/↓/→     |

## Strengths
What this location does measurably better than the network average. Specific agents or
scenarios where it outperforms.

## Gaps
Where this location underperforms. Hypotheses the agents are testing to close gaps.

## Best Practices to Export
Intelligence from this location that should be propagated to other locations.
Links to the specific wiki pages that encode this intelligence.

## Active Hypotheses
Hypotheses from `server/simulation/agents/` currently being tested at this location.

## Cross-References
- [[dso/network-overview.md]]
- [[agents/[AgentName].md]]
```

---

### `agents/_template.md`

```markdown
---
title: "[AgentName] — Self-Improvement Log"
category: agents
agent_name: [AgentName]
confidence: medium
last_updated: YYYY-MM-DD
source_count: 0
cited_by: []
tags: []
---

# [AgentName]

## Agent Description
What this agent does. Which scenarios it handles. How it scores patients.

## Performance History

| Run Date   | Avg Score | Success Rate | Dominant Scenario | Key Learning                     |
|------------|-----------|--------------|-------------------|----------------------------------|
| YYYY-MM-DD | XX/100    | XX%          | [scenario]        | [one-line insight]               |

## Scenario Affinity Map
Current affinity values per scenario (reflects last approved evolution).

| Scenario              | Affinity Score | Confidence |
|-----------------------|----------------|------------|
| implant_consult       | XX/40          | high       |
| recall_overdue        | XX/40          | medium     |
| treatment_decline     | XX/40          | low        |
| new_patient           | XX/40          | high       |
| emergency             | XX/40          | medium     |
| financial_barrier     | XX/40          | low        |
| dso_referral          | XX/40          | high       |
| insurance_issue       | XX/40          | medium     |

## Hypothesis Log
All hypotheses proposed by or for this agent. Status. What was learned.

| Hypothesis ID | Title                    | Status    | Impact (ΔScore) | Implemented |
|---------------|--------------------------|-----------|-----------------|-------------|
| hyp-001       | [hypothesis title]       | approved  | +X.X            | YYYY-MM-DD  |
| hyp-002       | [hypothesis title]       | rejected  | -X.X            | —           |
| hyp-003       | [hypothesis title]       | testing   | TBD             | —           |

## SelfCheck Interventions
What the SelfCheckAgent has flagged for this agent. Corrective actions taken.

## A/B Test Results
Results from `server/simulation/ab-testing.ts` for this agent.

| Test Name          | Variant B Description | Winner | Improvement |
|--------------------|-----------------------|--------|-------------|
| [test name]        | [description]         | B      | +X.X pts    |

## Cross-References
- [[patients/[relevant-scenario].md]]
- [[clinical/[cdt-code]-[name].md]]
```

---

### `competitors/_template.md`

```markdown
---
title: "[Competitor Name] — Competitive Intelligence"
category: competitors
confidence: low
last_updated: YYYY-MM-DD
source_count: 0
cited_by: []
tags: []
---

# [Competitor Name]

## Overview
Type of competitor (DSO chain / single-location practice / SaaS CRM / digital-first brand).
Geographic footprint. Approximate patient volume. Estimated revenue tier.

## Feature Comparison

| Capability                        | Full-Arch CRM     | [Competitor]      | Gap Direction |
|-----------------------------------|-------------------|-------------------|---------------|
| AI Scribe                         | ✓ (live)          | [status]          | [our lead]    |
| Insurance calling automation      | ✓ (live)          | [status]          | [our lead]    |
| EOB posting automation            | ✓ (live)          | [status]          | [our lead]    |
| Self-improving simulation         | ✓ (live)          | ✗ (not present)   | our lead      |
| Treatment plan acceptance AI      | ✓ (live)          | [status]          | —             |
| Multi-clinic DSO dashboard        | ✓ (live)          | [status]          | —             |
| Wiki-driven learning              | ✓ (live)          | ✗ (not present)   | our lead      |
| [other feature]                   | [status]          | [status]          | —             |

## Pricing Intelligence
What is publicly known about their pricing. Per-seat, per-location, or % of collections.

## Patient Experience Gaps
What their patients complain about (review mining, forums).
Where patients say they prefer us.

## Sales Intelligence
Objections they raise when practices consider switching to us.
Win/loss patterns observed.

## Strategic Assessment
Threat level: low / medium / high.
Time horizon for them to close key capability gaps.
Recommended response: ignore / monitor / counter / accelerate.

## Cross-References
- [[dso/network-overview.md]]
```

---

## `index.md` — Wiki Catalog

This file is the entry point for all agent queries. Updated on every ingest operation.
Agents read this first, then drill into specific pages.

```markdown
---
title: "Full-Arch CRM Knowledge Wiki — Index"
last_updated: YYYY-MM-DD
total_pages: 0
total_source_events: 0
---

# Full-Arch CRM Knowledge Wiki

## Quick Stats
- **Total pages:** N
- **Last ingest:** YYYY-MM-DD HH:MM UTC
- **Highest-confidence category:** [category]
- **Stalest page:** [[path/to/page.md]] (last updated YYYY-MM-DD)

## Patient Intelligence
| Page                                          | Confidence | Last Updated | Source Count |
|-----------------------------------------------|------------|--------------|--------------|
| [[patients/implant-consult.md]]               | high       | YYYY-MM-DD   | N            |
| [[patients/recall-overdue.md]]                | medium     | YYYY-MM-DD   | N            |
| [[patients/treatment-decline.md]]             | medium     | YYYY-MM-DD   | N            |
| [[patients/new-patient.md]]                   | low        | YYYY-MM-DD   | N            |
| [[patients/emergency.md]]                     | low        | YYYY-MM-DD   | N            |
| [[patients/financial-barrier.md]]             | medium     | YYYY-MM-DD   | N            |
| [[patients/dso-referral.md]]                  | low        | YYYY-MM-DD   | N            |
| [[patients/insurance-issue.md]]               | medium     | YYYY-MM-DD   | N            |

## Clinical Intelligence
| Page                                          | CDT   | Confidence | Source Count |
|-----------------------------------------------|-------|------------|--------------|
| [[clinical/D6010-implant-body.md]]            | D6010 | high       | N            |
| [[clinical/D4341-periodontal-scaling.md]]     | D4341 | medium     | N            |
| ...                                           |       |            |              |

## Insurance Intelligence
| Page                                          | Payer Type | Confidence | Source Count |
|-----------------------------------------------|------------|------------|--------------|
| [[insurance/ppo-general.md]]                  | PPO        | high       | N            |
| [[insurance/hmo-general.md]]                  | HMO        | medium     | N            |
| [[insurance/medicaid-general.md]]             | Medicaid   | medium     | N            |
| [[insurance/medicare-general.md]]             | Medicare   | low        | N            |

## DSO Intelligence
| Page                                          | Confidence | Last Updated |
|-----------------------------------------------|------------|--------------|
| [[dso/network-overview.md]]                   | medium     | YYYY-MM-DD   |
| [[dso/[location-slug].md]]                    | low        | YYYY-MM-DD   |

## Agent Self-Improvement Logs
| Page                                          | Avg Score | Last Updated |
|-----------------------------------------------|-----------|--------------|
| [[agents/PatientAcquisition.md]]              | XX/100    | YYYY-MM-DD   |
| [[agents/InsuranceAgent.md]]                  | XX/100    | YYYY-MM-DD   |
| ...                                           |           |              |

## Competitor Intelligence
| Page                                          | Threat Level | Last Updated |
|-----------------------------------------------|--------------|--------------|
| [[competitors/asha-dental.md]]                | high         | YYYY-MM-DD   |

## Lint Status
- Last lint: YYYY-MM-DD HH:MM UTC
- Orphan pages: N (see log.md for details)
- Contradiction flags: N
- Stale pages (>90 days): N
```

---

## `log.md` — Append-Only Event Log

Every ingest, query result, and lint pass appends a structured entry. Each entry starts
with a parseable prefix so agents can grep efficiently:

```bash
grep "^## \[" server/simulation/wiki/log.md | tail -10
grep "^## \[.*\] lint" server/simulation/wiki/log.md
grep "^## \[.*\] ingest | insurance" server/simulation/wiki/log.md
```

### Log Entry Format

```markdown
## [YYYY-MM-DD HH:MM UTC] ingest | PatientVisit | ep-1719441234-InsuranceAgent-42
- **Trigger:** SimulationEngine.runBatch() completed — cycle 47
- **Pages updated:**
  - [[patients/implant-consult.md]] — added D6010 success pattern, confidence now high
  - [[insurance/ppo-general.md]] — updated D6010 approval rate from 78% → 82% (n=14)
  - [[clinical/D6010-implant-body.md]] — added documentation tip from approved claim
  - [[agents/InsuranceAgent.md]] — logged score 88/100, best for implant_consult scenario
  - [[index.md]] — updated source counts
- **Key insight extracted:** PPO approves D6010 at higher rate when full-mouth X-ray series included

## [YYYY-MM-DD HH:MM UTC] ingest | ClaimResolution | claim-BCBS-2026-06-26-D4341
- **Trigger:** EOB processing (server/rcm/eob-service.ts) — claim resolved
- **Outcome:** Denied — reason: frequency limitation
- **Pages updated:**
  - [[insurance/ppo-general.md]] — added frequency limitation note for D4341
  - [[insurance/appeals/ppo-general-D4341.md]] — created new appeal template (first instance)
  - [[clinical/D4341-periodontal-scaling.md]] — updated denial rate for PPO
  - [[index.md]] — added appeals/ppo-general-D4341.md to catalog

## [YYYY-MM-DD HH:MM UTC] ingest | SimulationLoop | cycle-47
- **Trigger:** OrchestrationAgent.runCycle() completed
- **Hypotheses tested:** 2
- **Hypotheses approved:** 1 (hyp-034: "Increase affinity for implant_consult in InsuranceAgent by 8 pts")
- **Score delta:** +1.4 pts (baseline 81.2 → new 82.6)
- **Pages updated:**
  - [[agents/InsuranceAgent.md]] — logged hypothesis hyp-034 approval and score delta
  - [[agents/OrchestrationAgent.md]] — logged cycle 47 metadata

## [YYYY-MM-DD HH:MM UTC] query | InsuranceAgent | insurance/ppo-general.md
- **Query:** "What documentation maximizes D6010 approval for PPO payers?"
- **Pages read:** [[insurance/ppo-general.md]], [[clinical/D6010-implant-body.md]]
- **Answer filed to:** (ephemeral — not filed; see note below)
- **Latency:** 12ms

## [YYYY-MM-DD HH:MM UTC] lint | weekly | SelfCheckAgent
- **Pages scanned:** 34
- **Orphan pages found:** 2 → [[insurance/appeals/hmo-D0220.md]], [[clinical/D9999-misc.md]]
  - Action: flagged in frontmatter as `orphan: true` — will be deleted next lint if still orphan
- **Contradiction flags:** 1
  - [[insurance/ppo-general.md]] claims D6010 approval rate 82%
  - [[clinical/D6010-implant-body.md]] claims D6010 PPO approval rate 79%
  - Resolution needed: ReconcileAgent should re-count from episodes (source_count: 14 vs 11)
- **Stale pages (>90 days):** 3 → flagged in frontmatter
- **Missing pages:** 1 → D2740 is referenced in [[patients/implant-consult.md]] but has no page
  - Action: created stub [[clinical/D2740-ceramic-crown.md]] with confidence: low
```

---

## Operations

### 1. INGEST — How Agents Write to the Wiki

The ingest operation is the core of the wiki's value. It is **always triggered** by:
- `SimulationEngine.runBatch()` completing (after every simulation loop)
- `server/rcm/eob-service.ts` resolving a claim (after every EOB post)
- A patient visit completing via `server/booking/booking-service.ts`
- `OrchestrationAgent.runCycle()` completing (after every orchestration cycle)

#### TypeScript Interface

```typescript
// server/simulation/wiki/wiki-service.ts

export interface WikiIngestTrigger {
  type: 'simulation_batch' | 'claim_resolved' | 'patient_visit' | 'orchestration_cycle';
  sourceId: string;            // episode ID, claim ID, visit ID, or cycle ID
  cycleNumber?: number;
  episodeIds?: string[];
  claimData?: {
    payerType: SimInsuranceType;
    cdtCode: string;
    outcome: 'approved' | 'denied' | 'appealed' | 'paid';
    denialReason?: string;
    reimbursement?: number;
  };
  patientScenario?: SimScenario;
  agentName?: string;
  score?: number;
}

export interface WikiIngestResult {
  pagesCreated: string[];
  pagesUpdated: string[];
  keyInsights: string[];
  logEntry: string;
  durationMs: number;
}

export class WikiService {
  private wikiRoot: string;

  constructor(wikiRoot = path.join(import.meta.dirname, 'wiki')) {
    this.wikiRoot = wikiRoot;
  }

  /**
   * Main ingest entrypoint. Called after every meaningful event.
   * Reads relevant existing pages, synthesizes new intelligence, writes updates.
   */
  async ingest(trigger: WikiIngestTrigger): Promise<WikiIngestResult> {
    const startMs = Date.now();
    const result: WikiIngestResult = {
      pagesCreated: [],
      pagesUpdated: [],
      keyInsights: [],
      logEntry: '',
      durationMs: 0,
    };

    // 1. Determine which pages need updating based on trigger type
    const targetPages = this.resolveTargetPages(trigger);

    // 2. For each target page: read current content, apply intelligence update
    for (const pagePath of targetPages) {
      const updated = await this.updatePage(pagePath, trigger);
      if (updated.created) result.pagesCreated.push(pagePath);
      else result.pagesUpdated.push(pagePath);
      if (updated.insight) result.keyInsights.push(updated.insight);
    }

    // 3. Update index.md
    await this.updateIndex();

    // 4. Append to log.md
    result.logEntry = this.buildLogEntry(trigger, result);
    await this.appendToLog(result.logEntry);

    result.durationMs = Date.now() - startMs;
    return result;
  }

  /**
   * Query interface: agents call this before making decisions.
   * Returns synthesized intelligence from relevant wiki pages.
   * This replaces raw DB lookups for intelligence-class decisions.
   */
  async query(params: {
    category: 'patients' | 'clinical' | 'insurance' | 'dso' | 'agents' | 'competitors';
    key?: string;       // scenario name, CDT code, payer slug, agent name
    question: string;   // natural language question
    topK?: number;      // max pages to read (default 3)
  }): Promise<{
    answer: string;
    confidence: 'low' | 'medium' | 'high';
    sourcePaths: string[];
    pagesRead: number;
  }> {
    // 1. Read index.md to find candidate pages
    const index = await this.readIndex();

    // 2. Filter to relevant pages by category + key
    const candidates = this.filterIndex(index, params.category, params.key);

    // 3. Read top-K pages
    const pages = await Promise.all(
      candidates.slice(0, params.topK ?? 3).map(p => this.readPage(p.path))
    );

    // 4. Synthesize answer using askClaude with dataClass: 'ops_safe'
    // (wiki content is synthetic intelligence, never real PHI)
    const context = pages.map(p => `## ${p.path}\n${p.content}`).join('\n\n---\n\n');
    const answer = await askClaude(
      `Given this wiki context:\n\n${context}\n\nAnswer this question: ${params.question}`,
      { dataClass: 'ops_safe', maxTokens: 500 }
    );

    // 5. Append query entry to log.md (ephemeral queries not filed back)
    await this.appendToLog(
      `## [${new Date().toISOString()}] query | ${params.category} | ${params.key ?? 'general'}\n` +
      `- **Question:** ${params.question}\n- **Pages read:** ${candidates.slice(0, params.topK ?? 3).map(p => p.path).join(', ')}\n`
    );

    return {
      answer,
      confidence: this.lowestConfidence(pages),
      sourcePaths: candidates.slice(0, params.topK ?? 3).map(p => p.path),
      pagesRead: pages.length,
    };
  }

  /**
   * Lint pass: weekly, triggered by SelfCheckAgent.
   * Scans all pages for contradictions, orphans, stale data, missing pages.
   */
  async lint(): Promise<{
    orphans: string[];
    contradictions: Array<{ pages: string[]; description: string }>;
    stalePages: string[];
    missingPages: string[];
    actions: string[];
  }> {
    // Implementation: read all pages, check frontmatter, cross-reference cited_by links
    // Flag orphans (no inbound cited_by links for >30 days)
    // Flag contradictions (same metric with significantly different values across pages)
    // Flag stale pages (last_updated > 90 days)
    // Flag missing pages (pages referenced via [[link]] but not existing)
    // Write lint log entry
    // ...
  }
}

export const wikiService = new WikiService();
```

---

### 2. QUERY — How Agents Use the Wiki

Agents query the wiki at **decision time** rather than querying raw database state.
The wiki is pre-compiled intelligence; it is always faster and richer than a raw query.

#### Integration Points

**`OrchestrationAgent.runCycle()`** — before deciding `nextAction`:
```typescript
// server/simulation/orchestrator.ts (addition)
const insuranceIntelligence = await wikiService.query({
  category: 'insurance',
  question: 'Which insurance types have the lowest approval rates right now?',
});
const patternIntelligence = await wikiService.query({
  category: 'patients',
  question: 'Which patient scenarios convert best with high treatment values?',
});
// Use insuranceIntelligence.answer and patternIntelligence.answer
// to inform the nextAction decision and hypothesis generation
```

**`InsuranceAgent` (via agents.ts)** — before scoring a patient:
```typescript
// In BaseAgent.process() or a specialized InsuranceAgent
if (patient.insuranceType !== 'none') {
  const payerIntel = await wikiService.query({
    category: 'insurance',
    key: patient.insuranceType,
    question: `What are the best approval strategies for ${patient.insuranceType} patients with scenario ${patient.scenario}?`,
    topK: 2,
  });
  // Inject payerIntel.answer into the scoring/action logic
}
```

**`SelfCheckAgent.analyze()`** — before generating interventions:
```typescript
// server/simulation/self-check.ts (addition)
const agentIntel = await wikiService.query({
  category: 'agents',
  key: weakestAgent.agentName,
  question: 'What hypotheses have already been tested and failed for this agent?',
});
// Avoid re-proposing rejected hypotheses
```

**`server/tools/letters/appeal.ts`** — before writing appeal letters:
```typescript
const appealTemplate = await wikiService.query({
  category: 'insurance',
  key: `appeals/${payerSlug}-${cdtCode}`,
  question: `What is the most successful appeal strategy for ${payerSlug} denying ${cdtCode}?`,
});
// Use appealTemplate.answer as the letter foundation
```

---

### 3. LINT — How SelfCheckAgent Maintains the Wiki

The lint pass runs **weekly** (cron: every Sunday at 2am UTC) and on-demand via
`GET /api/simulation/wiki/lint`.

```typescript
// server/simulation/routes.ts (addition)
simulationRouter.post('/api/simulation/wiki/lint', async (_req, res) => {
  const lintResult = await wikiService.lint();
  res.json(lintResult);
});

simulationRouter.get('/api/simulation/wiki/query', async (req, res) => {
  const { category, key, question } = req.query as Record<string, string>;
  const result = await wikiService.query({ category: category as any, key, question });
  res.json(result);
});
```

#### Lint Rules (enforced by `wikiService.lint()`)

| Rule                 | Check                                                         | Action                                        |
|----------------------|---------------------------------------------------------------|-----------------------------------------------|
| **Orphan**           | Page has no inbound `cited_by` links for >30 days            | Set `orphan: true` in frontmatter; delete on next lint if still orphan |
| **Contradiction**    | Same metric appears with >10% delta across 2 pages           | Flag both pages; add contradiction note; queue for ReconcileAgent |
| **Stale**            | `last_updated` > 90 days                                      | Set `stale: true` in frontmatter; log for re-ingest |
| **Missing page**     | `[[link]]` in body refers to non-existent page               | Create stub page with `confidence: low`       |
| **Missing frontmatter** | Page body exists but YAML block is absent or malformed    | Re-add frontmatter from template defaults     |
| **Source-count drift** | `source_count` in frontmatter != actual citation count in log | Recount from log.md and correct              |
| **Dead CDT reference** | CDT code in clinical page not recognized by ADA code set   | Flag for human review                         |

---

## Trigger Map — When Each Wiki Section Gets Updated

| Trigger Event                          | Pages Updated                                                    |
|----------------------------------------|------------------------------------------------------------------|
| `SimulationEngine.runBatch()` complete | `patients/[scenario].md`, `agents/[AgentName].md`, `index.md`   |
| EOB claim → **approved**               | `insurance/[payer].md`, `clinical/[cdt].md`, `agents/InsuranceAgent.md` |
| EOB claim → **denied**                 | `insurance/[payer].md`, `clinical/[cdt].md`, `insurance/appeals/[payer]-[cdt].md` |
| EOB claim → **appeal won**             | `insurance/appeals/[payer]-[cdt].md`, `insurance/[payer].md`    |
| Patient visit completed                | `patients/[scenario].md`, `clinical/[cdt codes used].md`        |
| `OrchestrationAgent.runCycle()` done   | `agents/[AgentName].md`, `agents/OrchestrationAgent.md`         |
| Hypothesis approved                    | `agents/[AgentName].md` (score delta logged)                    |
| Hypothesis rejected                    | `agents/[AgentName].md` (rejection + rationale logged)          |
| A/B test complete                      | `agents/[AgentName].md`, `patients/[scenario].md`               |
| Insurance call completed               | `insurance/[payer].md` (call outcome, pre-auth status)          |
| Weekly cron (Sunday 2am UTC)           | Lint pass → all pages                                           |

---

## Confidence Scoring

Wiki pages carry a `confidence` field in frontmatter. Agents should weight results
from `high`-confidence pages more heavily than `low`-confidence pages when making decisions.

| Level    | Minimum `source_count` | Description                                             |
|----------|------------------------|---------------------------------------------------------|
| `low`    | 1–3                    | Early observations. Do not rely on alone.               |
| `medium` | 4–9                    | Emerging pattern. Valid for directional guidance.       |
| `high`   | 10+                    | Validated pattern. Reliable for decision-making.        |

The `WikiService.query()` method returns `confidence` as the lowest confidence level
among all pages it read to answer the question.

---

## Agent Writing Protocol

When an agent writes to the wiki, it must follow these rules:

1. **Never delete existing content** — only append or update. Use strikethrough (`~~old value~~`) for superseded claims, then write the updated value. This preserves the audit trail.
2. **Always update `last_updated` and `source_count`** in frontmatter.
3. **Always append the source event ID** to `source_events` in frontmatter (cap at 20 most recent).
4. **Never write real PHI** — the wiki contains synthetic intelligence. Real patient names, DOBs, or claim numbers must never appear. Use anonymized identifiers only.
5. **Cross-reference liberally** — every new insight should be linked from the relevant patient, clinical, and insurance pages.
6. **Write for the next agent, not the current one** — the value of a wiki page is that a future agent can read it cold and immediately make a better decision than if it had to re-derive the pattern from raw data.
7. **Cite the score delta** for any hypothesis that modified agent behavior. The wiki is the ledger of what improved the simulation score and why.

---

## Bootstrap Procedure

On first install, the wiki directory is empty. The bootstrap procedure:

```bash
# Run from repo root
ts-node server/simulation/wiki/bootstrap.ts
```

This creates:
- All template directories
- `AGENTS.md` (this file)
- `index.md` with zero pages
- `log.md` with a single bootstrap entry
- Stub pages for all 8 patient scenarios at `confidence: low`
- Stub pages for the 6 agents at `confidence: low`

After bootstrap, run one simulation batch to trigger the first ingest pass:
```bash
curl -X POST http://localhost:5000/api/simulation/run
```

The first ingest will populate patient and agent pages from episode data.
Clinical and insurance pages populate as EOB data flows in from `server/rcm/eob-service.ts`.
