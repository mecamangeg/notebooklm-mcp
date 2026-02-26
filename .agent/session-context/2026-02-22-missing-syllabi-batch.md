# Session Context: Missing Syllabi Batch Processing
**Date:** 2026-02-22 | **Time checkpoint:** 17:02 PHT  
**Project:** `C:\PROJECTS\notebooklm-mcp`

---

## Objective

Generate `-generated-syllabi.md` files for **32 missing cases** so that `remaining_files.json` is fully processed and all files have corresponding entries in `with-generated-SYLLABI/`.

---

## What Was Done

### 1. Identification of Missing Files
- Created and ran `check_missing.py` → produced `actually_missing_files.json`
- **32 files confirmed missing** from `with-generated-SYLLABI/`
- The JSON is at: `C:\PROJECTS\notebooklm-mcp\actually_missing_files.json`

### 2. NotebookLM Pipeline Attempts
- Created notebook: **"Missing Case Digests Batch"** → `notebook_id: 9bdf69ab-1a33-443f-84b0-b0d6f960cbcc`
- Ran `notebook_digest_pipeline` for all 32 files → **ALL FAILED** with `"Query returned no answer"`
- Root cause identified: **NotebookLM refuses structured queries** (I. CAPTION, II. FACTS format) on sensitive criminal cases (rape, trafficking, etc.) due to content safety filters
- "Short summary" queries succeed, but formatted digest queries return empty strings

