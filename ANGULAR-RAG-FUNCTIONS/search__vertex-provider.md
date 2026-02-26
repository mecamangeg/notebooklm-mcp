# search / vertex-provider

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `src` |
| **Role** | Source |
| **Bundle** | `search__vertex-provider` |
| **Files** | 1 |
| **Total size** | 12,603 bytes |
| **Generated** | 2026-02-26 14:05 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `search/vertex-provider.ts` (12,603 bytes, Source)

---

## `search/vertex-provider.ts`

| Field | Value |
|-------|-------|
| **Role** | Source |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-18 |
| **Size** | 12,603 bytes |
| **Exports** | `VertexSearchProvider` |

```typescript
import { SearchServiceClient } from '@google-cloud/discoveryengine';
import { env } from '../env';
import { EvidenceItem, SearchOptions, SearchResult } from '../agent/types';

// Singleton client
let searchClient: SearchServiceClient | null = null;

function getSearchClient(): SearchServiceClient {
    if (!searchClient) {
        searchClient = new SearchServiceClient();
    }
    return searchClient;
}

const SEARCH_CONFIG = {
    projectId: env.GOOGLE_PROJECT_ID,
    location: env.VERTEX_AI_SEARCH_LOCATION,
    engineId: env.VERTEX_AI_SEARCH_ENGINE_ID,
    collectionId: "default_collection",
    servingConfigId: "default_search"
} as const;

// Helper: unwrapProtobufValue
function unwrapValue(value: any): any {
    if (!value || typeof value !== 'object') return value;
    if ('kind' in value) {
        switch (value.kind) {
            case 'stringValue': return value.stringValue;
            case 'numberValue': return value.numberValue;
            case 'boolValue': return value.boolValue;
            case 'nullValue': return null;
            case 'listValue': return (value.listValue?.values || []).map(unwrapValue);
            case 'structValue': return unwrapStruct(value.structValue);
        }
    }
    if ('fields' in value && typeof value.fields === 'object') return unwrapStruct(value);
    if (Array.isArray(value)) return value.map(unwrapValue);
    const result: Record<string, unknown> = {};
    for (const [key, val] of Object.entries(value)) {
        result[key] = unwrapValue(val);
    }
    return result;
}

function unwrapStruct(struct: any): Record<string, any> {
    if (!struct || !struct.fields) return {};
    const result: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(struct.fields)) {
        result[key] = unwrapValue(value);
    }
    return result;
}

function getTierLabel(tier: number): string {
    switch (tier) {
        case 1: return "TIER_1_SUPREME";
        case 2: return "TIER_2_BINDING";
        case 3: return "TIER_3_PERSUASIVE";
        case 4: return "TIER_4_REFERENCE";
        default: return "TIER_UNKNOWN";
    }
}

export class VertexSearchProvider {
    async search(options: SearchOptions): Promise<SearchResult> {
        const startTime = Date.now();
        const { query, filterTier = "ALL", domain = "auto", searchMode = "SNIPPET", sortBy = "RELEVANCE", docType } = options;

        let filter = "";
        if (filterTier === "TIER_1_SUPREME") {
            filter = 'authority_tier: ANY("1")';
        } else if (filterTier === "TIER_1_AND_2") {
            filter = 'authority_tier: ANY("1", "2")';
        }

        if (domain !== "auto" && domain) {
            const domainFilter = `domain: ANY("${domain}")`;
            filter = filter ? `(${filter}) AND ${domainFilter}` : domainFilter;
        }

        if (docType && docType !== 'all') {
            const docTypeFilter = `doc_type: ANY("${docType}")`;
            filter = filter ? `(${filter}) AND ${docTypeFilter}` : docTypeFilter;
        }

        const contentSearchSpec = searchMode === 'DEEP_READ'
            ? {
                snippetSpec: { returnSnippet: true, maxSnippetCount: 3 },
                extractiveContentSpec: {
                    maxExtractiveSegmentCount: 10,
                    maxExtractiveAnswerCount: 5,
                    numPreviousSegments: 3,
                    numNextSegments: 3,
                    returnExtractiveSegmentScore: true
                }
            }
            : {
                snippetSpec: { returnSnippet: true, maxSnippetCount: 3 },
                extractiveContentSpec: {
                    maxExtractiveSegmentCount: 2,
                    maxExtractiveAnswerCount: 2,
                    numPreviousSegments: 1,
                    numNextSegments: 1,
                    returnExtractiveSegmentScore: true,
                }
            };

        const pageSize = options.pageSize || 5;
        const client = getSearchClient();
        const servingConfig = client.projectLocationCollectionEngineServingConfigPath(
            SEARCH_CONFIG.projectId,
            SEARCH_CONFIG.location,
            SEARCH_CONFIG.collectionId,
            SEARCH_CONFIG.engineId,
            SEARCH_CONFIG.servingConfigId
        );

        const orderBy = sortBy === 'DATE_DESC' ? 'update_time desc' : undefined;

        const baseRequest = {
            servingConfig,
            query,
            pageSize,
            contentSearchSpec,
            ...(orderBy ? { orderBy } : {}),
            queryExpansionSpec: { condition: 'AUTO' as const, pinUnexpandedResults: true },
            spellCorrectionSpec: { mode: 'AUTO' as const },
            rankingExpressionBackend: 'RANK_BY_FORMULA' as const,
            rankingExpression: '0.4 * relevance_score + 0.2 * keyword_similarity_score + 0.2 * rr(fill_nan(c.authority_tier, 4), 1) + 0.1 * fill_nan(c.boost_modifier, 0) + 0.1 * log(fill_nan(c.syllabi_count, 0) + 1)',
            relevanceFilterSpec: {
                keywordSearchThreshold: { relevanceThreshold: 'LOW' },
                semanticSearchThreshold: { semanticRelevanceThreshold: 0.25 },
            },
        };

        try {
            // ATTEMPT 1: Strict Search (with filters)
            console.log(`[Search] Attempting STRICT search. Filter: [${filter || "NONE"}]`);

            const response = await client.search({
                ...baseRequest,
                filter: filter || undefined
            }, { autoPaginate: false });

            const resultsArray = response[0];
            const rawResponse = response[2] as any;
            const totalSize = rawResponse?.totalSize ?? resultsArray?.length ?? 0;

            if (rawResponse?.redirectUri) {
                return {
                    evidence: [{
                        sourceId: "[Redirect]",
                        title: "System Redirect",
                        content: `Redirected to: ${rawResponse.redirectUri}`,
                        authority: { tier: 4, label: "REDIRECT", type: "System" },
                        citation: { display: "Redirect", uri: rawResponse.redirectUri },
                        domain: "general" as const
                    }], totalFound: 0
                };
            }

            let evidence = this.transformResults(resultsArray || [], "VERIFIED_TIER");

            // FAIL-OPEN: If strict filter returned 0 results, retry without filter
            if (evidence.length === 0 && filter) {
                console.warn(`[Search] ⚠️ STRICT search returned 0 results with filter. Retrying BROAD...`);
                const broadResponse = await client.search({
                    ...baseRequest,
                    filter: undefined
                }, { autoPaginate: false });
                evidence = this.transformResults(broadResponse[0] || [], "UNVERIFIED_FALLBACK");

                if (evidence.length > 0) {
                    evidence[0].content = `[⚠️ SYSTEM NOTE: Strict authority filtering returned 0 results (filter: ${filter}). These results are from BROAD search based on text relevance ONLY. Verify authority tier manually.]\n\n${evidence[0].content}`;
                }
            }

            return { evidence, totalFound: totalSize };
        } catch (error) {
            const err = error as { code?: number; message?: string };

            // FAIL-OPEN: Catch INVALID_ARGUMENT (schema mismatch, unsupported filter fields)
            // This handles cases like authority_tier not being filterable yet
            const isSchemaError =
                err.code === 3 ||
                err.message?.includes("INVALID_ARGUMENT") ||
                err.message?.includes("filter") ||
                err.message?.includes("unsupported");

            if (isSchemaError && filter) {
                console.warn(`[Search] ⚠️ Filter syntax error (${err.message}). Retrying WITHOUT filter...`);

                try {
                    const broadResponse = await client.search({
                        ...baseRequest,
                        filter: undefined
                    }, { autoPaginate: false });

                    const fallbackResults = broadResponse[0];
                    const broadRaw = broadResponse[2] as any;
                    const broadTotalSize = broadRaw?.totalSize ?? fallbackResults?.length ?? 0;

                    const evidence = this.transformResults(fallbackResults || [], "UNVERIFIED_FALLBACK");

                    if (evidence.length > 0) {
                        evidence[0].content = `[⚠️ SYSTEM NOTE: Strict authority filtering failed due to schema configuration. These results are based on text relevance ONLY. You MUST verify the authority tier manually from the document metadata.]\n\n${evidence[0].content}`;
                    }

                    console.log(`[Search] ✅ FALLBACK search succeeded. Found ${evidence.length} documents (totalSize: ${broadTotalSize}).`);
                    return { evidence, totalFound: broadTotalSize };

                } catch (retryError) {
                    console.error(`[Search] ❌ FALLBACK search also failed:`, retryError);
                    throw retryError;
                }
            }

            console.error("[Search] Fatal Error:", error);
            throw error;
        }
    }

    private transformResults(resultsArray: any[], matchType: string): EvidenceItem[] {
        return resultsArray.map((res, idx) => {
            const doc = res.document;
            const structData = unwrapStruct(doc?.structData || {});
            const derivedData = unwrapStruct(doc?.derivedStructData || {});

            const tierStr = String(structData.authority_tier || "4");
            const tierNum = Math.min(Math.max(parseInt(tierStr, 10) || 4, 1), 4) as 1 | 2 | 3 | 4;

            const extractiveSegments = derivedData.extractive_segments as any[] || [];
            const snippets = derivedData.snippets as any[] || [];
            const preservedSegments = extractiveSegments.map(seg => ({
                content: seg.content,
                relevanceScore: seg.relevanceScore != null ? Number(seg.relevanceScore) : undefined,
                pageNumber: seg.pageNumber != null ? String(seg.pageNumber) : undefined,
            })).filter(s => s.content);

            let content = "";
            if (extractiveSegments.length > 0) {
                content = extractiveSegments.map(seg => {
                    const parts = [];
                    if (seg.previous_segments) parts.push(...seg.previous_segments.map((p: any) => p.content || ''));
                    if (seg.content) parts.push(seg.content);
                    if (seg.next_segments) parts.push(...seg.next_segments.map((n: any) => n.content || ''));
                    return parts.join('\n\n');
                }).join('\n\n---\n\n');
            } else {
                content = snippets[0]?.snippet || "No content available";
            }

            const metadataParts = [];
            if (structData.case_title) metadataParts.push(`Case Title: ${structData.case_title}`);
            if (structData.docket_number) metadataParts.push(`Docket Number: ${structData.docket_number}`);
            if (structData.date) metadataParts.push(`Decision Date: ${structData.date}`);
            if (structData.ponente) metadataParts.push(`Ponente: Justice ${structData.ponente}`);

            if (metadataParts.length > 0) {
                content = metadataParts.join('\n') + '\n\n---\n\n' + content;
            }

            return {
                sourceId: `[Source ${idx + 1}]`,
                title: structData.case_title || structData.title || structData.docket_number || "Untitled",
                content,
                authority: {
                    tier: tierNum,
                    label: getTierLabel(tierNum),
                    type: structData.doc_type || "Unknown"
                },
                citation: {
                    display: structData.docket_number || "N/A",
                    uri: structData.display_uri || doc?.name || ""
                },
                domain: (structData.domain as any) || "legal",
                _extractiveSegments: preservedSegments.length > 0 ? preservedSegments : undefined
            };
        });
    }
}
```
