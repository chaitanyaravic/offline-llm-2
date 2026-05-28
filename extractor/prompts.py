"""Prompt templates for clinical data extraction.

Phase 2 uses *few-shot* prompting: we show the model one example of a note
plus the expected output, then ask it to do the same for a new note.

Each entry in `messages` is a turn in a chat:
    {"role": "system",    "content": "..."}  ← global instructions
    {"role": "user",      "content": "..."}  ← example note
    {"role": "assistant", "content": "..."}  ← example expected answer
    {"role": "user",      "content": "..."}  ← the real note we want extracted

The instruct-tuned Llama 3.2 model auto-applies its chat template when we use
`llm.create_chat_completion(messages=...)`.
"""

SYSTEM_PROMPT = """You are a clinical data extraction assistant.
Given a clinical note, extract the following fields. Be concise. If a field
is not stated, write "not stated". Use this exact format:

Patient name: <name>
MRN: <mrn>
DOB: <date>
Sex: <M/F/other>
Admit date: <date>
Discharge date: <date>
Diagnoses:
- <diagnosis 1>
- <diagnosis 2>
Medications:
- <name> | <dose> | <route> | <frequency>
- <name> | <dose> | <route> | <frequency>
"""


FEWSHOT_NOTE = """Patient: Jane Doe
MRN: 99887766
DOB: 1980-06-22  Sex: F
Diagnoses: 1. Type 2 diabetes mellitus 2. Hyperlipidemia
Medications: Metformin 1000mg PO BID; Atorvastatin 20mg PO daily
"""

FEWSHOT_OUTPUT = """Patient name: Jane Doe
MRN: 99887766
DOB: 1980-06-22
Sex: F
Admit date: not stated
Discharge date: not stated
Diagnoses:
- Type 2 diabetes mellitus
- Hyperlipidemia
Medications:
- Metformin | 1000 mg | PO | BID
- Atorvastatin | 20 mg | PO | daily
"""


def build_messages(note: str) -> list[dict]:
    """Return the chat messages array for extracting from `note`."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Clinical note:\n{FEWSHOT_NOTE}"},
        {"role": "assistant", "content": FEWSHOT_OUTPUT},
        {"role": "user", "content": f"Clinical note:\n{note}"},
    ]


# ----- Phase 3: JSON-schema prompts -----

JSON_SYSTEM_PROMPT = """You are a clinical data extraction assistant.
Extract structured fields from the clinical note. Return ONLY a JSON object
matching this shape:

{
  "patient":     {"name", "mrn", "dob", "sex"},
  "encounter":   {"admit_date", "discharge_date"},
  "diagnoses":   ["..."],
  "medications": [{"name", "dose", "route", "frequency"}, ...]
}

Rules:
- Use ISO dates (YYYY-MM-DD) when possible.
- If a field is not stated in the note, set it to null.
- Do not invent data. Only use what's in the note.
"""

JSON_FEWSHOT_NOTE = """Patient: Jane Doe
MRN: 99887766
DOB: 1980-06-22  Sex: F
Diagnoses: 1. Type 2 diabetes mellitus 2. Hyperlipidemia
Medications: Metformin 1000mg PO BID; Atorvastatin 20mg PO daily
"""

JSON_FEWSHOT_OUTPUT = (
    '{"patient":{"name":"Jane Doe","mrn":"99887766","dob":"1980-06-22","sex":"F"},'
    '"encounter":{"admit_date":null,"discharge_date":null},'
    '"diagnoses":["Type 2 diabetes mellitus","Hyperlipidemia"],'
    '"medications":['
    '{"name":"Metformin","dose":"1000 mg","route":"PO","frequency":"BID"},'
    '{"name":"Atorvastatin","dose":"20 mg","route":"PO","frequency":"daily"}'
    ']}'
)


def build_messages_json(note: str) -> list[dict]:
    """Chat messages for Phase 3 JSON-constrained extraction."""
    return [
        {"role": "system", "content": JSON_SYSTEM_PROMPT},
        {"role": "user", "content": f"Clinical note:\n{JSON_FEWSHOT_NOTE}"},
        {"role": "assistant", "content": JSON_FEWSHOT_OUTPUT},
        {"role": "user", "content": f"Clinical note:\n{note}"},
    ]
