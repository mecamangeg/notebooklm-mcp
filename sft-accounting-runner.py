"""SFT Accounting Dataset Generator via NotebookLM.

Parses multi-part IFRS/IAS scenario questions from the question bank files,
sends each to NotebookLM (which has IFRS PDFs uploaded as sources), and
harvests the grounded answers for SFT dataset creation.

Usage:
  python sft-accounting-runner.py --notebook-id <UUID>
  python sft-accounting-runner.py --notebook-id <UUID> --start-at 50
  python sft-accounting-runner.py --notebook-id <UUID> --dry-run
  python sft-accounting-runner.py --post-process-only

The notebook must already have IFRS/IAS PDFs uploaded as sources.
"""
import json
import logging
import os
import re
import sys
import time
import argparse
import traceback
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

# Add source to path so we can import directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# ── Logging Setup ─────────────────────────────────────────────────
LOG_DIR = Path.home() / ".notebooklm-mcp"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "sft-accounting.log"

logger = logging.getLogger("sft_accounting")
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

# Also capture server logs
logging.getLogger("notebooklm_mcp.server").setLevel(logging.DEBUG)
logging.getLogger("notebooklm_mcp.server").addHandler(_fh)

# Force auth from cached tokens
os.environ.setdefault("NOTEBOOKLM_BL", "boq_labs-tailwind-frontend_20260212.13_p0")

# ── Paths ─────────────────────────────────────────────────────────
QUESTIONS_DIR = r"C:\PROJECTS\robsky-ai-vertex\SUPERVISED FINE TUNING"
OUTPUT_DIR = r"C:\PROJECTS\robsky-ai-vertex\SUPERVISED FINE TUNING\ACCOUNTING_RAW_ANSWERS"
SFT_OUTPUT_DIR = r"C:\PROJECTS\robsky-ai-vertex\SUPERVISED FINE TUNING"

QUESTION_FILES = [
    os.path.join(QUESTIONS_DIR, "NOTEBOOKLM_ACCOUNTING_QUESTIONS.md"),        # Q1-Q25
    os.path.join(QUESTIONS_DIR, "NOTEBOOKLM_ACCOUNTING_QUESTIONS_PART2.md"),  # Q26-Q75
    os.path.join(QUESTIONS_DIR, "NOTEBOOKLM_ACCOUNTING_QUESTIONS_PART3.md"),  # Q76-Q125
    os.path.join(QUESTIONS_DIR, "NOTEBOOKLM_ACCOUNTING_QUESTIONS_PART4.md"),  # Q126-Q155
]

# ── Rate Limiting ─────────────────────────────────────────────────
QUERY_DELAY_SECONDS = 15  # Delay between queries to avoid rate limits
MAX_RETRIES = 5           # Retry failed queries
BACKOFF_BASE = 30         # Base backoff on empty answer (doubles each retry)
COOLDOWN_AFTER_FAILURES = 60  # Cooldown seconds after consecutive failures
MAX_CONSECUTIVE_FAILURES = 3  # Trigger cooldown after N consecutive failures

