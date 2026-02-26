"""Extract structured context from YouTube videos via NotebookLM.

Fetches the YouTube video transcript via youtube-transcript-api, then adds
it as a TEXT source to a NotebookLM notebook. Configures the chat to use a
custom context-extraction role with "longer" responses, then fires a series
of targeted queries to harvest the full knowledge from the video.

Why text source (not URL)? NotebookLM's add_url_source for YouTube only
scrapes the page HTML (footer boilerplate). The transcript must be fetched
separately and injected as pasted text to get real video content.

Usage:
  python youtube-context-runner.py --url "https://www.youtube.com/watch?v=XXXX"
  python youtube-context-runner.py --url "https://youtu.be/XXXX" --notebook-id <UUID>
  python youtube-context-runner.py --url "..." --output-dir C:\\MyOutputs
  python youtube-context-runner.py --url "..." --no-cleanup   (keep source in notebook)

Output:
  YOUTUBE-CONTEXTS/{video-id}/context-extraction.md

Auth resilience:
  - Automatic cookie refresh via Chrome CDP before each run
  - Chrome must be open with NotebookLM loaded for CDP cookie extraction
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

# Add source to path so we can import directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# ── Logging Setup ─────────────────────────────────────────────────
LOG_DIR = Path.home() / ".notebooklm-mcp"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "youtube-context-runner.log"

logger = logging.getLogger("youtube_context_runner")
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

# Default output root
DEFAULT_OUTPUT_ROOT = r"C:\PROJECTS\youtube-context-extractor\output"

# Designated NotebookLM notebook for YouTube context extraction
DEFAULT_NOTEBOOK_ID = "a7d3b9c8-f255-4442-834d-e0bbbe30ec8f"

# Query settings
MAX_RETRIES = 3
QUERY_DELAY_SECONDS = 5   # Brief pause between multi-query batches
BACKOFF_BASE = 20         # Base backoff on empty answer

# Source ingestion wait after add_text_source (much shorter than URL ingestion)
SOURCE_WAIT_SECONDS = 10

# Max transcript chars to send as text source (NotebookLM text limit is ~500k)
MAX_TRANSCRIPT_CHARS = 400_000

# ═══════════════════════════════════════════════════════════════════
# CONFIGURE-CHAT: Custom Role Prompt (goal=custom, response=longer)
# ═══════════════════════════════════════════════════════════════════

YOUTUBE_CUSTOM_PROMPT = """\
You are an expert knowledge extractor and educator specializing in converting video content into structured, comprehensive reference documents. Your task is to deeply analyze the YouTube video provided as a source and extract ALL meaningful knowledge from it.

## YOUR ROLE

Act as a diligent research assistant who has watched the entire video multiple times. You understand every concept discussed, every argument made, every example given, and every practical insight shared. You transform raw video content into highly organized, detailed reference material that teaches readers everything the video covers — as if they watched it themselves and took perfect notes.

## OUTPUT PRINCIPLES

1. **COMPREHENSIVE**: Cover ALL major topics, subtopics, examples, demonstrations, code snippets, tips, and insights from the video. Leave nothing important out.

2. **STRUCTURED**: Organize content with clear headings, subheadings, and nested bullet points. Use numbered steps for procedures. Use tables for comparisons.

3. **VERBATIM FIDELITY WHERE IT MATTERS**: When the speaker gives definitions, commands, code, formulas, or direct instructions — preserve them exactly. Paraphrase explanations and context where helpful.

4. **EDUCATIONAL**: Write for someone who has NOT watched the video. They should be able to learn everything from your output alone.

5. **CONCRETE**: Include specific details — actual values, exact commands, real examples, concrete numbers — not vague summaries.

