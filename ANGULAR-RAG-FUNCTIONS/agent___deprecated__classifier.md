# _deprecated / classifier

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `src` |
| **Role** | Source |
| **Bundle** | `agent___deprecated__classifier` |
| **Files** | 1 |
| **Total size** | 21,473 bytes |
| **Generated** | 2026-02-26 14:05 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `agent/_deprecated/classifier.ts` (21,473 bytes, Source)

---

## `agent/_deprecated/classifier.ts`

| Field | Value |
|-------|-------|
| **Role** | Source |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-18 |
| **Size** | 21,473 bytes |
| **Exports** | `ClassifierResult`, `classifyQueryIntent`, `classifyQueryIntentSync`, `extractTonalDirective`, `getTonalPromptText`, `QueryIntent`, `TonalDirective` |

```typescript
/**
 * V5.0 Hybrid Intent Classifier
 * Ported from robsky-ai-vertex to robsky-angular
 * 
 * Architecture: Regex Fast-Lane + Flash-Lite Fallback
 * 
 * Phase 1: High-confidence regex rules (0ms, $0)
 * Phase 2: gemini-2.5-flash-lite few-shot classifier (~700ms, ~$0.000028/query)
 */

import { GoogleGenAI, type GenerateContentResponse } from "@google/genai";

// V4.4 Intent Taxonomy — 15 distinct intents
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

// All valid intents for LLM output parsing
const VALID_INTENTS: QueryIntent[] = [
    'LOOKUP', 'DRAFTING', 'COMPUTATION', 'INSTRUCTIONAL',
    'STRATEGIC', 'COMPARATIVE', 'PEDAGOGICAL', 'RESEARCH',
    'CONVERSATIONAL', 'PREDICTIVE', 'ANALYTICAL', 'COMPLIANCE',
    'VERIFICATION', 'SUMMARIZATION', 'TEMPORAL',
];

// Intent pattern entry for the regex cascade
interface IntentPattern {
    intent: QueryIntent;
    patterns: RegExp[];
}

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

/** VERIFICATION patterns (checked before COMPLIANCE to prioritize "verify" verbs) */
const VERIFICATION_FAST_PATTERNS = [
    /\b(verify|fact[- ]?check|validate|confirm)\b/i,
    /\bstill (good law|valid|applicable|in effect|enforced)\b/i,
    /\bis it true\b/i,
    /\bis it correct\b/i,
    /\bare you sure\b/i,
];

/** Citation patterns → LOOKUP (when no competing verb present) */
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
// PHASE 2: FLASH-LITE FEW-SHOT CLASSIFIER (LLM Fallback)
// ══════════════════════════════════════════════════════════════

const FLASH_LITE_MODEL = "gemini-2.5-flash-lite";

const FLASH_LITE_SYSTEM_PROMPT = `You are an intent classifier for a Philippine Legal, Tax, and Accounting AI. Classify the user query into exactly one label.

LOOKUP — Cites a specific case, statute, standard, regulation, or asks for a digest/full text.
DRAFTING — Asks to prepare/draft/write/compose a legal document.
COMPUTATION — Asks to compute/calculate a numeric result.
INSTRUCTIONAL — Asks "how to", "steps to", "procedure for", "requirements for".
STRATEGIC — Asks about options, risks, strategy, pros/cons, best approach.
COMPARATIVE — Asks to compare/distinguish/contrast two or more concepts.
PEDAGOGICAL — Asks to teach, quiz, create exam questions, or practice problems.
RESEARCH — General legal/tax/accounting question. Default fallback.
CONVERSATIONAL — Follow-up referencing prior conversation. Only when [hasHistory=true].
PREDICTIVE — Asks to predict, forecast, or assess probability.
ANALYTICAL — Asks for statistics, counts, trends, or data analysis.
COMPLIANCE — Asks about deadlines, filing requirements, due dates.
VERIFICATION — Asks to verify, fact-check, or check if something is still valid/good law.
SUMMARIZATION — Starts with "summarize", "summary of", "key points".
TEMPORAL — Asks about timeline, chronology, evolution over time.

