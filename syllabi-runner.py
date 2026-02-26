"""Generate SCRA-format syllabi for Supreme Court cases using NotebookLM.

Processes cases from Sept 2022 onwards (supreme-court-scraper MARKDOWN files)
and generates syllabi using NotebookLM's AI with a custom "configure chat" prompt.

Usage:
  python syllabi-runner.py --month 2022/09_Sep
  python syllabi-runner.py --all  (All months from Sep 2022 onward)
  python syllabi-runner.py --all --start-at 2023/06_Jun
  python syllabi-runner.py --dry-run  (Show what would be processed, no API calls)

Output:
  with-generated-SYLLABI/2022/09_Sep/{case-name}-generated-syllabi.md
  with-generated-SYLLABI/2023/01_Jan/{case-name}-generated-syllabi.md
  ...

Auth resilience (same as notebooklm-mcp-runner):
  - Thread-safe auth recovery via Chrome CDP
  - Per-month retry with cookie refresh between attempts
  - Proactive cookie refresh every N months or M seconds
  - Chrome must be open with NotebookLM loaded
"""
import json
import logging
import os
import sys
import time
import argparse
import re
import traceback
from pathlib import Path

# Add source to path so we can import directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# ── Logging Setup ─────────────────────────────────────────────────
LOG_DIR = Path.home() / ".notebooklm-mcp"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "syllabi-runner.log"

logger = logging.getLogger("syllabi_runner")
logger.setLevel(logging.DEBUG)

_fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
_fh.setLevel(logging.DEBUG)
_fh.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
))
logger.addHandler(_fh)

_ch = logging.StreamHandler(sys.stderr)
_ch.setLevel(logging.INFO)
_ch.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(_ch)

# Also configure the server logger
logging.getLogger("notebooklm_mcp.server").setLevel(logging.DEBUG)
logging.getLogger("notebooklm_mcp.server").addHandler(_fh)
logging.getLogger("notebooklm_mcp.server").addHandler(_ch)

# Force auth from cached tokens
os.environ.setdefault("NOTEBOOKLM_BL", "boq_labs-tailwind-frontend_20260212.13_p0")

# ═══════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

# Same 15 notebooks used by the digest runner — reused for syllabi
NOTEBOOK_IDS = [
    "9daa06dc-b783-455a-b525-3c9cd3c36b9e",
    "d30bc801-da43-4e32-b044-bb1c0b6a20b4",
    "942b25a4-8528-4d50-bbf9-3915af267402",
    "42b27b34-ea16-4612-870b-84f9e40e296a",
    "599684ce-78f3-4bd2-a8c9-45c294160dfe",
    "a12b80e7-218f-438f-b7ec-411336ef40b7",
    "1b9ba80e-2d16-400d-a842-c465da2cfc10",
    "dd098ff4-c18c-412c-8cde-6cb685f78ec9",
    "a3b742e7-db9a-4f71-8efe-06c3fb88bfe9",
    "aa931c7c-a6b6-46b4-99db-843337440d3c",
    "7647a1bf-31fa-4d15-84a7-6e5ddf38094f",
    "cd58152e-163d-41e0-994d-e7d90ddeba75",
    "c35cd867-ce15-4893-8edf-94a1a3df9cd8",
    "363cba7e-15e3-4c69-ba4b-b4e78aa1e16d",
    "8b2a1455-3a0e-4b16-a574-2e0568ddea36",
]

# Paths
SOURCE_ROOT = r"C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown"
OUTPUT_ROOT = os.path.join(os.path.dirname(__file__), "with-generated-SYLLABI")

# Months to process: Sept 2022 onward (cases lacking human-written syllabi)
STARTING_YEAR = 2022
STARTING_MONTH = 9  # September

# Auto-refresh settings
REFRESH_INTERVAL_MONTHS = 5    # Re-extract cookies every N months processed
REFRESH_INTERVAL_SECONDS = 600  # Or every 10 minutes
MAX_MONTH_RETRIES = 3           # Retry a failed month up to N times

