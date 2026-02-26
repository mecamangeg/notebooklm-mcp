# app.routes.server

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `robsky-angular` |
| **Role** | Routes |
| **Bundle** | `app.routes.server` |
| **Files** | 1 |
| **Total size** | 239 bytes |
| **Generated** | 2026-02-26 11:07 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `app/app.routes.server.ts` (239 bytes, Routes)

---

## `app/app.routes.server.ts`

| Field | Value |
|-------|-------|
| **Role** | Routes |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-24 |
| **Size** | 239 bytes |
| **Exports** | `serverRoutes` |

```typescript
import { RenderMode, ServerRoute } from '@angular/ssr';

export const serverRoutes: ServerRoute[] = [
  {
    path: '**',
    renderMode: RenderMode.Client  // CSR: no server prerender — Firebase Auth and CDN caching safe
  }
];
```
