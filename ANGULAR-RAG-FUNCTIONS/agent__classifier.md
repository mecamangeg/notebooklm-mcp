# agent / classifier

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `src` |
| **Role** | Source |
| **Bundle** | `agent__classifier` |
| **Files** | 1 |
| **Total size** | 26,826 bytes |
| **Generated** | 2026-02-26 14:05 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `agent/classifier.ts` (26,826 bytes, Source)

---

## `agent/classifier.ts`

| Field | Value |
|-------|-------|
| **Role** | Source |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-20 |
| **Size** | 26,826 bytes |
| **Exports** | `ClassifierResult`, `classifyDomain`, `extractTonalDirective`, `classifyQuery`, `QueryIntent`, `QueryDomain`, `TonalDirective` |

```typescript
/**
 * Architecture C — Query Router (Intent + Domain + Tonal Classification)
 *
 * Architecture: Two-phase hybrid classifier
 *   Phase 1: Regex Fast-Lane (0ms, $0) — covers ~80% of queries
 *   Phase 2: Flash-Lite LLM Fallback (~200ms, ~$0.000028/query)
 *
 * Post-Conversational Intelligence Refactor:
 *   - Intent classification now drives RAG optimization (pageSize, domain filters)
 *   - Intent NO LONGER drives prompt persona selection (unified persona always used)
 *   - CONVERSATIONAL intent signals the orchestrator to lighten/skip RAG retrieval
 *   - Regex fast-lane output feeds into model-config for pageSize and temperature
 */

import { GoogleGenAI, type GenerateContentResponse } from "@google/genai";
import { env } from '../env';

// ══════════════════════════════════════════════════════════════
// Types
// ══════════════════════════════════════════════════════════════

/** 15-intent taxonomy (V4.4) */
export type QueryIntent =
    | 'LOOKUP'
    | 'DRAFTING'
    | 'COMPUTATION'
    | 'INSTRUCTIONAL'
    | 'STRATEGIC'
    | 'COMPARATIVE'
    | 'PEDAGOGICAL'
    | 'RESEARCH'
    | 'CONVERSATIONAL'
    | 'PREDICTIVE'
    | 'ANALYTICAL'
    | 'COMPLIANCE'
    | 'VERIFICATION'
    | 'SUMMARIZATION'
    | 'TEMPORAL';

/** Domain classification */
export type QueryDomain = 'LEGAL' | 'TAX' | 'ACCOUNTING' | 'MIXED';

/** Tonal directive */
export type TonalDirective =
    | 'SIMPLE' | 'FORMAL' | 'AGGRESSIVE' | 'CONCISE' | 'DETAILED' | 'CAUTIOUS'
    | null;

/** Complete classification result */
export interface ClassifierResult {
    intent: QueryIntent;
    domain: QueryDomain;
    tone: TonalDirective;
    source: 'REGEX_FAST' | 'FLASH_LITE' | 'REGEX_FALLBACK';
    latencyMs: number;
}

// All valid intents
const VALID_INTENTS: QueryIntent[] = [
    'LOOKUP', 'DRAFTING', 'COMPUTATION', 'INSTRUCTIONAL',
    'STRATEGIC', 'COMPARATIVE', 'PEDAGOGICAL', 'RESEARCH',
    'CONVERSATIONAL', 'PREDICTIVE', 'ANALYTICAL', 'COMPLIANCE',
    'VERIFICATION', 'SUMMARIZATION', 'TEMPORAL',
];

const VALID_DOMAINS: QueryDomain[] = ['LEGAL', 'TAX', 'ACCOUNTING', 'MIXED'];

// ══════════════════════════════════════════════════════════════
// PHASE 1: HIGH-CONFIDENCE REGEX (Fast Lane)
// ══════════════════════════════════════════════════════════════

/** Bare greetings without history → RESEARCH (skip LLM) */
const GREETING_NO_HISTORY = /^(hello|hi|hey|good morning|good afternoon|good evening|yo|sup)\s*[!.?]?\s*$/i;

/** Conversational deictic markers — only with history */
const CONVERSATIONAL_PATTERNS = [
    /^(ok|okay|yes|no|sure|thanks|thank you|got it|alright|noted|right)\b/i,
    /\b(that|this|those|these|it|the above|above)\b/i,
    /^(explain|simplify|elaborate|clarify|go on|continue)\b/i,
    /^(what|how) (does|do|did|about|is) (that|this|it)\b/i,
    /^(can you|please) (simplify|explain|clarify|elaborate)/i,
    /^(tell me more|go on|continue|more detail)/i,
    /^(but what about|what if|and (?:what|how) about)\b/i,
    /^thanks?.+but\b/i,
    /^(create|write|draft|generate|make|prepare|compose)\b.*(from|based on|out of|about|for)\b.*(this|that|the|case|ruling|discussion)/i,
    /^(create|write|draft|generate|make)\b.*(bar question|motion|demand letter|quiz|outline|brief|review question)/i,
    /^now\b/i,
];

/** VERIFICATION patterns */
const VERIFICATION_FAST_PATTERNS = [
    /\b(verify|fact[- ]?check|validate|confirm)\b/i,
    /\bstill (good law|valid|applicable|in effect|enforced)\b/i,
    /\bis it true\b/i,
    /\bis it correct\b/i,
    /\bare you sure\b/i,
];

/** Citation patterns → LOOKUP */
const CITATION_FAST_PATTERNS = [
    /\bG\.?R\.?\s*(No\.?)?\s*\d/i,
    /\b(Republic Act|RA|R\.A\.)\s*(No\.?)?\s*\d/i,
    /\b(Presidential Decree|PD|P\.D\.)\s*(No\.?)?\s*\d/i,
    /\b(Executive Order|EO|E\.O\.)\s*(No\.?)?\s*\d/i,
    /\b(RR|RMC|RMO|Revenue Regulation)\s*(No\.?)?\s*\d/i,
    /\bcase digest[:;]\s/i,
    /\bfull text[:;]\s/i,
    /\b(IFRS|IAS|PAS|PFRS)\s*\d/i,
    /\bdigest of\b/i,
    /\bPeople\b.*\bvs?\.?\b/i,
    /\bvs?\.?\b.*\bC\.?A\.?\b/i,
    /\bdecision\s+in\b/i,
    /\bPIC\s*Q/i,
];

/** Clear DRAFTING verb + legal document noun */
const DRAFTING_FAST_PATTERNS = [
    /\b(draft|prepare|write|compose|make)\b.*\b(motion|complaint|affidavit|contract|deed|petition|answer|letter|pleading|memorandum|certification|agreement|notice|brief|comment|resolution|ordinance|writ|warrant|subpoena)\b/i,
];

/** Clear COMPUTATION verb */
const COMPUTATION_FAST_PATTERNS = [
    /\b(compute|calculate|how much|determine the (amount|tax|salary|pay))\b/i,
];

/** SUMMARIZATION at start of query */
const SUMMARIZATION_FAST_PATTERNS = [
    /^(summarize|summary of|tl;?dr|key points of|gist of|highlight)\b/i,
];

/**
 * Phase 1: Fast-lane regex classification.
 * Returns the intent if high-confidence, or null to defer to Flash-Lite.
 */
function classifyFastLane(query: string, hasHistory: boolean): QueryIntent | null {
    const trimmed = query.trim();

    // Rule 0: Bare greeting without history → RESEARCH
    if (!hasHistory && GREETING_NO_HISTORY.test(trimmed)) {
        return 'RESEARCH';
    }

    // Rule 1: Short queries with history → CONVERSATIONAL
    if (hasHistory && trimmed.length < 25) {
        return 'CONVERSATIONAL';
    }

    // Rule 2: Conversational deictic markers with history
    if (hasHistory && CONVERSATIONAL_PATTERNS.some(p => p.test(trimmed))) {
        return 'CONVERSATIONAL';
    }

    // Rule 3: VERIFICATION (before citations and compliance)
    if (VERIFICATION_FAST_PATTERNS.some(p => p.test(trimmed))) {
        return 'VERIFICATION';
    }

    // Rule 4: Citation LOOKUP (no competing verb)
    if (CITATION_FAST_PATTERNS.some(p => p.test(trimmed))) {
        const hasCompetingVerb =
            COMPUTATION_FAST_PATTERNS.some(p => p.test(trimmed)) ||
            DRAFTING_FAST_PATTERNS.some(p => p.test(trimmed));
        if (!hasCompetingVerb) {
            return 'LOOKUP';
        }
    }

    // Rule 5: DRAFTING
    if (DRAFTING_FAST_PATTERNS.some(p => p.test(trimmed))) {
        return 'DRAFTING';
    }

    // Rule 6: COMPUTATION
    if (COMPUTATION_FAST_PATTERNS.some(p => p.test(trimmed))) {
        return 'COMPUTATION';
    }

    // Rule 7: SUMMARIZATION
    if (SUMMARIZATION_FAST_PATTERNS.some(p => p.test(trimmed))) {
        return 'SUMMARIZATION';
    }

    // Not confident → defer to Flash-Lite
    return null;
}

// ══════════════════════════════════════════════════════════════
// DOMAIN CLASSIFICATION (Regex-based)
// ══════════════════════════════════════════════════════════════

const DOMAIN_PATTERNS: { domain: QueryDomain; patterns: RegExp[] }[] = [
    {
        domain: 'LEGAL',
        patterns: [
            /\bG\.?R\.?\s*(No\.?)?\s*\d/i,
            /\b(Republic Act|R\.?A\.?)\s*(No\.?)?\s*\d/i,
            /\bPeople\b.*\bvs?\.?\b/i,
            /\bjurisprudence\b/i,
            /\bSupreme Court\b/i,
            /\billegal dismissal\b/i,
            /\bRules of Court\b/i,
            /\bconstitution(al)?\b/i,
            /\bcriminal (law|case|offense)\b/i,
            /\bcivil (code|procedure|case)\b/i,
            /\blabor (code|law|case)\b/i,
            /\b(motion|petition|complaint|pleading|affidavit)\b/i,
        ],
    },
    {
        domain: 'TAX',
        patterns: [
            /\bBIR\b/i,
            /\bNIRC\b/i,
            /\bwithholding\b/i,
            /\b(ITR|income tax return)\b/i,
            /\bVAT\b/i,
            /\bRevenue (Regulation|Memorandum)/i,
            /\b(RR|RMC|RMO)\s*(No\.?)?\s*\d/i,
            /\btax(able|ation|payer)?\b/i,
            /\bexcise\b/i,
            /\bdonor'?s?\s*tax\b/i,
            /\bestate\s*tax\b/i,
            /\bcapital gains tax\b/i,
        ],
    },
    {
        domain: 'ACCOUNTING',
        patterns: [
            /\b(PFRS|PAS|IFRS|IAS)\s*\d/i,
            /\bjournal entr(y|ies)\b/i,
            /\bdepreciation\b/i,
            /\baudit(ing|or)?\b/i,
            /\bfinancial statements?\b/i,
            /\bPIC\s*Q/i,
            /\b(debit|credit)\s*(memo|note)\b/i,
            /\baccounting standard/i,
            /\brecognition\b.*\b(revenue|asset|liability)\b/i,
            /\b(revenue|asset|liability)\b.*\brecognition\b/i,
            /\bfair value\b/i,
            /\bimpairment\b/i,
        ],
    },
];

/**
 * Classify domain via regex patterns.
 * Returns MIXED if signals from multiple domains or no clear domain.
 */
export function classifyDomain(query: string): QueryDomain {
    const matches = new Set<QueryDomain>();

    for (const entry of DOMAIN_PATTERNS) {
        if (entry.patterns.some(p => p.test(query))) {
            matches.add(entry.domain);
        }
    }

    if (matches.size === 0) return 'MIXED';
    if (matches.size === 1) return [...matches][0];
    return 'MIXED'; // Multiple domains detected → MIXED
}

// ══════════════════════════════════════════════════════════════
// PHASE 2: FLASH-LITE CLASSIFIER (LLM Fallback with structured output)
// ══════════════════════════════════════════════════════════════

const CLASSIFIER_SYSTEM_PROMPT = `You are an intent and domain classifier for a Philippine Legal, Tax, and Accounting AI.
Classify the query into one intent label and one domain label.