# ── Intent → System Instruction Mapping ──────────────────────────
# These map to the Robsky output format taxonomy from IMPLEMENTATION_PLAN_SFT_V2.md
SYSTEM_INSTRUCTIONS = {
    "COMPUTATION": (
        "You are a Senior CPA and IFRS specialist. You produce structured "
        "computation workbenches following this format: "
        "Inputs → Formula/Standard Reference → Step-by-Step Calculation → "
        "Result → Journal Entries → Authority Citation. "
        "Show all intermediate steps. Use formal accounting prose. "
        "Every computation must trace back to the referenced IFRS/IAS standard."
    ),
    "RESEARCH": (
        "You are a Senior Partner at a top-tier accounting and advisory firm "
        "specializing in IFRS/IAS. You produce structured advisories following "
        "this format: BLUF (Bottom Line Up Front) → Detailed Analysis → "
        "Authority Hierarchy (IFRS/IAS references) → Practical Implications → "
        "Caveats. Use formal professional prose. Every assertion must be "
        "grounded in the referenced standards."
    ),
    "COMPARATIVE": (
        "You are a Senior IFRS Analyst. You produce comparative matrices "
        "following this format: Side-by-Side Comparison Table → Detailed "
        "Analysis of Key Differences → Practical Implications → "
        "Recommendation. Use clear tabular formats where possible. "
        "Ground all comparisons in specific IFRS/IAS paragraphs."
    ),
    "INSTRUCTIONAL": (
        "You are an Accounting Professor and IFRS Expert. You produce "
        "procedural guides following this format: Prerequisites → "
        "Step-by-Step Procedure → Common Pitfalls → Examples → "
        "Standard References. Use clear, instructional prose. "
        "Ground all guidance in specific IFRS/IAS requirements."
    ),
    "COMPLIANCE": (
        "You are an IFRS Compliance Specialist. You produce compliance "
        "checklists following this format: Requirements → Recognition "
        "Criteria → Measurement Rules → Disclosure Requirements → "
        "Common Non-Compliance Issues → Standard References. "
        "Use regulatory prose. Every requirement must cite specific "
        "IFRS/IAS paragraphs."
    ),
    "ANALYTICAL": (
        "You are a Financial Reporting Analyst specializing in IFRS. "
        "You produce analytical reports following this format: "
        "Key Metrics → Impact Analysis → Trend Implications → "
        "Financial Statement Effects → Standard References. "
        "Use data-driven, analytical prose."
    ),
    "PEDAGOGICAL": (
        "You are an Accounting Professor preparing tutorial materials. "
        "You produce tutorials following this format: Concept Overview → "
        "Detailed Explanation with Examples → Practice Scenarios → "
        "Common Misconceptions → Key Takeaways → Standard References. "
        "Use pedagogical, accessible prose while maintaining technical accuracy."
    ),
}

# Default system instruction for questions that don't match a specific intent
DEFAULT_SYSTEM_INSTRUCTION = SYSTEM_INSTRUCTIONS["RESEARCH"]


# ── Data Models ───────────────────────────────────────────────────

@dataclass
class ParsedQuestion:
    """A single parsed question from the question bank."""
    number: int                    # Q1, Q2, ..., Q155
    title: str                     # "Step Acquisition to Control (IFRS 3 + IFRS 10)"
    category: str                  # "BUSINESS COMBINATIONS & CONSOLIDATION"
    standards: list[str]           # ["IFRS 3", "IFRS 10"]
    background: str                # The scenario text
    sub_questions: list[str]       # ["a. How should...", "b. Calculate..."]
    full_text: str                 # The complete question as sent to NotebookLM
    source_file: str               # Which file it came from
    intent: str = "RESEARCH"       # Mapped Robsky intent


# ── Question Parser ───────────────────────────────────────────────

