# Offline Clinical Data Extractor

A fully **offline** pipeline that reads clinical notes (`.txt` or `.pdf`),
extracts structured fields with a small local LLM, normalizes the result,
and writes per-file JSON plus a summary CSV.

---

## Overall summary

This repo is a complete, working end-to-end implementation — not a roadmap.
A small open-weights LLM (Llama 3.2 1B, quantized to ~770 MB) runs entirely
on the local CPU via `llama-cpp-python`. The pipeline ingests a clinical
note, asks the model for a JSON object whose shape is enforced by a JSON
Schema (so output is **guaranteed** parseable), then runs rule-based
cleanup (ISO dates, canonical drug routes/frequencies, dose suffix stripping,
diagnosis-modifier merging). The CLI batches a whole folder and produces
one structured `.json` per note plus a `summary.csv`.

It was built as a phased learning project (see `INSTRUCTIONS.md`); each
phase introduces one concept and is independently demoable.

### What's shipped

| Component                | Status     | Where                                                        |
|--------------------------|-----------:|--------------------------------------------------------------|
| GGUF model loader        | ✅ done    | `extractor/model.py` (`load_model`, `generate`)              |
| Few-shot text extraction | ✅ done    | `extractor/prompts.py` + `extractor/extract.py::extract_text`|
| JSON-schema extraction   | ✅ done    | `extractor/schema.py` + `extract.py::extract_json` (grammar-constrained) |
| Rule-based cleanup       | ✅ done    | `extractor/cleanup.py` (dates, route, freq, dose, dx merge)   |
| Ingestion (.txt + .pdf)  | ✅ done    | `extractor/ingest.py` (read, overlap chunking, merge)        |
| Batch CLI                | ✅ done    | `extractor/cli.py` → `python -m extractor.cli`               |
| Pytest suite             | ✅ done    | `tests/` — 58 tests, LLM mocked, <1 s                        |
| End-to-end validation    | ✅ done    | `VALIDATION.md` — 24/28 fields correct on 5 synthetic notes  |
| Synthetic note dataset   | ✅ done    | `samples/note1..8.txt` (5 scored in `VALIDATION.md`, 3 added as edge-case exercise material) |
| Per-phase demo scripts   | ✅ done    | `scripts/phase{1..5}*.py`                                     |
| Learner docs             | ✅ done    | `INSTRUCTIONS.md`, `EXTRACTOR_EXPLAINED.md`                   |

### Measured accuracy (1B baseline)

| Dimension          | Result        |
|--------------------|---------------|
| Patient IDs        | 14 / 14   ✅  |
| Encounter dates    | 3.5 / 4   🟡  |
| Diagnoses          | 4 / 5     🟡  |
| Medications        | 6 / 8     🟡  |
| Robustness (nulls) | 1 / 1     ✅  |
| Output JSON shape  | 5 / 5     ✅  |
| **Overall**        | **24 / 28 (86%)** |

See `VALIDATION.md` for the per-note grid and the specific failure modes.

### Sample dataset (`samples/`)

| File              | Shape / what it stresses                                                              |
|-------------------|---------------------------------------------------------------------------------------|
| `note1.txt`       | Discharge summary — COPD/pneumonia. Clean structured fields, ISO dates.               |
| `note2.txt`       | Endocrine progress note — diabetes/lipids. Mixed date formats ("5/9/2026", "June 22"). |
| `note3.txt`       | ED note — NSTEMI. Heavy abbreviations, military time, hold/continue meds.             |
| `note4.txt`       | Pediatrics well-child — minimal med list, PRN dosing.                                 |
| `note5_empty.txt` | **Edge case:** no patient identifiers at all. Tests null-robustness.                  |
| `note6.txt`       | Oncology discharge — modifier diagnoses ("severe", "uncontrolled"), "by mouth" route. |
| `note7.txt`       | Psychiatry follow-up — concatenated dosing ("100mg"), dashed DOB ("9-30-1992").       |
| `note8.txt`       | ID consult — slash-separated date ("2026/04/27"), spelled-out DOB, IV frequencies.    |

The first five are scored in `VALIDATION.md`. The latter three are
unscored exercise material — use them to probe edge cases when you change
extraction or cleanup logic.

---

## Setup

```bash
cd /path/to/offline-llm
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

mkdir -p models
curl -L -o models/Llama-3.2-1B-Instruct-Q4_K_M.gguf \
  https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf
```

## Run

```bash
# smoke test — load model + one raw completion
python scripts/phase1_hello.py

# few-shot text extraction (no schema yet)
python scripts/phase2_extract.py samples/note1.txt

# JSON-schema-constrained extraction
python scripts/phase3_extract_json.py samples/note1.txt

# RAW LLM JSON vs CLEANED JSON, side by side
python scripts/phase4_cleanup.py samples/note1.txt

# ingest a .txt or .pdf, chunk if long, merge, clean
python scripts/phase5_ingest.py samples/note2.txt

# batch a folder → outputs/*.json + outputs/summary.csv
python -m extractor.cli --input samples --output outputs
```

