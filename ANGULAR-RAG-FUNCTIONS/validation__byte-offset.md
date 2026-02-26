# validation / byte-offset

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `src` |
| **Role** | Source |
| **Bundle** | `validation__byte-offset` |
| **Files** | 1 |
| **Total size** | 3,368 bytes |
| **Generated** | 2026-02-26 14:05 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `validation/byte-offset.ts` (3,368 bytes, Source)

---

## `validation/byte-offset.ts`

| Field | Value |
|-------|-------|
| **Role** | Source |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-18 |
| **Size** | 3,368 bytes |
| **Exports** | `byteOffsetToCharOffset`, `buildByteToCharMap` |

```typescript
/**
 * Architecture C — UTF-8 Byte Offset ↔ Character Offset Mapper
 *
 * The Check Grounding API returns byte offsets (UTF-8 encoded),
 * but JavaScript strings use UTF-16 code units. This is critical for
 * Filipino text which contains multi-byte characters (ñ, etc.) and
 * potentially Filipino characters, smart quotes, em-dashes, etc.
 *
 * Strategy: Build a byte→char mapping once per response text,
 * then do O(1) lookups for each claim.
 */

/**
 * Convert a UTF-8 byte offset to a JavaScript string character offset.
 *
 * This handles:
 *   - ASCII (1 byte → 1 char)
 *   - Latin supplement: ñ, ü, etc. (2 bytes → 1 char)
 *   - CJK, emoji, etc. (3-4 bytes → 1-2 chars)
 *
 * @param text - The original text string
 * @param byteOffset - The byte offset from the API
 * @returns Character offset in the JavaScript string
 */
export function byteOffsetToCharOffset(text: string, byteOffset: number): number {
    if (byteOffset <= 0) return 0;

    let currentByteOffset = 0;
    let charIndex = 0;

    for (const char of text) {
        if (currentByteOffset >= byteOffset) {
            return charIndex;
        }

        // Calculate UTF-8 byte length of this character
        const codePoint = char.codePointAt(0)!;
        let byteLen: number;

        if (codePoint <= 0x7F) {
            byteLen = 1;         // ASCII
        } else if (codePoint <= 0x7FF) {
            byteLen = 2;         // Latin supplement (ñ, ü, etc.)
        } else if (codePoint <= 0xFFFF) {
            byteLen = 3;         // BMP (most CJK, etc.)
        } else {
            byteLen = 4;         // Supplementary (emoji, rare CJK)
        }

        currentByteOffset += byteLen;

        // In JavaScript, characters outside BMP (> 0xFFFF) use 2 UTF-16 code units (surrogate pair)
        if (codePoint > 0xFFFF) {
            charIndex += 2;
        } else {
            charIndex += 1;
        }
    }

    // If byteOffset extends past the string, clamp to string length
    return charIndex;
}

/**
 * Build a pre-computed byte-offset → char-offset lookup table.
 * Use this when you need to map many offsets for the same text.
 *
 * @param text - The original text string
 * @returns Array where index = byte offset, value = char offset
 */
export function buildByteToCharMap(text: string): number[] {
    const encoder = new TextEncoder();
    const bytes = encoder.encode(text);
    const map = new Array<number>(bytes.length + 1);

    let charIndex = 0;
    let byteIndex = 0;

    for (const char of text) {
        const codePoint = char.codePointAt(0)!;
        let byteLen: number;

        if (codePoint <= 0x7F) {
            byteLen = 1;
        } else if (codePoint <= 0x7FF) {
            byteLen = 2;
        } else if (codePoint <= 0xFFFF) {
            byteLen = 3;
        } else {
            byteLen = 4;
        }

        // Map each byte of this character to the same char index
        for (let b = 0; b < byteLen; b++) {
            map[byteIndex + b] = charIndex;
        }

        byteIndex += byteLen;

        if (codePoint > 0xFFFF) {
            charIndex += 2;
        } else {
            charIndex += 1;
        }
    }

    // Sentinel at the end
    map[byteIndex] = charIndex;

    return map;
}
```
