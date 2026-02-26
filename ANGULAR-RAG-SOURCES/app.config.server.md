# app.config.server

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `robsky-angular` |
| **Role** | Config |
| **Bundle** | `app.config.server` |
| **Files** | 1 |
| **Total size** | 438 bytes |
| **Generated** | 2026-02-26 11:06 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `app/app.config.server.ts` (438 bytes, Config)

---

## `app/app.config.server.ts`

| Field | Value |
|-------|-------|
| **Role** | Config |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-17 |
| **Size** | 438 bytes |
| **Exports** | `config` |

```typescript
import { mergeApplicationConfig, ApplicationConfig } from '@angular/core';
import { provideServerRendering, withRoutes } from '@angular/ssr';
import { appConfig } from './app.config';
import { serverRoutes } from './app.routes.server';

const serverConfig: ApplicationConfig = {
  providers: [
    provideServerRendering(withRoutes(serverRoutes))
  ]
};

export const config = mergeApplicationConfig(appConfig, serverConfig);
```
