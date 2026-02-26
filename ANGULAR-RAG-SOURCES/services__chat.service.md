# chat.service

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `robsky-angular` |
| **Role** | Source |
| **Bundle** | `services__chat.service` |
| **Files** | 1 |
| **Total size** | 16,042 bytes |
| **Generated** | 2026-02-26 11:03 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `app/services/chat.service.ts` (16,042 bytes, Service)

---

## `app/services/chat.service.ts`

| Field | Value |
|-------|-------|
| **Role** | Service |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-26 |
| **Size** | 16,042 bytes |
| **Exports** | `ChatService`, `StreamingPhase`, `StreamMeta` |

```typescript
import { Injectable, inject, signal, computed } from '@angular/core';
import { Auth } from '@angular/fire/auth';
import { Message, Citation, DebugData } from '../models/types';
import { SessionService } from './session.service';
import { AgentEngineService } from './agent-engine.service';
import { GroundingAuditService } from './grounding-audit.service';
import { buildCitationsFromEvents } from '../utils/citation-extractor';
import type { AgentEngineEvent } from '../models/agent-engine.types';

// Re-export DebugData so existing consumers (pipeline-debug-panel, etc.) keep working
export type { DebugData } from '../models/types';

/** Streaming phase info — maps ADK event patterns to UI phases */
export interface StreamingPhase {
    type: 'searching' | 'analyzing' | 'synthesizing' | 'idle';
    label: string;
    phaseIndex: number;
    totalPhases: number;
}

/** Early metadata from the backend's stream_meta event (kept for API compatibility) */
export interface StreamMeta {
    searchResultCount: number;
    citationCount: number;
    answerSkippedReasons: string[];
}


@Injectable({
    providedIn: 'root'
})
export class ChatService {
    private readonly auth = inject(Auth);
    private readonly sessionService = inject(SessionService);
    private readonly agentEngine = inject(AgentEngineService);
    private readonly groundingAudit = inject(GroundingAuditService);

    // Real-time state for the current conversation
    readonly messages = signal<Message[]>([]);
    readonly isProcessing = signal(false);

    // ── Streaming state ──
    /** True while text deltas are actively arriving */
    readonly isStreaming = signal(false);
    /** Current phase of the streaming lifecycle */
    readonly streamingPhase = signal<StreamingPhase>({
        type: 'idle', label: '', phaseIndex: 0, totalPhases: 0
    });
    /** Early metadata (kept for API compatibility with components) */
    readonly streamMeta = signal<StreamMeta | null>(null);
    /** True when 30s+ has elapsed without the final message */
    readonly isSlowResponse = signal(false);
    /** Pipeline debug data — null for direct Agent Engine path (no backend debug panel) */
    readonly debugData = signal<DebugData | null>(null);

    // ── Resilience state ──
    readonly retryQuery = signal<string | null>(null);
    readonly aiErrorMessage = signal<string | null>(null);
    readonly lastMessageIsGroundingRefusal = computed(() => {
        const msgs = this.messages();
        const last = msgs[msgs.length - 1];
        return (
            last?.role === 'assistant' &&
            last.content.startsWith(
                'I was unable to generate a sufficiently grounded response'
            )
        );
    });

    /** Current streaming message ID */
    private streamingMsgId: string | null = null;

    clearRetry(): void {
        this.retryQuery.set(null);
        this.aiErrorMessage.set(null);
    }

    async retryLastMessage(): Promise<void> {
        const query = this.retryQuery();
        if (!query || this.isProcessing()) return;
        this.clearRetry();
        await this.sendMessage(query);
    }

    /**
     * Initialize messages from current session (called when session changes)
     */
    loadFromSession() {
        const session = this.sessionService.currentSession();
        this.messages.set(session?.messages || []);
    }

    /**
     * Sends a message directly to Vertex AI Agent Engine via SSE.
     *
     * ARCHITECTURE CHANGE (2026-02-25):
     * Previously this called Firebase Cloud Functions → Agent Engine (2 hops).
     * Now this calls Agent Engine directly using the GCP OAuth2 token from
     * Google Sign-In (cloud-platform scope). Zero proxy, zero Cloud Functions.
     *
     * The only surviving Cloud Function is `documentContent` (GCS proxy),
     * which still needs a service account to read private GCS buckets.
     *
     * Event handling:
     *   - function_call parts → phase: 'researching'
     *   - robsky_partner text parts → stream to UI
     *   - state_delta.researcher_evidence_packet → phase: 'synthesizing'
     *   - All events collected → citation extraction via buildCitationsFromEvents()
     *
     * devknowledge reference: Agent Engine streamQuery?alt=sse
     */
    async sendMessage(content: string): Promise<void> {
        const sessionId = this.sessionService.currentSessionId();
        if (!sessionId) return;

        this.retryQuery.set(null);
        this.aiErrorMessage.set(null);

        const userMessage: Message = {
            id: crypto.randomUUID(),
            role: 'user',
            content,
            timestamp: new Date()
        };

        this.messages.update(prev => [...prev, userMessage]);
        this.sessionService.addMessage(sessionId, userMessage);
        this.isProcessing.set(true);
        this.isSlowResponse.set(false);
        this.streamMeta.set(null);
        this.debugData.set(null);
        this.streamingPhase.set({
            type: 'searching', label: 'Thinking and searching...', phaseIndex: 0, totalPhases: 3
        });

        // 30s slow-response warning
        const slowTimer = setTimeout(() => {
            if (this.isProcessing()) {
                this.isSlowResponse.set(true);
            }
        }, 30_000);

        const fetchStartMs = performance.now();
        let ttfbMs = 0;
        let chunkCount = 0;

        // Placeholders for building the final message
        const msgId = crypto.randomUUID();
        let assistantMsg: Message | null = null;
        let accumulatedText = '';
        const allEvents: AgentEngineEvent[] = [];

        try {
            const userId = this.auth.currentUser?.uid ?? 'anonymous';
            // Use the existing ADK session ID if available (multi-turn continuity)
            const adkSessionId = this.sessionService.currentSession()?.adkSessionId;
            // Item 5: archive the previous session to Memory Bank before starting this new one
            const previousSessionId = this.sessionService.getPreviousAdkSessionId();

            // ── Phase: Thinking / Searching ──
            this.streamingPhase.set({
                type: 'searching', label: 'Thinking and searching...', phaseIndex: 0, totalPhases: 3
            });

            for await (const event of this.agentEngine.streamQuery(content, userId, adkSessionId, previousSessionId)) {
                allEvents.push(event);

                // ── Detect phase transitions from ADK event patterns ──
                const hasFunctionCall = event.content?.parts?.some(p => p.function_call);
                const hasFunctionResponse = event.content?.parts?.some(p => p.function_response);
                const stateDelta = event.actions?.state_delta as Record<string, unknown> | undefined;

                if (hasFunctionCall && this.streamingPhase().type !== 'analyzing') {
                    this.streamingPhase.set({
                        type: 'analyzing', label: 'Analyzing with AI agents...', phaseIndex: 1, totalPhases: 3
                    });
                }

                if (stateDelta?.['researcher_evidence_packet'] || hasFunctionResponse) {
                    if (this.streamingPhase().type !== 'synthesizing') {
                        this.streamingPhase.set({
                            type: 'synthesizing', label: 'Composing response...', phaseIndex: 2, totalPhases: 3
                        });
                    }
                }

                // ── Accumulate text from any text-producing agent ──
                // Full agent roster (from agent.py):
                //   robsky_coordinator    — conversational replies, routing confirmations
                //   robsky_partner        — deep research synthesis (SequentialAgent pipeline)
                //   robsky_fast_researcher — TYPE A fast lookups (docket, simple Q&A)
                //   robsky_revision_partner — revision requests
                //   robsky_computation    — tax/financial arithmetic output
                // robsky_researcher is an evidence-gathering internal agent — its output
                // goes into the pipeline but is NOT the final response to the user.
                const TEXT_AUTHORS = new Set([
                    'robsky_coordinator',
                    'robsky_partner',
                    'robsky_fast_researcher',
                    'robsky_revision_partner',
                    'robsky_computation',
                ]);
                if (TEXT_AUTHORS.has(event.author ?? '')) {
                    for (const part of event.content?.parts ?? []) {
                        if (!part.text || part.thought) continue;  // skip thinking-step parts (thought: true)

                        chunkCount++;
                        if (chunkCount === 1) {
                            ttfbMs = Math.round(performance.now() - fetchStartMs);
                            this.isStreaming.set(true);
                        }

                        accumulatedText += part.text;

                        if (!assistantMsg) {
                            // First text chunk — create the streaming placeholder
                            this.streamingMsgId = msgId;
                            assistantMsg = {
                                id: msgId,
                                role: 'assistant',
                                content: accumulatedText,
                                timestamp: new Date(),
                                isStreaming: true,
                            };
                            this.messages.update(prev => [...prev, assistantMsg!]);
                        } else {
                            // Subsequent chunks — update in place
                            const updated: Message = { ...assistantMsg, content: accumulatedText, isStreaming: true };
                            assistantMsg = updated;
                            this.messages.update(prev =>
                                prev.map(m => m.id === msgId ? updated : m)
                            );
                        }
                    }
                }
            }

            // ── Stream complete — stop cursor animation ──
            this.isStreaming.set(false);
            this.streamingMsgId = null;

            // ── Build citations from ALL collected events ──
            const citations: Citation[] = buildCitationsFromEvents(allEvents, accumulatedText);

            // ── [Layer 2 / Signal & Citator] Year-based YELLOW flag (synchronous, zero latency) ──
            // Any citation with a decision year > 15 years ago gets yearFlag = true.
            // This surfaces as a ⚠️ on each SOURCE LINK in the citation tooltip.
            // Does NOT require corpus tagging — uses the year extracted from the URI/title.
            // Hard-demoting old cases from retrieval is WRONG (lawyers legitimately cite old cases
            // for legal history). The flag prompts verification, not rejection.
            const currentYear = new Date().getFullYear();
            citations.forEach(c => {
                if (c.year && (currentYear - c.year) > 15) {
                    c.yearFlag = true;
                }
            });

            // ── Build the final message (replaces streaming placeholder) ──
            const finalMsg: Message = {
                id: msgId,
                role: 'assistant',
                content: accumulatedText || 'I was unable to generate a response. Please try rephrasing your question.',
                citations,
                timestamp: new Date(),
                isStreaming: false,
                relatedQuestions: [],
            };

            if (assistantMsg) {
                this.messages.update(prev => prev.map(m => m.id === msgId ? finalMsg : m));
            } else {
                // No text was streamed (e.g. pure tool-call response) — add directly
                this.messages.update(prev => [...prev, finalMsg]);
            }

            // ── Log timing ──
            const totalMs = Math.round(performance.now() - fetchStartMs);
            console.log(
                `[Chat:Direct] TTFB=${ttfbMs}ms | Events=${allEvents.length} | ` +
                `Chunks=${chunkCount} | Citations=${citations.length} | Total=${totalMs}ms`
            );

            // ── Persist to session ──
            this.sessionService.addMessage(sessionId, finalMsg);

            // ── [Layer 2] Non-blocking Grounding Audit ──
            // Fires AFTER the user already sees the complete response.
            // The badge fades in ~500ms later via SessionService.updateMessageAudit().
            // DO NOT await — this must never delay the response display.
            this.groundingAudit.checkGrounding(accumulatedText, citations).then(audit => {
                if (audit) {
                    audit.docsUsed = citations.length;
                    // Update both the local messages signal and the persisted session
                    this.messages.update(prev =>
                        prev.map(m => m.id === msgId ? { ...m, audit } : m)
                    );
                    this.sessionService.updateMessageAudit(msgId, audit);
                }
            }).catch(err => {
                // Grounding audit failures are non-fatal — response already shown
                console.warn('[GroundingAudit] Post-stream audit failed silently:', err);
            });

            // ── Persist ADK session ID for multi-turn continuity ──
            // The session ID is embedded in the first event's invocation_id pattern
            // OR we can extract it from state_delta. If none found, the Agent Engine
            // is managing sessions internally — no action needed on our side.
            // (The Agent Engine auto-created a session; on next call without session_id,
            // it will create a new one — which is acceptable for now.)
            // Future: extract the ADK session ID from event response headers if exposed.

        } catch (error: unknown) {
            console.error('[Chat:Direct] Agent Engine call failed', error);

            this.isStreaming.set(false);
            this.streamingMsgId = null;

            const errorMsg: Message = {
                id: crypto.randomUUID(),
                role: 'assistant',
                content: '⚠️ Failed to reach the AI service. Please check your connection and try again.',
                timestamp: new Date()
            };
            this.messages.update(prev => [...prev, errorMsg]);

            this.retryQuery.set(content);

            // If it's a token expiry error, make the message more actionable
            const errStr = String(error);
            if (errStr.includes('GCP token') || errStr.includes('auth failed') || errStr.includes('401') || errStr.includes('403')) {
                this.aiErrorMessage.set(
                    'Your session token expired. Please sign out and sign back in with Google to continue.'
                );
            } else {
                this.aiErrorMessage.set(
                    'Our AI service is temporarily unavailable. Your question has been saved.'
                );
            }
        } finally {
            clearTimeout(slowTimer);
            this.isProcessing.set(false);
            this.isStreaming.set(false);
            this.isSlowResponse.set(false);
            this.streamingMsgId = null;
            this.streamingPhase.set({
                type: 'idle', label: '', phaseIndex: 0, totalPhases: 0
            });
        }
    }
}
```
