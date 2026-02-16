"""
Convert NotebookLM MCP query responses (JSON) to clean Markdown files.

Usage:
    # Single file:
    python save_digests.py output.json -o "Case Name-case-digest.md"

    # Batch from directory of JSON files + label mapping:
    python save_digests.py batch --input-dir ./json_outputs --output-dir ./2013 --mapping mapping.json

    # Pipe from stdin:
    echo '{"status":"success","answer":"# Hello"}' | python save_digests.py - -o hello.md
"""
import argparse
import json
import os
import sys
from pathlib import Path


def extract_answer(json_data: str | dict) -> str:
    """Extract the 'answer' field from a NotebookLM query response."""
    if isinstance(json_data, str):
        data = json.loads(json_data)
    else:
        data = json_data

    if data.get("status") != "success":
        raise ValueError(f"Response has error status: {data.get('error', 'unknown')}")

    answer = data.get("answer", "")
    if not answer:
        raise ValueError("No answer found in response")

    return answer


def save_markdown(content: str, output_path: str) -> None:
    """Save markdown content to a file, creating directories as needed."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  ✓ Saved: {output_path} ({len(content):,} chars)")


def process_single(input_path: str, output_path: str) -> None:
    """Process a single JSON file to markdown."""
    if input_path == "-":
        raw = sys.stdin.read()
    else:
        with open(input_path, "r", encoding="utf-8") as f:
            raw = f.read()

    answer = extract_answer(raw)
    save_markdown(answer, output_path)


def process_batch(input_dir: str, output_dir: str, mapping: dict | None = None) -> None:
    """Process all JSON files in a directory to markdown.

    Args:
        input_dir: Directory containing JSON response files
        output_dir: Directory to write .md files to
        mapping: Optional dict mapping input filenames to output filenames.
                 If None, uses input filename with .md extension.
    """
    input_path = Path(input_dir)
    json_files = sorted(input_path.glob("*.json")) + sorted(input_path.glob("*.txt"))

    if not json_files:
        print(f"No JSON/TXT files found in {input_dir}")
        return

    success = 0
    failed = 0

    for jf in json_files:
        try:
            with open(jf, "r", encoding="utf-8") as f:
                raw = f.read()

            answer = extract_answer(raw)

            # Determine output filename
            if mapping and jf.name in mapping:
                out_name = mapping[jf.name]
            elif mapping and jf.stem in mapping:
                out_name = mapping[jf.stem]
            else:
                out_name = jf.stem + "-case-digest.md"

            out_path = os.path.join(output_dir, out_name)
            save_markdown(answer, out_path)
            success += 1
        except Exception as e:
            print(f"  ✗ Failed: {jf.name} — {e}")
            failed += 1

    print(f"\nDone: {success} saved, {failed} failed, {len(json_files)} total")


def main():
    parser = argparse.ArgumentParser(
        description="Convert NotebookLM query JSON responses to Markdown files"
    )
    parser.add_argument("input", nargs="?", help="Input JSON file (or '-' for stdin)")
    parser.add_argument("-o", "--output", help="Output .md file path")
    parser.add_argument("--batch", action="store_true", help="Batch mode")
    parser.add_argument("--input-dir", "-i", help="[batch] Directory with JSON files")
    parser.add_argument("--output-dir", "-d", help="[batch] Output directory for .md files")
    parser.add_argument("--mapping", "-m", help="[batch] JSON mapping file")

    args = parser.parse_args()

    if args.batch:
        if not args.input_dir or not args.output_dir:
            parser.error("--batch requires --input-dir and --output-dir")
        mapping = None
        if args.mapping:
            with open(args.mapping, "r") as f:
                mapping = json.load(f)
        process_batch(args.input_dir, args.output_dir, mapping)
    elif args.input and args.output:
        process_single(args.input, args.output)
    else:
        parser.print_help()



if __name__ == "__main__":
    main()
