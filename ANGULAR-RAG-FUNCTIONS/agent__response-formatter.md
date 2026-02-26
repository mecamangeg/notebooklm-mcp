# agent / response-formatter

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `src` |
| **Role** | Source |
| **Bundle** | `agent__response-formatter` |
| **Files** | 1 |
| **Total size** | 8,379 bytes |
| **Generated** | 2026-02-26 14:05 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `agent/response-formatter.ts` (8,379 bytes, Source)

---

## `agent/response-formatter.ts`

| Field | Value |
|-------|-------|
| **Role** | Source |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-18 |
| **Size** | 8,379 bytes |
| **Exports** | `BadgeResult`, `Citation`, `FormattedResponse`, `FormatInput`, `computeBadge`, `extractCitations`, `formatResponse` |

```typescript
/**
 * Architecture C — Response Formatter
 *
 * Post-processing layer that:
 *   1. Computes the badge (GREEN/YELLOW/RED) from grounding results
 *   2. Maps grounding claims to the generated response
 *   3. Structures the final response for the frontend
 */

import type { QueryIntent } from './classifier';
import type { GroundingResult } from '../validation/check-grounding';
import type { RetrievedDocument } from '../retrieval/search-retriever';
import type { GenerationResult } from '../generation/model-adapter';

// ══════════════════════════════════════════════════════════════
// Types
// ══════════════════════════════════════════════════════════════

export interface BadgeResult {
    level: 'GREEN' | 'YELLOW' | 'RED';
    confidence: number;       // 0-1
    label: string;            // Human-readable label
}

export interface Citation {
    sourceNumber: number;
    title: string;
    uri: string;
    snippet: string;
}

export interface FormattedResponse {
    content: string;
    badge: BadgeResult;
    citations: Citation[];
    grounding: {
        supportScore: number;
        groundedClaimCount: number;
        totalClaimCount: number;
        latencyMs: number;
    };
    debug: {
        engine: string;
        intent: string;
        domain: string;
        model: string;
        pipelineVersion: 'v2';
        searchResultCount: number;
        classifierLatencyMs: number;
        retrievalLatencyMs: number;
        generationLatencyMs: number;
        groundingLatencyMs: number;
        totalLatencyMs: number;
    };
    relatedQuestions: string[];
}

// ══════════════════════════════════════════════════════════════
// Badge Computation
// ══════════════════════════════════════════════════════════════

/**
 * Compute the confidence badge from grounding results and intent.
 *
 * Rules:
 *   - GREEN: supportScore >= 0.8 OR intent is CONVERSATIONAL (no grounding needed)
 *   - YELLOW: supportScore >= 0.5
 *   - RED: supportScore < 0.5 or grounding failed
 *
 * Creative intents (DRAFTING, PEDAGOGICAL) get a relaxed threshold:
 *   - GREEN: >= 0.6
 *   - YELLOW: >= 0.3
 */
export function computeBadge(
    supportScore: number,
    intent: QueryIntent,
): BadgeResult {
    // CONVERSATIONAL: no grounding needed
    if (intent === 'CONVERSATIONAL') {
        return { level: 'GREEN', confidence: 1.0, label: 'Conversational follow-up' };
    }

    // Grounding check failed (-1)
    if (supportScore < 0) {
        return { level: 'YELLOW', confidence: 0.5, label: 'Grounding check unavailable' };
    }

    // Creative intents → relaxed thresholds
    const isCreative = ['DRAFTING', 'PEDAGOGICAL', 'PREDICTIVE', 'STRATEGIC'].includes(intent);

    if (isCreative) {
        if (supportScore >= 0.6) return { level: 'GREEN', confidence: supportScore, label: 'Well-grounded' };
        if (supportScore >= 0.3) return { level: 'YELLOW', confidence: supportScore, label: 'Partially grounded' };
        return { level: 'RED', confidence: supportScore, label: 'Insufficiently grounded' };
    }

    // Standard intents → strict thresholds
    if (supportScore >= 0.8) return { level: 'GREEN', confidence: supportScore, label: 'Well-grounded' };
    if (supportScore >= 0.5) return { level: 'YELLOW', confidence: supportScore, label: 'Partially grounded' };
    return { level: 'RED', confidence: supportScore, label: 'Insufficiently grounded' };
}

// ══════════════════════════════════════════════════════════════
// Citation Extraction
// ══════════════════════════════════════════════════════════════

/**
 * Extract citation references from the generated content.
 * Maps [source N] references to the retrieved documents.
 */
export function extractCitations(
    content: string,
    retrievedDocs: RetrievedDocument[],
): Citation[] {
    const citationPattern = /\[source\s+(\d+)\]/gi;
    const cited = new Set<number>();

    let match;
    while ((match = citationPattern.exec(content)) !== null) {
        cited.add(parseInt(match[1], 10));
    }

    return Array.from(cited)
        .sort((a, b) => a - b)
        .map(num => {
            const doc = retrievedDocs.find(d => d.sourceNumber === num);
            if (!doc) {
                return {
                    sourceNumber: num,
                    title: `Source ${num}`,
                    uri: '',
                    snippet: '',
                };
            }
            return {
                sourceNumber: doc.sourceNumber,
                title: doc.title,
                uri: doc.uri,
                snippet: doc.snippet || doc.content.substring(0, 200),
            };
        });
}

// ══════════════════════════════════════════════════════════════
// Response Formatting
// ══════════════════════════════════════════════════════════════

export interface FormatInput {
    generationResult: GenerationResult;
    groundingResult: GroundingResult | null;
    retrievedDocs: RetrievedDocument[];
    intent: QueryIntent;
    domain: string;
    classifierLatencyMs: number;
    retrievalLatencyMs: number;
    totalStartMs: number;
}

/**
 * Format the final response for the frontend.
 */
export function formatResponse(input: FormatInput): FormattedResponse {
    const content = input.generationResult.content;
    const citations = extractCitations(content, input.retrievedDocs);

    // Compute badge from grounding (or fallback to citation count)
    let badge: BadgeResult;
    let groundingInfo = {
        supportScore: -1,
        groundedClaimCount: 0,
        totalClaimCount: 0,
        latencyMs: 0,
    };

    if (input.groundingResult && input.groundingResult.supportScore >= 0) {
        badge = computeBadge(input.groundingResult.supportScore, input.intent);
        groundingInfo = {
            supportScore: input.groundingResult.supportScore,
            groundedClaimCount: input.groundingResult.groundedClaimCount,
            totalClaimCount: input.groundingResult.totalClaimCount,
            latencyMs: input.groundingResult.latencyMs,
        };
    } else {
        // Fallback: use citation presence as a rough proxy
        const hasCitations = citations.length > 0;
        badge = hasCitations
            ? { level: 'YELLOW', confidence: 0.6, label: 'Citations found (grounding not verified)' }
            : { level: 'RED', confidence: 0.2, label: 'No citations detected' };
    }

    const totalLatencyMs = Date.now() - input.totalStartMs;

    return {
        content,
        badge,
        citations,
        grounding: groundingInfo,
        debug: {
            engine: 'architecture-c-v2',
            intent: input.intent,
            domain: input.domain,
            model: input.generationResult.modelId,
            pipelineVersion: 'v2',
            searchResultCount: input.retrievedDocs.length,
            classifierLatencyMs: input.classifierLatencyMs,
            retrievalLatencyMs: input.retrievalLatencyMs,
            generationLatencyMs: input.generationResult.latencyMs,
            groundingLatencyMs: groundingInfo.latencyMs,
            totalLatencyMs,
        },
        relatedQuestions: [], // TODO: Phase 2 — extract from generation or compute
    };
}
```