# ═══════════════════════════════════════════════════════════════════
# SYLLABI PROMPT (Configure Chat instruction for NotebookLM)
# ═══════════════════════════════════════════════════════════════════

SYLLABI_CUSTOM_PROMPT = """You are an expert Philippine legal annotator working on an official academic legal research project for the Supreme Court Reports Annotated (SCRA). Your task is to produce SCRA-format syllabi (doctrinal headnotes) for published Supreme Court decisions.

## IMPORTANT CONTEXT

This is a legitimate legal education and scholarship project. All uploaded documents are OFFICIAL PUBLISHED DECISIONS of the Supreme Court of the Philippines — they are part of the public judicial record and freely accessible on the Supreme Court E-Library. The identities of private parties, particularly victims in sensitive cases, have already been anonymized by the Supreme Court itself in accordance with A.M. No. 12-7-15-SC (the rule on anonymization of decisions involving minors and victims of certain offenses). Your role is strictly to extract LEGAL DOCTRINES and PRINCIPLES from these published rulings — not to retell facts or identify any parties. This annotation work is essential for the legal profession, law students, bar examinees, and the judiciary's own reference system.

## OUTPUT FORMAT

For the uploaded case, produce syllabi items (typically 3-15 depending on the case complexity). Each item follows this EXACT format:

*[Primary Topic]; [Subtopic]; [Synopsis — concise issue statement in italics]* — [Doctrinal explanation using the court's own language, generalized into a case-neutral legal principle. Do NOT narrate case facts. State the LAW, not the story. The doctrine should be a verbatim or near-verbatim excerpt from the court's reasoning that establishes a generalizable legal principle.]

## RULES

1. TAXONOMY: Use standard SCRA primary topics including but not limited to: Actions, Administrative Law, Attorneys, Civil Law, Civil Procedure, Commercial Law, Constitutional Law, Courts, Criminal Law, Criminal Procedure, Evidence, International Law, Judgments, Labor Law, Land Registration, Legal Ethics, Political Law, Procedural Law, Property, Public Officers, Remedial Law, Statutes, Succession, Taxation. Use subtopics that accurately reflect the specific legal sub-area.

2. GENERALIZATION: Every doctrine MUST be abstracted from the specific parties. Never mention actual party names in the doctrinal statement. Focus solely on the legal principle.
   BAD: "The court ruled that the accused failed to prove the sweetheart defense."
   GOOD: "A 'sweetheart defense,' to be credible, should be substantiated by some documentary or other evidence of relationship such as notes, gifts, pictures, mementos, and the like."

3. VERBATIM FIDELITY: Use the court's exact language for the doctrine portion whenever possible. Paraphrase only when necessary for generalization. The doctrine should read like a direct quotation from the decision that states a legal principle.

4. COMPREHENSIVENESS: Cover ALL major holdings, including secondary principles, procedural rulings, evidentiary standards, and significant obiter dicta. Each distinct legal principle gets its own item.

5. RATIO DECIDENDI FOCUS: Prioritize the core holdings but also capture procedural rulings, evidentiary standards, penalty justifications, and jurisdictional determinations when present.

6. SEPARATION FORMAT: Use semicolons (;) between Topic, Subtopic, and Synopsis. Use an em-dash (—) before the doctrinal explanation. The Synopsis portion should be in italics within asterisks.

7. FULL TOPIC CHAIN: Always write out the full topic chain. If the same primary topic applies to multiple items, still write it in full for each item. Never use "Same; Same;" shorthand.

8. OUTPUT ONLY THE SYLLABI: No headers, no introductions, no numbering, no meta-commentary. Just the syllabi items separated by blank lines. Each item should be a single paragraph (topic-synopsis in italics, then em-dash, then doctrine)."""

