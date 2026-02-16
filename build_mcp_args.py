"""Build MCP tool arguments for notebook_digest_multi from a volume directory.

Usage: py build_mcp_args.py Volume_001
Outputs JSON arguments ready for the MCP tool call.
"""
import json
import os
import sys

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

SOURCE_ROOT = r"C:\PROJECTS\e-scra\MARKDOWN"
OUTPUT_ROOT = r"C:\PROJECTS\notebooklm-mcp\CASE-DIGESTS"


def build_args(volume_name):
    src_dir = os.path.join(SOURCE_ROOT, volume_name)
    if not os.path.isdir(src_dir):
        print(f"ERROR: {src_dir} not found")
        sys.exit(1)

    files = sorted([
        os.path.join(src_dir, f)
        for f in os.listdir(src_dir)
        if f.endswith(".md")
    ])

    out_dir = os.path.join(OUTPUT_ROOT, volume_name)

    args = {
        "notebook_ids": NOTEBOOK_IDS,
        "file_paths": files,
        "output_dir": out_dir,
    }

    print(f"Volume: {volume_name}")
    print(f"Files: {len(files)}")
    print(f"Output: {out_dir}")
    print(json.dumps(args))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: py build_mcp_args.py Volume_NNN")
        sys.exit(1)
    build_args(sys.argv[1])
