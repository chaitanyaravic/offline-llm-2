"""Phase 3 demo: JSON-schema constrained extraction.

Usage:
    python scripts/phase3_extract_json.py samples/note1.txt
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from extractor.extract import extract_json
from extractor.model import load_model


def main() -> None:
    note_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("samples/note1.txt")
    note = note_path.read_text()

    print(f"Loading model and extracting JSON from {note_path}...\n")
    llm = load_model()
    data = extract_json(llm, note)

    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