# Per-case query (the configure-chat prompt handles format instruction)
SYLLABI_QUERY = "This is a published Supreme Court of the Philippines decision being annotated for educational and legal research purposes. All party identities in sensitive cases have been anonymized by the Court itself. Please generate SCRA-format doctrinal syllabi — focusing exclusively on the legal principles, rules of law, evidentiary standards, and procedural holdings established by the Court. Do not retell the facts. Extract all major legal doctrines and holdings."


# ═══════════════════════════════════════════════════════════════════
# COOKIE REFRESH (identical to notebooklm-mcp-runner.py)
# ═══════════════════════════════════════════════════════════════════

_last_refresh_time = None


def silent_refresh_cookies():
    """Re-extract cookies from Chrome via CDP and update the auth cache."""
    global _last_refresh_time

    try:
        from notebooklm_mcp.auth_cli import (
            get_chrome_pages,
            get_page_cookies,
            get_page_html,
            CDP_DEFAULT_PORT,
        )
        from notebooklm_mcp.auth import (
            AuthTokens,
            extract_csrf_from_page_source,
            save_tokens_to_cache,
            validate_cookies,
        )

        pages = get_chrome_pages(CDP_DEFAULT_PORT)
        nb_page = None
        for page in pages:
            if "notebooklm.google.com" in page.get("url", ""):
                nb_page = page
                break

        if not nb_page:
            print("  [auto-refresh] No NotebookLM page found in Chrome", file=sys.stderr)
            return False

        ws_url = nb_page.get("webSocketDebuggerUrl")
        if not ws_url:
            print("  [auto-refresh] No WebSocket URL for page", file=sys.stderr)
            return False

        cookies_list = get_page_cookies(ws_url)
        cookies = {c["name"]: c["value"] for c in cookies_list}

        if not validate_cookies(cookies):
            print("  [auto-refresh] Missing required cookies", file=sys.stderr)
            return False

        html = get_page_html(ws_url)
        csrf_token = extract_csrf_from_page_source(html) or ""

        from notebooklm_mcp.auth_cli import extract_session_id_from_html
        session_id = extract_session_id_from_html(html)

        tokens = AuthTokens(
            cookies=cookies,
            csrf_token=csrf_token,
            session_id=session_id,
            extracted_at=time.time(),
        )
        save_tokens_to_cache(tokens, silent=True)

        from notebooklm_mcp import server
        server.reset_client()

        _last_refresh_time = time.time()
        print(f"  [auto-refresh] ✅ Cookies refreshed ({len(cookies)} cookies, CSRF={'yes' if csrf_token else 'no'})")
        return True

    except Exception as e:
        logger.error("[auto-refresh] Cookie refresh failed", exc_info=True)
        print(f"  [auto-refresh] ⚠️ Failed: {e}", file=sys.stderr)
        return False


def _auth_recovery_callback():
    """Auth recovery callback for mid-flight recovery by pipeline threads."""
    print("\n  🔑 [mid-flight auth recovery] Thread detected expired auth, refreshing...", file=sys.stderr)
    success = silent_refresh_cookies()
    if success:
        print("  🔑 [mid-flight auth recovery] ✅ Done — threads will resume with fresh auth", file=sys.stderr)
    else:
        print("  🔑 [mid-flight auth recovery] ❌ Could not refresh from Chrome", file=sys.stderr)
    return success


def should_refresh(months_since_refresh):
    """Check if it's time for a proactive cookie refresh."""
    if months_since_refresh >= REFRESH_INTERVAL_MONTHS:
        return True
    if _last_refresh_time is not None and (time.time() - _last_refresh_time) > REFRESH_INTERVAL_SECONDS:
        return True
    return False


# ═══════════════════════════════════════════════════════════════════
# NOTEBOOK MANAGEMENT
# ═══════════════════════════════════════════════════════════════════

