"""Time and motion study: Pipeline vs Parallel query_save vs Batch query.

Compares wall-clock time for 3 approaches to generating case digests:
- Method A: Single notebook_digest_pipeline call (sequential inside server)
- Method B: notebook_add_local_files + N parallel notebook_query_save calls 
            (serialized by proxy mutex, but each is a separate MCP call)
- Method C: notebook_add_local_files + notebook_query_batch (single batch call)

Usage: 
  This script is run by the agent, not standalone.
  It measures time by wrapping MCP tool calls with timestamps.
"""

import json
import time
import sys
import os

def format_duration(seconds):
    """Format seconds to human-readable string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{minutes}m {secs:.1f}s"

def print_results(method_name, start_time, end_time, doc_count, results=None):
    """Pretty-print timing results."""
    total = end_time - start_time
    per_doc = total / doc_count if doc_count > 0 else 0
    
    print(f"\n{'='*60}")
    print(f"  {method_name}")
    print(f"{'='*60}")
    print(f"  Documents:    {doc_count}")
    print(f"  Total time:   {format_duration(total)}")
    print(f"  Per document: {format_duration(per_doc)}")
    if results:
        for k, v in results.items():
            print(f"  {k}: {v}")
    print(f"{'='*60}")
    return total

if __name__ == "__main__":
    print("This script provides timing utilities for the MCP time study.")
    print("Run the time study through the agent's MCP tool calls.")
