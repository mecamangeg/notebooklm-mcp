"""Dump the raw API response for a failed case."""
import os
import sys
import time
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
os.environ.setdefault("NOTEBOOKLM_BL", "boq_labs-tailwind-frontend_20260212.13_p0")

from notebooklm_mcp.server import get_client

NB_ID = "9daa06dc-b783-455a-b525-3c9cd3c36b9e"
TEST_FILE = r"C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown\2022\09_Sep\People v. Cericos, 929 Phil. 442 (G.R. No. 248997. September 5, 2022).md"
QUERY = "Generate SCRA-format syllabi for this case."

client = get_client()

# Check if source already exists, otherwise add it
print("Checking notebook state...")
nb_data = client.get_notebook(NB_ID)
source_ids = []
if isinstance(nb_data, list) and len(nb_data) > 0:
    nb_info = nb_data[0] if isinstance(nb_data[0], list) else nb_data
    if len(nb_info) > 1 and isinstance(nb_info[1], list):
        for src_item in nb_info[1]:
            if isinstance(src_item, list) and len(src_item) > 0:
                sid_wrapper = src_item[0]
                if isinstance(sid_wrapper, list) and len(sid_wrapper) > 0:
                    source_ids.append(sid_wrapper[0])

if source_ids:
    print(f"  Found {len(source_ids)} existing sources, using first one: {source_ids[0][:12]}...")
    source_id = source_ids[0]
else:
    print("  No sources, adding test case...")
    with open(TEST_FILE, "r", encoding="utf-8") as f:
        text = f.read()
    title = os.path.splitext(os.path.basename(TEST_FILE))[0]
    add_result = client.add_text_source(NB_ID, text=text, title=title)
    source_id = add_result["id"]
    print(f"  Added: {source_id}")
    time.sleep(3)

# Now query and capture the FULL raw response
print(f"\nQuerying with source_id={source_id[:12]}...")
result = client.query(NB_ID, query_text=QUERY, source_ids=[source_id])

print(f"\nResult dict keys: {list(result.keys()) if result else 'None'}")
if result:
    print(f"  answer: {result.get('answer')!r}")
    print(f"  answer type: {type(result.get('answer')).__name__}")
    print(f"  answer length: {len(result.get('answer', '') or '')}")
    print(f"  conversation_id: {result.get('conversation_id')}")
    print(f"  turn_number: {result.get('turn_number')}")
    
    raw_resp = result.get("raw_response", "")
    print(f"\n  Raw response (first 1000 chars):")
    print(f"  {raw_resp}")

# Now do a deeper parse of the full raw response
print("\n\n--- DEEP PARSE: Making raw request directly ---")
import urllib.parse

source_array = [[[source_id]]]
params = [source_array, QUERY, None, [2, None, [1]], "debug-conv"]
params_json = json.dumps(params, separators=(",", ":"))
f_req = [None, params_json]
f_req_json = json.dumps(f_req, separators=(",", ":"))

body_parts = [f"f.req={urllib.parse.quote(f_req_json, safe='')}"]
if client.csrf_token:
    body_parts.append(f"at={urllib.parse.quote(client.csrf_token, safe='')}")
body = "&".join(body_parts) + "&"

client._reqid_counter += 100000
url_params = {
    "bl": os.environ.get("NOTEBOOKLM_BL"),
    "hl": "en",
    "_reqid": str(client._reqid_counter),
    "rt": "c",
}
if client._session_id:
    url_params["f.sid"] = client._session_id

query_string = urllib.parse.urlencode(url_params)
url = f"{client.BASE_URL}{client.QUERY_ENDPOINT}?{query_string}"

http_client = client._get_client()
response = http_client.post(url, content=body)

print(f"HTTP Status: {response.status_code}")
print(f"Response length: {len(response.text)} chars")
print(f"\nFULL RAW RESPONSE:")
print("---START---")
print(response.text)
print("---END---")

# Parse the inner JSON to see what NotebookLM actually responded with
raw = response.text
if raw.startswith(")]}'"):
    raw = raw[4:]
lines = raw.strip().split("\n")
print(f"\n--- LINE-BY-LINE PARSE ({len(lines)} lines) ---")
for i, line in enumerate(lines):
    line_s = line.strip()
    if not line_s:
        print(f"  Line {i}: (empty)")
        continue
    try:
        num = int(line_s)
        print(f"  Line {i}: byte_count={num}")
        continue
    except ValueError:
        pass
    try:
        data = json.loads(line_s)
        print(f"  Line {i}: JSON parsed, type={type(data).__name__}")
        if isinstance(data, list):
            for j, item in enumerate(data):
                if isinstance(item, list) and len(item) >= 3 and item[0] == "wrb.fr":
                    inner_str = item[2]
                    if isinstance(inner_str, str):
                        try:
                            inner = json.loads(inner_str)
                            print(f"    Item {j}: inner JSON = {json.dumps(inner, indent=2)[:500]}")
                        except json.JSONDecodeError:
                            print(f"    Item {j}: inner string (not JSON) = {inner_str[:200]!r}")
                    else:
                        print(f"    Item {j}: inner = {str(item[2])[:200]}")
                else:
                    print(f"    Item {j}: {str(item)[:200]}")
    except json.JSONDecodeError:
        print(f"  Line {i}: not JSON = {line_s[:200]!r}")

# Clean up
try:
    client.delete_source(source_id)
    print("\nCleaned up source.")
except:
    pass
