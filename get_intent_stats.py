import os
import re
from collections import Counter

OUTPUT_DIR = r"C:\PROJECTS\robsky-ai-vertex\SUPERVISED FINE TUNING\ACCOUNTING_RAW_ANSWERS"

def get_stats():
    intents = []
    for filename in os.listdir(OUTPUT_DIR):
        if filename.startswith("Q") and filename.endswith(".md"):
            filepath = os.path.join(OUTPUT_DIR, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
                match = re.search(r"\*\*Intent:\*\*\s*(.+)", content)
                if match:
                    intents.append(match.group(1).strip())
    
    counts = Counter(intents)
    print("Intent Distribution:")
    for intent, count in counts.items():
        print(f"- {intent}: {count}")
    print(f"Total: {len(intents)}")

if __name__ == "__main__":
    get_stats()
