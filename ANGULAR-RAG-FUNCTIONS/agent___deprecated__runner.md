# _deprecated / runner

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `src` |
| **Role** | Source |
| **Bundle** | `agent___deprecated__runner` |
| **Files** | 1 |
| **Total size** | 25,009 bytes |
| **Generated** | 2026-02-26 14:05 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `agent/_deprecated/runner.ts` (25,009 bytes, Source)

---

## `agent/_deprecated/runner.ts`

| Field | Value |
|-------|-------|
| **Role** | Source |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-18 |
| **Size** | 25,009 bytes |
| **Exports** | `AgentResponse`, `runAgenticPipeline` |

```typescript

import { runParalegalLoop } from "./paralegal";
import { runSeniorPartner } from "./partner";
import { classifyQueryIntent, type QueryIntent } from "./classifier";
import { executeFastLaneLookup } from "./fast-lane";
import { EvidenceItem } from "./types";
import { checkGrounding, type GroundingCheckResult } from "./check-grounding";
import { determineBadge, applyGroundingFusion, type BadgeResult } from "./badges";

export interface AgentResponse {
    content: string;
    evidence: EvidenceItem[];
    /** Confidence badge (GREEN/YELLOW/RED) with audit message */
    badge: BadgeResult;
    /** Check Grounding API result (null if skipped or failed) */
    grounding?: GroundingCheckResult;
    debug: {
        intent: string;
        /** Fast Lane telemetry (LOOKUP bypass) */
        fastLane?: {
            attempted: boolean;
            hit: boolean;
            latencyMs: number;
        };
        paralegal: {
            turns: number;
            latencyMs: number;
        };
        /** Sniper Quality Gate telemetry */
        qualityGate?: {
            triggered: boolean;
            type: 'SNIPER';
            evidenceBefore: number;
            evidenceAfter: number;
            latencyMs: number;
        };
        partner: {
            model: string;
            latencyMs: number;
        };
        /** Phase C: Check Grounding telemetry */
        grounding?: {
            latencyMs: number;
            supportScore: number | null;
            claimCount: number;
            error?: string;
        };
    };
    totalLatencyMs: number;
}

// ═══════════════════════════════════════════════════════════════
// LOOKUP Precision Filter — keeps only evidence that matches the
// specific entity (person, statute, docket) the user asked about.
//
// Used as a POST-FILTER on Paralegal results when Fast Lane
// falls through (e.g., Fast Lane miss → Paralegal fallback).
// ═══════════════════════════════════════════════════════════════

const LEGAL_STOP_WORDS = new Set([
    'case', 'digest', 'people', 'republic', 'philippines', 'plaintiff',
    'appellee', 'accused', 'appellant', 'defendant', 'petitioner',
    'respondent', 'vs', 'versus', 'of', 'the', 'and', 'in', 'for',
    'no', 'nos', 'gr', 'g.r', 'summary', 'summarize', 'brief',
    'explain', 'what', 'is', 'are', 'was', 'were', 'how', 'who',
    'may', 'can', 'de', 'del', 'los', 'la', 'y', 'a', 'an',
]);

function filterLookupEvidence(query: string, evidence: EvidenceItem[]): EvidenceItem[] {
    // Try docket-number matching first (most precise)
    const grMatch = query.match(/g\.?r\.?\s*no\.?\s*(\d+)/i);
    if (grMatch) {
        const docketNum = grMatch[1];
        const docketMatches = evidence.filter(e =>
            e.citation.display.includes(docketNum) ||
            e.content.includes(docketNum)
        );
        if (docketMatches.length > 0) {
            console.log(`[LOOKUP Filter] Docket match on ${docketNum}: ${docketMatches.length} results`);
            return docketMatches.slice(0, 1);
        }
    }

    // VS-party title verification gate (from robsky-ai-vertex fast-lane.ts)
    const vsMatch = query.match(/\b(\w+)\s+vs?\.?\s+(.+)/i);
    if (vsMatch) {
        const partyAfterVs = vsMatch[2]
            .replace(/[^\w\s]/g, ' ')
            .split(/\s+/)
            .filter(t => t.length >= 2 && !LEGAL_STOP_WORDS.has(t.toLowerCase()))
            .map(t => t.toLowerCase());

        if (partyAfterVs.length > 0) {
            const partyScored = evidence.map(item => {
                const haystack = `${item.title} ${item.citation.display} ${item.content}`.toLowerCase();
                const matchCount = partyAfterVs.filter(t => haystack.includes(t)).length;
                return { item, matchCount };
            });
            partyScored.sort((a, b) => b.matchCount - a.matchCount);

            const bestPartyScore = partyScored[0].matchCount;
            if (bestPartyScore > 0 && bestPartyScore > partyScored[partyScored.length - 1].matchCount) {
                const filtered = partyScored
                    .filter(s => s.matchCount === bestPartyScore)
                    .map(s => s.item);
                console.log(`[LOOKUP Filter] VS-party gate: [${partyAfterVs.join(', ')}] | Best: ${bestPartyScore}/${partyAfterVs.length} | Kept: ${filtered.length}/${evidence.length}`);
                return filtered.slice(0, 2);
            }
        }
    }

    // Extract distinguishing terms from query
    const queryTerms = query
        .toLowerCase()
        .replace(/[^\w\s]/g, ' ')
        .split(/\s+/)
        .filter(t => t.length >= 2 && !LEGAL_STOP_WORDS.has(t));

    if (queryTerms.length === 0) {
        return evidence.slice(0, 1);
    }

    // Score each evidence item by query-term overlap
    const scored = evidence.map(item => {
        const haystack = `${item.title} ${item.citation.display} ${item.content}`.toLowerCase();
        const matchCount = queryTerms.filter(t => haystack.includes(t)).length;
        return { item, matchCount };
    });

    scored.sort((a, b) => b.matchCount - a.matchCount);

    const bestScore = scored[0].matchCount;
    if (bestScore === 0) {
        return evidence.slice(0, 1);
    }

    const filtered = scored
        .filter(s => s.matchCount === bestScore)
        .map(s => s.item);

    console.log(`[LOOKUP Filter] Terms: [${queryTerms.join(', ')}] | Best score: ${bestScore}/${queryTerms.length} | Kept: ${filtered.length}/${evidence.length}`);
    return filtered.slice(0, 2);
}

// ═══════════════════════════════════════════════════════════════
// Intents that MUST produce tool calls — Integrity Guard (V5.1)
// If the Paralegal skips search for these, block PATH A to
// prevent ungrounded synthesis.
// ═══════════════════════════════════════════════════════════════
const MUST_SEARCH_INTENTS: QueryIntent[] = [
    'RESEARCH', 'LOOKUP', 'VERIFICATION', 'COMPARATIVE',
    'COMPLIANCE', 'COMPUTATION', 'DRAFTING', 'ANALYTICAL',
    'SUMMARIZATION', 'TEMPORAL',
];

// Intents that trigger the Sniper Gate when only 1 source is found
const SNIPER_GATE_INTENTS: QueryIntent[] = [
    'RESEARCH', 'DRAFTING', 'COMPUTATION', 'COMPARATIVE',
];

export async function runAgenticPipeline(
    userQuery: string,
    history?: any[]
): Promise<AgentResponse> {
    const startTime = Date.now();

    // ═════════════════════════════════════════════════════════
    // Step 1: Intent Classification (Hybrid: Regex + Fallback)
    // ═════════════════════════════════════════════════════════
    const classification = await classifyQueryIntent(userQuery, !!history?.length);
    const intent = classification.intent;

    console.log(`[Agent] ═════════════════════════════════════════════════════════════`);
    console.log(`[Agent] Pipeline Starting`);
    console.log(`[Agent] Query: "${userQuery.substring(0, 80)}..."`);
    console.log(`[Agent] Intent: ${intent} (via ${classification.source}, ${classification.latencyMs}ms)`);
    console.log(`[Agent] History: ${history?.length || 0} messages`);
    console.log(`[Agent] ═════════════════════════════════════════════════════════════`);

    // ═════════════════════════════════════════════════════════
    // PATH D: FAST LANE (LOOKUP intent — bypass Paralegal)
    // ═════════════════════════════════════════════════════════
    if (intent === 'LOOKUP') {
        console.log(`[Agent] 🚀 PATH D: FAST LANE — Direct lookup (bypassing Paralegal)`);

        const fastLaneResult = await executeFastLaneLookup(userQuery);

        if (fastLaneResult.evidence.length > 0) {
            // Fast Lane success → go directly to Partner
            console.log(`[Agent] ✅ Fast Lane found ${fastLaneResult.evidence.length} documents (${fastLaneResult.latencyMs}ms)`);

            const partnerResult = await runSeniorPartner(
                userQuery,
                fastLaneResult.evidence,
                fastLaneResult.summary,
                intent
            );

            const totalLatencyMs = Date.now() - startTime;

            console.log(`[Agent] ═════════════════════════════════════════════════════════`);
            console.log(`[Agent] PATH D Complete: ${totalLatencyMs}ms total`);
            console.log(`[Agent]   - Fast Lane: ${fastLaneResult.latencyMs}ms (${fastLaneResult.evidence.length} docs)`);
            console.log(`[Agent]   - Partner: ${partnerResult.latencyMs}ms`);
            console.log(`[Agent] ═════════════════════════════════════════════════════════`);

            // Phase C: Check Grounding for Fast Lane results
            const groundingResult = await checkGrounding(partnerResult.advisory, fastLaneResult.evidence);
            const initialBadge = determineBadge(intent, fastLaneResult.evidence.length);
            const badge = applyGroundingFusion(initialBadge, groundingResult.supportScore, groundingResult.totalClaimCount);

            return {
                content: partnerResult.advisory,
                evidence: fastLaneResult.evidence,
                badge,
                grounding: groundingResult,
                debug: {
                    intent,
                    fastLane: {
                        attempted: true,
                        hit: true,
                        latencyMs: fastLaneResult.latencyMs,
                    },
                    paralegal: {
                        turns: 0,
                        latencyMs: fastLaneResult.latencyMs,
                    },
                    partner: {
                        model: partnerResult.model,
                        latencyMs: partnerResult.latencyMs,
                    },
                    grounding: {
                        latencyMs: groundingResult.latencyMs,
                        supportScore: groundingResult.supportScore,
                        claimCount: groundingResult.totalClaimCount,
                        ...(groundingResult.error ? { error: groundingResult.error } : {}),
                    },
                },
                totalLatencyMs: Date.now() - startTime,
            };
        }

        // Fast Lane missed → fall through to regular Paralegal
        console.log(`[Agent] ⚠️ Fast Lane miss — falling through to Paralegal`);
    }

    // ═════════════════════════════════════════════════════════
    // PHASE A: INVESTIGATION (The Paralegal)
    // ═════════════════════════════════════════════════════════
    console.log(`[Agent] ─── Phase A: Investigation ───`);

    const paralegalResult = await runParalegalLoop(userQuery, history);

    console.log(`[Agent] Phase A Complete: ${paralegalResult.evidence.length} sources, ${paralegalResult.turns} turns, in ${paralegalResult.latencyMs}ms`);

    // ═════════════════════════════════════════════════════════
    // 3-WAY FORK: Behavior-Based Routing
    //
    //   PATH A: No tools called → Conversational follow-up
    //   PATH B: Tools called, 0 evidence → Failed search
    //   PATH C: Tools called, evidence found → Research synthesis
    // ═════════════════════════════════════════════════════════

    const toolsCalled = paralegalResult.turns > 0;

    // ─── INTEGRITY GUARD (V5.1) ──────────────────────────────
    // Certain intents MUST produce tool calls. If the Paralegal
    // skips search for these, force PATH B to prevent hallucination.
    const integrityViolation = !toolsCalled && MUST_SEARCH_INTENTS.includes(intent);
    if (integrityViolation) {
        console.warn(`[Agent] 🚨 INTEGRITY GUARD: ${intent} intent requires search but Paralegal used 0 tools`);
        console.warn(`[Agent]    Blocking PATH A — forcing PATH B to prevent ungrounded synthesis`);
    }

    // ─── PATH A: CONVERSATIONAL (No tools called) ────────────
    if (!toolsCalled && !integrityViolation) {
        console.log(`[Agent] 💬 PATH A: Conversational/creative follow-up detected (0 tool calls)`);

        // Use the Paralegal's own summary as the response —
        // no need for the expensive Partner model
        const totalLatencyMs = Date.now() - startTime;

        console.log(`[Agent] ═════════════════════════════════════════════════════════`);
        console.log(`[Agent] PATH A Complete: ${totalLatencyMs}ms total`);
        console.log(`[Agent]   - Paralegal: ${paralegalResult.latencyMs}ms (decided to skip search)`);
        console.log(`[Agent] ═════════════════════════════════════════════════════════`);

        return {
            content: paralegalResult.summary,
            evidence: [],
            badge: { level: 'YELLOW', confidence: 0.7, message: 'Conversational follow-up — based on prior discussion' },
            debug: {
                intent: 'CONVERSATIONAL',
                paralegal: {
                    turns: paralegalResult.turns,
                    latencyMs: paralegalResult.latencyMs,
                },
                partner: {
                    model: 'skipped (PATH A)',
                    latencyMs: 0,
                },
            },
            totalLatencyMs,
        };
    }

    // ─── PATH B: FAILED SEARCH (Tools called, 0 evidence) ───
    if (paralegalResult.evidence.length === 0) {
        const totalLatencyMs = Date.now() - startTime;
        console.log(`[Agent] 📭 PATH B: Search performed but no evidence found`);

        return {
            content: `I searched for information regarding your query but could not find specific matches in our legal corpus. 

