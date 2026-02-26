# environment.prod

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `robsky-angular` |
| **Role** | Environment Config |
| **Bundle** | `environments__environment.prod` |
| **Files** | 1 |
| **Total size** | 881 bytes |
| **Generated** | 2026-02-26 11:04 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `environments/environment.prod.ts` (881 bytes, Environment Config)

---

## `environments/environment.prod.ts`

| Field | Value |
|-------|-------|
| **Role** | Environment Config |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-25 |
| **Size** | 881 bytes |
| **Exports** | `environment` |

```typescript
export const environment = {
    production: true,
    devBypassAuth: false,  // always false in production
    // NOTE: functionsUrl now ONLY serves documentContent (GCS proxy).
    // All chat traffic goes directly to Agent Engine via AgentEngineService.
    functionsUrl: 'https://us-central1-robsky-ai.cloudfunctions.net',
    // Direct Agent Engine connection (Angular → Agent Engine, no proxy)
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
