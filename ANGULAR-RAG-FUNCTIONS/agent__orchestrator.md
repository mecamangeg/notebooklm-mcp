# agent / orchestrator

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `src` |
| **Role** | Source |
| **Bundle** | `agent__orchestrator` |
| **Files** | 1 |
| **Total size** | 18,434 bytes |
| **Generated** | 2026-02-26 14:05 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `agent/orchestrator.ts` (18,434 bytes, Source)

---

## `agent/orchestrator.ts`

| Field | Value |
|-------|-------|
| **Role** | Source |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-20 |
| **Size** | 18,434 bytes |
| **Exports** | `OrchestratorInput`, `StreamCallbacks`, `runPipeline`, `runPipelineStreaming` |

```typescript
/**
 * Architecture C — Pipeline Orchestrator (Conversational Intelligence Refactor)
 *
 * Central coordinator that runs the decoupled pipeline:
 *
 *   1. CLASSIFY  → Intent + Domain + Tone (classifier.ts)
 *   2. RETRIEVE  → Search-only documents (search-retriever.ts)
 *   3. ASSEMBLE  → Unified persona prompt (prompt-assembler.ts)
 *   4. GENERATE  → Any model via adapter (model-adapter.ts)
 *   5. VALIDATE  → Check Grounding API (check-grounding.ts)
 *   6. FORMAT    → Badge + citations (response-formatter.ts)
 *
 * Supports both sync and streaming modes.
 *
 * Key design principles:
 *   - CLASSIFY + RETRIEVE run in parallel (they're independent)
 *   - ALL intents go through generation (no fast-lane bypasses)
 *   - Conversation history injected universally for persona continuity
 *   - Ungrounded responses (< 0.3) get a strict re-prompt
 *   - Empty retrieval returns a clear no-results message
 *
 * Phase 4 (Function Calling) additions:
 *   - Optional tool registration via enableToolCalling flag
 *   - When enabled, the model can call vertexSearch organically during generation
 *   - Current pipeline remains explicit (CLASSIFY → RETRIEVE → GENERATE)
 *   - Tools provide a supplemental retrieval channel, not a replacement
 */

import { classifyQuery, type QueryIntent } from './classifier';
import { retrieveDocuments, type RetrievedDocument } from '../retrieval/search-retriever';
import { assemblePrompt, type ConversationTurn } from './prompt-assembler';
import { selectModel, getTemperatureForIntent, getPageSizeForIntent } from '../generation/model-config';
import { createModelAdapter } from '../generation/model-adapter';
import { checkGrounding, isGroundingEnabled } from '../validation/check-grounding';
import { formatResponse, type FormattedResponse } from './response-formatter';
import { STRICT_GROUNDING_ADDENDUM } from './prompt-templates';
import { getToolDefinitions, createFunctionCallHandler } from './tool-registry';
import { env } from '../env';

// ══════════════════════════════════════════════════════════════
// Types
// ══════════════════════════════════════════════════════════════

export interface OrchestratorInput {
    query: string;
    conversationHistory?: ConversationTurn[];
    hasHistory: boolean;
    /** Override model selection */
    modelOverride?: string;
    /** Enable/disable grounding check for this request */
    enableGrounding?: boolean;
    /** Enable function calling — model can invoke tools like vertexSearch organically */
    enableToolCalling?: boolean;
}

export interface StreamCallbacks {
    onPhase?: (phase: { type: string; label: string; phaseIndex: number; totalPhases: number }) => void;
    onChunk?: (chunk: string) => void;
    onMeta?: (meta: { searchResultCount: number; citationCount: number; intent: string; domain: string }) => void;
}

// Threshold below which we retry with a strict grounding prompt
const STRICT_GROUNDING_RETRY_THRESHOLD = 0.3;

/** Resolve tool calling enablement: per-request flag → env var → default (false) */
function isToolCallingEnabled(inputFlag?: boolean): boolean {
    if (inputFlag !== undefined) return inputFlag;
    return env.ENABLE_TOOL_CALLING === 'true';
}

/** Get max tool calling rounds from env (default: 5) */
function getMaxToolRounds(): number {
    const parsed = parseInt(env.MAX_TOOL_ROUNDS, 10);
    return isNaN(parsed) ? 5 : Math.max(1, Math.min(parsed, 20));
}

// ══════════════════════════════════════════════════════════════
// (LOOKUP Fast Lane Removed — all intents now go through generation)
// (Phase 4: Tool calling available via enableToolCalling flag)
// ══════════════════════════════════════════════════════════════

// ══════════════════════════════════════════════════════════════
// No-Results Fallback
// ══════════════════════════════════════════════════════════════

function buildNoResultsResponse(
    query: string,
    intent: string,
    domain: string,
    classifierLatencyMs: number,
    retrievalLatencyMs: number,
    totalStartMs: number,
): FormattedResponse {
    return {
        content: 'I could not find any relevant documents in the legal corpus to answer this question. Try rephrasing with more specific legal terms, case names, or statutory references.',
        badge: { level: 'RED', confidence: 0.0, label: 'No sources found' },
        citations: [],
        grounding: {
            supportScore: 0,
            groundedClaimCount: 0,
            totalClaimCount: 0,
            latencyMs: 0,
        },
        debug: {
            engine: 'architecture-c-v2',
            intent,
            domain,
            model: 'none (no results)',
            pipelineVersion: 'v2',
            searchResultCount: 0,
            classifierLatencyMs,
            retrievalLatencyMs,
            generationLatencyMs: 0,
            groundingLatencyMs: 0,
            totalLatencyMs: Date.now() - totalStartMs,
        },
        relatedQuestions: [],
    };
}

// ══════════════════════════════════════════════════════════════
// Pipeline Orchestrator (Sync)
// ══════════════════════════════════════════════════════════════

/**
 * Run the Architecture C pipeline (sync mode).
 * Returns a fully formatted response with grounding validation.
 */
export async function runPipeline(input: OrchestratorInput): Promise<FormattedResponse> {
    const totalStartMs = Date.now();

    // ── Phase 1: CLASSIFY + RETRIEVE (parallel) ──
    // Classification and initial retrieval are independent — run concurrently
    const classifyPromise = classifyQuery(input.query, input.hasHistory);
    const initialRetrievalPromise = retrieveDocuments(input.query, { pageSize: 10 });

    const classification = await classifyPromise;
    console.log(`[Orchestrator] Classified: ${classification.intent}/${classification.domain} (${classification.source}, ${classification.latencyMs}ms)`);

    // (LOOKUP fast-lane removed — all intents go through RETRIEVE → ASSEMBLE → GENERATE → FORMAT)

    // ── Phase 2: RETRIEVE (with domain filter if classification provides it) ──
    const retrievalStartMs = Date.now();
    const pageSize = getPageSizeForIntent(classification.intent);

    // If domain differs from default, do a domain-filtered retrieval; otherwise use initial result
    let retrievedDocs: RetrievedDocument[];
    if (classification.domain !== 'MIXED' || pageSize !== 10) {
        // Re-retrieve with domain filter and correct page size
        retrievedDocs = await retrieveDocuments(input.query, {
            domain: classification.domain,
            pageSize,
        });
    } else {
        // Use the parallel initial retrieval
        retrievedDocs = await initialRetrievalPromise;
    }
    const retrievalLatencyMs = Date.now() - retrievalStartMs;
    console.log(`[Orchestrator] Retrieved: ${retrievedDocs.length} docs (${retrievalLatencyMs}ms)`);

    // ── No results? ──
    if (retrievedDocs.length === 0) {
        return buildNoResultsResponse(input.query, classification.intent, classification.domain, classification.latencyMs, retrievalLatencyMs, totalStartMs);
    }

    // ── Phase 3: ASSEMBLE ──
    const { systemInstruction, userMessage } = assemblePrompt({
        intent: classification.intent,
        domain: classification.domain,
        tone: classification.tone,
        query: input.query,
        retrievedDocs,
        conversationHistory: input.conversationHistory,
    });

    // ── Phase 4: GENERATE ──
    const modelId = input.modelOverride || selectModel(classification.intent, classification.domain);
    const adapter = createModelAdapter(modelId);
    const temperature = getTemperatureForIntent(classification.intent);

    // Resolve tool calling: per-request flag → env var → false
    const toolCallingEnabled = isToolCallingEnabled(input.enableToolCalling);
    if (toolCallingEnabled) {
        console.log(`[Orchestrator] Tool calling ENABLED for this request (maxRounds=${getMaxToolRounds()})`);
    }

    let generationResult = await adapter.generate({
        systemInstruction,
        userMessage,
        temperature,
        maxTokens: 4096,
        // Phase 4: Wire tools for organic retrieval when enabled
        ...(toolCallingEnabled ? {
            tools: getToolDefinitions(),
            onFunctionCall: createFunctionCallHandler(),
            maxToolRounds: getMaxToolRounds(),
        } : {}),
    });

    // Observability: log function calls made during generation
    if (generationResult.functionCallsMade?.length) {
        console.log(`[Orchestrator] Model made ${generationResult.functionCallsMade.length} organic tool call(s): ${generationResult.functionCallsMade.map(fc => fc.name).join(', ')}`);
    }
    console.log(`[Orchestrator] Generated: ${generationResult.content.length} chars via ${modelId} (${generationResult.latencyMs}ms)`);

    // ── Phase 5: VALIDATE (optional) ──
    let groundingResult = null;
    const shouldCheckGrounding = (input.enableGrounding ?? isGroundingEnabled())
        && classification.intent !== 'CONVERSATIONAL'
        && retrievedDocs.length > 0;

    if (shouldCheckGrounding) {
        const facts = retrievedDocs.map(d => d.content);
        groundingResult = await checkGrounding(generationResult.content, facts);

        // ── Strict re-prompt if critically ungrounded ──
        if (groundingResult.supportScore >= 0 && groundingResult.supportScore < STRICT_GROUNDING_RETRY_THRESHOLD) {
            console.warn(`[Orchestrator] Low grounding (${groundingResult.supportScore.toFixed(2)}) — retrying with strict prompt`);
            const strictResult = await adapter.generate({
                systemInstruction: systemInstruction + STRICT_GROUNDING_ADDENDUM,
                userMessage,
                temperature: 0.0, // Zero temperature for maximum fidelity
                maxTokens: 4096,
            });
            // Re-validate the strict result
            groundingResult = await checkGrounding(strictResult.content, facts);
            generationResult = {
                ...strictResult,
                latencyMs: generationResult.latencyMs + strictResult.latencyMs,
            };
            console.log(`[Orchestrator] Strict re-prompt grounding: ${groundingResult.supportScore.toFixed(2)}`);
        }
    }

    // ── Phase 6: FORMAT ──
    return formatResponse({
        generationResult,
        groundingResult,
        retrievedDocs,
        intent: classification.intent,
        domain: classification.domain,
        classifierLatencyMs: classification.latencyMs,
        retrievalLatencyMs,
        totalStartMs,
    });
}

// ══════════════════════════════════════════════════════════════
// Pipeline Orchestrator (Streaming)
// ══════════════════════════════════════════════════════════════

/**
 * Run the Architecture C pipeline with SSE streaming.
 * Emits phase events and text chunks as they arrive.
 */
export async function runPipelineStreaming(
    input: OrchestratorInput,
    callbacks: StreamCallbacks,
): Promise<FormattedResponse> {
    const totalStartMs = Date.now();
    const groundingEnabled = input.enableGrounding ?? isGroundingEnabled();
    const totalPhases = groundingEnabled ? 4 : 3;

    // ── Phase 1: CLASSIFY + RETRIEVE (parallel) ──
    callbacks.onPhase?.({
        type: 'searching',
        label: 'Searching sources...',
        phaseIndex: 1,
        totalPhases,
    });

    // Run classify and initial retrieval concurrently
    const classifyPromise = classifyQuery(input.query, input.hasHistory);
    const initialRetrievalPromise = retrieveDocuments(input.query, { pageSize: 10 });

    const classification = await classifyPromise;
    console.log(`[Orchestrator] Classified: ${classification.intent}/${classification.domain} (${classification.source}, ${classification.latencyMs}ms)`);

    // (LOOKUP fast-lane removed — all intents go through RETRIEVE → ASSEMBLE → GENERATE → FORMAT)

    // Resolve retrieval with domain filter
    const retrievalStartMs = Date.now();
    const pageSize = getPageSizeForIntent(classification.intent);

    let retrievedDocs: RetrievedDocument[];
    if (classification.domain !== 'MIXED' || pageSize !== 10) {
        retrievedDocs = await retrieveDocuments(input.query, {
            domain: classification.domain,
            pageSize,
        });
    } else {
        retrievedDocs = await initialRetrievalPromise;
    }
    const retrievalLatencyMs = Date.now() - retrievalStartMs;
    console.log(`[Orchestrator] Retrieved: ${retrievedDocs.length} docs (${retrievalLatencyMs}ms)`);

    // Emit metadata early
    callbacks.onMeta?.({
        searchResultCount: retrievedDocs.length,
        citationCount: 0,
        intent: classification.intent,
        domain: classification.domain,
    });

    // ── No results? ──
    if (retrievedDocs.length === 0) {
        const noResults = buildNoResultsResponse(input.query, classification.intent, classification.domain, classification.latencyMs, retrievalLatencyMs, totalStartMs);
        callbacks.onChunk?.(noResults.content);
        return noResults;
    }

    // ── Phase 2: GENERATE (with streaming) ──
    callbacks.onPhase?.({
        type: 'synthesizing',
        label: 'Generating response...',
        phaseIndex: 2,
        totalPhases,
    });

    const { systemInstruction, userMessage } = assemblePrompt({
        intent: classification.intent,
        domain: classification.domain,
        tone: classification.tone,
        query: input.query,
        retrievedDocs,
        conversationHistory: input.conversationHistory,
    });

    const modelId = input.modelOverride || selectModel(classification.intent, classification.domain);
    const adapter = createModelAdapter(modelId);
    const temperature = getTemperatureForIntent(classification.intent);

    // Resolve tool calling: per-request flag → env var → false
    const toolCallingEnabled = isToolCallingEnabled(input.enableToolCalling);
    if (toolCallingEnabled) {
        console.log(`[Orchestrator:Stream] Tool calling ENABLED (maxRounds=${getMaxToolRounds()}). Note: streaming falls back to sync for function calling rounds.`);
    }

    let generationResult = await adapter.generate({
        systemInstruction,
        userMessage,
        temperature,
        maxTokens: 4096,
        stream: true,
        onChunk: callbacks.onChunk,
        // Phase 4: Wire tools for organic retrieval when enabled
        // Note: streaming + tools falls back to sync in the adapter,
        // then emits the final text as a single chunk
        ...(toolCallingEnabled ? {
            tools: getToolDefinitions(),
            onFunctionCall: createFunctionCallHandler(),
            maxToolRounds: getMaxToolRounds(),
        } : {}),
    });

    // Observability: log function calls made during generation
    if (generationResult.functionCallsMade?.length) {
        console.log(`[Orchestrator:Stream] Model made ${generationResult.functionCallsMade.length} organic tool call(s): ${generationResult.functionCallsMade.map(fc => fc.name).join(', ')}`);
    }
    console.log(`[Orchestrator] Generated: ${generationResult.content.length} chars via ${modelId} (${generationResult.latencyMs}ms)`);

    // ── Phase 3: VALIDATE (optional) ──
    let groundingResult = null;
    const shouldCheckGrounding = groundingEnabled
        && classification.intent !== 'CONVERSATIONAL'
        && retrievedDocs.length > 0;

    if (shouldCheckGrounding) {
        callbacks.onPhase?.({
            type: 'analyzing',
            label: 'Verifying grounding...',
            phaseIndex: 3,
            totalPhases,
        });

        const facts = retrievedDocs.map(d => d.content);
        groundingResult = await checkGrounding(generationResult.content, facts);

        // Strict re-prompt if critically ungrounded
        // Note: In streaming mode, user already saw the first response.
        // We log but do NOT regenerate for streaming — the badge will reflect the score.
        if (groundingResult.supportScore >= 0 && groundingResult.supportScore < STRICT_GROUNDING_RETRY_THRESHOLD) {
            console.warn(
                `[Orchestrator] Low grounding (${groundingResult.supportScore.toFixed(2)}) — ` +
                `streaming mode: badge will reflect low confidence. Retry available in sync mode.`
            );
        }
    }

    // ── Phase 4: FORMAT ──
    return formatResponse({
        generationResult,
        groundingResult,
        retrievedDocs,
        intent: classification.intent,
        domain: classification.domain,
        classifierLatencyMs: classification.latencyMs,
        retrievalLatencyMs,
        totalStartMs,
    });
}
```
