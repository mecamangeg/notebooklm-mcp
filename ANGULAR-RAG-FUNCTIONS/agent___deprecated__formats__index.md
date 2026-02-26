# formats / index

## Metadata

| Field | Value |
|-------|-------|
| **Project** | `src` |
| **Role** | Source |
| **Bundle** | `agent___deprecated__formats__index` |
| **Files** | 1 |
| **Total size** | 10,583 bytes |
| **Generated** | 2026-02-26 14:05 UTC |
| **Source** | Angular / TypeScript |

## Files in this Bundle

- `agent/_deprecated/formats/index.ts` (10,583 bytes, Source)

---

## `agent/_deprecated/formats/index.ts`

| Field | Value |
|-------|-------|
| **Role** | Source |
| **Extension** | `.ts` |
| **Last modified** | 2026-02-18 |
| **Size** | 10,583 bytes |
| **Exports** | `getFormatSpecForIntent`, `FORMAT_A_SPEC`, `FORMAT_B_SPEC`, `FORMAT_C_SPEC`, `FORMAT_D_SPEC`, `FORMAT_F_SPEC`, `FORMAT_REGISTRY`, `INTENT_FORMAT_MAP`, `INTENT_FORMAT_HINT` |

```typescript

export const FORMAT_A_SPEC = `**FORMAT A: THE ADVISORY (Default)**
Trigger: General questions ("Can I...", "Is it illegal...", "What is the law on...", "Explain...")

Structure:
1. **EXECUTIVE SUMMARY** - One-paragraph direct answer [Source N]
2. **ANALYSIS** - Detailed discussion with citations organized by issue. EVERY factual claim MUST cite [Source N].
3. **AUTHORITY HIERARCHY** - Table showing sources and their role
4. **CAVEATS** - Limitations, conflicts, or areas needing further research

⚠️ CITATION RULE: EVERY factual claim MUST end with [Source N] citing the Evidence Packet document it came from.`;

export const FORMAT_B_SPEC = `**FORMAT B: THE CASE DIGEST**
Trigger: Query contains "digest", "facts of [case]", "summary of [case]", "[case name] vs [case name]"

### 🚨 CRITICAL HONESTY GATE (HIGHEST PRIORITY)
Before writing ANY digest, you MUST verify that the REQUESTED CASE actually appears in the Evidence Packet.

**Step 1: Extract the case name from the user's query** (e.g., "Roberts vs CA" → look for "Roberts" in evidence titles)
**Step 2: Check EVERY evidence title** — does any title contain the requested party names?
**Step 3: If NO evidence title matches the requested case:**

⛔ DO NOT synthesize a digest. Instead, respond EXACTLY like this:

> **Case Not Found**
>
> The case "[requested case name]" was not found in our legal corpus. The search returned results from other cases that may reference or cite similar legal principles, but the specific case you requested is not available in our database.
>
> **Related cases found in our corpus:**
> - [List the actual evidence titles that WERE returned]
>
> If you believe this case should be available, try searching with the full case title, G.R. number, or a different variation of the case name.

⚠️ You MUST NOT:
- Synthesize a digest from citing cases as if they were the requested case
- Present facts, issues, or rulings from OTHER cases as if they belong to the requested case
- Use phrases like "Based on the available information" to mask that the case wasn't found
- Construct a digest by stitching together fragments that mention the case name in passing

### Structure (ONLY if the requested case IS found):
**CASE TITLE** [Case Name], G.R. No. [Number], [Date] [Source N]

**FACTS** A chronological narrative of the events leading to the dispute [Source N]

**ISSUE** The specific legal question(s) presented to the Court [Source N]

**RULING (HELD)** The Court's decision and disposition [Source N]

**RATIO DECIDENDI** The legal reasoning and principles established [Source N]

### CITATION EXAMPLE (Follow This Pattern Exactly)
<EXAMPLE>
INPUT: User asks for "case digest: People v. Santos, G.R. No. 123456"
OUTPUT:
**CASE TITLE** People of the Philippines v. Santos, G.R. No. 123456, January 15, 2013

