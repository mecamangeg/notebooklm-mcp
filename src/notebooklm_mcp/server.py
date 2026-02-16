"""NotebookLM MCP Server."""

from typing import Any

from fastmcp import FastMCP

from .api_client import NotebookLMClient, extract_cookies_from_chrome_export, parse_timestamp

# Initialize MCP server
mcp = FastMCP(
    name="notebooklm",
    instructions="""NotebookLM MCP - Access NotebookLM (notebooklm.google.com).

**Auth:** Use save_auth_tokens with cookies from Chrome DevTools. CSRF/session auto-extracted.
**Confirmation:** Tools with confirm param require user approval before setting confirm=True.
**Studio:** After creating audio/video/infographic/slides, poll studio_status for completion.""",
)

# Global state
_client: NotebookLMClient | None = None


def get_client() -> NotebookLMClient:
    """Get or create the API client.

    Tries environment variables first, falls back to cached tokens from auth CLI.
    """
    global _client
    if _client is None:
        import os

        from .auth import load_cached_tokens

        cookie_header = os.environ.get("NOTEBOOKLM_COOKIES", "")
        csrf_token = os.environ.get("NOTEBOOKLM_CSRF_TOKEN", "")
        session_id = os.environ.get("NOTEBOOKLM_SESSION_ID", "")

        if cookie_header:
            # Use environment variables
            cookies = extract_cookies_from_chrome_export(cookie_header)
        else:
            # Try cached tokens from auth CLI
            cached = load_cached_tokens()
            if cached:
                cookies = cached.cookies
                csrf_token = csrf_token or cached.csrf_token
                session_id = session_id or cached.session_id
            else:
                raise ValueError(
                    "No authentication found. Either:\n"
                    "1. Run 'notebooklm-mcp-auth' to authenticate via Chrome, or\n"
                    "2. Set NOTEBOOKLM_COOKIES environment variable manually"
                )

        _client = NotebookLMClient(
            cookies=cookies,
            csrf_token=csrf_token,
            session_id=session_id,
        )
    return _client


