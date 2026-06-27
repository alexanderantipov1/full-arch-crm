/**
 * full-arch-crm — WikiService
 *
 * The Karpathy-pattern persistent knowledge base. Lives in full-arch-crm (the universal
 * SaaS layer) — NOT in any individual clinic's backend.
 *
 * Architecture position:
 *   Any clinic's DatabaseAdapter → full-arch-crm → WikiService (here)
 *                                                         ↓
 *                                         Anonymized patterns pushed back to
 *                                         all connected clinics via adapter.pushIntelligence()
 *
 * The wiki learns from ALL connected clinics and feeds intelligence back to each.
 * No PHI ever enters the wiki — only aggregated, anonymized patterns.
 *
 * Three operations:
 *   ingest(trigger)  — called after every meaningful event (EOB, visit, simulation cycle)
 *   query(params)    — agents call before making decisions (replaces raw DB lookups)
 *   lint()           — weekly check for orphans, contradictions, stale pages
 *
 * Based on: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
 */

import * as fs from 'fs';
import { askClaude } from '../../services/ai';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_WIKI_ROOT = path.join(__dirname);   // wiki/ lives alongside this file

// ── Types ──────────────────────────────────────────────────────────────────────

export type WikiCategory = 'patients' | 'clinical' | 'insurance' | 'dso' | 'agents' | 'competitors';
export type Confidence = 'low' | 'medium' | 'high';
export type InsuranceType = 'ppo' | 'hmo' | 'medicaid' | 'medicare' | 'self_pay' | 'none';
export type SimScenario =
  | 'implant_consult'
  | 'recall_overdue'
  | 'treatment_decline'
  | 'new_patient'
  | 'emergency'
  | 'financial_barrier'
  | 'dso_referral'
  | 'insurance_issue';