def empty_notebook(client, notebook_id, label=""):
    """Delete all sources from a notebook to start fresh.

    Returns the number of sources deleted.
    """
    try:
        notebook_data = client.get_notebook(notebook_id)
        if not notebook_data:
            print(f"  {label}Could not get notebook {notebook_id[:8]}...", file=sys.stderr)
            return 0

        # Extract source IDs
        source_ids = []
        if isinstance(notebook_data, list) and len(notebook_data) > 0:
            nb_info = notebook_data[0] if isinstance(notebook_data[0], list) else notebook_data
            if len(nb_info) > 1 and isinstance(nb_info[1], list):
                for src in nb_info[1]:
                    if isinstance(src, list) and len(src) > 0:
                        sid_wrapper = src[0]
                        if isinstance(sid_wrapper, list) and len(sid_wrapper) > 0:
                            source_ids.append(sid_wrapper[0])

        if not source_ids:
            return 0

        deleted = 0
        for sid in source_ids:
            try:
                client.delete_source(sid)
                deleted += 1
            except Exception as e:
                logger.warning("%sFailed to delete source %s: %s", label, sid[:8], e)

        return deleted

    except Exception as e:
        logger.warning("%sFailed to empty notebook %s: %s", label, notebook_id[:8], e)
        return 0


def empty_all_notebooks(client):
    """Empty all 15 notebooks before starting the syllabi run."""
    print("\n🧹 Emptying all notebooks before starting...")
    total_deleted = 0

    for i, nb_id in enumerate(NOTEBOOK_IDS):
        deleted = empty_notebook(client, nb_id, label=f"NB{i}: ")
        if deleted > 0:
            print(f"  NB{i}: Deleted {deleted} source(s) from {nb_id[:8]}...")
            total_deleted += deleted
        time.sleep(0.5)  # Brief pause between notebooks

    if total_deleted > 0:
        print(f"  🧹 Emptied {total_deleted} total sources across {len(NOTEBOOK_IDS)} notebooks\n")
    else:
        print(f"  ✅ All {len(NOTEBOOK_IDS)} notebooks already empty\n")

    return total_deleted


def configure_all_notebooks(client):
    """Set custom chat instructions on all 15 notebooks for syllabi generation."""
    print("⚙️  Configuring chat instructions on all notebooks...")

    success_count = 0
    for i, nb_id in enumerate(NOTEBOOK_IDS):
        try:
            result = client.configure_chat(
                notebook_id=nb_id,
                goal="custom",
                custom_prompt=SYLLABI_CUSTOM_PROMPT,
                response_length="longer",
            )
            if result and result.get("status") == "success":
                success_count += 1
            else:
                print(f"  NB{i}: ⚠️ configure_chat unexpected result: {result}", file=sys.stderr)
                success_count += 1  # May still work — count it
        except Exception as e:
            print(f"  NB{i}: ❌ Failed to configure chat: {e}", file=sys.stderr)
            logger.error("Failed to configure NB%d (%s)", i, nb_id[:8], exc_info=True)
        time.sleep(0.3)

    print(f"  ⚙️  Configured {success_count}/{len(NOTEBOOK_IDS)} notebooks\n")
    return success_count


# ═══════════════════════════════════════════════════════════════════
# SYLLABI VALIDATION
# ═══════════════════════════════════════════════════════════════════

def _is_syllabi_valid(filepath):
    """Check if a generated syllabi file is valid.

    Unlike digests which check for CAPTION/FACTS/ISSUE/RULING markers,
    syllabi are validated by:
    - Minimum size (300 bytes — even a single syllabus item is ~200 chars)
    - Presence of topic/doctrine separators (semicolons and em-dashes)
    - At least one italicized segment (the synopsis)
    """
    try:
        if not os.path.exists(filepath):
            return False
        size = os.path.getsize(filepath)
        if size < 300:  # Minimum viable syllabi
            return False
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Must contain semicolons (topic;subtopic;synopsis pattern)
        has_semicolons = content.count(";") >= 2
        # Must contain em-dash or regular dash separator
        has_dash = "—" in content or "–" in content or " - " in content
        # Must have some italicized text (asterisk-wrapped)
        has_italics = content.count("*") >= 2

        return has_semicolons and (has_dash or has_italics)
    except Exception:
        logger.debug("_is_syllabi_valid failed for %s", filepath, exc_info=True)
        return False


