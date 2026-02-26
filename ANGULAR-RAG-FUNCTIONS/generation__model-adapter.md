# generation / model-adapter

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `src` |
| **Role** | Model/Types |
| **Bundle** | `generation__model-adapter` |
| **Files** | 1 |
| **Total size** | 16,995 bytes |
| **Generated** | 2026-02-26 14:05 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `generation/model-adapter.ts` (16,995 bytes, Model/Types)

---

## `generation/model-adapter.ts`

| Field | Value |
|-------|-------|
| **Role** | Model/Types |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-20 |
| **Size** | 16,995 bytes |
| **Exports** | `GeminiAdapter`, `ClaudeAdapter`, `ToolDefinition`, `GenerateParams`, `GenerationResult`, `ModelAdapter`, `createModelAdapter`, `FunctionCallHandler` |

```typescript
/**
 * Architecture C — Model Adapter (Strategy + Factory Pattern)
 *
 * Switch models via configuration, not code changes.
 *
 * Phase 1: GeminiAdapter only (matches current Architecture A behavior)
 * Phase 3: ClaudeAdapter added for partner model support
 * Phase 4: Function Calling support (Conversational Intelligence Refactor)
 *
 * Each adapter handles:
 *   - API-specific auth and endpoint formatting
 *   - System prompt format differences (Gemini vs Claude)
 *   - Token usage extraction
 *   - Latency tracking
 *   - Function calling loop with tool execution callbacks
 *   - Thought signature preservation (automatic via full response appending)
 */

import { GoogleGenAI, Type } from '@google/genai';
import type { FunctionDeclaration, Content, Part, FunctionCall } from '@google/genai';
import { env } from '../env';
import { GoogleAuth } from 'google-auth-library';

// ══════════════════════════════════════════════════════════════
// Types
// ══════════════════════════════════════════════════════════════

/**
 * A tool definition that can be registered with the model adapter.
 * Uses Google's FunctionDeclaration schema.
 */
export interface ToolDefinition {
    /** Function declarations for the model to call */
    functionDeclarations: FunctionDeclaration[];
}

/**
 * Callback type for executing function calls from the model.
 * The adapter invokes this when the model emits a functionCall.
 * Returns a JSON-serializable result to send back to the model.
 */
export type FunctionCallHandler = (
    name: string,
    args: Record<string, any>,
) => Promise<Record<string, any>>;

export interface GenerateParams {
    systemInstruction: string;
    userMessage: string;
    maxTokens?: number;
    temperature?: number;
    stream?: boolean;
    onChunk?: (chunk: string) => void;
    /** Optional tools the model can call (Phase 4 — Function Calling) */
    tools?: ToolDefinition[];
    /** Handler invoked when the model emits a function_call.
     *  If tools are provided but no handler, function calls are logged and ignored. */
    onFunctionCall?: FunctionCallHandler;
    /** Maximum function calling rounds to prevent infinite loops (default: 5) */
    maxToolRounds?: number;
}

export interface GenerationResult {
    content: string;
    tokenUsage: { inputTokens: number; outputTokens: number };
    latencyMs: number;
    modelId: string;
    /** Function calls made during generation (for observability) */
    functionCallsMade?: Array<{ name: string; args: Record<string, any> }>;
}

export interface ModelAdapter {
    readonly provider: 'google' | 'anthropic' | 'meta' | 'mistral';
    readonly modelId: string;
    generate(params: GenerateParams): Promise<GenerationResult>;
}

// ══════════════════════════════════════════════════════════════
// Gemini Adapter (Google-native via @google/genai)
// ══════════════════════════════════════════════════════════════

let _geminiClient: GoogleGenAI | null = null;

function getGeminiClient(): GoogleGenAI {
    if (!_geminiClient) {
        // Use Vertex AI mode (server-side, ADC auth)
        _geminiClient = new GoogleGenAI({
            vertexai: true,
            project: env.GOOGLE_PROJECT_ID,
            location: env.VERTEX_AI_SEARCH_LOCATION === 'global' ? 'us-central1' : env.VERTEX_AI_SEARCH_LOCATION,
        });
    }
    return _geminiClient;
}

export class GeminiAdapter implements ModelAdapter {
    readonly provider = 'google' as const;

    constructor(readonly modelId: string = 'gemini-2.5-flash') { }

    async generate(params: GenerateParams): Promise<GenerationResult> {
        const client = getGeminiClient();
        const start = Date.now();

        // Streaming with function calling is not yet supported — fall back to sync
        if (params.stream && params.onChunk && !params.tools?.length) {
            return this.generateStream(client, params, start);
        }

        // Build config with optional tools
        const config: any = {
            systemInstruction: params.systemInstruction,
            temperature: params.temperature ?? 0.2,
            maxOutputTokens: params.maxTokens ?? 4096,
        };

        if (params.tools?.length) {
            config.tools = params.tools;
        }

        // Initial request
        let response = await client.models.generateContent({
            model: this.modelId,
            contents: params.userMessage,
            config,
        });

        // ── Function Calling Loop ──
        // If the model emits functionCall(s), execute them and send results back.
        // Thought signatures are preserved automatically by appending the full model
        // response (including any thought_signature fields in parts) to the contents.
        const functionCallsMade: Array<{ name: string; args: Record<string, any> }> = [];
        const maxRounds = params.maxToolRounds ?? 5;
        let round = 0;

        while (response.functionCalls && response.functionCalls.length > 0 && round < maxRounds) {
            round++;
            const functionCall = response.functionCalls[0];
            const fcName = functionCall.name || 'unknown';
            const fcArgs = (functionCall.args as Record<string, any>) || {};

            console.log(`[ModelAdapter] Function call #${round}: ${fcName}(${JSON.stringify(fcArgs).substring(0, 200)})`);
            functionCallsMade.push({ name: fcName, args: fcArgs });

            // Execute the function via callback
            let functionResult: Record<string, any>;
            if (params.onFunctionCall) {
                try {
                    functionResult = await params.onFunctionCall(fcName, fcArgs);
                } catch (err) {
                    console.error(`[ModelAdapter] Function ${fcName} execution failed:`, err);
                    functionResult = { error: (err as Error).message };
                }
            } else {
                console.warn(`[ModelAdapter] No onFunctionCall handler — returning empty result for ${fcName}`);
                functionResult = { error: 'No handler registered for this function' };
            }

            console.log(`[ModelAdapter] Function result: ${JSON.stringify(functionResult).substring(0, 300)}`);

            // Build multi-turn contents with the model's response (preserving thought signatures)
            // and the function execution result
            const contents: Content[] = [
                { role: 'user', parts: [{ text: params.userMessage }] },
                // Append the FULL model response (includes thought_signature in parts)
                response.candidates![0].content!,
                // Append function result as user turn
                {
                    role: 'user',
                    parts: [{
                        functionResponse: {
                            name: fcName,
                            response: functionResult,
                        },
                    }],
                },
            ];

            // Continue generation with function result
            response = await client.models.generateContent({
                model: this.modelId,
                contents,
                config,
            });
        }

        if (round >= maxRounds) {
            console.warn(`[ModelAdapter] Hit max function calling rounds (${maxRounds}). Returning last response.`);
        }

        // Stream the final text response if streaming was requested
        if (params.stream && params.onChunk && response.text) {
            params.onChunk(response.text);
        }

        return {
            content: response.text || '',
            tokenUsage: {
                inputTokens: response.usageMetadata?.promptTokenCount ?? 0,
                outputTokens: response.usageMetadata?.candidatesTokenCount ?? 0,
            },
            latencyMs: Date.now() - start,
            modelId: this.modelId,
            functionCallsMade: functionCallsMade.length > 0 ? functionCallsMade : undefined,
        };
    }

    private async generateStream(
        client: GoogleGenAI,
        params: GenerateParams,
        startMs: number
    ): Promise<GenerationResult> {
        const response = await client.models.generateContentStream({
            model: this.modelId,
            contents: params.userMessage,
            config: {
                systemInstruction: params.systemInstruction,
                temperature: params.temperature ?? 0.2,
                maxOutputTokens: params.maxTokens ?? 4096,
            },
        });

        let fullText = '';
        let inputTokens = 0;
        let outputTokens = 0;

        for await (const chunk of response) {
            const text = chunk.text || '';
            if (text && params.onChunk) {
                params.onChunk(text);
            }
            fullText += text;

            // Capture token usage from last chunk
            if (chunk.usageMetadata) {
                inputTokens = chunk.usageMetadata.promptTokenCount ?? inputTokens;
                outputTokens = chunk.usageMetadata.candidatesTokenCount ?? outputTokens;
            }
        }

        return {
            content: fullText,
            tokenUsage: { inputTokens, outputTokens },
            latencyMs: Date.now() - startMs,
            modelId: this.modelId,
        };
    }
}