@mcp.tool()
def notebook_list(max_results: int = 100) -> dict[str, Any]:
    """List all notebooks.

    Args:
        max_results: Maximum number of notebooks to return (default: 100)
    """
    try:
        client = get_client()
        notebooks = client.list_notebooks()

        # Count owned vs shared notebooks
        owned_count = sum(1 for nb in notebooks if nb.is_owned)
        shared_count = len(notebooks) - owned_count
        
        # Count notebooks shared by me (owned + is_shared=True)
        shared_by_me_count = sum(1 for nb in notebooks if nb.is_owned and nb.is_shared)

        return {
            "status": "success",
            "count": len(notebooks),
            "owned_count": owned_count,
            "shared_count": shared_count,
            "shared_by_me_count": shared_by_me_count,
            "notebooks": [
                {
                    "id": nb.id,
                    "title": nb.title,
                    "source_count": nb.source_count,
                    "url": nb.url,
                    "ownership": nb.ownership,
                    "is_shared": nb.is_shared,
                    "created_at": nb.created_at,
                    "modified_at": nb.modified_at,
                }
                for nb in notebooks[:max_results]
            ],
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def notebook_create(title: str = "") -> dict[str, Any]:
    """Create a new notebook.

    Args:
        title: Optional title for the notebook
    """
    try:
        client = get_client()
        notebook = client.create_notebook(title=title)

        if notebook:
            return {
                "status": "success",
                "notebook": {
                    "id": notebook.id,
                    "title": notebook.title,
                    "url": notebook.url,
                },
            }
        return {"status": "error", "error": "Failed to create notebook"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def notebook_get(notebook_id: str) -> dict[str, Any]:
    """Get notebook details with sources.

    Args:
        notebook_id: Notebook UUID
    """
    try:
        client = get_client()
        result = client.get_notebook(notebook_id)

        # Extract timestamps from metadata if available
        # Result structure: [title, sources, id, emoji, null, metadata, ...]
        # metadata[5] = modified_at, metadata[8] = created_at
        created_at = None
        modified_at = None
        if result and isinstance(result, list) and len(result) > 5:
            metadata = result[5]
            if isinstance(metadata, list):
                if len(metadata) > 5:
                    modified_at = parse_timestamp(metadata[5])
                if len(metadata) > 8:
                    created_at = parse_timestamp(metadata[8])

        return {
            "status": "success",
            "notebook": result,
            "created_at": created_at,
            "modified_at": modified_at,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def notebook_describe(notebook_id: str) -> dict[str, Any]:
    """Get AI-generated notebook summary with suggested topics.

    Args:
        notebook_id: Notebook UUID

    Returns: summary (markdown), suggested_topics list
    """
    try:
        client = get_client()
        result = client.get_notebook_summary(notebook_id)

        return {
            "status": "success",
            **result,  # Includes summary and suggested_topics
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def source_describe(source_id: str) -> dict[str, Any]:
    """Get AI-generated source summary with keyword chips.

    Args:
        source_id: Source UUID

    Returns: summary (markdown with **bold** keywords), keywords list
    """
    try:
        client = get_client()
        result = client.get_source_guide(source_id)

        return {
            "status": "success",
            **result,  # Includes summary and keywords
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def notebook_add_url(notebook_id: str, url: str) -> dict[str, Any]:
    """Add URL (website or YouTube) as source.

    Args:
        notebook_id: Notebook UUID
        url: URL to add
    """
    try:
        client = get_client()
        result = client.add_url_source(notebook_id, url=url)

        if result:
            return {
                "status": "success",
                "source": result,
            }
        return {"status": "error", "error": "Failed to add URL source"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def notebook_add_text(
    notebook_id: str,
    text: str,
    title: str = "Pasted Text",
) -> dict[str, Any]:
    """Add pasted text as source.

    Args:
        notebook_id: Notebook UUID
        text: Text content to add
        title: Optional title
    """
    try:
        client = get_client()
        result = client.add_text_source(notebook_id, text=text, title=title)

        if result:
            return {
                "status": "success",
                "source": result,
            }
        return {"status": "error", "error": "Failed to add text source"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def notebook_add_drive(
    notebook_id: str,
    document_id: str,
    title: str,
    doc_type: str = "doc",
) -> dict[str, Any]:
    """Add Google Drive document as source.

    Args:
        notebook_id: Notebook UUID
        document_id: Drive document ID (from URL)
        title: Display title
        doc_type: doc|slides|sheets|pdf
    """
    try:
        mime_types = {
            "doc": "application/vnd.google-apps.document",
            "docs": "application/vnd.google-apps.document",
            "slides": "application/vnd.google-apps.presentation",
            "sheets": "application/vnd.google-apps.spreadsheet",
            "pdf": "application/pdf",
        }

        mime_type = mime_types.get(doc_type.lower())
        if not mime_type:
            return {
                "status": "error",
                "error": f"Unknown doc_type '{doc_type}'. Use 'doc', 'slides', 'sheets', or 'pdf'.",
            }

        client = get_client()
        result = client.add_drive_source(
            notebook_id,
            document_id=document_id,
            title=title,
            mime_type=mime_type,
        )

        if result:
            return {
                "status": "success",
                "source": result,
            }
        return {"status": "error", "error": "Failed to add Drive source"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def notebook_query(
    notebook_id: str,
    query: str,
    source_ids: list[str] | None = None,
    conversation_id: str | None = None,
) -> dict[str, Any]:
    """Ask AI about EXISTING sources already in notebook. NOT for finding new sources.

    Use research_start instead for: deep research, web search, find new sources, Drive search.

    Args:
        notebook_id: Notebook UUID
        query: Question to ask
        source_ids: Source IDs to query (default: all)
        conversation_id: For follow-up questions
    """
    try:
        client = get_client()
        result = client.query(
            notebook_id,
            query_text=query,
            source_ids=source_ids,
            conversation_id=conversation_id,
        )

        if result:
            return {
                "status": "success",
                "answer": result.get("answer", ""),
                "conversation_id": result.get("conversation_id"),
            }
        return {"status": "error", "error": "Failed to query notebook"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def notebook_delete(
    notebook_id: str,
    confirm: bool = False,
) -> dict[str, Any]:
    """Delete notebook permanently. IRREVERSIBLE. Requires confirm=True.

    Args:
        notebook_id: Notebook UUID
        confirm: Must be True after user approval
    """
    if not confirm:
        return {
            "status": "error",
            "error": "Deletion not confirmed. You must ask the user to confirm "
                     "before deleting. Set confirm=True only after user approval.",
            "warning": "This action is IRREVERSIBLE. The notebook and all its "
                       "sources will be permanently deleted.",
        }

    try:
        client = get_client()
        result = client.delete_notebook(notebook_id)

        if result:
            return {
                "status": "success",
                "message": f"Notebook {notebook_id} has been permanently deleted.",
            }
        return {"status": "error", "error": "Failed to delete notebook"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def notebook_rename(
    notebook_id: str,
    new_title: str,
) -> dict[str, Any]:
    """Rename a notebook.

    Args:
        notebook_id: Notebook UUID
        new_title: New title
    """
    try:
        client = get_client()
        result = client.rename_notebook(notebook_id, new_title)

        if result:
            return {
                "status": "success",
                "notebook": {
                    "id": notebook_id,
                    "title": new_title,
                },
            }
        return {"status": "error", "error": "Failed to rename notebook"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def chat_configure(
    notebook_id: str,
    goal: str = "default",
    custom_prompt: str | None = None,
    response_length: str = "default",
) -> dict[str, Any]:
    """Configure notebook chat settings.

    Args:
        notebook_id: Notebook UUID
        goal: default|learning_guide|custom
        custom_prompt: Required when goal=custom (max 10000 chars)
        response_length: default|longer|shorter
    """
    try:
        client = get_client()
        result = client.configure_chat(
            notebook_id=notebook_id,
            goal=goal,
            custom_prompt=custom_prompt,
            response_length=response_length,
        )
        return result
    except ValueError as e:
        return {"status": "error", "error": str(e)}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def source_list_drive(notebook_id: str) -> dict[str, Any]:
    """List sources with types and Drive freshness status.

    Use before source_sync_drive to identify stale sources.

    Args:
        notebook_id: Notebook UUID
    """
    try:
        client = get_client()
        sources = client.get_notebook_sources_with_types(notebook_id)

        # Separate sources by syncability
        syncable_sources = []
        other_sources = []

        for src in sources:
            if src.get("can_sync"):
                # Check freshness for syncable sources (Drive docs and Gemini Notes)
                is_fresh = client.check_source_freshness(src["id"])
                src["is_fresh"] = is_fresh
                src["needs_sync"] = is_fresh is False
                syncable_sources.append(src)
            else:
                other_sources.append(src)

        # Count stale sources
        stale_count = sum(1 for s in syncable_sources if s.get("needs_sync"))

        return {
            "status": "success",
            "notebook_id": notebook_id,
            "summary": {
                "total_sources": len(sources),
                "syncable_sources": len(syncable_sources),
                "stale_sources": stale_count,
                "other_sources": len(other_sources),
            },
            "syncable_sources": syncable_sources,
            "other_sources": [
                {"id": s["id"], "title": s["title"], "type": s["source_type_name"]}
                for s in other_sources
            ],
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def source_sync_drive(
    source_ids: list[str],
    confirm: bool = False,
) -> dict[str, Any]:
    """Sync Drive sources with latest content. Requires confirm=True.

    Call source_list_drive first to identify stale sources.

    Args:
        source_ids: Source UUIDs to sync
        confirm: Must be True after user approval
    """
    if not confirm:
        return {
            "status": "error",
            "error": "Sync not confirmed. You must ask the user to confirm "
                     "before syncing. Set confirm=True only after user approval.",
            "hint": "First call source_list_drive to show stale sources, "
                    "then ask user to confirm before syncing.",
        }

    if not source_ids:
        return {
            "status": "error",
            "error": "No source_ids provided. Use source_list_drive to get source IDs.",
        }

    try:
        client = get_client()
        results = []
        synced_count = 0
        failed_count = 0

        for source_id in source_ids:
            try:
                result = client.sync_drive_source(source_id)
                if result:
                    results.append({
                        "source_id": source_id,
                        "status": "synced",
                        "title": result.get("title"),
                    })
                    synced_count += 1
                else:
                    results.append({
                        "source_id": source_id,
                        "status": "failed",
                        "error": "Sync returned no result",
                    })
                    failed_count += 1
            except Exception as e:
                results.append({
                    "source_id": source_id,
                    "status": "failed",
                    "error": str(e),
                })
                failed_count += 1

        return {
            "status": "success" if failed_count == 0 else "partial",
            "summary": {
                "total": len(source_ids),
                "synced": synced_count,
                "failed": failed_count,
            },
            "results": results,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def source_delete(
    source_id: str,
    confirm: bool = False,
) -> dict[str, Any]:
    """Delete source permanently. IRREVERSIBLE. Requires confirm=True.

    Args:
        source_id: Source UUID to delete
        confirm: Must be True after user approval
    """
    if not confirm:
        return {
            "status": "error",
            "error": "Deletion not confirmed. You must ask the user to confirm "
                     "before deleting. Set confirm=True only after user approval.",
            "warning": "This action is IRREVERSIBLE. The source will be "
                       "permanently deleted from the notebook.",
        }

    try:
        client = get_client()
        result = client.delete_source(source_id)

        if result:
            return {
                "status": "success",
                "message": f"Source {source_id} has been permanently deleted.",
            }
        return {"status": "error", "error": "Failed to delete source"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def research_start(
    query: str,
    source: str = "web",
    mode: str = "fast",
    notebook_id: str | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    """Deep research / fast research: Search web or Google Drive to FIND NEW sources.

    Use this for: "deep research on X", "find sources about Y", "search web for Z", "search Drive".
    Workflow: research_start -> poll research_status -> research_import.

    Args:
        query: What to search for (e.g. "quantum computing advances")
        source: web|drive (where to search)
        mode: fast (~30s, ~10 sources) | deep (~5min, ~40 sources, web only)
        notebook_id: Existing notebook (creates new if not provided)
        title: Title for new notebook
    """
    try:
        client = get_client()

        # Validate mode + source combination early
        if mode.lower() == "deep" and source.lower() == "drive":
            return {
                "status": "error",
                "error": "Deep Research only supports Web sources. Use mode='fast' for Drive.",
            }

        # Create notebook if needed
        if not notebook_id:
            notebook_title = title or f"Research: {query[:50]}"
            notebook = client.create_notebook(title=notebook_title)
            if not notebook:
                return {"status": "error", "error": "Failed to create notebook"}
            notebook_id = notebook.id
            created_notebook = True
        else:
            created_notebook = False

        # Start research
        result = client.start_research(
            notebook_id=notebook_id,
            query=query,
            source=source,
            mode=mode,
        )

        if result:
            response = {
                "status": "success",
                "task_id": result["task_id"],
                "notebook_id": notebook_id,
                "notebook_url": f"https://notebooklm.google.com/notebook/{notebook_id}",
                "query": query,
                "source": result["source"],
                "mode": result["mode"],
                "created_notebook": created_notebook,
            }

            # Add helpful message based on mode
            if result["mode"] == "deep":
                response["message"] = (
                    "Deep Research started. This takes 3-5 minutes. "
                    "Call research_status to check progress."
                )
            else:
                response["message"] = (
                    "Fast Research started. This takes about 30 seconds. "
                    "Call research_status to check progress."
                )

            return response

        return {"status": "error", "error": "Failed to start research"}
    except ValueError as e:
        return {"status": "error", "error": str(e)}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _compact_research_result(result: dict) -> dict:
    """Compact research result to save tokens.

    Truncates report to 500 chars and limits sources to first 10.
    Users can query the notebook for full details.
    """
    if not isinstance(result, dict):
        return result

    # Truncate report if present
    if "report" in result and result["report"]:
        report = result["report"]
        if len(report) > 500:
            result["report"] = report[:500] + f"\n\n... (truncated {len(report) - 500} characters. Query the notebook for full details)"

    # Limit sources shown
    if "sources" in result and isinstance(result["sources"], list):
        total_sources = len(result["sources"])
        if total_sources > 10:
            result["sources"] = result["sources"][:10]
            result["sources_truncated"] = f"Showing first 10 of {total_sources} sources. Set compact=False for all sources."

    return result


@mcp.tool()
def research_status(
    notebook_id: str,
    poll_interval: int = 30,
    max_wait: int = 300,
    compact: bool = True,
) -> dict[str, Any]:
    """Poll research progress. Blocks until complete or timeout.

    Args:
        notebook_id: Notebook UUID
        poll_interval: Seconds between polls (default: 30)
        max_wait: Max seconds to wait (default: 300, 0=single poll)
        compact: If True (default), truncate report and limit sources shown to save tokens.
                Use compact=False to get full details.
    """
    import time

    try:
        client = get_client()
        start_time = time.time()
        polls = 0

        while True:
            polls += 1
            result = client.poll_research(notebook_id)

            if not result:
                return {"status": "error", "error": "Failed to poll research status"}

            # If completed or no research found, return immediately
            if result.get("status") in ("completed", "no_research"):
                result["polls_made"] = polls
                result["wait_time_seconds"] = round(time.time() - start_time, 1)

                # Compact mode: truncate to save tokens
                if compact and result.get("status") == "completed":
                    result = _compact_research_result(result)

                return {
                    "status": "success",
                    "research": result,
                }

            # Check if we should stop waiting
            elapsed = time.time() - start_time
            if max_wait == 0 or elapsed >= max_wait:
                result["polls_made"] = polls
                result["wait_time_seconds"] = round(elapsed, 1)
                result["message"] = (
                    f"Research still in progress after {round(elapsed, 1)}s. "
                    f"Call research_status again to continue waiting."
                )

                # Compact mode even for in-progress
                if compact:
                    result = _compact_research_result(result)

                return {
                    "status": "success",
                    "research": result,
                }

            # Wait before next poll
            time.sleep(poll_interval)

    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def research_import(
    notebook_id: str,
    task_id: str,
    source_indices: list[int] | None = None,
) -> dict[str, Any]:
    """Import discovered sources into notebook.

    Call after research_status shows status="completed".

    Args:
        notebook_id: Notebook UUID
        task_id: Research task ID
        source_indices: Source indices to import (default: all)
    """
    try:
        client = get_client()

        # First, get the current research results to get source details
        poll_result = client.poll_research(notebook_id)

        if not poll_result or poll_result.get("status") == "no_research":
            return {
                "status": "error",
                "error": "No research found for this notebook. Run research_start first.",
            }

        if poll_result.get("status") != "completed":
            return {
                "status": "error",
                "error": f"Research is still in progress (status: {poll_result.get('status')}). "
                         "Wait for completion before importing.",
            }

        # Get sources from poll result
        all_sources = poll_result.get("sources", [])
        report_content = poll_result.get("report", "")

        if not all_sources:
            return {
                "status": "error",
                "error": "No sources found in research results.",
            }

        # Separate deep_report sources (type 5) from importable web/drive sources
        # Deep reports will be imported as text sources, web sources imported normally
        deep_report_source = None
        web_sources = []

        for src in all_sources:
            if src.get("result_type") == 5:
                deep_report_source = src
            else:
                web_sources.append(src)

        # Filter sources by indices if specified
        if source_indices is not None:
            sources_to_import = []
            invalid_indices = []
            for idx in source_indices:
                if 0 <= idx < len(all_sources):
                    sources_to_import.append(all_sources[idx])
                else:
                    invalid_indices.append(idx)

            if invalid_indices:
                return {
                    "status": "error",
                    "error": f"Invalid source indices: {invalid_indices}. "
                             f"Valid range is 0-{len(all_sources)-1}.",
                }
        else:
            sources_to_import = all_sources

        # Import web/drive sources (skip deep_report sources as they don't have URLs)
        web_sources_to_import = [s for s in sources_to_import if s.get("result_type") != 5]
        imported = client.import_research_sources(
            notebook_id=notebook_id,
            task_id=task_id,
            sources=web_sources_to_import,
        )

        # If deep research with report, import the report as a text source
        if deep_report_source and report_content:
            try:
                report_result = client.add_text_source(
                    notebook_id=notebook_id,
                    title=deep_report_source.get("title", "Deep Research Report"),
                    text=report_content,
                )
                if report_result:
                    imported.append({
                        "id": report_result.get("id"),
                        "title": report_result.get("title", "Deep Research Report"),
                    })
            except Exception as e:
                # Don't fail the entire import if report import fails
                pass

        return {
            "status": "success",
            "imported_count": len(imported),
            "total_available": len(all_sources),
            "sources": imported,
            "notebook_url": f"https://notebooklm.google.com/notebook/{notebook_id}",
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def audio_overview_create(
    notebook_id: str,
    source_ids: list[str] | None = None,
    format: str = "deep_dive",
    length: str = "default",
    language: str = "en",
    focus_prompt: str = "",
    confirm: bool = False,
) -> dict[str, Any]:
    """Generate audio overview. Requires confirm=True after user approval.

    Args:
        notebook_id: Notebook UUID
        source_ids: Source IDs (default: all)
        format: deep_dive|brief|critique|debate
        length: short|default|long
        language: BCP-47 code (en, es, fr, de, ja)
        focus_prompt: Optional focus text
        confirm: Must be True after user approval
    """
    if not confirm:
        return {
            "status": "pending_confirmation",
            "message": "Please confirm these settings before creating the audio overview:",
            "settings": {
                "notebook_id": notebook_id,
                "format": format,
                "length": length,
                "language": language,
                "focus_prompt": focus_prompt or "(none)",
                "source_ids": source_ids or "all sources",
            },
            "note": "Set confirm=True after user approves these settings.",
        }

    try:
        client = get_client()

        # Map format string to code
        format_codes = {
            "deep_dive": 1,
            "brief": 2,
            "critique": 3,
            "debate": 4,
        }
        format_code = format_codes.get(format.lower())
        if format_code is None:
            return {
                "status": "error",
                "error": f"Unknown format '{format}'. Use: deep_dive, brief, critique, or debate.",
            }

        # Map length string to code
        length_codes = {
            "short": 1,
            "default": 2,
            "long": 3,
        }
        length_code = length_codes.get(length.lower())
        if length_code is None:
            return {
                "status": "error",
                "error": f"Unknown length '{length}'. Use: short, default, or long.",
            }

        # Get source IDs if not provided
        if source_ids is None:
            sources = client.get_notebook_sources_with_types(notebook_id)
            source_ids = [s["id"] for s in sources if s["id"]]

        if not source_ids:
            return {
                "status": "error",
                "error": "No sources found in notebook. Add sources before creating audio overview.",
            }

        result = client.create_audio_overview(
            notebook_id=notebook_id,
            source_ids=source_ids,
            format_code=format_code,
            length_code=length_code,
            language=language,
            focus_prompt=focus_prompt,
        )

        if result:
            return {
                "status": "success",
                "artifact_id": result["artifact_id"],
                "type": "audio",
                "format": result["format"],
                "length": result["length"],
                "language": result["language"],
                "generation_status": result["status"],
                "message": "Audio generation started. Use studio_status to check progress.",
                "notebook_url": f"https://notebooklm.google.com/notebook/{notebook_id}",
            }
        return {"status": "error", "error": "Failed to create audio overview"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def video_overview_create(
    notebook_id: str,
    source_ids: list[str] | None = None,
    format: str = "explainer",
    visual_style: str = "auto_select",
    language: str = "en",
    focus_prompt: str = "",
    confirm: bool = False,
) -> dict[str, Any]:
    """Generate video overview. Requires confirm=True after user approval.

    Args:
        notebook_id: Notebook UUID
        source_ids: Source IDs (default: all)
        format: explainer|brief
        visual_style: auto_select|classic|whiteboard|kawaii|anime|watercolor|retro_print|heritage|paper_craft
        language: BCP-47 code (en, es, fr, de, ja)
        focus_prompt: Optional focus text
        confirm: Must be True after user approval
    """
    if not confirm:
        return {
            "status": "pending_confirmation",
            "message": "Please confirm these settings before creating the video overview:",
            "settings": {
                "notebook_id": notebook_id,
                "format": format,
                "visual_style": visual_style,
                "language": language,
                "focus_prompt": focus_prompt or "(none)",
                "source_ids": source_ids or "all sources",
            },
            "note": "Set confirm=True after user approves these settings.",
        }

    try:
        client = get_client()

        # Map format string to code
        format_codes = {
            "explainer": 1,
            "brief": 2,
        }
        format_code = format_codes.get(format.lower())
        if format_code is None:
            return {
                "status": "error",
                "error": f"Unknown format '{format}'. Use: explainer or brief.",
            }

        # Map style string to code
        style_codes = {
            "auto_select": 1,
            "custom": 2,
            "classic": 3,
            "whiteboard": 4,
            "kawaii": 5,
            "anime": 6,
            "watercolor": 7,
            "retro_print": 8,
            "heritage": 9,
            "paper_craft": 10,
        }
        style_code = style_codes.get(visual_style.lower())
        if style_code is None:
            valid_styles = ", ".join(style_codes.keys())
            return {
                "status": "error",
                "error": f"Unknown visual_style '{visual_style}'. Use: {valid_styles}",
            }

        # Get source IDs if not provided
        if source_ids is None:
            sources = client.get_notebook_sources_with_types(notebook_id)
            source_ids = [s["id"] for s in sources if s["id"]]

        if not source_ids:
            return {
                "status": "error",
                "error": "No sources found in notebook. Add sources before creating video overview.",
            }

        result = client.create_video_overview(
            notebook_id=notebook_id,
            source_ids=source_ids,
            format_code=format_code,
            visual_style_code=style_code,
            language=language,
            focus_prompt=focus_prompt,
        )

        if result:
            return {
                "status": "success",
                "artifact_id": result["artifact_id"],
                "type": "video",
                "format": result["format"],
                "visual_style": result["visual_style"],
                "language": result["language"],
                "generation_status": result["status"],
                "message": "Video generation started. Use studio_status to check progress.",
                "notebook_url": f"https://notebooklm.google.com/notebook/{notebook_id}",
            }
        return {"status": "error", "error": "Failed to create video overview"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def studio_status(notebook_id: str) -> dict[str, Any]:
    """Check studio content generation status and get URLs.

    Args:
        notebook_id: Notebook UUID
    """
    try:
        client = get_client()
        artifacts = client.poll_studio_status(notebook_id)

        # Separate by status
        completed = [a for a in artifacts if a["status"] == "completed"]
        in_progress = [a for a in artifacts if a["status"] == "in_progress"]

        return {
            "status": "success",
            "notebook_id": notebook_id,
            "summary": {
                "total": len(artifacts),
                "completed": len(completed),
                "in_progress": len(in_progress),
            },
            "artifacts": artifacts,
            "notebook_url": f"https://notebooklm.google.com/notebook/{notebook_id}",
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def studio_delete(
    notebook_id: str,
    artifact_id: str,
    confirm: bool = False,
) -> dict[str, Any]:
    """Delete studio artifact. IRREVERSIBLE. Requires confirm=True.

    Args:
        notebook_id: Notebook UUID
        artifact_id: Artifact UUID (from studio_status)
        confirm: Must be True after user approval
    """
    if not confirm:
        return {
            "status": "error",
            "error": "Deletion not confirmed. You must ask the user to confirm "
                     "before deleting. Set confirm=True only after user approval.",
            "warning": "This action is IRREVERSIBLE. The artifact will be permanently deleted.",
            "hint": "First call studio_status to list artifacts with their IDs and titles.",
        }

    try:
        client = get_client()
        result = client.delete_studio_artifact(artifact_id)

        if result:
            return {
                "status": "success",
                "message": f"Artifact {artifact_id} has been permanently deleted.",
                "notebook_id": notebook_id,
            }
        return {"status": "error", "error": "Failed to delete artifact"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def infographic_create(
    notebook_id: str,
    source_ids: list[str] | None = None,
    orientation: str = "landscape",
    detail_level: str = "standard",
    language: str = "en",
    focus_prompt: str = "",
    confirm: bool = False,
) -> dict[str, Any]:
    """Generate infographic. Requires confirm=True after user approval.

    Args:
        notebook_id: Notebook UUID
        source_ids: Source IDs (default: all)
        orientation: landscape|portrait|square
        detail_level: concise|standard|detailed
        language: BCP-47 code (en, es, fr, de, ja)
        focus_prompt: Optional focus text
        confirm: Must be True after user approval
    """
    if not confirm:
        return {
            "status": "pending_confirmation",
            "message": "Please confirm these settings before creating the infographic:",
            "settings": {
                "notebook_id": notebook_id,
                "orientation": orientation,
                "detail_level": detail_level,
                "language": language,
                "focus_prompt": focus_prompt or "(none)",
                "source_ids": source_ids or "all sources",
            },
            "note": "Set confirm=True after user approves these settings.",
        }

    try:
        client = get_client()

        # Map orientation string to code
        orientation_codes = {
            "landscape": 1,
            "portrait": 2,
            "square": 3,
        }
        orientation_code = orientation_codes.get(orientation.lower())
        if orientation_code is None:
            return {
                "status": "error",
                "error": f"Unknown orientation '{orientation}'. Use: landscape, portrait, or square.",
            }

        # Map detail_level string to code
        detail_codes = {
            "concise": 1,
            "standard": 2,
            "detailed": 3,
        }
        detail_code = detail_codes.get(detail_level.lower())
        if detail_code is None:
            return {
                "status": "error",
                "error": f"Unknown detail_level '{detail_level}'. Use: concise, standard, or detailed.",
            }

        # Get source IDs if not provided
        if source_ids is None:
            sources = client.get_notebook_sources_with_types(notebook_id)
            source_ids = [s["id"] for s in sources if s["id"]]

        if not source_ids:
            return {
                "status": "error",
                "error": "No sources found in notebook. Add sources before creating infographic.",
            }

        result = client.create_infographic(
            notebook_id=notebook_id,
            source_ids=source_ids,
            orientation_code=orientation_code,
            detail_level_code=detail_code,
            language=language,
            focus_prompt=focus_prompt,
        )

        if result:
            return {
                "status": "success",
                "artifact_id": result["artifact_id"],
                "type": "infographic",
                "orientation": result["orientation"],
                "detail_level": result["detail_level"],
                "language": result["language"],
                "generation_status": result["status"],
                "message": "Infographic generation started. Use studio_status to check progress.",
                "notebook_url": f"https://notebooklm.google.com/notebook/{notebook_id}",
            }
        return {"status": "error", "error": "Failed to create infographic"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def slide_deck_create(
    notebook_id: str,
    source_ids: list[str] | None = None,
    format: str = "detailed_deck",
    length: str = "default",
    language: str = "en",
    focus_prompt: str = "",
    confirm: bool = False,
) -> dict[str, Any]:
    """Generate slide deck. Requires confirm=True after user approval.

    Args:
        notebook_id: Notebook UUID
        source_ids: Source IDs (default: all)
        format: detailed_deck|presenter_slides
        length: short|default
        language: BCP-47 code (en, es, fr, de, ja)
        focus_prompt: Optional focus text
        confirm: Must be True after user approval
    """
    if not confirm:
        return {
            "status": "pending_confirmation",
            "message": "Please confirm these settings before creating the slide deck:",
            "settings": {
                "notebook_id": notebook_id,
                "format": format,
                "length": length,
                "language": language,
                "focus_prompt": focus_prompt or "(none)",
                "source_ids": source_ids or "all sources",
            },
            "note": "Set confirm=True after user approves these settings.",
        }

    try:
        client = get_client()

        # Map format string to code
        format_codes = {
            "detailed_deck": 1,
            "presenter_slides": 2,
        }
        format_code = format_codes.get(format.lower())
        if format_code is None:
            return {
                "status": "error",
                "error": f"Unknown format '{format}'. Use: detailed_deck or presenter_slides.",
            }

        # Map length string to code
        length_codes = {
            "short": 1,
            "default": 3,
        }
        length_code = length_codes.get(length.lower())
        if length_code is None:
            return {
                "status": "error",
                "error": f"Unknown length '{length}'. Use: short or default.",
            }

        # Get source IDs if not provided
        if source_ids is None:
            sources = client.get_notebook_sources_with_types(notebook_id)
            source_ids = [s["id"] for s in sources if s["id"]]

        if not source_ids:
            return {
                "status": "error",
                "error": "No sources found in notebook. Add sources before creating slide deck.",
            }

        result = client.create_slide_deck(
            notebook_id=notebook_id,
            source_ids=source_ids,
            format_code=format_code,
            length_code=length_code,
            language=language,
            focus_prompt=focus_prompt,
        )

        if result:
            return {
                "status": "success",
                "artifact_id": result["artifact_id"],
                "type": "slide_deck",
                "format": result["format"],
                "length": result["length"],
                "language": result["language"],
                "generation_status": result["status"],
                "message": "Slide deck generation started. Use studio_status to check progress.",
                "notebook_url": f"https://notebooklm.google.com/notebook/{notebook_id}",
            }
        return {"status": "error", "error": "Failed to create slide deck"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def report_create(
    notebook_id: str,
    source_ids: list[str] | None = None,
    report_format: str = "Briefing Doc",
    custom_prompt: str = "",
    language: str = "en",
    confirm: bool = False,
) -> dict[str, Any]:
    """Generate report. Requires confirm=True after user approval.

    Args:
        notebook_id: Notebook UUID
        source_ids: Source IDs (default: all)
        report_format: "Briefing Doc"|"Study Guide"|"Blog Post"|"Create Your Own"
        custom_prompt: Required for "Create Your Own"
        language: BCP-47 code (en, es, fr, de, ja)
        confirm: Must be True after user approval
    """
    if not confirm:
        return {
            "status": "pending_confirmation",
            "message": "Please confirm these settings before creating the report:",
            "settings": {
                "notebook_id": notebook_id,
                "report_format": report_format,
                "language": language,
                "custom_prompt": custom_prompt or "(none)",
                "source_ids": source_ids or "all sources",
            },
            "note": "Set confirm=True after user approves these settings.",
        }

    try:
        client = get_client()

        # Get source IDs if not provided
        if not source_ids:
            sources = client.get_notebook_sources_with_types(notebook_id)
            source_ids = [s["id"] for s in sources if s.get("id")]

        result = client.create_report(
            notebook_id=notebook_id,
            source_ids=source_ids,
            report_format=report_format,
            custom_prompt=custom_prompt,
            language=language,
        )

        if result:
            return {
                "status": "success",
                "artifact_id": result["artifact_id"],
                "type": "report",
                "format": result["format"],
                "language": result["language"],
                "generation_status": result["status"],
                "message": "Report generation started. Use studio_status to check progress.",
                "notebook_url": f"https://notebooklm.google.com/notebook/{notebook_id}",
            }
        return {"status": "error", "error": "Failed to create report"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def flashcards_create(
    notebook_id: str,
    source_ids: list[str] | None = None,
    difficulty: str = "medium",
    confirm: bool = False,
) -> dict[str, Any]:
    """Generate flashcards. Requires confirm=True after user approval.

    Args:
        notebook_id: Notebook UUID
        source_ids: Source IDs (default: all)
        difficulty: easy|medium|hard
        confirm: Must be True after user approval
    """
    if not confirm:
        return {
            "status": "pending_confirmation",
            "message": "Please confirm these settings before creating flashcards:",
            "settings": {
                "notebook_id": notebook_id,
                "difficulty": difficulty,
                "source_ids": source_ids or "all sources",
            },
            "note": "Set confirm=True after user approves these settings.",
        }

    try:
        client = get_client()

        # Get source IDs if not provided
        if not source_ids:
            sources = client.get_notebook_sources_with_types(notebook_id)
            source_ids = [s["id"] for s in sources if s.get("id")]

        result = client.create_flashcards(
            notebook_id=notebook_id,
            source_ids=source_ids,
            difficulty=difficulty,
        )

        if result:
            return {
                "status": "success",
                "artifact_id": result["artifact_id"],
                "type": "flashcards",
                "difficulty": result["difficulty"],
                "generation_status": result["status"],
                "message": "Flashcards generation started. Use studio_status to check progress.",
                "notebook_url": f"https://notebooklm.google.com/notebook/{notebook_id}",
            }
        return {"status": "error", "error": "Failed to create flashcards"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def quiz_create(
    notebook_id: str,
    source_ids: list[str] | None = None,
    question_count: int = 2,
    difficulty: int = 2,
    confirm: bool = False,
) -> dict[str, Any]:
    """Generate quiz. Requires confirm=True after user approval.

    Args:
        notebook_id: Notebook UUID
        source_ids: Source IDs (default: all)
        question_count: Number of questions (default: 2)
        difficulty: Difficulty level (default: 2)
        confirm: Must be True after user approval
    """
    if not confirm:
        return {
            "status": "pending_confirmation",
            "message": "Please confirm these settings before creating quiz:",
            "settings": {
                "notebook_id": notebook_id,
                "question_count": question_count,
                "difficulty": difficulty,
                "source_ids": source_ids or "all sources",
            },
            "note": "Set confirm=True after user approves these settings.",
        }

    try:
        client = get_client()

        if not source_ids:
            sources = client.get_notebook_sources_with_types(notebook_id)
            source_ids = [s["id"] for s in sources if s.get("id")]

        result = client.create_quiz(
            notebook_id=notebook_id,
            source_ids=source_ids,
            question_count=question_count,
            difficulty=difficulty,
        )

        if result:
            return {
                "status": "success",
                "artifact_id": result["artifact_id"],
                "type": "quiz",
                "question_count": result["question_count"],
                "difficulty": result["difficulty"],
                "generation_status": result["status"],
                "message": "Quiz generation started. Use studio_status to check progress.",
                "notebook_url": f"https://notebooklm.google.com/notebook/{notebook_id}",
            }
        return {"status": "error", "error": "Failed to create quiz"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def data_table_create(
    notebook_id: str,
    description: str,
    source_ids: list[str] | None = None,
    language: str = "en",
    confirm: bool = False,
) -> dict[str, Any]:
    """Generate data table. Requires confirm=True after user approval.

    Args:
        notebook_id: Notebook UUID
        description: Description of the data table to create
        source_ids: Source IDs (default: all)
        language: Language code (default: "en")
        confirm: Must be True after user approval
    """
    if not confirm:
        return {
            "status": "pending_confirmation",
            "message": "Please confirm these settings before creating data table:",
            "settings": {
                "notebook_id": notebook_id,
                "description": description,
                "language": language,
                "source_ids": source_ids or "all sources",
            },
            "note": "Set confirm=True after user approves these settings.",
        }

    try:
        client = get_client()

        if not source_ids:
            sources = client.get_notebook_sources_with_types(notebook_id)
            source_ids = [s["id"] for s in sources if s.get("id")]

        result = client.create_data_table(
            notebook_id=notebook_id,
            source_ids=source_ids,
            description=description,
            language=language,
        )

        if result:
            return {
                "status": "success",
                "artifact_id": result["artifact_id"],
                "type": "data_table",
                "description": result["description"],
                "generation_status": result["status"],
                "message": "Data table generation started. Use studio_status to check progress.",
                "notebook_url": f"https://notebooklm.google.com/notebook/{notebook_id}",
            }
        return {"status": "error", "error": "Failed to create data table"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def mind_map_create(
    notebook_id: str,
    source_ids: list[str] | None = None,
    title: str = "Mind Map",
    confirm: bool = False,
) -> dict[str, Any]:
    """Generate and save mind map. Requires confirm=True after user approval.

    Args:
        notebook_id: Notebook UUID
        source_ids: Source IDs (default: all)
        title: Display title
        confirm: Must be True after user approval
    """
    if not confirm:
        return {
            "status": "pending_confirmation",
            "message": "Please confirm these settings before creating the mind map:",
            "settings": {
                "notebook_id": notebook_id,
                "title": title,
                "source_ids": source_ids or "all sources",
            },
            "note": "Set confirm=True after user approves these settings.",
        }

    try:
        client = get_client()

        # Get source IDs if not provided
        if not source_ids:
            sources = client.get_notebook_sources_with_types(notebook_id)
            source_ids = [s["id"] for s in sources if s.get("id")]

        # Step 1: Generate the mind map
        gen_result = client.generate_mind_map(source_ids=source_ids)
        if not gen_result or not gen_result.get("mind_map_json"):
            return {"status": "error", "error": "Failed to generate mind map"}

        # Step 2: Save the mind map to the notebook
        save_result = client.save_mind_map(
            notebook_id=notebook_id,
            mind_map_json=gen_result["mind_map_json"],
            source_ids=source_ids,
            title=title,
        )

        if save_result:
            # Parse the JSON to get structure info
            import json
            try:
                mind_map_data = json.loads(save_result.get("mind_map_json", "{}"))
                root_name = mind_map_data.get("name", "Unknown")
                children_count = len(mind_map_data.get("children", []))
            except json.JSONDecodeError:
                root_name = "Unknown"
                children_count = 0

            return {
                "status": "success",
                "mind_map_id": save_result["mind_map_id"],
                "notebook_id": notebook_id,
                "title": save_result.get("title", title),
                "root_name": root_name,
                "children_count": children_count,
                "message": "Mind map created and saved successfully.",
                "notebook_url": f"https://notebooklm.google.com/notebook/{notebook_id}",
            }
        return {"status": "error", "error": "Failed to save mind map"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def mind_map_list(notebook_id: str) -> dict[str, Any]:
    """List all mind maps in a notebook.

    Args:
        notebook_id: Notebook UUID
    """
    try:
        client = get_client()
        mind_maps = client.list_mind_maps(notebook_id)

        return {
            "status": "success",
            "count": len(mind_maps),
            "mind_maps": [
                {
                    "mind_map_id": mm.get("mind_map_id"),
                    "title": mm.get("title", "Untitled"),
                    "created_at": mm.get("created_at"),
                }
                for mm in mind_maps
            ],
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# Essential cookies for NotebookLM API authentication
# Only these are needed - no need to save all 20+ cookies from the browser
ESSENTIAL_COOKIES = [
    "SID", "HSID", "SSID", "APISID", "SAPISID",  # Core auth cookies
    "__Secure-1PSID", "__Secure-3PSID",  # Secure session variants
    "__Secure-1PAPISID", "__Secure-3PAPISID",  # Secure API variants
    "OSID", "__Secure-OSID",  # Origin-bound session
    "__Secure-1PSIDTS", "__Secure-3PSIDTS",  # Timestamp tokens (rotate frequently)
    "SIDCC", "__Secure-1PSIDCC", "__Secure-3PSIDCC",  # Session cookies (rotate frequently)
]


@mcp.tool()
def save_auth_tokens(
    cookies: str,
    csrf_token: str = "",
    session_id: str = "",
    request_body: str = "",
    request_url: str = "",
) -> dict[str, Any]:
    """Save NotebookLM cookies. CSRF and session ID are auto-extracted.

    Args:
        cookies: Cookie header from Chrome DevTools get_network_request
        csrf_token: (deprecated, auto-extracted from request_body or page)
        session_id: (deprecated, auto-extracted from request_url or page)
        request_body: Optional request body from get_network_request (contains CSRF token)
        request_url: Optional request URL from get_network_request (contains session ID)
    """
    global _client

    try:
        import time
        import urllib.parse
        from .auth import AuthTokens, save_tokens_to_cache

        # Parse cookie string to dict
        all_cookies = {}
        for part in cookies.split("; "):
            if "=" in part:
                key, value = part.split("=", 1)
                all_cookies[key] = value

        # Validate required cookies
        required = ["SID", "HSID", "SSID", "APISID", "SAPISID"]
        missing = [c for c in required if c not in all_cookies]
        if missing:
            return {
                "status": "error",
                "error": f"Missing required cookies: {missing}",
            }

        # Filter to only essential cookies (reduces noise significantly)
        cookie_dict = {k: v for k, v in all_cookies.items() if k in ESSENTIAL_COOKIES}

        # Try to extract CSRF token from request body if provided
        if not csrf_token and request_body:
            # Request body format: f.req=...&at=<csrf_token>&
            if "at=" in request_body:
                # Extract and URL-decode the CSRF token
                at_part = request_body.split("at=")[1].split("&")[0]
                csrf_token = urllib.parse.unquote(at_part)

        # Try to extract session ID from request URL if provided
        if not session_id and request_url:
            # URL format: ...?f.sid=<session_id>&...
            if "f.sid=" in request_url:
                sid_part = request_url.split("f.sid=")[1].split("&")[0]
                session_id = urllib.parse.unquote(sid_part)

        # Create and save tokens
        # Note: csrf_token and session_id will be auto-extracted from page on first use if still empty
        tokens = AuthTokens(
            cookies=cookie_dict,
            csrf_token=csrf_token,  # May be empty - will be auto-extracted from page
            session_id=session_id,  # May be empty - will be auto-extracted from page
            extracted_at=time.time(),
        )
        save_tokens_to_cache(tokens)

        # Reset client so next call uses fresh tokens
        _client = None

        from .auth import get_cache_path

        # Build status message
        if csrf_token and session_id:
            token_msg = "CSRF token and session ID extracted from network request - no page fetch needed! ⚡"
        elif csrf_token:
            token_msg = "CSRF token extracted from network request. Session ID will be auto-extracted on first use."
        elif session_id:
            token_msg = "Session ID extracted from network request. CSRF token will be auto-extracted on first use."
        else:
            token_msg = "CSRF token and session ID will be auto-extracted on first API call (~1-2s one-time delay)."

        return {
            "status": "success",
            "message": f"Saved {len(cookie_dict)} essential cookies (filtered from {len(all_cookies)}). {token_msg}",
            "cache_path": str(get_cache_path()),
            "extracted_csrf": bool(csrf_token),
            "extracted_session_id": bool(session_id),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def check_auth_status() -> dict[str, Any]:
    """Validate NotebookLM authentication before starting a batch pipeline.

    Call this FIRST before any batch operations to catch expired cookies early,
    rather than failing mid-pipeline. Returns account info if auth is valid.
    """
    try:
        client = get_client()
        # Attempt a lightweight API call to validate auth
        notebooks = client.list_notebooks()
        return {
            "status": "success",
            "auth_valid": True,
            "notebook_count": len(notebooks),
            "message": "Authentication is valid. Ready for batch operations.",
        }
    except ValueError as e:
        error_msg = str(e)
        if "expired" in error_msg.lower() or "login" in error_msg.lower():
            return {
                "status": "error",
                "auth_valid": False,
                "error": "Cookies have expired. Re-extract fresh cookies from Chrome DevTools.",
                "hint": "Use save_auth_tokens with fresh cookies from Chrome DevTools.",
            }
        return {"status": "error", "auth_valid": False, "error": error_msg}
    except Exception as e:
        return {"status": "error", "auth_valid": False, "error": str(e)}


@mcp.tool()
def notebook_add_text_batch(
    notebook_id: str,
    sources: list[dict],
) -> dict[str, Any]:
    """Add multiple text sources to a notebook in one call. 10x faster than individual calls.

    Use this instead of calling notebook_add_text in a loop.

    Args:
        notebook_id: Notebook UUID
        sources: List of {"text": str, "title": str} objects to add
    """
    if not sources:
        return {"status": "error", "error": "No sources provided"}

    try:
        client = get_client()
        results = []
        success_count = 0
        fail_count = 0

        for i, src in enumerate(sources):
            text = src.get("text", "")
            title = src.get("title", f"Source {i + 1}")

            if not text:
                results.append({
                    "index": i,
                    "title": title,
                    "status": "skipped",
                    "error": "Empty text",
                })
                fail_count += 1
                continue

            try:
                result = client.add_text_source(notebook_id, text=text, title=title)
                if result:
                    results.append({
                        "index": i,
                        "title": title,
                        "status": "success",
                        "source_id": result.get("id"),
                    })
                    success_count += 1
                else:
                    results.append({
                        "index": i,
                        "title": title,
                        "status": "failed",
                        "error": "API returned no result",
                    })
                    fail_count += 1
            except Exception as e:
                results.append({
                    "index": i,
                    "title": title,
                    "status": "failed",
                    "error": str(e),
                })
                fail_count += 1

        return {
            "status": "success" if fail_count == 0 else "partial",
            "summary": {
                "total": len(sources),
                "success": success_count,
                "failed": fail_count,
            },
            "sources": results,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def notebook_add_local_files(
    notebook_id: str,
    file_paths: list[str],
    titles: list[str] | None = None,
) -> dict[str, Any]:
    """Add local files as text sources. Reads files from disk — no need to paste content.

    Avoids shuttling text through agent context window. Supports .md, .txt, .html files.

    Args:
        notebook_id: Notebook UUID
        file_paths: List of absolute file paths to read and add
        titles: Optional list of titles (one per file). Defaults to filename.
    """
    import os

    if not file_paths:
        return {"status": "error", "error": "No file paths provided"}

    try:
        client = get_client()
        results = []
        success_count = 0
        fail_count = 0

        for i, path in enumerate(file_paths):
            # Determine title
            if titles and i < len(titles):
                title = titles[i]
            else:
                title = os.path.splitext(os.path.basename(path))[0]

            # Read file
            if not os.path.exists(path):
                results.append({
                    "index": i,
                    "path": path,
                    "title": title,
                    "status": "failed",
                    "error": f"File not found: {path}",
                })
                fail_count += 1
                continue

            try:
                # Try UTF-8 first, fall back to latin-1
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        text = f.read()
                except UnicodeDecodeError:
                    with open(path, "r", encoding="latin-1") as f:
                        text = f.read()

                if not text.strip():
                    results.append({
                        "index": i,
                        "path": path,
                        "title": title,
                        "status": "skipped",
                        "error": "File is empty",
                    })
                    fail_count += 1
                    continue

                result = client.add_text_source(notebook_id, text=text, title=title)
                if result:
                    results.append({
                        "index": i,
                        "path": path,
                        "title": title,
                        "status": "success",
                        "source_id": result.get("id"),
                        "size_bytes": len(text.encode("utf-8")),
                    })
                    success_count += 1
                else:
                    results.append({
                        "index": i,
                        "path": path,
                        "title": title,
                        "status": "failed",
                        "error": "API returned no result",
                    })
                    fail_count += 1
            except Exception as e:
                results.append({
                    "index": i,
                    "path": path,
                    "title": title,
                    "status": "failed",
                    "error": str(e),
                })
                fail_count += 1

        return {
            "status": "success" if fail_count == 0 else "partial",
            "summary": {
                "total": len(file_paths),
                "success": success_count,
                "failed": fail_count,
            },
            "sources": results,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def notebook_query_batch(
    notebook_id: str,
    queries: list[dict],
) -> dict[str, Any]:
    """Query multiple sources in one call. Returns all results together.

    Use this instead of calling notebook_query in a loop.

    Args:
        notebook_id: Notebook UUID
        queries: List of {"query": str, "source_ids": list[str] (optional), "label": str (optional)}
    """
    if not queries:
        return {"status": "error", "error": "No queries provided"}

    try:
        client = get_client()
        results = []
        success_count = 0
        fail_count = 0

        for i, q in enumerate(queries):
            query_text = q.get("query", "")
            source_ids = q.get("source_ids")
            label = q.get("label", f"Query {i + 1}")

            if not query_text:
                results.append({
                    "index": i,
                    "label": label,
                    "status": "skipped",
                    "error": "Empty query",
                })
                fail_count += 1
                continue

            try:
                result = client.query(
                    notebook_id,
                    query_text=query_text,
                    source_ids=source_ids,
                )
                if result:
                    results.append({
                        "index": i,
                        "label": label,
                        "status": "success",
                        "answer": result.get("answer", ""),
                        "conversation_id": result.get("conversation_id"),
                    })
                    success_count += 1
                else:
                    results.append({
                        "index": i,
                        "label": label,
                        "status": "failed",
                        "error": "Query returned no result",
                    })
                    fail_count += 1
            except Exception as e:
                results.append({
                    "index": i,
                    "label": label,
                    "status": "failed",
                    "error": str(e),
                })
                fail_count += 1

        return {
            "status": "success" if fail_count == 0 else "partial",
            "summary": {
                "total": len(queries),
                "success": success_count,
                "failed": fail_count,
            },
            "results": results,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

DEFAULT_DIGEST_QUERY = (
    "Write a case digest for this Philippine Supreme Court decision following "
    "this exact format:\n\n"
    "SHORT_TITLE: [Provide a corrected short case title using 'v.' format, "
    "e.g. 'Agoy v. NLRC' or 'Heirs of Buensuceso v. Perez'. Use the primary "
    "petitioner surname and primary respondent surname/agency only. Remove "
    "first names, 'et al.', 'Inc.', and other unnecessary words. Keep it "
    "under 40 characters.]\n\n"
    "I. CAPTION\n"
    "Provide: Full case title (Petitioner v. Respondent), G.R. Number, "
    "date decided, Phil. Reports citation if available, and the ponente "
    "(the Justice who wrote the decision, formatted as 'J.' e.g. 'Carpio, J.'). "
    "Example: 'ASIAN TERMINALS, INC. v. SIMON ENTERPRISES, INC., "
    "G.R. No. 177116, February 27, 2013, 705 Phil. 83, Leonen, J.'\n\n"
    "II. FACTS\n"
    "State only the facts relevant to the main legal issue. Answer the "
    "Who, What, When, How, and Why. Include the procedural history "
    "(what the lower courts ruled) leading up to the Supreme Court. "
    "Be concise but complete.\n\n"
    "III. ISSUE/S\n"
    "Frame each issue as a question answerable by YES or NO, using the "
    "'Whether or not (W/N)' format. Example: 'W/N the contract of sale "
    "is void.' Include only the main legal issues.\n\n"
    "IV. RULING\n"
    "For each issue, start with a categorical YES or NO in bold, then "
    "explain the Court's reasoning. Integrate the ratio decidendi "
    "(the legal principle or doctrine applied) directly into the ruling "
    "explanation. Cite the specific legal provisions, doctrines, or "
    "jurisprudence the Court relied upon. If the petition was granted or "
    "denied, state the disposition at the end of this section.\n\n"
    "V. CONCURRING/DISSENTING OPINIONS (if any)\n"
    "If there are concurring, separate, or dissenting opinions, briefly "
    "note the Justice and the gist of their position. If none, omit "
    "this section entirely.\n\n"
    "IMPORTANT RULES:\n"
    "- Do NOT add a separate 'Ratio Decidendi' or 'Disposition' section. "
    "The ratio is part of the Ruling, and the disposition is stated at "
    "the end of the Ruling.\n"
    "- Use 'W/N' abbreviation for 'Whether or not' in issues.\n"
    "- Be precise with dates, amounts, and legal citations.\n"
    "- Keep the digest concise — a law student should be able to review "
    "it quickly before class.\n"
    "- The SHORT_TITLE line MUST be the very first line of your response."
)

# ── Corpus Profile Abstraction ─────────────────────────────────
# Maps corpus-specific field names for frontmatter handling.
# Auto-detected from each file's frontmatter, or overridden via corpus_type param.

CORPUS_PROFILES = {
    "elibrary": {
        "label": "SC e-Library",
        "short_title_field": "abridged_title",
        "extra_fields": [
            "doc_id", "phil_citation", "scra_citation",
            "word_count", "source_url", "citation_format",
        ],
    },
    "escra": {
        "label": "e-SCRA",
        "short_title_field": "short_title",
        "extra_fields": [
            "case_nature", "disposition",
            "source_type", "source_file",
        ],
    },
    "generic": {
        "label": "Generic",
        "short_title_field": "short_title",
        "extra_fields": [],
    },
}


def _detect_corpus(frontmatter: dict) -> str:
    """Auto-detect corpus type from frontmatter fields."""
    if frontmatter.get("source_type") == "SCRA":
        return "escra"
    if "doc_id" in frontmatter:
        return "elibrary"
    return "generic"


@mcp.tool()
def notebook_query_save(
    notebook_id: str,
    query: str,
    output_path: str,
    source_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Query notebook and save the answer directly to a .md file on disk.

    The answer text NEVER transits through the agent context — only metadata is returned.
    Use this instead of notebook_query when you want to save the result to a file.

    Args:
        notebook_id: Notebook UUID
        query: Question to ask
        output_path: Absolute path to save the .md file
        source_ids: Source IDs to query (default: all)
    """
    import os

    try:
        client = get_client()
        result = client.query(
            notebook_id,
            query_text=query,
            source_ids=source_ids,
        )

        if not result or not result.get("answer"):
            return {"status": "error", "error": "Query returned no answer"}

        answer = result["answer"]

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(answer)

        return {
            "status": "success",
            "output_path": output_path,
            "size_bytes": len(answer.encode("utf-8")),
            "conversation_id": result.get("conversation_id"),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def notebook_digest_pipeline(
    notebook_id: str,
    file_paths: list[str],
    output_dir: str,
    query_template: str = DEFAULT_DIGEST_QUERY,
    titles: list[str] | None = None,
    max_retries: int = 2,
    batch_size: int = 3,
    parallel: int = 2,
    delay: float = 1.0,
) -> dict[str, Any]:
    """Full pipeline: reads files from disk → adds as sources → queries each → saves digests.

    This is the OPTIMAL tool for batch case digest generation. The agent only sees
    metadata — no document text or digest content passes through the context window.

    Architecture (v3 — two-phase + batch + parallel):
      Phase 1: Add all files as sources (sequential, ~2s each)
      Phase 2: Query in multi-case batches using threaded parallelism

    Features:
    - Multi-case batching: queries batch_size cases per API call (default: 3)
    - Threaded parallelism: runs up to 'parallel' queries concurrently (default: 2)
    - Human-like delay: staggers parallel requests by 'delay' seconds
    - Per-document retry: retries failed queries up to max_retries times
    - Resume on re-run: skips files whose digest already exists in output_dir
    - Incremental saves: partial results are preserved even if pipeline times out

    Args:
        notebook_id: Notebook UUID
        file_paths: List of absolute file paths to process
        output_dir: Directory to save digest .md files
        query_template: Query to use for each source (default: Madera case digest)
        titles: Optional list of titles (one per file). Defaults to filename.
        max_retries: Max retry attempts per batch for failed queries (default: 2)
        batch_size: Number of cases to query in a single API call (default: 3)
        parallel: Max concurrent query threads (default: 2)
        delay: Seconds between starting parallel threads (default: 1.0)
    """
    import os
    import re
    import time
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if not file_paths:
        return {"status": "error", "error": "No file paths provided"}

    os.makedirs(output_dir, exist_ok=True)

    try:
        client = get_client()
    except Exception as e:
        return {"status": "error", "error": f"Auth failed: {e}"}

    # ── Compute titles and output paths ──────────────────────────
    entries = []
    for i, path in enumerate(file_paths):
        if titles and i < len(titles):
            title = titles[i]
        else:
            title = os.path.splitext(os.path.basename(path))[0]

        safe_title = "".join(
            c if c.isalnum() or c in " .-_()," else "_"
            for c in title
        ).strip() or f"digest_{i}"

        output_path = os.path.join(output_dir, f"{safe_title}-case-digest.md")
        entries.append({
            "index": i,
            "title": title,
            "path": path,
            "output_path": output_path,
            "safe_title": safe_title,
        })

    # ── Phase 0: Resume — skip already-completed digests ─────────
    results = []
    to_add = []
    skipped = 0

    for entry in entries:
        if os.path.exists(entry["output_path"]):
            existing_size = os.path.getsize(entry["output_path"])
            if existing_size > 100:
                results.append({
                    **entry,
                    "status": "skipped",
                    "output_size": existing_size,
                    "reason": "Digest already exists",
                })
                skipped += 1
                continue
        to_add.append(entry)

    if not to_add:
        return {
            "status": "success",
            "summary": {
                "total": len(entries),
                "sources_added": 0,
                "digests_saved": skipped,
                "skipped": skipped,
                "failed": 0,
            },
            "results": results,
        }

    # ── Phase 1: Add all files as sources (sequential) ───────────
    source_entries = []  # Entries that were successfully added

    for entry in to_add:
        path = entry["path"]
        if not os.path.exists(path):
            results.append({**entry, "status": "failed", "error": f"File not found: {path}"})
            continue

        try:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    text = f.read()
            except UnicodeDecodeError:
                with open(path, "r", encoding="latin-1") as f:
                    text = f.read()

            if not text.strip():
                results.append({**entry, "status": "skipped", "error": "File is empty"})
                continue

            add_result = client.add_text_source(notebook_id, text=text, title=entry["title"])
            if not add_result:
                results.append({**entry, "status": "failed", "error": "Failed to add source"})
                continue

            entry["source_id"] = add_result.get("id")
            entry["input_size"] = len(text.encode("utf-8"))
            source_entries.append(entry)

        except Exception as e:
            results.append({**entry, "status": "failed", "error": f"Add source failed: {e}"})

    if not source_entries:
        add_count = 0
        return {
            "status": "partial",
            "summary": {
                "total": len(entries), "sources_added": 0,
                "digests_saved": skipped, "skipped": skipped,
                "failed": len(to_add),
            },
            "results": results,
        }

    # ── Phase 2: Query in batches with parallelism ───────────────

    def _build_batch_query(batch_entries, template):
        """Build a multi-case query for a batch of sources."""
        if len(batch_entries) == 1:
            return template  # Single case — use template as-is
        # Multi-case: list the case titles so NotebookLM digests each
        case_list = "\n".join(
            f"- {e['title']}" for e in batch_entries
        )
        return (
            f"Write separate case digests for each of the following cases. "
            f"Use a clear separator (a line of dashes: ---) between each digest.\n\n"
            f"Cases:\n{case_list}\n\n"
            f"For EACH case, follow this format:\n{template}"
        )

    def _split_multi_digest(text, expected_count):
        """Split a multi-case response into individual digests."""
        if expected_count == 1:
            return [text]

        # Split on separator lines (----, ===, or "Case Digest:" headers)
        parts = re.split(
            r'\n-{3,}\n|\n={3,}\n|\n\*{3,}\n',
            text
        )
        # Filter out empty/trivial parts
        parts = [p.strip() for p in parts if p.strip() and len(p.strip()) > 100]

        if len(parts) == expected_count:
            return parts

        # Fallback: try splitting on "I. CAPTION" or "Case Digest:" headers
        header_parts = re.split(
            r'(?=\*{0,2}I\.\s*CAPTION\*{0,2})|(?=Case Digest:)',
            text,
            flags=re.IGNORECASE
        )
        header_parts = [p.strip() for p in header_parts if p.strip() and len(p.strip()) > 100]

        if len(header_parts) == expected_count:
            return header_parts

        # Last resort: if we got fewer parts, return what we have
        return parts if parts else [text]

    def _query_batch(batch_entries, batch_idx):
        """Query a batch of cases and save each digest to disk."""
        batch_results = []
        source_ids = [e["source_id"] for e in batch_entries]
        query_text = _build_batch_query(batch_entries, query_template)

        last_error = None
        answer = None

        for attempt in range(1, max_retries + 1):
            try:
                query_result = client.query(
                    notebook_id,
                    query_text=query_text,
                    source_ids=source_ids,
                )
                if query_result and query_result.get("answer"):
                    answer = query_result["answer"]
                    last_error = None
                    break
                else:
                    last_error = "Query returned no answer"
                    if attempt < max_retries:
                        time.sleep(2)
            except Exception as e:
                last_error = str(e)
                if attempt < max_retries:
                    time.sleep(2)

        if last_error or not answer:
            # All retries failed for this batch
            for entry in batch_entries:
                batch_results.append({
                    **entry,
                    "status": "partial",
                    "error": f"Query failed after {max_retries} attempts: {last_error}",
                    "attempts": max_retries,
                })
            return batch_results

        # Split multi-case response into individual digests
        digests = _split_multi_digest(answer, len(batch_entries))

        for j, entry in enumerate(batch_entries):
            if j < len(digests):
                digest_text = digests[j]
                try:
                    with open(entry["output_path"], "w", encoding="utf-8") as f:
                        f.write(digest_text)
                    batch_results.append({
                        **entry,
                        "status": "success",
                        "output_size": len(digest_text.encode("utf-8")),
                        "attempts": 1,
                        "batch_index": batch_idx,
                    })
                except Exception as e:
                    batch_results.append({
                        **entry,
                        "status": "partial",
                        "error": f"Save failed: {e}",
                    })
            else:
                # Fewer digests than expected — save entire response for this entry
                batch_results.append({
                    **entry,
                    "status": "partial",
                    "error": f"Could not split batch response (got {len(digests)} digests for {len(batch_entries)} cases)",
                    "batch_index": batch_idx,
                })

        # LIFO cleanup: delete sources after saving digests
        for entry in batch_entries:
            sid = entry.get("source_id")
            if sid:
                try:
                    client.delete_source(sid)
                except Exception:
                    pass  # Best-effort cleanup

        return batch_results

    # Create batches
    batches = []
    for b in range(0, len(source_entries), batch_size):
        batches.append(source_entries[b:b + batch_size])

    # Execute batches in parallel threads with staggered delay
    query_success = skipped  # Start with skipped count
    all_batch_results = []

    with ThreadPoolExecutor(max_workers=parallel) as executor:
        futures = {}
        for batch_idx, batch in enumerate(batches):
            if batch_idx > 0:
                time.sleep(delay)  # Human-like stagger
            future = executor.submit(_query_batch, batch, batch_idx)
            futures[future] = batch_idx

        for future in as_completed(futures):
            batch_results = future.result()
            all_batch_results.extend(batch_results)

    # Merge and count
    for br in all_batch_results:
        results.append(br)
        if br.get("status") == "success":
            query_success += 1

    total = len(entries)
    return {
        "status": "success" if query_success == total else "partial",
        "summary": {
            "total": total,
            "sources_added": len(source_entries),
            "digests_saved": query_success,
            "skipped": skipped,
            "failed": total - query_success,
            "batches": len(batches),
            "batch_size": batch_size,
            "parallel_threads": parallel,
        },
        "results": results,
    }


@mcp.tool()
def notebook_digest_multi(
    notebook_ids: list[str],
    file_paths: list[str],
    output_dir: str,
    query_template: str = DEFAULT_DIGEST_QUERY,
    corpus_type: str = "auto",
    batch_size: int = 1,
    max_retries: int = 3,
    delay: float = 1.0,
) -> dict[str, Any]:
    """Distribute files across MULTIPLE notebooks for maximum parallel throughput.

    Architecture: 1 case → 1 notebook → 1 query → 1 digest (no batching/splitting).
    Each notebook processes its share of files sequentially with LIFO cleanup.
    All notebooks run concurrently — true parallelism with zero contention.

    For N notebooks and F files:
      - Each notebook gets ceil(F/N) files
      - All notebooks process simultaneously
      - Per case: add source → query → validate → save → delete source

    Example: 10 files across 10 notebooks
      Notebook-1: add 1 → query → save → delete  ─┐
      Notebook-2: add 1 → query → save → delete  ─┤ all concurrent
      ...                                          ─┤
      Notebook-10: add 1 → query → save → delete ─┘
      Total: ~17s instead of ~170s (10x speedup)

    Args:
        notebook_ids: List of notebook UUIDs to distribute work across (use 10)
        file_paths: List of absolute file paths to process
        output_dir: Directory to save digest .md files
        query_template: Query template (default: Madera case digest)
        corpus_type: Corpus type — "auto" (detect from frontmatter), "elibrary", "escra", "generic"
        batch_size: Not used (kept for API compat, always processes 1 at a time)
        max_retries: Retry attempts per query (default: 2)
        delay: Seconds between staggered starts (default: 1.0)
    """
    import math
    import os
    import time
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if not file_paths:
        return {"status": "error", "error": "No file paths provided"}
    if not notebook_ids:
        return {"status": "error", "error": "No notebook IDs provided"}

    os.makedirs(output_dir, exist_ok=True)

    try:
        client = get_client()
    except Exception as e:
        return {"status": "error", "error": f"Auth failed: {e}"}

    n_notebooks = len(notebook_ids)
    n_files = len(file_paths)
    chunk_size = math.ceil(n_files / n_notebooks)

    # Split files into per-notebook chunks
    notebook_chunks = []
    for i in range(n_notebooks):
        start = i * chunk_size
        end = min(start + chunk_size, n_files)
        if start < n_files:
            notebook_chunks.append({
                "notebook_id": notebook_ids[i],
                "file_paths": file_paths[start:end],
                "notebook_index": i,
            })

    def _is_digest_valid(filepath):
        """Check if a digest file is complete and well-formed."""
        try:
            if not os.path.exists(filepath):
                return False
            size = os.path.getsize(filepath)
            if size < 500:  # Minimum viable digest is ~500 bytes
                return False
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            # Must contain at least 2 of these structural markers
            markers = 0
            for marker in ["CAPTION", "FACTS", "ISSUE", "RULING"]:
                if marker in content.upper():
                    markers += 1
            return markers >= 2
        except Exception:
            return False

    # ── Shared progress tracking (thread-safe) ──
    import threading
    import re as _re
    import sys
    _progress_lock = threading.Lock()
    _progress = {"done": 0, "success": 0, "failed": 0, "skipped": 0}
    _progress_log = []  # timestamped log entries
    _start_time = time.time()
    _total_queries = {"count": 0}  # mutable for closure access

    def _log_progress(msg):
        """Thread-safe progress logger."""
        elapsed = time.time() - _start_time
        entry = f"[{elapsed:6.1f}s] {msg}"
        with _progress_lock:
            _progress_log.append(entry)
        print(entry, file=sys.stderr, flush=True)

    def _process_notebook_chunk(chunk):
        """Process a chunk of files in a single notebook using LIFO source management.

        For each case: add source → query → validate → save → DELETE source.
        One case at a time (batch_size=1) eliminates all split/regex issues.
        """
        nb_id = chunk["notebook_id"]
        paths = chunk["file_paths"]
        nb_idx = chunk["notebook_index"]
        chunk_results = []
        sources_deleted = 0
        nb_queries = 0

        # Pre-filter: compute titles/paths, skip already-done files
        pending = []
        for path in paths:
            title = os.path.splitext(os.path.basename(path))[0]
            safe_title = "".join(
                c if c.isalnum() or c in " .-_()," else "_"
                for c in title
            ).strip() or f"digest_{nb_idx}"
            output_path = os.path.join(output_dir, f"{safe_title}-case-digest.md")

            # Resume: skip only if digest is VALID (content-checked, not just size)
            if _is_digest_valid(output_path):
                chunk_results.append({
                    "title": title, "path": path, "output_path": output_path,
                    "status": "skipped", "output_size": os.path.getsize(output_path),
                    "notebook_index": nb_idx,
                })
                continue

            pending.append({
                "title": title, "path": path, "output_path": output_path,
                "notebook_index": nb_idx,
            })

        if not pending:
            return chunk_results

        # Process one case at a time: add → query → validate → save → delete
        for item in pending:
            path = item["path"]
            source_id = None

            if not os.path.exists(path):
                chunk_results.append({
                    **item, "status": "failed", "error": "File not found",
                })
                continue

            try:
                # ── Read file ──
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        text = f.read()
                except UnicodeDecodeError:
                    with open(path, "r", encoding="latin-1") as f:
                        text = f.read()

                if not text.strip():
                    chunk_results.append({
                        **item, "status": "skipped", "error": "File is empty",
                    })
                    continue

                # ── Parse YAML frontmatter from source ──
                frontmatter = {}
                fm_match = _re.match(
                    r'^---\s*\r?\n(.*?)\r?\n---\s*\r?\n',
                    text, _re.DOTALL,
                )
                if fm_match:
                    fm_text = fm_match.group(1)
                    for line in fm_text.split("\n"):
                        line = line.strip()
                        if ":" in line:
                            key, _, val = line.partition(":")
                            key = key.strip()
                            val = val.strip().strip('"').strip("'")
                            if key:  # skip empty keys
                                frontmatter[key] = val

                # ── Add source ──
                add_result = client.add_text_source(nb_id, text=text, title=item["title"])
                if not add_result:
                    with _progress_lock:
                        _progress["done"] += 1
                        _progress["failed"] += 1
                    _log_progress(f"NB{nb_idx}: ❌ {_progress['done']}/{n_files} {item['title'][:40]} — add source failed")
                    chunk_results.append({
                        **item, "status": "failed", "error": "Failed to add source",
                    })
                    continue

                source_id = add_result.get("id")
                item["source_id"] = source_id
                item["input_size"] = len(text.encode("utf-8"))

                # ── Query with retry ──
                answer = None
                last_error = None
                for attempt in range(1, max_retries + 1):
                    try:
                        result = client.query(
                            nb_id, query_text=query_template,
                            source_ids=[source_id],
                        )
                        nb_queries += 1
                        with _progress_lock:
                            _total_queries["count"] += 1
                        if result and result.get("answer"):
                            answer = result["answer"]
                            break
                        last_error = "No answer returned"
                        if attempt < max_retries:
                            time.sleep(2)
                    except Exception as e:
                        last_error = str(e)
                        if attempt < max_retries:
                            time.sleep(2)

                if not answer:
                    with _progress_lock:
                        _progress["done"] += 1
                        _progress["failed"] += 1
                    _log_progress(f"NB{nb_idx}: ❌ {_progress['done']}/{n_files} {item['title'][:40]} — query failed")
                    chunk_results.append({
                        **item, "status": "failed",
                        "error": f"Query failed after {max_retries} attempts: {last_error}",
                    })
                    continue

                # ── Validate answer before saving ──
                markers_found = sum(
                    1 for m in ["CAPTION", "FACTS", "ISSUE", "RULING"]
                    if m in answer.upper()
                )
                if markers_found < 2 or len(answer) < 300:
                    with _progress_lock:
                        _progress["done"] += 1
                        _progress["failed"] += 1
                    _log_progress(f"NB{nb_idx}: ❌ {_progress['done']}/{n_files} {item['title'][:40]} — validation failed ({markers_found}/4 markers)")
                    chunk_results.append({
                        **item, "status": "failed",
                        "error": f"Response failed validation ({markers_found}/4 markers, {len(answer)} chars)",
                    })
                    continue

                # ── Extract SHORT_TITLE from response ──
                digest_body = answer
                short_title = ""
                st_match = _re.match(
                    r'^\s*(?:\*{0,2})SHORT[_\s]?TITLE(?:\*{0,2})\s*[:：]\s*(.+)',
                    answer, _re.IGNORECASE,
                )
                if st_match:
                    short_title = st_match.group(1).strip().strip('*').strip()
                    # Remove the SHORT_TITLE line from the digest body
                    digest_body = answer[st_match.end():].lstrip("\n\r")

                # ── Build output with preserved frontmatter ──
                output_content = digest_body
                # Detect corpus profile for field mapping
                if corpus_type == "auto":
                    _detected = _detect_corpus(frontmatter) if frontmatter else "generic"
                else:
                    _detected = corpus_type
                _profile = CORPUS_PROFILES.get(_detected, CORPUS_PROFILES["generic"])

                if frontmatter:
                    # Update the correct short title field based on corpus profile
                    if short_title:
                        _st_field = _profile["short_title_field"]
                        frontmatter[_st_field] = short_title
                    fm_lines = ["---"]
                    for key, val in frontmatter.items():
                        # Quote string values
                        if isinstance(val, str) and not val.isdigit():
                            fm_lines.append(f'{key}: "{val}"')
                        else:
                            fm_lines.append(f"{key}: {val}")
                    fm_lines.append("---")
                    output_content = "\n".join(fm_lines) + "\n\n" + digest_body

                # ── Save digest ──
                os.makedirs(os.path.dirname(item["output_path"]), exist_ok=True)
                with open(item["output_path"], "w", encoding="utf-8") as f:
                    f.write(output_content)
                with _progress_lock:
                    _progress["done"] += 1
                    _progress["success"] += 1
                st_display = short_title or frontmatter.get(_profile["short_title_field"], item["title"][:30])
                _log_progress(
                    f"NB{nb_idx}: ✅ {_progress['done']}/{n_files} "
                    f"{st_display}"
                )
                chunk_results.append({
                    **item, "status": "success",
                    "output_size": len(output_content.encode("utf-8")),
                    "short_title": short_title or frontmatter.get(_profile["short_title_field"], ""),
                })

            except Exception as e:
                with _progress_lock:
                    _progress["done"] += 1
                    _progress["failed"] += 1
                _log_progress(
                    f"NB{nb_idx}: ❌ {_progress['done']}/{n_files} "
                    f"{item['title'][:40]} — {str(e)[:60]}"
                )
                chunk_results.append({
                    **item, "status": "failed", "error": str(e),
                })
            finally:
                # ── LIFO cleanup: always delete source ──
                if source_id:
                    try:
                        client.delete_source(source_id)
                        sources_deleted += 1
                    except Exception:
                        pass  # Best-effort cleanup

        _log_progress(f"NB{nb_idx}: finished — {len(chunk_results)} processed, {sources_deleted} sources cleaned")
        return chunk_results

    # Execute all notebook chunks in parallel
    all_results = []
    with ThreadPoolExecutor(max_workers=n_notebooks) as executor:
        futures = {}
        for i, chunk in enumerate(notebook_chunks):
            if i > 0:
                time.sleep(delay)
            future = executor.submit(_process_notebook_chunk, chunk)
            futures[future] = i

        for future in as_completed(futures):
            all_results.extend(future.result())

    success = sum(1 for r in all_results if r.get("status") == "success")
    skipped = sum(1 for r in all_results if r.get("status") == "skipped")
    failed = n_files - success - skipped
    elapsed = time.time() - _start_time
    total_q = _total_queries["count"]
    qpm = (total_q / elapsed * 60) if elapsed > 0 else 0

    _log_progress(
        f"DONE — {success} saved, {skipped} skipped, {failed} failed "
        f"in {elapsed:.1f}s ({total_q} queries, {qpm:.1f} q/min)"
    )

    return {
        "status": "success" if (success + skipped) == n_files else "partial",
        "summary": {
            "total": n_files,
            "notebooks_used": len(notebook_chunks),
            "digests_saved": success + skipped,
            "skipped": skipped,
            "failed": failed,
            "elapsed_seconds": round(elapsed, 1),
            "total_queries": total_q,
            "queries_per_minute": round(qpm, 1),
        },
        "results": all_results,
        "progress_log": _progress_log,
    }

def main():
    """Run the MCP server."""
    mcp.run()
    return 0


if __name__ == "__main__":
    exit(main())
