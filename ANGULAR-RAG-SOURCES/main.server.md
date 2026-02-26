# main.server

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `robsky-angular` |
| **Role** | Source |
| **Bundle** | `main.server` |
| **Files** | 1 |
| **Total size** | 300 bytes |
| **Generated** | 2026-02-26 11:04 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `main.server.ts` (300 bytes, Source)

---

## `main.server.ts`

| Field | Value |
|-------|-------|
| **Role** | Source |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-17 |
| **Size** | 300 bytes |

```typescript
import { BootstrapContext, bootstrapApplication } from '@angular/platform-browser';
import { App } from './app/app';
import { config } from './app/app.config.server';

const bootstrap = (context: BootstrapContext) =>
    bootstrapApplication(App, config, context);

export default bootstrap;
```