def _count_valid_syllabi(out_dir, files):
    """Count how many source files already have valid syllabi in out_dir."""
    if not os.path.isdir(out_dir):
        return 0, len(files)

    valid = 0
    for f in files:
        title = os.path.splitext(os.path.basename(f))[0]
        safe_title = _make_safe_title(title)
        syllabi_path = os.path.join(out_dir, f"{safe_title}-generated-syllabi.md")
        if _is_syllabi_valid(syllabi_path):
            valid += 1

    return valid, len(files)


def _make_safe_title(title):
    """Create a filesystem-safe title from a case name."""
    return "".join(
        c if c.isalnum() or c in " .-_()," else "_"
        for c in title
    ).strip() or "untitled"


# ═══════════════════════════════════════════════════════════════════
# DIRECTORY DISCOVERY
# ═══════════════════════════════════════════════════════════════════

def get_target_months():
    """Discover all year/month directories from Sept 2022 onward.

    Returns list of (year_str, month_str, full_path) tuples sorted chronologically.
    Example: [("2022", "09_Sep", "C:/...markdown/2022/09_Sep"), ...]
    """
    months = []

    for year_name in os.listdir(SOURCE_ROOT):
        year_path = os.path.join(SOURCE_ROOT, year_name)
        if not os.path.isdir(year_path):
            continue
        try:
            year_num = int(year_name)
        except ValueError:
            continue

        if year_num < STARTING_YEAR:
            continue

        for month_name in os.listdir(year_path):
            month_path = os.path.join(year_path, month_name)
            if not os.path.isdir(month_path):
                continue

            # Parse month number from e.g. "09_Sep"
            match = re.match(r'^(\d{2})_', month_name)
            if not match:
                continue
            month_num = int(match.group(1))

            # Skip months before our starting point
            if year_num == STARTING_YEAR and month_num < STARTING_MONTH:
                continue

            months.append((year_name, month_name, month_path, year_num, month_num))

    # Sort chronologically
    months.sort(key=lambda x: (x[3], x[4]))
    return [(y, m, p) for y, m, p, _, _ in months]


def get_month_label(year, month):
    """Create a human-readable label like '2022/09_Sep'."""
    return f"{year}/{month}"


# ═══════════════════════════════════════════════════════════════════
# CORE PROCESSING (adapted from notebooklm-mcp-runner's process_directory)
# ═══════════════════════════════════════════════════════════════════

