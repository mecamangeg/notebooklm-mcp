# document-viewer

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `robsky-angular` |
| **Role** | Source |
| **Bundle** | `components__document-viewer` |
| **Files** | 1 |
| **Total size** | 21,086 bytes |
| **Generated** | 2026-02-26 11:00 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `app/components/document-viewer/document-viewer.ts` (21,086 bytes, Source)

---

## `app/components/document-viewer/document-viewer.ts`

| Field | Value |
|-------|-------|
| **Role** | Source |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-25 |
| **Size** | 21,086 bytes |
| **Exports** | `DocumentViewerComponent` |

```typescript
import {
  Component, inject, signal, effect, viewChild,
  ElementRef, ChangeDetectionStrategy
} from '@angular/core';
import { DOCUMENT } from '@angular/common';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

import { DocumentViewerService } from '../../services/document-viewer.service';
import { AuthService } from '../../services/auth.service';
import { environment } from '../../../environments/environment';
import { beautifyLegalDocument } from '../../utils/document-beautifier';

@Component({
  selector: 'app-document-viewer',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [],
  styles: [`
    :host { display: contents; }

    /* ── Active state: panel with content ── */
    .document-viewer {
      display: flex;
      flex-direction: column;
      height: 100%;
      overflow: hidden;
      background: var(--bg-surface);
    }

    /* ── Empty/placeholder state ── */
    .document-viewer--empty {
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .document-viewer-placeholder {
      text-align: center;
      color: var(--text-muted);
      padding: 32px 24px;
    }

    .placeholder-icon {
      font-size: 40px;
      margin-bottom: 16px;
      opacity: 0.35;
      display: block;
    }

    .document-viewer-placeholder h3 {
      font-size: 0.9375rem;
      font-weight: 600;
      color: var(--text-secondary);
      margin-bottom: 8px;
    }

    .document-viewer-placeholder p {
      font-size: 0.8125rem;
      max-width: 240px;
    }

    /* ── Header bar ── */
    .viewer-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 8px 14px;
      border-bottom: 1px solid var(--border-color-subtle);
      background: var(--bg-surface);
      flex-shrink: 0;
    }

    .viewer-header-content {
      display: flex;
      align-items: center;
      gap: 8px;
      min-width: 0;
      flex: 1;
    }

    .viewer-title {
      font-size: 0.875rem;
      font-weight: 600;
      color: var(--text-primary);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      margin: 0;
    }

    .viewer-header-actions {
      display: flex;
      gap: 4px;
      flex-shrink: 0;
    }

    .viewer-action-button {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 30px;
      height: 30px;
      background: transparent;
      border: none;
      border-radius: 4px;
      color: var(--text-tertiary);
      cursor: pointer;
      transition: all 150ms ease;
    }

    .viewer-action-button:hover {
      background: var(--bg-surface-hover);
      color: var(--text-primary);
    }

    .viewer-close-button:hover {
      background: var(--error);
      color: white;
    }

    /* ── Content area ── */
    .viewer-content {
      flex: 1;
      overflow: hidden;
      position: relative;
    }

    /* The iframe fills 100% of the content area */
    .viewer-iframe {
      width: 100%;
      height: 100%;
      border: none;
      background: #faf9f7;
    }

    /* ── Loading state ── */
    .viewer-loading {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 12px;
      height: 100%;
      color: var(--text-tertiary);
      font-size: 0.875rem;
    }

    @keyframes spin {
      from { transform: rotate(0deg); }
      to   { transform: rotate(360deg); }
    }

    .animate-spin { animation: spin 1s linear infinite; }

    /* ── Error state ── */
    .viewer-error {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 12px;
      height: 100%;
      color: var(--error);
      padding: 24px;
      text-align: center;
    }

    .viewer-error button {
      padding: 8px 20px;
      background: var(--accent-primary);
      color: white;
      border: none;
      border-radius: 8px;
      cursor: pointer;
      font-size: 0.875rem;
      font-family: inherit;
      transition: background 0.2s;
    }

    .viewer-error button:hover { background: var(--accent-primary-hover); }
  `],
  template: `
    @if (docViewer.isOpen()) {
      <section class="document-viewer" aria-label="Document viewer">
        <div class="viewer-header">
          <div class="viewer-header-content">
            <span class="material-symbols-outlined" style="font-size:18px" aria-hidden="true">description</span>
            <h3 class="viewer-title" [title]="docViewer.activeDocument()?.title || 'Document'">
              {{ docViewer.activeDocument()?.title || 'Document' }}
            </h3>
          </div>
          <div class="viewer-header-actions">
            <button class="viewer-action-button" type="button"
                    aria-label="Open document in new tab"
                    (click)="openDocExternal()">
              <span class="material-symbols-outlined" style="font-size:16px" aria-hidden="true">open_in_new</span>
            </button>
            <button class="viewer-action-button viewer-close-button" type="button"
                    aria-label="Close document viewer"
                    (click)="docViewer.closeDocument()">
              <span class="material-symbols-outlined" style="font-size:18px" aria-hidden="true">close</span>
            </button>
          </div>
        </div>
        <div class="viewer-content">
          @if (loading()) {
            <div class="viewer-loading" role="status" aria-live="polite" aria-label="Loading document...">
              <span class="material-symbols-outlined animate-spin" style="font-size:32px" aria-hidden="true">progress_activity</span>
              <span>Loading document...</span>
            </div>
          } @else if (error()) {
            <div class="viewer-error" role="alert">
              <p>{{ error() }}</p>
              <button type="button" aria-label="Retry loading document" (click)="fetchDocument()">Retry</button>
            </div>
          } @else {
            <iframe
              #docIframe
              title="Document Viewer"
              sandbox="allow-scripts"
              class="viewer-iframe"
            ></iframe>
          }
        </div>
      </section>
    } @else {
      <div class="document-viewer document-viewer--empty" role="region" aria-label="Document viewer (no document selected)">
        <div class="document-viewer-placeholder">
          <span class="material-symbols-outlined placeholder-icon" aria-hidden="true">description</span>
          <h3 aria-hidden="true">Document Viewer</h3>
          <p>Click on a citation link to view the source document here.</p>
        </div>
      </div>
    }
  `
})
export class DocumentViewerComponent {
  protected readonly docViewer = inject(DocumentViewerService);
  private readonly authService = inject(AuthService);
  private readonly document = inject(DOCUMENT);
  private readonly http = inject(HttpClient);

  private readonly docIframeRef = viewChild<ElementRef<HTMLIFrameElement>>('docIframe');

  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);

  constructor() {
    effect(() => {
      const doc = this.docViewer.activeDocument();
      if (doc && this.docViewer.isOpen()) {
        this.fetchDocument();
      }
    });
  }

  openDocExternal() {
    const doc = this.docViewer.activeDocument();
    if (doc?.uri) {
      this.document.defaultView?.open(doc.uri, '_blank');
    }
  }

  async fetchDocument() {
    const doc = this.docViewer.activeDocument();
    if (!doc?.uri) return;

    this.loading.set(true);
    this.error.set(null);

    try {
      const idToken = await this.authService.getIdToken();
      const headers = idToken
        ? new HttpHeaders({ Authorization: `Bearer ${idToken}` })
        : new HttpHeaders();

      const rawHtml = await firstValueFrom(
        this.http.get(
          `${environment.functionsUrl}/documentContent?uri=${encodeURIComponent(doc.uri.trim().replace(/\\n/g, '').replace(/\n/g, ''))}`,
          { headers, responseType: 'text' }
        )
      );
      const html = beautifyLegalDocument(rawHtml);

      // Write to iframe after a tick (allows iframe to render in DOM first)
      setTimeout(() => this.writeToIframe(html), 50);
    } catch (err: unknown) {
      console.error('[DocumentViewer] Fetch error:', err);
      this.error.set(`Document unavailable. Please try refreshing.`);
    } finally {
      this.loading.set(false);
    }
  }

  private writeToIframe(html: string) {
    const iframe = this.docIframeRef()?.nativeElement;
    if (!iframe) return;

    const highlightText = this.docViewer.activeDocument()?.highlightText || '';
    const enhancedHtml = buildIframeHtml(html, highlightText);

    // Use a blob URL instead of document.write() so we don't need allow-same-origin
    // in the sandbox (which together with allow-scripts creates an escape vector).
    // Blob URLs are origin-isolated; the highlight script still runs inside the iframe.
    const blob = new Blob([enhancedHtml], { type: 'text/html; charset=utf-8' });
    const blobUrl = URL.createObjectURL(blob);

    // Revoke previous blob URL if one was set
    const prev = iframe.getAttribute('data-blob-url');
    if (prev) URL.revokeObjectURL(prev);

    iframe.setAttribute('data-blob-url', blobUrl);
    iframe.src = blobUrl;

    // Revoke after load to free memory (can't reuse blob URLs)
    iframe.onload = () => {
      URL.revokeObjectURL(blobUrl);
      iframe.removeAttribute('data-blob-url');
      iframe.onload = null;
    };
  }
}

// ── Iframe HTML builder (standalone function — avoids TS template-literal escaping issues) ──

const HIGHLIGHT_CSS = `<style id="robsky-highlight-styles">
  mark.robsky-highlight {
    background: linear-gradient(135deg, #fef08a 0%, #fde047 50%, #facc15 100%);
    padding: 2px 4px;
    border-radius: 3px;
    box-shadow: 0 0 0 2px rgba(250, 204, 21, 0.3), 0 2px 8px rgba(250, 204, 21, 0.2);
    color: #1a1a1a !important;
    font-weight: inherit;
    transition: all 0.3s ease;
    animation: robsky-highlight-pulse 2s ease-in-out;
    scroll-margin-top: 80px;
  }
  mark.robsky-highlight:first-of-type {
    outline: 2px solid #f59e0b;
    outline-offset: 2px;
  }
  @keyframes robsky-highlight-pulse {
    0% { box-shadow: 0 0 0 2px rgba(250, 204, 21, 0.3), 0 2px 8px rgba(250, 204, 21, 0.2); }
    50% { box-shadow: 0 0 0 6px rgba(250, 204, 21, 0.4), 0 4px 20px rgba(250, 204, 21, 0.3); }
    100% { box-shadow: 0 0 0 2px rgba(250, 204, 21, 0.3), 0 2px 8px rgba(250, 204, 21, 0.2); }
  }
</style>`;

function buildHighlightScript(highlightText: string): string {
  if (!highlightText) return '';

  // JSON.stringify safely encodes the text for embedding in JS
  const jsonText = JSON.stringify(highlightText);

  // The iframe script — uses regular string concatenation to avoid escaping issues
  return [
    '<script id="robsky-highlight-script">',
    '(function() {',
    '  var searchText = ' + jsonText + ';',
    '  if (!searchText || searchText.length < 10) return;',
    '',
    '  function normalize(s) {',
    '    return s',
    '      .replace(/\\[\\[FN\\s+\\d+:[\\s\\S]{0,500}?\\]\\]/g, " ")',  // [[FN N: ...]] in RetrievedContext.text
    '      .replace(/\\[\\d+\\]/g, "")',                               // [N] superscripts from beautifyLegalDocument()
    '      .replace(/<[^>]+>/g, "")',                                 // HTML tags (may appear in extractive segments)
    '      .replace(/&[a-z]+;/gi, " ")',                             // HTML entities
    '      .replace(/\\s+/g, " ")',
    '      .trim();',
    '  }',

    '',
    '  var bodyText = normalize(document.body.innerText || document.body.textContent || "");',
    '  var searchNorm = normalize(searchText);',
    '  var minLen = Math.min(20, Math.floor(searchNorm.length * 0.4));',
    '  var found = false;',
    '',
    '  for (var chunkLen = searchNorm.length; chunkLen >= minLen; chunkLen = Math.floor(chunkLen * 0.7)) {',
    '    var chunk = searchNorm.substring(0, chunkLen);',
    '    if (bodyText.indexOf(chunk) >= 0) {',
    '      found = highlightInDom(chunk);',
    '      if (found) break;',
    '    }',
    '  }',
    '',
    '  function highlightInDom(text) {',
    '    var walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);',
    '    var entries = [];',
    '    var origFull = "";',
    '    var n;',
    '    while (n = walker.nextNode()) {',
    '      var raw = n.textContent || "";',
    '      entries.push({ node: n, origStart: origFull.length, origLen: raw.length });',
    '      origFull += raw;',
    '    }',
    '',
    '    var normFull = normalize(origFull);',
    '    var matchIdx = normFull.indexOf(text);',
    '    if (matchIdx < 0) return false;',
    '    var matchEndN = matchIdx + text.length;',
    '',
    '    var normPos = 0;',
    '    var origMatchStart = -1, origMatchEnd = -1;',
    '    var inSpace = false;',
    '    for (var oi = 0; oi < origFull.length; oi++) {',
    '      var ch = origFull[oi];',
    '      if (/\\s/.test(ch)) {',
    '        if (!inSpace && normPos > 0) { inSpace = true; normPos++; }',
    '      } else {',
    '        inSpace = false;',
    '        if (normPos === matchIdx && origMatchStart < 0) origMatchStart = oi;',
    '        normPos++;',
    '        if (normPos >= matchEndN && origMatchEnd < 0) { origMatchEnd = oi + 1; break; }',
    '      }',
    '      if (origMatchStart < 0 && normPos > matchIdx) origMatchStart = oi;',
    '    }',
    '    if (origMatchStart < 0) origMatchStart = 0;',
    '    if (origMatchEnd < 0) origMatchEnd = origFull.length;',
    '',
    '    var firstMark = null;',
    '    for (var i = 0; i < entries.length; i++) {',
    '      var e = entries[i];',
    '      var nodeStart = e.origStart;',
    '      var nodeEnd = e.origStart + e.origLen;',
    '      if (nodeEnd <= origMatchStart || nodeStart >= origMatchEnd) continue;',
    '      var sliceStart = Math.max(0, origMatchStart - nodeStart);',
    '      var sliceEnd = Math.min(e.origLen, origMatchEnd - nodeStart);',
    '      if (sliceStart >= sliceEnd) continue;',
    '      try {',
    '        var targetNode = e.node;',
    '        if (sliceEnd < targetNode.textContent.length) targetNode.splitText(sliceEnd);',
    '        if (sliceStart > 0) targetNode = targetNode.splitText(sliceStart);',
    '        var mark = document.createElement("mark");',
    '        mark.className = "robsky-highlight";',
    '        targetNode.parentNode.insertBefore(mark, targetNode);',
    '        mark.appendChild(targetNode);',
    '        if (!firstMark) firstMark = mark;',
    '      } catch (ex) {',
    '        var parent = e.node.parentElement;',
    '        if (parent && !firstMark) {',
    '          var snippet = text.substring(0, Math.min(80, text.length));',
    // Use new RegExp constructor to avoid the regex-literal escaping issue
    '          var escaped = snippet.replace(new RegExp("[.*+?^${}()|[\\\\]\\\\\\\\]", "g"), "\\\\$&");',
    '          var re = new RegExp("(" + escaped + ")", "i");',
    '          if (re.test(parent.innerHTML)) {',
    '            parent.innerHTML = parent.innerHTML.replace(re, "<mark class=\\"robsky-highlight\\">$1</mark>");',
    '            firstMark = document.querySelector(".robsky-highlight");',
    '          }',
    '        }',
    '      }',
    '    }',
    '    if (firstMark) {',
    '      setTimeout(function() { firstMark.scrollIntoView({ behavior: "smooth", block: "center" }); }, 300);',
    '      return true;',
    '    }',
    '    return false;',
    '  }',
    '})();',
    '<\/script>'
  ].join('\n');
}

function buildIframeHtml(html: string, highlightText: string): string {
  const highlightScript = buildHighlightScript(highlightText);

  let enhanced = html;

  // ── Responsive viewport + site-override CSS ──
  // Injected into every iframe document so that external HTML (e.g. elibrary.judiciary.gov.ph)
  // renders readably inside the narrow panel instead of as a shrunken full-desktop layout.
  const VIEWPORT_AND_RESET = `
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style id="robsky-viewer-reset">
  *, *::before, *::after { box-sizing: border-box !important; }

  /* Single scrollbar: only body scrolls — html is locked to viewport height.
     Using height:100vh on html prevents the legacy E-Library page's own height
     styles from creating a second scroll context above the iframe's body. */
  html {
    overflow: hidden !important;
    height: 100vh !important;
    margin: 0 !important;
    padding: 0 !important;
  }

  body {
    overflow-x: hidden !important;
    overflow-y: auto !important;
    /* height:auto lets the body grow to its full content height.
       Only body scrolls — all child wrappers have overflow:visible. */
    height: auto !important;
    margin: 0 !important;
    padding: 0 !important;
    background: #faf9f7 !important;
    color: #1a1a1a !important;
    font-family: Georgia, 'Times New Roman', serif !important;
    font-size: 14px !important;
  }

  /* ── Exact elibrary.judiciary.gov.ph chrome to hide ── */

  /* Site header: "Supreme Court E-Library / Information At Your Fingertips" */
  #blog-line { display: none !important; }

  /* Top navigation bar (HOME, PHILIPPINE REPORTS, etc.) */
  #nav { display: none !important; }

  /* Right sidebar: search button, contact info, court seals, foreign courts */
  #right { display: none !important; }

  /* Footer: #appendix wrapper + #credits copyright text */
  #appendix,
  #credits { display: none !important; }

  /* "View printer friendly version" link at top of document */
  a[href*="showdocsfriendly"] { display: none !important; }
  div[align="right"]:has(a[href*="showdocsfriendly"]) { display: none !important; }

  /* ── Content area: #outline > #content > #left > .single_content ──
     Rule: ONLY body scrolls. Every layout wrapper must have
     height:auto and overflow-y:visible so they don't clip or
     create a nested scroll context that limits how far the user
     can scroll inside the iframe. */
  #outline {
    max-width: 100% !important;
    width: 100% !important;
    height: auto !important;
    overflow: visible !important;
  }

  #content,
  #content.clearfix {
    display: block !important;
    width: 100% !important;
    height: auto !important;
    overflow: visible !important;
  }

  #left {
    display: block !important;
    width: 100% !important;
    max-width: 100% !important;
    height: auto !important;
    overflow: visible !important;
    padding: 16px !important;
    float: none !important;
  }

  .single_content {
    width: 100% !important;
    max-width: 100% !important;
    font-size: 14px !important;
    line-height: 1.75 !important;
  }

  /* Make tables inside the document scrollable instead of overflowing */
  .single_content table {
    overflow-x: auto !important;
    display: block !important;
    max-width: 100% !important;
    border-collapse: collapse !important;
  }

  /* Override fixed inline widths (e.g. width="760") */
  .single_content [width] { width: auto !important; }

  /* Images should never overflow */
  img { max-width: 100% !important; height: auto !important; }

  /* Paragraphs */
  p { line-height: 1.75 !important; }

  /* Links */
  a { color: #b45309 !important; }
  a:hover { color: #92400e !important; }
</style>`;

  // Inject viewport + reset CSS into <head>, or prepend if no <head>
  if (enhanced.includes('</head>')) {
    enhanced = enhanced.replace('</head>', VIEWPORT_AND_RESET + '</head>');
  } else if (enhanced.includes('<head>')) {
    enhanced = enhanced.replace('<head>', '<head>' + VIEWPORT_AND_RESET);
  } else {
    // No <head> tag at all — prepend
    enhanced = VIEWPORT_AND_RESET + enhanced;
  }

  // Inject highlight CSS into <head>
  if (enhanced.includes('</head>')) {
    enhanced = enhanced.replace('</head>', HIGHLIGHT_CSS + '</head>');
  } else {
    enhanced = HIGHLIGHT_CSS + enhanced;
  }

  // Inject highlight script before </body>
  if (highlightScript) {
    if (enhanced.includes('</body>')) {
      enhanced = enhanced.replace('</body>', highlightScript + '</body>');
    } else {
      enhanced = enhanced + highlightScript;
    }
  }

  return enhanced;
}
```