// ══════════════════════════════════════════════════════════════
// Claude Adapter (Anthropic Partner Model on Vertex AI)
// ══════════════════════════════════════════════════════════════

let _googleAuth: GoogleAuth | null = null;

async function getAccessToken(): Promise<string> {
    if (!_googleAuth) {
        _googleAuth = new GoogleAuth({
            scopes: 'https://www.googleapis.com/auth/cloud-platform',
        });
    }
    const client = await _googleAuth.getClient();
    const token = await client.getAccessToken();
    return token.token || '';
}

export class ClaudeAdapter implements ModelAdapter {
    readonly provider = 'anthropic' as const;

    constructor(readonly modelId: string = 'claude-opus-4-6') { }

    async generate(params: GenerateParams): Promise<GenerationResult> {
        const start = Date.now();
        const accessToken = await getAccessToken();
        const region = env.CLAUDE_REGION || 'us-east5';

        const isStreaming = params.stream && params.onChunk;

        // streamRawPredict for streaming, rawPredict for sync
        const method = isStreaming ? 'streamRawPredict' : 'rawPredict';
        const endpoint = `https://${region}-aiplatform.googleapis.com/v1/projects/${env.GOOGLE_PROJECT_ID}/locations/${region}/publishers/anthropic/models/${this.modelId}:${method}`;

        const body: any = {
            anthropic_version: 'vertex-2023-10-16',
            max_tokens: params.maxTokens ?? 4096,
            system: params.systemInstruction,
            messages: [{
                role: 'user',
                content: params.userMessage,
            }],
            stream: !!isStreaming,
        };

        if (params.temperature !== undefined) {
            body.temperature = params.temperature;
        }

        const response = await fetch(endpoint, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${accessToken}`,
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(body),
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`Claude API error ${response.status}: ${errorText.substring(0, 500)}`);
        }

        if (isStreaming) {
            return this.parseStreamResponse(response, params.onChunk!, start);
        }

        const data: any = await response.json();

        return {
            content: data.content?.[0]?.text || '',
            tokenUsage: {
                inputTokens: data.usage?.input_tokens ?? 0,
                outputTokens: data.usage?.output_tokens ?? 0,
            },
            latencyMs: Date.now() - start,
            modelId: this.modelId,
        };
    }

    /**
     * Parse Claude SSE stream response.
     * Claude streams SSE events in the format:
     *   event: content_block_delta
     *   data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"..."}}
     */
    private async parseStreamResponse(
        response: Response,
        onChunk: (chunk: string) => void,
        startMs: number,
    ): Promise<GenerationResult> {
        let fullText = '';
        let inputTokens = 0;
        let outputTokens = 0;

        const reader = response.body?.getReader();
        if (!reader) {
            throw new Error('Claude streaming response has no body');
        }

        const decoder = new TextDecoder();
        let buffer = '';

        try {
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });

                // Process complete SSE lines
                const lines = buffer.split('\n');
                buffer = lines.pop() || ''; // Keep incomplete last line in buffer

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const jsonStr = line.substring(6).trim();
                        if (jsonStr === '[DONE]') continue;

                        try {
                            const event: any = JSON.parse(jsonStr);

                            if (event.type === 'content_block_delta' && event.delta?.type === 'text_delta') {
                                const text = event.delta.text || '';
                                if (text) {
                                    onChunk(text);
                                    fullText += text;
                                }
                            } else if (event.type === 'message_delta' && event.usage) {
                                outputTokens = event.usage.output_tokens ?? outputTokens;
                            } else if (event.type === 'message_start' && event.message?.usage) {
                                inputTokens = event.message.usage.input_tokens ?? inputTokens;
                            }
                        } catch {
                            // Skip malformed JSON lines
                        }
                    }
                }
            }
        } finally {
            reader.releaseLock();
        }

        return {
            content: fullText,
            tokenUsage: { inputTokens, outputTokens },
            latencyMs: Date.now() - startMs,
            modelId: this.modelId,
        };
    }
}

// ══════════════════════════════════════════════════════════════
// Model Factory
// ══════════════════════════════════════════════════════════════

/**
 * Create a model adapter based on the model ID.
 * Uses naming convention to determine provider.
 */
export function createModelAdapter(modelId: string): ModelAdapter {
    if (modelId.startsWith('claude-')) {
        return new ClaudeAdapter(modelId);
    }
    if (modelId.startsWith('gemini-')) {
        return new GeminiAdapter(modelId);
    }

    // Add more providers as needed:
    // if (modelId.startsWith('mistral-')) return new MistralAdapter(modelId);
    // if (modelId.startsWith('llama-')) return new LlamaAdapter(modelId);

    // Default to Gemini for unknown models
    console.warn(`[ModelAdapter] Unknown model "${modelId}", defaulting to GeminiAdapter`);
    return new GeminiAdapter(modelId);
}
```
