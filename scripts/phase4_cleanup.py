"""Phase 4 demo: extract JSON, then apply cleanup. Show before/after.

Usage:
    python scripts/phase4_cleanup.py samples/note1.txt
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from extractor.cleanup import clean_extraction
from extractor.extract import extract_json
from extractor.model import load_model


def main() -> None:
    note_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("samples/note1.txt")
    note = note_path.read_text()

    print(f"Extracting from {note_path}...")
    llm = load_model()
    raw = extract_json(llm, note)
    cleaned = clean_extraction(raw)

    print("\n----- RAW (from LLM) -----")
    print(json.dumps(raw, indent=2))
    print("\n----- CLEANED -----")
    print(json.dumps(cleaned, indent=2))


if __name__ == "__main__":
    main()
