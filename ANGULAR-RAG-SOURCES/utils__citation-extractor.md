# citation-extractor

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `robsky-angular` |
| **Role** | Utility |
| **Bundle** | `utils__citation-extractor` |
| **Files** | 1 |
| **Total size** | 11,706 bytes |
| **Generated** | 2026-02-26 11:05 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `app/utils/citation-extractor.ts` (11,706 bytes, Utility)

---

## `app/utils/citation-extractor.ts`

| Field | Value |
|-------|-------|
| **Role** | Utility |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-26 |
| **Size** | 11,706 bytes |
| **Exports** | `extractToolResultsFromEvents`, `buildCitationsFromEvents` |

```typescript
import type { AgentEngineEvent } from '../models/agent-engine.types';
import type { Citation, GroundingSegment } from '../models/types';

/**
 * Sanitize a raw grounding chunk snippet for storage and highlighting.
 *
 * devknowledge validated: Vertex AI RetrievedContext.text has NO server-side
 * truncation — the API returns the full indexed chunk. We store the full text
 * so document viewer highlight treewalk gets the verbatim passage.
 *
 * Display truncation is handled by TruncateSnippetPipe at render time.
 *
 * Rules applied (cleaning only — NO truncation):
 * 1. Strip [[FN N: ...]] footnote blocks (present in PH SC decision HTML exports).
 * 2. Strip raw HTML tags (Vertex AI extractive segments may include <b> markup).
 * 3. Collapse excess whitespace / newlines.
 *
 * @param raw   The raw text from RetrievedContext.text or Snippet: field.
 */
function sanitizeSnippet(raw: string): string {
    if (!raw) return '';
    // Strip [[FN N: ...]] blocks — lazy quantifier prevents eating across footnotes
    const stripped = raw.replace(/\[\[FN\s+\d+:[\s\S]*?\]\]/g, '').trim();
    // Strip raw HTML tags (Vertex AI Search may include <b> in extractive segments)
    const noHtml = stripped.replace(/<[^>]+>/g, '');
    // Collapse excess whitespace / newlines to single spaces
    return noHtml.replace(/\s+/g, ' ').trim();
}

/**
 * Raw tool result extracted from ADK function_response events.
 * Intermediate structure before converting to Citation objects.
 */
interface RawToolResult {
    index: number;
    title: string;
    url: string;
    docket: string;
    domain: 'legal' | 'tax' | 'accounting';
    snippet: string;
}

/**
 * Extract citation metadata from ADK function_response events.
 *
 * Two tool response formats (confirmed by diagnostic 2026-02-25):
 *  - lookup_with_native_grounding → {grounding_chunks: [{uri, title, text}]}
 *  - search_documents / search_by_domain → "Result 1:\n  Title: ....\n  Source: gs://..."
 *
 * This is a faithful TypeScript port of `_extract_tool_results_from_adk_events()`
 * from the now-deleted `functions/main.py`. Logic is identical; unit tests can
 * be run against both using the captured diagnostic events from 2026-02-25.
 */
export function extractToolResultsFromEvents(events: AgentEngineEvent[]): RawToolResult[] {
    const results: RawToolResult[] = [];
    const seenUrls = new Set<string>();
    let idx = 0;

    function extractDocketFromUrl(url: string): string {
        const m = url.match(/(GRNo\d+|AMNo[^_]+|ACNo\d+)/);
        if (!m) return '';
        return m[1]
            .replace('GRNo', 'G.R. No. ')
            .replace('AMNo', 'A.M. No. ')
            .replace('ACNo', 'A.C. No. ');
    }

    function addResult(
        title: string,
        url: string,
        docket = '',
        domain: string = 'legal',
        snippet = '',
    ): void {
        if (!title) return;
        const normUrl = url.replace(/^(gs:\/\/|https?:\/\/)/, '');
        if (normUrl && seenUrls.has(normUrl)) return;
        if (normUrl) seenUrls.add(normUrl);
        if (!docket && url) docket = extractDocketFromUrl(url);
        const validDomain: 'legal' | 'tax' | 'accounting' = (
            ['legal', 'tax', 'accounting'].includes(domain)
                ? domain
                : 'legal'
        ) as 'legal' | 'tax' | 'accounting';
        results.push({ index: ++idx, title, url, docket, domain: validDomain, snippet });
    }

    for (const event of events) {
        for (const part of event.content?.parts ?? []) {
            const fn = part.function_response;
            if (!fn) continue;

            const toolName = fn.name;
            const responseVal = fn.response as Record<string, unknown>;

            // PATH A: lookup_with_native_grounding → grounding_chunks
            if (toolName === 'lookup_with_native_grounding' && typeof responseVal === 'object' && responseVal !== null) {
                const chunks = (responseVal['grounding_chunks'] as Array<Record<string, string>>) ?? [];
                for (const chunk of chunks) {
                    if (!chunk) continue;
                    addResult(
                        chunk['title'] || chunk['uri'] || '',
                        chunk['uri'] ?? '',
                        '',
                        'legal',
                        sanitizeSnippet(chunk['text'] ?? ''),
                    );
                }
                continue;
            }

            // PATH B: search_documents / search_by_domain → formatted string
            let responseStr = '';
            if (typeof responseVal === 'string') {
                responseStr = responseVal;
            } else if (typeof responseVal === 'object' && responseVal !== null) {
                responseStr = (responseVal['output'] as string) ?? JSON.stringify(responseVal);
            }

            if (!responseStr || responseStr.includes('SEARCH RETURNED ZERO RESULTS')) continue;

            // Parse "Result N:" blocks from _format_results() output
            const blocks = ('\n' + responseStr).split(/\nResult\s+\d+:/);
            for (const block of blocks) {
                if (!block.trim()) continue;
                const titleM = block.match(/Title:\s*(.+)/);
                if (!titleM) continue;
                // Source: stop at first whitespace (GCS paths may have literal \n in output)
                const sourceM = block.match(/Source:\s*(gs:\/\/[^\s]+|https?:\/\/[^\s]+)/);
                const docketM = block.match(/Docket:\s*(.+)/);
                const domainM = block.match(/Domain:\s*(.+)/);
                // Snippet: stop before next labelled field (Segment:/Source:/Content:)
                const snippetM = block.match(/Snippet:\s*(.+?)(?=\n\s*(?:Segment|Source|Content|Domain):|$)/s);
                // Clean URI: remove whitespace AND literal backslash-n escape sequences
                const rawUri = sourceM?.[1] ?? '';
                const cleanUri = rawUri.trim().replace(/\\n/g, '').replace(/\n/g, '');
                addResult(
                    titleM[1].trim(),
                    cleanUri,
                    docketM?.[1].trim() ?? '',
                    domainM?.[1].trim().toLowerCase() ?? 'legal',
                    sanitizeSnippet(snippetM?.[1] ?? ''),
                );
            }
        }
    }

    return results;
}

/**
 * Extract the decision year from a citation URI or title (best-effort).
 *
 * Philippine SC GCS URIs follow the pattern:
 *   gs://robsky-curated/documents/{YEAR}/GRNo{docket}-{YYYYMMDD}.html
 *
 * Fallback: check the title for a 4-digit year ∈ [1900, currentYear].
 *
 * @returns 4-digit year as number, or undefined if not found.
 */
function extractYearFromCitation(uri: string, title: string): number | undefined {
    const currentYear = new Date().getFullYear();

    // Priority 1: path segment — documents/YEAR/ pattern
    const pathYearMatch = uri.match(/\/documents\/(\d{4})\//);
    if (pathYearMatch) {
        const y = parseInt(pathYearMatch[1], 10);
        if (y >= 1900 && y <= currentYear) return y;
    }

    // Priority 2: filename suffix — GRNo12345-YYYYMMDD.html
    const fileYearMatch = uri.match(/-(\d{4})\d{4}\.\w+$/);
    if (fileYearMatch) {
        const y = parseInt(fileYearMatch[1], 10);
        if (y >= 1900 && y <= currentYear) return y;
    }

    // Priority 3: title may contain a year e.g. "People v. Dela Cruz (2008)"
    const titleYearMatch = title.match(/\b(1[9]\d{2}|20[0-2]\d)\b/);
    if (titleYearMatch) {
        const y = parseInt(titleYearMatch[1], 10);
        if (y >= 1900 && y <= currentYear) return y;
    }

    return undefined;
}

/**
 * Convert raw ADK tool results into Citation objects, matched to inline [Source N] refs.
 *
 * Called once at the end of the streaming session when all ADK events
 * have been collected and the final response text is assembled.
 */
export function buildCitationsFromEvents(
    events: AgentEngineEvent[],
    responseText: string,
): Citation[] {
    const toolResults = extractToolResultsFromEvents(events);
    const resultMap = new Map(toolResults.map(r => [r.index, r]));

    // Find all inline citation refs in the response text
    const refs = new Set<number>();
    for (const m of responseText.matchAll(/\[Source\s+(\d+)\]/gi)) {
        refs.add(parseInt(m[1], 10));
    }

    // Build citations in source-number order
    const citations = Array.from(refs).sort((a, b) => a - b).map(num => {
        const tool = resultMap.get(num);
        const snippet = tool?.snippet ?? '';
        const uri = tool?.url ?? '';
        const title = tool?.title ?? `Source ${num}`;

        // Extract decision year for the year-based YELLOW flag logic in ChatService.
        // yearFlag itself is set in ChatService (not here) — this only provides the raw year.
        const year = extractYearFromCitation(uri, title);

        return {
            id: crypto.randomUUID(),
            sourceNumber: num,
            title,
            uri,
            domain: tool?.domain ?? 'legal',
            // Full sanitized text stored — display truncation via TruncateSnippetPipe
            snippet,
            // highlightText = same full text, used by DocumentViewerService for treewalk
            highlightText: snippet,
            tier: 2,
            year,
        } as Citation;
    });

    // ── Item 4: Attach groundingSupports sentence-level segments ────────────
    // groundingSupports[].groundingChunkIndices[] (0-based) maps to citation.sourceNumber-1.
    // Byte offsets are UTF-8 (devknowledge validated): startIndex inclusive, endIndex exclusive.
    // Fallback: if no groundingSupports in events, skip silently (no regression).
    const groundingSupports = extractGroundingSupports(events);
    for (const support of groundingSupports) {
        const chunkIndices = (support['groundingChunkIndices'] as number[] | undefined) ?? [];
        const rawSeg = support['segment'] as Record<string, unknown> | undefined;
        if (!rawSeg) continue;

        const gs: GroundingSegment = {
            startIndex: (rawSeg['startIndex'] as number) ?? 0,
            endIndex: (rawSeg['endIndex'] as number) ?? 0,
            text: (rawSeg['text'] as string) ?? '',
        };

        // Map 0-based chunk index → 1-based sourceNumber → Citation
        for (const chunkIdx of chunkIndices) {
            const citation = citations.find(c => (c.sourceNumber ?? 0) - 1 === chunkIdx);
            if (citation) {
                citation.responseSegments ??= [];
                citation.responseSegments.push(gs);
            }
        }
    }

    return citations;
}

/**
 * Item 4: Extract groundingSupports from ADK events.
 * groundingMetadata is nested inside the final response candidate's grounding_metadata field.
 * Returns the raw groundingSupports array or empty array if not found.
 */
function extractGroundingSupports(events: AgentEngineEvent[]): Record<string, unknown>[] {
    for (const event of events) {
        // groundingMetadata lives in the final response candidate returned by the Gemini model
        const meta = (event as Record<string, unknown>)['grounding_metadata'];
        if (!meta) continue;
        const supports = (meta as Record<string, unknown>)['grounding_supports'];
        if (Array.isArray(supports)) return supports as Record<string, unknown>[];
    }
    return [];
}
```
