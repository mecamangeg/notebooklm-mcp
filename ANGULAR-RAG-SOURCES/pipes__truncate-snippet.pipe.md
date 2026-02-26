# truncate-snippet.pipe

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `robsky-angular` |
| **Role** | Source |
| **Bundle** | `pipes__truncate-snippet.pipe` |
| **Files** | 1 |
| **Total size** | 1,926 bytes |
| **Generated** | 2026-02-26 11:01 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `app/pipes/truncate-snippet.pipe.ts` (1,926 bytes, Pipe)

---

## `app/pipes/truncate-snippet.pipe.ts`

| Field | Value |
|-------|-------|
| **Role** | Pipe |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-25 |
| **Size** | 1,926 bytes |
| **Exports** | `TruncateSnippetPipe` |

```typescript
import { Pipe, PipeTransform } from '@angular/core';

/**
 * TruncateSnippetPipe — Display-time truncation and sanitation of
 * GroundingChunk RetrievedContext.text for the Sources panel.
 *
 * Angular MCP validated pattern (v21):
 *  - pure: true (default) → runs only when input reference changes (OnPush safe)
 *  - Strips [[FN N: ...]] footnote markers (injected by CURATED corpus pipeline)
 *  - Strips raw HTML tags (Vertex AI extractive segments may include <b> bold)
 *  - Truncates at word boundary, appends ellipsis
 *
 * Design decision: truncation happens ONLY at display time (not at extraction).
 * citation.snippet stores the full RetrievedContext.text so it can be passed
 * verbatim to the document viewer's highlight treewalk for maximum match reliability.
 *
 * Usage:
 *   {{ citation.snippet | truncateSnippet }}
 *   {{ citation.snippet | truncateSnippet:180 }}
 */
@Pipe({ name: 'truncateSnippet' })
export class TruncateSnippetPipe implements PipeTransform {
    transform(text: string | undefined | null, maxLength = 280): string {
        if (!text) return '';

        // 1. Strip [[FN N: ...]] footnote markers (from CURATED HTML corpus pipeline)
        let clean = text.replace(/\[\[FN\s+\d+:[\s\S]*?\]\]/g, '');

        // 2. Strip raw HTML tags (Vertex AI Search extractive segments may include <b>)
        clean = clean.replace(/<[^>]+>/g, '');

        // 3. Collapse whitespace
        clean = clean.replace(/\s+/g, ' ').trim();

        // 4. If within limit, return as-is
        if (clean.length <= maxLength) return clean;

        // 5. Truncate at last word boundary before maxLength (stay above 70% of limit)
        const truncated = clean.slice(0, maxLength);
        const lastSpace = truncated.lastIndexOf(' ');
        return (lastSpace > maxLength * 0.7 ? truncated.slice(0, lastSpace) : truncated).trimEnd() + '\u2026';
    }
}
```
