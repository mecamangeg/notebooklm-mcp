---
description: Implementation plan to optimize the SFT Accounting Runner using patterns from the e-SCRA runner.
---

# SFT Accounting Runner Optimization Plan

This plan outlines the steps to port high-performance and resilient patterns from the `notebooklm-mcp-runner.py` (e-SCRA) to the `sft-accounting-runner.py` (SFT).

## Objectives
1. **Resilience**: Implement a batch retry loop with proactive "mop-up" of failed questions.
2. **Observability**: Stream real-time server logs to the console for better debugging.
3. **Accuracy**: Align ETA calculations and skip logic with disk reality instead of sidecar progress files.
4. **Flexibility**: Allow CLI overrides for performance tuning.

---

## Phase 1: Logging & CLI Improvements
**Target Gaps: 2, 6**

1. **Enable Server Console Logs**:
   - Update logging setup to add `_ch` (StreamHandler) to the `notebooklm_mcp.server` logger.
2. **Add Missing CLI Arguments**:
   - Add `--max-retries` (default: 3).
   - Add `--refresh-every` (default: 20).
   - Add `--max-batch-retries` (default: 3) for the outer mop-up loop.

---

## Phase 2: Progress & ETA Logic Refactor
**Target Gaps: 3, 5**

1. **Adopt Disk-Truth Skip Logic**:
   - Deprecate `_progress.json` saving/loading.
   - Use `is_answer_valid(path)` as the sole source of truth for skip decisions.
2. **Refined ETA Calculation**:
   - Before starting the batch, filter `target_questions` into `active_questions` (those that don't pass `is_answer_valid`).
   - Base progress counters (`done_count`, `total_count`) and ETA strictly on `active_questions`.
   - Result:ETA accurately reflects the time remaining for *work actually being done*.

---

## Phase 3: Batch Retry & Mop-up Loop
**Target Gaps: 1, 4**

1. **Implement Outer Retry Loop**:
   - Wrap the main query loop in a `for attempt in range(1, args.max_batch_retries + 1)` loop.
   - Inside the loop:
     - Re-evaluate which questions still need work (mop-up).
     - If `failed_count == 0`, break success.
     - If `attempt > 1`, trigger a mandatory `silent_refresh_cookies()` (CDP) before retrying.
2. **Acceptance Threshold**:
   - Implement an "acceptance threshold" (e.g., if failure rate < 5%, don't retry the whole batch, just log and finish).

---

## Phase 4: Verification
1. **Dry Run Pass**:
   - Verify that `--dry-run` properly identifies existing files on disk and correctly reports "Done" vs "Missing" questions without relying on a JSON file.
2. **Failure Simulation**:
   - Temporarily force a failure on a question and verify the outer loop triggers a cookie refresh and re-attempts the question.
3. **ETA Verification**:
   - Run a batch with 90% completion and verify the ETA calculates minutes for the remaining 10%, not hours for the whole 100%.

---

## Implementation Sequence
1. **Single File Edit**: Apply all changes to `sft-accounting-runner.py` in one coordinated `multi_replace_file_content` call.
2. **Validation**: Run `uv run python sft-accounting-runner.py --dry-run` to confirm parsing and pathing.
3. **Execution**: Resume the current mop-up work with the new resilient loop.
