# _deprecated / tools

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `src` |
| **Role** | Source |
| **Bundle** | `agent___deprecated__tools` |
| **Files** | 1 |
| **Total size** | 1,983 bytes |
| **Generated** | 2026-02-26 14:05 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `agent/_deprecated/tools.ts` (1,983 bytes, Source)

---

## `agent/_deprecated/tools.ts`

| Field | Value |
|-------|-------|
| **Role** | Source |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-18 |
| **Size** | 1,983 bytes |
| **Exports** | `FunctionDeclaration`, `ToolDeclaration`, `legalTools`, `legalToolsObject` |

```typescript

export interface FunctionDeclaration {
    name: string;
    description: string;
    parameters?: {
        type: 'OBJECT' | 'STRING' | 'NUMBER' | 'INTEGER' | 'BOOLEAN' | 'ARRAY';
        properties?: Record<string, {
            type: 'STRING' | 'NUMBER' | 'INTEGER' | 'BOOLEAN' | 'ARRAY' | 'OBJECT';
            description?: string;
            enum?: string[];
        }>;
        required?: string[];
    };
}

export interface ToolDeclaration {
    functionDeclarations: FunctionDeclaration[];
}

const searchLegalCorpus: FunctionDeclaration = {
    name: "search_legal_corpus",
    description: `REQUIRED for legal questions. Searches a curated Philippine legal corpus with Authority Tier metadata.`,
    parameters: {
        type: 'OBJECT',
        properties: {
            query: { type: 'STRING', description: "The specific legal concept." },
            filter_tier: { type: 'STRING', enum: ["TIER_1_SUPREME", "TIER_1_AND_2", "ALL"] },
            domain: { type: 'STRING', enum: ["legal", "tax", "accounting", "auto"] },
            search_mode: { type: 'STRING', enum: ["SNIPPET", "DEEP_READ"] },
            sort_by: { type: 'STRING', enum: ["RELEVANCE", "DATE_DESC"] },
            doc_type: { type: 'STRING', enum: ["all", "judicial_form", "practice_template"] }
        },
        required: ["query"]
    }
};

const getDocumentByCitation: FunctionDeclaration = {
    name: "get_document_by_citation",
    description: `Retrieve a specific document by its citation reference.`,
    parameters: {
        type: 'OBJECT',
        properties: {
            citation: { type: 'STRING', description: "The exact citation reference (G.R. No., RA, IFRS, RR, etc.)" }
        },
        required: ["citation"]
    }
};

export const legalTools: FunctionDeclaration[] = [
    searchLegalCorpus,
    getDocumentByCitation
];

export const legalToolsObject: ToolDeclaration = {
    functionDeclarations: legalTools
};
```