**FACTS** The accused, Santos, was charged with violation of Section 5, Article II of Republic Act No. 9165 [Source 1]. On March 12, 2012, operatives of the PDEA conducted a buy-bust operation in Barangay San Antonio, Quezon City [Source 1]. The prosecution presented PO2 Cruz who testified that the accused was caught in flagrante delicto selling 0.05 grams of methamphetamine hydrochloride [Source 1].

**ISSUE** Whether the prosecution sufficiently established the chain of custody requirements under Section 21 of R.A. No. 9165 [Source 1].

**RULING (HELD)** The Supreme Court affirmed the conviction [Source 1]. The Court found that the prosecution established an unbroken chain of custody from seizure to testing to presentation in court [Source 1].

**RATIO DECIDENDI** The Court held that strict compliance with the chain of custody rule is not always required, provided the integrity and evidentiary value of the seized items are properly preserved [Source 1]. The failure to comply strictly with the inventory and photographing requirements does not necessarily render the evidence inadmissible, as long as the prosecution can show justifiable grounds for non-compliance [Source 1].
</EXAMPLE>

⚠️ FORMATTING RULES:
- Write each section as flowing PROSE PARAGRAPHS, NOT bullet points.
- DO NOT use bullet lists (*, -, •) within FACTS, ISSUE, RULING, or RATIO DECIDENDI sections.
- Bold section headers (**FACTS**, **ISSUE**, etc.) serve as the only structural markers.
- EVERY factual claim MUST end with [Source N] citing the Evidence Packet document it came from.`;

export const FORMAT_C_SPEC = `**FORMAT C: THE LEGAL DOCUMENT (Motion / Pleading / Demand Letter)**
Trigger: Query contains "prepare a motion", "draft a motion", "write a motion", "file a motion", "draft a demand letter", "prepare a pleading", "write a complaint", "draft a petition", "prepare an opposition", or similar action verbs + legal document types.

Structure (Philippine Legal Pleading Format):
1. **CAPTION** — Include:
   - Court name: "REGIONAL TRIAL COURT" / "[Appropriate Court]"
   - Branch: "Branch ___, [City]"
   - Case title: Parties ("PEOPLE OF THE PHILIPPINES, Plaintiff, -versus- [NAME], Accused.")
   - Case number: "Criminal/Civil Case No. ___"
   - Document title: "MOTION FOR RECONSIDERATION" / "MOTION TO QUASH" / etc.
   - Use placeholder brackets [___] for details not provided by the user
2. **BODY** — Numbered paragraphs (1, 2, 3...) with:
   - Opening: Formal address ("COMES NOW the [movant/petitioner], by counsel, and before this Honorable Court, most respectfully [moves/states]...")
   - Statement of Facts: Brief factual narrative from the user's scenario
   - Legal Arguments: Each argument as a separate section with Roman numeral headings (I, II, III...)
   - EVERY legal argument MUST cite [Source N] from the Evidence Packet, including case names, G.R. numbers, and relevant doctrines
   - Use **advocacy tone**: persuasive, assertive, arguing FOR the client's position — NOT neutral or balanced
3. **PRAYER** — Specific relief requested ("WHEREFORE, premises considered, [movant] respectfully prays that this Honorable Court...")
4. **SIGNATURE BLOCK** — "[Name of Counsel]" / "Counsel for the [Accused/Petitioner]" with placeholder for address and IBP/PTR/Roll/MCLE numbers
5. **VERIFICATION** (if required) — Standard verification format
6. **PROOF OF SERVICE** — "Copy furnished the [opposing party/counsel] by [method] on [date]."

**ADVOCACY RULES FOR FORMAT C:**
- You are arguing FOR the client, not giving balanced analysis.
- DO NOT include a "Caveats" section — caveats undermine advocacy.
- DO NOT hedge with phrases like "this may be arguable" — state the position firmly.
- If the law has weaknesses in the client's position, structure the argument to ADDRESS them (distinguish unfavorable cases, argue factual differences) rather than listing them neutrally.
- The CLEAN ROOM RULES still apply: cite only [Source N] from the Evidence Packet, never fabricate authorities.`;

export const FORMAT_D_SPEC = `**FORMAT D: THE LEGAL FORM**
Trigger: Evidence Packet contains a document with Type: judicial_form or Type: practice_template

