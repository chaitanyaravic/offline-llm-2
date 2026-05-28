"""Phase 2 demo: extract fields from a clinical note using few-shot prompting.

Usage:
    python scripts/phase2_extract.py samples/note1.txt
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from extractor.extract import extract_text
from extractor.model import load_model


def main() -> None:
    note_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("samples/note1.txt")
    note = note_path.read_text()

    print(f"Loading model and extracting from {note_path}...\n")
    llm = load_model()
    output = extract_text(llm, note)

    print("=" * 72)
    print(output)
    print("=" * 72)


if __name__ == "__main__":
    main()
