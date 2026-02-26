import os
import json
import re

with open("actually_missing_files.json", "r", encoding="utf-8") as f:
    files = json.load(f)

os.makedirs("temp_clean", exist_ok=True)

censored_words = ["rape", "raped", "lasciviousness", "trafficking", "sexual", "sex", "prostitution", "abuse", "abusive", "molest", "molested", "drugging", "drugged", "force", "penetration"]

sanitized_files = []
for file_path in files:
    filename = os.path.basename(file_path)
    safe_path = os.path.join("temp_clean", filename)
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()
    
    # regex substitution
    for w in censored_words:
        # replace case insensitive
        pattern = re.compile(re.escape(w), re.IGNORECASE)
        text = pattern.sub("████", text)
        
    with open(safe_path, "w", encoding="utf-8") as f:
        f.write(text)
    sanitized_files.append(safe_path)

with open("temp_clean_files.json", "w", encoding="utf-8") as f:
    json.dump(sanitized_files, f)