EXAMPLES:
"G.R. No. 163109" → LOOKUP
"Republic Act 10963" → LOOKUP
"IFRS 15 revenue recognition" → LOOKUP
"RR No. 12-2024" → LOOKUP
"draft a motion to dismiss" → DRAFTING
"prepare a certification against forum shopping" → DRAFTING
"compute my final pay" → COMPUTATION
"calculate withholding tax on P50,000" → COMPUTATION
"how to file a complaint" → INSTRUCTIONAL
"what are the requirements for filing a motion" → INSTRUCTIONAL
"compare illegal vs constructive dismissal" → COMPARATIVE
"what are the rules on double jeopardy?" → RESEARCH
"is adultery still a crime?" → VERIFICATION
"quiz me on labor law" → PEDAGOGICAL
"teach me about dismissal" → PEDAGOGICAL
"write a bar exam question about dismissal" → PEDAGOGICAL
"what are my options?" → STRATEGIC
"assess the risks of not filing" → STRATEGIC
"will I win this case?" → PREDICTIVE
"how many cases were filed in 2024?" → ANALYTICAL
"deadline for filing ITR" → COMPLIANCE
"when is the BIR deadline?" → COMPLIANCE
"summarize the TRAIN law" → SUMMARIZATION
"verify if Agabon is still good law" → VERIFICATION
"is this ruling still applicable?" → VERIFICATION
"timeline of labor law reforms" → TEMPORAL
"explain that" [hasHistory=true] → CONVERSATIONAL
"ok" [hasHistory=true] → CONVERSATIONAL
"what does that mean?" [hasHistory=true] → CONVERSATIONAL