Investigation Details:
${paralegalResult.summary}`,
            evidence: [],
            badge: determineBadge('FAILED_SEARCH', 0),
            debug: {
                intent: 'FAILED_SEARCH',
                paralegal: {
                    turns: paralegalResult.turns,
                    latencyMs: paralegalResult.latencyMs,
                },
                partner: {
                    model: 'skipped (PATH B)',
                    latencyMs: 0,
                },
            },
            totalLatencyMs,
        };
    }

    // ─── PATH C: RESEARCH (Tools called, evidence found) ─────
    console.log(`[Agent] 📚 PATH C: Research query — ${paralegalResult.evidence.length} sources found`);

    let evidence = paralegalResult.evidence;

    // ═════════════════════════════════════════════════════════
    // QUALITY GATE 1: SNIPER (Corroboration)
    //
    // If only 1 source was found for a research-class query,
    // request one more search turn to find corroboration.
    // The Partner cannot verify the Paralegal's work, so
    // single-source research is risky.
    // ═════════════════════════════════════════════════════════
    let qualityGateDebug: AgentResponse['debug']['qualityGate'] | undefined;

    if (SNIPER_GATE_INTENTS.includes(intent)
        && evidence.length === 1
        && paralegalResult.turns < 3) {

        console.log(`[Agent] ⚠️ GATE 1 (SNIPER): Single source — requesting corroboration search`);
        console.log(`[Agent]   Evidence: "${evidence[0].title}"`);

        const gateStart = Date.now();
        const evidenceBefore = evidence.length;

        // Run an additional search for corroboration
        const { executeSearch } = await import('./implementations');
        const sniperQuery = `${evidence[0].title} governing statute`;
        console.log(`[Agent]   Sniper query: "${sniperQuery}"`);

        try {
            const sniperResult = await executeSearch(sniperQuery, 'ALL', 'auto', 'SNIPPET');
            const existingUris = new Set(evidence.map(e => e.citation.uri));

            for (const item of sniperResult.evidence) {
                if (!existingUris.has(item.citation.uri)) {
                    existingUris.add(item.citation.uri);
                    item.sourceId = `[Source ${evidence.length + 1}]`;
                    evidence.push(item);
                }
            }
        } catch (error) {
            console.warn(`[Agent] Sniper gate search failed:`, error);
        }

        const gateLatency = Date.now() - gateStart;
        console.log(`[Agent] SNIPER result: ${evidence.length} sources (was ${evidenceBefore}) in ${gateLatency}ms`);

        qualityGateDebug = {
            triggered: true,
            type: 'SNIPER',
            evidenceBefore,
            evidenceAfter: evidence.length,
            latencyMs: gateLatency,
        };
    }

    // ═════════════════════════════════════════════════════════
    // LOOKUP Post-Filter (fallback path only)
    //
    // This runs when the Fast Lane missed but the Paralegal
    // found results. Apply precision filtering to narrow down.
    // ═════════════════════════════════════════════════════════
    if (intent === 'LOOKUP' && evidence.length > 1) {
        evidence = filterLookupEvidence(userQuery, evidence);
        console.log(`[Runner] LOOKUP precision filter: ${paralegalResult.evidence.length} → ${evidence.length}`);
    }

    // ═════════════════════════════════════════════════════════
    // PHASE B: SYNTHESIS (The Senior Partner — Clean Room)
    // ═════════════════════════════════════════════════════════
    console.log(`[Agent] ─── Phase B: Synthesis (Clean Room) ───`);

    let content = "";
    let partnerModel = "skipped";
    let partnerLatency = 0;

    if (evidence.length > 0) {
        const partnerResult = await runSeniorPartner(
            userQuery,
            evidence,
            paralegalResult.summary,
            intent
        );
        content = partnerResult.advisory;
        partnerModel = partnerResult.model;
        partnerLatency = partnerResult.latencyMs;
    } else {
        content = `I searched for information regarding your query but could not find specific matches in our legal corpus. 

