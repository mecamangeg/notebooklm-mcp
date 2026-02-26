"""Investigate the root cause of 43 persistent NotebookLM failures."""
import os
import sys

src = r"C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown"
out = r"C:\PROJECTS\notebooklm-mcp\with-generated-SYLLABI"

# Collect all failed files
failed = []
success_sample = []

for year in sorted(os.listdir(src)):
    yp = os.path.join(src, year)
    if not os.path.isdir(yp) or not year.isdigit():
        continue
    yn = int(year)
    for month in sorted(os.listdir(yp)):
        mp = os.path.join(yp, month)
        if not os.path.isdir(mp):
            continue
        mn = int(month[:2]) if month[:2].isdigit() else 0
        if yn < 2022 or (yn == 2022 and mn < 9):
            continue
        op = os.path.join(out, year, month)
        done_set = set()
        if os.path.isdir(op):
            for f in os.listdir(op):
                if f.endswith("-generated-syllabi.md"):
                    base = f[: -len("-generated-syllabi.md")]
                    done_set.add(base)
        for f in sorted(os.listdir(mp)):
            if not f.endswith(".md"):
                continue
            title = os.path.splitext(f)[0]
            safe = "".join(
                c if c.isalnum() or c in " .-_()," else "_" for c in title
            ).strip()
            filepath = os.path.join(mp, f)
            if safe not in done_set:
                failed.append(filepath)
            elif len(success_sample) < 20:
                success_sample.append(filepath)

# Sensitive content keywords
SENSITIVE_KW = [
    "rape", "sexual abuse", "sexual assault", "acts of lasciviousness",
    "statutory rape", "qualified trafficking", "child abuse",
    "incestuous", "molestation", "pedophil", "obscen",
    "xxx", "yyy", "zzz", "bbb", "aaa", "ccc",  # anonymization markers
]

CASE_TYPE_KW = [
    "murder", "homicide", "kidnapping", "carnapping",
    "drug", "dangerous drugs", "estafa", "robbery", "theft",
]


