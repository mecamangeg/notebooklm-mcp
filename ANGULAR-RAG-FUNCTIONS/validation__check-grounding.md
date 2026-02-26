# validation / check-grounding

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `src` |
| **Role** | Source |
| **Bundle** | `validation__check-grounding` |
| **Files** | 1 |
| **Total size** | 6,657 bytes |
| **Generated** | 2026-02-26 14:05 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `validation/check-grounding.ts` (6,657 bytes, Source)

---

## `validation/check-grounding.ts`

| Field | Value |
|-------|-------|
| **Role** | Source |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-18 |
| **Size** | 6,657 bytes |
| **Exports** | `GroundingClaim`, `GroundingResult`, `checkGrounding`, `isGroundingEnabled` |

```typescript
/**
 * Architecture C — Check Grounding API Integration
 *
 * Post-generation validation using Discovery Engine's Check Grounding API.
 * Verifies that the generated response is grounded in the retrieved documents.
 *
 * Uses: GroundedGenerationServiceClient.checkGrounding()
 *
 * Returns:
 *   - Support score (0-1) for the overall response
 *   - Per-claim grounding with byte offsets → mapped to character offsets
 *   - List of cited chunks from the source documents
 */

import { GroundedGenerationServiceClient } from '@google-cloud/discoveryengine';
import { env } from '../env';
import { byteOffsetToCharOffset } from './byte-offset';

// ══════════════════════════════════════════════════════════════
// Types
// ══════════════════════════════════════════════════════════════

export interface GroundingClaim {
    claimText: string;
    startPos: number;          // Character offset (0-indexed)
    endPos: number;            // Character offset (0-indexed, exclusive)
    supportScore: number;      // 0-1 support score for this claim
    citedChunkIndices: number[]; // Which source chunks support this claim
    grounded: boolean;         // true if supportScore >= threshold
}

export interface GroundingResult {
    /** Overall support score for the response (0-1) */
    supportScore: number;
    /** Per-claim grounding assessments */
    claims: GroundingClaim[];
    /** Number of claims that are grounded */
    groundedClaimCount: number;
    /** Total number of claims assessed */
    totalClaimCount: number;
    /** Latency of the grounding check */
    latencyMs: number;
    /** Raw API response for debugging */
    rawResponse?: any;
}

// ══════════════════════════════════════════════════════════════
// Singleton Client
// ══════════════════════════════════════════════════════════════

let _groundingClient: GroundedGenerationServiceClient | null = null;

function getGroundingClient(): GroundedGenerationServiceClient {
    if (!_groundingClient) {
        _groundingClient = new GroundedGenerationServiceClient();
    }
    return _groundingClient;
}

// ══════════════════════════════════════════════════════════════
// Core API Call
// ══════════════════════════════════════════════════════════════

/**
 * Check if a generated response is grounded in the retrieved source documents.
 *
 * @param answerCandidate - The generated response text to validate
 * @param facts - Array of source document content strings
 * @param threshold - Support score threshold (default from env)
 *
 * @returns GroundingResult with per-claim analysis
 */
export async function checkGrounding(
    answerCandidate: string,
    facts: string[],
    threshold?: number,
): Promise<GroundingResult> {
    const client = getGroundingClient();
    const startMs = Date.now();
    const supportThreshold = threshold ?? (parseFloat(env.GROUNDING_THRESHOLD) || 0.6);

    // Check Grounding API requires a grounding config parent path
    const groundingConfig = `projects/${env.GOOGLE_PROJECT_ID}/locations/${env.VERTEX_AI_SEARCH_LOCATION || 'global'}/groundingConfigs/default_grounding_config`;

    const request: any = {
        groundingConfig,
        answerCandidate,
        facts: facts.map((content, index) => ({
            factText: content,
        })),
        groundingSpec: {
            citationThreshold: supportThreshold,
        },
    };

    try {
        const [response] = await client.checkGrounding(request);
        const latencyMs = Date.now() - startMs;

        // Parse claims with byte-offset → character-offset mapping
        const claims: GroundingClaim[] = (response.claims || []).map((claim: any) => {
            const startByte = claim.startPos ?? 0;
            const endByte = claim.endPos ?? 0;

            // Convert byte offsets to character offsets (critical for Filipino text)
            const startPos = byteOffsetToCharOffset(answerCandidate, startByte);
            const endPos = byteOffsetToCharOffset(answerCandidate, endByte);

            const citedChunkIndices = (claim.citationIndices || []).map(Number);
            const score = claim.score ?? 0;

            return {
                claimText: claim.claimText || answerCandidate.substring(startPos, endPos),
                startPos,
                endPos,
                supportScore: score,
                citedChunkIndices,
                grounded: score >= supportThreshold,
            };
        });

        const groundedClaimCount = claims.filter(c => c.grounded).length;
        const overallScore = response.supportScore ?? (
            claims.length > 0
                ? claims.reduce((sum, c) => sum + c.supportScore, 0) / claims.length
                : 0
        );

        console.log(
            `[CheckGrounding] Score: ${overallScore.toFixed(2)} | ` +
            `${groundedClaimCount}/${claims.length} claims grounded | ${latencyMs}ms`
        );

        return {
            supportScore: overallScore,
            claims,
            groundedClaimCount,
            totalClaimCount: claims.length,
            latencyMs,
            rawResponse: response,
        };

    } catch (error: any) {
        const latencyMs = Date.now() - startMs;
        console.error(`[CheckGrounding] Error (${latencyMs}ms):`, error.message || error);

        // Graceful degradation: return unknown grounding
        return {
            supportScore: -1, // -1 indicates grounding check failed
            claims: [],
            groundedClaimCount: 0,
            totalClaimCount: 0,
            latencyMs,
        };
    }
}

/**
 * Check if the grounding API is enabled via environment config.
 */
export function isGroundingEnabled(): boolean {
    return env.ENABLE_GROUNDING_CHECK !== 'false';
}
```
