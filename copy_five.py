import os, shutil

src_dir = r'C:\PROJECTS\supreme-court-scraper\Renamed-with-Native-Syllabi_RAW_HTML-1996-2022'
dst_dir = r'C:\PROJECTS\notebooklm-mcp\cases with all different opinions with native syllabi\for-extraction'

os.makedirs(dst_dir, exist_ok=True)

targets = [
    "G.R. No. 205813, January 10, 2018",
    "G.R. No. 107487, September 29, 1997",
    "G.R. No. 133250, November 11, 2003",
    "G.R. No. 131392, February 06, 2002",
    "G.R. No. 211833, April 07, 2015",
]

# Build index
file_index = {}
for root, dirs, files in os.walk(src_dir):
    for f in files:
        file_index[f] = os.path.join(root, f)

copied = 0
for target in targets:
    found = False
    for fname, fpath in file_index.items():
        if target in fname:
            shutil.copy2(fpath, os.path.join(dst_dir, fname))
            print(f"  OK: {fname}")
            copied += 1
            found = True
            break
    if not found:
        print(f"  NOT FOUND: {target}")

print(f"\nCopied {copied} / {len(targets)} files to {dst_dir}")
