"""Debug: count exactly how many sources get_notebook_sources() returns vs raw count."""
import sys, os
sys.path.insert(0, 'src')
os.environ.setdefault('NOTEBOOKLM_BL', 'boq_labs-tailwind-frontend_20260212.13_p0')

from notebooklm_mcp.server import get_client
sys.path.insert(0, str(__import__('pathlib').Path('.').resolve()))
import importlib.util, pathlib
_spec = importlib.util.spec_from_file_location('runner', pathlib.Path('angular-rag-runner.py'))
runner = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(runner)

client = get_client()
nb_id = "117e47ed-6385-4dc5-9abc-1bf57588a263"

# What does get_notebook_sources return?
parsed = runner.get_notebook_sources(client, nb_id)
print(f"get_notebook_sources() returned: {len(parsed)} entries")

angular = [s for s in parsed if s['title'].startswith('[Angular]')]
print(f"[Angular] sources in parsed result: {len(angular)}")
print()

# Also check raw
data = client.get_notebook(nb_id)
nb = data[0] if isinstance(data[0], list) else data
sources_raw = nb[1] if len(nb) > 1 else []
print(f"Raw sources_data length: {len(sources_raw)}")
print()

# What entries does the raw parser SKIP?
skipped = []
for i, src in enumerate(sources_raw):
    if not isinstance(src, list):
        skipped.append((i, 'not a list', type(src).__name__))
        continue
    if len(src) < 2:
        skipped.append((i, 'too short', len(src)))
        continue
    sid_wrapper = src[0]
    sid = sid_wrapper[0] if isinstance(sid_wrapper, list) and sid_wrapper else None
    if not sid:
        skipped.append((i, 'no sid', repr(sid_wrapper)[:60]))

print(f"Entries SKIPPED by parser: {len(skipped)}")
for s in skipped:
    print(f"  [{s[0]}] reason={s[1]} detail={s[2]}")

# Check duplicate between parsed and actual
from collections import Counter
titles = Counter(s['title'] for s in parsed)
print()
print("Title counts (parsed):")
for t, c in sorted(titles.items()):
    if c > 1 or 'types' in t or 'stream' in t:
        print(f"  {c}x  {t}")