def parse_questions_from_file(filepath: str) -> list[ParsedQuestion]:
    """Parse all questions from a single markdown file."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    questions = []
    current_category = ""

    # Split on question headers: ### Q1 — Title
    # Use regex to find all question blocks
    q_pattern = re.compile(
        r'^### (Q(\d+))\s*[—–-]\s*(.+?)$',
        re.MULTILINE
    )

    matches = list(q_pattern.finditer(content))

    for i, match in enumerate(matches):
        q_label = match.group(1)       # "Q1"
        q_number = int(match.group(2)) # 1
        q_title = match.group(3).strip()  # "Step Acquisition to Control (IFRS 3 + IFRS 10)"

        # Extract the block between this match and the next (or end of file)
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        block = content[start:end].strip()

        # Find category from ## headers above this question
        # Look backwards from the question position for the last ## header
        cat_pattern = re.compile(r'^## (.+?)$', re.MULTILINE)
        cat_matches = list(cat_pattern.finditer(content[:match.start()]))
        if cat_matches:
            current_category = cat_matches[-1].group(1).strip()
            # Clean up category (remove "continued" etc.)
            current_category = re.sub(r'\s*\(continued\)\s*', '', current_category)

        # Extract standards from title (things in parentheses like "IFRS 3 + IFRS 10")
        standards = []
        std_match = re.search(r'\(([^)]+)\)', q_title)
        if std_match:
            std_text = std_match.group(1)
            standards = [s.strip() for s in re.split(r'[+,&]', std_text)]

        # Split into background and sub-questions
        # Background is everything before "**Questions:**" or the first "a."
        bg_split = re.split(r'\*\*Questions?:\*\*', block, maxsplit=1)
        if len(bg_split) == 2:
            background = bg_split[0].strip()
            questions_text = bg_split[1].strip()
        else:
            # Try splitting at first "a." line
            a_match = re.search(r'^a\.\s', block, re.MULTILINE)
            if a_match:
                background = block[:a_match.start()].strip()
                questions_text = block[a_match.start():].strip()
            else:
                background = block
                questions_text = ""

        # Parse individual sub-questions (a., b., c., d., e.)
        sub_questions = []
        if questions_text:
            # Match lines starting with a letter followed by a period
            sq_pattern = re.compile(r'^([a-z])\.\s+(.+?)(?=\n[a-z]\.\s|\n---|\Z)', re.MULTILINE | re.DOTALL)
            for sq_match in sq_pattern.finditer(questions_text):
                sub_q = f"{sq_match.group(1)}. {sq_match.group(2).strip()}"
                sub_questions.append(sub_q)

        # If we couldn't parse sub-questions properly, just use the full questions text
        if not sub_questions and questions_text:
            sub_questions = [questions_text]

        # Determine intent based on sub-question content and category
        intent = _classify_intent(q_title, background, sub_questions, current_category)

        # Build the full query text to send to NotebookLM
        full_text = _build_query_text(q_number, q_title, background, sub_questions, standards)

        questions.append(ParsedQuestion(
            number=q_number,
            title=q_title,
            category=current_category,
            standards=standards,
            background=background,
            sub_questions=sub_questions,
            full_text=full_text,
            source_file=os.path.basename(filepath),
            intent=intent,
        ))

    return questions


def _classify_intent(title: str, background: str, sub_questions: list[str], category: str) -> str:
    """Classify a question into a Robsky intent based on its content."""
    combined = (title + " " + " ".join(sub_questions)).lower()

    # Computation: questions asking for calculations, journal entries, amounts
    computation_triggers = ["calculate", "compute", "journal entr", "what amount", "how much",
                           "determine the", "show the computation", "measurement", "what is the amount"]
    if any(t in combined for t in computation_triggers) and not any(
        t in combined for t in ["compare", "difference between", "contrast"]):
        return "COMPUTATION"

    # Comparative: questions asking for comparison
    comparative_triggers = ["compare", "contrast", "difference between", "how does.*differ",
                           "side-by-side", "versus", "vs", "which approach"]
    if any(t in combined for t in comparative_triggers):
        return "COMPARATIVE"

    # Instructional: step-by-step procedure questions
    instructional_triggers = ["how should", "step-by-step", "procedure", "what steps",
                              "how to account for", "walk through"]
    # Only classify as instructional if there's no strong computation signal
    if any(t in combined for t in instructional_triggers) and \
       not any(t in combined for t in computation_triggers):
        return "INSTRUCTIONAL"

    # Compliance: disclosure and compliance questions
    compliance_triggers = ["disclosure", "what are the requirements", "compliance",
                          "what must be disclosed", "regulatory"]
    if any(t in combined for t in compliance_triggers):
        return "COMPLIANCE"

    # Pedagogical: teaching/learning questions
    pedagogical_triggers = ["explain why", "what is the rationale", "concept",
                           "what does.*mean", "pedagogical"]
    if any(t in combined for t in pedagogical_triggers):
        return "PEDAGOGICAL"

    # Analytical: impact analysis
    analytical_triggers = ["impact", "effect on financial", "analyze", "implication"]
    if any(t in combined for t in analytical_triggers):
        return "ANALYTICAL"

    # Default: RESEARCH (the advisory format)
    return "RESEARCH"


def _build_query_text(q_number: int, title: str, background: str, sub_questions: list[str],
                      standards: list[str]) -> str:
    """Build the full query text to send to NotebookLM."""
    parts = []

    # Header with standard references for grounding
    if standards:
        parts.append(f"Based on {', '.join(standards)}, please answer the following scenario-based question.\n")

    # Background/scenario
    parts.append(f"**Scenario (Q{q_number}: {title}):**\n{background}\n")

    # Sub-questions
    parts.append("**Questions:**")
    for sq in sub_questions:
        parts.append(sq)

    # Instruction for comprehensive answer
    parts.append(
        "\nPlease provide a comprehensive, well-structured answer addressing "
        "each sub-question. Include specific paragraph references to the relevant "
        "IFRS/IAS standards. Show all calculations step-by-step where applicable."
    )

    return "\n".join(parts)


def parse_all_questions() -> list[ParsedQuestion]:
    """Parse questions from all 4 question files."""
    all_questions = []

    for filepath in QUESTION_FILES:
        if not os.path.exists(filepath):
            logger.warning(f"Question file not found: {filepath}")
            continue

        questions = parse_questions_from_file(filepath)
        logger.info(f"Parsed {len(questions)} questions from {os.path.basename(filepath)}")
        all_questions.extend(questions)

    # Sort by question number
    all_questions.sort(key=lambda q: q.number)

    return all_questions


# ── Cookie Refresh ────────────────────────────────────────────────

# Track auth.json modification time for auto-reload
_auth_file_mtime: float = 0.0


def _get_auth_file_path() -> str:
    """Get the path to the auth.json cache file."""
    return str(Path.home() / ".notebooklm-mcp" / "auth.json")


def reload_cookies_from_disk(force: bool = False) -> bool:
    """Re-read cookies from auth.json and reset the client singleton.
    
    This is the PRIMARY refresh mechanism. When fresh cookies are saved
    via MCP's save_auth_tokens tool, this function picks them up.
    
    Args:
        force: If True, always reload. If False, only reload if file changed.
    
    Returns True if cookies were successfully reloaded.
    """
    global _auth_file_mtime
    
    try:
        auth_path = _get_auth_file_path()
        if not os.path.exists(auth_path):
            logger.warning("[disk-reload] auth.json not found")
            return False
        
        current_mtime = os.path.getmtime(auth_path)
        
        if not force and current_mtime == _auth_file_mtime:
            return False  # File hasn't changed
        
        # File changed — reload
        from notebooklm_mcp.server import reset_client
        reset_client()
        _auth_file_mtime = current_mtime
        
        print(f"  [disk-reload] ✅ Cookies reloaded from auth.json", file=sys.stderr)
        logger.info(f"[disk-reload] Reloaded cookies (mtime={current_mtime})")
        return True
    except Exception as e:
        logger.error("[disk-reload] Failed", exc_info=True)
        print(f"  [disk-reload] ⚠️ Failed: {e}", file=sys.stderr)
        return False


def check_and_reload_cookies() -> bool:
    """Check if auth.json has been updated and reload if so.
    
    Called before each query to auto-detect when fresh cookies
    are saved externally (e.g., via MCP save_auth_tokens).
    """
    return reload_cookies_from_disk(force=False)


def silent_refresh_cookies():
    """Try CDP first, fall back to disk reload."""
    # Try CDP (works if Chrome is open with debugging port)
    try:
        from notebooklm_mcp.auth_cli import (
            get_chrome_pages, get_page_cookies, get_page_html, CDP_DEFAULT_PORT,
        )
        from notebooklm_mcp.auth import (
            AuthTokens, extract_csrf_from_page_source, save_tokens_to_cache, validate_cookies,
        )

        pages = get_chrome_pages(CDP_DEFAULT_PORT)
        nb_page = next((p for p in pages if "notebooklm.google.com" in p.get("url", "")), None)
        if nb_page:
            ws_url = nb_page.get("webSocketDebuggerUrl")
            if ws_url:
                cookies_list = get_page_cookies(ws_url)
                cookies = {c["name"]: c["value"] for c in cookies_list}
                if validate_cookies(cookies):
                    html = get_page_html(ws_url)
                    csrf_token = extract_csrf_from_page_source(html) or ""
                    from notebooklm_mcp.auth_cli import extract_session_id_from_html
                    session_id = extract_session_id_from_html(html)
                    tokens = AuthTokens(cookies=cookies, csrf_token=csrf_token,
                                        session_id=session_id, extracted_at=time.time())
                    save_tokens_to_cache(tokens, silent=True)
                    from notebooklm_mcp import server
                    server.reset_client()
                    print(f"  [auto-refresh] ✅ Cookies refreshed via CDP ({len(cookies)} cookies)")
                    return True
    except Exception:
        pass  # CDP not available, fall through to disk reload
    
    # Fall back to disk reload (picks up cookies saved via MCP)
    return reload_cookies_from_disk(force=True)


# ── Query Execution ───────────────────────────────────────────────

def query_notebooklm(notebook_id: str, question: ParsedQuestion, output_path: str) -> dict:
    """Send a question to NotebookLM and save the answer to disk.

    Returns a result dict with status, answer length, etc.
    """
    from notebooklm_mcp.server import get_client

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # Check for fresh cookies from disk before each attempt
            if attempt > 1:
                check_and_reload_cookies()
            
            client = get_client()
            result = client.query(notebook_id, query_text=question.full_text)

            if not result or not result.get("answer"):
                logger.warning(f"Q{question.number}: Empty answer (attempt {attempt}/{MAX_RETRIES})")
                if attempt < MAX_RETRIES:
                    # Exponential backoff: 30s, 60s, 120s, 240s
                    backoff = BACKOFF_BASE * (2 ** (attempt - 1))
                    logger.info(f"Q{question.number}: Backing off {backoff}s before retry")
                    print(f"Q{question.number}: Backing off {backoff}s before retry", file=sys.stderr)
                    time.sleep(backoff)
                    # Force reload from disk (in case cookies were saved via MCP)
                    reload_cookies_from_disk(force=True)
                    continue
                return {"status": "error", "error": "Empty answer", "q_number": question.number}

            answer = result["answer"]

            # Save to disk
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                # Write metadata header
                f.write(f"# Q{question.number} — {question.title}\n")
                f.write(f"**Category:** {question.category}\n")
                f.write(f"**Standards:** {', '.join(question.standards)}\n")
                f.write(f"**Intent:** {question.intent}\n")
                f.write(f"**Source File:** {question.source_file}\n")
                f.write(f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write("---\n\n")
                f.write("## Question\n\n")
                f.write(question.full_text)
                f.write("\n\n---\n\n")
                f.write("## Answer\n\n")
                f.write(answer)

            return {
                "status": "success",
                "q_number": question.number,
                "answer_length": len(answer),
                "output_path": output_path,
                "conversation_id": result.get("conversation_id"),
            }

        except Exception as e:
            logger.error(f"Q{question.number}: Query failed (attempt {attempt}/{MAX_RETRIES})",
                        exc_info=True)
            if attempt < MAX_RETRIES:
                if "expired" in str(e).lower() or "auth" in str(e).lower():
                    # Auth error — wait and reload from disk
                    # This gives time for user to paste fresh cookies via MCP
                    wait_secs = BACKOFF_BASE * (2 ** (attempt - 1))
                    print(f"  🔑 Auth error on Q{question.number} — waiting {wait_secs}s for fresh cookies...", file=sys.stderr)
                    time.sleep(wait_secs)
                    reload_cookies_from_disk(force=True)
                else:
                    time.sleep(QUERY_DELAY_SECONDS * 2)
            else:
                return {"status": "error", "error": str(e), "q_number": question.number}

    return {"status": "error", "error": "Max retries exceeded", "q_number": question.number}


def get_output_path(q_number: int) -> str:
    """Get the output file path for a given question number."""
    return os.path.join(OUTPUT_DIR, f"Q{q_number:03d}.md")


def is_answer_valid(filepath: str) -> bool:
    """Check if an answer file exists and is well-formed."""
    try:
        if not os.path.exists(filepath):
            return False
        size = os.path.getsize(filepath)
        if size < 300:  # Minimum viable answer
            return False
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        # Must have both Question and Answer sections
        return "## Question" in content and "## Answer" in content and len(content) > 500
    except Exception:
        return False


# ── Post-Processing to SFT JSONL ─────────────────────────────────

def parse_raw_answer(filepath: str) -> Optional[dict]:
    """Parse a raw answer .md file into structured data."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Extract metadata from header
        metadata = {}
        for line in content.split("\n")[:10]:
            if line.startswith("**") and ":**" in line:
                key = line.split(":**")[0].replace("**", "").strip()
                value = line.split(":**")[1].strip()
                metadata[key.lower()] = value

        # Extract question and answer sections
        parts = content.split("## Answer")
        if len(parts) < 2:
            return None

        q_section = parts[0]
        answer = parts[1].strip()

        # Extract the question text (between "## Question" and "---")
        q_parts = q_section.split("## Question")
        if len(q_parts) < 2:
            return None
        question_text = q_parts[1].strip().rstrip("---").strip()

        return {
            "intent": metadata.get("intent", "RESEARCH"),
            "category": metadata.get("category", ""),
            "standards": metadata.get("standards", ""),
            "question": question_text,
            "answer": answer,
        }
    except Exception as e:
        logger.error(f"Failed to parse {filepath}: {e}", exc_info=True)
        return None


