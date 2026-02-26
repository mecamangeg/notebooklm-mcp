import json
from collections import Counter

JSONL_PATH = r"C:\PROJECTS\robsky-ai-vertex\SUPERVISED FINE TUNING\sft_accounting.jsonl"

def get_stats():
    intents = []
    with open(JSONL_PATH, "r", encoding="utf-8") as f:
        for line in f:
            data = json.loads(line)
            instr = data["systemInstruction"]["parts"][0]["text"]
            
            # Map back to intent key
            if "computation workbenches" in instr:
                intents.append("COMPUTATION")
            elif "structured advisories" in instr:
                intents.append("RESEARCH")
            elif "comparative matrices" in instr:
                intents.append("COMPARATIVE")
            elif "procedural guides" in instr:
                intents.append("INSTRUCTIONAL")
            elif "compliance checklists" in instr:
                intents.append("COMPLIANCE")
            elif "analytical reports" in instr:
                intents.append("ANALYTICAL")
            elif "tutorial materials" in instr:
                intents.append("PEDAGOGICAL")
            else:
                intents.append("UNKNOWN")
    
    counts = Counter(intents)
    print("Intent Distribution (from JSONL):")
    for intent, count in counts.items():
        print(f"- {intent}: {count}")
    print(f"Total: {len(intents)}")

if __name__ == "__main__":
    get_stats()
