# retrieval / search-retriever

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `src` |
| **Role** | Source |
| **Bundle** | `retrieval__search-retriever` |
| **Files** | 1 |
| **Total size** | 10,883 bytes |
| **Generated** | 2026-02-26 14:05 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `retrieval/search-retriever.ts` (10,883 bytes, Source)

---

## `retrieval/search-retriever.ts`

| Field | Value |
|-------|-------|
| **Role** | Source |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-18 |
| **Size** | 10,883 bytes |
| **Exports** | `RetrievedDocument`, `RetrievalOptions`, `retrieveDocuments` |

```typescript
/**
 * Architecture C — Retrieval Layer (Search-Only)
 *
 * Decoupled Vertex AI Search API wrapper using SearchServiceClient.search().
 * Returns raw documents with extractive segments — NO generation.
 *
 * This is the critical decoupling: we use the search method (not answerQuery)
 * to get pure document retrieval, enabling any model for generation.
 */

import { SearchServiceClient } from '@google-cloud/discoveryengine';
import { env } from '../env';
import type { QueryDomain } from '../agent/classifier';

// ══════════════════════════════════════════════════════════════
// Types
// ══════════════════════════════════════════════════════════════

export interface RetrievedDocument {
    sourceNumber: number;
    id: string;
    title: string;
    uri: string;
    content: string;
    snippet: string;
    extractiveSegments: Array<{
        content: string;
        relevanceScore?: number;
        pageNumber?: string;
        previousSegments?: string[];
        nextSegments?: string[];
    }>;
    extractiveAnswers: Array<{
        content: string;
        pageNumber?: string;
    }>;
    relevanceScore?: number;
    /** Structured metadata from document schema */
    metadata: Record<string, any>;
}

export interface RetrievalOptions {
    domain?: QueryDomain;
    pageSize?: number;
    maxExtractiveSegments?: number;
    boostSpec?: any;
    filter?: string;
}

// ══════════════════════════════════════════════════════════════
// Singleton Client
// ══════════════════════════════════════════════════════════════

let searchClient: SearchServiceClient | null = null;

function getSearchClient(): SearchServiceClient {
    if (!searchClient) {
        searchClient = new SearchServiceClient();
    }
    return searchClient;
}

// ══════════════════════════════════════════════════════════════
// Protobuf Helpers (reused from vertex-provider.ts pattern)
// ══════════════════════════════════════════════════════════════

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
    // Legacy protobuf format
    if (value.stringValue !== undefined) return value.stringValue;
    if (value.numberValue !== undefined) return value.numberValue;
    if (value.boolValue !== undefined) return value.boolValue;
    if (value.structValue) return unwrapStruct(value.structValue);
    if (value.listValue?.values) {
        return value.listValue.values.map((v: any) => unwrapValue(v));
    }
    if ('fields' in value && typeof value.fields === 'object') return unwrapStruct(value);
    if (Array.isArray(value)) return value.map(unwrapValue);
    return value;
}

function unwrapStruct(struct: any): Record<string, any> {
    if (!struct?.fields) return {};
    const result: Record<string, any> = {};
    for (const [key, val] of Object.entries(struct.fields)) {
        result[key] = unwrapValue(val);
    }
    return result;
}

// ══════════════════════════════════════════════════════════════
// Core Retrieval
// ══════════════════════════════════════════════════════════════

/**
 * Retrieve documents from Vertex AI Search using search-only mode.
 * No generation — just pure retrieval with extractive content.
 *
 * @param query - User's search query
 * @param options - Retrieval configuration (domain filter, page size, etc.)
 * @returns Array of retrieved documents with extractive segments
 */
export async function retrieveDocuments(
    query: string,
    options: RetrievalOptions = {}
): Promise<RetrievedDocument[]> {
    const client = getSearchClient();
    const startMs = Date.now();

    const servingConfig = client.projectLocationCollectionEngineServingConfigPath(
        env.GOOGLE_PROJECT_ID,
        env.VERTEX_AI_SEARCH_LOCATION || 'global',
        'default_collection',
        env.VERTEX_AI_SEARCH_ENGINE_ID,
        'default_search',
    );

    // Build domain filter
    let filter = options.filter || '';
    if (options.domain && options.domain !== 'MIXED' && !filter) {
        filter = `domain: ANY("${options.domain.toLowerCase()}")`;
    }

    const request: any = {
        servingConfig,
        query,
        pageSize: options.pageSize ?? 10,
        contentSearchSpec: {
            extractiveContentSpec: {
                maxExtractiveSegmentCount: options.maxExtractiveSegments ?? 3,
                maxExtractiveAnswerCount: 1,
                returnExtractiveSegmentScore: true,
                numPreviousSegments: 1,
                numNextSegments: 1,
            },
            snippetSpec: { returnSnippet: true },
        },
        queryExpansionSpec: { condition: 'AUTO' as const, pinUnexpandedResults: true },
        spellCorrectionSpec: { mode: 'AUTO' as const },
        ...(filter ? { filter } : {}),
        ...(options.boostSpec ? { boostSpec: options.boostSpec } : {}),
    };

    try {
        const response = await client.search(request, { autoPaginate: false });
        const resultsArray = response[0] || [];

        const docs = resultsArray.map((result: any, index: number) => {
            const doc = result.document;
            const structData = unwrapStruct(doc?.structData || {});
            const derivedData = unwrapStruct(doc?.derivedStructData || {});

            // Extract extractive segments with context
            const segments = (derivedData.extractive_segments as any[] || []).map((seg: any) => ({
                content: seg.content || '',
                relevanceScore: seg.relevanceScore != null ? Number(seg.relevanceScore) : undefined,
                pageNumber: seg.pageNumber != null ? String(seg.pageNumber) : undefined,
                previousSegments: seg.previous_segments?.map((p: any) => p.content || '') || [],
                nextSegments: seg.next_segments?.map((n: any) => n.content || '') || [],
            })).filter((s: any) => s.content);

            const answers = (derivedData.extractive_answers as any[] || []).map((ans: any) => ({
                content: ans.content || '',
                pageNumber: ans.pageNumber != null ? String(ans.pageNumber) : undefined,
            })).filter((a: any) => a.content);

            const snippets = derivedData.snippets as any[] || [];

            // Build consolidated content with metadata prepended
            let content = '';
            if (segments.length > 0) {
                content = segments.map((seg: any) => {
                    const parts: string[] = [];
                    if (seg.previousSegments?.length) parts.push(...seg.previousSegments);
                    if (seg.content) parts.push(seg.content);
                    if (seg.nextSegments?.length) parts.push(...seg.nextSegments);
                    return parts.join('\n\n');
                }).join('\n\n---\n\n');
            } else if (snippets.length > 0) {
                content = snippets[0]?.snippet || '';
            }

            // Prepend document metadata
            const metaParts: string[] = [];
            if (structData.case_title) metaParts.push(`Case Title: ${structData.case_title}`);
            if (structData.docket_number) metaParts.push(`Docket Number: ${structData.docket_number}`);
            if (structData.date) metaParts.push(`Decision Date: ${structData.date}`);
            if (structData.ponente) metaParts.push(`Ponente: Justice ${structData.ponente}`);
            if (metaParts.length > 0) {
                content = metaParts.join('\n') + '\n\n---\n\n' + content;
            }

            const title = structData.case_title || structData.title || structData.docket_number || 'Untitled';

            return {
                sourceNumber: index + 1,
                id: doc?.id || doc?.name || '',
                title,
                uri: structData.display_uri || doc?.name || '',
                content,
                snippet: snippets[0]?.snippet || '',
                extractiveSegments: segments,
                extractiveAnswers: answers,
                relevanceScore: derivedData.relevance_score,
                metadata: structData,
            };
        });

        const elapsedMs = Date.now() - startMs;
        console.log(`[Retriever] Query: "${query.substring(0, 50)}..." | ${docs.length} docs | ${filter || 'no filter'} | ${elapsedMs}ms`);

        // FAIL-OPEN: If domain filter returned 0 and we had a filter, retry without
        if (docs.length === 0 && filter) {
            console.warn(`[Retriever] ⚠️ Domain filter returned 0 results. Retrying without filter...`);
            return retrieveDocuments(query, { ...options, domain: undefined, filter: undefined });
        }

        return docs;

    } catch (error: any) {
        // FAIL-OPEN on filter errors
        const isFilterError =
            error.code === 3 ||
            error.message?.includes('INVALID_ARGUMENT') ||
            error.message?.includes('filter');

        if (isFilterError && filter) {
            console.warn(`[Retriever] ⚠️ Filter error (${error.message}). Retrying without filter...`);
            return retrieveDocuments(query, { ...options, domain: undefined, filter: undefined });
        }

        console.error(`[Retriever] Error:`, error.message || error);
        throw error;
    }
}
```