INTENTS:
LOOKUP — Cites a specific case, statute, standard, regulation, or asks for a digest/full text.
DRAFTING — Asks to prepare/draft/write/compose a legal document.
COMPUTATION — Asks to compute/calculate a numeric result.
INSTRUCTIONAL — Asks "how to", "steps to", "procedure for", "requirements for".
STRATEGIC — Asks about options, risks, strategy, pros/cons, best approach.
COMPARATIVE — Asks to compare/distinguish/contrast two or more concepts.
PEDAGOGICAL — Asks to teach, quiz, create exam questions, or practice problems.
RESEARCH — General legal/tax/accounting question. Default fallback.
CONVERSATIONAL — Follow-up referencing prior conversation. Only when [hasHistory=true]. Signals the orchestrator to lighten RAG retrieval.
PREDICTIVE — Asks to predict, forecast, or assess probability.
ANALYTICAL — Asks for statistics, counts, trends, or data analysis.
COMPLIANCE — Asks about deadlines, filing requirements, due dates.
VERIFICATION — Asks to verify, fact-check, or check if something is still valid/good law.
SUMMARIZATION — Starts with "summarize", "summary of", "key points".
TEMPORAL — Asks about timeline, chronology, evolution over time.

DOMAINS:
LEGAL — Philippine law, jurisprudence, courts, statutes, case law.
TAX — Philippine taxation, BIR, NIRC, revenue regulations.
ACCOUNTING — PFRS, PAS, IFRS, IAS, audit, financial statements.
MIXED — Cross-domain or no clear domain signals.

