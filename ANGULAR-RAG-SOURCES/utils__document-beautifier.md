# document-beautifier

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `robsky-angular` |
| **Role** | Utility |
| **Bundle** | `utils__document-beautifier` |
| **Files** | 1 |
| **Total size** | 22,284 bytes |
| **Generated** | 2026-02-26 11:05 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `app/utils/document-beautifier.ts` (22,284 bytes, Utility)

---

## `app/utils/document-beautifier.ts`

| Field | Value |
|-------|-------|
| **Role** | Utility |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-22 |
| **Size** | 22,284 bytes |
| **Exports** | `beautifyLegalDocument` |

```typescript
/**
 * Document Beautifier for Legal Documents
 *
 * Transforms CURATED HTML (optimized for Vertex AI Search semantic retrieval)
 * into a visually polished reading experience for the Document Viewer.
 *
 * The CURATED HTML has these characteristics:
 *   - Single <p> wall of text in opinion sections
 *   - Footnotes inlined as [[FN N: content]]
 *   - Footnotes duplicated at the end of the <p> as plain text
 *   - No paragraph breaks, blockquotes, or rich formatting
 *
 * This transform converts those into superscript links, paragraph breaks,
 * blockquote detection, disposition highlighting, and a proper footnote section.
 */

// ─── Reading Stylesheet ──────────────────────────────────────────────

const READING_CSS = `
<style id="robsky-reading-styles">
  @import url('https://fonts.googleapis.com/css2?family=Literata:ital,opsz,wght@0,7..72,400;0,7..72,500;0,7..72,600;0,7..72,700;1,7..72,400;1,7..72,500&family=Inter:wght@400;500;600;700&display=swap');

  *, *::before, *::after { box-sizing: border-box; }

  body {
    margin: 0;
    padding: 32px 24px 64px;
    background: #faf9f7;
    color: #1a1a2e;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }

  article {
    max-width: 740px;
    margin: 0 auto;
    font-family: 'Literata', 'Georgia', 'Times New Roman', serif;
    font-size: 15.5px;
    line-height: 1.82;
    color: #2c2c3e;
  }

  /* ── Case Title ── */
  h1 {
    font-family: 'Inter', -apple-system, sans-serif;
    font-size: 1.35rem;
    font-weight: 700;
    color: #1a1a2e;
    letter-spacing: -0.02em;
    line-height: 1.35;
    margin: 0 0 20px 0;
    padding-bottom: 16px;
    border-bottom: 2px solid #c9a961;
  }

  /* ── Metadata Header ── */
  article > header {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 6px 24px;
    padding: 16px 20px;
    margin-bottom: 28px;
    background: #f5f3ef;
    border-radius: 10px;
    border: 1px solid #e8e4dd;
  }

  article > header p {
    margin: 0;
    font-family: 'Inter', sans-serif;
    font-size: 0.8125rem;
    color: #5a5a6e;
    line-height: 1.6;
  }

  article > header strong {
    color: #3a3a4e;
    font-weight: 600;
  }

  /* ── Section Headings (h2) ── */
  h2 {
    font-family: 'Inter', sans-serif;
    font-size: 0.9375rem;
    font-weight: 700;
    color: #1a1a2e;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin: 36px 0 16px 0;
    padding-bottom: 8px;
    border-bottom: 1px solid #e0ddd6;
  }

  /* ── Syllabi Section ──
     Hidden from the document viewer. The syllabi (doctrinal headnotes)
     exist in the CURATED HTML to boost Vertex AI Search semantic retrieval
     quality — they are NOT meant for human display.
     Covers both CURATED format (.syllabi) and E-SCRA native format (.syllabi-rw). */
  .syllabi,
  .syllabi-rw {
    display: none !important;
  }


  /* ── Disposition (WHEREFORE) ── */
  .disposition {
    margin: 32px 0;
    padding: 20px 24px;
    background: linear-gradient(135deg, #f0faf4 0%, #eef8f2 100%);
    border-left: 4px solid #16a34a;
    border-radius: 0 10px 10px 0;
    border: 1px solid #d0e8d8;
    border-left: 4px solid #16a34a;
  }

  .disposition h2 {
    margin-top: 0;
    color: #15803d;
    border-bottom-color: #a7d4b6;
    font-size: 0.8125rem;
  }

  .disposition p {
    font-weight: 500;
    color: #1e4030;
    line-height: 1.75;
  }

  /* ── Opinion Section ── */
  .opinion p {
    margin: 0 0 18px 0;
    text-align: justify;
    text-justify: inter-word;
    hyphens: auto;
  }

  /* ── Footnote References (superscript) ── */
  .fn-ref {
    color: #b45309;
    cursor: pointer;
    font-family: 'Inter', sans-serif;
    font-size: 0.7em;
    font-weight: 600;
    vertical-align: super;
    line-height: 0;
    padding: 0 1px;
    text-decoration: none;
    transition: color 0.15s ease, background-color 0.15s ease;
    border-radius: 2px;
  }

  .fn-ref:hover {
    color: #92400e;
    background-color: rgba(180, 83, 9, 0.08);
  }

  /* ── Blockquotes (detected legal quotations) ── */
  blockquote {
    border-left: 3px solid #c9a961;
    margin: 20px 0 20px 8px;
    padding: 12px 20px;
    background: #faf8f3;
    color: #4a4a5e;
    font-size: 0.9375em;
    line-height: 1.75;
    border-radius: 0 6px 6px 0;
  }

  blockquote p {
    margin: 0 0 8px 0;
  }

  blockquote p:last-child {
    margin-bottom: 0;
  }

  /* ── Issue Headings ── */
  .issue-heading {
    font-family: 'Inter', sans-serif;
    font-size: 0.9375rem;
    font-weight: 600;
    color: #1a1a2e;
    margin: 28px 0 12px 0;
    padding: 8px 0;
    border-bottom: 1px dashed #d0cdc6;
  }

  /* ── Article / Statutory Provisions ── */
  .legal-provision {
    margin: 16px 0;
    padding: 14px 20px;
    background: #f8f7f5;
    border: 1px solid #e8e4dd;
    border-radius: 8px;
    font-size: 0.9375em;
    line-height: 1.7;
  }

  /* ── SO ORDERED + Concurrence ── */
  .so-ordered {
    font-weight: 700;
    font-style: italic;
    margin-top: 32px;
    color: #1a1a2e;
  }

  .concurrence {
    font-family: 'Inter', sans-serif;
    font-size: 0.8125rem;
    color: #6b7280;
    font-style: italic;
    margin-top: 8px;
    line-height: 1.5;
  }

  /* ── Footnotes Section ── */
  .footnotes-section {
    margin-top: 48px;
    padding-top: 24px;
    border-top: 2px solid #e0ddd6;
  }

  .footnotes-section h3 {
    font-family: 'Inter', sans-serif;
    font-size: 0.8125rem;
    font-weight: 700;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin: 0 0 16px 0;
  }

  .footnotes-section ol {
    margin: 0;
    padding-left: 28px;
    counter-reset: footnote-counter;
    list-style: none;
  }

  .footnotes-section li {
    position: relative;
    font-size: 0.8125rem;
    line-height: 1.65;
    color: #6b7280;
    margin-bottom: 8px;
    padding-left: 4px;
    counter-increment: footnote-counter;
  }

  .footnotes-section li::before {
    content: counter(footnote-counter) ".";
    position: absolute;
    left: -24px;
    font-weight: 600;
    color: #9ca3af;
    font-family: 'Inter', sans-serif;
    font-size: 0.75rem;
  }

  .footnotes-section li:target {
    background: #fef3c7;
    border-radius: 4px;
    padding: 4px 8px;
    margin-left: -8px;
  }

  /* ── Emphasis patterns ── */
  .case-name-italic {
    font-style: italic;
  }

  /* ── Responsive ── */
  @media (max-width: 600px) {
    body { padding: 20px 16px 48px; }
    article { font-size: 15px; }
    article > header { grid-template-columns: 1fr; }
    h1 { font-size: 1.15rem; }
  }
</style>
`;

// ─── Core Transformer ──────────────────────────────────────────────

interface FootnoteEntry {
  num: number;
  content: string;
}

/**
 * Main entry point: transforms CURATED HTML into readable format.
 */
export function beautifyLegalDocument(html: string): string {
  // Quick check: if it doesn't look like a CURATED HTML document, return as-is
  if (!html.includes('[[FN ') && !html.includes('<article>')) {
    return html;
  }

  let result = html;

  // 1. Inject the reading stylesheet
  result = injectStylesheet(result);

  // 2. Process the opinion section(s): extract footnotes, split paragraphs
  result = processOpinionSections(result);

  return result;
}

// ─── Step 1: Inject Stylesheet ────────────────────────────────────

function injectStylesheet(html: string): string {
  if (html.includes('</head>')) {
    return html.replace('</head>', READING_CSS + '</head>');
  }
  // Fallback: prepend before the content
  return READING_CSS + html;
}

// ─── Step 2: Process Opinion Sections ─────────────────────────────

function processOpinionSections(html: string): string {
  // Match each opinion section's <p> content
  // Pattern: <section class="opinion...">...<p>CONTENT</p>...</section>
  const opinionRegex = /(<section\s+class="opinion[^"]*">\s*<h2>[^<]*<\/h2>\s*)<p>([\s\S]*?)<\/p>(\s*<\/section>)/gi;

  return html.replace(opinionRegex, (_match, prefix, rawContent, suffix) => {
    const { paragraphs, footnotes } = transformOpinionContent(rawContent);
    const bodyHtml = paragraphs.join('\n');
    const footnotesHtml = buildFootnotesSection(footnotes);
    return prefix + bodyHtml + footnotesHtml + suffix;
  });
}

// ─── Content Transformer ─────────────────────────────────────────

function transformOpinionContent(raw: string): { paragraphs: string[]; footnotes: FootnoteEntry[] } {
  const footnotes: FootnoteEntry[] = [];

  // 1. Extract and replace inline footnotes: [[FN N: content]]
  //    Also handle [[FN N: content text [[FN...]] nested ]] by non-greedy matching
  let text = extractFootnotes(raw, footnotes);

  // 2. Remove the duplicated footnote block at the end
  text = removeDuplicateFootnoteBlock(text, footnotes);

  // 3. Split into paragraphs and apply formatting
  const paragraphs = splitIntoParagraphs(text);

  return { paragraphs, footnotes };
}

/**
 * Extracts [[FN N: content]] markers from text, builds footnote entries,
 * and replaces them with superscript references.
 */
function extractFootnotes(text: string, footnotes: FootnoteEntry[]): string {
  const seen = new Set<number>();

  // Process from innermost to outermost by handling non-nested first
  // Pattern: [[FN N: content]]  — content may NOT contain another [[FN
  // We iterate to handle any nesting
  let result = text;
  let safety = 0;

  while (result.includes('[[FN ') && safety < 50) {
    safety++;
    result = result.replace(
      /\[\[FN\s+(\d+):\s*((?:(?!\[\[FN)[\s\S])*?)\]\]/g,
      (_m, numStr, content) => {
        const num = parseInt(numStr, 10);
        if (!seen.has(num)) {
          seen.add(num);
          footnotes.push({ num, content: content.trim() });
        }
        return `<a class="fn-ref" href="#fn-${num}" id="fnref-${num}" title="${escapeAttr(content.trim())}">[${num}]</a>`;
      }
    );
  }

  // Handle any remaining simple [[FN N: text]] without content
  result = result.replace(
    /\[\[FN\s+(\d+)\]\]/g,
    (_m, numStr) => {
      const num = parseInt(numStr, 10);
      return `<a class="fn-ref" href="#fn-${num}" id="fnref-${num}">[${num}]</a>`;
    }
  );

  // Sort footnotes by number
  footnotes.sort((a, b) => a.num - b.num);

  return result;
}

/**
 * Removes the duplicated footnote text that appears after "SO ORDERED."
 * The CURATED HTML appends all footnotes as plain text at the end of the <p>.
 */
function removeDuplicateFootnoteBlock(text: string, footnotes: FootnoteEntry[]): string {
  if (footnotes.length === 0) return text;

  // Find the last "SO ORDERED." occurrence
  const soOrderedIdx = text.lastIndexOf('SO ORDERED.');
  if (soOrderedIdx === -1) {
    // Try alternative endings
    const altIdx = text.lastIndexOf('SO ORDERED');
    if (altIdx === -1) return text;
    // Look for where the duplicated footnotes start after the concurrence line
    return trimDuplicatedFootnotes(text, altIdx);
  }

  return trimDuplicatedFootnotes(text, soOrderedIdx);
}

function trimDuplicatedFootnotes(text: string, soOrderedIdx: number): string {
  // Find the concurrence line after SO ORDERED (e.g., "Leonardo-De Castro, Bersamin, ... concur.")
  const afterSo = text.substring(soOrderedIdx);

  // Look for the pattern where duplicated footnotes begin:
  // After "concur." or after the SO ORDERED block, there's a sequence of
  // footnote references followed by their plain text duplicates
  // Example: "...concur.  <a class="fn-ref"...>[1]</a> Rollo, pp. 19-27..."
  //
  // The duplicated block starts when we see fn-ref followed immediately by the
  // footnote content text (not as a superscript in context, but as a standalone block)

  // Find the first fn-ref after concurrence
  const concurMatch = afterSo.match(/concur\.\s*(?:\*[^.]*\.\s*)?/i);
  if (concurMatch) {
    const concurEnd = soOrderedIdx + (concurMatch.index ?? 0) + concurMatch[0].length;

    // Check if what follows looks like a duplicated footnote block
    const remainder = text.substring(concurEnd);

    // If the remainder starts with an fn-ref, it's the duplicate block
    if (remainder.trimStart().startsWith('<a class="fn-ref"')) {
      // Keep everything up to and including the concurrence
      return text.substring(0, concurEnd).trimEnd();
    }
  }

  // Alternative: if SO ORDERED has fn-refs right after it, try to detect
  // the duplicate block by looking for a sequence of fn-ref + plain text pairs
  // This is a less precise fallback
  const fnDuplicatePattern = /(<a class="fn-ref"[^>]*>\[\d+\]<\/a>\s*[^<]+){3,}/;
  const dupMatch = afterSo.match(fnDuplicatePattern);
  if (dupMatch && dupMatch.index !== undefined) {
    // Check if this block appears after the main content ends
    const blockStart = soOrderedIdx + dupMatch.index;
    // Only trim if the block is near the end (within last 30% of content)
    if (blockStart > text.length * 0.7) {
      return text.substring(0, blockStart).trimEnd();
    }
  }

  return text;
}

/**
 * Splits the flat text into meaningful paragraphs.
 */
function splitIntoParagraphs(text: string): string[] {
  const result: string[] = [];

  // First, split on explicit newlines or double spaces that indicate breaks
  // In CURATED HTML, sentence boundaries before certain patterns indicate paragraphs
  let content = text.trim();

  // Normalize whitespace but preserve fn-ref tags
  content = content.replace(/\s{2,}/g, ' ');

  // Split at natural paragraph boundaries
  const segments = splitAtParagraphBoundaries(content);

  for (const segment of segments) {
    const trimmed = segment.trim();
    if (!trimmed) continue;

    const formatted = formatSegment(trimmed);
    if (formatted) {
      result.push(formatted);
    }
  }

  return result;
}

/**
 * Identifies natural paragraph boundaries in legal text.
 * Uses an iterative scan instead of complex lookbehind regexes to avoid
 * catastrophic backtracking on large documents with embedded HTML tags.
 */
function splitAtParagraphBoundaries(text: string): string[] {
  // Words/phrases that signal a new paragraph when they appear after ". "
  const breakStarters = new Set([
    'Meanwhile', 'Accordingly', 'Nevertheless', 'However', 'Consequently',
    'Further', 'Moreover', 'Thus', 'Hence', 'Verily', 'Given', 'Therefore',
    'Following', 'Applying', 'Guided', 'Amplifying', 'WHEREFORE',
  ]);

  // Multi-word starters (checked as prefix)
  const multiWordStarters = [
    'In view', 'In this case', 'In the case', 'In its ', 'In his ', 'In her ',
    'The NLRC', 'The CA ', 'The Court', 'The RTC', 'The Labor',
    'This Court', 'To these', 'From the foregoing', 'Against this',
    'We deny', 'We find', 'We disagree', 'We agree', 'We affirm',
    'We hold', 'We reverse', 'We do not',
    'SO ORDERED', 'OUR RULING', 'DISCUSSION', 'The Facts', 'FACTS',
    'THE ISSUE', 'ISSUES',
    'First issue', 'Second issue', 'Third issue', 'Fourth issue',
    'Fifth issue', 'Sixth issue',
  ];

  // Strip HTML tags for scanning but track positions relative to original text
  // Instead, we scan the text directly, skipping HTML tags

  const breakPoints = new Set<number>();

  // Find all positions of ". " (end of sentence) and check what follows
  let searchFrom = 0;
  while (searchFrom < text.length) {
    // Find ". " or ".) " patterns
    let dotIdx = text.indexOf('. ', searchFrom);
    if (dotIdx === -1) break;

    // Move past the ". " to find what comes after
    let afterDot = dotIdx + 2;

    // Skip any whitespace and HTML tags (fn-ref elements)
    while (afterDot < text.length) {
      if (text[afterDot] === ' ' || text[afterDot] === '\t' || text[afterDot] === '\n' || text[afterDot] === '\r') {
        afterDot++;
      } else if (text[afterDot] === '<') {
        // Skip entire HTML tag
        const tagEnd = text.indexOf('>', afterDot);
        if (tagEnd === -1) break;
        afterDot = tagEnd + 1;
      } else {
        break;
      }
    }

    if (afterDot >= text.length) break;

    const remaining = text.substring(afterDot);

    // Check single-word starters
    const nextWordMatch = remaining.match(/^([A-Z]\w*)/);
    if (nextWordMatch && breakStarters.has(nextWordMatch[1])) {
      breakPoints.add(afterDot);
    }

    // Check multi-word starters
    for (const starter of multiWordStarters) {
      if (remaining.startsWith(starter)) {
        breakPoints.add(afterDot);
        break;
      }
    }

    // Check date pattern: "On NN Month YYYY"
    if (/^On\s+\d{1,2}\s+\w+\s+\d{4}/.test(remaining)) {
      breakPoints.add(afterDot);
    }

    searchFrom = dotIdx + 1;
  }

  // Sort break points
  const sorted = Array.from(breakPoints).sort((a, b) => a - b);

  if (sorted.length === 0) {
    return [text];
  }

  const segments: string[] = [];
  let lastIdx = 0;
  for (const bp of sorted) {
    const segment = text.substring(lastIdx, bp).trim();
    if (segment) {
      segments.push(segment);
    }
    lastIdx = bp;
  }

  // Add the remainder
  const remainder = text.substring(lastIdx).trim();
  if (remainder) {
    segments.push(remainder);
  }

  return segments;
}

/**
 * Formats a single paragraph segment with appropriate HTML wrapping.
 */
function formatSegment(text: string): string {
  const plainText = text.replace(/<[^>]*>/g, '').trim();

  // Detect combined "SO ORDERED. <concurrence>" in one segment
  // This happens because the paragraph splitter breaks BEFORE "SO ORDERED"
  // but doesn't break between "SO ORDERED." and the concurrence names
  const soOrderedMatch = plainText.match(/^SO ORDERED\.?\s*(.*)/i);
  if (soOrderedMatch) {
    const soHtml = `<p class="so-ordered">SO ORDERED.</p>`;
    const afterSo = soOrderedMatch[1].trim();
    if (afterSo && /concur\.?\s*(\*.*)?$/i.test(afterSo)) {
      // Combined SO ORDERED + concurrence
      // Find the concurrence part in the original HTML (with tags)
      const soEndInHtml = text.search(/SO ORDERED\.?\s*/i);
      const soMatch = text.match(/SO ORDERED\.?\s*/i);
      const concurrenceHtml = text.substring(soEndInHtml + (soMatch?.[0].length ?? 12)).trim();
      return soHtml + '\n' + `<p class="concurrence">${concurrenceHtml}</p>`;
    }
    if (!afterSo) {
      return soHtml;
    }
    // SO ORDERED followed by non-concurrence text — just style SO ORDERED
    return soHtml + '\n' + `<p>${text.substring(text.search(/SO ORDERED\.?\s*/i) + (text.match(/SO ORDERED\.?\s*/i)?.[0].length ?? 12))}</p>`;
  }

  // Detect standalone concurrence lines (e.g., "Leonardo-De Castro, Bersamin, ... concur.")
  if (/^[A-Z][a-z].*concur\.?\s*(\*.*)?$/i.test(plainText) && plainText.length < 300) {
    return `<p class="concurrence">${text}</p>`;
  }

  // Detect issue headings
  if (/^(?:First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth)\s+(?:issue|Issue)[.:]/i.test(plainText)) {
    return `<div class="issue-heading">${text}</div>`;
  }

  // Detect ALL-CAPS section headings (short ones)
  if (/^[A-Z\s]{5,50}$/.test(plainText) && plainText.length < 60) {
    return `<div class="issue-heading">${text}</div>`;
  }

  // Detect article/section citations as blockquotes
  if (/^(?:Art\.\s*\d+|Sec(?:tion)?\.?\s*\d+|RULE\s+\d+|SECTION\s+\d+)/i.test(plainText)) {
    // If it's a long statutory text, wrap in blockquote
    if (plainText.length > 100) {
      return `<blockquote class="legal-provision">${text}</blockquote>`;
    }
  }

  // Detect block quotes: text that starts with "x x x" or is within quotes
  if (plainText.startsWith('x x x') || plainText.startsWith('X X X')) {
    return `<blockquote>${text}</blockquote>`;
  }

  // Default: wrap in paragraph
  return `<p>${text}</p>`;
}

// ─── Footnotes Section Builder ────────────────────────────────────

function buildFootnotesSection(footnotes: FootnoteEntry[]): string {
  if (footnotes.length === 0) return '';

  // Deduplicate footnotes by number, keeping the first occurrence
  const unique = new Map<number, FootnoteEntry>();
  for (const fn of footnotes) {
    if (!unique.has(fn.num)) {
      unique.set(fn.num, fn);
    }
  }

  const sorted = Array.from(unique.values()).sort((a, b) => a.num - b.num);
  const items = sorted.map(fn =>
    `<li id="fn-${fn.num}"><a href="#fnref-${fn.num}" class="fn-ref" style="font-size:0.8em;vertical-align:baseline;font-weight:400;">↩</a> ${escapeHtml(fn.content)}</li>`
  ).join('\n');

  return `
    <div class="footnotes-section">
      <h3>Footnotes</h3>
      <ol>
        ${items}
      </ol>
    </div>
  `;
}

// ─── Utilities ────────────────────────────────────────────────────

function escapeAttr(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .substring(0, 200); // Truncate for title attribute
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
```