export interface WikiIngestTrigger {
  type: 'simulation_batch' | 'claim_resolved' | 'patient_visit' | 'orchestration_cycle';
  sourceId: string;             // episode ID, claim ID, visit ID, or cycle ID
  cycleNumber?: number;
  episodeIds?: string[];
  claimData?: {
    payerType: InsuranceType;
    cdtCode: string;
    outcome: 'approved' | 'denied' | 'appealed' | 'paid';
    denialReason?: string;
    reimbursement?: number;
    sampleCount?: number;       // aggregated — never single-claim when pushing network
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

export interface WikiQueryParams {
  category: WikiCategory;
  key?: string;       // scenario name, CDT code, payer slug, agent name
  question: string;
  topK?: number;
}

export interface WikiQueryResult {
  answer: string;
  confidence: Confidence;
  sourcePaths: string[];
  pagesRead: number;
}

export interface LintResult {
  orphans: string[];
  contradictions: Array<{ pages: string[]; description: string }>;
  stalePages: string[];
  missingPages: string[];
  actions: string[];
}

interface PageFrontmatter {
  title?: string;
  category?: WikiCategory;
  confidence?: Confidence;
  last_updated?: string;
  source_count?: number;
  cited_by?: string[];
  tags?: string[];
  orphan?: boolean;
  stale?: boolean;
  [key: string]: unknown;
}

interface IndexedPage {
  path: string;
  category: WikiCategory;
  confidence: Confidence;
  lastUpdated: string;
  sourceCount: number;
}

// ── WikiService ────────────────────────────────────────────────────────────────

export class WikiService {
  private wikiRoot: string;

  constructor(wikiRoot?: string) {
    this.wikiRoot = wikiRoot ?? DEFAULT_WIKI_ROOT;
  }

  // ── INGEST ─────────────────────────────────────────────────────────────────

  /**
   * Main ingest entrypoint. Called after every meaningful event.
   * Reads relevant existing pages, synthesizes new intelligence, writes updates.
   * Never writes PHI — all patterns are anonymized before reaching this method.
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

    const targetPaths = this.resolveTargetPages(trigger);

    for (const pagePath of targetPaths) {
      const fullPath = path.join(this.wikiRoot, pagePath);
      const exists = fs.existsSync(fullPath);

      const updated = this.applyIntelligenceUpdate(fullPath, trigger);
      if (updated) {
        if (!exists) result.pagesCreated.push(pagePath);
        else result.pagesUpdated.push(pagePath);
        if (updated.insight) result.keyInsights.push(updated.insight);
      }
    }

    await this.updateIndex(result);

    result.logEntry = this.buildLogEntry(trigger, result);
    await this.appendToLog(result.logEntry);

    result.durationMs = Date.now() - startMs;
    return result;
  }

  /** Determine which wiki pages need updating based on trigger type. */
  private resolveTargetPages(trigger: WikiIngestTrigger): string[] {
    const pages: string[] = [];

    switch (trigger.type) {
      case 'claim_resolved':
        if (trigger.claimData) {
          const { payerType, cdtCode } = trigger.claimData;
          pages.push(`insurance/${payerType}-general.md`);
          pages.push(`clinical/${cdtCode.toLowerCase()}-procedure.md`);
          if (trigger.claimData.outcome === 'denied' || trigger.claimData.outcome === 'appealed') {
            pages.push(`insurance/appeals/${payerType}-${cdtCode}.md`);
          }
          if (trigger.agentName) pages.push(`agents/${trigger.agentName}.md`);
        }
        break;

      case 'patient_visit':
        if (trigger.patientScenario) {
          pages.push(`patients/${trigger.patientScenario.replace(/_/g, '-')}.md`);
        }
        break;

      case 'simulation_batch':
        if (trigger.patientScenario) {
          pages.push(`patients/${trigger.patientScenario.replace(/_/g, '-')}.md`);
        }
        if (trigger.agentName) pages.push(`agents/${trigger.agentName}.md`);
        break;

      case 'orchestration_cycle':
        if (trigger.agentName) pages.push(`agents/${trigger.agentName}.md`);
        pages.push('agents/OrchestrationAgent.md');
        break;
    }

    pages.push('index.md');
    return [...new Set(pages)];
  }

  /** Read an existing page or create a stub, then apply intelligence update. */
  private applyIntelligenceUpdate(
    fullPath: string,
    trigger: WikiIngestTrigger,
  ): { insight: string } | null {
    const dir = path.dirname(fullPath);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });

    let existing = '';
    if (fs.existsSync(fullPath)) {
      existing = fs.readFileSync(fullPath, 'utf-8');
    }

    const update = this.buildPageUpdate(fullPath, existing, trigger);
    if (!update) return null;

    fs.writeFileSync(fullPath, update.content, 'utf-8');
    return { insight: update.insight };
  }

  /** Build the updated page content. Never deletes content — only appends/updates. */
  private buildPageUpdate(
    fullPath: string,
    existing: string,
    trigger: WikiIngestTrigger,
  ): { content: string; insight: string } | null {
    const today = new Date().toISOString().slice(0, 10);
    const timestamp = new Date().toISOString().replace('T', ' ').slice(0, 16) + ' UTC';
    const pageName = path.basename(fullPath, '.md');

    // index.md is handled by updateIndex()
    if (fullPath.endsWith('index.md')) return null;

    if (!existing) {
      // Create stub page
      const category = this.inferCategory(fullPath);
      const frontmatter = this.buildFrontmatter(category, pageName, today, trigger);
      const body = this.buildStubBody(category, pageName, trigger);
      const insight = `Created stub page: ${path.relative(this.wikiRoot, fullPath)}`;
      return { content: `${frontmatter}\n\n${body}`, insight };
    }

    // Append evolution log entry to existing page
    const evolutionEntry = this.buildEvolutionEntry(timestamp, trigger);
    if (!evolutionEntry) return null;

    const updatedFrontmatter = this.updateFrontmatter(existing, today, trigger);
    const content = updatedFrontmatter + '\n\n' + evolutionEntry;
    const insight = this.buildInsightString(trigger);
    return { content, insight };
  }

  private inferCategory(fullPath: string): WikiCategory {
    const rel = path.relative(this.wikiRoot, fullPath);
    if (rel.startsWith('patients/')) return 'patients';
    if (rel.startsWith('clinical/')) return 'clinical';
    if (rel.startsWith('insurance/')) return 'insurance';
    if (rel.startsWith('dso/')) return 'dso';
    if (rel.startsWith('agents/')) return 'agents';
    if (rel.startsWith('competitors/')) return 'competitors';
    return 'clinical';
  }

