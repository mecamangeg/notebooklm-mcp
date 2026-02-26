# app.config

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `robsky-angular` |
| **Role** | Source |
| **Bundle** | `app.config` |
| **Files** | 1 |
| **Total size** | 1,420 bytes |
| **Generated** | 2026-02-26 11:06 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `app/app.config.ts` (1,420 bytes, Config)

---

## `app/app.config.ts`

| Field | Value |
|-------|-------|
| **Role** | Config |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-24 |
| **Size** | 1,420 bytes |
| **Exports** | `appConfig` |

```typescript

import { ApplicationConfig, provideZonelessChangeDetection } from '@angular/core';
import { provideRouter } from '@angular/router';

import { routes } from './app.routes';
// provideClientHydration removed: RenderMode.Client = pure CSR, no server HTML to hydrate from.
// Angular docs also explicitly state hydration is unsupported with zoneless/noop Zone.js
// (our provideZonelessChangeDetection() setup). Source: angular.dev/guide/hydration
import { provideHttpClient, withFetch } from '@angular/common/http';

import { provideFirebaseApp, initializeApp } from '@angular/fire/app';
import { provideAuth, getAuth } from '@angular/fire/auth';
import { provideFirestore, getFirestore } from '@angular/fire/firestore';
import { provideFunctions, getFunctions } from '@angular/fire/functions';
import { provideStorage, getStorage } from '@angular/fire/storage';
import { environment } from '../environments/environment';
import { provideMarkdown } from 'ngx-markdown';

export const appConfig: ApplicationConfig = {
  providers: [
    provideZonelessChangeDetection(),
    provideRouter(routes),
    provideHttpClient(withFetch()),
    provideMarkdown(),
    provideFirebaseApp(() => initializeApp(environment.firebase)),
    provideAuth(() => getAuth()),
    provideFirestore(() => getFirestore()),
    provideFunctions(() => getFunctions()),
    provideStorage(() => getStorage())
  ]
};
```
