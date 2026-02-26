"""
Debug: inspect PRE-FLIGHT SYNC matching logic.
Shows what titles the runner generates vs what titles are in the notebook.
Also checks for title mismatches that would cause update instead of skip.
"""
import sys, os
sys.path.insert(0, 'src')
os.environ.setdefault('NOTEBOOKLM_BL', 'boq_labs-tailwind-frontend_20260212.13_p0')

from pathlib import Path
from notebooklm_mcp.server import get_client

NB_IDS = [
    "117e47ed-6385-4dc5-9abc-1bf57588a263",
    "b0376e17-644a-4228-8911-fdce0439a672",
    "493bbdb5-7ca4-409f-bf96-673d86311d9e",
]
output_dir = Path('ANGULAR-RAG-SOURCES')
md_files = sorted(p for p in output_dir.glob('*.md') if not p.name.startswith('upload-log'))

# Compute titles the runner would generate
runner_titles = {}
for p in md_files:
    title = f"[Angular] {p.stem.replace('__', ' / ').replace('_', ' ')}"
    runner_titles[title] = p.name

client = get_client()

for nb_id in NB_IDS:
    print(f"\n{'='*60}")
    print(f"Notebook: {nb_id[:8]}")
    print(f"{'='*60}")

    # Get actual notebook sources
    data = client.get_notebook(nb_id)
    nb_sources = {}  # title -> [id, id, ...]
    if isinstance(data, list) and data:
        nb = data[0] if isinstance(data[0], list) else data
        if len(nb) > 1 and isinstance(nb[1], list):
            for s in nb[1]:
                if isinstance(s, list) and len(s) > 1:
                    sid_wrapper = s[0]
                    sid = sid_wrapper[0] if isinstance(sid_wrapper, list) and sid_wrapper else None
                    title = s[1] if isinstance(s[1], str) else str(s[1])
                    if title.startswith('[Angular]'):
                        nb_sources.setdefault(title, [])
                        if sid:
                            nb_sources[title].append(sid)

    print(f"Sources in notebook: {sum(len(v) for v in nb_sources.values())} total, {len(nb_sources)} unique titles")

    # Find titles in runner but NOT in notebook (would be uploaded as new)
    missing_in_nb = set(runner_titles) - set(nb_sources)
    # Find titles in notebook but NOT in runner (orphaned)
    orphaned = set(nb_sources) - set(runner_titles)
    # Duplicates
    dupes = {t: v for t, v in nb_sources.items() if len(v) > 1}

    if missing_in_nb:
        print(f"\n  MISSING from notebook (would be uploaded as NEW):")
        for t in sorted(missing_in_nb):
            print(f"    - {t}")
    if orphaned:
        print(f"\n  ORPHANED in notebook (no matching MD file):")
        for t in sorted(orphaned):
            print(f"    - {t}  ({len(nb_sources[t])} copies)")
    if dupes:
        print(f"\n  DUPLICATES in notebook:")
        for t, ids in sorted(dupes.items()):
            print(f"    - {t}  ({len(ids)} copies, IDs: {[i[:8] for i in ids]})")
    if not missing_in_nb and not orphaned and not dupes:
        print("  ✅ All clean — 40 unique matching sources")
