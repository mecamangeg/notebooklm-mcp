# grounding-audit.service

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `robsky-angular` |
| **Role** | Source |
| **Bundle** | `services__grounding-audit.service` |
| **Files** | 1 |
| **Total size** | 7,059 bytes |
| **Generated** | 2026-02-26 14:45 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `app/services/grounding-audit.service.ts` (7,059 bytes, Service)

---

## `app/services/grounding-audit.service.ts`

| Field | Value |
|-------|-------|
| **Role** | Service |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-26 |
| **Size** | 7,059 bytes |
| **Exports** | `GroundingAuditService` |

```typescript
import { Injectable, inject } from '@angular/core';
import { AuthService } from './auth.service';
import { environment } from '../../environments/environment';
import type { Citation, GroundingAudit, GroundingClaim } from '../models/types';

/**
 * GroundingAuditService — Layer 2 trust badge.
 *
 * Calls the Vertex AI Check Grounding API after each response stream completes.
 * The call is NON-BLOCKING — the response appears immediately; the badge updates ~500ms later.
 *
 * devknowledge MCP-validated (2026-02-25, updated 2026-02-26):
 *   - Latency < 500ms (GA confirmed)
 *   - Claim-level scores GA since April 24, 2025
 *   - groundingCheckRequired = false → non-factual claim, excluded from score
 *   - Bug F (2026-02-26): Must send groundingSpec.enableClaimLevelScore=true or claims[].score
 *     is never populated. Parser must read c['score'] not c['claimScore'] (API field name).
 *
 * Endpoint:
 *   POST https://discoveryengine.googleapis.com/v1/projects/{PROJECT}/locations/global/
 *        groundingConfigs/default_grounding_config:check
 *   Authorization: Bearer {GCP_TOKEN}
 */
@Injectable({ providedIn: 'root' })
export class GroundingAuditService {
    private readonly auth = inject(AuthService);

    private readonly PROJECT = environment.agentEngine.projectId;
    private readonly ENDPOINT =
        `https://discoveryengine.googleapis.com/v1/projects/${this.PROJECT}` +
        `/locations/global/groundingConfigs/default_grounding_config:check`;

    /**
     * Calls the checkGrounding API and returns a GroundingAudit, or null on failure/skip.
     *
     * @param responseText - The full assistant response text (answerCandidate)
     * @param citations    - Citation[] from buildCitationsFromEvents(); snippets become facts[]
     */
    async checkGrounding(
        responseText: string,
        citations: Citation[],
    ): Promise<GroundingAudit | null> {
        if (!responseText || citations.length === 0) return null;

        const token = await this.auth.getGcpToken();
        if (!token) return null;

        // Build facts[] from citation snippets (full sanitized RetrievedContext.text)
        const facts = citations
            .filter(c => !!c.snippet)
            .map(c => ({
                factText: c.snippet,
                attributes: {
                    title: c.title ?? '',
                    uri: c.uri ?? '',
                    source: `Source ${c.sourceNumber ?? ''}`,
                },
            }));

        if (facts.length === 0) return null;

        try {
            const res = await fetch(this.ENDPOINT, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    answerCandidate: responseText,
                    facts,
                    // enableClaimLevelScore: required to get per-claim `score` in response.
                    // Without this, claims[].score is never populated → all claims
                    // score as 0 → permanent RED badge (Bug F, fixed 2026-02-26).
                    // Note: citationThreshold is intentionally omitted (causes 400 — Bug C).
                    groundingSpec: {
                        enableClaimLevelScore: true,
                    },
                }),
            });

            if (!res.ok) {
                console.warn(`[GroundingAudit] API error ${res.status}:`, await res.text().catch(() => ''));
                return null;
            }

            const data = await res.json();
            return this.parseAuditResponse(data);
        } catch (err) {
            console.warn('[GroundingAudit] Check failed (non-blocking — response unaffected):', err);
            return null;
        }
    }

    private parseAuditResponse(data: unknown): GroundingAudit {
        const d = data as Record<string, unknown>;

        // supportScore ∈ [0, 1] — fraction of factual claims grounded in facts[]
        const score = typeof d['supportScore'] === 'number' ? d['supportScore'] : 0;

        const rawClaims = Array.isArray(d['claims'])
            ? (d['claims'] as Array<Record<string, unknown>>)
            : [];

        // Filter: groundingCheckRequired = false → non-factual (e.g. "Here is what I found")
        // Only factual claims count towards the score and badge
        const claims: GroundingClaim[] = rawClaims
            .filter(c => c['groundingCheckRequired'] !== false)
            .map(c => {
                // API field is `score` (not `claimScore`) — set only when
                // groundingSpec.enableClaimLevelScore=true is in the request (Bug F fix).
                const claimScore = typeof c['score'] === 'number' ? c['score'] : undefined;
                return {
                    text: typeof c['claimText'] === 'string' ? c['claimText'] : '',
                    grounded: c['groundingCheckRequired'] !== false && (claimScore ?? 0) >= 0.5,
                    score: claimScore,
                    charStartPos: typeof c['startPos'] === 'number' ? c['startPos'] : undefined,
                    charEndPos: typeof c['endPos'] === 'number' ? c['endPos'] : undefined,
                    citationIndices: Array.isArray(c['citationIndices'])
                        ? (c['citationIndices'] as number[])
                        : [],
                };
            });

        const groundedCount = claims.filter(c => c.grounded).length;
        const totalFactual = claims.length;

        // Signal & Citator level mapping (revised 2026-02-25 — Citator Paradox):
        //   Any un-grounded claim (grounded=false AND score < 0.5) → RED warning
        //   Otherwise → GREY (neutral source count — does NOT imply legal correctness)
        //
        //   GREEN is NEVER used — 'checkGrounding' is closed-loop: it validates
        //   attribution against the snippets WE supply, not legal accuracy.
        //   An overturned 1995 case accurately summarised still passes. GREEN implies
        //   legal correctness that this API cannot guarantee (Citator Paradox).
        //
        //   YELLOW is NOT used at response level — repurposed as per-citation year flag
        //   in ChatService (citations > 15 years old get yearFlag = true).
        const hasUngroundedClaim = claims.some(c => !c.grounded && (c.score ?? 0) < 0.5);
        const level: GroundingAudit['level'] = hasUngroundedClaim ? 'RED' : 'GREY';

        return {
            level,
            docsUsed: 0,            // populated by caller (citations.length)
            confidence: score,
            groundingScore: score,
            message: totalFactual > 0
                ? `${groundedCount}/${totalFactual} claims grounded`
                : 'Response grounded',
            claims,
        };
    }
}
```