  private buildFrontmatter(
    category: WikiCategory,
    pageName: string,
    today: string,
    trigger: WikiIngestTrigger,
  ): string {
    return `---
title: "${pageName} — ${category} (stub)"
category: ${category}
confidence: low
last_updated: ${today}
source_events:
  - ${trigger.sourceId}
source_count: 1
cited_by: []
tags: []
---`;
  }

  private buildStubBody(category: WikiCategory, pageName: string, trigger: WikiIngestTrigger): string {
    const cdt = trigger.claimData?.cdtCode ?? '';
    const payer = trigger.claimData?.payerType ?? '';
    return `# ${pageName}

> Auto-generated stub. Confidence: low. Enrich with more source events.

## Summary
_(To be populated as more events are ingested)_

## Source Events
- ${trigger.type}: ${trigger.sourceId}${cdt ? ` — CDT: ${cdt}` : ''}${payer ? ` — Payer: ${payer}` : ''}
`;
  }

  private updateFrontmatter(existing: string, today: string, trigger: WikiIngestTrigger): string {
    // Update last_updated and source_count in-place
    return existing
      .replace(/last_updated: \d{4}-\d{2}-\d{2}/, `last_updated: ${today}`)
      .replace(/source_count: (\d+)/, (_, n) => `source_count: ${parseInt(n) + 1}`);
  }

  private buildEvolutionEntry(timestamp: string, trigger: WikiIngestTrigger): string | null {
    if (trigger.type === 'claim_resolved' && trigger.claimData) {
      const { cdtCode, outcome, denialReason, payerType } = trigger.claimData;
      return `\n## Evolution — ${timestamp}
- **Trigger:** ${trigger.type} — ${trigger.sourceId}
- **CDT:** ${cdtCode} | **Payer:** ${payerType} | **Outcome:** ${outcome}${denialReason ? ` | **Denial reason:** ${denialReason}` : ''}
- _(Aggregated pattern — no PHI)_
`;
    }
    if (trigger.type === 'simulation_batch' && trigger.score !== undefined) {
      return `\n## Evolution — ${timestamp}
- **Trigger:** simulation_batch — ${trigger.sourceId}
- **Score:** ${trigger.score}${trigger.agentName ? ` | **Agent:** ${trigger.agentName}` : ''}
`;
    }
    return null;
  }

  private buildInsightString(trigger: WikiIngestTrigger): string {
    if (trigger.claimData) {
      const { cdtCode, outcome, payerType } = trigger.claimData;
      return `${cdtCode} ${outcome} via ${payerType}`;
    }
    if (trigger.score !== undefined) {
      return `Score update: ${trigger.score}`;
    }
    return trigger.sourceId;
  }

  // ── QUERY ──────────────────────────────────────────────────────────────────

  /**
   * Agent query interface — call before making decisions.
   * Returns synthesized intelligence from relevant wiki pages.
   * Replaces raw DB lookups for intelligence-class decisions.
   *
   * Example:
   *   const intel = await wikiService.query({
   *     category: 'insurance',
   *     key: 'ppo',
   *     question: 'What documentation maximizes D6010 approval for PPO?',
   *   });
   *   // Use intel.answer to guide claim submission
   */
  async query(params: WikiQueryParams): Promise<WikiQueryResult> {
    const { category, key, question, topK = 3 } = params;

    // 1. Find candidate pages in this category
    const candidates = this.findCandidatePages(category, key);

    // 2. Read top-K pages
    const pages = candidates.slice(0, topK).map(p => {
      const fullPath = path.join(this.wikiRoot, p);
      if (!fs.existsSync(fullPath)) return null;
      return { path: p, content: fs.readFileSync(fullPath, 'utf-8') };
    }).filter(Boolean) as Array<{ path: string; content: string }>;

    if (pages.length === 0) {
      return {
        answer: `No wiki pages found for category '${category}'${key ? ` / key '${key}'` : ''}. ` +
          `Ingest more events to build intelligence.`,
        confidence: 'low',
        sourcePaths: [],
        pagesRead: 0,
      };
    }

    // 3. Synthesize answer from page content
    // In production this calls an LLM with the page context.
    // Here we return a structured summary of what was found.
    const answer = await this.synthesizeAnswerAsync(pages, question);
    const confidence = this.lowestConfidence(pages.map(p => p.content));

    // 4. Append query to log
    const timestamp = new Date().toISOString().replace('T', ' ').slice(0, 16) + ' UTC';
    const logEntry = `## [${timestamp}] query | ${category} | ${key ?? 'general'}\n` +
      `- **Question:** ${question}\n` +
      `- **Pages read:** ${pages.map(p => p.path).join(', ')}\n` +
      `- **Confidence:** ${confidence}\n`;
    await this.appendToLog(logEntry);

    return {
      answer,
      confidence,
      sourcePaths: pages.map(p => p.path),
      pagesRead: pages.length,
    };
  }

