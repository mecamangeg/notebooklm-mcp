import os, shutil

src_dir = r'C:\PROJECTS\supreme-court-scraper\Renamed-with-Native-Syllabi_RAW_HTML-1996-2022'
dst_dir = r'C:\PROJECTS\notebooklm-mcp\cases with all different opinions with native syllabi'

os.makedirs(dst_dir, exist_ok=True)

# Build index of all files in source (recursively)
file_index = {}
for root, dirs, files in os.walk(src_dir):
    for f in files:
        file_index[f] = os.path.join(root, f)

print(f"Indexed {len(file_index)} files in source directory")

# Read the results file to get filenames
results = []
with open('opinions_results.txt', 'r', encoding='utf-8') as fh:
    for line in fh:
        line = line.strip()
        if line and line[0].isdigit() and '. ' in line:
            filename = line.split('. ', 1)[1]
            results.append(filename)

copied = 0
errors = []
for filename in results:
    if filename in file_index:
        shutil.copy2(file_index[filename], os.path.join(dst_dir, filename))
        copied += 1
    else:
        errors.append(filename)

print(f"Copied {copied} / {len(results)} files to:")
print(f"  {dst_dir}")
if errors:
    print(f"\n{len(errors)} files not found:")
    for e in errors[:10]:
        print(f"  {e}")
    if len(errors) > 10:
        print(f"  ... and {len(errors) - 10} more")
