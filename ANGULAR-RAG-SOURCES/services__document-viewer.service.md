# document-viewer.service

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `robsky-angular` |
| **Role** | Source |
| **Bundle** | `services__document-viewer.service` |
| **Files** | 1 |
| **Total size** | 744 bytes |
| **Generated** | 2026-02-26 11:02 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `app/services/document-viewer.service.ts` (744 bytes, Service)

---

## `app/services/document-viewer.service.ts`

| Field | Value |
|-------|-------|
| **Role** | Service |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-17 |
| **Size** | 744 bytes |
| **Exports** | `DocumentViewerService`, `ViewDocument` |

```typescript
import { Injectable, signal } from '@angular/core';

export interface ViewDocument {
    uri: string;
    title: string;
    highlightText?: string;
}

@Injectable({
    providedIn: 'root'
})
export class DocumentViewerService {
    // Reactive state for the document viewer panel
    readonly activeDocument = signal<ViewDocument | null>(null);
    readonly isOpen = signal(false);

    openDocument(uri?: string, title?: string, highlightText?: string) {
        if (!uri) return;

        this.activeDocument.set({
            uri,
            title: title || 'Document',
            highlightText
        });
        this.isOpen.set(true);
    }

    closeDocument() {
        this.isOpen.set(false);
    }
}
```