  private findCandidatePages(category: WikiCategory, key?: string): string[] {
    const dir = path.join(this.wikiRoot, category);
    if (!fs.existsSync(dir)) return [];

    const files = fs.readdirSync(dir)
      .filter(f => f.endsWith('.md') && !f.startsWith('_'))
      .map(f => `${category}/${f}`);

    if (!key) return files;

    // Prioritize pages that match the key (CDT code, payer slug, scenario name, agent name)
    const normalized = key.toLowerCase().replace(/[^a-z0-9]/g, '-');
    const exact = files.filter(f => f.toLowerCase().includes(normalized));
    const rest = files.filter(f => !exact.includes(f));
    return [...exact, ...rest];
  }

  private synthesizeAnswer(pages: Array<{ path: string; content: string }>, question: string): string {
    // Sync fallback — used when caller doesn't await. Real synthesis via synthesizeAnswerAsync().
    const summary = pages.map(p => {
      const lines = p.content.split('\n').slice(0, 20).join('\n');
      return `[${p.path}]:\n${lines}`;
    }).join('\n\n---\n\n');
    return `[Sync summary — ${pages.length} pages]: ${question}\n\n${summary}`;
  }

  /**
   * Full LLM-powered synthesis. Agents should call this via query() which
   * uses askClaude with ops_safe data class (wiki = no PHI).
   */
  async synthesizeAnswerAsync(
    pages: Array<{ path: string; content: string }>,
    question: string,
  ): Promise<string> {
    const context = pages
      .map(p => `## ${p.path}\n${p.content.slice(0, 2000)}`)
      .join('\n\n---\n\n');

    try {
      return await askClaude(
        `You are the Full-Arch CRM knowledge base AI. Answer this question using ONLY the wiki context below.\n\n` +
        `Question: ${question}\n\nWiki context:\n\n${context}\n\n` +
        `Be specific. Cite page names in brackets like [patients/implant-consult.md]. ` +
        `If the wiki doesn't have enough data to answer confidently, say so and suggest what additional data to ingest.`,
        'You are a dental CRM knowledge synthesis AI. All data is anonymized clinical intelligence — no PHI. Respond concisely.',
        600,
        { dataClass: 'ops_safe', purpose: 'wiki_query' },
      );
    } catch {
      return this.synthesizeAnswer(pages, question);
    }
  }

  private lowestConfidence(pageContents: string[]): Confidence {
    const levels: Confidence[] = pageContents.map(content => {
      if (content.includes('confidence: high')) return 'high';
      if (content.includes('confidence: medium')) return 'medium';
      return 'low';
    });
    if (levels.includes('low')) return 'low';
    if (levels.includes('medium')) return 'medium';
    return 'high';
  }

  // ── LINT ───────────────────────────────────────────────────────────────────

  /**
   * Lint pass — weekly, triggered by SelfCheckAgent or GET /api/simulation/wiki/lint.
   * Scans all pages for contradictions, orphans, stale data, missing pages.
   */
  async lint(): Promise<LintResult> {
    const result: LintResult = {
      orphans: [],
      contradictions: [],
      stalePages: [],
      missingPages: [],
      actions: [],
    };

    const nintyDaysAgo = new Date();
    nintyDaysAgo.setDate(nintyDaysAgo.getDate() - 90);
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

    const allPages = this.getAllPages();
    const allPaths = new Set(allPages.map(p => p.path));

    // Collect all cited_by references across pages
    const citedByCount = new Map<string, number>();
    const linkPattern = /\[\[([^\]]+)\]\]/g;

