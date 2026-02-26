# env

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `src` |
| **Role** | Source |
| **Bundle** | `env` |
| **Files** | 1 |
| **Total size** | 2,740 bytes |
| **Generated** | 2026-02-26 14:05 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `env.ts` (2,740 bytes, Source)

---

## `env.ts`

| Field | Value |
|-------|-------|
| **Role** | Source |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-20 |
| **Size** | 2,740 bytes |
| **Exports** | `env` |

```typescript
export const env = {
    // ═══════════════════════════════════════════════
    // Existing (Architecture A)
    // ═══════════════════════════════════════════════
    GOOGLE_PROJECT_ID: process.env.GOOGLE_PROJECT_ID || '',
    VERTEX_AI_SEARCH_LOCATION: process.env.VERTEX_AI_SEARCH_LOCATION || 'global',
    /** Engine (blended app) ID — used by SearchServiceClient in vertex-provider.ts */
    VERTEX_AI_SEARCH_ENGINE_ID: process.env.VERTEX_AI_SEARCH_ENGINE_ID || '',
    /** Data Store ID — used by ConversationalSearchServiceClient in unified-engine.ts */
    VERTEX_AI_SEARCH_DATA_STORE_ID: process.env.VERTEX_AI_SEARCH_DATA_STORE_ID || '',

    // ═══════════════════════════════════════════════
    // Architecture C configuration
    // ═══════════════════════════════════════════════

    /** Pipeline version: 'v1' (Architecture A unified-engine) or 'v2' (Architecture C decoupled) */
    PIPELINE_VERSION: process.env.PIPELINE_VERSION || 'v1',

    /** Default generation model */
    DEFAULT_MODEL: process.env.DEFAULT_MODEL || 'gemini-2.5-flash',

    /** Classifier LLM model for Phase 2 fallback */
    CLASSIFIER_MODEL: process.env.CLASSIFIER_MODEL || 'gemini-2.5-flash-lite',

    /** Check Grounding threshold (0-1) */
    GROUNDING_THRESHOLD: process.env.GROUNDING_THRESHOLD || '0.6',

    /** Enable/disable Check Grounding API */
    ENABLE_GROUNDING_CHECK: process.env.ENABLE_GROUNDING_CHECK || 'true',

    /** Claude-specific region (required if using Claude models) */
    CLAUDE_REGION: process.env.CLAUDE_REGION || 'us-east5',

    /** Model overrides per intent (JSON string) */
    MODEL_INTENT_OVERRIDES: process.env.MODEL_INTENT_OVERRIDES || '',

    // ═══════════════════════════════════════════════
    // Phase 4: Function Calling
    // ═══════════════════════════════════════════════

    /** Enable organic function calling during generation (model can call vertexSearch etc.) */
    ENABLE_TOOL_CALLING: process.env.ENABLE_TOOL_CALLING || 'false',

    /** Max function calling rounds per request (prevents infinite loops) */
    MAX_TOOL_ROUNDS: process.env.MAX_TOOL_ROUNDS || '5',
};
```
