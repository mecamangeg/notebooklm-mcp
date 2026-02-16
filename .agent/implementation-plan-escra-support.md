# Implementation Plan: e-SCRA Corpus Support

> **Created**: 2026-02-16 14:20 PHT  
> **Status**: Draft — awaiting review  
> **Scope**: Add e-SCRA markdown corpus support to the existing NotebookLM MCP server  
> **Baseline tag**: `v1.0-sc-elibrary` (current `main`)

---

## 1. Problem Statement

The MCP server's batch digest pipeline (`notebook_digest_multi`) is currently hardcoded for the **SC e-Library** corpus:

- Frontmatter field names: `doc_id`, `docket_number`, `abridged_title`, `decision_date`, `ponente`, `division`, `doc_type`, `phil_citation`, `scra_citation`, `word_count`, `source_url`, `citation_format`
- Output filename: `{safe_title}-case-digest.md`
- Frontmatter update: writes `abridged_title` with corrected short title
- Validation: checks for `CAPTION`, `FACTS`, `ISSUE`, `RULING` markers

We need to support the **e-SCRA** corpus (~53,351 files across 1,026 volumes) which has:

- Different frontmatter fields: `title`, `short_title`, `docket`, `date`, `ponente`, `case_nature`, `disposition`, `source_type`, `source_file`
- Different directory structure: `Volume_{NNN}/*.md` instead of `{YEAR}/{MM_Mon}/*.md`
- Rich existing content: SYLLABI section, citation metadata table, footnotes — all fed to NotebookLM as source content for better digest quality
- Different field mapping: `short_title` ↔ `abridged_title`, `docket` ↔ `docket_number`, `date` ↔ `decision_date`

---

## 2. Architecture Decision

**Approach: Corpus Profile Abstraction** — NOT a separate MCP server.

| Option | Pros | Cons |
|--------|------|------|
| ❌ Separate MCP server | Clean separation | Double maintenance, 95% code duplication |
| ❌ Runtime `corpus_type` parameter | No code restructuring | Leaky — caller must always specify |
| ✅ **Corpus profile dict + auto-detection** | Zero-config, extensible | Need to write auto-detection logic |

The pipeline's core loop (`add source → query → validate → save → delete source`) is 100% corpus-agnostic. Only three thin layers are corpus-specific:

1. **Frontmatter field mapping** (how to read/write YAML keys)
2. **Short title field name** (which key stores the corrected title)
3. **Output metadata formatting** (which fields to emit in the digest frontmatter)

### Auto-Detection Logic

Detect corpus type from the **first file's frontmatter**:

```python
if "source_type" in frontmatter and frontmatter.get("source_type") == "SCRA":
    corpus = "escra"
elif "doc_id" in frontmatter:
    corpus = "elibrary"
else:
    corpus = "generic"  # fallback — preserve frontmatter as-is
```

This is robust because:
- Every e-SCRA file has `source_type: "SCRA"` in its frontmatter
- Every SC e-Library file has `doc_id` (numeric) in its frontmatter
- No overlap between the two

---

## 3. Corpus Profile Specification

### 3.1 Profile Data Structure

```python
# New constant in server.py (near DEFAULT_DIGEST_QUERY)

CORPUS_PROFILES = {
    "elibrary": {
        "label": "SC e-Library",
        "short_title_field": "abridged_title",      # field to UPDATE with corrected title
        "frontmatter_map": {                         # canonical → corpus-specific field name
            "title": "title",
            "short_title": "abridged_title",
            "docket": "docket_number",
            "date": "decision_date",
            "ponente": "ponente",
            "division": "division",
            "doc_type": "doc_type",
        },
        "extra_fields": [                            # additional fields to preserve
            "doc_id", "phil_citation", "scra_citation",
            "word_count", "source_url", "citation_format",
        ],
        "output_suffix": "-case-digest.md",
    },
    "escra": {
        "label": "e-SCRA",
        "short_title_field": "short_title",          # e-SCRA uses short_title
        "frontmatter_map": {
            "title": "title",
            "short_title": "short_title",
            "docket": "docket",
            "date": "date",
            "ponente": "ponente",
        },
        "extra_fields": [                            # fields unique to e-SCRA
            "case_nature", "disposition",
            "source_type", "source_file",
        ],
        "output_suffix": "-case-digest.md",
    },
    "generic": {
        "label": "Generic",
        "short_title_field": "short_title",
        "frontmatter_map": {},
        "extra_fields": [],
        "output_suffix": "-case-digest.md",
    },
}
```