    for (const page of allPages) {
      const fullPath = path.join(this.wikiRoot, page.path);
      const content = fs.readFileSync(fullPath, 'utf-8');

      // Check staleness
      const dateMatch = content.match(/last_updated: (\d{4}-\d{2}-\d{2})/);
      if (dateMatch) {
        const lastUpdated = new Date(dateMatch[1]);
        if (lastUpdated < nintyDaysAgo) {
          result.stalePages.push(page.path);
          result.actions.push(`Flag stale: ${page.path} (last updated: ${dateMatch[1]})`);
        }
      }

      // Collect [[links]] to find orphans and missing pages
      let match;
      while ((match = linkPattern.exec(content)) !== null) {
        const linked = match[1];
        citedByCount.set(linked, (citedByCount.get(linked) ?? 0) + 1);

        // Check for missing pages
        if (!allPaths.has(linked) && !linked.startsWith('agents/') && !linked.startsWith('patients/')) {
          result.missingPages.push(linked);
          result.actions.push(`Create stub: ${linked} (referenced from ${page.path} but missing)`);
        }
      }
    }

    // Orphan check — pages with 0 inbound citations (excluding AGENTS.md, index.md, log.md)
    const skipOrphanCheck = new Set(['AGENTS.md', 'index.md', 'log.md']);
    for (const page of allPages) {
      if (skipOrphanCheck.has(page.path)) continue;
      const count = citedByCount.get(page.path) ?? 0;
      if (count === 0) {
        result.orphans.push(page.path);
        result.actions.push(`Orphan: ${page.path} — no inbound cited_by links`);
      }
    }

    // Contradiction check — same metric with >10% delta across pages
    result.contradictions.push(...this.checkContradictions(allPages));

    // Write lint log entry
    const timestamp = new Date().toISOString().replace('T', ' ').slice(0, 16) + ' UTC';
    const logEntry = `## [${timestamp}] lint | weekly | SelfCheckAgent
- **Pages scanned:** ${allPages.length}
- **Orphan pages found:** ${result.orphans.length}${result.orphans.length > 0 ? ' → ' + result.orphans.join(', ') : ''}
- **Contradiction flags:** ${result.contradictions.length}
- **Stale pages (>90 days):** ${result.stalePages.length}${result.stalePages.length > 0 ? ' → ' + result.stalePages.join(', ') : ''}
- **Missing pages:** ${result.missingPages.length}${result.missingPages.length > 0 ? ' → ' + [...new Set(result.missingPages)].join(', ') : ''}
`;
    await this.appendToLog(logEntry);

