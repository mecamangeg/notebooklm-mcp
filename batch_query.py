import os
import json
import time
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from notebooklm_mcp.server import get_client

# Mapping from output.txt step 963
sources = [
    {"source_id": "08aade81-16e3-47ae-b25e-e0ba5c091dbb", "path": r"C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown\2023\02_Feb\Navarro v. Cornejo, 935 Phil. 776 (G.R. No. 263329. February 8, 2023).md"},
    {"source_id": "2be5b28b-b265-4aa1-89a8-4dec3e325415", "path": r"C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown\2023\04_Apr\Palacio v. People, 940 Phil. 333 (G.R. No. 262473. April 12, 2023).md"},
    {"source_id": "36a8ea19-0945-42c5-8405-e0c48055e315", "path": r"C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown\2023\10_Oct\People v. Rodriguez, 948 Phil. 67 (G.R. No. 263603. October 9, 2023).md"},
    {"source_id": "bb37fa90-2e41-43b8-a56c-444c717e2a71", "path": r"C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown\2023\10_Oct\People v. Unknown, 948 Phil. 685 (G.R. No. 258054. October 25, 2023).md"},
    {"source_id": "8956e969-7252-4936-b44d-9fa203d2a6d1", "path": r"C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown\2023\11_Nov\People v. Unknown, 949 Phil. 562 (G.R. No. 263553. November 20, 2023).md"},
    {"source_id": "e69293dc-cf3a-4cec-960b-70058e4cf543", "path": r"C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown\2023\11_Nov\People v. Xxx, 949 Phil. 271 (G.R. No. 262520. November 13, 2023).md"},
    {"source_id": "964ed9da-0db3-4f63-be25-be69a5cbdde0", "path": r"C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown\2023\11_Nov\People v. Xxx, 949 Phil. 594 (G.R. No. 262812. November 22, 2023).md"},
    {"source_id": "0b955327-16d6-4844-adfe-db1869621a71", "path": r"C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown\2023\11_Nov\Unknown v. Unknown, 949 Phil. 236 (G.R. No. 261422. November 13, 2023).md"},
    {"source_id": "ea9894ae-d9e6-42e4-9fe8-93c762c6b3cd", "path": r"C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown\2024\01_Jan\People v. Saldivar, 950 Phil. 506 (G.R. No. 266754. January 29, 2024).md"},
    {"source_id": "0e3ff27b-527a-495f-a647-174da2d2ca56", "path": r"C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown\2024\04_Apr\People v. Almero, 953 Phil. 93 (G.R. No. 269401. April 11, 2024).md"},
    {"source_id": "23dd3c57-37cf-4308-bd14-abc6b14acea2", "path": r"C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown\2024\04_Apr\People v. Arraz, 952 Phil. 685 (G.R. No. 262362. April 8, 2024).md"},
    {"source_id": "7261f16c-50a2-4407-a597-e893ddbe836d", "path": r"C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown\2024\05_May\People v. 'Freda,', 954 Phil. 834 (G.R. No. 267609. May 27, 2024).md"},
    {"source_id": "035bd2e9-d971-47d8-a48b-c98b15bf61b1", "path": r"C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown\2024\05_May\People v. 'Sopingsofia', 954 Phil. 819 (G.R. No. 264039. May 27, 2024).md"},
    {"source_id": "67e0e149-cbe8-456d-9d28-75317fcfeae3", "path": r"C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown\2024\05_May\People v. Cañas, 954 Phil. 239 (G.R. No. 267360. May 15, 2024).md"},
    {"source_id": "d222915d-7dcd-4653-88ab-43cbbfccda4f", "path": r"C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown\2024\05_May\People v. Jjj, 954 Phil. 337 (G.R. No. 262749. May 20, 2024).md"},
    {"source_id": "c822f3f6-f400-4cd8-a37b-27bb05d1ea6d", "path": r"C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown\2024\05_May\People v. Tuazon, 954 Phil. 851 (G.R. No. 267946. May 27, 2024).md"},
    {"source_id": "296e257b-3ab7-491d-a3df-ec6ade82587e", "path": r"C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown\2024\06_Jun\People v. Zzz, 955 Phil. 733 (G.R. No. 266706. June 26, 2024).md"},
    {"source_id": "14059a3b-23de-4ecb-a09a-4a4a944c9bc1", "path": r"C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown\2024\08_Aug\People v. Batomalaque, 957 Phil. 512 (G.R. No. 266608. August 7, 2024).md"},
    {"source_id": "45f60a9f-2fba-46d1-b166-ca9fd2e7a8b5", "path": r"C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown\2024\10_Oct\People v. Bautista, 959 Phil. 1080 (G.R. No. 270003. October 30, 2024).md"},
    {"source_id": "0a0317d6-b955-463c-acb7-3962e5d7ff26", "path": r"C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown\2024\10_Oct\People v. Unknown, 959 Phil. 833 (G.R. No. 270317. October 23, 2024).md"},
    {"source_id": "f894adcf-f3d1-4f12-83c6-45a0c702fc83", "path": r"C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown\2024\10_Oct\People v. Xxx, 959 Phil. 396 (G.R. No. 273190. October 16, 2024).md"},
    {"source_id": "5b6966a3-4123-4ae0-975a-7e2fc427411f", "path": r"C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown\2024\11_Nov\People v. Riddel', 961 Phil. 362 (G.R. No. 270174. November 26, 2024).md"},
    {"source_id": "b72519e5-daf3-4ee4-8d9d-cef2d44662fe", "path": r"C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown\2024\11_Nov\People v. Unknown, 960 Phil. 597 (G.R. No. 270870. November 11, 2024).md"},
    {"source_id": "1032cb8e-c0ec-4ff3-b33a-4e33f3c5fc5c", "path": r"C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown\2025\01_Jan\People v. Echanes (G.R. No. 272974. January 20, 2025).md"},
    {"source_id": "169ca79a-0fb4-4a3a-90ff-7f0f814df0e9", "path": r"C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown\2025\01_Jan\People v. Unknown (G.R. No. 270897. January 14, 2025).md"},
    {"source_id": "a9670a72-8090-4c63-99d7-9adc4f727c4c", "path": r"C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown\2025\03_Mar\People v. Unknown (G.R. No. 234512. March 5, 2025).md"},
    {"source_id": "03953d2b-bfc1-4f8b-a96c-949eab8dbda5", "path": r"C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown\2025\04_Apr\People v. Bolagot (G.R. No. 267833. April 7, 2025).md"},
    {"source_id": "b578a001-a969-452f-987e-37192119520b", "path": r"C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown\2025\04_Apr\People v. Xxx (G.R. No. 252606. April 2, 2025).md"},
    {"source_id": "d2a9cabe-c23b-4c5c-b68c-404f547eb567", "path": r"C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown\2025\08_Aug\People v. Jakobsen (G.R. No. 277260. August 18, 2025).md"},
    {"source_id": "224d6a61-2e9d-4632-aae6-15e22e55cba9", "path": r"C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown\2025\08_Aug\People v. Unknown (G.R. No. 276383. August 6, 2025).md"},
    {"source_id": "4131479b-1bfc-4b71-b11c-60f14ab9bc83", "path": r"C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown\2025\08_Aug\People v. Unknown (G.R. No. 276422. August 11, 2025).md"},
    {"source_id": "8e993ccc-71d8-4e5b-b18a-774462a90442", "path": r"C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown\2025\08_Aug\People v. Zzz (G.R. No. 264132. August 13, 2025).md"}
]

