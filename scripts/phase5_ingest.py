"""Phase 5 demo: ingest, chunk, extract per chunk, merge, clean.

Usage:
    python scripts/phase5_ingest.py samples/note1.txt
    python scripts/phase5_ingest.py path/to/some.pdf
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from extractor.cleanup import clean_extraction
from extractor.extract import extract_json
from extractor.ingest import chunk_text, merge_extractions, read_document
from extractor.model import load_model


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/phase5_ingest.py <path-to-.txt-or-.pdf>")
        sys.exit(1)
    path = Path(sys.argv[1])

    print(f"Reading {path}...")
    text = read_document(path)
    chunks = chunk_text(text)
    print(f"{len(text)} characters → {len(chunks)} chunk(s)")

    llm = load_model()
    extractions = []
    for i, chunk in enumerate(chunks, 1):
        print(f"  Extracting chunk {i}/{len(chunks)}...")
        extractions.append(extract_json(llm, chunk))

    merged = merge_extractions(extractions)
    cleaned = clean_extraction(merged)

    print("\n----- FINAL -----")
    print(json.dumps(cleaned, indent=2))


if __name__ == "__main__":
    main()
