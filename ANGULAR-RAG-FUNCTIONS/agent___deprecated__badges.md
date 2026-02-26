# _deprecated / badges

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `src` |
| **Role** | Source |
| **Bundle** | `agent___deprecated__badges` |
| **Files** | 1 |
| **Total size** | 9,667 bytes |
| **Generated** | 2026-02-26 14:05 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `agent/_deprecated/badges.ts` (9,667 bytes, Source)

---

## `agent/_deprecated/badges.ts`

| Field | Value |
|-------|-------|
| **Role** | Source |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-18 |
| **Size** | 9,667 bytes |
| **Exports** | `BadgeResult`, `determineBadge`, `applyGroundingFusion`, `GROUNDING_THRESHOLDS` |

```typescript
/**
 * V4.4 Badge Rules — Grounding Level Determination
 * Ported from robsky-ai-vertex to robsky-angular
 * 
 * Determines GREEN/YELLOW/RED badge based on:
 *   - Intent classification
 *   - Evidence count
 *   - Verification confidence
 * 
 * Badge Fusion (V5.3): Post-processing layer that can DOWNGRADE
 * badges based on Check Grounding API supportScore.
 */

import { type QueryIntent } from './classifier';

export interface BadgeResult {
    level: 'GREEN' | 'YELLOW' | 'RED';
    confidence: number;
    message: string;
}

// Intents where LLM performs generative operations — NEVER GREEN
const ALWAYS_YELLOW: QueryIntent[] = [
    'COMPUTATION', 'STRATEGIC', 'PEDAGOGICAL', 'ANALYTICAL'
];

// Intent where output is speculative — ALWAYS RED with disclaimer
const ALWAYS_RED: QueryIntent[] = ['PREDICTIVE'];

// Intents where GREEN requires 2+ corroborating sources
const CONDITIONAL_GREEN_2: QueryIntent[] = [
    'INSTRUCTIONAL', 'COMPARATIVE', 'TEMPORAL', 'COMPLIANCE'
];

// Intents where GREEN requires only 1+ source (targeted retrieval)
const GREEN_ON_ANY: QueryIntent[] = [
    'LOOKUP', 'DRAFTING', 'SUMMARIZATION'
];

// Intent-specific audit messages
const INTENT_MESSAGES: Partial<Record<QueryIntent, (evidenceCount: number) => string>> = {
    'LOOKUP': (n) => `V4.4 Verified: ${n} sources (targeted case/statute retrieval)`,
    'RESEARCH': (n) => `V4.4 Agentic: ${n} sources via multi-turn investigation`,
    'DRAFTING': (n) => `V4.4 RAT: ${n} sources (form template + governing law)`,
    'COMPUTATION': (n) => `V4.4 System-Calculated: ${n} sources. Code execution verified. User should verify inputs.`,
    'INSTRUCTIONAL': (n) => `V4.4 Guide: ${n} sources (procedural steps from cited rules)`,
    'STRATEGIC': (n) => `V4.4 AI-Assessment: ${n} sources. Risk analysis from cited authority. Professional judgment advised.`,
    'COMPARATIVE': (n) => `V4.4 Matrix: ${n} sources (comparison built from cited attributes)`,
    'PEDAGOGICAL': (n) => `V4.4 Illustrative: ${n} sources. Examples/quizzes from cited rules. Not real-world cases.`,
    'PREDICTIVE': (n) => `⚠️ PREDICTIVE: ${n} sources. This is speculative analysis, NOT legal advice. Outcomes depend on jurisdiction, judge, and facts.`,
    'ANALYTICAL': (n) => `V4.4 Analytics: ${n} sources. Statistical trends from corpus data. Verify underlying methodology.`,
    'VERIFICATION': (n) => `V4.4 Fact-Check: ${n} sources. Cross-referenced against legal corpus.`,
    'COMPLIANCE': (n) => `V4.4 Compliance: ${n} sources. Deadlines and requirements from regulatory authority.`,
    'SUMMARIZATION': (n) => `V4.4 Summary: ${n} sources. Key points extracted from cited documents.`,
    'TEMPORAL': (n) => `V4.4 Timeline: ${n} sources. Chronological analysis from cited materials.`,
};

/**
 * Determine the grounding badge for an agent response.
 * 
 * @param intent - The classified query intent (or 'FAILED_SEARCH')
 * @param evidenceCount - Number of evidence items in the response
 * @param verificationConfidence - Optional confidence score for VERIFICATION intent
 * @param hasCodeExecution - Whether the Paralegal used code execution
 * @returns BadgeResult with level, confidence, and audit message
 */
export function determineBadge(
    intent: QueryIntent | 'FAILED_SEARCH',
    evidenceCount: number,
    verificationConfidence?: number,
    hasCodeExecution?: boolean
): BadgeResult {
    const hasEvidence = evidenceCount > 0;

    // FAILED_SEARCH
    if (intent === 'FAILED_SEARCH') {
        return { level: 'RED', confidence: 0.1, message: 'Pipeline failure — no results' };
    }

    // ALWAYS RED (Predictive)
    if (ALWAYS_RED.includes(intent as QueryIntent)) {
        return {
            level: 'RED',
            confidence: 0.3,
            message: INTENT_MESSAGES[intent as QueryIntent]?.(evidenceCount) || 'Speculative analysis',
        };
    }

    // No evidence
    if (!hasEvidence) {
        if (intent === 'CONVERSATIONAL') {
            return { level: 'YELLOW', confidence: 0.7, message: 'Conversational follow-up — based on prior discussion' };
        }
        return { level: 'RED', confidence: 0.3, message: 'No evidence found in legal database' };
    }

    // ALWAYS YELLOW (LLM generative) — EXCEPT code-verified computation
    if (ALWAYS_YELLOW.includes(intent as QueryIntent)) {
        if (intent === 'COMPUTATION' && hasCodeExecution && evidenceCount > 0) {
            return {
                level: 'GREEN',
                confidence: 0.95,
                message: `V5.2 Code-Verified: ${evidenceCount} sources. Computation verified by Python interpreter.`,
            };
        }

        return {
            level: 'YELLOW',
            confidence: 0.75,
            message: INTENT_MESSAGES[intent as QueryIntent]?.(evidenceCount) || `V4.4: ${evidenceCount} sources (AI-generated output)`,
        };
    }

    // VERIFICATION: Special tiered logic
    if (intent === 'VERIFICATION') {
        const conf = verificationConfidence ?? 0.7;
        if (conf >= 0.9 && evidenceCount >= 2) {
            return { level: 'GREEN', confidence: conf, message: INTENT_MESSAGES[intent]?.(evidenceCount) || '' };
        }
        if (conf >= 0.7) {
            return { level: 'YELLOW', confidence: conf, message: INTENT_MESSAGES[intent]?.(evidenceCount) || '' };
        }
        return { level: 'RED', confidence: conf, message: INTENT_MESSAGES[intent]?.(evidenceCount) || '' };
    }

    // GREEN on any evidence (targeted retrieval)
    if (GREEN_ON_ANY.includes(intent as QueryIntent)) {
        return {
            level: 'GREEN',
            confidence: 0.95,
            message: INTENT_MESSAGES[intent as QueryIntent]?.(evidenceCount) || `V4.4: ${evidenceCount} sources`,
        };
    }

    // Conditional GREEN (2+ sources)
    if (CONDITIONAL_GREEN_2.includes(intent as QueryIntent)) {
        return {
            level: evidenceCount >= 2 ? 'GREEN' : 'YELLOW',
            confidence: evidenceCount >= 2 ? 0.85 : 0.7,
            message: INTENT_MESSAGES[intent as QueryIntent]?.(evidenceCount) || `V4.4: ${evidenceCount} sources`,
        };
    }

    // Default (RESEARCH, etc.): GREEN if 3+ sources
    return {
        level: evidenceCount >= 3 ? 'GREEN' : 'YELLOW',
        confidence: evidenceCount >= 3 ? 0.9 : 0.7,
        message: INTENT_MESSAGES[intent as QueryIntent]?.(evidenceCount) || `V4.4: ${evidenceCount} sources`,
    };
}


// ═══════════════════════════════════════════════════════════════
// V5.3: Grounding Badge Fusion — Thresholds
// ═══════════════════════════════════════════════════════════════

export const GROUNDING_THRESHOLDS = {
    /**
     * Minimum supportScore to maintain GREEN badge.
     * Calibrated at 0.4 — legal analysis inherently synthesizes
     * beyond literal evidence text. Scores of 40-60% are normal.
     */
    GREEN_MIN: 0.4,
    /** Minimum supportScore to maintain YELLOW badge (below → RED) */
    YELLOW_MIN: 0.2,
    /**
     * Minimum number of claims for grounding to be meaningful.
     * Short responses (1-2 claims) get noisy API scores.
     */
    MIN_CLAIMS: 3,
} as const;

/**
 * V5.3 Grounding Badge Fusion — Downgrade-only post-processing
 * 
 * Applies the Check Grounding API's supportScore as a circuit breaker:
 *   - GREEN → YELLOW if supportScore < GREEN_MIN
 *   - GREEN/YELLOW → RED if supportScore < YELLOW_MIN
 *   - Never upgrades (RED stays RED)
 */
export function applyGroundingFusion(
    badge: BadgeResult,
    groundingScore: number | null,
    totalClaimCount: number,
): BadgeResult {
    // Null safety: if grounding check failed, preserve original badge
    if (groundingScore === null) {
        return badge;
    }

    // Minimum claims gate: don't downgrade on tiny responses
    if (totalClaimCount < GROUNDING_THRESHOLDS.MIN_CLAIMS) {
        return badge;
    }

    // Already RED — can't downgrade further
    if (badge.level === 'RED') {
        return badge;
    }

    // Code-verified compute — not subject to grounding downgrade
    if (badge.message.includes('Code-Verified')) {
        return badge;
    }

    // GREEN → YELLOW or RED
    if (badge.level === 'GREEN' && groundingScore < GROUNDING_THRESHOLDS.GREEN_MIN) {
        const downgradeLevel = groundingScore < GROUNDING_THRESHOLDS.YELLOW_MIN ? 'RED' : 'YELLOW';
        return {
            level: downgradeLevel,
            confidence: groundingScore,
            message: downgradeLevel === 'RED'
                ? `⚠️ Limited evidence support — review cited sources carefully. ${badge.message}`
                : `AI Synthesis — response includes substantive analysis beyond direct quotes. ${badge.message}`,
        };
    }

    // YELLOW → RED
    if (badge.level === 'YELLOW' && groundingScore < GROUNDING_THRESHOLDS.YELLOW_MIN) {
        return {
            level: 'RED',
            confidence: groundingScore,
            message: `⚠️ Limited evidence support — review cited sources carefully. ${badge.message}`,
        };
    }

    // Score is above thresholds → upgrade confidence
    return {
        ...badge,
        confidence: Math.max(badge.confidence, groundingScore),
    };
}
```