### 3. Sanitization Attempt (Incomplete)
- Created `sanitize_cases.py` → redacts explicit terms → outputs to `temp_clean/`
- Created sanitized versions of all 32 files in `C:\PROJECTS\notebooklm-mcp\temp_clean\`
- Created second notebook **"Sanitized Missing Cases"** → `notebook_id: 32f8623c-44dd-44c5-ab0f-7dd9e3549223`
- **Pipeline call was cancelled** before it ran — pipeline has NOT been executed on sanitized files yet

---

## Key Discovery: Root Cause of Failures

NotebookLM returns **empty answers** (not errors) for structured queries on:
- Sexual assault / rape cases
- Human trafficking cases
- Drug-facilitated crime cases

**Simple non-structured queries work fine** (e.g., "Provide a short summary of this case"). The `notebook_query` tool returns content successfully, but the `notebook_digest_pipeline` uses a rigid `DEFAULT_DIGEST_QUERY` with section headers (I. CAPTION, II. FACTS, III. ISSUES, IV. RULING) which seems to trigger the filter.

---

## The 32 Missing Files (from `actually_missing_files.json`)

```
2023\02_Feb\Navarro v. Cornejo, 935 Phil. 776 (G.R. No. 263329. February 8, 2023).md
2023\04_Apr\Palacio v. People, 940 Phil. 333 (G.R. No. 262473. April 12, 2023).md
2023\10_Oct\People v. Rodriguez, 948 Phil. 67 (G.R. No. 263603. October 9, 2023).md
2023\10_Oct\People v. Unknown, 948 Phil. 685 (G.R. No. 258054. October 25, 2023).md
2023\11_Nov\People v. Unknown, 949 Phil. 562 (G.R. No. 263553. November 20, 2023).md
2023\11_Nov\People v. Xxx, 949 Phil. 271 (G.R. No. 262520. November 13, 2023).md
2023\11_Nov\People v. Xxx, 949 Phil. 594 (G.R. No. 262812. November 22, 2023).md
2023\11_Nov\Unknown v. Unknown, 949 Phil. 236 (G.R. No. 261422. November 13, 2023).md
2024\01_Jan\People v. Saldivar, 950 Phil. 506 (G.R. No. 266754. January 29, 2024).md
2024\04_Apr\People v. Almero, 953 Phil. 93 (G.R. No. 269401. April 11, 2024).md
2024\04_Apr\People v. Arraz, 952 Phil. 685 (G.R. No. 262362. April 8, 2024).md
2024\05_May\People v. 'Freda,', 954 Phil. 834 (G.R. No. 267609. May 27, 2024).md
2024\05_May\People v. 'Sopingsofia', 954 Phil. 819 (G.R. No. 264039. May 27, 2024).md
2024\05_May\People v. Cañas, 954 Phil. 239 (G.R. No. 267360. May 15, 2024).md
2024\05_May\People v. Jjj, 954 Phil. 337 (G.R. No. 262749. May 20, 2024).md
2024\05_May\People v. Tuazon, 954 Phil. 851 (G.R. No. 267946. May 27, 2024).md
2024\06_Jun\People v. Zzz, 955 Phil. 733 (G.R. No. 266706. June 26, 2024).md
2024\08_Aug\People v. Batomalaque, 957 Phil. 512 (G.R. No. 266608. August 7, 2024).md
2024\10_Oct\People v. Bautista, 959 Phil. 1080 (G.R. No. 270003. October 30, 2024).md
2024\10_Oct\People v. Unknown, 959 Phil. 833 (G.R. No. 270317. October 23, 2024).md
2024\10_Oct\People v. Xxx, 959 Phil. 396 (G.R. No. 273190. October 16, 2024).md
2024\11_Nov\People v. Riddel', 961 Phil. 362 (G.R. No. 270174. November 26, 2024).md
2024\11_Nov\People v. Unknown, 960 Phil. 597 (G.R. No. 270870. November 11, 2024).md
2025\01_Jan\People v. Echanes (G.R. No. 272974. January 20, 2025).md
2025\01_Jan\People v. Unknown (G.R. No. 270897. January 14, 2025).md
2025\03_Mar\People v. Unknown (G.R. No. 234512. March 5, 2025).md
2025\04_Apr\People v. Bolagot (G.R. No. 267833. April 7, 2025).md
2025\04_Apr\People v. Xxx (G.R. No. 252606. April 2, 2025).md
2025\08_Aug\People v. Jakobsen (G.R. No. 277260. August 18, 2025).md
2025\08_Aug\People v. Unknown (G.R. No. 276383. August 6, 2025).md
2025\08_Aug\People v. Unknown (G.R. No. 276422. August 11, 2025).md
2025\08_Aug\People v. Zzz (G.R. No. 264132. August 13, 2025).md
```

---

## Source IDs Already Added to Notebook `9bdf69ab-...`

All 32 files were uploaded as sources to that notebook. Source ID mapping:

| File | source_id |
|------|-----------|
| Navarro v. Cornejo, Feb 2023 | 08aade81-16e3-47ae-b25e-e0ba5c091dbb |
| Palacio v. People, Apr 2023 | 2be5b28b-b265-4aa1-89a8-4dec3e325415 |
| People v. Rodriguez, Oct 2023 | 36a8ea19-0945-42c5-8405-e0c48055e315 |
| People v. Unknown, 948 Phil. 685 Oct 2023 | bb37fa90-2e41-43b8-a56c-444c717e2a71 |
| People v. Unknown, 949 Phil. 562 Nov 2023 | 8956e969-7252-4936-b44d-9fa203d2a6d1 |
| People v. Xxx, 949 Phil. 271 Nov 2023 | e69293dc-cf3a-4cec-960b-70058e4cf543 |
| People v. Xxx, 949 Phil. 594 Nov 2023 | 964ed9da-0db3-4f63-be25-be69a5cbdde0 |
| Unknown v. Unknown, 949 Phil. 236 Nov 2023 | 0b955327-16d6-4844-adfe-db1869621a71 |
| People v. Saldivar, Jan 2024 | ea9894ae-d9e6-42e4-9fe8-93c762c6b3cd |
| People v. Almero, Apr 2024 | 0e3ff27b-527a-495f-a647-174da2d2ca56 |
| People v. Arraz, Apr 2024 | 23dd3c57-37cf-4308-bd14-abc6b14acea2 |
| People v. 'Freda,', May 2024 | 7261f16c-50a2-4407-a597-e893ddbe836d |
| People v. 'Sopingsofia', May 2024 | 035bd2e9-d971-47d8-a48b-c98b15bf61b1 |
| People v. Cañas, May 2024 | 67e0e149-cbe8-456d-9d28-75317fcfeae3 |
| People v. Jjj, May 2024 | d222915d-7dcd-4653-88ab-43cbbfccda4f |
| People v. Tuazon, May 2024 | c822f3f6-f400-4cd8-a37b-27bb05d1ea6d |
| People v. Zzz, Jun 2024 | 296e257b-3ab7-491d-a3df-ec6ade82587e |
| People v. Batomalaque, Aug 2024 | 14059a3b-23de-4ecb-a09a-4a4a944c9bc1 |
| People v. Bautista, Oct 2024 | 45f60a9f-2fba-46d1-b166-ca9fd2e7a8b5 |
| People v. Unknown, 959 Phil. 833 Oct 2024 | 0a0317d6-b955-463c-acb7-3962e5d7ff26 |
| People v. Xxx, 959 Phil. 396 Oct 2024 | f894adcf-f3d1-4f12-83c6-45a0c702fc83 |
| People v. Riddel', Nov 2024 | 5b6966a3-4123-4ae0-975a-7e2fc427411f |
| People v. Unknown, 960 Phil. 597 Nov 2024 | b72519e5-daf3-4ee4-8d9d-cef2d44662fe |
| People v. Echanes, Jan 2025 | 1032cb8e-c0ec-4ff3-b33a-4e33f3c5fc5c |
| People v. Unknown, Jan 2025 (270897) | 169ca79a-0fb4-4a3a-90ff-7f0f814df0e9 |
| People v. Unknown, Mar 2025 (234512) | a9670a72-8090-4c63-99d7-9adc4f727c4c |
| People v. Bolagot, Apr 2025 | 03953d2b-bfc1-4f8b-a96c-949eab8dbda5 |
| People v. Xxx, Apr 2025 (252606) | b578a001-a969-452f-987e-37192119520b |
| People v. Jakobsen, Aug 2025 | d2a9cabe-c23b-4c5c-b68c-404f547eb567 |
| People v. Unknown, Aug 2025 (276383) | 224d6a61-2e9d-4632-aae6-15e22e55cba9 |
| People v. Unknown, Aug 2025 (276422) | 4131479b-1bfc-4b71-b11c-60f14ab9bc83 |
| People v. Zzz, Aug 2025 (264132) | 8e993ccc-71d8-4e5b-b18a-774462a90442 |

---

## Output Format Reference

Look at existing working `-generated-syllabi.md` files for the expected format:

`C:\PROJECTS\notebooklm-mcp\with-generated-SYLLABI\2023\08_Aug\People v. Celis, 945 Phil. 794 (G.R. No. 262197. August 14, 2023)-generated-syllabi.md`

The format is:
```
---
[frontmatter from the source .md file]
---

