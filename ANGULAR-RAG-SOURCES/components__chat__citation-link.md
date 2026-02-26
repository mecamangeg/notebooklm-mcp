# citation-link

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `robsky-angular` |
| **Role** | Source |
| **Bundle** | `components__chat__citation-link` |
| **Files** | 1 |
| **Total size** | 2,185 bytes |
| **Generated** | 2026-02-26 11:07 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `app/components/chat/citation-link/citation-link.ts` (2,185 bytes, Source)

---

## `app/components/chat/citation-link/citation-link.ts`

| Field | Value |
|-------|-------|
| **Role** | Source |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-25 |
| **Size** | 2,185 bytes |
| **Exports** | `CitationLinkComponent` |

```typescript
import { Component, input, inject, ChangeDetectionStrategy } from '@angular/core';
import { Citation } from '../../../models/types';
import { DocumentViewerService } from '../../../services/document-viewer.service';

@Component({
  selector: 'app-citation-link',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <button
      class="citation-link"
      type="button"
      [class]="'tier-' + (citation().tier || 1)"
      (click)="handleClick()"
      [attr.aria-label]="'Source ' + citation().sourceNumber + ': ' + citation().title"
    >
      {{ citation().sourceNumber }}
    </button>
  `,
  styles: [`
    .citation-link {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 18px;
      height: 18px;
      padding: 0 4px;
      font-size: 10px;
      font-weight: 700;
      border-radius: 4px;
      border: none;
      cursor: pointer;
      vertical-align: super;
      margin: 0 2px;
      font-family: 'Outfit', sans-serif;
      transition: all 0.2s ease;
      background: var(--bg-surface-active);
      color: var(--text-secondary);
      box-shadow: var(--shadow-sm);

      &:hover {
        transform: scale(1.1);
        filter: brightness(1.1);
      }

      &.tier-1 { background: var(--tier-1); color: white; }
      &.tier-2 { background: var(--tier-2); color: white; }
      &.tier-3 { background: var(--tier-3); color: white; }
      &.tier-4 { background: var(--tier-4); color: white; }
    }
  `]
})
export class CitationLinkComponent {
  readonly citation = input.required<Citation>();
  readonly contextSnippet = input<string>();

  private readonly docViewer = inject(DocumentViewerService);

  handleClick() {
    // Prefer highlightText (full verbatim text, best for treewalk) over snippet.
    // Both are identical in our architecture but highlightText is semantically correct.
    const highlightText = this.citation().highlightText || this.citation().snippet || this.contextSnippet();
    this.docViewer.openDocument(
      this.citation().uri,
      this.citation().title,
      highlightText
    );
  }
}
```
