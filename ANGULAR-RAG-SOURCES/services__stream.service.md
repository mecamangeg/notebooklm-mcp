# stream.service

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `robsky-angular` |
| **Role** | Source |
| **Bundle** | `services__stream.service` |
| **Files** | 1 |
| **Total size** | 9,807 bytes |
| **Generated** | 2026-02-26 11:08 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `app/services/stream.service.ts` (9,807 bytes, Service)

---

## `app/services/stream.service.ts`

| Field | Value |
|-------|-------|
| **Role** | Service |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-26 |
| **Size** | 9,807 bytes |
| **Exports** | `StreamService`, `StreamEvent`, `StreamPhase` |

```typescript
import { Injectable, inject, signal, computed } from '@angular/core';
import { Auth } from '@angular/fire/auth';
import { environment } from '../../environments/environment';

/**
 * SSE event types for the research streaming phase.
 *
 * StreamService is now wired to the live /streamChat Firebase Function (B1 / B4 fix).
 * The /streamChat endpoint uses Agent Engine async_stream_query() to stream ADK events
 * as SSE frames. This service maps those frames to Angular signal state transitions.
 */
export interface StreamEvent {
    type:
    | 'research_start'
    | 'evidence_found'
    | 'synthesis_start'
    | 'response_chunk'
    | 'response_done'
    | 'error';
    message?: string;
    sources?: Array<{ title: string; docket?: string; snippet?: string }>;
    text?: string;
    tool_results?: unknown[];
}

/**
 * Streaming research phase visible to the UI.
 * Maps 1:1 to the SSE event lifecycle.
 */
export type StreamPhase =
    | 'idle'
    | 'researching'
    | 'synthesizing'
    | 'done'
    | 'error';

/**
 * StreamService — Angular SSE client for the backend /stream endpoint.
 *
 * Runs in parallel with ChatService: StreamService manages the live research
 * phase indicator (sources panel, spinner) while ChatService manages the
 * full message thread and session persistence.
 *
 * Note: POST-based SSE requires fetch + ReadableStream.
 * Native EventSource only supports GET — not usable with body payloads.
 *
 * Angular MCP compliance:
 * - ChangeDetectionStrategy.OnPush compatible: all state is signals
 * - inject() for DI — no constructor injection
 * - computed() for derived state
 * - No ngOnDestroy needed: AbortController cancels the fetch
 */
@Injectable({ providedIn: 'root' })
export class StreamService {
    private readonly auth = inject(Auth);

    // ── Reactive state (signals for OnPush compatibility) ──────────────────
    readonly streamPhase = signal<StreamPhase>('idle');
    readonly evidenceSources = signal<Array<{ title: string; docket?: string; snippet?: string }>>([]);
    readonly researchMessage = signal<string>('');
    readonly errorMessage = signal<string>('');
    /** Item 3: exposes the live query arg from each tool_call ADK event.
     * Used by ResearchIndicatorComponent to show e.g. Searching: "estafa Article 315…" */
    readonly activeSearchQuery = signal<string>('');

    /** True while research or synthesis is in progress */
    readonly isStreaming = computed(() => {
        const p = this.streamPhase();
        return p === 'researching' || p === 'synthesizing';
    });

    /** True when evidence sources have been received */
    readonly hasEvidence = computed(() => this.evidenceSources().length > 0);

    private _abortController: AbortController | null = null;

    /**
     * Fire a streaming query to the backend /stream endpoint.
     * Emits phase updates and evidence sources in real-time.
     *
     * Note: This service is for phase indicator UI only.
     * The final response text is handled by ChatService.
     *
     * @param query     User's question
     * @param userId    Firebase UID
     * @param sessionId Optional ADK session ID for multi-turn continuity
     */
    async streamQuery(query: string, userId: string, sessionId?: string): Promise<void> {
        // Cancel any in-flight request
        this._abortController?.abort();
        this._abortController = new AbortController();

        this.streamPhase.set('researching');
        this.evidenceSources.set([]);
        this.researchMessage.set('Starting research...');
        this.errorMessage.set('');

        // ── B4 fix: Live /streamChat SSE endpoint (async_stream_query bridge) ───
        // This replaces the no-op stub. The /streamChat Cloud Function wraps
        // Agent Engine async_stream_query() and streams ADK events as SSE.
        const url = `${environment.functionsUrl}/streamChat`;

        try {
            const idToken = await this.auth.currentUser?.getIdToken();
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...(idToken ? { 'Authorization': `Bearer ${idToken}` } : {}),
                },
                body: JSON.stringify({ query, userId, sessionId }),
                signal: this._abortController.signal,
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const reader = response.body!.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) {
                    this.streamPhase.set('done');
                    break;
                }
                buffer += decoder.decode(value, { stream: true });

                // SSE events are separated by double newlines
                const lines = buffer.split('\n\n');
                buffer = lines.pop() ?? '';

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const event = JSON.parse(line.slice(6)) as Record<string, unknown>;
                            this._handleADKEvent(event);
                        } catch {
                            // Ignore malformed SSE frames
                        }
                    }
                }
            }
        } catch (err: unknown) {
            if ((err as Error).name === 'AbortError') {
                // Cancelled intentionally — not an error
                return;
            }
            this.errorMessage.set(String(err));
            this.streamPhase.set('error');
        }
    }

    /** Cancel any in-flight streaming request */
    cancel(): void {
        this._abortController?.abort();
        this._abortController = null;
    }

    /** Reset all state to idle */
    reset(): void {
        this.cancel();
        this.streamPhase.set('idle');
        this.evidenceSources.set([]);
        this.researchMessage.set('');
        this.errorMessage.set('');
        this.activeSearchQuery.set('');
    }

    /** Map ADK event types (from async_stream_query) to StreamPhase signal transitions.
     *
     * ADK events from the backend:
     *   tool_call       → researching (Researcher is calling a search tool)
     *   evidence_found  → researching (tool function_response returned)
     *   response_chunk  → synthesizing (Partner or Researcher emitting text)
     *   response_done   → done        (terminal sentinel from async_stream_query)
     */
    private _handleADKEvent(event: Record<string, unknown>): void {
        const type = event['type'] as string;
        const author = event['author'] as string;

        switch (type) {
            case 'tool_call': {
                this.streamPhase.set('researching');
                // Item 3: extract query arg from function_call payload
                // Supports both search_legal_corpus (uses 'query') and
                // traverse_citation_graph (uses 'case_name') — Plan §5
                const fc = (event['function_call'] as Record<string, unknown> | undefined);
                const args = (fc?.['args'] as Record<string, unknown> | undefined);
                const toolName = fc?.['name'] as string | undefined;
                const isGraphTraversal = toolName === 'traverse_citation_graph';

                // Prefer 'query', fall back to 'case_name' for graph traversal
                const toolQuery = (args?.['query'] ?? args?.['case_name']) as string | undefined;

                if (typeof toolQuery === 'string' && toolQuery.trim()) {
                    const preview = toolQuery.trim();
                    this.activeSearchQuery.set(preview);
                    const label = isGraphTraversal
                        ? `Traversing citation graph: "${preview.slice(0, 50)}${preview.length > 50 ? '\u2026' : ''}"`
                        : `Searching: "${preview.slice(0, 60)}${preview.length > 60 ? '\u2026' : ''}"`;
                    this.researchMessage.set(label);
                } else {
                    this.activeSearchQuery.set('');
                    this.researchMessage.set(
                        isGraphTraversal ? 'Traversing citation graph...' : 'Searching legal corpus...'
                    );
                }
                break;
            }
            case 'evidence_found':
                this.streamPhase.set('researching');
                this.researchMessage.set('Analysing sources...');
                break;
            case 'response_chunk':
                if (author === 'robsky_partner' || author === 'robsky_researcher') {
                    this.streamPhase.set('synthesizing');
                    this.researchMessage.set('Drafting advisory...');
                    // Text chunks are handled by ChatService — StreamService only tracks phase
                }
                break;
            case 'response_done':
                this.streamPhase.set('done');
                break;
            default:
                break;
        }
    }

    private _handleEvent(event: StreamEvent): void {
        switch (event.type) {
            case 'research_start':
                this.streamPhase.set('researching');
                this.researchMessage.set(event.message ?? 'Researching sources...');
                break;
            case 'evidence_found':
                this.evidenceSources.set(event.sources ?? []);
                break;
            case 'synthesis_start':
                this.streamPhase.set('synthesizing');
                this.researchMessage.set(event.message ?? 'Drafting advisory...');
                break;
            case 'response_chunk':
                // Text chunks are handled by ChatService — StreamService only tracks phase
                break;
            case 'response_done':
                this.streamPhase.set('done');
                break;
            case 'error':
                this.errorMessage.set(event.message ?? 'Unknown error');
                this.streamPhase.set('error');
                break;
        }
    }
}
```