### 3.2 Detect Function

```python
def _detect_corpus(frontmatter: dict) -> str:
    """Auto-detect corpus type from frontmatter fields."""
    if frontmatter.get("source_type") == "SCRA":
        return "escra"
    if "doc_id" in frontmatter:
        return "elibrary"
    return "generic"
```

---

## 4. Code Changes — Line-by-Line Plan

All changes are in `src/notebooklm_mcp/server.py`. No other files need modification.

### Phase 1: Add Infrastructure (non-breaking)

| Step | Lines | What | Details |
|------|-------|------|---------|
| **1a** | After L2142 | Add `CORPUS_PROFILES` dict | Insert the profile data structure (§3.1) |
| **1b** | After `CORPUS_PROFILES` | Add `_detect_corpus()` function | Insert auto-detection function (§3.2) |
| **1c** | After `_detect_corpus()` | Add `_build_output_frontmatter()` helper | Generic frontmatter builder that uses the profile |

### Phase 2: Refactor `notebook_digest_multi._process_notebook_chunk` (the core)

The key function is `_process_notebook_chunk` (lines 2628–2844). It currently has hardcoded e-Library assumptions in three places:

| Location | Current Code | Change |
|----------|-------------|--------|
| **L2694–2709** | Parses frontmatter into a raw dict | ✅ Keep as-is — this is already generic |
| **L2777–2787** | Extracts `SHORT_TITLE` from response | ✅ Keep as-is — this is response parsing, not corpus-specific |
| **L2789–2803** | Builds output frontmatter, hardcodes `abridged_title` | 🔴 **CHANGE**: Use corpus profile to determine which field to update |

#### Specific change at L2789–2803:

**Before** (hardcoded `abridged_title`):
```python
# ── Build output with preserved frontmatter ──
output_content = digest_body
if frontmatter:
    # Update abridged_title with corrected short title
    if short_title:
        frontmatter["abridged_title"] = short_title
    fm_lines = ["---"]
    for key, val in frontmatter.items():
        # Quote string values
        if isinstance(val, str) and not val.isdigit():
            fm_lines.append(f'{key}: "{val}"')
        else:
            fm_lines.append(f"{key}: {val}")
    fm_lines.append("---")
    output_content = "\n".join(fm_lines) + "\n\n" + digest_body
```

**After** (corpus-aware):
```python
# ── Build output with preserved frontmatter ──
output_content = digest_body
if frontmatter:
    # Auto-detect corpus type and get profile
    corpus_type = _detect_corpus(frontmatter)
    profile = CORPUS_PROFILES.get(corpus_type, CORPUS_PROFILES["generic"])
    
    # Update the correct short title field
    if short_title:
        st_field = profile["short_title_field"]
        frontmatter[st_field] = short_title
    
    fm_lines = ["---"]
    for key, val in frontmatter.items():
        if isinstance(val, str) and not val.isdigit():
            fm_lines.append(f'{key}: "{val}"')
        else:
            fm_lines.append(f"{key}: {val}")
    fm_lines.append("---")
    output_content = "\n".join(fm_lines) + "\n\n" + digest_body
```

This is a **minimal, surgical change** — only the field name lookup is different.

### Phase 3: Update `notebook_digest_multi` signature

| Step | Lines | What | Details |
|------|-------|------|---------|
| **3a** | L2522–2530 | Add optional `corpus_type` parameter | `corpus_type: str = "auto"` — allows explicit override but defaults to auto-detection |
| **3b** | L2553 | Update docstring | Document the new parameter |

**Updated signature:**
```python
def notebook_digest_multi(
    notebook_ids: list[str],
    file_paths: list[str],
    output_dir: str,
    query_template: str = DEFAULT_DIGEST_QUERY,
    corpus_type: str = "auto",        # NEW — "auto", "elibrary", "escra", "generic"
    batch_size: int = 1,
    max_retries: int = 3,
    delay: float = 1.0,
) -> dict[str, Any]:
```

