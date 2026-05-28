"""One-function entry point: file → cleaned, structured extraction.

`extract_from_file(llm, path)` runs the full pipeline: read → chunk →
extract per chunk → merge → clean.
"""

from pathlib import Path

from llama_cpp import Llama

from extractor.cleanup import clean_extraction
from extractor.extract import extract_json
from extractor.ingest import chunk_text, merge_extractions, read_document


def extract_from_file(llm: Llama, path: str | Path) -> dict:
    text = read_document(path)
    chunks = chunk_text(text)
    per_chunk = [extract_json(llm, c) for c in chunks]
    merged = merge_extractions(per_chunk)
    return clean_extraction(merged)
