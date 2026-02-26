# agent / unified-engine

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `src` |
| **Role** | Source |
| **Bundle** | `agent__unified-engine` |
| **Files** | 1 |
| **Total size** | 28,502 bytes |
| **Generated** | 2026-02-26 14:05 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `agent/unified-engine.ts` (28,502 bytes, Source)

---

## `agent/unified-engine.ts`

| Field | Value |
|-------|-------|
| **Role** | Source |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-18 |
| **Size** | 28,502 bytes |
| **Exports** | `UnifiedBadge`, `UnifiedCitation`, `UnifiedResponse`, `queryUnifiedEngine`, `streamQueryUnifiedEngine`, `StreamChunkCallback` |

```typescript
/**
 * Unified Engine — Vertex AI Search Answer API
 *
 * Replaces the deprecated `converseConversation()` with the `answerQuery()` method,
 * the officially recommended API for Vertex AI Search.
 *
 * Architecture: "Stop building the engine. Use the engine."
 *
 * Three-phase managed pipeline:
 *   Phase 1: Query Understanding (rephrasing, classification)
 *   Phase 2: Search (managed retrieval from data store)
 *   Phase 3: Answer Generation (grounded answer with citations)
 *
 * Preamble persona: ALT AI Senior Partner — Philippine Legal, Tax, and Accounting.
 * 9-way automatic format detection (Advisory → Case Digest → Drafting → Computation →
 * Comparison → Procedural → Strategic → Tutorial → Quiz).
 *
 * Key improvements over converse:
 *   - Complex query decomposition
 *   - System instructions (preamble) with Senior Partner persona
 *   - Grounding score filtering (HIGH)
 *   - Related question suggestions
 *   - Answer skip reasons for graceful fallback
 *   - Step-level observability
 *   - Streaming via streamAnswerQuery
 *
 * @see https://cloud.google.com/generative-ai-app-builder/docs/answer
 * @see https://cloud.google.com/generative-ai-app-builder/docs/stream-answer
 * @see https://cloud.google.com/generative-ai-app-builder/docs/preamble
 */

import { ConversationalSearchServiceClient } from '@google-cloud/discoveryengine';
import { env } from '../env';

// ═══════════════════════════════════════════════════════════════
// Configuration
// ═══════════════════════════════════════════════════════════════

const CONFIG = {
    projectId: env.GOOGLE_PROJECT_ID,
    location: env.VERTEX_AI_SEARCH_LOCATION || 'global',
    collectionId: 'default_collection',
    // answerQuery uses ENGINE path (not data store path)
    engineId: env.VERTEX_AI_SEARCH_ENGINE_ID,
    servingConfigId: 'default_serving_config',
} as const;

// ═══════════════════════════════════════════════════════════════
// Preamble — ALT AI Senior Partner System Instructions
// ═══════════════════════════════════════════════════════════════
//
// Structure follows Google's official preamble best practices:
//   Part 1: Task Description (persona + task)
//   Part 2: Additional Instructions (6 numbered rules)
//
// @see https://cloud.google.com/generative-ai-app-builder/docs/preamble
// @see https://cloud.google.com/vertex-ai/generative-ai/docs/learn/prompts/system-instruction-introduction
// ═══════════════════════════════════════════════════════════════

const PREAMBLE = `You are a Senior Partner at ALT AI, the Philippines' premier Legal, Tax, and Accounting advisory firm. Your role is to write authoritative professional advisories for Philippine CPAs, lawyers, and tax practitioners who rely on your output in their professional practice.

Given a user query and a list of source documents from the ALT AI legal corpus, write a definitive response that cites individual sources comprehensively using inline [Source N] references. Every factual claim must cite its source. Present information directly as established facts — never reference your research process, tools, or data sources.

If this is a multi-turn conversation, maintain continuity with prior exchanges while answering the current query with the same citation rigor.

Follow these rules:

1. CITATION PROTOCOL — Every factual claim must end with [Source N] matching the source document it came from. Multiple sources supporting one claim: [Source 1], [Source 3]. Never fabricate source numbers. Never format citations as markdown links. If a point is not supported by the provided sources, state: "The evidence provided does not directly address this point."

2. AUTHORITY HIERARCHY — Source documents carry descending weight: Tier 1 (Constitution, Republic Acts, Supreme Court En Banc, IFRS Standards) supersedes Tier 2 (SC Division Decisions, Revenue Regulations), which supersedes Tier 3 (CA Decisions, BIR Rulings, RMCs), which supersedes Tier 4 (Commentaries, Treatises). If a lower-tier source conflicts with a higher-tier source, explicitly state the conflict and note the higher-tier authority controls. If a source's tier is not determinable from its metadata, cite it verbatim without assigning a tier.

3. OUTPUT FORMAT — Detect the appropriate structure from the query:
   - General questions ("Can I…", "Is it legal…", "What is the law on…") → Executive Summary + Analysis with citations organized by issue + Authority Hierarchy table + Caveats.
   - Case digests ("digest of…", "facts of [case]", "[Party] vs [Party]") → Case Title + Facts + Issue + Ruling (Held) + Ratio Decidendi.
   - Drafting ("draft a motion…", "prepare a pleading…") → Philippine legal pleading format with Caption, Body (numbered paragraphs), Prayer, Signature Block.
   - Computation ("compute…", "calculate…", "how much…") → Given Facts + Applicable Rule with citation + Step-by-step Calculation + Result in ₱ format.
   - Comparison ("compare…", "difference between…") → Comparison Table with attributes, definitions, and legal basis per concept.
   - Procedural ("how to…", "steps to…", "requirements for…") → Overview + Prerequisites + Numbered Step-by-Step Procedure + Deadlines.
   - Strategic ("options…", "risks…", "pros and cons…") → Situation Analysis + Options Matrix table + Risk Assessment + Recommendation.
   - Tutorial ("teach me…", "explain the concept of…") → Definition + Analogy + Deep Dive with cited elements + Illustrative Example using fictional names.
   - Quiz ("quiz me…", "bar question…") → Scenario-based MCQs with Choices, Answer, and Explanation citing [Source N].

4. DOMAIN REGISTER — For legal matters, use standard legal writing conventions with IRAC methodology. For tax matters, use direct English with specific section references and present rates in tables. For accounting matters, use PFRS/IFRS terminology and reference specific standards. For cross-domain queries, lead with the most relevant domain.

5. GROUNDING CONSTRAINT — Base your response strictly on the source documents provided. Do not use your training knowledge to fill gaps. If the sources are insufficient, say so. Do not fabricate cases, statutes, rates, thresholds, deadlines, or standards. You may apply arithmetic, logic, formatting, and hypothetical scenarios to facts cited from the sources, but never invent underlying data.

