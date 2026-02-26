# _deprecated / fast-lane

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `src` |
| **Role** | Source |
| **Bundle** | `agent___deprecated__fast-lane` |
| **Files** | 1 |
| **Total size** | 8,252 bytes |
| **Generated** | 2026-02-26 14:05 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `agent/_deprecated/fast-lane.ts` (8,252 bytes, Source)

---

## `agent/_deprecated/fast-lane.ts`

| Field | Value |
|-------|-------|
| **Role** | Source |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-18 |
| **Size** | 8,252 bytes |
| **Exports** | `FastLaneResult`, `executeFastLaneLookup` |

```typescript
/**
 * Fast Lane — Direct LOOKUP Bypass (Ported from robsky-ai-vertex)
 *
 * For LOOKUP intents, skips the Paralegal ReAct loop entirely.
 * Executes the appropriate tool call(s) directly based on query analysis.
 *
 * Decision logic:
 *   1. If query contains a G.R. number, RA number, etc. → get_document_by_citation
 *   2. If query says "case digest" or "full text"      → search_legal_corpus (DEEP_READ)
 *      with dual-pass augmented retrieval for full-spectrum coverage
 *   3. Otherwise                                       → search_legal_corpus (SNIPPET)
 */

import { executeSearch, getDocumentByCitation } from './implementations';
import { EvidenceItem } from './types';

export interface FastLaneResult {
    evidence: EvidenceItem[];
    summary: string;
    latencyMs: number;
    /** Research Funnel: Total matching documents from Vertex AI totalSize */
    totalFound?: number;
}

// Citation extraction patterns
const GR_PATTERN = /G\.?R\.?\s*(No\.?)?\s*(\d+)/i;
const RA_PATTERN = /(Republic Act|R\.?A\.?)\s*(No\.?)?\s*(\d+)/i;
const IFRS_PATTERN = /(IFRS|IAS|PAS|PFRS)\s*(\d+)/i;
const RR_PATTERN = /(RR|RMC|RMO|Revenue Regulation)\s*(No\.?)?\s*([\d-]+)/i;
const PD_PATTERN = /(Presidential Decree|P\.?D\.?)\s*(No\.?)?\s*(\d+)/i;
const EO_PATTERN = /(Executive Order|E\.?O\.?)\s*(No\.?)?\s*(\d+)/i;

const DEEP_READ_TRIGGERS = /case digest|full text|digest of|summary of/i;
const VS_PATTERN = /\b(\w+)\s+vs?\.?\s+(\w+)/i;

// Patterns that trigger dual-pass augmented retrieval
const CASE_DIGEST_PATTERN = /case digest|digest of/i;

// Prefixes to strip from query for clean case name extraction
const QUERY_PREFIXES = /^(?:case digest|digest of|summary of|full text):?\s*/i;

/**
 * Execute a Fast Lane LOOKUP — bypass Paralegal entirely
 *
 * @param query - The user's query (already classified as LOOKUP)
 * @returns FastLaneResult with evidence gathered via direct tool calls
 */
export async function executeFastLaneLookup(query: string): Promise<FastLaneResult> {
    const startTime = Date.now();
    let evidence: EvidenceItem[] = [];
    let totalFound = 0;

    // Strategy 1: Direct citation lookup
    const citationMatch = query.match(GR_PATTERN)
        || query.match(RA_PATTERN)
        || query.match(IFRS_PATTERN)
        || query.match(RR_PATTERN)
        || query.match(PD_PATTERN)
        || query.match(EO_PATTERN);

    if (citationMatch) {
        const citation = citationMatch[0];
        console.log(`[FastLane] 📌 Direct citation lookup: "${citation}"`);

        const doc = await getDocumentByCitation(citation);
        if (doc) {
            doc.sourceId = '[Source 1]';
            evidence.push(doc);
        }
    }

    // Strategy 2: Case name search (e.g., "People vs De Jesus") or fallback
    if (evidence.length === 0) {
        const searchMode = DEEP_READ_TRIGGERS.test(query) ? 'DEEP_READ' : 'SNIPPET';

        // Clean query — strip prefixes for better case name matching
        const cleanQuery = query.replace(QUERY_PREFIXES, '').trim();
        const vsMatch = cleanQuery.match(VS_PATTERN);
        const searchQuery = vsMatch ? vsMatch[0] : cleanQuery;

        console.log(`[FastLane] 🔍 Pass 1 — Corpus search: "${searchQuery}" (mode: ${searchMode})`);

        const pass1Result = await executeSearch(searchQuery, 'ALL', 'auto', searchMode);
        evidence = pass1Result.evidence;
        totalFound += pass1Result.totalFound;

        // Dual-Pass Augmented Retrieval for Case Digests
        // When a case digest is requested and Pass 1 found documents,
        // run a second search targeting the factual narrative.
        if (CASE_DIGEST_PATTERN.test(query) && evidence.length > 0) {
            const augQuery = `${searchQuery} facts ruling held disposition`;
            console.log(`[FastLane] 🔍 Pass 2 — Augmented retrieval: "${augQuery}" (mode: ${searchMode})`);

            const pass2Result = await executeSearch(augQuery, 'ALL', 'auto', searchMode);
            const pass2Evidence = pass2Result.evidence;
            totalFound += pass2Result.totalFound;

            // Merge strategy: deduplicate by title, concatenate content for same doc
            let mergedCount = 0;
            let newCount = 0;
            for (const p2 of pass2Evidence) {
                const existing = evidence.find(e => e.title === p2.title);
                if (existing) {
                    // Same document — append Pass 2 content
                    existing.content += '\n\n--- [Pass 2: Majority Opinion Targeting] ---\n\n' + p2.content;
                    mergedCount++;
                } else {
                    evidence.push(p2);
                    newCount++;
                }
            }
            console.log(`[FastLane] ✅ Pass 2 merged: ${mergedCount} augmented, ${newCount} new docs`);
        }

        // Renumber sources after merge
        evidence.forEach((e, i) => { e.sourceId = `[Source ${i + 1}]`; });

        // Title-match verification gate for case digest queries
        // If the user requested "case digest: X vs Y", verify that X or Y
        // actually appears in the returned evidence titles
        if (CASE_DIGEST_PATTERN.test(query) && evidence.length > 0 && vsMatch) {
            const party1 = vsMatch[1].toLowerCase();
            const party2 = vsMatch[2].toLowerCase();
            const foundRequestedCase = evidence.some(e => {
                const titleLower = e.title.toLowerCase();
                return titleLower.includes(party1) && titleLower.includes(party2);
            });

            if (!foundRequestedCase) {
                const foundPartialMatch = evidence.some(e => {
                    const titleLower = e.title.toLowerCase();
                    return titleLower.includes(party1) || titleLower.includes(party2);
                });

                if (foundPartialMatch) {
                    console.log(`[FastLane] ⚠️ PARTIAL MATCH: Found "${party1}" or "${party2}" but not both.`);
                } else {
                    console.log(`[FastLane] ⛔ NO MATCH: Requested case "${vsMatch[0]}" NOT found in evidence titles.`);
                    // Inject a synthetic "not found" marker so the Partner knows
                    const evidenceTitles = evidence.map(e => e.title).join('; ');
                    evidence.unshift({
                        sourceId: '[Source 0]',
                        title: `⚠️ CASE NOT FOUND: "${vsMatch[0]}"`,
                        content: `IMPORTANT: The user requested a case digest for "${vsMatch[0]}" but this specific case was NOT found in the legal corpus. ` +
                            `The following evidence items are from OTHER cases that may cite or reference "${vsMatch[0]}" in their text, ` +
                            `but they are NOT the requested case itself. ` +
                            `Do NOT synthesize a case digest from these citing cases. ` +
                            `Instead, inform the user that "${vsMatch[0]}" is not available in the corpus. ` +
                            `Evidence titles actually returned: ${evidenceTitles}`,
                        citation: { display: 'System Notice', uri: 'system-notice' },
                        authority: { label: 'System', tier: 1, type: 'SYSTEM_NOTICE' },
                        domain: 'general',
                    });
                    // Re-number after prepend
                    evidence.forEach((e, i) => { e.sourceId = `[Source ${i + 1}]`; });
                }
            } else {
                console.log(`[FastLane] ✅ Title match confirmed: "${vsMatch[0]}" found in evidence.`);
            }
        }
    }

    const latencyMs = Date.now() - startTime;
    const summary = evidence.length > 0
        ? `Fast Lane found ${evidence.length} document(s): ${evidence.map(e => e.title).join(', ')}`
        : 'No documents found via Fast Lane.';

    console.log(`[FastLane] Complete: ${evidence.length} docs in ${latencyMs}ms`);

    return { evidence, summary, latencyMs, totalFound: totalFound > 0 ? totalFound : undefined };
}
```