Output ONLY the label, nothing else.`;

let _genaiClient: GoogleGenAI | null = null;

function getGenAIClient(): GoogleGenAI {
    if (!_genaiClient) {
        const apiKey = process.env.GEMINI_API_KEY;
        if (!apiKey) {
            throw new Error("[Classifier] GEMINI_API_KEY not set — Flash-Lite fallback unavailable");
        }
        _genaiClient = new GoogleGenAI({ apiKey });
    }
    return _genaiClient;
}

/**
 * Call Flash-Lite for nuanced classification.
 * Returns the classified intent plus latency for observability.
 */
async function classifyWithFlashLite(query: string, hasHistory: boolean): Promise<{ intent: QueryIntent; latencyMs: number }> {
    const client = getGenAIClient();
    const startTime = Date.now();

    const historyTag = hasHistory ? " [hasHistory=true]" : "";

    const response: GenerateContentResponse = await client.models.generateContent({
        model: FLASH_LITE_MODEL,
        contents: `Query: "${query}"${historyTag}`,
        config: {
            systemInstruction: FLASH_LITE_SYSTEM_PROMPT,
            temperature: 0.0,
            maxOutputTokens: 10,
        },
    });

    const latencyMs = Date.now() - startTime;
    const raw = (response.text || "").trim().toUpperCase();
    const matched = VALID_INTENTS.find(i => raw === i || raw.startsWith(i));
    const intent: QueryIntent = matched || "RESEARCH";

    return { intent, latencyMs };
}

// ══════════════════════════════════════════════════════════════
// LEGACY REGEX CASCADE (preserved for sync fallback)
// ══════════════════════════════════════════════════════════════

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

// Export for testing/introspection
export { VERB_INTENTS, LOOKUP_PATTERNS };

/**
 * Conversational pattern matching (extracted for clarity)
 * Only runs when hasHistory === true
 */
function matchesConversational(query: string): boolean {
    const conversationalPatterns = [
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
    return conversationalPatterns.some(p => p.test(query.trim()));
}

// ══════════════════════════════════════════════════════════════
// PUBLIC API
// ══════════════════════════════════════════════════════════════

export interface ClassifierResult {
    intent: QueryIntent;
    source: 'REGEX_FAST' | 'FLASH_LITE' | 'REGEX_FALLBACK';
    latencyMs: number;
}

/**
 * V5.0 HYBRID Classifier — Async (production entry point)
 * 
 * Phase 1: High-confidence regex fast-lane (0ms, $0)
 * Phase 2: Flash-Lite LLM fallback (~700ms, ~$0.000028)
 * 
 * Falls back to sync regex if GEMINI_API_KEY is not available.
 */
export async function classifyQueryIntent(
    query: string,
    hasHistory: boolean
): Promise<ClassifierResult> {
    // Phase 1: Regex fast-lane
    const fastResult = classifyFastLane(query, hasHistory);
    if (fastResult !== null) {
        return { intent: fastResult, source: 'REGEX_FAST', latencyMs: 0 };
    }

    // Phase 2: Flash-Lite LLM
    try {
        const { intent, latencyMs } = await classifyWithFlashLite(query, hasHistory);
        console.log(`[Classifier] Flash-Lite: "${query.substring(0, 40)}..." → ${intent} (${latencyMs}ms)`);
        return { intent, source: 'FLASH_LITE', latencyMs };
    } catch (error) {
        // Graceful degradation: fall back to sync regex
        console.warn(`[Classifier] Flash-Lite unavailable, falling back to regex:`, (error as Error).message);
        const intent = classifyQueryIntentSync(query, hasHistory);
        return { intent, source: 'REGEX_FALLBACK', latencyMs: 0 };
    }
}

/**
 * V4.4 SYNC Classifier — Regex only (preserved for tests & sync contexts)
 */
export function classifyQueryIntentSync(query: string, hasHistory: boolean): QueryIntent {
    // Phase 1: CONVERSATIONAL (history-gated)
    if (hasHistory && matchesConversational(query)) {
        return 'CONVERSATIONAL';
    }

    // Phase 2: Verb-based intents
    for (const entry of VERB_INTENTS) {
        if (entry.patterns.some(p => p.test(query))) {
            return entry.intent;
        }
    }

    // Phase 3: LOOKUP (citation-based)
    if (LOOKUP_PATTERNS.some(p => p.test(query))) {
        return 'LOOKUP';
    }

    // Phase 4: RESEARCH (fallback)
    return 'RESEARCH';
}

// ══════════════════════════════════════════════════════════════
// V5.2 TONAL DIRECTIVES
// ══════════════════════════════════════════════════════════════

export type TonalDirective =
    | 'SIMPLE' | 'FORMAL' | 'AGGRESSIVE' | 'CONCISE' | 'DETAILED' | 'CAUTIOUS'
    | null;

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

const TONAL_PROMPT_MAP: Record<Exclude<TonalDirective, null>, string> = {
    'SIMPLE': `\n\n🎯 TONAL DIRECTIVE: Explain in simple, plain language. Avoid legal jargon. Define any technical terms you must use. Write as if explaining to a non-lawyer client.`,
    'FORMAL': `\n\n🎯 TONAL DIRECTIVE: Use formal legal language and proper citation format. Write as if addressing a court or fellow counsel.`,
    'AGGRESSIVE': `\n\n🎯 TONAL DIRECTIVE: Adopt a persuasive, assertive tone. Emphasize strengths of position, identify weaknesses in opposing arguments. Write as if advocating zealously.`,
    'CONCISE': `\n\n🎯 TONAL DIRECTIVE: Be brief. Provide only the essential answer with key citations. Target 2-3 paragraphs maximum.`,
    'DETAILED': `\n\n🎯 TONAL DIRECTIVE: Provide a comprehensive, detailed analysis. Cover all relevant angles, cite supporting and opposing authority. Target a thorough treatment.`,
    'CAUTIOUS': `\n\n🎯 TONAL DIRECTIVE: Take a conservative, risk-averse approach. Emphasize requirements, risks of non-compliance, and safe harbors. Flag uncertainties explicitly.`,
};

export function getTonalPromptText(tone: TonalDirective): string {
    if (!tone) return '';
    return TONAL_PROMPT_MAP[tone] || '';
}
```
