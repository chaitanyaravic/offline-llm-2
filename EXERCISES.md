# Exercises — Improvisations for Learners

Short challenges to extend each phase. Pick whichever look interesting; they
don't need to be done in order. Each one has:

- **Goal:** what you'll learn or build.
- **Hint:** where to start in the code.
- **Success looks like:** the observable result.

Difficulty: 🟢 easy · 🟡 medium · 🔴 stretch

---

## Phase 1 exercises — Hello Llama

### 🟢 1.1  Make output reproducible
**Goal:** see what `seed` does.
**Hint:** add `seed=42` to the `Llama(...)` call in `extractor/model.py`, or
pass it through `generate()`.
**Success looks like:** run `python scripts/phase1_hello.py` twice — same
completion both times.

### 🟢 1.2  Compare prompts
**Goal:** feel how prompt wording steers the model.
**Hint:** edit `scripts/phase1_hello.py` and try three different prompts:
"In a sunny meadow", "def fibonacci(n):", "The patient is a 67-year-old male with".
**Success looks like:** each prompt yields a wildly different style.

### 🟡 1.3  Time the inference
**Goal:** measure tokens-per-second on your machine.
**Hint:** wrap `generate(...)` with `time.perf_counter()`; divide
`max_tokens` by elapsed seconds.
**Success looks like:** you can quote your CPU throughput.

---

## Phase 2 exercises — Extraction by prompt

### 🟢 2.1  Crank the temperature
**Goal:** see why `temperature=0` matters for extraction.
**Hint:** pass `temperature=1.0` to `extract_text` and run the demo three times.
**Success looks like:** outputs differ across runs; some have hallucinated
extra meds or drifted formats.

### 🟡 2.2  Add a second few-shot example
**Goal:** test the "two-shot helps small models" claim.
**Hint:** in `extractor/prompts.py`, append another `user`/`assistant` pair
between the first one and the real note. Use a note shaped differently
from the first example.
**Success looks like:** behaviour on edge-case notes (Note 4 pediatric) improves.

### 🔴 2.3  Write your own synthetic note
**Goal:** stress-test the extractor on a format it hasn't seen.
**Hint:** new file in `samples/`, then re-run `phase2_extract.py` on it.
**Success looks like:** you can predict which fields will succeed/fail
before you run it.

---

## Phase 3 exercises — Structured output (JSON schema)

### 🟢 3.1  Constrain `sex` to an enum
**Goal:** use JSON Schema enum to forbid invalid values.
**Hint:** in `extractor/schema.py`, change
`"sex": {"type": ["string", "null"]}` to
`"sex": {"type": ["string", "null"], "enum": ["M", "F", "other", null]}`.
**Success looks like:** `sex` can ONLY be one of those values.

### 🟡 3.2  Add a new required field
**Goal:** learn how schema changes ripple through the code.
**Hint:** add `"chief_complaint": {"type": ["string", "null"]}` to the patient
object and mark it required. Update the JSON few-shot in `prompts.py` to
include it. Re-run.
**Success looks like:** all outputs now contain `chief_complaint` (often null).

### 🔴 3.3  Switch to a Pydantic model
**Goal:** generate the schema from a Pydantic class — single source of truth.
**Hint:** `pip install pydantic`, define a `BaseModel`, then
`response_format={"type": "json_object", "schema": MyModel.model_json_schema()}`.
**Success looks like:** removing `schema.py` and using the Pydantic class instead.

---

## Phase 4 exercises — Cleanup & normalization

### 🟢 4.1  Add a new frequency alias
**Goal:** make `normalize_frequency` understand "q4-6h".
**Hint:** add tests to `tests/test_cleanup.py` FIRST (TDD), then update
`_FREQ_MAP` in `extractor/cleanup.py`.
**Success looks like:** `pytest -v` includes a new green test row.

### 🟡 4.2  Extract numeric dose value + unit separately
**Goal:** turn `"40 mg"` into `{"value": 40, "unit": "mg"}`.
**Hint:** new function `parse_dose_value(value: str) -> dict | None`.
Don't replace `normalize_dose` — call this in addition.
**Success looks like:** medications carry both a tidy string AND structured numbers.

### 🔴 4.3  Build a tiny ICD-10 lookup
**Goal:** hint at codes for common diagnoses.
**Hint:** small dict in a new `extractor/icd10.py`:
`{"hypertension": "I10", "type 2 diabetes mellitus": "E11.9", ...}`
Add `icd10` field to each diagnosis in the output.
**Success looks like:** `outputs/note1.json` shows `{"text": "Hypertension...", "icd10": "I10"}`.

---

## Phase 5 exercises — Document ingestion

### 🟢 5.1  Add `.docx` support
**Goal:** parse Word documents.
**Hint:** `pip install python-docx`; add a `_read_docx(path)` to
`extractor/ingest.py` and extend `read_document`.
**Success looks like:** dropping a `.docx` into `samples/` works.

