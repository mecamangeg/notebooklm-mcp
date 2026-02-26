import os
import json
import shutil

# map filename to relative directory
with open("actually_missing_files.json", "r", encoding="utf-8") as f:
    files = json.load(f)

base_input_dir = r"C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown"
output_dir = r"C:\PROJECTS\notebooklm-mcp\with-generated-SYLLABI"
temp_dir = r"C:\PROJECTS\notebooklm-mcp\temp_digests"

# filename to relative path
mapping = {}
for path in files:
    if path.startswith(base_input_dir):
        rel = os.path.relpath(path, base_input_dir)
        # e.g., 2023\02_Feb\Case.md
        folder = os.path.dirname(rel)
        name = os.path.basename(path)
        generated_name = name.replace(".md", "-generated-syllabi.md")
        mapping[generated_name] = folder

success_count = 0
for generated_file in os.listdir(temp_dir):
    if generated_file in mapping:
        folder = mapping[generated_file]
        target_folder = os.path.join(output_dir, folder)
        os.makedirs(target_folder, exist_ok=True)
        
        src_path = os.path.join(temp_dir, generated_file)
        dst_path = os.path.join(target_folder, generated_file)
        
        # move it
        shutil.move(src_path, dst_path)
        success_count += 1
        print(f"Moved {generated_file} to {target_folder}")

print(f"Successfully moved {success_count} files.")
