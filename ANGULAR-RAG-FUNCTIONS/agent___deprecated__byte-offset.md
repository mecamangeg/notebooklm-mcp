# _deprecated / byte-offset

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `src` |
| **Role** | Source |
| **Bundle** | `agent___deprecated__byte-offset` |
| **Files** | 1 |
| **Total size** | 462 bytes |
| **Generated** | 2026-02-26 14:05 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `agent/_deprecated/byte-offset.ts` (462 bytes, Source)

---

## `agent/_deprecated/byte-offset.ts`

| Field | Value |
|-------|-------|
| **Role** | Source |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-18 |
| **Size** | 462 bytes |
| **Exports** | `byteOffsetToCharOffset` |

```typescript
const textEncoder = new TextEncoder();

/**
 * Convert a UTF-8 byte offset to a JavaScript string character offset.
 */
export function byteOffsetToCharOffset(text: string, byteOffset: number): number {
    if (byteOffset <= 0) return 0;
    const bytes = textEncoder.encode(text);
    const clampedOffset = Math.min(byteOffset, bytes.length);
    const decoder = new TextDecoder();
    return decoder.decode(bytes.slice(0, clampedOffset)).length;
}
```