def analyze_file(filepath):
    """Analyze a case file for content characteristics."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    lower = content.lower()
    size = len(content)
    lines = content.count("\n") + 1

    # Check for sensitive keywords
    sensitive_flags = [kw for kw in SENSITIVE_KW if kw in lower]
    case_type_flags = [kw for kw in CASE_TYPE_KW if kw in lower]

    # Check if party name is anonymized
    has_anonymized_party = any(
        marker in lower
        for marker in ["xxx", "yyy", "zzz", "bbb", "aaa", "unknown v.", "v. unknown"]
    )

    # Check title pattern
    basename = os.path.basename(filepath)
    is_people_case = basename.lower().startswith("people v.")
    is_unknown = "unknown" in basename.lower() or "xxx" in basename.lower() or "zzz" in basename.lower()

    # Check for special characters in filename
    has_apostrophe_in_name = "'" in basename.split(",")[0] if "," in basename else False

    return {
        "file": basename,
        "size": size,
        "lines": lines,
        "sensitive_flags": sensitive_flags,
        "case_type_flags": case_type_flags,
        "has_anonymized_party": has_anonymized_party,
        "is_people_case": is_people_case,
        "is_unknown_party": is_unknown,
        "has_apostrophe": has_apostrophe_in_name,
    }


print("=" * 70)
print("  FAILURE ROOT CAUSE ANALYSIS")
print(f"  {len(failed)} failed files, {len(success_sample)} success samples")
print("=" * 70)

# Analyze all failed files
print("\n--- FAILED FILES ANALYSIS ---\n")
failed_stats = {"sensitive": 0, "people_case": 0, "anonymized": 0, "apostrophe": 0}
failed_analyses = []

for f in failed:
    analysis = analyze_file(f)
    failed_analyses.append(analysis)
    if analysis["sensitive_flags"]:
        failed_stats["sensitive"] += 1
    if analysis["is_people_case"]:
        failed_stats["people_case"] += 1
    if analysis["is_unknown_party"]:
        failed_stats["anonymized"] += 1
    if analysis["has_apostrophe"]:
        failed_stats["apostrophe"] += 1
    
    flags_str = ", ".join(analysis["sensitive_flags"][:5]) if analysis["sensitive_flags"] else "none"
    case_str = ", ".join(analysis["case_type_flags"][:3]) if analysis["case_type_flags"] else "none"
    print(
        f"  {analysis['file'][:70]:72s} "
        f"size={analysis['size']:>6,}  "
        f"sensitive=[{flags_str}]  "
        f"case=[{case_str}]"
    )

print(f"\n--- FAILED STATS ({len(failed)} files) ---")
print(f"  People v. cases:      {failed_stats['people_case']}/{len(failed)} ({100*failed_stats['people_case']/len(failed):.0f}%)")
print(f"  Has sensitive content: {failed_stats['sensitive']}/{len(failed)} ({100*failed_stats['sensitive']/len(failed):.0f}%)")
print(f"  Anonymized party:     {failed_stats['anonymized']}/{len(failed)} ({100*failed_stats['anonymized']/len(failed):.0f}%)")
print(f"  Has apostrophe:       {failed_stats['apostrophe']}/{len(failed)} ({100*failed_stats['apostrophe']/len(failed):.0f}%)")

# Now analyze success samples for comparison
print(f"\n--- SUCCESS SAMPLE ANALYSIS ({len(success_sample)} files) ---\n")
success_stats = {"sensitive": 0, "people_case": 0, "anonymized": 0, "apostrophe": 0}

for f in success_sample:
    analysis = analyze_file(f)
    if analysis["sensitive_flags"]:
        success_stats["sensitive"] += 1
    if analysis["is_people_case"]:
        success_stats["people_case"] += 1
    if analysis["is_unknown_party"]:
        success_stats["anonymized"] += 1
    if analysis["has_apostrophe"]:
        success_stats["apostrophe"] += 1

print(f"  People v. cases:      {success_stats['people_case']}/{len(success_sample)} ({100*success_stats['people_case']/max(len(success_sample),1):.0f}%)")
print(f"  Has sensitive content: {success_stats['sensitive']}/{len(success_sample)} ({100*success_stats['sensitive']/max(len(success_sample),1):.0f}%)")
print(f"  Anonymized party:     {success_stats['anonymized']}/{len(success_sample)} ({100*success_stats['anonymized']/max(len(success_sample),1):.0f}%)")

# File size comparison
failed_sizes = [a["size"] for a in failed_analyses]
print(f"\n--- FILE SIZE COMPARISON ---")
print(f"  Failed avg:  {sum(failed_sizes)/len(failed_sizes):,.0f} bytes")
print(f"  Failed min:  {min(failed_sizes):,} bytes")
print(f"  Failed max:  {max(failed_sizes):,} bytes")

# What percentage are sexual violence cases?
sexual_violence = sum(
    1 for a in failed_analyses
    if any(kw in a["sensitive_flags"] for kw in ["rape", "sexual abuse", "sexual assault", "statutory rape", "acts of lasciviousness", "molestation"])
)
print(f"\n--- KEY FINDING ---")
print(f"  Sexual violence cases: {sexual_violence}/{len(failed)} ({100*sexual_violence/len(failed):.0f}%)")
print(f"  Anonymized parties:    {failed_stats['anonymized']}/{len(failed)} ({100*failed_stats['anonymized']/len(failed):.0f}%)")

# Now test: try a manual API call on one small case to see the actual error
print(f"\n--- MANUAL API TEST ---")
print("  Testing one failed case to see the actual API response...")

# Pick the smallest failed case
smallest = min(failed, key=os.path.getsize)
print(f"  Test file: {os.path.basename(smallest)} ({os.path.getsize(smallest):,} bytes)")