6. PROFESSIONAL VOICE — Write as a senior practitioner at a professional advisory firm. Present conclusions first, then supporting analysis. Start with substance. Never begin with filler ("Certainly!", "Great question!"). Avoid AI-flagged vocabulary: "delve", "crucial" (as filler), "landscape" (metaphorical), "multifaceted", "foster", "leverage", "pivotal", "unleash", "game-changer", "navigate" (metaphorical). No empty intensifiers ("It is important to note that…"). No speculative gap-filling. Use exact words from the source documents where possible.`;

// ═══════════════════════════════════════════════════════════════
// Singleton Client
// ═══════════════════════════════════════════════════════════════

let client: ConversationalSearchServiceClient | null = null;

function getClient(): ConversationalSearchServiceClient {
    if (!client) {
        const apiEndpoint = CONFIG.location === 'global'
            ? 'discoveryengine.googleapis.com'
            : `${CONFIG.location}-discoveryengine.googleapis.com`;

        client = new ConversationalSearchServiceClient({ apiEndpoint });
    }
    return client;
}

// ═══════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════

export interface UnifiedBadge {
    level: 'GREEN' | 'YELLOW' | 'RED';
    confidence: number;
    message: string;
}

export interface UnifiedCitation {
    id: string;
    sourceNumber: number;
    uri: string;
    title: string;
    snippet: string;
    source: string;
    tier: number;
    domain: 'accounting' | 'legal' | 'tax' | 'general';
    confidence: number;
}

export interface UnifiedResponse {
    content: string;
    citations: UnifiedCitation[];
    badge: UnifiedBadge;
    grounding: {
        supportScore: number;
        groundedClaimCount: number;
        totalClaimCount: number;
        latencyMs: number;
    };
    debug: {
        sessionId: string;
        engine: 'unified-v2';
        searchResultCount: number;
        totalLatencyMs: number;
    };
    // 🆕 New fields from answer method
    relatedQuestions: string[];
    answerSkippedReasons: string[];
}

/** Callback for streaming — called for each chunk of the answer text */
export type StreamChunkCallback = (chunk: {
    /** Incremental answer text (delta only — may be inaccurate if API revises text) */
    answerText: string;
    /** Full accumulated text so far — always authoritative */
    fullText?: string;
    /** Whether this is the final chunk */
    isFinal: boolean;
}) => void;

// ═══════════════════════════════════════════════════════════════
// Helpers: Protobuf struct unwrapping
// ═══════════════════════════════════════════════════════════════

function unwrapValue(value: any): any {
    if (value === null || value === undefined) return null;
    if (value.stringValue !== undefined) return value.stringValue;
    if (value.numberValue !== undefined) return value.numberValue;
    if (value.boolValue !== undefined) return value.boolValue;
    if (value.structValue) return unwrapStruct(value.structValue);
    if (value.listValue?.values) {
        return value.listValue.values.map((v: any) => unwrapValue(v));
    }
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

// ═══════════════════════════════════════════════════════════════
// Shared Request Builder
// ═══════════════════════════════════════════════════════════════

/**
 * Build the AnswerQueryRequest object shared by both sync and streaming calls.
 */
function buildAnswerRequest(query: string, sessionId?: string): any {
    const searchClient = getClient();
    const isNew = !sessionId || sessionId === '-';

    const servingConfig = searchClient.projectLocationCollectionEngineServingConfigPath(
        CONFIG.projectId,
        CONFIG.location,
        CONFIG.collectionId,
        CONFIG.engineId,
        CONFIG.servingConfigId,
    );

    const request: any = {
        servingConfig,

        // The query
        query: { text: query },

        // Visitor tracking
        userPseudoId: 'robsky-user',

        // ─── Phase 1: Query Understanding ───
        // Note: streamAnswer limits maxRephraseSteps to 1
        queryUnderstandingSpec: {
            queryRephraserSpec: {
                disable: false,
                maxRephraseSteps: 1,
            },
            queryClassificationSpec: {
                types: [
                    'ADVERSARIAL_QUERY',
                    'NON_ANSWER_SEEKING_QUERY',
                ],
            },
        },

        // ─── Phase 3: Answer Generation ───
        answerGenerationSpec: {
            ignoreAdversarialQuery: true,
            // DYNAMIC: For first-turn (new session), block non-search queries (greetings,
            // chitchat). For follow-up turns within a session, allow creative/pedagogical
            // queries like "write a bar exam question based on the case digest" which are
            // legitimate conversational follow-ups but classified as "non-answer-seeking".
            // Grounding quality is always enforced by ignoreLowRelevantContent + groundingSpec
            // + the preamble's Rule 5 (GROUNDING CONSTRAINT).
            ignoreNonAnswerSeekingQuery: isNew,
            // GROUNDING CHECK — always active to ensure answers are based on relevant content
            ignoreLowRelevantContent: true,
            modelSpec: {
                modelVersion: 'gemini-2.5-flash/answer_gen/v1',
            },
            promptSpec: {
                preamble: PREAMBLE,
            },
            includeCitations: true,
            answerLanguageCode: 'en',
        },

        // ─── Grounding Quality Filter ───
        groundingSpec: {
            filteringLevel: 'FILTERING_LEVEL_HIGH',
        },

        // ─── Related Questions ───
        relatedQuestionsSpec: {
            enable: true,
        },
    };

    // ── Session management ──
    if (!isNew) {
        request.session = searchClient.projectLocationCollectionEngineSessionsPath(
            CONFIG.projectId,
            CONFIG.location,
            CONFIG.collectionId,
            CONFIG.engineId,
            sessionId,
        );
    }

    return request;
}

// ═══════════════════════════════════════════════════════════════
// Shared Response Parser
// ═══════════════════════════════════════════════════════════════

/**
 * Parse an AnswerQueryResponse into a UnifiedResponse.
 * Used by both sync `answerQuery` and as the final parse for `streamAnswerQuery`.
 */
function parseAnswerResponse(
    response: any,
    fallbackSessionId: string | undefined,
    elapsedMs: number,
): UnifiedResponse {
    // ── Extract session ID for continuity ──
    const returnedSessionId = response.session?.name?.split('/sessions/').pop() || fallbackSessionId || 'unknown';

    // ── Extract answer ──
    const answer = response.answer;
    const answerText = answer?.answerText || '';
    const answerState = answer?.state?.toString() || 'UNKNOWN';
    const answerSkippedReasons: string[] = (answer?.answerSkippedReasons || []).map((r: any) => r.toString());
    const relatedQuestions: string[] = (answer?.relatedQuestions || []).map((q: any) => typeof q === 'string' ? q : q.toString());

    // ── Determine content ──
    // IMPORTANT: If answerText exists, always prefer it — the text was already streamed
    // to the user. Only use fallback messages when the API produced no text at all.
    // Skip reasons still affect the badge (GREEN/YELLOW/RED) but never discard real text.
    let content: string;
    if (answerSkippedReasons.length > 0) {
        console.warn(`[UnifiedEngine] Answer skipped: ${answerSkippedReasons.join(', ')}`);
        if (answerText) {
            // API generated text despite skip reasons — keep it (user already saw it streaming)
            content = answerText;
        } else if (answerSkippedReasons.some(r => r.includes('ADVERSARIAL'))) {
            content = 'I cannot process this query. Please rephrase your question about Philippine law.';
        } else if (answerSkippedReasons.some(r => r.includes('NON_ANSWER_SEEKING'))) {
            content = 'This appears to be a non-research query. Please ask a specific legal question.';
        } else if (answerSkippedReasons.some(r => r.includes('LOW_GROUNDED'))) {
            content = 'I could not find sufficiently grounded information in the legal corpus to answer this question. Try rephrasing with more specific legal terms.';
        } else {
            content = 'I could not find a relevant answer in the legal corpus.';
        }
    } else if (answerState === 'FAILED' || answerState === '3') {
        content = answerText || 'The search query failed. Please try again.';
    } else {
        content = answerText || 'I could not find a relevant answer in the legal corpus.';
    }

    // ── Extract citations from answer steps ──
    const citations: UnifiedCitation[] = [];
    const steps = answer?.steps || [];
    let searchResultCount = 0;

    for (const step of steps) {
        const actions = step.actions || [];
        for (const action of actions) {
            const searchResults = action.observation?.searchResults || [];
            searchResultCount += searchResults.length;

            for (const result of searchResults) {
                const idx = citations.length;
                const docName = result.document || '';

                // Extract chunk content
                let snippet = '';
                const chunkInfos = result.chunkInfo || [];
                if (chunkInfos.length > 0) {
                    snippet = chunkInfos[0]?.content || chunkInfos[0]?.relevanceScore?.toString() || '';
                }
                if (!snippet) {
                    const snippetInfos = result.snippetInfo || [];
                    if (snippetInfos.length > 0) {
                        snippet = snippetInfos[0]?.snippet || '';
                    }
                }

                const uri = result.uri || docName || `doc-${idx}`;
                const title = result.title || 'Unknown Document';

                if (snippet.length > 1500) {
                    snippet = snippet.substring(0, 1500);
                }

                const domainFromUri = uri.includes('elibrary.judiciary') || uri.includes('supreme-court')
                    ? 'legal' as const
                    : uri.includes('accounting') || uri.includes('ifrs')
                        ? 'accounting' as const
                        : uri.includes('tax') || uri.includes('bir') || uri.includes('nirc')
                            ? 'tax' as const
                            : 'legal' as const;

                // Deduplicate by URI
                const existing = citations.find(c => c.uri === uri);
                if (!existing) {
                    citations.push({
                        id: `source_${citations.length + 1}`,
                        sourceNumber: citations.length + 1,
                        uri,
                        title,
                        snippet,
                        source: title || uri.split('/').pop() || 'Source',
                        tier: 1,
                        domain: domainFromUri,
                        confidence: 0.9,
                    });
                }
            }
        }
    }

    // ── Determine badge ──
    let badge: UnifiedBadge;

    if (answerSkippedReasons.length > 0) {
        badge = {
            level: 'RED',
            confidence: 0.1,
            message: `Answer skipped: ${answerSkippedReasons.join(', ')}`,
        };
    } else if (citations.length >= 3) {
        badge = {
            level: 'GREEN',
            confidence: 0.95,
            message: `Grounded: ${citations.length} sources from legal corpus`,
        };
    } else if (citations.length >= 1) {
        badge = {
            level: 'GREEN',
            confidence: 0.85,
            message: `Grounded: ${citations.length} source(s) from legal corpus`,
        };
    } else if (content && content !== 'I could not find a relevant answer in the legal corpus.') {
        badge = {
            level: 'YELLOW',
            confidence: 0.5,
            message: 'AI Summary — no direct citations returned',
        };
    } else {
        badge = {
            level: 'RED',
            confidence: 0.1,
            message: 'No grounding found in legal corpus',
        };
    }

    console.log(`[UnifiedEngine] ${answerState} | ${citations.length} citations | ${relatedQuestions.length} related Qs | ${elapsedMs}ms`);

    return {
        content,
        citations,
        badge,
        grounding: {
            supportScore: badge.confidence,
            groundedClaimCount: citations.length,
            totalClaimCount: citations.length,
            latencyMs: elapsedMs,
        },
        debug: {
            sessionId: returnedSessionId,
            engine: 'unified-v2',
            searchResultCount,
            totalLatencyMs: elapsedMs,
        },
        relatedQuestions,
        answerSkippedReasons,
    };
}

// ═══════════════════════════════════════════════════════════════
// Core Engine: Synchronous
// ═══════════════════════════════════════════════════════════════

/**
 * Query the Vertex AI Search Answer API (synchronous / non-streaming).
 *
 * One API call handles: query understanding, retrieval, generation, grounding, and citations.
 *
 * @param query - The user's question
 * @param sessionId - Optional session ID for multi-turn conversation.
 * @returns UnifiedResponse with content, citations, badge, related questions, and debug telemetry
 */
export async function queryUnifiedEngine(
    query: string,
    sessionId?: string,
): Promise<UnifiedResponse> {
    const startMs = Date.now();
    const isNew = !sessionId || sessionId === '-';

    console.log(`[UnifiedEngine] Query: "${query.substring(0, 100)}..." | Session: ${isNew ? 'NEW' : sessionId}`);

    try {
        const request = buildAnswerRequest(query, sessionId);

        // ── Call the Answer API ──
        const [response] = await getClient().answerQuery(request);

        return parseAnswerResponse(response, sessionId, Date.now() - startMs);

    } catch (error: any) {
        const elapsedMs = Date.now() - startMs;
        console.error(`[UnifiedEngine] Error after ${elapsedMs}ms:`, error.message || error);

        const wrappedError = new Error(
            `[UnifiedEngine] Vertex AI Search failed: ${error.message || 'Unknown error'}`
        );
        (wrappedError as any).cause = error;
        throw wrappedError;
    }
}

// ═══════════════════════════════════════════════════════════════
// Core Engine: Streaming
// ═══════════════════════════════════════════════════════════════

/**
 * Query the Vertex AI Search Answer API with streaming.
 *
 * Uses `streamAnswerQuery` to receive answer text incrementally. Each chunk
 * of the answer is emitted via the `onChunk` callback, enabling real-time
 * SSE streaming to the frontend.
 *
 * The final UnifiedResponse (with citations, badge, related questions) is
 * built from the last chunk which contains the complete response.
 *
 * Limitations (per API docs):
 * - maxRephraseSteps is always 1 (cannot be changed for streaming)
 * - Only Gemini models supported
 *
 * @param query - The user's question
 * @param sessionId - Optional session ID for multi-turn conversation.
 * @param onChunk - Callback invoked for each streaming chunk with partial answer text
 * @returns UnifiedResponse from the final aggregated response
 */
export async function streamQueryUnifiedEngine(
    query: string,
    sessionId?: string,
    onChunk?: StreamChunkCallback,
): Promise<UnifiedResponse> {
    const startMs = Date.now();
    const isNew = !sessionId || sessionId === '-';

    console.log(`[UnifiedEngine:Stream] Query: "${query.substring(0, 100)}..." | Session: ${isNew ? 'NEW' : sessionId}`);

    try {
        const request = buildAnswerRequest(query, sessionId);

        // ── Call the Streaming Answer API ──
        // streamAnswerQuery returns a readable stream of AnswerQueryResponse chunks
        const stream = getClient().streamAnswerQuery(request);

        let lastResponse: any = null;
        let peakStreamedText = '';  // Accumulate text we stream to the user

        // Process stream chunks
        // NOTE: Per official Vertex AI docs, each streaming chunk's answerText
        // contains an INDIVIDUAL sentence fragment — NOT cumulative text.
        // Only the final SUCCEEDED chunk has the complete full text.
        for await (const chunk of stream) {
            lastResponse = chunk;

            const state = chunk.answer?.state?.toString() || '';
            const chunkText = chunk.answer?.answerText || '';

            if (onChunk && chunkText && state === 'STREAMING') {
                // Each streaming chunk is a sentence fragment — pass it through directly
                peakStreamedText += chunkText;  // Accumulate for guard

                onChunk({
                    answerText: chunkText,
                    fullText: peakStreamedText,
                    isFinal: false,
                });
            }
        }

        if (!lastResponse) {
            throw new Error('Stream ended without any response');
        }

        // Signal completion
        if (onChunk) {
            onChunk({
                answerText: '',
                isFinal: true,
            });
        }

        // ── Guard: Restore streamed text if the API replaced it in the final chunk ──
        // Vertex AI may replace the accumulated answer with a fallback message
        // (e.g. "A summary could not be generated...") when grounding is low.
        // Since we already streamed the real text to the user, preserve it.
        const finalText = lastResponse.answer?.answerText || '';
        if (peakStreamedText.length > finalText.length && peakStreamedText.length > 50) {
            console.warn(`[UnifiedEngine:Stream] API replaced streamed text (${peakStreamedText.length} chars) with fallback (${finalText.length} chars). Restoring streamed text.`);
            lastResponse.answer.answerText = peakStreamedText;
        }

        // Parse the final (complete) response
        return parseAnswerResponse(lastResponse, sessionId, Date.now() - startMs);

    } catch (error: any) {
        const elapsedMs = Date.now() - startMs;
        console.error(`[UnifiedEngine:Stream] Error after ${elapsedMs}ms:`, error.message || error);

        const wrappedError = new Error(
            `[UnifiedEngine:Stream] Vertex AI Search streaming failed: ${error.message || 'Unknown error'}`
        );
        (wrappedError as any).cause = error;
        throw wrappedError;
    }
}
```