6. **LONGER RESPONSES**: Always give the most complete, detailed answer possible. Do not abbreviate or truncate.
"""

# ═══════════════════════════════════════════════════════════════════
# EXTRACTION QUERIES
# Each query targets a different dimension of the video's content.
# They are sent sequentially so the conversation context builds up.
# ═══════════════════════════════════════════════════════════════════

EXTRACTION_QUERIES = [
    {
        "id": "overview",
        "label": "Video Overview & Key Topics",
        "query": (
            "Please provide a comprehensive overview of this YouTube video. Include:\n"
            "1. The video's main topic, purpose, and target audience\n"
            "2. The speaker's name/credentials (if mentioned)\n"
            "3. A complete outline of ALL topics covered, in the order they appear\n"
            "4. The key problem being solved or question being answered\n"
            "5. The overall conclusion or main takeaway\n\n"
            "Be thorough — this overview will serve as the table of contents for our full extraction."
        ),
    },
    {
        "id": "core_concepts",
        "label": "Core Concepts & Explanations",
        "query": (
            "Now extract ALL core concepts, terms, frameworks, and ideas introduced in the video. "
            "For each concept:\n"
            "- Give its exact name/term as used in the video\n"
            "- Provide the full explanation or definition given by the speaker\n"
            "- Include any analogies or examples used to explain it\n"
            "- Note how it relates to other concepts covered\n\n"
            "Organize by topic/section. Be exhaustive — include even the concepts "
            "that seem minor or obvious, as they may be crucial for understanding the full picture."
        ),
    },
    {
        "id": "technical_details",
        "label": "Technical Details, Code & Implementation",
        "query": (
            "Extract all technical content from the video — code, commands, configurations, "
            "architecture details, and implementation steps. Include:\n"
            "1. Any code snippets or pseudocode shown/discussed (reproduce them exactly)\n"
            "2. Step-by-step procedures and how-to instructions\n"
            "3. Architecture diagrams or system designs described\n"
            "4. Configuration settings, parameters, or options mentioned\n"
            "5. APIs, libraries, tools, or technologies referenced\n"
            "6. File structures or data schemas discussed\n\n"
            "If the video is non-technical, instead extract: specific processes, "
            "methodologies, frameworks, models, or structured approaches described.\n\n"
            "Be very specific — include exact names, exact values, exact syntax."
        ),
    },
    {
        "id": "examples_demonstrations",
        "label": "Examples, Demonstrations & Use Cases",
        "query": (
            "Extract every example, demonstration, case study, scenario, and use case "
            "presented in the video. For each:\n"
            "- Describe what is being demonstrated\n"
            "- Walk through it step by step as shown in the video\n"
            "- Note the outcome or result\n"
            "- Capture any key insights revealed by the example\n\n"
            "Also list any counterexamples, anti-patterns, or 'what NOT to do' cases mentioned."
        ),
    },
    {
        "id": "insights_tips",
        "label": "Key Insights, Tips & Best Practices",
        "query": (
            "Extract all practical insights, tips, best practices, recommendations, warnings, "
            "and expert opinions shared in the video. Include:\n"
            "1. Explicit tips or advice given by the speaker (quote directly where possible)\n"
            "2. Best practices recommended\n"
            "3. Common mistakes or pitfalls to avoid\n"
            "4. Opinions or preferences expressed about tools/approaches\n"
            "5. Lessons learned or hard-won insights shared\n"
            "6. Comparisons between different approaches and which is preferred\n\n"
            "These are often the highest-value parts of any video — be thorough."
        ),
    },
    {
        "id": "questions_answers",
        "label": "Q&A, FAQs & Clarifications",
        "query": (
            "Extract any questions and answers, FAQs, or clarifications from the video. "
            "This includes:\n"
            "1. Questions the speaker explicitly addresses or anticipates\n"
            "2. Questions from audience/comments that are addressed in the video\n"
            "3. Clarifications the speaker provides to resolve potential confusion\n"
            "4. 'What if' scenarios and their answers\n"
            "5. Limitations, caveats, or 'it depends' situations explained\n\n"
            "Format as Q: / A: pairs. If no explicit Q&A, extract the implicit questions "
            "the video answers through its content."
        ),
    },
    {
        "id": "resources_references",
        "label": "Resources, References & Next Steps",
        "query": (
            "Extract all resources, references, and next steps mentioned in the video:\n"
            "1. Books, papers, articles, or documentation referenced\n"
            "2. External tools, libraries, services, or websites mentioned\n"
            "3. Other videos, courses, or content the speaker recommends\n"
            "4. GitHub repos, code samples, or downloads mentioned\n"
            "5. Follow-up topics the speaker suggests exploring\n"
            "6. Prerequisites or background knowledge recommended\n"
            "7. Any specific 'call to action' the speaker gives\n\n"
            "Include URLs or specific identifiers where mentioned."
        ),
    },
]

# ═══════════════════════════════════════════════════════════════════
# COOKIE REFRESH (identical pattern to other runners)
# ═══════════════════════════════════════════════════════════════════

_last_refresh_time = None

# CDP ports to probe, in priority order.
# Antigravity IDE uses port 9000 (Electron/CDP for auto-accept extension).
# Chrome for NotebookLM auth should run on 9222 (default) or 9223 (legacy fallback).
_CDP_PROBE_PORTS = [9222, 9223, 9000]


def _find_notebooklm_chrome_page(probe_ports=None):
    """Try each CDP port in order and return (port, page_dict) for the first
    port that has a NotebookLM page open, or (None, None) if none found."""
    from notebooklm_mcp.auth_cli import get_chrome_pages

    for port in (probe_ports or _CDP_PROBE_PORTS):
        try:
            pages = get_chrome_pages(port)
            for page in pages:
                if "notebooklm.google.com" in page.get("url", ""):
                    return port, page
        except Exception:
            pass
    return None, None


def silent_refresh_cookies(cdp_port: int | None = None, auto_launch: bool = True):
    """Re-extract cookies from Chrome via CDP and update the auth cache.

    Args:
        cdp_port: Explicit CDP port to use. If None, probes ports in
                  _CDP_PROBE_PORTS order (9222, 9223, 9000).
        auto_launch: If True and no Chrome page is found, attempt to
                     auto-launch Chrome with the persistent notebooklm
                     profile and wait briefly for it to open.
    """
    global _last_refresh_time

    try:
        from notebooklm_mcp.auth_cli import (
            get_chrome_pages,
            get_page_cookies,
            get_page_html,
            launch_chrome,
            CDP_DEFAULT_PORT,
        )
        from notebooklm_mcp.auth import (
            AuthTokens,
            extract_csrf_from_page_source,
            save_tokens_to_cache,
            validate_cookies,
        )

        # Determine which ports to probe
        if cdp_port is not None:
            probe_ports = [cdp_port]
        else:
            probe_ports = _CDP_PROBE_PORTS

        found_port, nb_page = _find_notebooklm_chrome_page(probe_ports)

        if nb_page is None and auto_launch:
            # No Chrome with a NotebookLM page found — try to auto-launch
            target_port = cdp_port or CDP_DEFAULT_PORT  # 9222
            print(f"  [auto-refresh] No NotebookLM page found on ports {probe_ports}", file=sys.stderr)
            print(f"  [auto-refresh] Auto-launching Chrome on port {target_port}...", file=sys.stderr)
            try:
                from notebooklm_mcp.auth_cli import find_or_create_notebooklm_page
                launch_chrome(target_port, headless=False)
                time.sleep(5)  # Give Chrome time to open
                # Re-probe after launch
                found_port, nb_page = _find_notebooklm_chrome_page([target_port])
                if nb_page is None:
                    # Chrome opened but no NB page yet — try to navigate
                    nb_page = find_or_create_notebooklm_page(target_port)
                    if nb_page:
                        found_port = target_port
                        time.sleep(4)  # Wait for NB page to load session
            except Exception as launch_err:
                logger.warning("[auto-refresh] Chrome launch failed: %s", launch_err)

        if nb_page is None:
            print(
                f"  [auto-refresh] ⚠️  No NotebookLM page found on any Chrome instance.\n"
                f"  [auto-refresh]    Open Chrome at https://notebooklm.google.com and try again.",
                file=sys.stderr,
            )
            return False

        ws_url = nb_page.get("webSocketDebuggerUrl")
        if not ws_url:
            print("  [auto-refresh] No WebSocket URL for page", file=sys.stderr)
            return False

        cookies_list = get_page_cookies(ws_url)
        cookies = {c["name"]: c["value"] for c in cookies_list}

        if not validate_cookies(cookies):
            print("  [auto-refresh] Missing required cookies — page may not be logged in", file=sys.stderr)
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
        print(
            f"  [auto-refresh] ✅ Cookies refreshed from port {found_port} "
            f"({len(cookies)} cookies, CSRF={'yes' if csrf_token else 'no'})"
        )
        return True

    except Exception as e:
        logger.error("[auto-refresh] Cookie refresh failed", exc_info=True)
        print(f"  [auto-refresh] ⚠️ Failed: {e}", file=sys.stderr)
        return False


# ═══════════════════════════════════════════════════════════════════
# NOTEBOOK MANAGEMENT
# ═══════════════════════════════════════════════════════════════════

def get_notebook_sources(client, notebook_id):
    """Return a list of {id, title} dicts for all sources in the notebook."""
    try:
        notebook_data = client.get_notebook(notebook_id)
        if not notebook_data:
            return []

        source_ids = []
        if isinstance(notebook_data, list) and len(notebook_data) >= 1:
            nb_info = notebook_data[0] if isinstance(notebook_data[0], list) else notebook_data
            sources_data = nb_info[1] if len(nb_info) > 1 else []
            if isinstance(sources_data, list):
                for src in sources_data:
                    if isinstance(src, list) and len(src) >= 2:
                        sid_wrapper = src[0]
                        sid = sid_wrapper[0] if isinstance(sid_wrapper, list) and sid_wrapper else None
                        title = src[1] if len(src) > 1 else "Untitled"
                        if sid:
                            source_ids.append({"id": sid, "title": title})

        return source_ids
    except Exception as e:
        logger.warning("Failed to list sources for notebook %s: %s", notebook_id[:8], e)
        return []


def delete_source(client, source_id, label=""):
    """Delete a single source from a notebook."""
    try:
        client.delete_source(source_id)
        return True
    except Exception as e:
        logger.warning("%sFailed to delete source %s: %s", label, source_id[:8], e)
        return False


def configure_notebook(client, notebook_id):
    """Configure the notebook chat: goal=custom, response_length=longer."""
    print("  ⚙️  Configuring chat (goal=custom, response=longer)...")
    try:
        result = client.configure_chat(
            notebook_id=notebook_id,
            goal="custom",
            custom_prompt=YOUTUBE_CUSTOM_PROMPT,
            response_length="longer",
        )
        if result and result.get("status") == "success":
            print("  ⚙️  Chat configured ✅")
            return True
        else:
            print(f"  ⚙️  configure_chat returned: {result}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"  ⚙️  Failed to configure chat: {e}", file=sys.stderr)
        logger.error("configure_chat failed for %s", notebook_id[:8], exc_info=True)
        return False


# ═══════════════════════════════════════════════════════════════════
# YOUTUBE URL HELPERS & TRANSCRIPT FETCHER
# ═══════════════════════════════════════════════════════════════════

def extract_video_id(url: str) -> str | None:
    """Extract the YouTube video ID from any YouTube URL format."""
    patterns = [
        r"(?:v=|youtu\.be/|embed/|shorts/)([A-Za-z0-9_-]{11})",
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return None


def make_safe_filename(text: str, max_len: int = 120) -> str:
    """Convert arbitrary text to a safe filename (no extension).

    Preserves spaces, mixed case, and most printable characters.
    Only strips characters that are illegal on Windows/macOS file systems.
    """
    # Remove filesystem-illegal chars: \ / : * ? " < > |
    safe = re.sub(r'[\\/:*?"<>|]', "", text)
    # Collapse runs of whitespace to a single space
    safe = re.sub(r"\s+", " ", safe).strip()
    return safe[:max_len] or "youtube-video"


def fetch_youtube_title(video_id: str) -> str:
    """Fetch the human-readable title of a YouTube video.

    Uses httpx to request the YouTube watch page and extracts the
    og:title meta tag.  Falls back to the video ID if anything fails.
    """
    try:
        import httpx
        url = f"https://www.youtube.com/watch?v={video_id}"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }
        resp = httpx.get(url, headers=headers, timeout=10, follow_redirects=True)
        # Primary: <title> tag — always contains full title and is static HTML
        m = re.search(r"<title>(.+?)</title>", resp.text, re.DOTALL)
        if m:
            title = m.group(1).replace(" - YouTube", "").strip()
            title = title.replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">")
            title = re.sub(r"\s+", " ", title).strip()
            if title and title != video_id:
                return title
        # Fallback: og:title meta tag
        m = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\'](.*?)["\']', resp.text)
        if m:
            title = m.group(1)
            title = title.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'")
            return re.sub(r"\s+", " ", title).strip()
    except Exception as e:
        logger.warning("Could not fetch YouTube title for %s: %s", video_id, e)

    return video_id  # Last resort: use the video ID as title


def fetch_youtube_transcript(video_id: str, youtube_url: str) -> dict:
    """Fetch the video transcript and return a dict with text + metadata.

    Returns:
        {
          'status': 'success'|'error',
          'title': str,         # Best title we can derive
          'transcript': str,    # Full formatted transcript text
          'language': str,      # Language code used
          'char_count': int,
          'error': str,         # Only present on error
        }
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        return {
            "status": "error",
            "error": "youtube-transcript-api not installed. Run: uv pip install youtube-transcript-api",
        }

    print(f"  📝 Fetching transcript for video: {video_id}...")
    try:
        # v1.2.x: instance methods, not class methods
        api = YouTubeTranscriptApi()
        all_transcripts = list(api.list(video_id))

        chosen = None
        language_used = "unknown"

        # Priority 1: manual English
        for t in all_transcripts:
            if not t.is_generated and t.language_code.startswith("en"):
                chosen = t; language_used = t.language_code; break

        # Priority 2: auto-generated English
        if not chosen:
            for t in all_transcripts:
                if t.is_generated and t.language_code.startswith("en"):
                    chosen = t; language_used = t.language_code; break

        # Priority 3: any manual transcript
        if not chosen:
            for t in all_transcripts:
                if not t.is_generated:
                    chosen = t; language_used = t.language_code; break

        # Priority 4: whatever's first
        if not chosen and all_transcripts:
            chosen = all_transcripts[0]
            language_used = chosen.language_code

        if not chosen:
            return {"status": "error", "error": "No transcript available for this video."}

        # v1.2.x: fetch() returns FetchedTranscript (iterable of snippet objects)
        raw = chosen.fetch()
        lines = []
        for entry in raw:
            ts_sec = int(entry.start)
            minutes = ts_sec // 60
            seconds = ts_sec % 60
            text = entry.text.strip().replace("\n", " ")
            if text:
                lines.append(f"[{minutes:02d}:{seconds:02d}] {text}")

        transcript_text = "\n".join(lines)

        # Truncate if too long
        if len(transcript_text) > MAX_TRANSCRIPT_CHARS:
            transcript_text = transcript_text[:MAX_TRANSCRIPT_CHARS]
            transcript_text += f"\n\n[TRANSCRIPT TRUNCATED at {MAX_TRANSCRIPT_CHARS:,} chars]"

        char_count = len(transcript_text)
        print(f"  ✅ Transcript fetched: {len(lines)} segments, {char_count:,} chars, lang={language_used}")

        return {
            "status": "success",
            "title": f"YouTube Transcript: {video_id}",
            "transcript": transcript_text,
            "language": language_used,
            "char_count": char_count,
            "segment_count": len(lines),
        }

    except Exception as e:
        err = str(e)
        print(f"  ❌ Transcript fetch failed: {err}", file=sys.stderr)
        logger.error("Transcript fetch failed for %s", video_id, exc_info=True)
        return {"status": "error", "error": err}


