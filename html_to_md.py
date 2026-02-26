#!/usr/bin/env python3
"""Convert 5 HTML case files to Markdown using the same extraction logic
as sc_scraper_v4-optimized.py (BeautifulSoup text extraction + YAML frontmatter)."""

import os, re, hashlib
from pathlib import Path
from bs4 import BeautifulSoup

SRC_DIR = Path(r'C:\PROJECTS\notebooklm-mcp\cases with all different opinions with native syllabi\for-extraction')
OUT_DIR = SRC_DIR  # output .md alongside .html

def extract_text_from_html(html_content: str) -> str:
    """Extract clean text from SC E-Library HTML (friendly page format)."""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Try #left > div selector first (standard E-Library layout)
    content_div = soup.select_one('#left > div')
    if not content_div:
        # Fallback: try body
        content_div = soup.find('body')
    if not content_div:
        content_div = soup
    
    # Get text preserving paragraph breaks
    text = content_div.get_text(separator='\n')
    
    # Clean up
    # Remove E-Library footer
    footer_pattern = r'\n*Source:\s*Supreme Court E-Library[\s\S]*?E-LibCMS\)?\.\s*$'
    text = re.sub(footer_pattern, '', text, flags=re.IGNORECASE)
    fallback_patterns = [
        r'\n*Source:\s*Supreme Court E-Library[^\n]*\n?',
        r'\n*This page was dynamically generated[^\n]*\n?',
        r'\n*by the E-Library Content Management System[^\n]*\n?',
    ]
    for pattern in fallback_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    
    # Normalize whitespace (collapse multiple blank lines to max 2)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def extract_metadata(text: str, filename: str) -> dict:
    """Extract basic metadata from text."""
    meta = {
        'docket_number': '',
        'title': '',
        'decision_date': '',
        'ponente': '',
        'division': '',
    }
    
    # Docket number from filename
    gr_match = re.search(r'((?:G\.R\.|A\.M\.|A\.C\.)\s*No[s]?\.\s*[\w\-\s&]+)', filename)
    if gr_match:
        meta['docket_number'] = gr_match.group(1).strip().rstrip(',')
    
    # Date from filename
    date_match = re.search(r'((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4})', filename)
    if date_match:
        meta['decision_date'] = date_match.group(1)
    
    # Title: text before "DECISION" or "RESOLUTION"  
    title_match = re.search(r'^(.*?)\n.*?(?:D\s*E\s*C\s*I\s*S\s*I\s*O\s*N|DECISION|RESOLUTION)', text[:3000], re.DOTALL)
    if title_match:
        candidate = title_match.group(1).strip()
        # Look for VS. pattern
        vs_match = re.search(r'([A-Z][A-Z\s\.,\-\'\"]+(?:VS?\.?|VERSUS)[A-Z\s\.,\-\'\"]+)', candidate)
        if vs_match:
            meta['title'] = re.sub(r'\s+', ' ', vs_match.group(1)).strip()
    
    # Ponente
    ponente_match = re.search(r'([A-Z][A-Z\s]+),\s*(?:J\.|C\.?J\.)', text[:3000])
    if ponente_match:
        meta['ponente'] = ponente_match.group(1).strip().title()
    
    return meta

def generate_markdown(text: str, meta: dict) -> str:
    """Generate markdown with YAML frontmatter."""
    lines = []
    lines.append('---')
    for key, val in meta.items():
        safe_val = str(val).replace('"', "'").replace('\n', ' ')
        lines.append(f'{key}: "{safe_val}"')
    lines.append('---')
    lines.append('')
    lines.append(text)
    return '\n'.join(lines)

# Process all HTML files in the directory
html_files = list(SRC_DIR.glob('*.html'))
print(f"Found {len(html_files)} HTML files in {SRC_DIR}")

for html_file in sorted(html_files):
    print(f"\nProcessing: {html_file.name}")
    
    html_content = html_file.read_text(encoding='utf-8', errors='ignore')
    text = extract_text_from_html(html_content)
    meta = extract_metadata(text, html_file.name)
    
    md_content = generate_markdown(text, meta)
    
    md_file = html_file.with_suffix('.md')
    md_file.write_text(md_content, encoding='utf-8')
    
    word_count = len(text.split())
    print(f"  Docket: {meta['docket_number']}")
    print(f"  Date:   {meta['decision_date']}")
    print(f"  Words:  {word_count}")
    print(f"  Output: {md_file.name}")

print(f"\nDone! Converted {len(html_files)} files.")
