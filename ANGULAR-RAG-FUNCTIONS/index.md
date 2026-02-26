# index

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `src` |
| **Role** | Source |
| **Bundle** | `index` |
| **Files** | 1 |
| **Total size** | 18,702 bytes |
| **Generated** | 2026-02-26 14:05 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `index.ts` (18,702 bytes, Source)

---

## `index.ts`

| Field | Value |
|-------|-------|
| **Role** | Source |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-24 |
| **Size** | 18,702 bytes |
| **Exports** | `chat`, `documentContent` |

```typescript
﻿
import { onRequest } from "firebase-functions/v2/https";
import * as logger from "firebase-functions/logger";
import * as admin from "firebase-admin";
import { Storage } from "@google-cloud/storage";
import { streamQueryUnifiedEngine } from "./agent/unified-engine";
import { runPipelineStreaming } from "./agent/orchestrator";
import { env } from "./env";
import cors from "cors";

admin.initializeApp();

const corsHandler = cors({ origin: true });

/** Only these emails can use the API. Must match frontend whitelist. */
const ALLOWED_EMAILS = ["mecamangeg@gmail.com"];

/** Shared auth gate — reusable across endpoints */
async function verifyAuth(req: any, res: any): Promise<boolean> {
    const authHeader = req.headers.authorization;
    if (!authHeader?.startsWith("Bearer ")) {
        res.status(401).json({ error: "Missing or invalid Authorization header" });
        return false;
    }

    try {
        const token = authHeader.split("Bearer ")[1];
        const decoded = await admin.auth().verifyIdToken(token);
        const email = decoded.email?.toLowerCase();

        if (!email || !ALLOWED_EMAILS.includes(email)) {
            logger.warn(`[Auth] Rejected: ${email}`);
            res.status(403).json({ error: `Access denied. ${email} is not authorized.` });
            return false;
        }

        logger.info(`[Auth] Verified: ${email}`);
        return true;
    } catch (authErr) {
        logger.error("[Auth] Token verification failed", authErr);
        res.status(401).json({ error: "Invalid or expired token" });
        return false;
    }
}

// ═══════════════════════════════════════════════════════════
// Chat Endpoint (SSE streaming)
// Uses Vertex AI Search Answer API with streamAnswerQuery
// ═══════════════════════════════════════════════════════════

export const chat = onRequest({
    region: "us-central1",
    memory: "512MiB",
    timeoutSeconds: 300
}, async (req: any, res: any) => {
    return corsHandler(req, res, async () => {
        if (!(await verifyAuth(req, res))) return;

        res.setHeader("Content-Type", "text/event-stream");
        res.setHeader("Cache-Control", "no-cache");
        res.setHeader("Connection", "keep-alive");

        const sendEvent = (event: string, data: any) => {
            res.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);
        };

        // SSE heartbeat comment — prevents proxy timeout (every 15s)
        const sendHeartbeat = () => {
            res.write(`: heartbeat\n\n`);
        };

        try {
            const { messages, conversationId, vertexSessionId, enableToolCalling } = req.body;

            if (!messages || !Array.isArray(messages)) {
                res.status(400).send("Messages required");
                return;
            }

            const lastMessage = messages[messages.length - 1];
            const msgId = crypto.randomUUID();
            const requestStartMs = Date.now();

            logger.info(`[Chat] Query: ${lastMessage.content} | Pipeline: ${env.PIPELINE_VERSION}`);

            // ═══════════════════════════════════════════════
            // Feature Flag: Pipeline Version Routing
            // ═══════════════════════════════════════════════
            if (env.PIPELINE_VERSION === 'v2') {
                // ── Architecture C: Decoupled Pipeline ──
                await handleV2Pipeline(sendEvent, sendHeartbeat, messages, lastMessage, msgId, requestStartMs, res, { enableToolCalling });
            } else {
                // ── Architecture A: Unified Engine (existing) ──
                await handleV1Pipeline(sendEvent, sendHeartbeat, lastMessage, msgId, requestStartMs, conversationId, vertexSessionId, res);
            }

        } catch (error) {
            logger.error("[Chat] Error", error);
            sendEvent("error", { message: (error as Error).message });
            res.status(500).end();
        }
    });
});

// ═══════════════════════════════════════════════════════════════
// V1 Pipeline Handler (Architecture A — Unified Engine)
// ═══════════════════════════════════════════════════════════════

async function handleV1Pipeline(
    sendEvent: (event: string, data: any) => void,
    sendHeartbeat: () => void,
    lastMessage: any,
    msgId: string,
    requestStartMs: number,
    conversationId: string | undefined,
    vertexSessionId: string | undefined,
    res: any,
) {
    // ── Phase 1/3: Searching sources ──
    sendEvent("phase", {
        type: "searching",
        phaseIndex: 1,
        totalPhases: 3,
        label: "Searching sources...",
    });

    const heartbeatInterval = setInterval(sendHeartbeat, 15000);

    let chunkCount = 0;
    let firstDeltaMs = 0;
    let lastChunkMs = requestStartMs;
    const chunkTimings: number[] = [];

    const sessionForVertex = vertexSessionId || conversationId;
    logger.info(`[Chat:V1] Session: conversationId=${conversationId || 'NONE'} | vertexSessionId=${vertexSessionId || 'NONE'} | resolved=${sessionForVertex || 'NEW'}`);

    const result = await streamQueryUnifiedEngine(
        lastMessage.content,
        sessionForVertex,
        (chunk) => {
            if (chunk.isFinal) return;

            const nowMs = Date.now();

            if (chunkCount === 0 && chunk.answerText) {
                firstDeltaMs = nowMs - requestStartMs;
                sendEvent("phase", {
                    type: "analyzing",
                    phaseIndex: 2,
                    totalPhases: 3,
                    label: "Analyzing documents...",
                });
            }

            if (chunk.answerText) {
                chunkCount++;
                const interChunkMs = nowMs - lastChunkMs;
                chunkTimings.push(interChunkMs);
                lastChunkMs = nowMs;

                sendEvent("stream_delta", {
                    id: msgId,
                    role: "assistant",
                    delta: chunk.answerText,
                    fullText: chunk.fullText || chunk.answerText,
                });
            }
        },
    );

    clearInterval(heartbeatInterval);

    sendEvent("stream_done", { totalChunks: chunkCount });

    sendEvent("phase", {
        type: "synthesizing",
        phaseIndex: 3,
        totalPhases: 3,
        label: "Synthesizing response...",
    });

    sendEvent("stream_meta", {
        searchResultCount: result.debug.searchResultCount,
        citationCount: result.citations.length,
        answerSkippedReasons: result.answerSkippedReasons,
    });

    const assistantMessage = {
        id: msgId,
        role: "assistant",
        content: result.content,
        timestamp: new Date(),
        badge: result.badge,
        grounding: result.grounding,
        citations: result.citations,
        conversationId: result.debug.sessionId,
        relatedQuestions: result.relatedQuestions,
        answerSkippedReasons: result.answerSkippedReasons,
    };

    sendEvent("message", assistantMessage);

    const totalMs = Date.now() - requestStartMs;
    const avgInterChunkMs = chunkTimings.length > 1
        ? Math.round(chunkTimings.slice(1).reduce((a, b) => a + b, 0) / (chunkTimings.length - 1))
        : 0;
    logger.info(`[Chat:V1:Timing] TTFB=${firstDeltaMs}ms | Chunks=${chunkCount} | AvgInterval=${avgInterChunkMs}ms | Total=${totalMs}ms`);

    res.end();
}

// ═══════════════════════════════════════════════════════════════
// V2 Pipeline Handler (Architecture C — Decoupled Pipeline)
// ═══════════════════════════════════════════════════════════════

async function handleV2Pipeline(
    sendEvent: (event: string, data: any) => void,
    sendHeartbeat: () => void,
    messages: any[],
    lastMessage: any,
    msgId: string,
    requestStartMs: number,
    res: any,
    options?: { enableToolCalling?: boolean },
) {
    const heartbeatInterval = setInterval(sendHeartbeat, 15000);

    let chunkCount = 0;
    let firstDeltaMs = 0;

    // Build conversation history from messages array
    const conversationHistory = messages.slice(0, -1).map((m: any) => ({
        role: m.role as 'user' | 'assistant',
        content: m.content,
    }));
    const hasHistory = conversationHistory.length > 0;

    logger.info(`[Chat:V2] Pipeline start | hasHistory=${hasHistory} | historyTurns=${conversationHistory.length}`);

    const result = await runPipelineStreaming(
        {
            query: lastMessage.content,
            conversationHistory,
            hasHistory,
            enableToolCalling: options?.enableToolCalling,
        },
        {
            onPhase: (phase) => {
                sendEvent("phase", phase);
            },
            onChunk: (chunk) => {
                chunkCount++;
                if (chunkCount === 1) {
                    firstDeltaMs = Date.now() - requestStartMs;
                }
                sendEvent("stream_delta", {
                    id: msgId,
                    role: "assistant",
                    delta: chunk,
                    fullText: undefined, // V2 sends progressive deltas
                });
            },
            onMeta: (meta) => {
                sendEvent("stream_meta", {
                    searchResultCount: meta.searchResultCount,
                    citationCount: meta.citationCount,
                    intent: meta.intent,
                    domain: meta.domain,
                    answerSkippedReasons: [],
                });
            },
        },
    );

    clearInterval(heartbeatInterval);

    sendEvent("stream_done", { totalChunks: chunkCount });

    // Send the complete message with all metadata
    const assistantMessage = {
        id: msgId,
        role: "assistant",
        content: result.content,
        timestamp: new Date(),
        badge: result.badge,
        grounding: result.grounding,
        citations: result.citations,
        conversationId: msgId, // V2 doesn't have Vertex session IDs
        relatedQuestions: result.relatedQuestions,
        answerSkippedReasons: [],
        debug: result.debug,
    };

    sendEvent("message", assistantMessage);

    const totalMs = Date.now() - requestStartMs;
    logger.info(
        `[Chat:V2:Timing] TTFB=${firstDeltaMs}ms | Chunks=${chunkCount} | ` +
        `Classify=${result.debug.classifierLatencyMs}ms | Retrieval=${result.debug.retrievalLatencyMs}ms | ` +
        `Generation=${result.debug.generationLatencyMs}ms | Grounding=${result.debug.groundingLatencyMs}ms | ` +
        `Total=${totalMs}ms`
    );

    res.end();
}

// ═══════════════════════════════════════════════════════════
// Document Content Proxy
// Serves document HTML for the iframe viewer.
// Handles: gs://bucket/path (GCS) and elib://12345 (E-Library)
// Ported from Next.js /api/documents/content/route.ts
// ═══════════════════════════════════════════════════════════

let storageClient: Storage | null = null;
function getStorageClient(): Storage {
    if (!storageClient) {
        storageClient = new Storage();
    }
    return storageClient;
}

/** Basic HTML sanitization: strip scripts and event handlers */
function sanitizeHtml(html: string): string {
    // Remove script tags and their contents
    let clean = html.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '');
    // Remove event handlers (onclick, onload, onerror, etc.)
    clean = clean.replace(/\s+on\w+\s*=\s*["'][^"']*["']/gi, '');
    clean = clean.replace(/\s+on\w+\s*=\s*\S+/gi, '');
    return clean;
}

export const documentContent = onRequest({
    region: "us-central1",
    memory: "256MiB",
    timeoutSeconds: 30
}, async (req: any, res: any) => {
    return corsHandler(req, res, async () => {
        if (!(await verifyAuth(req, res))) return;

        const uri = req.query.uri as string;

        if (!uri) {
            res.status(400).json({ error: "Missing uri parameter" });
            return;
        }

        logger.info(`[ContentProxy] Request for: ${uri}`);

        try {
            // ── Handle GCS URIs: gs://bucket/path/to/file.html ──
            if (uri.startsWith("gs://")) {
                const gcsPath = uri.replace("gs://", "");
                const slashIndex = gcsPath.indexOf("/");

                if (slashIndex === -1) {
                    res.status(400).json({ error: "Invalid GCS URI" });
                    return;
                }

                const bucketName = gcsPath.substring(0, slashIndex);
                const objectPath = gcsPath.substring(slashIndex + 1);

                const storage = getStorageClient();
                const bucket = storage.bucket(bucketName);
                const file = bucket.file(objectPath);

                const [exists] = await file.exists();
                if (!exists) {
                    logger.warn(`[ContentProxy] File not found: ${objectPath}`);
                    res.status(404).json({ error: "File not found in storage" });
                    return;
                }

                const [fileContent] = await file.download();
                logger.info(`[ContentProxy] Downloaded from GCS: ${objectPath} (${fileContent.length} bytes)`);

                if (objectPath.endsWith(".html")) {
                    const sanitized = sanitizeHtml(fileContent.toString("utf-8"));
                    res.setHeader("Content-Type", "text/html");
                    res.setHeader("Cache-Control", "no-store");
                    res.send(sanitized);
                } else if (objectPath.endsWith(".pdf")) {
                    res.setHeader("Content-Type", "application/pdf");
                    res.setHeader("Cache-Control", "no-store");
                    res.send(fileContent);
                } else {
                    res.setHeader("Content-Type", "text/plain");
                    res.send(fileContent);
                }
                return;
            }

            // ── Handle elib:// URIs (Philippine Supreme Court E-Library) ──
            // Maps elib://55518 → https://elibrary.judiciary.gov.ph/thebookshelf/showdocs/1/55518
            if (uri.startsWith("elib://")) {
                const elibId = uri.replace("elib://", "");

                if (!elibId || !/^\d+$/.test(elibId)) {
                    res.status(400).json({ error: "Invalid elib URI format" });
                    return;
                }

                const elibUrl = `https://elibrary.judiciary.gov.ph/thebookshelf/showdocs/1/${elibId}`;
                logger.info(`[ContentProxy] Fetching from E-Library: ${elibUrl}`);

                const elibResponse = await fetch(elibUrl, {
                    headers: {
                        "User-Agent": "Mozilla/5.0 (compatible; ALT-AI-Viewer/1.0)",
                        "Accept": "text/html",
                    },
                    signal: AbortSignal.timeout(15000),
                });

                if (!elibResponse.ok) {
                    logger.error(`[ContentProxy] E-Library returned ${elibResponse.status}`);
                    res.status(502).json({ error: `E-Library returned ${elibResponse.status}` });
                    return;
                }

                // Auto-detect charset: Content-Type header → <meta charset> → utf-8 default.
                // The E-Library (Joomla-based) serves UTF-8. Hardcoding windows-1252 caused
                // `â€"` artifacts; hardcoding nothing used ISO-8859-1 causing single `â`.
                const rawBuffer = await elibResponse.arrayBuffer();
                const rawBytes = new Uint8Array(rawBuffer);

                let charset = 'utf-8';
                const ctHeader = elibResponse.headers.get('content-type') || '';
                const ctMatch = ctHeader.match(/charset=([^\s;,]+)/i);
                if (ctMatch) {
                    charset = ctMatch[1].toLowerCase();
                } else {
                    // Peek at first 2 KB (ASCII-safe) for <meta charset="...">
                    const head = new TextDecoder('ascii', { fatal: false }).decode(rawBytes.slice(0, 2048));
                    const metaMatch = head.match(/<meta[^>]+charset=["']?([^"';\s>]+)/i);
                    if (metaMatch) charset = metaMatch[1].toLowerCase();
                }

                const htmlContent = new TextDecoder(charset, { fatal: false }).decode(rawBuffer);
                logger.info(`[ContentProxy] Downloaded from E-Library: elib://${elibId} (${rawBuffer.byteLength} bytes, decoded as ${charset})`);

                const sanitized = sanitizeHtml(htmlContent);
                res.setHeader("Content-Type", "text/html; charset=utf-8");
                res.setHeader("Cache-Control", "no-store");
                res.setHeader("X-Doc-Source", "elib");
                res.send(sanitized);
                return;
            }

            res.status(400).json({ error: "Unsupported URI format. Supported: gs://, elib://" });

        } catch (error) {
            logger.error("[ContentProxy] Error:", error);
            res.status(500).json({ error: "Failed to fetch document content" });
        }
    });
});
```