### 🟡 5.2  Force a multi-chunk run
**Goal:** see what happens with a long note.
**Hint:** create `samples/note_long.txt` ≥ 15k chars (copy-paste a real
guideline into it). Run `phase5_ingest.py`.
**Success looks like:** "X characters → N chunks" with N ≥ 3; merge still produces sensible JSON.

### 🔴 5.3  Better merge for conflicting scalars
**Goal:** instead of first-non-null-wins, pick the *majority* value across chunks.
**Hint:** in `merge_extractions`, count occurrences of each candidate per
field, take the mode.
**Success looks like:** a long note that mentions DOB twice in two formats
ends up with the most common normalized form.

---

## Phase 6 exercises — Batch CLI

### 🟢 6.1  Add a `--quiet` flag
**Goal:** practice argparse.
**Hint:** `p.add_argument("--quiet", action="store_true")`; gate the
`print(...)` statements.
**Success looks like:** `python -m extractor.cli ... --quiet` prints only errors.

### 🟡 6.2  Skip already-processed files
**Goal:** make runs resumable.
**Hint:** before each note, check if `output_dir / f"{stem}.json"` exists; skip if so.
**Success looks like:** re-running on the same folder is instant after the first pass.

### 🔴 6.3  Parallelize across files (with care)
**Goal:** use a process pool to do multiple notes at once.
**Hint:** llama-cpp Llama objects aren't safe to share across processes —
each worker must load its own. Try `concurrent.futures.ProcessPoolExecutor`
with a small `max_workers`; pass the model path, not the Llama object.
**Success looks like:** wall-clock time drops by ~workers× on a large folder,
though peak RAM rises by the same factor.

---

## Phase 7 exercises — Tests

### 🟢 7.1  Lock the schema shape
**Goal:** catch accidental schema breakage.
**Hint:** new test in `tests/test_schema.py` that asserts
`set(EXTRACTION_SCHEMA["properties"]) == {"patient","encounter","diagnoses","medications"}`.
**Success looks like:** removing a top-level key fails CI.

### 🟡 7.2  Add a sample-fixture-driven test
**Goal:** read `samples/note1.txt` once and reuse via a fixture.
**Hint:** `@pytest.fixture(scope="session")` returning the file's text.
**Success looks like:** several tests share the fixture without re-reading
the file.

### 🔴 7.3  Property-based test for `merge_extractions`
**Goal:** generate random extractions with Hypothesis, assert merge
properties (associativity, idempotent on duplicates, monotonic field counts).
**Hint:** `pip install hypothesis`; build a small strategy for an extraction dict.
**Success looks like:** the test finds at least one edge case the existing
unit tests miss.

---

## Phase 8 exercises — Validation

### 🟢 8.1  Compute extraction recall by hand
**Goal:** ground-truth one note and write the percentage.
**Hint:** open `samples/note1.txt`, count expected fields, then count how
many appear correctly in `outputs/note1.json`.
**Success looks like:** you can defend the "86%" figure in `VALIDATION.md` —
or correct it.

### 🟡 8.2  Build a tiny evaluator
**Goal:** automate Phase 8 grading.
**Hint:** create `scripts/evaluate.py`. For each note, load a ground-truth
JSON from `samples/note*.expected.json` and compare to `outputs/note*.json`
field by field. Print precision/recall.
**Success looks like:** one command gives you the same grid you'd produce by hand.

### 🔴 8.3  Run two models head-to-head
**Goal:** measure whether a 3B model meaningfully beats the 1B baseline.
**Hint:** download `Llama-3.2-3B-Instruct-Q4_K_M.gguf` to `models/`. Run
the CLI twice, once with each model, to different output folders. Compare.
**Success looks like:** a small markdown table showing per-dimension deltas.

---

## Capstone challenges

These pull multiple phases together.

### 🔴 Capstone A — Vitals + labs
Add `vitals: [{type, value, unit, timestamp}]` and `labs: [{name, value, unit,
reference_range, flag}]` to the schema. Update prompts, cleanup,
tests, and the validation grid.

### 🔴 Capstone B — De-identification layer
Add a `redact.py` module that masks names, MRNs, and dates in the input
*before* the LLM ever sees them, using a deterministic mapping so the
output can still be re-identified locally. Verify with a test that no
original name leaks through.

### 🔴 Capstone C — Tiny web UI
Build a single-page Flask/FastAPI form that accepts a pasted note and
returns the cleaned JSON. Keep it local-only — no network calls.

---

## How to share what you learned

If you do an exercise that surprises you, jot a one-line note (with the
date) in a `Lessons` section at the bottom of this file — or in a fresh
`NOTES.md` if you'd rather keep it separate. Future you (or future Claude)
will thank you.
