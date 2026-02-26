# environment

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `robsky-angular` |
| **Role** | Environment Config |
| **Bundle** | `environments__environment` |
| **Files** | 1 |
| **Total size** | 928 bytes |
| **Generated** | 2026-02-26 11:04 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `environments/environment.ts` (928 bytes, Environment Config)

---

## `environments/environment.ts`

| Field | Value |
|-------|-------|
| **Role** | Environment Config |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-25 |
| **Size** | 928 bytes |
| **Exports** | `environment` |

```typescript
export const environment = {
  production: false,
  devBypassAuth: false,  // Was true during debug panel testing — keep false for normal dev
  // NOTE: functionsUrl now ONLY serves documentContent (GCS proxy) in local dev.
  // Chat traffic goes directly to Agent Engine (live production) even in local dev.
  functionsUrl: 'http://localhost:5001/robsky-ai/us-central1',
  // Direct Agent Engine connection — same endpoint in dev and prod
  // (Agent Engine cannot be run locally; always uses live production)
  agentEngine: {
    projectId: '775551928651',
    location: 'us-central1',
    engineId: '3043741755288584192',
  },
  firebase: {
    apiKey: "AIzaSyDa12JMdrf7QyS35EFIbsakZ8eDlYakV5M",
    authDomain: "robsky-ai.firebaseapp.com",
    projectId: "robsky-ai",
    storageBucket: "robsky-ai.firebasestorage.app",
    messagingSenderId: "775551928651",
    appId: "1:775551928651:web:89eecb33e14e1045d400ce"
  }
};
```