When `corpus_type="auto"`, the first file's frontmatter is probed to detect the corpus. When explicitly set, the profile is used directly without probing.

### Phase 4: Update progress logging

| Step | Lines | What | Details |
|------|-------|------|---------|
| **4a** | L2812 | Progress display uses `abridged_title` | Change to use profile's `short_title_field` |

**Before:**
```python
st_display = short_title or frontmatter.get("abridged_title", item["title"][:30])
```

**After:**
```python
st_field = profile["short_title_field"]
st_display = short_title or frontmatter.get(st_field, item["title"][:30])
```

### Phase 5: Update `notebook_digest_pipeline` (older single-notebook tool)

The older `notebook_digest_pipeline` tool (L2194–2518) also needs the same frontmatter changes. But since it's the **deprecated** v2 pipeline, the change is identical:

- Add `corpus_type` parameter
- Use profile for frontmatter field mapping
- Same auto-detection logic

**Priority:** Low — this tool is kept for backward compatibility but `notebook_digest_multi` is the production tool.

---

## 5. Query Template Considerations

The `DEFAULT_DIGEST_QUERY` (L2099–2142) is **already corpus-agnostic**. It asks for:

- SHORT_TITLE, CAPTION, FACTS, ISSUE/S, RULING, CONCURRING/DISSENTING

These sections are the same regardless of whether the input is SC e-Library or e-SCRA markdown. The query prompt references "Philippine Supreme Court decision" which is correct for both.

**No changes needed to the query template.**

However, the e-SCRA markdown contains **additional rich content** (SYLLABI section, citation metadata table, footnotes) that the SC e-Library corpus doesn't have. This means:

- NotebookLM receives **more context** from e-SCRA files → potentially **higher quality** digests
- The SYLLABI section contains pre-existing headnotes that NotebookLM can leverage
- No special handling required — NotebookLM processes the full markdown content regardless

---

## 6. Output File Naming

| Corpus | Input filename example | Output filename |
|--------|----------------------|-----------------|
| SC e-Library | `Abbas v. Abbas, 702 Phil. 578 (G.R. No. 183896. November 4, 2013).md` | `Abbas v. Abbas, 702 Phil. 578 (G.R. No. 183896. November 4, 2013)-case-digest.md` |
| e-SCRA | `Amarillo, Jr. vs People, G.R. No. 153650, August 31, 2006.md` | `Amarillo, Jr. vs People, G.R. No. 153650, August 31, 2006-case-digest.md` |

Both use the same logic: `{safe_title}-case-digest.md` where `safe_title` is derived from the filename. **No change needed.**

---

## 7. Validation Rules

The current validation (L2762–2775) checks that the digest contains at least 2 of 4 structural markers (`CAPTION`, `FACTS`, `ISSUE`, `RULING`) and is at least 300 chars. This is **corpus-agnostic** and stays unchanged.

Similarly, `_is_digest_valid()` (L2591–2608) checks the same markers for resume/skip logic. **No change needed.**

---

## 8. Testing Plan

### 8.1 Unit Test: Auto-Detection

```python
# Test cases for _detect_corpus()
assert _detect_corpus({"source_type": "SCRA", "short_title": "X"}) == "escra"
assert _detect_corpus({"doc_id": "55438", "abridged_title": "X"}) == "elibrary"
assert _detect_corpus({"title": "X"}) == "generic"
assert _detect_corpus({}) == "generic"
```

### 8.2 Integration Test: e-SCRA 15-File Scale Test

1. **Select 15 e-SCRA files** from `Volume_500` (modern, well-structured)
2. **Run** `notebook_digest_multi` with the same 15 worker notebooks
3. **Verify:**
   - ✅ All 15 digests generated (100% success rate)
   - ✅ Frontmatter preserved with **e-SCRA field names** (`short_title` not `abridged_title`)
   - ✅ `short_title` field updated with corrected title from digest
   - ✅ CAPTION/FACTS/ISSUE/RULING sections present
   - ✅ Source corpus metadata preserved (`source_type: "SCRA"`, `case_nature`, `disposition`)
