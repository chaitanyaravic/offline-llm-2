"""Unit tests for extractor.cleanup — pure rule code, no LLM needed."""

import pytest

from extractor.cleanup import (
    clean_extraction,
    merge_modifier_diagnoses,
    normalize_date,
    normalize_dose,
    normalize_frequency,
    normalize_route,
)


# ---------- dates ----------

@pytest.mark.parametrize("raw, expected", [
    ("03/15/1957", "1957-03-15"),
    ("1957-03-15", "1957-03-15"),
    ("June 22, 1980", "1980-06-22"),
    ("Jun 22, 1980", "1980-06-22"),
    ("22 June 1980", "1980-06-22"),
    ("2026/04/10", "2026-04-10"),
    ("9-30-1992", "1992-09-30"),
    ("09-30-1992", "1992-09-30"),
    ("", None),
    (None, None),
    ("not stated", None),
])
def test_normalize_date(raw, expected):
    assert normalize_date(raw) == expected


def test_normalize_date_unparseable_passes_through():
    assert normalize_date("sometime last week") == "sometime last week"


# ---------- routes ----------

@pytest.mark.parametrize("raw, expected", [
    ("PO", "PO"),
    ("po", "PO"),
    ("by mouth", "PO"),
    ("mouth", "PO"),
    ("Oral", "PO"),
    ("IV", "IV"),
    ("intravenous", "IV"),
    ("subq", "SC"),
    ("Inhaled", "INH"),
    ("nebulized", "INH"),
    ("", None),
    (None, None),
])
def test_normalize_route(raw, expected):
    assert normalize_route(raw) == expected


# ---------- frequencies ----------

@pytest.mark.parametrize("raw, expected", [
    ("BID", "BID"),
    ("twice daily", "BID"),
    ("every 12 hours", "BID"),
    ("daily", "daily"),
    ("once daily", "daily"),
    ("as needed", "PRN"),
    ("at bedtime", "QHS"),
    ("bedtime", "QHS"),
    ("every 4 hours", "q4h"),
    ("", None),
    (None, None),
])
def test_normalize_frequency(raw, expected):
    assert normalize_frequency(raw) == expected


# ---------- dose ----------

@pytest.mark.parametrize("raw, expected", [
    ("40 mg PO daily for 5 days", "40 mg"),
    ("10 mg PO daily", "10 mg"),
    ("500 mg PO daily for 5 days", "500 mg"),
    ("1000mg", "1000 mg"),
    ("90 mcg, 2 puffs every 4 hours as needed", "90 mcg, 2 puffs"),
    ("", None),
    (None, None),
])
def test_normalize_dose(raw, expected):
    assert normalize_dose(raw) == expected


# ---------- diagnosis merging ----------

def test_merge_modifier_diagnoses_merges():
    assert merge_modifier_diagnoses(
        ["Hypertension", "well-controlled", "Type 2 diabetes"]
    ) == ["Hypertension, well-controlled", "Type 2 diabetes"]


def test_merge_modifier_diagnoses_leaves_real_diagnoses_alone():
    dx = ["Type 2 diabetes mellitus", "Hyperlipidemia", "Obesity"]
    assert merge_modifier_diagnoses(dx) == dx


def test_merge_handles_empty_and_whitespace():
    assert merge_modifier_diagnoses(["", "  ", "Asthma"]) == ["Asthma"]


# ---------- top-level idempotency ----------

def test_clean_extraction_is_idempotent():
    raw = {
        "patient": {"name": "X", "mrn": "1", "dob": "03/15/1957", "sex": "M"},
        "encounter": {"admit_date": "2026-04-10", "discharge_date": None},
        "diagnoses": ["Hypertension", "well-controlled"],
        "medications": [
            {"name": "Lisinopril", "dose": "10 mg PO daily",
             "route": "by mouth", "frequency": "once daily"},
        ],
    }
    once = clean_extraction(raw)
    twice = clean_extraction(once)
    assert once == twice


def test_clean_extraction_does_not_mutate_input():
    raw = {
        "patient": {"name": "X", "mrn": "1", "dob": "03/15/1957", "sex": "M"},
        "encounter": {"admit_date": None, "discharge_date": None},
        "diagnoses": ["Hypertension", "well-controlled"],
        "medications": [],
    }
    snapshot = {"dob": raw["patient"]["dob"], "diagnoses": list(raw["diagnoses"])}
    clean_extraction(raw)
    assert raw["patient"]["dob"] == snapshot["dob"]
    assert raw["diagnoses"] == snapshot["diagnoses"]
