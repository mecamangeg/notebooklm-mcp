# agent-engine.service

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `robsky-angular` |
| **Role** | Source |
| **Bundle** | `services__agent-engine.service` |
| **Files** | 1 |
| **Total size** | 6,959 bytes |
| **Generated** | 2026-02-26 11:05 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `app/services/agent-engine.service.ts` (6,959 bytes, Service)

---

## `app/services/agent-engine.service.ts`

| Field | Value |
|-------|-------|
| **Role** | Service |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-26 |
| **Size** | 6,959 bytes |
| **Exports** | `AgentEngineService` |

```typescript
import { Injectable, inject } from '@angular/core';
import { AuthService } from './auth.service';
import { AGENT_ENGINE } from '../config/agent-engine.config';
import type { AgentEngineEvent } from '../models/agent-engine.types';

/**
 * AgentEngineService — Direct REST connection to Vertex AI Agent Engine.
 *
 * devknowledge validated endpoint:
 *   POST {LOCATION}-aiplatform.googleapis.com/v1/.../reasoningEngines/{ID}:streamQuery?alt=sse
 *   Authorization: Bearer <gcp-access-token>
 *   Accept: text/event-stream
 */
@Injectable({ providedIn: 'root' })
export class AgentEngineService {
    private readonly auth = inject(AuthService);

    async *streamQuery(
        message: string,
        userId: string,
        sessionId?: string,
        previousSessionId?: string,   // Item 5: triggers Memory Bank archival on backend
    ): AsyncGenerator<AgentEngineEvent> {
        const token = await this.auth.getGcpToken();
        if (!token) {
            throw new Error(
                'GCP token expired or unavailable. Please sign out and sign back in with Google.'
            );
        }

        const body = {
            class_method: 'async_stream_query',
            input: {
                message,
                user_id: userId,
                ...(sessionId ? { session_id: sessionId } : {}),
                ...(previousSessionId ? { previous_session_id: previousSessionId } : {}),
            },
        };

        const url = AGENT_ENGINE.STREAM_URL + '?alt=sse';

        let response: Response;
        try {
            response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json',
                    'Accept': 'text/event-stream',  // Signal streaming intent
                },
                body: JSON.stringify(body),
            });
        } catch (networkErr) {
            throw new Error(`Network error reaching Agent Engine: ${networkErr}`);
        }

        if (!response.ok) {
            const errText = await response.text().catch(() => '(unreadable)');
            if (response.status === 401 || response.status === 403) {
                throw new Error(
                    `Agent Engine auth failed (${response.status}). ` +
                    `GCP token may be expired. Please sign out and sign back in.`
                );
            }
            throw new Error(`Agent Engine error ${response.status}: ${errText}`);
        }

        // ── Stream parsing ──
        // DIAGNOSTIC CONFIRMED: Agent Engine returns Content-Type: application/json,
        // NOT text/event-stream, even with ?alt=sse query parameter.
        // Format: one JSON object per line (\n separated), NO "data: " prefix.
        // Each line is a bare ADK event object with keys: author, content, actions, id, timestamp.
        // (No "response" wrapper — the event IS the top-level object.)
        const reader = response.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let frameCount = 0;
        let yieldCount = 0;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() ?? '';  // keep incomplete last line

            for (const line of lines) {
                const trimmedLine = line.trim();

                // Skip empty lines (blank separators)
                if (!trimmedLine) continue;

                frameCount++;

                try {
                    const parsed = JSON.parse(trimmedLine);

                    // Check for in-stream error objects (e.g., 429 RESOURCE_EXHAUSTED)
                    // These come as bare JSON: {"code": 429, "message": "...", "status": "..."}
                    if (typeof parsed['code'] === 'number' && parsed['message']) {
                        throw new Error(
                            `Agent Engine error ${parsed['code']}: ${String(parsed['message']).slice(0, 200)}`
                        );
                    }

                    // Agent Engine returns ADK events directly (no "response" wrapper).
                    // Legacy note: some old docs show { response: <AdkEvent> } — keep fallback.
                    const event: AgentEngineEvent = parsed['response'] ?? parsed;

                    // Debug: log first 5 frames + all text frames
                    if (yieldCount < 3 || (event.content?.parts?.some(p => p.text && !p.thought && !p.thought_signature))) {
                        const author = event.author ?? '(no author)';
                        const partTypes = (event.content?.parts ?? []).map(p =>
                            // Check thought BEFORE text — thought parts can have both fields set
                            (p.thought || p.thought_signature) && p.text ? `thought+text(${p.text.length})` :
                                p.thought || p.thought_signature ? 'thought' :
                                    p.text ? `text(${p.text.length})` :
                                        p.function_call ? `fn_call(${p.function_call.name})` :
                                            p.function_response ? `fn_resp(${p.function_response.name})` :
                                                'unknown'
                        ).join(',');
                        console.log(`[AE #${frameCount}] author=${author} parts=[${partTypes}]`);
                    }

                    yieldCount++;
                    yield event;
                } catch (parseErr) {
                    // Re-throw in-stream API errors (429, etc.) — don't swallow them
                    if (parseErr instanceof Error && parseErr.message.startsWith('Agent Engine error')) {
                        throw parseErr;
                    }
                    // Log malformed frames for diagnosis (genuine JSON parse failures)
                    console.warn(`[AE] parse error on frame #${frameCount}:`, trimmedLine.slice(0, 100), parseErr);
                }
            }
        }

        // Flush any remaining data in buffer
        if (buffer.trim()) {
            frameCount++;
            try {
                const parsed = JSON.parse(buffer.trim());
                const event: AgentEngineEvent = parsed['response'] ?? parsed;
                yieldCount++;
                yield event;
            } catch (parseErr) {
                console.warn(`[AE] parse error on final frame:`, buffer.slice(0, 100), parseErr);
            }
        }

        console.log(`[AE] Stream complete: ${frameCount} frames received, ${yieldCount} events yielded`);
    }
}
```
