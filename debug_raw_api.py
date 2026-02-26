"""Debug: print the raw get_notebook() response structure for a duplicate source."""
import sys, os, json
sys.path.insert(0, 'src')
os.environ.setdefault('NOTEBOOKLM_BL', 'boq_labs-tailwind-frontend_20260212.13_p0')

from notebooklm_mcp.server import get_client

client = get_client()
nb_id = "117e47ed-6385-4dc5-9abc-1bf57588a263"
data = client.get_notebook(nb_id)

nb = data[0] if isinstance(data[0], list) else data
sources_data = nb[1] if len(nb) > 1 else []

print(f"Total raw source entries: {len(sources_data)}")
print()

# Find and print the raw structure of the duplicate sources
seen_titles = {}
for i, src in enumerate(sources_data):
    if not isinstance(src, list) or len(src) < 2:
        continue
    title = src[1] if isinstance(src[1], str) else str(src[1])
    if 'types' in title or 'stream' in title:
        print(f"--- Entry [{i}]: title={repr(title)} ---")
        print(f"  src[0] (sid_wrapper): {repr(src[0])}")
        print(f"  src[1] (title):       {repr(src[1])}")
        if len(src) > 2:
            print(f"  src[2]:               {repr(src[2])[:120]}")
        print()