def convert_to_sft_jsonl(questions: list[ParsedQuestion], output_path: str):
    """Convert all raw answers to Vertex AI SFT JSONL format.

    Format matches existing sft_train.jsonl structure:
    {
        "systemInstruction": {"role": "system", "parts": [{"text": "..."}]},
        "contents": [
            {"role": "user", "parts": [{"text": "..."}]},
            {"role": "model", "parts": [{"text": "..."}]}
        ]
    }
    """
    examples = []
    missing = []

    for q in questions:
        raw_path = get_output_path(q.number)
        if not is_answer_valid(raw_path):
            missing.append(q.number)
            continue

        parsed = parse_raw_answer(raw_path)
        if not parsed:
            missing.append(q.number)
            continue

        # Get intent-appropriate system instruction
        system_instruction = SYSTEM_INSTRUCTIONS.get(q.intent, DEFAULT_SYSTEM_INSTRUCTION)

        # Build the SFT example
        example = {
            "systemInstruction": {
                "role": "system",
                "parts": [{"text": system_instruction}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": parsed["question"]}]
                },
                {
                    "role": "model",
                    "parts": [{"text": parsed["answer"]}]
                }
            ]
        }
        examples.append(example)

    # Write JSONL
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for ex in examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    logger.info(f"Wrote {len(examples)} SFT examples to {output_path}")
    if missing:
        logger.warning(f"{len(missing)} questions had no valid answers: {missing}")

    return len(examples), missing


