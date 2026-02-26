# agent-engine.types

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `robsky-angular` |
| **Role** | Model/Types |
| **Bundle** | `models__agent-engine.types` |
| **Files** | 1 |
| **Total size** | 1,366 bytes |
| **Generated** | 2026-02-26 11:03 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `app/models/agent-engine.types.ts` (1,366 bytes, Model/Types)

---

## `app/models/agent-engine.types.ts`

| Field | Value |
|-------|-------|
| **Role** | Model/Types |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-25 |
| **Size** | 1,366 bytes |
| **Exports** | `AgentEngineEvent`, `AgentEnginePart` |

```typescript
/**
 * TypeScript types for raw Vertex AI Agent Engine SSE events.
 *
 * These are the raw ADK event objects returned by the Agent Engine
 * `streamQuery?alt=sse` endpoint. The Angular ChatService processes
 * these events to build the streaming UI and extract citations.
 *
 * Confirmed event structure from diagnostic (2026-02-25):
 *   event["content"]["parts"][N]["function_response"]["name"] = tool name
 *   event["content"]["parts"][N]["function_response"]["response"] = tool output
 */

export interface AgentEngineEvent {
    author?: string;
    invocation_id?: string;
    id?: string;
    timestamp?: number;
    content?: {
        role: 'model' | 'user';
        parts: AgentEnginePart[];
    };
    actions?: {
        state_delta?: Record<string, unknown>;
        transfer_to_agent?: string;
    };
    finish_reason?: string;
}

export interface AgentEnginePart {
    text?: string;
    function_call?: {
        id: string;
        name: string;
        args: Record<string, unknown>;
    };
    function_response?: {
        id?: string;
        name: string;
        response: unknown;
    };
    /** True on thinking-step parts from gemini-2.5-flash extended thinking.
     * These are internal model thoughts — do NOT display to users. */
    thought?: boolean;
    thought_signature?: string;
}
```