4. **Compare quality** with SC e-Library digests — e-SCRA should be ≥ equal quality given richer input

### 8.3 Regression Test: SC e-Library

Re-run the existing eval test (15 files from `2013/01_Jan`) to confirm no regression:

- Same 15 files from `eval-test-paths.json`
- Compare output against existing `eval-test/` directory
- Verify frontmatter still uses `abridged_title` (not `short_title`)

### 8.4 Edge Cases

| Test | Expected |
|------|----------|
| Mixed corpus in single batch | Auto-detect per-file from frontmatter |
| File with no frontmatter | Falls back to `generic` profile, digest body only (no YAML header) |
| e-SCRA file with OCR artifacts (malformed UTF-8) | `latin-1` fallback encoding handles it |
| e-SCRA file from Volume_001 (tiny ~800 bytes) | May produce short digest; validation catches <300 char responses |
| Explicit `corpus_type="escra"` override | Skips auto-detection, uses e-SCRA profile for all files |

---

## 9. Git Workflow

```
main ──── v1.0-sc-elibrary (existing tag)
  │
  ├── Phase 1–4 changes (commit: "feat: add corpus profile abstraction for e-SCRA support")
  │
  ├── Phase 5 changes (commit: "feat: add corpus_type to notebook_digest_pipeline (backcompat)")
  │
  ├── Integration test results (commit: "test: e-SCRA 15-file scale test passing")
  │
  └── Tag: v2.0-multi-corpus
```

---

## 10. Implementation Checklist

- [ ] **Phase 1a**: Add `CORPUS_PROFILES` constant after `DEFAULT_DIGEST_QUERY`
- [ ] **Phase 1b**: Add `_detect_corpus()` function
- [ ] **Phase 1c**: (Optional) Add `_build_output_frontmatter()` helper
- [ ] **Phase 2**: Refactor `_process_notebook_chunk` frontmatter handling (L2789–2803)
- [ ] **Phase 3**: Add `corpus_type` parameter to `notebook_digest_multi`
- [ ] **Phase 4**: Update progress logging to use profile's `short_title_field`
- [ ] **Phase 5**: (Low priority) Update `notebook_digest_pipeline` similarly
- [ ] **Test 1**: Unit test `_detect_corpus()` with all three corpus types
- [ ] **Test 2**: e-SCRA 15-file scale test (Volume_500)
- [ ] **Test 3**: SC e-Library regression test (2013/01_Jan eval-test)
- [ ] **Tag**: `v2.0-multi-corpus`

---

## 11. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Auto-detection misidentifies corpus | Very Low | Medium | Both markers (`source_type: "SCRA"` and `doc_id`) are unique to their corpus |
| e-SCRA files too large for NotebookLM | Low | High | NotebookLM handles up to ~500KB text; largest e-SCRA file is ~57KB |
| OCR artifacts in e-SCRA degrade digest quality | Medium | Low | NotebookLM is robust to minor OCR errors; SYLLABI section provides compensating context |
| Frontmatter parsing fails on edge-case YAML | Low | Low | Parser is already permissive (key:value line-by-line, not a full YAML parser) |
| Regression in SC e-Library pipeline | Very Low | High | Regression test covers this; code path unchanged when `doc_id` detected |

---

## 12. Lines of Code Estimate

| Component | Lines Added | Lines Modified | Lines Deleted |
|-----------|------------|----------------|---------------|
| `CORPUS_PROFILES` constant | ~45 | 0 | 0 |
| `_detect_corpus()` function | ~8 | 0 | 0 |
| `_process_notebook_chunk` refactor | ~8 | ~15 | ~3 |
| `notebook_digest_multi` signature | ~2 | ~3 | 0 |
| Progress logging | ~2 | ~1 | ~1 |
| **Total** | **~65** | **~19** | **~4** |

**Net impact: ~80 lines** — minimal surface area for maximum extensibility.

---

## 13. Future Extensibility

Adding a third corpus (e.g., a future "LawPhil" corpus) requires only:

1. Add a new entry to `CORPUS_PROFILES`
2. Add a detection rule to `_detect_corpus()`
3. No other code changes

This is the power of the profile abstraction — O(1) code changes per new corpus.