# ── Progress Tracking ─────────────────────────────────────────────

def save_progress(progress: dict, filepath: str = None):
    """Save progress to a JSON file for resume support."""
    if filepath is None:
        filepath = os.path.join(OUTPUT_DIR, "_progress.json")
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2)


def load_progress(filepath: str = None) -> dict:
    """Load previously saved progress."""
    if filepath is None:
        filepath = os.path.join(OUTPUT_DIR, "_progress.json")
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"completed": [], "failed": [], "total_queries": 0}


def _format_eta(seconds: float) -> str:
    """Format seconds into human-readable duration."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        m, s = divmod(seconds, 60)
        return f"{int(m)}m {int(s)}s"
    else:
        h, remainder = divmod(seconds, 3600)
        m, _ = divmod(remainder, 60)
        return f"{int(h)}h {int(m)}m"


# ── Main Entry Point ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="SFT Accounting Dataset Generator via NotebookLM"
    )
    parser.add_argument("--notebook-id", required=False,
                        help="NotebookLM notebook UUID (must have IFRS PDFs as sources)")
    parser.add_argument("--start-at", type=int, default=1,
                        help="Start processing from question N (default: 1)")
    parser.add_argument("--end-at", type=int, default=999,
                        help="Stop processing after question N (default: all)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse and display questions without querying")
    parser.add_argument("--post-process-only", action="store_true",
                        help="Skip querying; convert existing raw answers to SFT JSONL")
    parser.add_argument("--delay", type=float, default=QUERY_DELAY_SECONDS,
                        help=f"Seconds between queries (default: {QUERY_DELAY_SECONDS})")
    parser.add_argument("--force", action="store_true",
                        help="Re-query even if valid answer already exists")

    args = parser.parse_args()

    # ── Step 1: Parse all questions ──
    print("📖 Parsing question files...")
    questions = parse_all_questions()
    print(f"   Found {len(questions)} questions across {len(QUESTION_FILES)} files")

    # Show intent distribution
    intent_counts = {}
    for q in questions:
        intent_counts[q.intent] = intent_counts.get(q.intent, 0) + 1
    print(f"\n   📊 Intent Distribution:")
    for intent, count in sorted(intent_counts.items(), key=lambda x: -x[1]):
        print(f"      {intent}: {count}")

    # ── Dry Run Mode ──
    if args.dry_run:
        print(f"\n🔍 Dry Run — showing questions {args.start_at} to {min(args.end_at, len(questions))}:\n")
        for q in questions:
            if q.number < args.start_at or q.number > args.end_at:
                continue
            print(f"  Q{q.number:3d} | {q.intent:14s} | {q.category[:40]:40s} | {q.title[:50]}")
            print(f"        Standards: {', '.join(q.standards) or 'N/A'}")
            print(f"        Sub-questions: {len(q.sub_questions)}")
            print(f"        Query length: {len(q.full_text)} chars")
            out_path = get_output_path(q.number)
            exists = is_answer_valid(out_path)
            print(f"        Output: {'✅ exists' if exists else '❌ missing'} ({out_path})")
            print()
        return

    # ── Post-Process Only Mode ──
    if args.post_process_only:
        print(f"\n📦 Post-processing {len(questions)} raw answers → SFT JSONL...")
        sft_path = os.path.join(SFT_OUTPUT_DIR, "sft_accounting.jsonl")
        count, missing = convert_to_sft_jsonl(questions, sft_path)
        print(f"   ✅ Wrote {count} examples to {sft_path}")
        if missing:
            print(f"   ⚠️  {len(missing)} questions missing valid answers: {missing[:20]}...")
        return

    # ── Query Mode — requires notebook ID ──
    if not args.notebook_id:
        print("❌ --notebook-id is required for querying. Use --dry-run or --post-process-only if you don't need it.")
        parser.print_help()
        sys.exit(1)

    notebook_id = args.notebook_id

    # Initial cookie load — snapshot the auth.json mtime
    global _auth_file_mtime
    print("\n🍪 Loading cookies...")
    auth_path = _get_auth_file_path()
    if os.path.exists(auth_path):
        _auth_file_mtime = os.path.getmtime(auth_path)
        print(f"   ✅ Using cookies from {auth_path}")
        print(f"   ℹ️  Auto-reload enabled: save fresh cookies via MCP and workers will pick them up")
    else:
        print("   ⚠️  No auth.json found — will fail on first query")

    # Register auth recovery callback (uses disk reload)
    from notebooklm_mcp.server import set_auth_recovery_callback
    set_auth_recovery_callback(lambda: reload_cookies_from_disk(force=True))

    # Load progress for resume support
    progress = load_progress()
    completed_set = set(progress.get("completed", []))

    # Filter to requested range
    target_questions = [q for q in questions
                        if args.start_at <= q.number <= args.end_at]

    # Count existing valid answers
    already_done = sum(1 for q in target_questions
                       if is_answer_valid(get_output_path(q.number)))
    remaining = len(target_questions) - already_done if not args.force else len(target_questions)

    print(f"\n🚀 Query Plan:")
    print(f"   Notebook: {notebook_id}")
    print(f"   Range: Q{args.start_at} → Q{min(args.end_at, max(q.number for q in questions))}")
    print(f"   Total: {len(target_questions)} questions")
    print(f"   Already done: {already_done}")
    print(f"   Remaining: {remaining}")
    print(f"   Delay: {args.delay}s between queries")
    print(f"   Estimated time: {_format_eta(remaining * (args.delay + 15))}")
    print(f"   Output: {OUTPUT_DIR}")
    print()

    if remaining == 0 and not args.force:
        print("✅ All questions already answered! Use --force to re-query.")
        print("   Run with --post-process-only to generate SFT JSONL from raw answers.")
        return

    # ── Main Query Loop ──
    batch_start = time.time()
    succeeded = 0
    failed = 0
    skipped = 0
    consecutive_failures = 0
    query_times = []
    refresh_counter = 0
    REFRESH_EVERY = 20  # Refresh cookies every N queries

    for i, q in enumerate(target_questions):
        out_path = get_output_path(q.number)

        # Skip if already done (unless --force)
        if not args.force and is_answer_valid(out_path):
            skipped += 1
            continue

        # Check for fresh cookies from disk before each query
        refresh_counter += 1
        if check_and_reload_cookies():
            refresh_counter = 0  # Reset counter after disk reload
        elif refresh_counter >= REFRESH_EVERY:
            print(f"\n  ⏰ Proactive cookie re-read (every {REFRESH_EVERY} queries)...")
            reload_cookies_from_disk(force=True)
            refresh_counter = 0

        # Progress display
        done_count = succeeded + failed + skipped
        total_count = len(target_questions)
        elapsed = time.time() - batch_start

        if query_times:
            avg_time = sum(query_times) / len(query_times)
            eta = avg_time * (total_count - done_count)
            eta_str = _format_eta(eta)
        else:
            eta_str = "calculating..."

        print(f"  [{done_count + 1}/{total_count}] Q{q.number:3d} — {q.title[:50]:50s} | ETA: {eta_str}")

        # Execute query
        q_start = time.time()
        result = query_notebooklm(notebook_id, q, out_path)
        q_elapsed = time.time() - q_start
        query_times.append(q_elapsed)

        if result["status"] == "success":
            succeeded += 1
            consecutive_failures = 0  # Reset on success
            answer_kb = result["answer_length"] / 1024
            print(f"         ✅ {answer_kb:.1f} KB in {q_elapsed:.1f}s")

            # Update progress
            progress["completed"].append(q.number)
            progress["total_queries"] = progress.get("total_queries", 0) + 1
            if succeeded % 5 == 0:  # Save progress every 5 successes
                save_progress(progress)
        else:
            failed += 1
            consecutive_failures += 1
            print(f"         ❌ {result.get('error', 'Unknown error')} ({q_elapsed:.1f}s)")
            progress.setdefault("failed", []).append(q.number)

            # Extended cooldown after consecutive failures (rate limit likely)
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                cooldown = COOLDOWN_AFTER_FAILURES * (consecutive_failures // MAX_CONSECUTIVE_FAILURES)
                cooldown = min(cooldown, 300)  # Cap at 5 minutes
                print(f"         ⏳ {consecutive_failures} consecutive failures — cooling down {cooldown}s...")
                print(f"         ℹ️  Save fresh cookies via MCP to resume automatically", file=sys.stderr)
                time.sleep(cooldown)
                # Reload from disk (picks up any freshly-saved cookies)
                reload_cookies_from_disk(force=True)
                continue  # Skip the normal delay

        # Rate limiting delay
        if i < len(target_questions) - 1:
            time.sleep(args.delay)

    # Final progress save
    save_progress(progress)

    # ── Summary ──
    total_elapsed = time.time() - batch_start
    print(f"\n{'='*60}")
    print(f"  🏁 QUERY BATCH COMPLETE")
    print(f"  Succeeded: {succeeded}")
    print(f"  Failed: {failed}")
    print(f"  Skipped (existing): {skipped}")
    print(f"  Total time: {_format_eta(total_elapsed)}")
    if query_times:
        print(f"  Avg query time: {sum(query_times)/len(query_times):.1f}s")
    print(f"{'='*60}")

    # Auto post-process if all done
    total_valid = sum(1 for q in questions if is_answer_valid(get_output_path(q.number)))
    if total_valid == len(questions):
        print(f"\n📦 All {len(questions)} answers collected! Auto-generating SFT JSONL...")
        sft_path = os.path.join(SFT_OUTPUT_DIR, "sft_accounting.jsonl")
        count, missing = convert_to_sft_jsonl(questions, sft_path)
        print(f"   ✅ Wrote {count} examples to {sft_path}")
    else:
        print(f"\n📊 {total_valid}/{len(questions)} answers collected so far.")
        print(f"   Run --post-process-only when all questions are answered.")


if __name__ == "__main__":
    logger.info("SFT Accounting Runner started, log: %s", LOG_FILE)
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Interrupted by user (Ctrl+C)")
        print("\n\nInterrupted! Progress saved. Re-run to resume.")
        sys.exit(1)
    except Exception as e:
        logger.critical("FATAL ERROR", exc_info=True)
        print(f"\nFATAL ERROR: {e}")
        traceback.print_exc()
        sys.exit(1)