def process_month(src_dir, out_dir, label, max_retries=MAX_MONTH_RETRIES):
    """Process a single month directory with automatic retry on failure.

    Uses the notebook_digest_multi infrastructure but with syllabi query
    and syllabi-specific output naming/validation.
    """
    if not os.path.isdir(src_dir):
        print(f"ERROR: {src_dir} not found")
        return None

    files = sorted([
        os.path.join(src_dir, f)
        for f in os.listdir(src_dir)
        if f.endswith(".md")
    ])

    if not files:
        print(f"  {label}: no .md files found")
        return None

    # Content-validated skip check
    valid_existing, total = _count_valid_syllabi(out_dir, files)

    print(f"\n{'='*60}")
    print(f"  Processing {label}")
    print(f"  {total} files found, {valid_existing} valid syllabi already exist")
    print(f"  Source: {src_dir}")
    print(f"  Output: {out_dir}")
    print(f"{'='*60}")

    if valid_existing >= total:
        print(f"  SKIP — all {total} already complete (content-validated)")
        return {"status": "skipped", "summary": {"total": total, "skipped": total, "failed": 0}}

    # Import here to avoid loading everything at startup
    from notebooklm_mcp.server import notebook_digest_multi

    best_result = None

    for attempt_num in range(1, max_retries + 1):
        if attempt_num > 1:
            valid_existing, total = _count_valid_syllabi(out_dir, files)
            if valid_existing >= total:
                print(f"  ✅ All {total} syllabi complete after retry!")
                return {"status": "success", "summary": {"total": total, "skipped": total, "failed": 0}}
            print(f"\n  🔄 Retry {attempt_num}/{max_retries} for {label} "
                  f"({valid_existing}/{total} done, {total - valid_existing} remaining)")

        start = time.time()

        # We use notebook_digest_multi but with our custom query
        # The function handles: add source → query → save → delete source
        # We override the output naming via a patched approach
        result = _run_syllabi_batch(files, out_dir, notebook_digest_multi)

        elapsed = time.time() - start

        summary = result.get("summary", {})
        status = result.get("status")
        failed = summary.get("failed", 0)
        saved = summary.get("digests_saved", 0)

        attempt_label = f"Attempt {attempt_num}" if attempt_num > 1 else "Result"
        print(f"\n  {attempt_label}: {status}")
        print(f"  Saved: {saved}/{summary.get('total', '?')}")
        print(f"  Failed: {failed}")
        print(f"  Elapsed: {elapsed:.1f}s ({summary.get('queries_per_minute', 0):.1f} q/min)")

        # Print progress log (last 30 lines)
        logs = result.get("progress_log", [])
        if len(logs) > 30:
            print(f"    ... {len(logs)-30} logs hidden ...")
            for line in logs[-30:]:
                print(f"    {line}")
        else:
            for line in logs:
                print(f"    {line}")

        best_result = result

        # Decide whether to retry
        if failed == 0:
            break

        failure_rate = failed / max(summary.get("total", 1), 1)
        if failure_rate < 0.05:
            print(f"  ℹ️ Only {failed} failures ({failure_rate:.0%}) — accepting result.")
            break

        if attempt_num < max_retries:
            print(f"\n  ⚠️ {failed} file(s) failed ({failure_rate:.0%}). Refreshing cookies before retry...")
            if silent_refresh_cookies():
                print(f"  ✅ Cookies refreshed. Retrying in 3s...")
                time.sleep(3)
            else:
                print(f"  ⚠️ Cookie refresh failed — retrying anyway...")
                time.sleep(2)
        else:
            print(f"\n  ⚠️ {failed} file(s) still failed after {max_retries} attempts.")


    return best_result


def _validate_syllabi_answer(answer_text):
    """Validate that an AI response is valid syllabi content.

    Checks for:
    - Minimum length (300 chars)
    - Semicolons (topic;subtopic;synopsis pattern)
    - Em-dash or regular dash separators
    - Italicized text (asterisk-wrapped)
    """
    if len(answer_text) < 300:
        return False
    has_semicolons = answer_text.count(";") >= 2
    has_dash = "\u2014" in answer_text or "\u2013" in answer_text or " - " in answer_text
    has_italics = answer_text.count("*") >= 2
    return has_semicolons and (has_dash or has_italics)


def _run_syllabi_batch(files, out_dir, notebook_digest_multi_fn):
    """Run the notebook_digest_multi pipeline with syllabi-specific config."""
    return notebook_digest_multi_fn.fn(
        notebook_ids=NOTEBOOK_IDS,
        file_paths=files,
        output_dir=out_dir,
        query_template=SYLLABI_QUERY,
        output_suffix="-generated-syllabi.md",
        validator=_validate_syllabi_answer,
    )





# ═══════════════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════════════

