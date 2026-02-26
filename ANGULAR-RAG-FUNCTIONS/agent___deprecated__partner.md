# _deprecated / partner

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `src` |
| **Role** | Source |
| **Bundle** | `agent___deprecated__partner` |
| **Files** | 1 |
| **Total size** | 3,563 bytes |
| **Generated** | 2026-02-26 14:05 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `agent/_deprecated/partner.ts` (3,563 bytes, Source)

---

## `agent/_deprecated/partner.ts`

| Field | Value |
|-------|-------|
| **Role** | Source |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-18 |
| **Size** | 3,563 bytes |
| **Exports** | `PartnerResult`, `runSeniorPartner` |

```typescript

import { GoogleGenAI, HarmCategory, HarmBlockThreshold } from "@google/genai";
import { buildSynthesisPrompt, getDateContext } from "./constitution";
import { EvidenceItem } from "./types";
import { env } from "../env";
import {
    getPartnerConfig,
    buildThinkingConfigFromRole,
    FALLBACK_MODEL,
    FALLBACK_THINKING_BUDGET
} from "./templates";

export interface PartnerResult {
    advisory: string;
    model: string;
    latencyMs: number;
}

let genai: GoogleGenAI | null = null;

function getClient(): GoogleGenAI {
    if (!genai) {
        genai = new GoogleGenAI({
            apiKey: env.GEMINI_API_KEY,
        });
    }
    return genai;
}

export async function runSeniorPartner(
    userQuery: string,
    evidencePacket: EvidenceItem[],
    paralegalSummary: string,
    queryIntent?: string
): Promise<PartnerResult> {
    const startTime = Date.now();
    const config = getPartnerConfig();
    const PARTNER_MODEL = config.model;
    const thinkingConfig = buildThinkingConfigFromRole(config.thinking);

    const client = getClient();
    const formattedEvidence = formatEvidenceForPrompt(evidencePacket);
    const synthesisPrompt = buildSynthesisPrompt(
        userQuery,
        paralegalSummary,
        formattedEvidence,
        queryIntent
    );

    const dateContext = getDateContext();
    const fullPrompt = `[System Note: ${dateContext}]\n\n${synthesisPrompt}`;

    try {
        const response = await client.models.generateContent({
            model: PARTNER_MODEL,
            contents: fullPrompt,
            config: {
                temperature: config.temperature,
                maxOutputTokens: config.maxOutputTokens,
                thinkingConfig: thinkingConfig,
                safetySettings: [
                    { category: HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold: HarmBlockThreshold.BLOCK_NONE },
                    { category: HarmCategory.HARM_CATEGORY_HARASSMENT, threshold: HarmBlockThreshold.BLOCK_NONE },
                    { category: HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold: HarmBlockThreshold.BLOCK_NONE },
                    { category: HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold: HarmBlockThreshold.BLOCK_NONE },
                ],
            },
        });

        return {
            advisory: response.text || "Unable to generate advisory.",
            model: PARTNER_MODEL,
            latencyMs: Date.now() - startTime
        };

    } catch (error) {
        console.warn(`[Partner] Fallback to ${FALLBACK_MODEL} due to error:`, error);
        // Fallback logic
        const response = await client.models.generateContent({
            model: FALLBACK_MODEL,
            contents: fullPrompt,
            config: {
                temperature: 1.0,
                maxOutputTokens: 4096,
                thinkingConfig: { thinkingBudget: FALLBACK_THINKING_BUDGET }
            },
        });

        return {
            advisory: response.text || "Unable to generate advisory.",
            model: `${FALLBACK_MODEL} (fallback)`,
            latencyMs: Date.now() - startTime
        };
    }
}

function formatEvidenceForPrompt(evidence: EvidenceItem[]): string {
    if (evidence.length === 0) return "No evidence found.";
    return evidence.map(item => `
<document id="${item.sourceId.replace(/\s+/g, '_').toLowerCase()}">
  <title>${item.title}</title>
  <content>${item.content}</content>
</document>`).join("\n\n");
}
```