*Topic; Subtopic; *Very specific subsubtopic** — [Explanation verbatim from decision.]

*Topic; Subtopic; *Very specific subsubtopic** — [Explanation verbatim from decision.]
```

Each headnote is one line in SCRA format: `*Topic; Subtopic; *Subsubtopic** — Explanation.`

---

## Recommended Next Steps

### Option A: Use the generate-syllabi SKILL directly (agent reads + generates)
For each of the 32 files, the agent reads the `.md` source and generates syllabi using the `generate-syllabi` skill. Zero external API cost. Completely bypasses NotebookLM content filters.

**Procedure:**
1. Read `C:\PROJECTS\notebooklm-mcp\actually_missing_files.json`
2. For each file in the list:
   a. `view_file` the source `.md`
   b. Apply the `generate-syllabi` SKILL (from `C:\Users\Michael\.gemini\antigravity\skills\generate-syllabi\SKILL.md`)
   c. `write_to_file` the output to the correct path in `with-generated-SYLLABI/`
3. Output file naming: source path `\2023\02_Feb\Navarro v. Cornejo, 935 Phil. 776 (...).md` → `\with-generated-SYLLABI\2023\02_Feb\Navarro v. Cornejo, 935 Phil. 776 (...)-generated-syllabi.md`

### Option B: Use sanitized files with NotebookLM simple query
- Sanitized copies already exist in `C:\PROJECTS\notebooklm-mcp\temp_clean\`
- Notebook `32f8623c-44dd-44c5-ab0f-7dd9e3549223` ("Sanitized Missing Cases") is ready
- Upload sanitized files, query using a simple non-structured prompt
- Map output filenames back to original paths

**Option A is strongly recommended** — the generate-syllabi skill is specifically designed for this exact use case and produces higher-quality SCRA-format output than NotebookLM's default digest format.

---

## Files and Scripts Created This Session

| File | Purpose |
|------|---------|
| `C:\PROJECTS\notebooklm-mcp\check_missing.py` | Checks which files are missing; creates `actually_missing_files.json` |
| `C:\PROJECTS\notebooklm-mcp\actually_missing_files.json` | List of 32 source files that need syllabi |
| `C:\PROJECTS\notebooklm-mcp\sanitize_cases.py` | Redacts sensitive terms → outputs to `temp_clean/` |
| `C:\PROJECTS\notebooklm-mcp\temp_clean\` | 32 sanitized case files (ready for upload) |
| `C:\PROJECTS\notebooklm-mcp\move_digests.py` | Moves generated digests from `temp_digests/` to correct subfolders |
| `C:\PROJECTS\notebooklm-mcp\batch_query.py` | Iterates 32 sources; queries NotebookLM per source; saves output (**abandoned — returns empty for sensitive cases**) |
| `C:\PROJECTS\notebooklm-mcp\temp_digests\` | Empty (pipeline never produced any files) |
