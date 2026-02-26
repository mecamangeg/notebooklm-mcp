# _deprecated / paralegal

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `src` |
| **Role** | Source |
| **Bundle** | `agent___deprecated__paralegal` |
| **Files** | 1 |
| **Total size** | 4,174 bytes |
| **Generated** | 2026-02-26 14:05 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `agent/_deprecated/paralegal.ts` (4,174 bytes, Source)

---

## `agent/_deprecated/paralegal.ts`

| Field | Value |
|-------|-------|
| **Role** | Source |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-18 |
| **Size** | 4,174 bytes |
| **Exports** | `ParalegalResult`, `runParalegalLoop` |

```typescript

import { GoogleGenAI, type Content, type FunctionCall } from "@google/genai";
import { legalToolsObject } from "./tools";
import { PARALEGAL_CONSTITUTION } from "./constitution";
import { executeSearch, getDocumentByCitation } from "./implementations";
import { EvidenceItem } from "./types";
import { env } from "../env";

const MAX_TURNS = 3;

export interface ParalegalResult {
    evidence: EvidenceItem[];
    summary: string;
    turns: number;
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

export async function runParalegalLoop(
    userQuery: string,
    conversationHistory?: Content[]
): Promise<ParalegalResult> {
    const startTime = Date.now();
    const client = getClient();
    const evidence: EvidenceItem[] = [];
    let turns = 0;
    let summary = "";

    const contents: Content[] = conversationHistory ? [...conversationHistory] : [];
    contents.push({ role: 'user', parts: [{ text: userQuery }] });

    try {
        let response = await client.models.generateContent({
            model: 'gemini-2.5-flash',
            contents: contents,
            config: {
                systemInstruction: PARALEGAL_CONSTITUTION,
                tools: [legalToolsObject] as any,
            },
        });

        while (turns < MAX_TURNS) {
            const candidate = response.candidates?.[0];
            const parts = candidate?.content?.parts || [];
            const calls = parts.filter(p => p.functionCall).map(p => p.functionCall as FunctionCall);

            if (calls.length === 0) break;

            turns++;
            const functionResponses = await Promise.all(calls.map(async (call) => {
                const result = await executeToolCall(call);
                if (Array.isArray(result)) {
                    result.forEach(item => {
                        if (!evidence.find(e => e.citation.uri === item.citation.uri)) {
                            evidence.push(item);
                        }
                    });
                } else if (result && (result as any).evidence) {
                    (result as any).evidence.forEach((item: any) => {
                        if (!evidence.find(e => e.citation.uri === item.citation.uri)) {
                            evidence.push(item);
                        }
                    });
                }

                return {
                    functionResponse: {
                        name: call.name,
                        response: { result: result }
                    }
                };
            }));

            contents.push({ role: 'model', parts: parts });
            contents.push({ role: 'user', parts: functionResponses as any });

            response = await client.models.generateContent({
                model: 'gemini-2.5-flash',
                contents: contents,
                config: {
                    systemInstruction: PARALEGAL_CONSTITUTION,
                    tools: [legalToolsObject] as any,
                },
            });
        }

        summary = response.text || `Gathered ${evidence.length} documents.`;

    } catch (error) {
        console.error("[Paralegal] Loop Error:", error);
        summary = `Error: ${(error as Error).message}`;
    }

    return {
        evidence,
        summary,
        turns,
        latencyMs: Date.now() - startTime
    };
}

async function executeToolCall(call: FunctionCall): Promise<any> {
    const { name, args } = call;
    const params = args as any;

    switch (name) {
        case "search_legal_corpus":
            return await executeSearch(params.query, params.filter_tier, params.domain, params.search_mode, params.sort_by, params.doc_type);
        case "get_document_by_citation":
            const doc = await getDocumentByCitation(params.citation);
            return doc ? [doc] : [];
        default:
            return null;
    }
}
```
