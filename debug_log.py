"""Debug: inspect upload log entries and hash matching for the two duplicate files."""
import sys, os, json, hashlib
sys.path.insert(0, 'src')
os.environ.setdefault('NOTEBOOKLM_BL', 'boq_labs-tailwind-frontend_20260212.13_p0')

from pathlib import Path

output_dir = Path('ANGULAR-RAG-SOURCES')
log_path = output_dir / 'upload-log-117e47ed.json'
log = json.loads(log_path.read_text())

print(f"Total log entries: {len(log)}")
print()

# Check the two problem files and ALL log entries
for fname in ['models__types.md', 'services__stream.service.md']:
    p = output_dir / fname
    content = p.read_text(encoding='utf-8', errors='replace')
    actual_hash = hashlib.sha256(content.encode('utf-8', errors='replace')).hexdigest()
    actual_short = actual_hash[:16]

    print(f"=== {fname} ===")
    print(f"  Actual content hash: {actual_short}")

    # Try matching by any key
    matched = []
    for key, entry in log.items():
        if fname in key or fname.replace('.md', '') in key:
            matched.append((key, entry))

    if matched:
        for key, entry in matched:
            stored_hash = entry.get('content_hash', 'MISSING')
            stored_short = stored_hash[:16] if stored_hash != 'MISSING' else 'MISSING'
            match = actual_short == stored_short
            print(f"  Log key:       {repr(key)}")
            print(f"  Stored hash:   {stored_short}")
            print(f"  Hash match:    {match}")
            print(f"  Source ID:     {entry.get('source_id', 'N/A')}")
    else:
        print("  NOT FOUND in upload log!")
    print()

# Also show what check_upload_status_loaded returns
print("=== check_upload_status_loaded results ===")
import angular_rag_core as core

for fname in ['models__types.md', 'services__stream.service.md']:
    p = output_dir / fname
    content = p.read_text(encoding='utf-8', errors='replace')
    status, old_sid = core.check_upload_status_loaded(str(p), content, log)
    print(f"  {fname}: status={status!r}, old_sid={str(old_sid)[:16] if old_sid else None}")