EXAMPLES:
"G.R. No. 163109" → {"intent":"LOOKUP","domain":"LEGAL"}
"Republic Act 10963" → {"intent":"LOOKUP","domain":"LEGAL"}
"IFRS 15 revenue recognition" → {"intent":"LOOKUP","domain":"ACCOUNTING"}
"RR No. 12-2024" → {"intent":"LOOKUP","domain":"TAX"}
"draft a motion to dismiss" → {"intent":"DRAFTING","domain":"LEGAL"}
"prepare a certification against forum shopping" → {"intent":"DRAFTING","domain":"LEGAL"}
"compute my final pay" → {"intent":"COMPUTATION","domain":"LEGAL"}
"calculate withholding tax on P50,000" → {"intent":"COMPUTATION","domain":"TAX"}
"how to file a complaint" → {"intent":"INSTRUCTIONAL","domain":"LEGAL"}
"what are the requirements for filing a motion" → {"intent":"INSTRUCTIONAL","domain":"LEGAL"}
"compare illegal vs constructive dismissal" → {"intent":"COMPARATIVE","domain":"LEGAL"}
"what are the rules on double jeopardy?" → {"intent":"RESEARCH","domain":"LEGAL"}
"is adultery still a crime?" → {"intent":"VERIFICATION","domain":"LEGAL"}
"quiz me on labor law" → {"intent":"PEDAGOGICAL","domain":"LEGAL"}
"teach me about dismissal" → {"intent":"PEDAGOGICAL","domain":"LEGAL"}
"write a bar exam question about dismissal" → {"intent":"PEDAGOGICAL","domain":"LEGAL"}
"what are my options?" → {"intent":"STRATEGIC","domain":"MIXED"}
"assess the risks of not filing" → {"intent":"STRATEGIC","domain":"TAX"}
"will I win this case?" → {"intent":"PREDICTIVE","domain":"LEGAL"}
"how many cases were filed in 2024?" → {"intent":"ANALYTICAL","domain":"LEGAL"}
"deadline for filing ITR" → {"intent":"COMPLIANCE","domain":"TAX"}
"when is the BIR deadline?" → {"intent":"COMPLIANCE","domain":"TAX"}
"summarize the TRAIN law" → {"intent":"SUMMARIZATION","domain":"TAX"}
"verify if Agabon is still good law" → {"intent":"VERIFICATION","domain":"LEGAL"}
"is this ruling still applicable?" → {"intent":"VERIFICATION","domain":"LEGAL"}
"timeline of labor law reforms" → {"intent":"TEMPORAL","domain":"LEGAL"}
"explain that" [hasHistory=true] → {"intent":"CONVERSATIONAL","domain":"MIXED"}
"ok" [hasHistory=true] → {"intent":"CONVERSATIONAL","domain":"MIXED"}
"what does that mean?" [hasHistory=true] → {"intent":"CONVERSATIONAL","domain":"MIXED"}
"what are the elements of estafa?" → {"intent":"RESEARCH","domain":"LEGAL"}
"explain the Regalian Doctrine" → {"intent":"RESEARCH","domain":"LEGAL"}
"PFRS 9 impairment model" → {"intent":"LOOKUP","domain":"ACCOUNTING"}
"depreciation methods under PAS 16" → {"intent":"RESEARCH","domain":"ACCOUNTING"}