def _format_eta(seconds):
    """Format seconds into a human-readable duration string."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        m, s = divmod(seconds, 60)
        return f"{int(m)}m {int(s)}s"
    else:
        h, remainder = divmod(seconds, 3600)
        m, s = divmod(remainder, 60)
        return f"{int(h)}h {int(m)}m"


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    global _last_refresh_time

    parser = argparse.ArgumentParser(
        description="Generate SCRA-format syllabi for SC cases via NotebookLM.",
        epilog="Output: with-generated-SYLLABI/{year}/{month}/{case}-generated-syllabi.md",
    )
    parser.add_argument("--month", help="Specific month (e.g., 2022/09_Sep)")
    parser.add_argument("--all", action="store_true",
                        help="Process all months from Sep 2022 onward")
    parser.add_argument("--start-at", metavar="MONTH",
                        help="Skip months before this one (e.g., --start-at 2023/06_Jun)")
    parser.add_argument("--refresh-every", type=int, default=REFRESH_INTERVAL_MONTHS,
                        help=f"Auto-refresh cookies every N months (default: {REFRESH_INTERVAL_MONTHS})")
    parser.add_argument("--max-retries", type=int, default=MAX_MONTH_RETRIES,
                        help=f"Max retry attempts per month (default: {MAX_MONTH_RETRIES})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be processed without making API calls")
    parser.add_argument("--skip-empty", action="store_true",
                        help="Skip the initial notebook emptying step")
    parser.add_argument("--skip-configure", action="store_true",
                        help="Skip configuring chat instructions (if already set)")

    args = parser.parse_args()
    refresh_interval = args.refresh_every
    max_retries = args.max_retries

    # ── Discover target months ──
    if args.month:
        # Single month mode
        parts = args.month.replace("\\", "/").split("/")
        if len(parts) != 2:
            print(f"ERROR: --month must be in format YYYY/MM_Mon (e.g., 2022/09_Sep)")
            sys.exit(1)
        year, month = parts
        src_dir = os.path.join(SOURCE_ROOT, year, month)
        if not os.path.isdir(src_dir):
            print(f"ERROR: Directory not found: {src_dir}")
            sys.exit(1)
        target_months = [(year, month, src_dir)]
    elif args.all:
        target_months = get_target_months()
    else:
        parser.print_help()
        return

    if not target_months:
        print("No months found to process!")
        return

    # ── Dry run: show what would be processed ──
    if args.dry_run:
        print(f"\n📋 DRY RUN — {len(target_months)} months to process:\n")
        total_files = 0
        total_existing = 0
        for year, month, src_dir in target_months:
            label = get_month_label(year, month)
            out_dir = os.path.join(OUTPUT_ROOT, year, month)
            files = [f for f in os.listdir(src_dir) if f.endswith(".md")]
            valid, _ = _count_valid_syllabi(out_dir, [os.path.join(src_dir, f) for f in files])
            remaining = len(files) - valid
            total_files += len(files)
            total_existing += valid
            status = "✅ DONE" if remaining == 0 else f"🔧 {remaining} to do"
            print(f"  {label:20s} {len(files):4d} files, {valid:4d} done  {status}")

        print(f"\n  Total: {total_files} files, {total_existing} done, {total_files - total_existing} remaining")
        print(f"  Estimated time: {_format_eta((total_files - total_existing) * 20)} (at ~20s/case)")
        return

    # ── Apply --start-at filter ──
    if args.start_at:
        start_parts = args.start_at.replace("\\", "/").split("/")
        if len(start_parts) == 2:
            start_year, start_month = start_parts
            original_count = len(target_months)
            target_months = [
                (y, m, p) for y, m, p in target_months
                if (y, m) >= (start_year, start_month)
            ]
            skipped = original_count - len(target_months)
            if skipped > 0:
                print(f"⏩ --start-at {args.start_at}: skipping {skipped} months")

    print(f"\n{'='*60}")
    print(f"  SYLLABI RUNNER")
    print(f"  {len(target_months)} months to process")
    print(f"  Source: {SOURCE_ROOT}")
    print(f"  Output: {OUTPUT_ROOT}")
    print(f"  Notebooks: {len(NOTEBOOK_IDS)}")
    print(f"{'='*60}\n")

    # ── Register auth-recovery callback ──
    from notebooklm_mcp.server import set_auth_recovery_callback, get_client
    set_auth_recovery_callback(_auth_recovery_callback)
    print("✅ Auth recovery callback registered (threads can self-heal)")

    # ── Initial cookie refresh ──
    print("Performing initial cookie refresh...")
    if silent_refresh_cookies():
        print("Starting with fresh cookies.\n")
    else:
        print("Could not refresh from Chrome — using cached cookies.\n")

    _last_refresh_time = time.time()

    # ── Get client and prepare notebooks ──
    try:
        client = get_client()
    except Exception as e:
        print(f"FATAL: Cannot authenticate: {e}")
        sys.exit(1)

    # Empty all notebooks first
    if not args.skip_empty:
        empty_all_notebooks(client)

    # Configure chat instructions
    if not args.skip_configure:
        configure_all_notebooks(client)

    # ── Process months ──
    months_since_refresh = 0
    batch_start_time = time.time()
    month_times = []
    total_files_processed = 0
    total_files_failed = 0
    total_files_skipped = 0

    for month_idx, (year, month, src_dir) in enumerate(target_months):
        month_start = time.time()

        # Proactive refresh check
        if should_refresh(months_since_refresh):
            print(f"\n  ⏰ Proactive cookie refresh (after {months_since_refresh} months)...")
            if silent_refresh_cookies():
                months_since_refresh = 0

        label = get_month_label(year, month)
        out_dir = os.path.join(OUTPUT_ROOT, year, month)
        os.makedirs(out_dir, exist_ok=True)

        result = process_month(src_dir, out_dir, label, max_retries=max_retries)
        months_since_refresh += 1

        # Accumulate stats
        month_elapsed = time.time() - month_start
        month_times.append(month_elapsed)

        if result and "summary" in result:
            s = result["summary"]
            total_files_processed += s.get("digests_saved", 0) - s.get("skipped", 0)
            total_files_failed += s.get("failed", 0)
            total_files_skipped += s.get("skipped", 0)

        # Cross-month progress report with ETA
        completed = month_idx + 1
        remaining = len(target_months) - completed
        overall_elapsed = time.time() - batch_start_time
        avg_time = sum(month_times) / len(month_times)
        eta_seconds = avg_time * remaining
        eta_str = _format_eta(eta_seconds) if remaining > 0 else "done"

        print(f"\n  📊 Overall: {completed}/{len(target_months)} months "
              f"({total_files_processed} saved, {total_files_skipped} skipped, {total_files_failed} failed) "
              f"| Elapsed: {_format_eta(overall_elapsed)} | ETA: {eta_str}")

    # Final summary
    total_elapsed = time.time() - batch_start_time
    print(f"\n{'='*60}")
    print(f"  🏁 SYLLABI GENERATION COMPLETE")
    print(f"  Months processed: {len(target_months)}")
    print(f"  New syllabi saved: {total_files_processed}")
    print(f"  Skipped (already done): {total_files_skipped}")
    print(f"  Failed: {total_files_failed}")
    print(f"  Total time: {_format_eta(total_elapsed)}")
    if month_times:
        print(f"  Avg time/month: {_format_eta(sum(month_times)/len(month_times))}")
    print(f"  Output: {OUTPUT_ROOT}")
    print(f"{'='*60}")


if __name__ == "__main__":
    logger.info("Syllabi runner started, log file: %s", LOG_FILE)
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Interrupted by user (Ctrl+C)")
        print("\n\nInterrupted! Progress saved to disk. Re-run to resume.")
        sys.exit(1)
    except Exception as e:
        logger.critical("FATAL ERROR", exc_info=True)
        print(f"\nFATAL ERROR: {e}")
        traceback.print_exc()
        sys.exit(1)
