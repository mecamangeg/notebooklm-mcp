# main

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `robsky-angular` |
| **Role** | Source |
| **Bundle** | `main` |
| **Files** | 1 |
| **Total size** | 315 bytes |
| **Generated** | 2026-02-26 11:05 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `main.ts` (315 bytes, Source)

---

## `main.ts`

| Field | Value |
|-------|-------|
| **Role** | Source |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-18 |
| **Size** | 315 bytes |

```typescript
import { bootstrapApplication } from '@angular/platform-browser';
import { appConfig } from './app/app.config';
import { App } from './app/app';

console.log('Bootstrapping app...');
bootstrapApplication(App, appConfig)
  .then(() => console.log('App bootstrapped!'))
  .catch((err) => console.error(err));
```
