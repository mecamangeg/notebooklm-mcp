# _deprecated / templates

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `src` |
| **Role** | Source |
| **Bundle** | `agent___deprecated__templates` |
| **Files** | 1 |
| **Total size** | 816 bytes |
| **Generated** | 2026-02-26 14:05 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `agent/_deprecated/templates.ts` (816 bytes, Source)

---

## `agent/_deprecated/templates.ts`

| Field | Value |
|-------|-------|
| **Role** | Source |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-18 |
| **Size** | 816 bytes |
| **Exports** | `getPartnerConfig`, `getActiveTemplateId`, `buildThinkingConfigFromRole`, `PIPELINE_TEMPLATES`, `FALLBACK_MODEL`, `FALLBACK_THINKING_BUDGET`, `TUNED_PARTNER_INTENTS`, `TUNED_PARTNER_ENDPOINT` |

```typescript

export const PIPELINE_TEMPLATES = [
    {
        id: "balanced",
        partner: {
            model: "gemini-2.5-flash",
            temperature: 1.0,
            maxOutputTokens: 8192,
            thinking: { thinkingBudget: 4096 }
        }
    }
];

export function getPartnerConfig() { return PIPELINE_TEMPLATES[0].partner; }
export function getActiveTemplateId() { return "balanced"; }
export function buildThinkingConfigFromRole(thinking: any) {
    if (thinking.thinkingBudget) return { thinkingBudget: thinking.thinkingBudget };
    return {};
}
export const FALLBACK_MODEL = "gemini-2.5-flash";
export const FALLBACK_THINKING_BUDGET = 4096;
export const TUNED_PARTNER_INTENTS: string[] = ["SUMMARIZATION"];
export const TUNED_PARTNER_ENDPOINT = "gemini-2.5-flash"; // Placeholder
```