notebook_id = "9bdf69ab-1a33-443f-84b0-b0d6f960cbcc"
base_input_dir = r"C:\PROJECTS\supreme-court-scraper\MARKDOWN\markdown"
output_dir = r"C:\PROJECTS\notebooklm-mcp\with-generated-SYLLABI"
query = "Provide a comprehensive SCRA-style syllabus (headnotes) for this case, extracting all legal doctrines, principles, and holdings. Determine the appropriate Topic and Subtopic, write a 1-sentence verbatim Synopsis directly from the text, and write an Explanation for each."

def process_all():
    client = get_client()
    for s in sources:
        rel_path = os.path.relpath(s["path"], base_input_dir)
        folder = os.path.dirname(rel_path)
        name = os.path.basename(rel_path)
        generated_name = name.replace(".md", "-generated-syllabi.md")
        target_folder = os.path.join(output_dir, folder)
        os.makedirs(target_folder, exist_ok=True)
        target_file = os.path.join(target_folder, generated_name)
        
        if os.path.exists(target_file):
            print(f"Skipping {target_file} (already exists)")
            continue
            
        print(f"\nQuerying NotebookLM for {name}...")
        try:
            result = client.query(
                notebook_id,
                query_text=query,
                source_ids=[s["source_id"]],
            )
            val = result.get("answer", "")
            if val:
                with open(target_file, "w", encoding="utf-8") as f:
                    f.write(val)
                print(f"✅ Saved to {target_file}")
            else:
                print(f"❌ Empty answer for {name}.")
        except Exception as e:
            print(f"❌ Error for {name}: {e}")
            
        time.sleep(2)

if __name__ == "__main__":
    process_all()
