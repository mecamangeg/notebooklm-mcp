"""Standalone unit tests for corpus profile abstraction.

Copies the minimal code under test directly (no fastmcp import needed).
"""

# ── Code under test (copied from server.py) ──────────────────────

CORPUS_PROFILES = {
    "elibrary": {
        "label": "SC e-Library",
        "short_title_field": "abridged_title",
        "extra_fields": [
            "doc_id", "phil_citation", "scra_citation",
            "word_count", "source_url", "citation_format",
        ],
    },
    "escra": {
        "label": "e-SCRA",
        "short_title_field": "short_title",
        "extra_fields": [
            "case_nature", "disposition",
            "source_type", "source_file",
        ],
    },
    "generic": {
        "label": "Generic",
        "short_title_field": "short_title",
        "extra_fields": [],
    },
}


def _detect_corpus(frontmatter: dict) -> str:
    """Auto-detect corpus type from frontmatter fields."""
    if frontmatter.get("source_type") == "SCRA":
        return "escra"
    if "doc_id" in frontmatter:
        return "elibrary"
    return "generic"


# ── Tests ─────────────────────────────────────────────────────────

def test_detect_escra():
    fm = {"title": "X", "short_title": "Y", "source_type": "SCRA", "source_file": "042_case.html"}
    result = _detect_corpus(fm)
    assert result == "escra", f"Expected escra, got {result}"
    print("  [PASS] e-SCRA detection")


def test_detect_elibrary():
    fm = {"doc_id": "55438", "docket_number": "G.R. No. 188056", "abridged_title": "X"}
    result = _detect_corpus(fm)
    assert result == "elibrary", f"Expected elibrary, got {result}"
    print("  [PASS] e-Library detection")


def test_detect_generic():
    fm = {"title": "Some document"}
    result = _detect_corpus(fm)
    assert result == "generic", f"Expected generic, got {result}"
    print("  [PASS] Generic fallback")


def test_detect_empty():
    result = _detect_corpus({})
    assert result == "generic", f"Expected generic, got {result}"
    print("  [PASS] Empty dict fallback")


def test_escra_priority():
    """e-SCRA should take priority when both markers present."""
    fm = {"doc_id": "123", "source_type": "SCRA"}
    result = _detect_corpus(fm)
    assert result == "escra", f"Expected escra, got {result}"
    print("  [PASS] e-SCRA priority over doc_id")


def test_profile_field_mapping():
    assert CORPUS_PROFILES["escra"]["short_title_field"] == "short_title"
    assert CORPUS_PROFILES["elibrary"]["short_title_field"] == "abridged_title"
    assert CORPUS_PROFILES["generic"]["short_title_field"] == "short_title"
    print("  [PASS] Profile short_title_field mapping")


def test_escra_frontmatter_update():
    """Simulate what _process_notebook_chunk does for e-SCRA."""
    fm = {"title": "FULL TITLE", "short_title": "Old Title", "source_type": "SCRA"}
    corpus = _detect_corpus(fm)
    profile = CORPUS_PROFILES[corpus]
    fm[profile["short_title_field"]] = "Corrected v. Title"
    assert fm["short_title"] == "Corrected v. Title"
    assert "abridged_title" not in fm
    print("  [PASS] e-SCRA frontmatter update (short_title)")


def test_elibrary_frontmatter_update():
    """Simulate what _process_notebook_chunk does for e-Library."""
    fm = {"title": "FULL TITLE", "abridged_title": "Old Title", "doc_id": "55438"}
    corpus = _detect_corpus(fm)
    profile = CORPUS_PROFILES[corpus]
    fm[profile["short_title_field"]] = "Corrected v. Title"
    assert fm["abridged_title"] == "Corrected v. Title"
    assert "short_title" not in fm
    print("  [PASS] e-Library frontmatter update (abridged_title)")


def test_real_escra_frontmatter():
    """Test with actual e-SCRA frontmatter from Volume_500."""
    fm = {
        "title": "FIDEL V. AMARILLO , JR . , petitioner, vs . THE PEOPLE OF THE PHILIPPINES",
        "short_title": "Amarillo, Jr. vs. People",
        "docket": "G.R. No. 153650",
        "date": "August 31, 2006",
        "ponente": "QUISUMBING",
        "case_nature": "PETITION for review on certiorari",
        "disposition": "Judgment and resolution affirmed, petition denied.",
        "source_type": "SCRA",
        "source_file": "042_case.html",
    }
    corpus = _detect_corpus(fm)
    assert corpus == "escra"
    profile = CORPUS_PROFILES[corpus]
    assert profile["short_title_field"] == "short_title"
    # Simulate short title correction
    fm[profile["short_title_field"]] = "Amarillo v. People"
    assert fm["short_title"] == "Amarillo v. People"
    print("  [PASS] Real e-SCRA frontmatter (Volume_500)")


def test_real_elibrary_frontmatter():
    """Test with actual SC e-Library frontmatter."""
    fm = {
        "doc_id": "55503",
        "docket_number": "G.R. No. 183896",
        "title": "SYED AZHAR ABBAS, PETITIONER, VS. GLORIA GOO ABBAS",
        "abridged_title": "Syed Azhar Abbas vs. Gloria Goo Abbas",
        "decision_date": "November 4, 2013",
        "ponente": "",
        "division": "THIRD DIVISION",
        "doc_type": "Decision",
        "phil_citation": "702 Phil. 578",
        "scra_citation": "",
        "word_count": "5121",
        "source_url": "https://elibrary.judiciary.gov.ph/thebookshelf/showdocs/1/55503",
        "citation_format": "G.R. No. 183896, November 4, 2013",
    }
    corpus = _detect_corpus(fm)
    assert corpus == "elibrary"
    profile = CORPUS_PROFILES[corpus]
    assert profile["short_title_field"] == "abridged_title"
    fm[profile["short_title_field"]] = "Abbas v. Abbas"
    assert fm["abridged_title"] == "Abbas v. Abbas"
    print("  [PASS] Real e-Library frontmatter (2013/01_Jan)")


if __name__ == "__main__":
    print("Running corpus profile unit tests...\n")
    test_detect_escra()
    test_detect_elibrary()
    test_detect_generic()
    test_detect_empty()
    test_escra_priority()
    test_profile_field_mapping()
    test_escra_frontmatter_update()
    test_elibrary_frontmatter_update()
    test_real_escra_frontmatter()
    test_real_elibrary_frontmatter()
    print("\nAll 10 tests passed!")