Output JSON with "intent" and "domain" fields only.`;

let _genaiClient: GoogleGenAI | null = null;

function getGenAIClient(): GoogleGenAI {
    if (!_genaiClient) {
        const apiKey = process.env.GEMINI_API_KEY;
        const projectId = env.GOOGLE_PROJECT_ID;

        if (projectId) {
            // Cloud Functions / Vertex AI mode — uses service account, no API key needed
            _genaiClient = new GoogleGenAI({
                vertexai: true,
                project: projectId,
                location: 'us-central1',
            });
        } else if (apiKey) {
            // Local dev mode — uses API key
            _genaiClient = new GoogleGenAI({ apiKey });
        } else {
            throw new Error("[Classifier] No GOOGLE_PROJECT_ID or GEMINI_API_KEY — Flash-Lite fallback unavailable");
        }
    }
    return _genaiClient;
}

/**
 * Call Flash-Lite for nuanced classification with structured JSON output.
 * Returns both intent and domain.
 */
async function classifyWithFlashLite(
    query: string,
    hasHistory: boolean
): Promise<{ intent: QueryIntent; domain: QueryDomain; latencyMs: number }> {
    const client = getGenAIClient();
    const startTime = Date.now();
    const historyTag = hasHistory ? " [hasHistory=true]" : "";

    const response: GenerateContentResponse = await client.models.generateContent({
        model: env.CLASSIFIER_MODEL || 'gemini-2.5-flash-lite',
        contents: `Query: "${query}"${historyTag}`,
        config: {
            systemInstruction: CLASSIFIER_SYSTEM_PROMPT,
            temperature: 0.0,
            maxOutputTokens: 50,
            responseMimeType: 'application/json',
            responseSchema: {
                type: 'OBJECT' as any,
                properties: {
                    intent: {
                        type: 'STRING' as any,
                        enum: VALID_INTENTS as string[],
                    },
                    domain: {
                        type: 'STRING' as any,
                        enum: VALID_DOMAINS as string[],
                    },
                },
                required: ['intent', 'domain'],
            },
        },
    });

    const latencyMs = Date.now() - startTime;

    let intent: QueryIntent = 'RESEARCH';
    let domain: QueryDomain = 'MIXED';

    try {
        const raw = (response.text || "").trim();
        const parsed = JSON.parse(raw);
        if (parsed.intent && VALID_INTENTS.includes(parsed.intent)) {
            intent = parsed.intent;
        }
        if (parsed.domain && VALID_DOMAINS.includes(parsed.domain)) {
            domain = parsed.domain;
        }
    } catch {
        // JSON parse failed — try raw text matching
        const raw = (response.text || "").trim().toUpperCase();
        const matched = VALID_INTENTS.find(i => raw === i || raw.startsWith(i));
        if (matched) intent = matched;
    }

    return { intent, domain, latencyMs };
}

// ══════════════════════════════════════════════════════════════
// LEGACY REGEX CASCADE (preserved for sync fallback)
// ══════════════════════════════════════════════════════════════

interface IntentPattern {
    intent: QueryIntent;
    patterns: RegExp[];
}

const VERB_INTENTS: IntentPattern[] = [
    {
        intent: 'DRAFTING',
        patterns: [
            /^(prepare|draft|write|compose|create|generate|make)\b.*(order|motion|resolution|deed|affidavit|contract|petition|complaint|answer|memorandum|brief|certificate|letter|notice|writ|warrant|subpoena)/i,
            /\bform no\b/i,
            /\bjudicial form\b/i,
            /\bjudicial affidavit\b/i,
            /\bcertification against forum shopping\b/i,
        ],
    },
    {
        intent: 'PEDAGOGICAL',
        patterns: [
            /(teach me|explain.+concept|quiz me|test me on|example of|bar\s+(?:exam(?:ination)?\s+)?question|(?:exam(?:ination)?|review|practice|sample)\s+question|tutorial|review question|practice problem|moot court|hypothetical|elements of)/i,
            /^(prepare|draft|write|compose|create|generate|make)\b.*\b(question|quiz|exam)\b/i,
        ],
    },
    {
        intent: 'PREDICTIVE',
        patterns: [
            /(predict|forecast|chances of|probability|will .+ win|likelihood|win or lose|outcome of)/i,
        ],
    },
    {
        intent: 'COMPUTATION',
        patterns: [
            /(compute|calculate|how much|salary|tax on|13th month|withholding|amortiz|final pay|overtime pay|separation pay|retirement pay|gross income|net income|taxable income)/i,
        ],
    },
    {
        intent: 'ANALYTICAL',
        patterns: [
            /(statistics|count of|how many cases|trend of|distribution|frequency|rate of|percentage of|data on)/i,
        ],
    },
    {
        intent: 'VERIFICATION',
        patterns: [
            /(verify|fact[- ]?check|is it true|validate|confirm if|is it correct|are you sure|still good law|still valid)/i,
        ],
    },
    {
        intent: 'SUMMARIZATION',
        patterns: [
            /^(summarize|summary of|tl;?dr|abstract|synopsis|key points|highlight|gist)/i,
        ],
    },
    {
        intent: 'COMPLIANCE',
        patterns: [
            /\bdeadline\b/i,
            /\bfiling\s+(requirements?|deadline|date|period|fee)/i,
            /(?<!\bnon-)compliance\b/i,
            /\brequirements for\b/i,
            /\bchecklist\b/i,
            /\bdue date\b/i,
            /\breporting requirement/i,
            /\bregulatory\b/i,
            /\bmust file\b/i,
            /\bmandatory\b/i,
        ],
    },
    {
        intent: 'COMPARATIVE',
        patterns: [
            /(compare|difference between|distinguish|\bvs\.?\b.*\bvs\.?\b|versus|similarities and differences)/i,
        ],
    },
    {
        intent: 'TEMPORAL',
        patterns: [
            /(timeline|chronology|history of|evolution of|when did|sequence of events|how has .+ changed)/i,
        ],
    },
    {
        intent: 'INSTRUCTIONAL',
        patterns: [
            /(how to|steps to|procedure|requirements for|process for|guide to|how do I|what are the steps)/i,
        ],
    },
    {
        intent: 'STRATEGIC',
        patterns: [
            /(options|risks|strategy|pros and cons|recommendation|what if|defend|assess|review this clause|best approach|evaluate|advisability)/i,
        ],
    },
];

const LOOKUP_PATTERNS: RegExp[] = [
    /case digest/i,
    /digest of/i,
    /summary of .+ vs/i,
    /G\.?R\.?\s*No/i,
    /Republic Act/i,
    /R\.?A\.?\s*(No\.?)?\s*\d/i,
    /IFRS\s*\d/i,
    /IAS\s*\d/i,
    /PIC\s*Q/i,
    /RR\s*No/i,
    /RMC\s*No/i,
    /\bvs?\.?\b.*\bC\.?A\.?\b/i,
    /\bvs?\.?\b.*\bPeople\b/i,
    /\bPeople\b.*\bvs?\.?\b/i,
    /\bdecision\s+in\b/i,
];

/**
 * Conversational pattern matching (history-gated)
 */
function matchesConversational(query: string): boolean {
    const patterns = [
        /^(summarize|explain|simplify|elaborate|clarify|rephrase)\b/i,
        /^(what|how) (does|do|did|about|is) (that|this|it|the above)\b/i,
        /^(can you|could you|please) (summarize|explain|simplify|elaborate|rephrase|break down)/i,
        /^(what does that mean|why is that|how so|in what way)\??$/i,
        /^(tell me more|go on|continue|more detail)/i,
        /^(but what about|what if|and (?:what|how) about)\b/i,
        /^thanks?.+but\b/i,
        /^(create|write|draft|generate|make|prepare|compose)\b.*(from|based on|out of|about|for)\b.*(this|that|the|case|ruling|discussion)/i,
        /^(create|write|draft|generate|make)\b.*(bar question|motion|demand letter|quiz|outline|brief|review question)/i,
        /^now\b/i,
        /^.{1,20}\??$/,
    ];
    return patterns.some(p => p.test(query.trim()));
}

/**
 * V4.4 SYNC Classifier — Regex only (fallback)
 */
function classifyQueryIntentSync(query: string, hasHistory: boolean): QueryIntent {
    if (hasHistory && matchesConversational(query)) {
        return 'CONVERSATIONAL';
    }
    for (const entry of VERB_INTENTS) {
        if (entry.patterns.some(p => p.test(query))) {
            return entry.intent;
        }
    }
    if (LOOKUP_PATTERNS.some(p => p.test(query))) {
        return 'LOOKUP';
    }
    return 'RESEARCH';
}

// ══════════════════════════════════════════════════════════════
// TONAL DIRECTIVES
// ══════════════════════════════════════════════════════════════

const TONAL_PATTERNS: { tone: Exclude<TonalDirective, null>; patterns: RegExp[] }[] = [
    {
        tone: 'SIMPLE',
        patterns: [
            /\b(simply|simple terms|layman|plain language|non-lawyer|basic|easy to understand)\b/i,
            /\b(ELI5|explain like)\b/i,
        ],
    },
    {
        tone: 'FORMAL',
        patterns: [
            /\b(formally|formal language|legal parlance|legal terms|professional tone)\b/i,
        ],
    },
    {
        tone: 'AGGRESSIVE',
        patterns: [
            /\b(aggressively|strong argument|persuasive|assertive|forceful|zealous)\b/i,
        ],
    },
    {
        tone: 'CONCISE',
        patterns: [
            /\b(briefly|concise|short answer|one paragraph|quick answer|in a nutshell)\b/i,
        ],
    },
    {
        tone: 'DETAILED',
        patterns: [
            /\b(in detail|detailed|comprehensive|thorough|exhaustive|full analysis)\b/i,
        ],
    },
    {
        tone: 'CAUTIOUS',
        patterns: [
            /\b(conservatively|conservative|cautious|safe approach|risk-averse|prudent)\b/i,
        ],
    },
];

export function extractTonalDirective(query: string): TonalDirective {
    for (const entry of TONAL_PATTERNS) {
        if (entry.patterns.some(p => p.test(query))) {
            return entry.tone;
        }
    }
    return null;
}

// ══════════════════════════════════════════════════════════════
// PUBLIC API
// ══════════════════════════════════════════════════════════════

/**
 * V5.0 HYBRID Classifier — Async (production entry point)
 *
 * Phase 1: High-confidence regex fast-lane (0ms, $0)
 * Phase 2: Flash-Lite LLM fallback with structured JSON output (~200ms)
 *
 * Returns intent, domain, and tonal directive.
 */
export async function classifyQuery(
    query: string,
    hasHistory: boolean
): Promise<ClassifierResult> {
    const tone = extractTonalDirective(query);

    // Phase 1: Regex fast-lane for intent
    const fastIntent = classifyFastLane(query, hasHistory);
    if (fastIntent !== null) {
        const domain = classifyDomain(query);
        return { intent: fastIntent, domain, tone, source: 'REGEX_FAST', latencyMs: 0 };
    }

    // Phase 2: Flash-Lite LLM (returns both intent + domain)
    try {
        const { intent, domain, latencyMs } = await classifyWithFlashLite(query, hasHistory);
        console.log(`[Classifier] Flash-Lite: "${query.substring(0, 40)}..." → ${intent}/${domain} (${latencyMs}ms)`);
        return { intent, domain, tone, source: 'FLASH_LITE', latencyMs };
    } catch (error) {
        // Graceful degradation: fall back to sync regex
        console.warn(`[Classifier] Flash-Lite unavailable, falling back to regex:`, (error as Error).message);
        const intent = classifyQueryIntentSync(query, hasHistory);
        const domain = classifyDomain(query);
        return { intent, domain, tone, source: 'REGEX_FALLBACK', latencyMs: 0 };
    }
}
```
