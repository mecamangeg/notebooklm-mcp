import json
import os

with open("remaining_files.json", "r", encoding="utf-8") as f:
    remaining_files = json.load(f)

input_base_dir = r"C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown"
output_base_dir = r"C:\PROJECTS\notebooklm-mcp\with-generated-SYLLABI"

missing_files = []

for file_path in remaining_files:
    # Get the relative path from the input base dir
    if file_path.startswith(input_base_dir):
        rel_path = os.path.relpath(file_path, input_base_dir)
        # Change .md to -generated-syllabi.md
        output_name = rel_path.replace(".md", "-generated-syllabi.md")
        output_file_path = os.path.join(output_base_dir, output_name)
        
        if not os.path.exists(output_file_path):
            missing_files.append(file_path)
            print(f"Missing: {output_file_path}")

print(f"Total missing files: {len(missing_files)}")

with open("actually_missing_files.json", "w", encoding="utf-8") as f:
    json.dump(missing_files, f, indent=2)
