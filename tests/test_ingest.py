"""Unit tests for ingest helpers — chunking, merging, file reading."""

from pathlib import Path

import pytest

from extractor.ingest import chunk_text, merge_extractions, read_document


# ---------- chunk_text ----------

def test_short_text_returns_single_chunk():
    text = "short note about a patient"
    assert chunk_text(text, max_chars=6000) == [text]


def test_long_text_splits_with_overlap():
    text = "A" * 12000
    chunks = chunk_text(text, max_chars=5000, overlap_chars=500)
    assert len(chunks) >= 3
    for chunk in chunks:
        assert len(chunk) <= 5000
    # Adjacent chunks should overlap by `overlap_chars`.
    assert chunks[0][-500:] == chunks[1][:500]


def test_chunk_text_strips_whitespace():
    assert chunk_text("   hello   ") == ["hello"]


# ---------- merge_extractions ----------

def test_merge_takes_first_nonnull_for_scalars():
    a = {"patient": {"name": None, "mrn": "1", "dob": None, "sex": None},
         "encounter": {"admit_date": None, "discharge_date": None},
         "diagnoses": [], "medications": []}
    b = {"patient": {"name": "Alice", "mrn": "2", "dob": "1990-01-01", "sex": "F"},
         "encounter": {"admit_date": "2026-01-01", "discharge_date": None},
         "diagnoses": [], "medications": []}
    merged = merge_extractions([a, b])
    assert merged["patient"]["name"] == "Alice"
    assert merged["patient"]["mrn"] == "1"          # earlier non-null wins
    assert merged["patient"]["dob"] == "1990-01-01"
    assert merged["encounter"]["admit_date"] == "2026-01-01"


def test_merge_unions_diagnoses_case_insensitive():
    a = {"patient": {}, "encounter": {}, "diagnoses": ["Asthma"], "medications": []}
    b = {"patient": {}, "encounter": {}, "diagnoses": ["asthma", "COPD"], "medications": []}
    merged = merge_extractions([a, b])
    assert merged["diagnoses"] == ["Asthma", "COPD"]


def test_merge_dedupes_meds_by_name():
    med1 = {"name": "Lisinopril", "dose": "10 mg", "route": "PO", "frequency": "daily"}
    med2 = {"name": "lisinopril", "dose": "20 mg", "route": "PO", "frequency": "daily"}
    a = {"patient": {}, "encounter": {}, "diagnoses": [], "medications": [med1]}
    b = {"patient": {}, "encounter": {}, "diagnoses": [], "medications": [med2]}
    merged = merge_extractions([a, b])
    assert len(merged["medications"]) == 1
    assert merged["medications"][0]["dose"] == "10 mg"  # first wins


def test_merge_empty_list():
    assert merge_extractions([]) == {}


# ---------- read_document ----------

def test_read_document_reads_txt(tmp_path: Path):
    p = tmp_path / "note.txt"
    p.write_text("hello world\nline two")
    assert read_document(p) == "hello world\nline two"


def test_read_document_rejects_unsupported(tmp_path: Path):
    p = tmp_path / "image.png"
    p.write_bytes(b"not really an image")
    with pytest.raises(ValueError):
        read_document(p)
