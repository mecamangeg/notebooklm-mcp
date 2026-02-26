# _deprecated / implementations

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `src` |
| **Role** | Source |
| **Bundle** | `agent___deprecated__implementations` |
| **Files** | 1 |
| **Total size** | 1,001 bytes |
| **Generated** | 2026-02-26 14:05 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `agent/_deprecated/implementations.ts` (1,001 bytes, Source)

---

## `agent/_deprecated/implementations.ts`

| Field | Value |
|-------|-------|
| **Role** | Source |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-18 |
| **Size** | 1,001 bytes |
| **Exports** | `executeSearch`, `getDocumentByCitation` |

```typescript

import { VertexSearchProvider } from '../search/vertex-provider';
import { EvidenceItem } from './types';

export async function executeSearch(
    query: string,
    filterTier: string = "ALL",
    domain: string = "auto",
    searchMode: string = "SNIPPET",
    sortBy: string = "RELEVANCE",
    docType: string = "all"
): Promise<{ evidence: EvidenceItem[], totalFound: number }> {
    const provider = new VertexSearchProvider();
    return provider.search({
        query,
        filterTier: filterTier as any,
        domain: domain as any,
        searchMode: searchMode as any,
        sortBy: sortBy as any,
        docType: docType as any
    });
}

export async function getDocumentByCitation(citation: string): Promise<EvidenceItem | null> {
    const provider = new VertexSearchProvider();
    const result = await provider.search({
        query: citation,
        pageSize: 1
    });
    return result.evidence.length > 0 ? result.evidence[0] : null;
}
```
