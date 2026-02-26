import os, re

digest_dir = r'C:\PROJECTS\supreme-court-scraper\Renamed-with-Native-Syllabi_RAW_HTML-1996-2022'
results = []

for root, dirs, files in os.walk(digest_dir):
    for f in files:
        if f.endswith(('.md', '.html', '.htm', '.txt')):
            path = os.path.join(root, f)
            try:
                content = open(path, 'r', encoding='utf-8', errors='ignore').read().lower()
                has_concurring = 'concurring' in content
                has_separate = 'separate opinion' in content or 'separate concurring' in content or 'separate dissenting' in content
                has_dissenting = 'dissenting' in content
                if has_concurring and has_separate and has_dissenting:
                    results.append(f)
            except:
                pass

print(f"Found {len(results)} files with concurring + separate + dissenting opinions.")

with open('opinions_results.txt', 'w', encoding='utf-8') as out:
    out.write(f"Found {len(results)} files with concurring + separate + dissenting opinions:\n\n")
    for i, r in enumerate(results, 1):
        out.write(f"{i}. {r}\n")

print("Results saved to opinions_results.txt")