# ═══════════════════════════════════════════════════════════════════
# QUERY EXECUTION
# ═══════════════════════════════════════════════════════════════════

def run_query(client, notebook_id: str, query_text: str, conversation_id: str | None,
              label: str = "") -> dict:
    """Run a single query against NotebookLM with retry logic.

    Returns {status, answer, conversation_id} or {status, error}.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = client.query(
                notebook_id,
                query_text=query_text,
                conversation_id=conversation_id,
            )

            if not result or not result.get("answer"):
                logger.warning("[%s] Empty answer (attempt %d/%d)", label, attempt, MAX_RETRIES)
                if attempt < MAX_RETRIES:
                    backoff = BACKOFF_BASE * (2 ** (attempt - 1))
                    print(f"  [{label}] Empty answer — backing off {backoff}s...", file=sys.stderr)
                    time.sleep(backoff)
                    # Attempt cookie refresh on empty answer
                    silent_refresh_cookies()
                    client_fresh = None
                    try:
                        from notebooklm_mcp.server import get_client
                        client = get_client()
                    except Exception:
                        pass
                    continue

                return {"status": "error", "error": "Empty answer after retries", "answer": ""}

            return {
                "status": "success",
                "answer": result["answer"],
                "conversation_id": result.get("conversation_id"),
            }

        except Exception as e:
            logger.error("[%s] Query failed (attempt %d/%d)", label, attempt, MAX_RETRIES, exc_info=True)
            if attempt < MAX_RETRIES:
                err_str = str(e).lower()
                if any(kw in err_str for kw in ["expired", "auth", "401", "403"]):
                    print(f"  [{label}] Auth error — refreshing cookies...", file=sys.stderr)
                    silent_refresh_cookies()
                    try:
                        from notebooklm_mcp.server import get_client
                        client = get_client()
                    except Exception:
                        pass
                else:
                    time.sleep(QUERY_DELAY_SECONDS * 2)
            else:
                return {"status": "error", "error": str(e), "answer": ""}

    return {"status": "error", "error": "Max retries exceeded", "answer": ""}


# ═══════════════════════════════════════════════════════════════════
# VALIDATION
# ═══════════════════════════════════════════════════════════════════

def is_extraction_valid(filepath: str) -> bool:
    """Check if an already-extracted context file is complete and valid."""
    try:
        if not os.path.exists(filepath):
            return False
        size = os.path.getsize(filepath)
        if size < 1000:  # A real extraction should be several KB
            return False
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        # Must contain at least a few of our extraction section headers
        found_sections = sum(
            1 for q in EXTRACTION_QUERIES
            if q["label"].lower() in content.lower() or f"## {q['label']}" in content
        )
        return found_sections >= 3
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════════
# CORE EXTRACTION PIPELINE
# ═══════════════════════════════════════════════════════════════════

def extract_youtube_context(
    youtube_url: str,
    video_id: str,
    notebook_id: str,
    output_path: str,
    cleanup: bool = True,
) -> dict:
    """Full extraction pipeline for a single YouTube URL.

    Steps:
    1. Fetch transcript via youtube-transcript-api
    2. Clean old sources from notebook
    3. Configure chat (custom role + longer responses)
    4. Add transcript as TEXT source (NOT URL — avoids HTML boilerplate)
    5. Brief wait for text source ingestion
    6. Run all extraction queries sequentially (building conversation)
    7. Save combined output to output_path
    8. (Optionally) delete the source from the notebook

    Returns {status, output_path, sections_extracted, error?}
    """
    from notebooklm_mcp.server import get_client

    print(f"\n{'='*60}")
    print(f"  YouTube Context Extraction")
    print(f"  URL: {youtube_url}")
    print(f"  Notebook: {notebook_id[:8]}...")
    print(f"  Output: {output_path}")
    print(f"{'='*60}")

    # ── Step 1: Fetch transcript ──
    transcript_result = fetch_youtube_transcript(video_id, youtube_url)
    if transcript_result["status"] != "success":
        return {
            "status": "error",
            "error": f"Transcript unavailable: {transcript_result['error']}",
        }

    transcript_text = transcript_result["transcript"]
    video_title = transcript_result["title"]
    language = transcript_result.get("language", "en")
    segment_count = transcript_result.get("segment_count", 0)

    # Build rich text source with context header + transcript
    source_text = (
        f"YouTube Video URL: {youtube_url}\n"
        f"Video ID: {video_id}\n"
        f"Transcript Language: {language}\n"
        f"Segments: {segment_count}\n"
        f"Chars: {transcript_result['char_count']:,}\n"
        f"\n{'='*60}\n"
        f"FULL TRANSCRIPT (with timestamps [MM:SS])\n"
        f"{'='*60}\n\n"
        f"{transcript_text}"
    )
    source_title = f"Transcript: {video_id}"

    client = get_client()

    # ── Step 2: Clean old sources from notebook ──
    existing_sources = get_notebook_sources(client, notebook_id)
    if existing_sources:
        print(f"\n  🧹 Removing {len(existing_sources)} existing source(s) from notebook...")
        for src in existing_sources:
            deleted = delete_source(client, src["id"], label=f"  [{src['title'][:30]}] ")
            if deleted:
                print(f"    ✅ Deleted: {src['title'][:50]}")
        time.sleep(1)

    # ── Step 3: Configure chat ──
    configure_notebook(client, notebook_id)

    # ── Step 4: Add transcript as TEXT source ──
    print(f"\n  � Adding transcript as text source ({len(source_text):,} chars)...")
    source_result = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            source_result = client.add_text_source(
                notebook_id,
                text=source_text,
                title=source_title,
            )
            if source_result:
                print(f"  ✅ Source added: {source_result.get('title', source_title)}")
                print(f"     Source ID: {source_result.get('id', 'unknown')[:16]}...")
                break
            else:
                print(f"  ⚠️ add_text_source returned None (attempt {attempt}/{MAX_RETRIES})", file=sys.stderr)
                if attempt < MAX_RETRIES:
                    time.sleep(10)
                    silent_refresh_cookies()
                    client = get_client()
        except Exception as e:
            logger.error("add_text_source failed (attempt %d)", attempt, exc_info=True)
            print(f"  ❌ Error adding source: {e}", file=sys.stderr)
            if attempt < MAX_RETRIES:
                time.sleep(10)
                silent_refresh_cookies()
                client = get_client()
            else:
                return {"status": "error", "error": f"Failed to add transcript as source: {e}"}

    if not source_result:
        return {"status": "error", "error": "Failed to add transcript as text source after retries"}

    source_id = source_result.get("id")
    source_title_final = source_result.get("title", source_title)

    # ── Step 5: Brief wait for text source ingestion ──
    print(f"\n  ⏳ Waiting {SOURCE_WAIT_SECONDS}s for NotebookLM to index the transcript...")
    time.sleep(SOURCE_WAIT_SECONDS)
    print(f"  ✅ Ready.")

    # ── Step 5: Run extraction queries ──
    print(f"\n  🔍 Starting extraction ({len(EXTRACTION_QUERIES)} queries)...\n")
    sections = {}
    conversation_id = None
    sections_ok = 0
    sections_failed = 0

    for i, query_def in enumerate(EXTRACTION_QUERIES):
        qid = query_def["id"]
        qlabel = query_def["label"]
        qtext = query_def["query"]

        print(f"  [{i+1}/{len(EXTRACTION_QUERIES)}] {qlabel}...")

        result = run_query(
            client,
            notebook_id,
            qtext,
            conversation_id=conversation_id,
            label=qid,
        )

        if result["status"] == "success" and result["answer"]:
            sections[qid] = {
                "label": qlabel,
                "answer": result["answer"],
            }
            # Carry conversation forward so each query builds on the previous
            conversation_id = result.get("conversation_id")
            sections_ok += 1
            answer_preview = result["answer"][:120].replace("\n", " ")
            print(f"     ✅ {len(result['answer'])} chars — {answer_preview}...")
        else:
            sections[qid] = {
                "label": qlabel,
                "answer": f"[EXTRACTION FAILED: {result.get('error', 'unknown error')}]",
            }
            sections_failed += 1
            print(f"     ❌ Failed: {result.get('error', 'unknown')}", file=sys.stderr)

        # Brief pause between queries to be respectful of rate limits
        if i < len(EXTRACTION_QUERIES) - 1:
            time.sleep(QUERY_DELAY_SECONDS)

    # ── Step 6: Save combined output ──
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        # Header
        f.write(f"# YouTube Context Extraction\n\n")
        f.write(f"**URL:** {youtube_url}\n")
        f.write(f"**Video ID:** {video_id}\n")
        f.write(f"**Source Title:** {source_title_final}\n")
        f.write(f"**Transcript:** {segment_count} segments, {transcript_result['char_count']:,} chars, lang={language}\n")
        f.write(f"**Notebook ID:** {notebook_id}\n")
        f.write(f"**Extracted:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Sections:** {sections_ok}/{len(EXTRACTION_QUERIES)} successful\n\n")
        f.write("---\n\n")

        # Each section
        for query_def in EXTRACTION_QUERIES:
            qid = query_def["id"]
            section = sections.get(qid, {})
            label = section.get("label", query_def["label"])
            answer = section.get("answer", "[No content]")

            f.write(f"## {label}\n\n")
            f.write(answer)
            f.write("\n\n---\n\n")

    print(f"\n  💾 Saved to: {output_path}")
    print(f"  📊 Sections: {sections_ok} OK, {sections_failed} failed")

    # ── Step 7: Cleanup ──
    if cleanup and source_id:
        print(f"\n  🧹 Cleaning up: removing source from notebook...")
        if delete_source(client, source_id):
            print(f"  ✅ Source removed")
        else:
            print(f"  ⚠️ Could not remove source (may need manual cleanup)", file=sys.stderr)

    return {
        "status": "success" if sections_ok > 0 else "error",
        "output_path": output_path,
        "sections_extracted": sections_ok,
        "sections_failed": sections_failed,
        "source_title": source_title_final,
        "transcript_chars": transcript_result["char_count"],
        "transcript_segments": segment_count,
    }


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Extract structured knowledge from a YouTube video via NotebookLM.",
        epilog=(
            "Example:\n"
            "  python youtube-context-runner.py "
            "--url \"https://www.youtube.com/watch?v=TokTT6GPq4Y\"\n\n"
            "NotebookLM will:\n"
            "  1. Ingest the YouTube video (extracts transcript)\n"
            "  2. Use a custom context-extraction role (goal=custom, response=longer)\n"
            "  3. Answer 7 targeted extraction queries to harvest all knowledge\n"
            "  4. Save a structured .md file with the full extracted context"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--url", required=True,
        help="YouTube URL to extract context from "
             "(e.g. https://www.youtube.com/watch?v=XXXX or https://youtu.be/XXXX)"
    )
    parser.add_argument(
        "--notebook-id",
        default=DEFAULT_NOTEBOOK_ID,
        help=f"Notebook UUID to use (default: {DEFAULT_NOTEBOOK_ID})"
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_ROOT,
        help=f"Output directory root (default: {DEFAULT_OUTPUT_ROOT})"
    )
    parser.add_argument(
        "--output-file",
        help="Explicit output file path (overrides --output-dir)"
    )
    parser.add_argument(
        "--no-cleanup", action="store_true",
        help="Keep the YouTube source in the notebook after extraction (default: remove it)"
    )
    parser.add_argument(
        "--no-cookie-refresh", action="store_true",
        help="Skip the initial cookie refresh (use cached cookies as-is)"
    )
    parser.add_argument(
        "--cdp-port", type=int, default=None,
        help=(
            "Chrome DevTools Protocol port where NotebookLM is open "
            "(default: auto-probe 9222, 9223, 9000 in order)"
        )
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-extract even if a valid output file already exists"
    )

    args = parser.parse_args()

    # ── Validate YouTube URL ──
    video_id = extract_video_id(args.url)
    if not video_id:
        print(f"ERROR: Could not extract video ID from URL: {args.url}", file=sys.stderr)
        print("Expected formats: https://www.youtube.com/watch?v=XXXX or https://youtu.be/XXXX")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  🎬 YouTube Context Extractor (via NotebookLM)")
    print(f"  Video ID: {video_id}")
    print(f"  URL: {args.url}")
    print(f"{'='*60}\n")

    # ── Initial cookie refresh ──
    if not args.no_cookie_refresh:
        print("Performing initial cookie refresh...")
        if silent_refresh_cookies(cdp_port=args.cdp_port, auto_launch=True):
            print("✅ Starting with fresh cookies.\n")
        else:
            print("⚠️  Could not refresh from Chrome — using cached cookies.\n")
    else:
        print("(Cookie refresh skipped)\n")

    # ── Get client ──
    try:
        from notebooklm_mcp.server import get_client
        client = get_client()
    except Exception as e:
        print(f"FATAL: Cannot authenticate: {e}", file=sys.stderr)
        sys.exit(1)

    # ── Resolve notebook ID ──
    notebook_id = args.notebook_id  # Has a default (DEFAULT_NOTEBOOK_ID)
    print(f"Using notebook: {notebook_id}")

    # ── Resolve output path ──
    if args.output_file:
        output_path = args.output_file
    else:
        # Fetch the real video title to name the output file
        print("  📌 Fetching video title...")
        video_title = fetch_youtube_title(video_id)
        safe_name = make_safe_filename(video_title)
        print(f"  📌 Title: {video_title}")
        os.makedirs(args.output_dir, exist_ok=True)
        output_path = os.path.join(args.output_dir, f"{safe_name}.md")

    # ── Skip if already extracted (and --force not set) ──
    # For title-based filenames we also scan the OUTPUT dir for any existing
    # file that embeds the video ID in its content header (handles renames).
    def _find_existing_extraction(out_dir: str, vid_id: str) -> str | None:
        """Scan out_dir for a .md file whose header contains this video ID."""
        try:
            for f in os.listdir(out_dir):
                if not f.endswith(".md"):
                    continue
                fpath = os.path.join(out_dir, f)
                with open(fpath, "r", encoding="utf-8", errors="ignore") as fp:
                    head = fp.read(1024)  # Only check the header block
                if vid_id in head:
                    return fpath
        except Exception:
            pass
        return None

    if not args.force:
        # Check the resolved output path first
        if is_extraction_valid(output_path):
            print(f"✅ Already extracted (content-validated): {output_path}")
            print("   Use --force to re-extract.")
            sys.exit(0)
        # Also scan the output dir for any title-named file containing this video ID
        if not args.output_file:
            existing = _find_existing_extraction(args.output_dir, video_id)
            if existing and is_extraction_valid(existing):
                print(f"✅ Already extracted as: {existing}")
                print("   Use --force to re-extract.")
                sys.exit(0)

    # ── Run extraction ──
    start_time = time.time()
    result = extract_youtube_context(
        youtube_url=args.url,
        video_id=video_id,
        notebook_id=notebook_id,
        output_path=output_path,
        cleanup=not args.no_cleanup,
    )
    elapsed = time.time() - start_time

    # ── Final summary ──
    print(f"\n{'='*60}")
    if result["status"] == "success":
        print(f"  🏁 EXTRACTION COMPLETE")
        print(f"  Video: {result.get('source_title', video_id)}")
        print(f"  Transcript: {result.get('transcript_segments', '?')} segments, {result.get('transcript_chars', 0):,} chars")
        print(f"  Sections extracted: {result['sections_extracted']}/{len(EXTRACTION_QUERIES)}")
        if result.get("sections_failed", 0) > 0:
            print(f"  Sections failed: {result['sections_failed']}")
        print(f"  Output: {result['output_path']}")
        print(f"  Time: {elapsed:.1f}s")
    else:
        print(f"  ❌ EXTRACTION FAILED")
        print(f"  Error: {result.get('error', 'unknown')}")
        print(f"  Time: {elapsed:.1f}s")
        sys.exit(1)
    print(f"{'='*60}")


if __name__ == "__main__":
    logger.info("YouTube context runner started, log file: %s", LOG_FILE)
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Interrupted by user (Ctrl+C)")
        print("\n\nInterrupted!")
        sys.exit(1)
    except Exception as e:
        logger.critical("FATAL ERROR", exc_info=True)
        print(f"\nFATAL ERROR: {e}")
        traceback.print_exc()
        sys.exit(1)
