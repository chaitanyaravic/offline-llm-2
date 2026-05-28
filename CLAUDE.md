# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project context

Offline, PHI-safe pipeline that reads clinical notes (`.txt` / `.pdf`),
extracts structured fields with a local LLM, normalizes the result, and
writes per-file JSON + a summary CSV. Built as a **phased learning project**
on Intel Mac with CPU-only `llama-cpp-python` against
`Llama-3.2-1B-Instruct-Q4_K_M.gguf` (~770 MB, gitignored at `models/`).

Every change should preserve the *pedagogical* shape: ONE new concept per phase,
"why before what" in any new `INSTRUCTIONS.md` section, and a Phase-X demo
script if you add a phase.

There is no linter or formatter wired up; tests are the only gate.

## Common commands

Always activate the venv first (`source venv/bin/activate`). Python 3.14.5.

| Task                             | Command                                                              |
|----------------------------------|----------------------------------------------------------------------|
| Install deps                     | `pip install -r requirements.txt`                                    |
| Smoke test (load model + 1 gen)  | `python scripts/phase1_hello.py`                                     |
| Few-shot text extraction (no schema) | `python scripts/phase2_extract.py samples/note1.txt`             |
| Extract JSON from one note       | `python scripts/phase3_extract_json.py samples/note1.txt`            |
| RAW vs CLEANED side-by-side      | `python scripts/phase4_cleanup.py samples/note1.txt`                 |
| Chunk + merge demo (long notes)  | `python scripts/phase5_ingest.py samples/note2.txt`                  |
| Batch a folder → outputs/        | `python -m extractor.cli --input samples --output outputs`           |
| Single file → outputs/           | `python -m extractor.cli --input samples/note1.txt --output outputs` |
| Override model                   | `python -m extractor.cli --input samples --model models/other.gguf`  |
| Larger context (default 2048)    | `python -m extractor.cli --input long_notes/ --n-ctx 8192`           |
| Run all tests                    | `pytest -v`                                                          |
| Run one test file                | `pytest tests/test_cleanup.py -v`                                    |
| Run one test by name             | `pytest -k normalize_date -v`                                        |

Tests never load the real LLM — they finish in <1 s. End-to-end LLM
validation lives in `VALIDATION.md`; reproduce with the batch CLI command above.

## Architecture

The library is a one-way dependency chain composed by `cli.py`. The single
entry point that wires it all together is **`pipeline.extract_from_file(llm, path)`**
— used by both the CLI and the mocked tests:

```
cli ─► pipeline ─► ingest    (read_document on .txt/.pdf via pypdf,
                              chunk_text, merge_extractions)
              ─► extract     (extract_text, extract_json — grammar-constrained)
                  ├─ prompts (SYSTEM_PROMPT + FEWSHOT_* + build_messages*)
                  └─ schema  (EXTRACTION_SCHEMA — JSON Schema dict)
              ─► cleanup     (normalize_date/route/frequency/dose + merge_modifier_diagnoses)
              ─► model       (load_model, generate)
```

Flow of one file through `extract_from_file`:

```
file ─► read_document ─► chunk_text ─► [per chunk: extract_json] ─►
        merge_extractions (first-non-null scalars; union dx; dedup meds) ─►
        clean_extraction (rule-based normalizers) ─► JSON on disk + CSV row
```

Two big-picture decisions to preserve:

- **Grammar-constrained JSON is non-negotiable.** `extract_json` uses
  `response_format={"type":"json_object","schema":EXTRACTION_SCHEMA}` so the
  sampler can ONLY emit tokens producing schema-valid JSON. Downstream code
  trusts the shape and does not defensively parse. If you add fields, update
  the schema first — everything else follows.
- **Rules normalize, LLM extracts.** The split in `cleanup.py` (dates,
  routes, frequencies, dose suffix-stripping, modifier-diagnosis merging) is
  deliberate — cheap, deterministic, testable. Resist the urge to ask the
  LLM to do these.

## Invariants (enforced by tests)

- `clean_extraction(x)` is **idempotent** and **does not mutate** its input.
- All LLM calls use **`temperature=0`**. Never add randomness to extraction.
- `EXTRACTION_SCHEMA` is the single source of truth for output shape.
- All bundled clinical data in `samples/` and `tests/` is **synthetic** —
  never commit real PHI.

## Test mocking strategy

Tests in `tests/test_pipeline_mocked.py` use `unittest.mock.MagicMock` to
stub `llm.create_chat_completion` with canned JSON responses. This lets the
full pipeline (ingest → extract → merge → clean) run without the model on
disk. New pipeline tests should follow the same `fake_llm` fixture pattern in
that file.

## Ripple guide — when you change X, update Y

| If you change…                  | Also update…                                                                  |
|---------------------------------|-------------------------------------------------------------------------------|
| `EXTRACTION_SCHEMA`             | `prompts.py` (JSON few-shot + `JSON_SYSTEM_PROMPT`), `cleanup.py`, tests       |
| A normalization rule            | `tests/test_cleanup.py` parametrize tables                                    |
| CLI flags                       | `INSTRUCTIONS.md` Phase 6 table, `CLAUDE.md` commands table, `README.md`      |
| Default model / model path      | `extractor/model.py::DEFAULT_MODEL_PATH`, `README.md` setup, `requirements.txt` if SDK bump |
| New runtime dependency          | `requirements.txt` (pin version, comment which phase needs it)                |
| New phase                       | Add `scripts/phaseN_*.py`, an `INSTRUCTIONS.md` section, an `EXERCISES.md` group |

## Performance notes

CPU-only on Intel Mac: first model load ~3–5 s, one `extract_json` call
~5–15 s for a short note, ~3 min for the full batch of 8 sample notes.
A 3B model is 2–3× slower again on this host. On Apple Silicon, llama.cpp
uses Metal automatically — no code change.

**Keep inputs short on this host.** If a sample triggers truncation or
runs hot, trim the note rather than bumping `max_tokens` or `n_ctx` —
the grammar-constrained sampler on the 1B model can emit unusually
verbose JSON on long inputs, and longer runs heat the laptop. Test logic
changes against the mocked `pytest` suite, not against the real model.

## Companion docs (read these before non-trivial work)

| File                     | Why open it                                                       |
|--------------------------|-------------------------------------------------------------------|
| `INSTRUCTIONS.md`        | Phase-by-phase rationale — why each module exists                 |
| `EXTRACTOR_EXPLAINED.md` | ASCII diagrams; quickest mental model refresh                     |
| `EXERCISES.md`           | Learner extension menu — useful as a backlog for safe enhancements |
| `VALIDATION.md`          | Honest end-to-end accuracy + known failure modes by dimension     |
