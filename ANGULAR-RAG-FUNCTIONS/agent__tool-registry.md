# agent / tool-registry

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `src` |
| **Role** | Source |
| **Bundle** | `agent__tool-registry` |
| **Files** | 1 |
| **Total size** | 6,762 bytes |
| **Generated** | 2026-02-26 14:05 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `agent/tool-registry.ts` (6,762 bytes, Source)

---

## `agent/tool-registry.ts`

| Field | Value |
|-------|-------|
| **Role** | Source |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-20 |
| **Size** | 6,762 bytes |
| **Exports** | `getToolDefinitions`, `createFunctionCallHandler` |

```typescript
/**
 * Architecture C — Tool Registry (Phase 4: Function Calling)
 *
 * Defines the tools available to the model during generation.
 * Each tool has:
 *   - A FunctionDeclaration (schema for the model)
 *   - An executor function (implementation)
 *
 * Currently registered tools:
 *   1. vertexSearch — Search the legal/tax/accounting corpus
 *
 * Future tools (when demand arises):
 *   - calculateTax — Income tax, VAT, withholding tax computation
 *   - draftDocument — Generate legal document from template
 *   - lookupStatute — Direct statute/regulation lookup by citation
 *
 * Tool invocation conditions follow Google's best practice:
 * "Be specific in your tool definitions. Be sure to tell Gemini under
 *  what conditions a tool call should be invoked."
 */

import { Type } from '@google/genai';
import type { FunctionDeclaration } from '@google/genai';
import { retrieveDocuments, type RetrievedDocument } from '../retrieval/search-retriever';
import type { FunctionCallHandler, ToolDefinition } from '../generation/model-adapter';

// ══════════════════════════════════════════════════════════════
// Tool Declarations (Model-facing schemas)
// ══════════════════════════════════════════════════════════════

/**
 * vertexSearch — Search the Philippine legal, tax, and accounting corpus.
 *
 * Invocation condition: Use when the user asks about court cases, statutes,
 * tax regulations, accounting standards, BIR issuances, or any factual
 * legal/tax/accounting question that requires citing authoritative sources.
 */
const VERTEX_SEARCH_DECLARATION: FunctionDeclaration = {
    name: 'vertexSearch',
    description: `Search the Philippine legal, tax, and accounting document corpus (Supreme Court decisions, statutes, BIR regulations, PFRS/PAS/IFRS standards, auditing standards). Use this tool when:
- The user asks about a specific case, statute, standard, or regulation
- The user asks a factual legal, tax, or accounting question
- You need to cite authoritative sources for your response
- The user references a G.R. number, Republic Act, Revenue Regulation, or accounting standard
Do NOT use this tool for:
- Simple greetings or conversational follow-ups that don't need new sources
- General knowledge questions unrelated to Philippine law/tax/accounting`,
    parameters: {
        type: Type.OBJECT,
        properties: {
            query: {
                type: Type.STRING,
                description: 'The search query. Use specific legal terms, case names, statute numbers, or accounting standard references for best results.',
            },
            domain: {
                type: Type.STRING,
                description: 'Optional domain filter to narrow results. Use LEGAL for court cases/statutes, TAX for BIR/NIRC, ACCOUNTING for PFRS/PAS/IFRS, or omit for cross-domain search.',
                // Note: enum is set in the properties, not here
            },
            pageSize: {
                type: Type.NUMBER,
                description: 'Number of documents to retrieve (default: 10, max: 20). Use 5 for targeted lookups, 15 for comprehensive research.',
            },
        },
        required: ['query'],
    },
};

// ══════════════════════════════════════════════════════════════
// Tool Executors (Server-side implementations)
// ══════════════════════════════════════════════════════════════

/**
 * Execute a vertexSearch tool call.
 * Maps the model's function call args to our retrieveDocuments API.
 */
async function executeVertexSearch(args: Record<string, any>): Promise<Record<string, any>> {
    const query = args.query || '';
    const domain = args.domain || undefined;
    const pageSize = Math.min(args.pageSize || 10, 20); // Cap at 20

    console.log(`[ToolRegistry] vertexSearch: query="${query.substring(0, 80)}" domain=${domain || 'ALL'} pageSize=${pageSize}`);

    const docs = await retrieveDocuments(query, {
        domain,
        pageSize,
    });

    // Return documents in a format the model can use
    return {
        resultCount: docs.length,
        documents: docs.map((doc) => ({
            sourceNumber: doc.sourceNumber,
            title: doc.title,
            content: doc.content.length > 6000
                ? doc.content.substring(0, 6000) + '\n[...truncated]'
                : doc.content,
            uri: doc.uri,
            relevanceScore: doc.relevanceScore,
        })),
    };
}

// ══════════════════════════════════════════════════════════════
// Public API
// ══════════════════════════════════════════════════════════════

/**
 * Get all tool definitions to pass to the model adapter.
 * Returns them in the format expected by GenerateParams.tools.
 */
export function getToolDefinitions(): ToolDefinition[] {
    return [{
        functionDeclarations: [
            VERTEX_SEARCH_DECLARATION,
        ],
    }];
}

/**
 * Create a function call handler that routes model function calls
 * to the appropriate executor.
 *
 * Usage:
 *   const handler = createFunctionCallHandler();
 *   adapter.generate({ tools: getToolDefinitions(), onFunctionCall: handler });
 */
export function createFunctionCallHandler(): FunctionCallHandler {
    return async (name: string, args: Record<string, any>): Promise<Record<string, any>> => {
        switch (name) {
            case 'vertexSearch':
                return executeVertexSearch(args);

            // Future tools:
            // case 'calculateTax':
            //     return executeCalculateTax(args);
            // case 'draftDocument':
            //     return executeDraftDocument(args);

            default:
                console.warn(`[ToolRegistry] Unknown function: ${name}`);
                return { error: `Unknown function: ${name}. Available: vertexSearch` };
        }
    };
}

/**
 * Re-export Type for use in orchestrator if needed.
 */
export { Type };
```
