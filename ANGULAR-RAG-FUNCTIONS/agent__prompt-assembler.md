# agent / prompt-assembler

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `src` |
| **Role** | Source |
| **Bundle** | `agent__prompt-assembler` |
| **Files** | 1 |
| **Total size** | 5,300 bytes |
| **Generated** | 2026-02-26 14:05 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `agent/prompt-assembler.ts` (5,300 bytes, Source)

---

## `agent/prompt-assembler.ts`

| Field | Value |
|-------|-------|
| **Role** | Source |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-20 |
| **Size** | 5,300 bytes |
| **Exports** | `ConversationTurn`, `PromptAssemblyInput`, `AssembledPrompt`, `assemblePrompt` |

```typescript
/**
 * Architecture C — Prompt Assembly Engine (Conversational Intelligence Refactor)
 *
 * Constructs the full prompt with a unified persona and universal context:
 *   Layer 1: Unified persona (persistent identity — "Robsky")
 *   Layer 2: Domain expertise (contextual, not persona-replacing)
 *   Layer 3: Intent context hint (awareness metadata for the model)
 *   Layer 4: Intent-specific response strategy (softened suggestion)
 *   Layer 5: Citation protocol + authority hierarchy
 *   Layer 6: Tonal adjustment
 *   Layer 7: Professional voice
 *   Layer 8: Grounding constraint (ALWAYS appended)
 *
 * Context is assembled into the user message:
 *   - SOURCE DOCUMENTS with [source N] numbering
 *   - Conversation history (ALWAYS included when available)
 *   - User query
 */

import type { QueryIntent, QueryDomain, TonalDirective } from './classifier';
import type { RetrievedDocument } from '../retrieval/search-retriever';
import {
    getDomainPersona,
    getDomainExpertise,
    getIntentDirective,
    getIntentContextHint,
    getTonalDirective,
    getCitationProtocol,
    getProfessionalVoice,
    GROUNDING_CONSTRAINT,
} from './prompt-templates';

// ══════════════════════════════════════════════════════════════
// Types
// ══════════════════════════════════════════════════════════════

export interface ConversationTurn {
    role: 'user' | 'assistant';
    content: string;
}

export interface PromptAssemblyInput {
    intent: QueryIntent;
    domain: QueryDomain;
    tone: TonalDirective;
    query: string;
    retrievedDocs: RetrievedDocument[];
    conversationHistory?: ConversationTurn[];
}

export interface AssembledPrompt {
    systemInstruction: string;
    userMessage: string;
}

// ══════════════════════════════════════════════════════════════
// Core Assembly
// ══════════════════════════════════════════════════════════════

/**
 * Assemble a complete prompt with unified persona and universal context.
 *
 * System instruction = unified persona + domain expertise + intent context hint
 *                    + response strategy + citation protocol + tone + voice + grounding
 * User message = SOURCE DOCUMENTS + conversation history (ALWAYS) + query
 */
export function assemblePrompt(input: PromptAssemblyInput): AssembledPrompt {
    // ── System Instruction (layered) ──
    const layers: string[] = [
        // Layer 1: Unified persona (persistent identity — always "Robsky")
        getDomainPersona(input.domain),
        // Layer 2: Domain expertise (contextual awareness, not persona replacement)
        getDomainExpertise(input.domain),
        // Layer 3: Intent context hint (awareness metadata for the model)
        getIntentContextHint(input.intent, input.domain),
        // Layer 4: Intent-specific response strategy (softened suggestion)
        getIntentDirective(input.intent),
        // Layer 5: Citation protocol + authority hierarchy
        getCitationProtocol(),
        // Layer 6: Tonal adjustment (optional)
        getTonalDirective(input.tone),
        // Layer 7: Professional voice
        getProfessionalVoice(),
        // Layer 8: Grounding constraint (ALWAYS)
        GROUNDING_CONSTRAINT,
    ];

    const systemInstruction = layers.filter(Boolean).join('\n\n');

    // ── User Message (context + query) ──
    const messageParts: string[] = [];

    // Source documents with numbering
    if (input.retrievedDocs.length > 0) {
        messageParts.push('SOURCE DOCUMENTS:');
        for (const doc of input.retrievedDocs) {
            // Trim content to avoid exceeding model context
            const content = doc.content.length > 8000
                ? doc.content.substring(0, 8000) + '\n[...truncated]'
                : doc.content;
            messageParts.push(`[source ${doc.sourceNumber}] ${doc.title}\n${content}`);
        }
        messageParts.push(''); // blank line separator
    }

    // Conversation history — ALWAYS included when available (universal injection)
    // No longer gated behind CONVERSATIONAL intent — every turn gets full context
    if (input.conversationHistory?.length) {
        messageParts.push('CONVERSATION HISTORY:');
        // Include only the last 6 turns to stay within context limits
        const recentHistory = input.conversationHistory.slice(-6);
        for (const turn of recentHistory) {
            messageParts.push(`${turn.role.toUpperCase()}: ${turn.content}`);
        }
        messageParts.push(''); // blank line separator
    }

    // User query
    messageParts.push(`QUERY: ${input.query}`);

    const userMessage = messageParts.join('\n');

    return { systemInstruction, userMessage };
}
```
