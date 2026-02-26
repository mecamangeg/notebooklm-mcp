# _deprecated / check-grounding

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `src` |
| **Role** | Source |
| **Bundle** | `agent___deprecated__check-grounding` |
| **Files** | 1 |
| **Total size** | 19,318 bytes |
| **Generated** | 2026-02-26 14:05 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `agent/_deprecated/check-grounding.ts` (19,318 bytes, Source)

---

## `agent/_deprecated/check-grounding.ts`

| Field | Value |
|-------|-------|
| **Role** | Source |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-18 |
| **Size** | 19,318 bytes |
| **Exports** | `SegmentationMetrics`, `GroundingCheckResult`, `checkGrounding` |

```typescript
/**
 * Check Grounding — Enterprise Validation Layer
 * Ported from robsky-ai-vertex to robsky-angular
 * 
 * Uses the Discovery Engine GroundedGenerationService to validate
 * the Senior Partner's advisory against the Paralegal's evidence.
 * 
 * Key corrections applied from DevKnowledge MCP validation:
 *   - grounding config uses `default_grounding_config` (NOT `default`)
 *   - GroundingFact uses `{ factText, attributes }` (NOT `{ text, uri, title }`)
 *   - Per-claim byte offsets converted via byte-offset.ts for UI rendering
 * 
 * This runs AFTER the Partner returns its advisory, adding ~500ms
 * of validation latency. It's non-blocking — failures are logged
 * but never break the pipeline.
 */

import { GroundedGenerationServiceClient } from '@google-cloud/discoveryengine/build/src/v1';
import type { google } from '@google-cloud/discoveryengine/build/protos/protos';
import { env } from '../env';
import type { EvidenceItem } from './types';
import { byteOffsetToCharOffset } from './byte-offset';

// ═══════════════════════════════════════════════════════════════
// SDK Type Aliases
// ═══════════════════════════════════════════════════════════════

type IClaim = google.cloud.discoveryengine.v1.CheckGroundingResponse.IClaim;
type IFactChunk = google.cloud.discoveryengine.v1.IFactChunk;
type ICheckGroundingFactChunk = google.cloud.discoveryengine.v1.CheckGroundingResponse.ICheckGroundingFactChunk;

// ═══════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════

/** Structured fact segmentation metrics for diagnostics */
export interface SegmentationMetrics {
    /** Number of evidence items received */
    inputCount: number;
    /** Number of fact chunks after segmentation */
    outputCount: number;
    /** Ratio: outputCount / inputCount */
    ratio: number;
    /** Average chunk character count */
    avgChunkChars: number;
    /** Maximum chunk character count */
    maxChunkChars: number;
    /** Number of chunks clamped near the 10K limit */
    clampedCount: number;
}

export interface GroundingCheckResult {
    /** Overall support score (0.0 – 1.0), null if check failed */
    supportScore: number | null;
    /** Individual grounded claims */
    claims: Array<{
        claimText: string;
        /** Indices into citedChunks[] that support this claim */
        citationIndices: number[];
        /** Whether the claim is grounded (has ≥1 citation above threshold) */
        grounded: boolean;
        /** Per-claim confidence score (0.0–1.0) */
        score?: number;
        /** Start position (bytes) of this claim in the answer candidate */
        startPos?: number;
        /** End position (bytes, exclusive) of this claim in the answer candidate */
        endPos?: number;
        /** Start position converted to JS string character offset */
        charStartPos?: number;
        /** End position converted to JS string character offset */
        charEndPos?: number;
    }>;
    /** Total number of grounded claims */
    groundedClaimCount: number;
    /** Total number of claims actually checked */
    totalClaimCount: number;
    /** Total claims in response including non-checked */
    rawClaimCount: number;
    /** Cited portions of input facts supporting claims */
    citedChunks: Array<{
        chunkText: string;
        source?: string;
        uri?: string;
        title?: string;
        domain?: string;
        sourceMetadata?: Record<string, string>;
    }>;
    /** Cited fact chunks (lightweight, text only) */
    citedFacts: string[];
    /** Evidence utilization ratio */
    evidenceUtilization: number;
    /** Fact segmentation metrics */
    segmentation: SegmentationMetrics;
    /** Latency of the check in ms */
    latencyMs: number;
    /** Whether the check itself failed (non-critical) */
    error?: string;
}

// ═══════════════════════════════════════════════════════════════
// Client Singleton (Lazy)
// ═══════════════════════════════════════════════════════════════

let groundingClient: GroundedGenerationServiceClient | null = null;

function getGroundingClient(): GroundedGenerationServiceClient {
    if (!groundingClient) {
        groundingClient = new GroundedGenerationServiceClient();
    }
    return groundingClient;
}

// ═══════════════════════════════════════════════════════════════
// Retry for Transient gRPC Failures
// ═══════════════════════════════════════════════════════════════

/** gRPC status codes for transient errors worth retrying */
const RETRYABLE_GRPC_CODES = new Set([
    4,   // DEADLINE_EXCEEDED
    14,  // UNAVAILABLE
]);

async function checkGroundingWithRetry(
    client: GroundedGenerationServiceClient,
    request: google.cloud.discoveryengine.v1.ICheckGroundingRequest,
): Promise<google.cloud.discoveryengine.v1.ICheckGroundingResponse> {
    try {
        const [response] = await client.checkGrounding(request);
        return response;
    } catch (err) {
        const error = err as { code?: number; message?: string };

        if (error.code && RETRYABLE_GRPC_CODES.has(error.code)) {
            console.warn(`[Grounding] ⚠️ Transient error (gRPC code ${error.code}), retrying in 200ms...`);
            await new Promise(resolve => setTimeout(resolve, 200));
            const [response] = await client.checkGrounding(request);
            return response;
        }

        throw err;
    }
}

// ═══════════════════════════════════════════════════════════════
// Smart Truncation on Sentence Boundaries
// ═══════════════════════════════════════════════════════════════

/**
 * Truncate advisory to API token limit, preserving sentence boundaries.
 * API limit is 4096 tokens. Conservative: 3800 tokens ≈ 19000 chars.
 */
function truncateForGrounding(advisory: string, maxChars: number = 19000): string {
    if (advisory.length <= maxChars) {
        return advisory;
    }

    const searchWindow = advisory.slice(0, maxChars);

    const lastSentenceEnd = Math.max(
        searchWindow.lastIndexOf('. '),
        searchWindow.lastIndexOf('.\n'),
        searchWindow.lastIndexOf('? '),
        searchWindow.lastIndexOf('?\n'),
        searchWindow.lastIndexOf('! '),
        searchWindow.lastIndexOf('!\n'),
        searchWindow.lastIndexOf(';\n'),
    );

    if (lastSentenceEnd > maxChars * 0.5) {
        return advisory.slice(0, lastSentenceEnd + 1).trimEnd();
    }

    const lastSpace = searchWindow.lastIndexOf(' ');
    if (lastSpace > maxChars * 0.8) {
        return advisory.slice(0, lastSpace).trimEnd();
    }

    return advisory.slice(0, maxChars);
}

// ═══════════════════════════════════════════════════════════════
// Legal-Aware Paragraph Splitting
// ═══════════════════════════════════════════════════════════════

function splitIntoParagraphs(text: string): string[] {
    let normalized = text
        .replace(/<br\s*\/?>/gi, '\n')
        .replace(/&nbsp;/gi, ' ')
        .replace(/&amp;/gi, '&');

    const splitPattern = new RegExp(
        [
            '\\n\\n',
            '\\n(?=(?:SECTION|ARTICLE|RULE|CHAPTER|PART|WHEREAS|NOW,?\\s+THEREFORE|RESOLUTION|CIRCULAR|ORDER|DECREE)\\b)',
            '\\n(?=(?:\\d{1,3}\\.\\s|\\([a-z]\\)|\\([0-9]+\\)|§\\s*\\d|[A-Z]\\.\\s))',
            '\\n(?=#{1,4}\\s)',
        ].join('|'),
        'gi'
    );

    return normalized
        .split(splitPattern)
        .map(p => p.trim())
        .filter(p => p.length > 20);
}

// ═══════════════════════════════════════════════════════════════
// Fact Segmentation
// ═══════════════════════════════════════════════════════════════

interface GroundingFact {
    factText: string;
    attributes: Record<string, string>;
}

/**
 * Segment evidence items into smaller fact chunks for better grounding.
 * Uses legal-aware paragraph boundaries for natural breaking points.
 * 
 * CORRECTED from DevKnowledge MCP validation:
 * - Uses `factText` (not `text`)
 * - Uses `attributes` map (not `uri`/`title` top-level fields)
 */
function segmentEvidence(evidence: EvidenceItem[]): { facts: GroundingFact[]; metrics: SegmentationMetrics } {
    const MAX_CHUNK_SIZE = 2000;
    const MAX_FACTS = 200;    // API hard limit
    const facts: GroundingFact[] = [];

    for (const item of evidence) {
        const text = item.content || item.title;
        if (!text) continue;

        // CORRECTED: use `attributes` map per DevKnowledge validation
        const baseAttrs: Record<string, string> = {
            source: item.sourceId || 'unknown',
            title: item.title || 'Untitled',
            ...(item.citation ? { citation: item.citation.display, uri: item.citation.uri } : {}),
        };

        // Short text → single fact
        if (text.length <= MAX_CHUNK_SIZE) {
            facts.push({ factText: text, attributes: baseAttrs });
            if (facts.length >= MAX_FACTS) break;
            continue;
        }

        // Legal-aware splitting for large documents
        const paragraphs = splitIntoParagraphs(text);
        let currentChunk = '';

        for (const para of paragraphs) {
            if ((currentChunk + para).length > MAX_CHUNK_SIZE && currentChunk) {
                facts.push({
                    factText: currentChunk.trim(),
                    attributes: { ...baseAttrs, chunk: `part ${facts.length + 1}` },
                });
                currentChunk = para;
                if (facts.length >= MAX_FACTS) break;
            } else {
                currentChunk += (currentChunk ? '\n\n' : '') + para;
            }
        }
        if (currentChunk.trim() && facts.length < MAX_FACTS) {
            facts.push({
                factText: currentChunk.trim(),
                attributes: { ...baseAttrs, chunk: `part ${facts.length + 1}` },
            });
        }

        if (facts.length >= MAX_FACTS) break;
    }

    const finalFacts = facts.slice(0, MAX_FACTS);

    // Compute segmentation metrics
    const chunkSizes = finalFacts.map(f => f.factText.length);
    const metrics: SegmentationMetrics = {
        inputCount: evidence.length,
        outputCount: finalFacts.length,
        ratio: evidence.length > 0 ? Math.round((finalFacts.length / evidence.length) * 100) / 100 : 0,
        avgChunkChars: chunkSizes.length > 0
            ? Math.round(chunkSizes.reduce((a, b) => a + b, 0) / chunkSizes.length)
            : 0,
        maxChunkChars: chunkSizes.length > 0 ? Math.max(...chunkSizes) : 0,
        clampedCount: chunkSizes.filter(s => s >= 9900).length,
    };

    return { facts: finalFacts, metrics };
}

// ═══════════════════════════════════════════════════════════════
// Core Function
// ═══════════════════════════════════════════════════════════════

/**
 * Validate the Partner's advisory against the evidence packet
 * using the Discovery Engine Check Grounding API.
 * 
 * This is a SOFT validation — failures never break the pipeline.
 */
export async function checkGrounding(
    advisory: string,
    evidence: EvidenceItem[],
): Promise<GroundingCheckResult> {
    const startTime = Date.now();

    const emptySegmentation: SegmentationMetrics = {
        inputCount: 0, outputCount: 0, ratio: 0,
        avgChunkChars: 0, maxChunkChars: 0, clampedCount: 0,
    };

    if (!evidence.length) {
        return {
            supportScore: null,
            claims: [],
            groundedClaimCount: 0,
            totalClaimCount: 0,
            rawClaimCount: 0,
            citedChunks: [],
            citedFacts: [],
            evidenceUtilization: 0,
            segmentation: emptySegmentation,
            latencyMs: 0,
            error: 'No evidence to ground against',
        };
    }

    // CORRECTED: use `default_grounding_config` per DevKnowledge validation
    const groundingConfigName = `projects/${env.GOOGLE_PROJECT_ID}/locations/${env.VERTEX_AI_SEARCH_LOCATION}/groundingConfigs/default_grounding_config`;

    try {
        const client = getGroundingClient();

        const { facts, metrics: segmentation } = segmentEvidence(evidence);
        console.log(`[Grounding] 📊 Segmentation: ${segmentation.inputCount} → ${segmentation.outputCount} facts, ` +
            `avg ${segmentation.avgChunkChars} chars, max ${segmentation.maxChunkChars} chars` +
            `${segmentation.clampedCount > 0 ? `, ${segmentation.clampedCount} clamped` : ''}`);

        const truncatedAdvisory = truncateForGrounding(advisory);
        if (truncatedAdvisory.length < advisory.length) {
            console.log(`[Grounding] ✂️ Advisory truncated: ${advisory.length} → ${truncatedAdvisory.length} chars (sentence boundary)`);
        }

        const response = await checkGroundingWithRetry(client, {
            groundingConfig: groundingConfigName,
            answerCandidate: truncatedAdvisory,
            facts,
            groundingSpec: {
                citationThreshold: 0.6,
                enableClaimLevelScore: true,
            },
        });

        const latencyMs = Date.now() - startTime;

        const allClaims: IClaim[] = response.claims || [];
        const rawClaimCount = allClaims.length;

        // Filter out claims where groundingCheckRequired === false
        const checkedClaims = allClaims.filter(
            (claim) => claim.groundingCheckRequired !== false
        );

        const claims = checkedClaims.map((claim) => {
            const citationIndices = (claim.citationIndices || []).map(Number);
            const startPos = claim.startPos != null ? Number(claim.startPos) : undefined;
            const endPos = claim.endPos != null ? Number(claim.endPos) : undefined;
            return {
                claimText: claim.claimText || '',
                citationIndices,
                grounded: citationIndices.length > 0,
                ...(claim.score != null ? { score: Number(claim.score) } : {}),
                ...(startPos != null ? { startPos } : {}),
                ...(endPos != null ? { endPos } : {}),
                // Byte → char offset conversion for UI highlighting
                ...(startPos != null ? { charStartPos: byteOffsetToCharOffset(truncatedAdvisory, startPos) } : {}),
                ...(endPos != null ? { charEndPos: byteOffsetToCharOffset(truncatedAdvisory, endPos) } : {}),
            };
        });

        const groundedClaimCount = claims.filter((c) => c.grounded).length;
        const supportScore = response.supportScore ?? null;

        const citedChunksRaw: IFactChunk[] = response.citedChunks || [];
        const citedChunks = citedChunksRaw.map((chunk) => ({
            chunkText: chunk.chunkText || '',
            source: chunk.source || undefined,
            uri: chunk.uri || undefined,
            title: chunk.title || undefined,
            domain: chunk.domain || undefined,
            sourceMetadata: chunk.sourceMetadata
                ? Object.fromEntries(Object.entries(chunk.sourceMetadata))
                : undefined,
        }));

        const citedFactsRaw: ICheckGroundingFactChunk[] = response.citedFacts || [];
        const citedFacts = citedFactsRaw
            .map((f) => f.chunkText || '')
            .filter(Boolean);

        const evidenceUtilization = facts.length > 0
            ? citedChunks.length / facts.length
            : 0;

        const skippedClaims = rawClaimCount - checkedClaims.length;
        console.log(`[Grounding] ✅ Check complete: score=${supportScore?.toFixed(3) ?? 'N/A'}, ` +
            `claims=${groundedClaimCount}/${claims.length} grounded` +
            `${skippedClaims > 0 ? ` (${skippedClaims} non-checkable skipped)` : ''}` +
            `${citedChunks.length > 0 ? `, ${citedChunks.length} cited chunks (${Math.round(evidenceUtilization * 100)}% utilization)` : ''}` +
            `${citedFacts.length > 0 ? `, ${citedFacts.length} cited facts` : ''}, ${latencyMs}ms`);

        return {
            supportScore,
            claims,
            groundedClaimCount,
            totalClaimCount: claims.length,
            rawClaimCount,
            citedChunks,
            citedFacts,
            evidenceUtilization,
            segmentation,
            latencyMs,
        };
    } catch (err) {
        const latencyMs = Date.now() - startTime;
        const error = err as { message?: string; code?: number };
        const errorMsg = error.message || 'Unknown grounding check error';

        console.warn(`[Grounding] ⚠️ Check failed (${latencyMs}ms): ${errorMsg}`);

        return {
            supportScore: null,
            claims: [],
            groundedClaimCount: 0,
            totalClaimCount: 0,
            rawClaimCount: 0,
            citedChunks: [],
            citedFacts: [],
            evidenceUtilization: 0,
            segmentation: emptySegmentation,
            latencyMs,
            error: errorMsg,
        };
    }
}
```
