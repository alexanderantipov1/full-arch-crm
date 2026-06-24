import { randomUUID } from 'crypto';
import { askClaude } from '../services/ai';
import type { ClaimToScrub, ScrubResult, ScrubIssue } from './claim-scrubber-types';

// Rule-based scrub first (fast, no API call)
function ruleBasedScrub(claim: ClaimToScrub): ScrubIssue[] {
  const issues: ScrubIssue[] = [];

  for (const line of claim.lines) {
    // Tooth number required for implant codes
    if (['D6010','D6056','D6058','D6065','D6066'].includes(line.procedureCode) && !line.toothNumber) {
      issues.push({
        code: 'MISSING_TOOTH_NUMBER',
        severity: 'error',
        affectedLine: line.procedureCode,
        message: `${line.procedureCode} requires a tooth number`,
        suggestion: 'Add tooth number (1-32 or letter for primary)',
        autoFixable: false,
      });
    }
    // Surface required for restorative codes
    if (['D2140','D2150','D2160','D2161'].includes(line.procedureCode) && !line.surface) {
      issues.push({
        code: 'MISSING_SURFACE',
        severity: 'error',
        affectedLine: line.procedureCode,
        message: `${line.procedureCode} requires surface designation`,
        suggestion: 'Add surface (M, O, D, B, L, or combination)',
        autoFixable: false,
      });
    }
    // Fee reasonableness check
    if (line.procedureCode === 'D6010' && line.fee < 1000) {
      issues.push({
        code: 'UNUSUALLY_LOW_FEE',
        severity: 'warning',
        affectedLine: line.procedureCode,
        message: `D6010 fee $${line.fee} is below typical California range ($1,800–$3,200)`,
        suggestion: 'Verify fee is correct for your area',
        autoFixable: false,
      });
    }
    // Missing diagnosis code for medical cross-billing
    if (['D6010','D6056'].includes(line.procedureCode) && !line.diagnosisCode) {
      issues.push({
        code: 'MISSING_DIAGNOSIS_CODE',
        severity: 'warning',
        affectedLine: line.procedureCode,
        message: `${line.procedureCode} without ICD-10 may be denied for medical necessity`,
        suggestion: 'Add K08.101 (complete upper) or K08.111 (complete lower) as applicable',
        autoFixable: false,
      });
    }
  }

  // NPI check
  if (!claim.providerNPI || claim.providerNPI.length !== 10) {
    issues.push({
      code: 'INVALID_NPI',
      severity: 'error',
      affectedLine: 'claim',
      message: 'Provider NPI must be exactly 10 digits',
      suggestion: 'Verify NPI at nppes.cms.hhs.gov',
      autoFixable: false,
    });
  }

  return issues;
}

export async function scrubClaim(claim: ClaimToScrub): Promise<ScrubResult> {
  const ruleIssues = ruleBasedScrub(claim);

  // AI scrub for complex issues
  const systemPrompt = `You are a dental insurance claim scrubbing expert. Review this claim for issues that would cause denial.

Check for:
1. Frequency limitations (e.g., D0330 panoramic — typically once per 3-5 years per insurer)
2. Age limitations (e.g., sealants D1351 typically limited to under 14)
3. Missing predetermination for high-value implant claims (usually >$500 requires prior auth)
4. Duplicate procedure on same date/tooth
5. Bundling issues (e.g., D7310 alveoloplasty with extraction)
6. Medical necessity documentation requirements for implants
7. Network status issues (common for out-of-network implant specialists)

Respond ONLY with JSON array of issues (empty array if none):
[{"code":"FREQ_LIMIT","severity":"warning","affectedLine":"D0330","message":"string","suggestion":"string","autoFixable":false}]
severity must be one of: "error", "warning", "info"`;

  let aiIssues: ScrubIssue[] = [];
  try {
    const raw = await askClaude(systemPrompt, JSON.stringify(claim), 1000, { dataClass: 'phi' });
    aiIssues = JSON.parse(raw.replace(/```json\n?|\n?```/g, '').trim());
  } catch { /* use only rule-based if AI fails */ }

  const allIssues = [...ruleIssues, ...aiIssues];
  const errorCount = allIssues.filter(i => i.severity === 'error').length;
  const warningCount = allIssues.filter(i => i.severity === 'warning').length;
  const cleanClaimScore = Math.max(0, 100 - errorCount * 20 - warningCount * 5);
  const estimatedDenialRisk: ScrubResult['estimatedDenialRisk'] =
    errorCount > 0 ? 'high' : warningCount >= 3 ? 'medium' : 'low';

  return {
    claimId: claim.id,
    passedScrub: errorCount === 0,
    issues: allIssues,
    errorCount,
    warningCount,
    estimatedDenialRisk,
    cleanClaimScore,
    readyToSubmit: errorCount === 0,
    scrubbedAt: new Date().toISOString(),
  };
}
