# agent / types

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `src` |
| **Role** | Model/Types |
| **Bundle** | `agent__types` |
| **Files** | 1 |
| **Total size** | 1,126 bytes |
| **Generated** | 2026-02-26 14:05 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `agent/types.ts` (1,126 bytes, Model/Types)

---

## `agent/types.ts`

| Field | Value |
|-------|-------|
| **Role** | Model/Types |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-18 |
| **Size** | 1,126 bytes |
| **Exports** | `EvidenceItem`, `SearchOptions`, `SearchResult` |

```typescript
export interface EvidenceItem {
    sourceId: string;
    title: string;
    content: string;
    authority: {
        tier: 1 | 2 | 3 | 4;
        label: string;
        type: string;
    };
    citation: {
        display: string;
        uri: string;
    };
    domain: "legal" | "tax" | "accounting" | "general";
    evidenceType?: 'case_law' | 'statute' | 'regulation' | 'commentary' | 'computation' | 'web';
    chunkId?: string;
    charStartPos?: number;
    charEndPos?: number;
    _extractiveSegments?: Array<{
        content: string;
        relevanceScore?: number;
        pageNumber?: string;
    }>;
}

export interface SearchOptions {
    query: string;
    filterTier?: "TIER_1_SUPREME" | "TIER_1_AND_2" | "ALL";
    domain?: "legal" | "tax" | "accounting" | "auto";
    searchMode?: "SNIPPET" | "DEEP_READ";
    sortBy?: "RELEVANCE" | "DATE_DESC";
    docType?: string | 'all';
    pageSize?: number;
    ponente?: string;
    modeOfSitting?: string;
    dateIso?: string;
}

export interface SearchResult {
    evidence: EvidenceItem[];
    totalFound: number;
}
```