    return result;
  }

  private getAllPages(): IndexedPage[] {
    const pages: IndexedPage[] = [];
    const categories: WikiCategory[] = ['patients', 'clinical', 'insurance', 'dso', 'agents', 'competitors'];

    // Root pages
    for (const f of ['AGENTS.md', 'index.md', 'log.md']) {
      const fullPath = path.join(this.wikiRoot, f);
      if (fs.existsSync(fullPath)) {
        pages.push({ path: f, category: 'agents', confidence: 'high', lastUpdated: '', sourceCount: 0 });
      }
    }

    for (const cat of categories) {
      const dir = path.join(this.wikiRoot, cat);
      if (!fs.existsSync(dir)) continue;

      this.readdirRecursive(dir).forEach(f => {
        if (!f.endsWith('.md')) return;
        const rel = path.relative(this.wikiRoot, f);
        const content = fs.readFileSync(f, 'utf-8');
        const conf = content.includes('confidence: high') ? 'high'
          : content.includes('confidence: medium') ? 'medium' : 'low';
        const dateMatch = content.match(/last_updated: (\d{4}-\d{2}-\d{2})/);
        const countMatch = content.match(/source_count: (\d+)/);
        pages.push({
          path: rel,
          category: cat,
          confidence: conf as Confidence,
          lastUpdated: dateMatch?.[1] ?? '',
          sourceCount: parseInt(countMatch?.[1] ?? '0'),
        });
      });
    }

    return pages;
  }

  private readdirRecursive(dir: string): string[] {
    const results: string[] = [];
    if (!fs.existsSync(dir)) return results;
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) results.push(...this.readdirRecursive(fullPath));
      else results.push(fullPath);
    }
    return results;
  }

  private checkContradictions(pages: IndexedPage[]): Array<{ pages: string[]; description: string }> {
    // Scan for approval rate numbers; flag when same CDT/payer appears with >10% delta
    const approvalRates = new Map<string, Array<{ path: string; rate: number }>>();
    const ratePattern = /D(\d{4}).*?(\d{1,3})%.*?approval/gi;

    for (const page of pages) {
      const fullPath = path.join(this.wikiRoot, page.path);
      if (!fs.existsSync(fullPath)) continue;
      const content = fs.readFileSync(fullPath, 'utf-8');
      let match;
      while ((match = ratePattern.exec(content)) !== null) {
        const key = `D${match[1]}`;
        const rate = parseInt(match[2]);
        if (!approvalRates.has(key)) approvalRates.set(key, []);
        approvalRates.get(key)!.push({ path: page.path, rate });
      }
    }

    const contradictions: Array<{ pages: string[]; description: string }> = [];
    for (const [cdt, entries] of approvalRates) {
      if (entries.length < 2) continue;
      const rates = entries.map(e => e.rate);
      const max = Math.max(...rates);
      const min = Math.min(...rates);
      if (max - min > 10) {
        contradictions.push({
          pages: entries.map(e => e.path),
          description: `${cdt} approval rate: ${min}%–${max}% across pages (delta > 10% — reconcile)`,
        });
      }
    }
    return contradictions;
  }

  // ── Log ────────────────────────────────────────────────────────────────────

  private buildLogEntry(trigger: WikiIngestTrigger, result: WikiIngestResult): string {
    const timestamp = new Date().toISOString().replace('T', ' ').slice(0, 16) + ' UTC';
    const typeLabel = trigger.type.replace(/_/g, ' ');
    const lines = [
      `## [${timestamp}] ingest | ${typeLabel} | ${trigger.sourceId}`,
      `- **Trigger:** ${trigger.type}${trigger.cycleNumber !== undefined ? ` — cycle ${trigger.cycleNumber}` : ''}`,
    ];
    if (result.pagesCreated.length > 0) {
      lines.push(`- **Pages created:** ${result.pagesCreated.map(p => `[[${p}]]`).join(', ')}`);
    }
    if (result.pagesUpdated.length > 0) {
      lines.push(`- **Pages updated:** ${result.pagesUpdated.map(p => `[[${p}]]`).join(', ')}`);
    }
    if (result.keyInsights.length > 0) {
      lines.push(`- **Key insights:** ${result.keyInsights.join(' | ')}`);
    }
    lines.push(`- **Duration:** ${result.durationMs}ms`);
    return lines.join('\n') + '\n';
  }

  private async appendToLog(entry: string): Promise<void> {
    const logPath = path.join(this.wikiRoot, 'log.md');
    if (!fs.existsSync(logPath)) {
      fs.writeFileSync(logPath, '# Wiki Log\n\n', 'utf-8');
    }
    fs.appendFileSync(logPath, '\n' + entry, 'utf-8');
  }

  private async updateIndex(result: WikiIngestResult): Promise<void> {
    const indexPath = path.join(this.wikiRoot, 'index.md');
    if (!fs.existsSync(indexPath)) return;

    const content = fs.readFileSync(indexPath, 'utf-8');
    const today = new Date().toISOString().slice(0, 10);
    const updated = content
      .replace(/last_updated: \d{4}-\d{2}-\d{2}/, `last_updated: ${today}`)
      .replace(/\*\*Last ingest:\*\* [^\n]+/, `**Last ingest:** ${today} (${result.pagesCreated.length} created, ${result.pagesUpdated.length} updated)`);
    fs.writeFileSync(indexPath, updated, 'utf-8');
  }
}

// ── Singleton ──────────────────────────────────────────────────────────────────

export const wikiService = new WikiService();