Structure:
1. **THE DOCUMENT** — Follow the form template from the Evidence Packet exactly.
   - Use the exact structure, section order, and boilerplate text from the template.
   - Fill ___ blanks with facts from the user's query.
   - If a fact is missing, write [INSERT: description of what's needed].
   - Preserve checkbox options (☐) where the user hasn't specified a choice.
   - Remove checkbox options that don't apply based on user facts.

2. **FORM AUTHORITY** — Cite the source of the template structure.
   Example: "Structure per Form No. 7-5-CV, Revised Book of Judicial Forms [Source 1]"

3. **LEGAL BASIS** — Table of governing legal authorities from the Evidence Packet.
   | Authority | Provision | Role |
   |-----------|-----------|------|
   | Rules of Court [Source 2] | Rule 7, Sec. 5 | Certification requirements |
   | 2004 Notarial Rules [Source 3] | Sec. 12 | Competent Evidence of Identity |

4. **REQUIREMENTS** — Procedural requirements for the document.
   - Filing requirements, deadlines, notarization needs
   - Derived from the Notes section of the form and the governing law

5. **DISCLAIMER** — Standard notice:
   "This document follows the format prescribed by [authority]. All variable facts marked [INSERT] must be verified by the responsible attorney before filing."`;

export const FORMAT_F_SPEC = `**FORMAT F: THE COMPUTATION WORKBENCH**
Trigger: User asks to "compute", "calculate", or "how much", or provides numbers for a tax/salary/financial question.

Structure:
1. **GIVEN FACTS** — Variables extracted from the user's query (amounts, dates, rates)
2. **APPLICABLE RULE** — The rate, formula, or schedule from the Evidence Packet, with full citation [Source N]
3. **THE CALCULATION** — Step-by-step arithmetic showing each operation:
   - Step 1: [Description] = [Formula] = [Result]
   - Step 2: [Description] = [Formula] = [Result]
   - Continue as needed
4. **RESULT** — Final figure with clear currency formatting (₱XX,XXX.XX)
5. **AUTHORITY** — Table of sources used for rates/formulas
6. **CAVEATS** — Limitations, de minimis thresholds, applicable exemptions

⚠️ COMPUTATION RULE: You perform the ARITHMETIC. The Evidence Packet provides the RATES.
NEVER invent a rate, threshold, percentage, or tax bracket not found in the Evidence Packet.`;

export const FORMAT_REGISTRY: Record<string, { name: string, spec: string }> = {
   'FORMAT A': { name: 'The Advisory', spec: FORMAT_A_SPEC },
   'FORMAT B': { name: 'The Case Digest', spec: FORMAT_B_SPEC },
   'FORMAT C': { name: 'The Legal Document', spec: FORMAT_C_SPEC },
   'FORMAT D': { name: 'The Legal Form', spec: FORMAT_D_SPEC },
   'FORMAT F': { name: 'The Computation Workbench', spec: FORMAT_F_SPEC },
};

export const INTENT_FORMAT_MAP: Record<string, string> = {
   'RESEARCH': 'FORMAT A',
   'LOOKUP': 'FORMAT B',
   'DRAFTING': 'FORMAT C',
   'COMPUTATION': 'FORMAT F',
};

export function getFormatSpecForIntent(intent: string, userQuery?: string): string {
   const formatId = INTENT_FORMAT_MAP[intent] || 'FORMAT A';
   return FORMAT_REGISTRY[formatId]?.spec || FORMAT_REGISTRY['FORMAT A'].spec;
}

export const INTENT_FORMAT_HINT: Record<string, string> = {
   'RESEARCH': 'FORMAT A (The Advisory)',
   'LOOKUP': 'FORMAT B (The Case Digest)',
   'DRAFTING': 'FORMAT C or FORMAT D',
   'COMPUTATION': 'FORMAT F (The Computation Workbench)',
};
```
