"""Rule-based normalization of the extracted JSON.

Why rules and not the LLM?  Tiny, deterministic transformations (dates,
units, route codes) are dirt cheap with regex, reproducible, and don't
need network/compute. We reserve the LLM for the *unstructured* parts.

Conventions applied:
- Dates              → ISO 8601 (YYYY-MM-DD)
- Drug routes        → standard abbreviations (PO, IV, IM, SC, INH, PR, TOP)
- Frequencies        → canonical short forms (BID, TID, QID, daily, PRN, q4h …)
- Doses              → "<value> <unit>" with the trailing route/freq stripped
- Diagnoses          → trim trailing modifier fragments that aren't a diagnosis
"""

from __future__ import annotations

import copy
import re
from datetime import date, datetime
from typing import Any


# ---------- dates ----------

_DATE_PATTERNS = [
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%m/%d/%y",
    "%d/%m/%Y",
    "%m-%d-%Y",
    "%B %d, %Y",
    "%b %d, %Y",
    "%d %B %Y",
    "%Y/%m/%d",
]


def normalize_date(value: str | None) -> str | None:
    """Return YYYY-MM-DD, or None if the input is missing/unparseable."""
    if not value:
        return None
    value = value.strip()
    if not value or value.lower() in {"not stated", "none", "null", "unknown"}:
        return None
    for fmt in _DATE_PATTERNS:
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return value  # last resort: hand back the original string


# ---------- routes ----------

_ROUTE_MAP = {
    "po": "PO", "by mouth": "PO", "mouth": "PO", "oral": "PO", "orally": "PO",
    "iv": "IV", "intravenous": "IV", "intravenously": "IV",
    "im": "IM", "intramuscular": "IM",
    "sc": "SC", "subq": "SC", "subcutaneous": "SC", "sub-q": "SC",
    "inh": "INH", "inhaled": "INH", "inhalation": "INH", "nebulized": "INH",
    "top": "TOP", "topical": "TOP",
    "pr": "PR", "rectal": "PR", "per rectum": "PR",
    "sl": "SL", "sublingual": "SL",
}


def normalize_route(value: str | None) -> str | None:
    if not value:
        return None
    return _ROUTE_MAP.get(value.strip().lower(), value.strip())


# ---------- frequencies ----------

_FREQ_MAP = {
    "qd": "daily", "once daily": "daily", "daily": "daily", "every day": "daily",
    "bid": "BID", "twice daily": "BID", "twice a day": "BID", "every 12 hours": "BID",
    "tid": "TID", "three times daily": "TID", "three times a day": "TID",
    "qid": "QID", "four times daily": "QID", "four times a day": "QID",
    "prn": "PRN", "as needed": "PRN", "as needed (prn)": "PRN",
    "qhs": "QHS", "at bedtime": "QHS", "bedtime": "QHS", "nightly": "QHS",
    "q4h": "q4h", "every 4 hours": "q4h",
    "q6h": "q6h", "every 6 hours": "q6h",
    "q8h": "q8h", "every 8 hours": "q8h",
}


def normalize_frequency(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip().lower().rstrip(".")
    return _FREQ_MAP.get(cleaned, value.strip())


# ---------- dose: strip trailing route/frequency words ----------

_DOSE_TAIL = re.compile(
    r"\s+("
    r"po|iv|im|sc|inh|top|pr|sl|"
    r"by\s+mouth|orally|oral|"
    r"daily|bid|tid|qid|prn|qhs|"
    r"every\s+\d+\s+hours?|"
    r"q\d+h|"
    r"for\s+\d+\s+(days?|weeks?|months?)|"
    r"as\s+needed|at\s+bedtime"
    r").*$",
    flags=re.IGNORECASE,
)


def normalize_dose(value: str | None) -> str | None:
    """Trim trailing route/frequency/duration fragments from a dose string."""
    if not value:
        return None
    cleaned = _DOSE_TAIL.sub("", value.strip())
    # collapse "10mg" → "10 mg"
    cleaned = re.sub(r"(\d)(mg|mcg|g|ml|units?|iu|meq|puffs?)\b", r"\1 \2", cleaned, flags=re.I)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,;.")
    return cleaned or None


# ---------- diagnoses: drop trailing severity modifiers stuck into their own bullet ----------

_MODIFIER_ONLY = re.compile(
    r"^(well[- ]controlled|controlled|uncontrolled|stable|active|chronic|acute|mild|moderate|severe)$",
    re.IGNORECASE,
)


def merge_modifier_diagnoses(diagnoses: list[str]) -> list[str]:
    """If a diagnosis entry is JUST a modifier word, fold it into the previous entry."""
    merged: list[str] = []
    for dx in diagnoses:
        dx = dx.strip()
        if not dx:
            continue
        if merged and _MODIFIER_ONLY.match(dx):
            merged[-1] = f"{merged[-1]}, {dx.lower()}"
        else:
            merged.append(dx)
    return merged


# ---------- top-level ----------

def clean_extraction(data: dict[str, Any]) -> dict[str, Any]:
    """Apply all normalizations. Returns a new dict (input not mutated)."""
    out = copy.deepcopy(data)

    patient = out.get("patient") or {}
    patient["dob"] = normalize_date(patient.get("dob"))
    out["patient"] = patient

    enc = out.get("encounter") or {}
    enc["admit_date"] = normalize_date(enc.get("admit_date"))
    enc["discharge_date"] = normalize_date(enc.get("discharge_date"))
    out["encounter"] = enc

    out["diagnoses"] = merge_modifier_diagnoses(out.get("diagnoses") or [])

    cleaned_meds = []
    for med in out.get("medications") or []:
        cleaned_meds.append({
            "name": (med.get("name") or "").strip() or None,
            "dose": normalize_dose(med.get("dose")),
            "route": normalize_route(med.get("route")),
            "frequency": normalize_frequency(med.get("frequency")),
        })
    out["medications"] = cleaned_meds

    return out