## Testing

```bash
pytest -v                                  # all 58 tests, <1 s
pytest tests/test_cleanup.py -v            # just the rule tests
pytest tests/test_pipeline_mocked.py -v    # end-to-end with mocked LLM
```

---

## Architecture

```
file ─► read_document ─► chunk_text ─► [per chunk: extract_json] ─►
        merge_extractions (first-non-null scalars; union dx; dedup meds) ─►
        clean_extraction (dates → ISO; routes/freq → canonical; dose suffix
        strip; dx-modifier merge) ─► one JSON per file + summary.csv
```

Module dependency direction is one-way:

```
cli ─► pipeline ─► ingest
                ─► extract ──► prompts
                          └──► schema
                ─► cleanup
                ─► model
```

Editable Mermaid versions of these (and the chunk/merge, sampling, and
end-to-end flows) live in [`diagrams/`](diagrams/) and render on GitHub.

## Project structure

```
offline-llm/
├── extractor/                  library (8 modules — see Architecture)
├── samples/                    8 synthetic clinical notes (5 scored, 3 edge-case)
├── scripts/                    per-phase demo scripts (phase1..phase5)
├── tests/                      58 pytest tests; LLM is mocked
├── diagrams/                   Mermaid sources for the architecture/flow diagrams
├── outputs/                    CLI output (.gitignored)
├── models/                     GGUF files (.gitignored)
├── venv/                       virtualenv (.gitignored)
│
├── INSTRUCTIONS.md             phase-by-phase learning guide
├── EXTRACTOR_EXPLAINED.md      ASCII diagrams of every concept
├── VALIDATION.md               accuracy report on the 5 sample notes
├── EXERCISES.md                optional extension menu for learners
├── PROGRESS.md                 session-resume status log
├── CLAUDE.md                   commands + architecture for future sessions
├── TEACHING_PLAYBOOK.md        the teaching style this project follows
├── README.md                   this file
├── requirements.txt
└── .gitignore
```

---

## Key concepts (already implemented in the code)

| Concept                | What it does                                         | Code pattern                                          |
|------------------------|------------------------------------------------------|-------------------------------------------------------|
| GGUF                   | One-file model format                                | `Llama(model_path="x.gguf")`                          |
| Quantization (Q4_K_M)  | 4-bit weights; ~4× smaller, ~4× faster than FP16     | (baked into the `.gguf` file)                         |
| Chat template          | Auto-applies role tags for instruct models           | `llm.create_chat_completion(messages=...)`            |
| Few-shot prompting     | One worked example in `messages` before the real note| `extractor/prompts.py::build_messages*`               |
| JSON-schema mode       | Sampler forced to match the schema                   | `response_format={"type":"json_object","schema":...}` |
| Idempotent cleanup     | `clean(clean(x)) == clean(x)`                        | `extractor/cleanup.py::clean_extraction`              |
| Overlap chunking       | Sliding-window splits so fields aren't cut in half   | `extractor/ingest.py::chunk_text`                     |
| Mocking the LLM        | Tests run in milliseconds, no model load             | `tests/test_pipeline_mocked.py`                       |

---

## Documentation

| File                                              | Purpose                                                            |
|---------------------------------------------------|--------------------------------------------------------------------|
| [INSTRUCTIONS.md](INSTRUCTIONS.md)                | Phase-by-phase learning guide. Start here.                         |
| [EXTRACTOR_EXPLAINED.md](EXTRACTOR_EXPLAINED.md)  | ASCII diagrams of every major concept.                             |
| [diagrams/](diagrams/)                            | Editable Mermaid sources for the architecture/flow diagrams.       |
| [VALIDATION.md](VALIDATION.md)                    | Honest end-to-end accuracy on the original 5 synthetic notes.      |
| [CLAUDE.md](CLAUDE.md)                            | Commands + architecture for future contributors.                   |
| [PROGRESS.md](PROGRESS.md)                        | Status log for resuming a session.                                 |
| [EXERCISES.md](EXERCISES.md)                      | *Optional* extension menu (challenges, not part of the shipped pipeline). |
| [TEACHING_PLAYBOOK.md](TEACHING_PLAYBOOK.md)      | The teaching style this project follows.                           |

---

## Built with

This project was built with [Claude Code](https://claude.ai/code) powered by **Claude Opus 4.7**.

---

## Safety / scope

- All bundled clinical notes in `samples/` and `tests/` are **synthetic**. No PHI.
- The whole point of running locally is that clinical text never leaves
  the machine. Don't add cloud LLM calls or telemetry without rethinking
  that guarantee.
- This is a learning baseline. Accuracy at the 1B model size is real but
  modest — see `VALIDATION.md` for exactly where it succeeds and fails.
