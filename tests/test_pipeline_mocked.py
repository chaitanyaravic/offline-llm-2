"""Tests for the full pipeline using a MOCKED llama model.

We never load the real model here — that would be slow and flaky. Instead we
stub `llm.create_chat_completion` to return canned JSON, exercising the
ingest → extract → merge → clean glue end to end.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from extractor.pipeline import extract_from_file


@pytest.fixture
def fake_llm():
    """A Llama-shaped mock that returns canned JSON for create_chat_completion."""
    llm = MagicMock()
    canned = {
        "patient": {"name": "John Smith", "mrn": "12345678",
                    "dob": "03/15/1957", "sex": "M"},
        "encounter": {"admit_date": "2026-04-10", "discharge_date": "2026-04-15"},
        "diagnoses": ["Hypertension", "well-controlled"],
        "medications": [
            {"name": "Lisinopril", "dose": "10 mg PO daily",
             "route": "by mouth", "frequency": "once daily"},
        ],
    }
    llm.create_chat_completion.return_value = {
        "choices": [{"message": {"content": json.dumps(canned)}}],
    }
    return llm


def test_pipeline_extracts_and_cleans(fake_llm, tmp_path: Path):
    note = tmp_path / "note.txt"
    note.write_text("Patient: John Smith\nMRN: 12345678\nDOB: 03/15/1957\nSex: M")

    result = extract_from_file(fake_llm, note)

    # Cleanup ran: ISO date, merged diagnosis, normalized route/freq, stripped dose.
    assert result["patient"]["dob"] == "1957-03-15"
    assert result["diagnoses"] == ["Hypertension, well-controlled"]
    assert result["medications"][0]["dose"] == "10 mg"
    assert result["medications"][0]["route"] == "PO"
    assert result["medications"][0]["frequency"] == "daily"


def test_pipeline_calls_model_once_per_chunk(fake_llm, tmp_path: Path):
    note = tmp_path / "note.txt"
    note.write_text("X" * 13000)  # forces multi-chunk

    extract_from_file(fake_llm, note)

    assert fake_llm.create_chat_completion.call_count >= 2
