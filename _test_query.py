"""Test a single query and save raw response for debugging."""
import sys, os, json, time
sys.path.insert(0, "src")
os.environ.setdefault("NOTEBOOKLM_BL", "boq_labs-tailwind-frontend_20260212.13_p0")

from notebooklm_mcp.api_client import NotebookLMClient
from notebooklm_mcp.auth import load_cached_tokens

tokens = load_cached_tokens()
client = NotebookLMClient(
    cookies=tokens.cookies,
    csrf_token=tokens.csrf_token,
    session_id=tokens.session_id,
)

notebook_id = "f6418509-d4a1-4e67-bf8e-294eb7b7d937"
query = "What are the five steps in IFRS 15 revenue recognition model?"

print(f"Querying notebook...")
http_client = client._get_client()

# Get source IDs
notebook_data = client.get_notebook(notebook_id)
source_ids = client._extract_source_ids_from_notebook(notebook_data)
print(f"Sources: {len(source_ids)}")

# Build request manually to capture raw response
import urllib.parse, uuid

sources_array = [[[sid]] for sid in source_ids]
conversation_id = str(uuid.uuid4())

params = [
    sources_array,
    query,
    None,
    [2, None, [1]],
    conversation_id,
]

params_json = json.dumps(params, separators=(",", ":"))
f_req = [None, params_json]
f_req_json = json.dumps(f_req, separators=(",", ":"))

body_parts = [f"f.req={urllib.parse.quote(f_req_json, safe='')}"]
if client.csrf_token:
    body_parts.append(f"at={urllib.parse.quote(client.csrf_token, safe='')}")
body = "&".join(body_parts) + "&"

client._reqid_counter += 100000
url_params = {
    "bl": os.environ.get("NOTEBOOKLM_BL", "boq_labs-tailwind-frontend_20260212.13_p0"),
    "hl": "en",
    "_reqid": str(client._reqid_counter),
    "rt": "c",
}
if client._session_id:
    url_params["f.sid"] = client._session_id

query_string = urllib.parse.urlencode(url_params)
url = f"{client.BASE_URL}{client.QUERY_ENDPOINT}?{query_string}"

print(f"POST {url[:100]}...")
response = http_client.post(url, content=body)
print(f"Status: {response.status_code}")
print(f"Response length: {len(response.text)} chars")

# Save raw response
with open("_raw_response.txt", "w", encoding="utf-8") as f:
    f.write(response.text)
print("Raw response saved to _raw_response.txt")

# Try parsing
answer = client._parse_query_response(response.text)
print(f"Parsed answer length: {len(answer)} chars")
if answer:
    print(f"Answer preview: {answer[:200]}...")
else:
    print("NO ANSWER PARSED!")
    # Show first 500 chars of raw response for debugging
    print(f"\nRaw response preview:\n{response.text[:500]}")
