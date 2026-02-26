# generation / model-config

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `src` |
| **Role** | Model/Types |
| **Bundle** | `generation__model-config` |
| **Files** | 1 |
| **Total size** | 5,141 bytes |
| **Generated** | 2026-02-26 14:05 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `generation/model-config.ts` (5,141 bytes, Model/Types)

---

## `generation/model-config.ts`

| Field | Value |
|-------|-------|
| **Role** | Model/Types |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-20 |
| **Size** | 5,141 bytes |
| **Exports** | `ModelConfig`, `selectModel`, `getTemperatureForIntent`, `getPageSizeForIntent`, `getStreamingModel` |

```typescript
/**
 * Architecture C — Model Configuration
 *
 * Configuration-driven model selection. Maps intents and domains to
 * specific models, enabling A/B testing and cost optimization without
 * code changes.
 */

import type { QueryIntent, QueryDomain } from '../agent/classifier';
import { env } from '../env';

// ══════════════════════════════════════════════════════════════
// Configuration
// ══════════════════════════════════════════════════════════════

export interface ModelConfig {
    /** Default model for general use */
    defaultModel: string;
    /** Intent-specific model overrides */
    intentOverrides?: Partial<Record<QueryIntent, string>>;
    /** Domain-specific model overrides */
    domainOverrides?: Partial<Record<QueryDomain, string>>;
    /** Streaming model (may differ from sync) */
    streamingModel?: string;
}

/**
 * Default model configuration.
 * Phase 1: All Gemini. Phase 3 enables Claude overrides.
 */
const DEFAULT_MODEL_CONFIG: ModelConfig = {
    defaultModel: 'gemini-2.5-flash',
    intentOverrides: {
        // Phase 3: Uncomment to enable Claude for premium intents
        // DRAFTING: 'claude-opus-4-6',
        // STRATEGIC: 'claude-opus-4-6',
        COMPARATIVE: 'gemini-2.5-pro',
        PEDAGOGICAL: 'gemini-2.5-flash',
        COMPUTATION: 'gemini-2.5-flash',
        // LOOKUP now goes through generation (conversational intelligence refactor)
        // Needs a capable model — flash-lite was only used when LOOKUP bypassed generation
        LOOKUP: 'gemini-2.5-flash',
    },
    streamingModel: 'gemini-2.5-flash',
};

/**
 * Get the active model configuration, with env overrides applied.
 */
function getModelConfig(): ModelConfig {
    const config = { ...DEFAULT_MODEL_CONFIG };

    // Override default model from env
    if (env.DEFAULT_MODEL) {
        config.defaultModel = env.DEFAULT_MODEL;
    }

    // Parse intent overrides from env JSON
    if (env.MODEL_INTENT_OVERRIDES) {
        try {
            const overrides = JSON.parse(env.MODEL_INTENT_OVERRIDES);
            config.intentOverrides = { ...config.intentOverrides, ...overrides };
        } catch {
            console.warn('[ModelConfig] Failed to parse MODEL_INTENT_OVERRIDES env var');
        }
    }

    return config;
}

// ══════════════════════════════════════════════════════════════
// Model Selection
// ══════════════════════════════════════════════════════════════

/**
 * Select the best model for a given intent + domain combination.
 *
 * Priority: intent override → domain override → default model
 */
export function selectModel(intent: QueryIntent, domain: QueryDomain): string {
    const config = getModelConfig();

    // Check intent override first
    if (config.intentOverrides?.[intent]) {
        return config.intentOverrides[intent]!;
    }

    // Check domain override
    if (config.domainOverrides?.[domain]) {
        return config.domainOverrides[domain]!;
    }

    // Fall back to default
    return config.defaultModel;
}

/**
 * Get the temperature setting for an intent.
 * More creative intents get higher temperature.
 */
export function getTemperatureForIntent(intent: QueryIntent): number {
    switch (intent) {
        case 'LOOKUP':
        case 'COMPUTATION':
        case 'VERIFICATION':
        case 'COMPLIANCE':
            return 0.1; // Precise, factual
        case 'DRAFTING':
        case 'PEDAGOGICAL':
        case 'PREDICTIVE':
            return 0.3; // Moderate creativity
        case 'STRATEGIC':
        case 'COMPARATIVE':
        case 'RESEARCH':
        case 'INSTRUCTIONAL':
        case 'ANALYTICAL':
        case 'SUMMARIZATION':
        case 'TEMPORAL':
        case 'CONVERSATIONAL':
            return 0.2; // Balanced
        default:
            return 0.2;
    }
}

/**
 * Get the appropriate page size for retrieval based on intent.
 */
export function getPageSizeForIntent(intent: QueryIntent): number {
    switch (intent) {
        case 'LOOKUP':
            return 5;   // Targeted — fewer, more precise
        case 'COMPARATIVE':
        case 'RESEARCH':
        case 'ANALYTICAL':
            return 15;  // Comprehensive — need breadth
        case 'DRAFTING':
        case 'STRATEGIC':
            return 10;  // Moderate
        default:
            return 10;
    }
}

/**
 * Get the streaming model choice.
 */
export function getStreamingModel(): string {
    const config = getModelConfig();
    return config.streamingModel || config.defaultModel;
}
```
