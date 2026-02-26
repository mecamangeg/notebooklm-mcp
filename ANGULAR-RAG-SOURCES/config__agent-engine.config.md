# agent-engine.config

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `robsky-angular` |
| **Role** | Source |
| **Bundle** | `config__agent-engine.config` |
| **Files** | 1 |
| **Total size** | 682 bytes |
| **Generated** | 2026-02-26 11:01 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `app/config/agent-engine.config.ts` (682 bytes, Config)

---

## `app/config/agent-engine.config.ts`

| Field | Value |
|-------|-------|
| **Role** | Config |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-25 |
| **Size** | 682 bytes |
| **Exports** | `AGENT_ENGINE` |

```typescript
/**
 * Agent Engine Configuration
 *
 * Single source of truth for the Vertex AI Agent Engine endpoint.
 * Angular calls this REST API directly using a GCP OAuth2 token
 * obtained from Google Sign-In (cloud-platform scope).
 *
 * No proxy layer — no Cloud Functions — Angular → Agent Engine directly.
 */
export const AGENT_ENGINE = {
    PROJECT_ID: '775551928651',
    LOCATION: 'us-central1',
    ENGINE_ID: '3043741755288584192',
    get STREAM_URL(): string {
        return `https://${this.LOCATION}-aiplatform.googleapis.com/v1/projects/${this.PROJECT_ID}/locations/${this.LOCATION}/reasoningEngines/${this.ENGINE_ID}:streamQuery`;
    },
} as const;
```
