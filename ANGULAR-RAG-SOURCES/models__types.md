# types

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `robsky-angular` |
| **Role** | Model/Types |
| **Bundle** | `models__types` |
| **Files** | 1 |
| **Total size** | 5,670 bytes |
| **Generated** | 2026-02-26 11:08 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `app/models/types.ts` (5,670 bytes, Model/Types)

---

## `app/models/types.ts`

| Field | Value |
|-------|-------|
| **Role** | Model/Types |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-26 |
| **Size** | 5,670 bytes |
| **Exports** | `Message`, `DebugData`, `PipelineMetadata`, `GroundingSegment`, `Citation`, `GroundingAudit`, `GroundingClaim`, `ChatRequest`, `ChatResponse` |

```typescript

/**
 * Type Definitions for Robsky Angular
 * Adapted from robsky-ai-vertex src/lib/types.ts
 */

export interface Message {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
    citations?: Citation[];
    audit?: GroundingAudit;
    isStreaming?: boolean;
    pipeline?: PipelineMetadata;
    /** AI-suggested follow-up questions from the Answer API */
    relatedQuestions?: string[];
    /** Per-response pipeline debug telemetry — attached when the debug SSE event arrives */
    debugData?: DebugData;
    /** ADK server-side session ID (stored so chat.service can re-use it) */
    adkSessionId?: string;
    /** Vertex AI Search conversation ID for multi-turn continuity */
    conversationId?: string;
}

/** Pipeline debug telemetry attached to each assistant message */
export interface DebugData {
    traceId: string;
    intent: string;
    model: string;
    path: string;
    latency: {
        total: number;
        classifier: number;
        llm: number;
        grounding: number;
        reranker: number;
    };
    search: {
        resultCount: number;
        rerankerOrderChanged: boolean;
        topRerankerScore: number;
    };
    grounding: {
        score: number | null;
        groundedClaims: number;
        totalClaims: number;
        level: 'GREEN' | 'YELLOW' | 'RED' | null;
    };
    cost: {
        inputTokens: number;
        outputTokens: number;
        totalUsd: number;
        model: string;
    };
    error: string | null;
    logUrl: string;
}

export interface PipelineMetadata {
    engine: string;
    sessionId: string;
    searchResultCount: number;
    totalLatencyMs: number;
}

/**
 * Sentence-level grounding segment from groundingSupports[].segment.
 * Byte offsets (UTF-8) into the full accumulated AI response text.
 * devknowledge validated: startIndex inclusive, endIndex exclusive.
 */
export interface GroundingSegment {
    /** UTF-8 byte offset start in the full accumulated response text (inclusive). */
    startIndex: number;
    /** UTF-8 byte offset end in the full accumulated response text (exclusive). */
    endIndex: number;
    /** The actual grounded text as returned by the Gemini API. */
    text: string;
}

export interface Citation {
    id: string;
    sourceNumber?: number;
    title: string;
    uri?: string;
    domain?: 'accounting' | 'legal' | 'tax' | 'general';
    /** Full RetrievedContext.text — display via TruncateSnippetPipe (truncates at 280 chars).
     * Also used as highlightText for the document viewer's fuzzy treewalk. */
    snippet?: string;
    /** Verbatim text from RetrievedContext.text — passed directly to DocumentViewerService.
     * Identical to snippet. Retained as a named field for semantic clarity at call sites. */
    highlightText?: string;
    pageNumber?: number;
    /** confidence is undefined for Gemini 2.5+ (confidenceScores[] is always empty).
     * See MCP validation report 2026-02-25: "For Gemini 2.5 and later, this list is empty." */
    confidence?: number;
    startIndex?: number;
    endIndex?: number;
    tier?: 1 | 2 | 3 | 4;
    sourceType?: string;
    /** answer-text byte offsets (NOT source doc offsets) — for inline underlines only */
    charStartPos?: number;
    charEndPos?: number;
    chunkId?: string;
    documentName?: string;
    /** Decision year extracted from URI or title (e.g. 2015).
     * Populated by citation-extractor; used for year-based YELLOW flag. */
    year?: number;
    /** True when decision year is > 15 years ago.
     * Set synchronously in ChatService after buildCitationsFromEvents().
     * Triggers per-citation ⚠️ flag in the UI (Signal & Citator pattern). */
    yearFlag?: boolean;
    /**
     * Item 4: Sentence-level grounding segments from groundingSupports[].segment.
     * Maps this citation's source chunks to exact byte spans in the AI response text.
     * Used by ParsedContentComponent to render dotted underlines on grounded sentences.
     */
    responseSegments?: GroundingSegment[];

    // ── Spanner Graph traversal metadata (Plan §4) ────────────────────────
    /** Number of citation hops from the originating case (traverse_citation_graph only).
     * Undefined for regular Vertex AI Search citations.
     * Future UI use: \"via 2 hops\" badge on citation card in citations-panel.ts */
    graphHops?: number;

    /** Relation type from traverse_citation_graph (CITES / OVERRULES / APPLIES / DISTINGUISHES).
     * Undefined for regular Vertex AI Search citations.
     * Future UI use: relation badge colour on citation card. */
    graphRelation?: string;
}


export interface GroundingAudit {
    /**
     * Signal & Citator levels (revised 2026-02-25 after 3-round Gemini Pro debate):
     *   'GREY'  — checkGrounding passed, neutral source count (replaces 'GREEN')
     *   'RED'   — any claim grounded=false + score < 0.5 (hallucination warning)
     *   'GREEN' — DEPRECATED, never shown (Citator Paradox: implies legal accuracy)
     *   'YELLOW'— REPURPOSED as per-citation year flag only (not response-level)
     */
    level: 'GREEN' | 'YELLOW' | 'RED' | 'GREY';
    docsUsed: number;
    confidence: number;
    message?: string;
    groundingScore?: number;
    claims?: GroundingClaim[];
}

export interface GroundingClaim {
    text: string;
    grounded: boolean;
    score?: number;
    charStartPos?: number;
    charEndPos?: number;
    citationIndices: number[];
}

export interface ChatRequest {
    messages: Array<{
        role: 'user' | 'assistant';
        content: string;
    }>;
    sessionId?: string;
    /** Vertex AI Search conversation ID for multi-turn session continuity */
    conversationId?: string;
}

export interface ChatResponse {
    role: 'assistant';
    content: string;
    citations: Citation[];
    audit: GroundingAudit;
    sessionId: string;
    /** Vertex AI Search session ID returned from the backend */
    conversationId?: string;
    pipeline?: PipelineMetadata;
    /** AI-suggested follow-up questions */
    relatedQuestions?: string[];
}
```