Investigation Details:
${paralegalResult.summary}`;
    }

    // ═════════════════════════════════════════════════════════
    // PHASE C: CHECK GROUNDING (Non-blocking validation)
    // ═════════════════════════════════════════════════════════
    let groundingResult: GroundingCheckResult | undefined;
    if (evidence.length > 0 && content) {
        console.log(`[Agent] ─── Phase C: Check Grounding ───`);
        groundingResult = await checkGrounding(content, evidence);
        console.log(`[Agent] Phase C Complete: score=${groundingResult.supportScore?.toFixed(3) ?? 'N/A'}, ${groundingResult.totalClaimCount} claims, ${groundingResult.latencyMs}ms`);
    }

    // ═════════════════════════════════════════════════════════
    // PHASE D: CONFIDENCE BADGE (Intent + Grounding Fusion)
    // ═════════════════════════════════════════════════════════
    const initialBadge = determineBadge(
        evidence.length === 0 ? 'FAILED_SEARCH' : intent,
        evidence.length
    );
    const badge = groundingResult
        ? applyGroundingFusion(initialBadge, groundingResult.supportScore, groundingResult.totalClaimCount)
        : initialBadge;

    const totalLatencyMs = Date.now() - startTime;

    console.log(`[Agent] ═════════════════════════════════════════════════════════`);
    console.log(`[Agent] Pipeline Complete: ${totalLatencyMs}ms total`);
    console.log(`[Agent]   - Paralegal: ${paralegalResult.latencyMs}ms (${paralegalResult.turns} turns)`);
    if (qualityGateDebug) {
        console.log(`[Agent]   - Sniper Gate: ${qualityGateDebug.latencyMs}ms (${qualityGateDebug.evidenceBefore} → ${qualityGateDebug.evidenceAfter} sources)`);
    }
    console.log(`[Agent]   - Partner: ${partnerLatency}ms (${partnerModel})`);
    if (groundingResult) {
        console.log(`[Agent]   - Grounding: ${groundingResult.latencyMs}ms (score=${groundingResult.supportScore?.toFixed(3) ?? 'N/A'})`);
    }
    console.log(`[Agent]   - Badge: ${badge.level} (${badge.confidence.toFixed(2)}) — ${badge.message}`);
    console.log(`[Agent] ═════════════════════════════════════════════════════════`);

    return {
        content,
        evidence,
        badge,
        grounding: groundingResult,
        debug: {
            intent,
            ...(intent === 'LOOKUP' ? {
                fastLane: {
                    attempted: true,
                    hit: false,
                    latencyMs: 0,
                },
            } : {}),
            paralegal: {
                turns: paralegalResult.turns,
                latencyMs: paralegalResult.latencyMs,
            },
            qualityGate: qualityGateDebug,
            partner: {
                model: partnerModel,
                latencyMs: partnerLatency,
            },
            ...(groundingResult ? {
                grounding: {
                    latencyMs: groundingResult.latencyMs,
                    supportScore: groundingResult.supportScore,
                    claimCount: groundingResult.totalClaimCount,
                    ...(groundingResult.error ? { error: groundingResult.error } : {}),
                },
            } : {}),
        },
        totalLatencyMs,
    };
}
```
