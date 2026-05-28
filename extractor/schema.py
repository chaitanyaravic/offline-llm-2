"""JSON schema for clinical extraction output.

llama-cpp-python accepts a JSON Schema via `response_format` and uses a
*grammar-constrained* sampler. The model is mathematically prevented from
emitting any token sequence that would violate the schema — so the output
is guaranteed parseable.

This schema is intentionally small for Phase 3. We add vitals, labs, and
ICD codes in later phases.
"""

EXTRACTION_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "patient": {
            "type": "object",
            "properties": {
                "name": {"type": ["string", "null"]},
                "mrn": {"type": ["string", "null"]},
                "dob": {"type": ["string", "null"]},
                "sex": {"type": ["string", "null"]},
            },
            "required": ["name", "mrn", "dob", "sex"],
        },
        "encounter": {
            "type": "object",
            "properties": {
                "admit_date": {"type": ["string", "null"]},
                "discharge_date": {"type": ["string", "null"]},
            },
            "required": ["admit_date", "discharge_date"],
        },
        "diagnoses": {
            "type": "array",
            "items": {"type": "string"},
        },
        "medications": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "dose": {"type": ["string", "null"]},
                    "route": {"type": ["string", "null"]},
                    "frequency": {"type": ["string", "null"]},
                },
                "required": ["name", "dose", "route", "frequency"],
            },
        },
    },
    "required": ["patient", "encounter", "diagnoses", "medications"],
}
