"""Read clinical notes from .txt or .pdf, and chunk long ones.

Why chunking?  Even though Llama 3.2 has a 128K context, we usually load it
at n_ctx=2048 for speed. If a note is longer than the budget, we split it
into overlapping chunks, extract from each, then merge.

For Phase 5 we keep merging simple:
- Patient/encounter/diagnoses → take the first non-empty result.
- Medications → union (de-duped by lowercase name).
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable


def read_document(path: str | Path) -> str:
    """Read a .txt or .pdf file and return its text content."""
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".pdf":
        return _read_pdf(p)
    if suffix in {".txt", ".md", ""}:
        return p.read_text(encoding="utf-8", errors="replace")
    raise ValueError(f"Unsupported file type: {suffix} ({p})")


def _read_pdf(path: Path) -> str:
    # Imported lazily so projects that don't use PDF don't pay the import cost.
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages).strip()


def chunk_text(text: str, max_chars: int = 6000, overlap_chars: int = 400) -> list[str]:
    """Split `text` into overlapping chunks no longer than `max_chars`.

    Why overlap? A field (e.g. a medication line) might straddle a chunk
    boundary. Overlap lets each chunk see a bit of the neighbour's content.
    """
    text = text.strip()
    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap_chars
    return chunks


def merge_extractions(extractions: Iterable[dict]) -> dict:
    """Merge per-chunk extractions into one.

    Strategy:
    - For scalar fields (patient.*, encounter.*) use first non-null value.
    - For diagnoses, take the union (preserving order).
    - For medications, de-dupe by lowercased name (first wins).
    """
    extractions = list(extractions)
    if not extractions:
        return {}

    merged: dict = {
        "patient": {"name": None, "mrn": None, "dob": None, "sex": None},
        "encounter": {"admit_date": None, "discharge_date": None},
        "diagnoses": [],
        "medications": [],
    }
    seen_dx: set[str] = set()
    seen_meds: set[str] = set()

    for e in extractions:
        for k in merged["patient"]:
            if merged["patient"][k] in (None, "") and (e.get("patient") or {}).get(k):
                merged["patient"][k] = e["patient"][k]
        for k in merged["encounter"]:
            if merged["encounter"][k] in (None, "") and (e.get("encounter") or {}).get(k):
                merged["encounter"][k] = e["encounter"][k]
        for dx in e.get("diagnoses") or []:
            key = dx.strip().lower()
            if key and key not in seen_dx:
                seen_dx.add(key)
                merged["diagnoses"].append(dx)
        for med in e.get("medications") or []:
            name = (med.get("name") or "").strip().lower()
            if name and name not in seen_meds:
                seen_meds.add(name)
                merged["medications"].append(med)

    return merged
