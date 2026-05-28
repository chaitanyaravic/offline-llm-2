# Offline Clinical Data Extractor — Phased Learning Guide

A local, offline pipeline that reads clinical notes, extracts structured
fields with a small open-weights LLM, and cleans up the result.
We build it in **8 phases**, one new concept at a time.

> Follow this guide top-to-bottom. Each phase ends with you running something
> and seeing it work before we move to the next one.

---

## Phase 1: Hello Llama

### What you'll learn

- **GGUF** — the file format that packages an LLM's weights into a single file.
- **Quantization** — shrinking a model's weights so it fits in laptop RAM.
- **`llama-cpp-python`** — Python bindings for the C++ engine `llama.cpp`.
- **A "completion"** — when a language model takes some text and continues it.

Before any code, here's the mental model:

```
┌──────────────────────┐        ┌──────────────────────┐        ┌─────────────────┐
│ Llama-3.2-1B         │ load   │  llama-cpp-python    │  call  │  text from the  │
│ Instruct.Q4_K_M.gguf │───────►│  (Llama object)      │───────►│  model          │
│  ≈ 770 MB on disk    │        │  loads weights to    │        │                 │
└──────────────────────┘        │  RAM, ready to run   │        └─────────────────┘
                                └──────────────────────┘
```

### Concepts explained before code

- **GGUF** = "GPT-Generated Unified Format". One file holds the model weights,
  the tokenizer, and metadata. Created by the `llama.cpp` project so models
  can be loaded by C++ programs without any Python framework.
- **Quantization** = compressing 16-bit floating-point weights down to 4-bit
  integers. A 1.2 GB raw model becomes ≈770 MB after quantization. You lose
  a little quality in exchange for huge speed and size wins.
  Think of it like a **JPEG of a photo** — smaller file, mostly the same picture.
- **`Q4_K_M`** = a specific quantization recipe. **Q4** = 4-bit, **K** = uses
  "k-quants" (a clever per-block scheme), **M** = medium accuracy variant.
  Good default for laptops.
- **`llama-cpp-python`** = a thin Python wrapper over the C++ engine. Your
  Python code calls into compiled C++ for the actual math.
- **`n_ctx`** = "context window" — the maximum number of tokens (prompt +
  generated output) the model can hold in mind at once. 2048 is plenty for
  Phase 1.

---

### Step 1.1 — Set up the Python environment

A **venv** (virtual environment) is a private folder of Python packages,
isolated from the rest of your system. Always use one per project.

```bash
cd /path/to/offline-llm
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

**Key concepts explained:**
- **`python3 -m venv venv`** — runs Python's built-in `venv` module to create
  a folder named `venv/` that holds an isolated Python install.
- **`source venv/bin/activate`** — switches your shell so `python` and `pip`
  now point inside `venv/`. You'll see `(venv)` in your prompt.
- **`pip install -r requirements.txt`** — installs every package listed in
  the `requirements.txt` file. Right now that's just `llama-cpp-python`.

---

### Step 1.2 — Download the model

We use **Llama 3.2 1B Instruct**, quantized to Q4_K_M (~770 MB).
Bartowski's Hugging Face mirror hosts GGUF builds with no login required.

```bash
mkdir -p models
curl -L -o models/Llama-3.2-1B-Instruct-Q4_K_M.gguf \
  https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf
```

**Key concepts explained:**
- **`curl -L`** — `curl` downloads files over HTTP. The `-L` flag follows
  redirects (Hugging Face URLs redirect once before the actual file).
- **`-o <file>`** — writes the download to this path instead of stdout.
- **`.gguf` is huge** — that's why `models/*.gguf` is in `.gitignore`.
  Never commit model files to git.

---

### Step 1.3 — Load the model and generate text

Open `extractor/model.py` — that's our minimal wrapper. The whole file is two
functions:

```python
def load_model(model_path, n_ctx=2048, verbose=False) -> Llama:
    return Llama(model_path=str(model_path), n_ctx=n_ctx, verbose=verbose)

def generate(llm, prompt, max_tokens=64) -> str:
    result = llm(prompt, max_tokens=max_tokens)
    return result["choices"][0]["text"]
```

**Key concepts explained:**
- **`Llama(...)`** — the class from `llama_cpp` that holds an in-memory model.
  Constructing it loads the .gguf file from disk into RAM (takes a few seconds).
- **`llm(prompt, max_tokens=...)`** — calling the instance like a function
  generates text. `max_tokens` is the hard cap on how many new tokens to
  produce. A **token** is roughly 3-4 characters of English text.
- **`result["choices"][0]["text"]`** — `llm()` returns a dictionary shaped
  like an OpenAI API response, even though we're running locally. We grab
  the first (only) choice's text.

---

### Step 1.4 — Run the demo

```bash
python scripts/phase1_hello.py
```

You should see something like:

```
Loading model... (first load may take a few seconds)
Model loaded.

PROMPT:     'The patient is a 67-year-old male with'
COMPLETION: ' a history of hypertension and type 2 diabetes who presents with...'
```

The exact continuation will differ every run — that's the model sampling
tokens. We'll learn to control that in **Phase 2**.

---

### Phase 1 checklist

- [ ] `venv/` exists and is activated
- [ ] `llama-cpp-python` installed
- [ ] `models/Llama-3.2-1B-Instruct-Q4_K_M.gguf` exists (~770 MB)
- [ ] `python scripts/phase1_hello.py` prints a non-empty completion
- [ ] You can explain GGUF, quantization, and what `n_ctx` means

When all five are true, you're ready for Phase 2.

---

## Phase 2: Extraction by prompt

### What you'll learn

- **Instruct-tuned model** — a model fine-tuned to *follow instructions*.
- **Chat template** — the special tokens an instruct model expects around
  each turn (`<|user|>...`, `<|assistant|>...`). The GGUF metadata stores it
  and `create_chat_completion` applies it for you.
- **Few-shot prompting** — showing the model 1-2 worked examples so it
  copies the format.
- **`temperature=0`** — making generation deterministic (no randomness),
  which is what you want for extraction tasks.

### The new mental model

```
┌──────────────────────────────────────────────────────────────────┐
│ messages = [                                                      │
│   {"role": "system",    "content": "You are an extractor..."},    │
│   {"role": "user",      "content": "Note: <example>"},            │
│   {"role": "assistant", "content": "<expected output>"},   ←shot  │
│   {"role": "user",      "content": "Note: <REAL note>"},          │
│ ]                                                                  │
│                              │                                     │
│                              ▼                                     │
│             llm.create_chat_completion(messages, temperature=0)    │
│                              │                                     │
│                              ▼                                     │
│                   text response from the model                     │
└──────────────────────────────────────────────────────────────────┘
```

The pattern in plain English: **"Here's how it should look. Now do it."**

### Files added in this phase

```
samples/note1.txt          ← synthetic discharge summary
samples/note2.txt          ← synthetic endocrinology progress note
extractor/prompts.py       ← system prompt + few-shot example + build_messages()
extractor/extract.py       ← extract_text(llm, note)
scripts/phase2_extract.py  ← demo: read a note file, print extracted fields
```

### Step 2.1 — Read the prompt module

Open `extractor/prompts.py`. Notice three pieces:

1. **`SYSTEM_PROMPT`** — global instructions ("you are an extractor, use this
   format, write 'not stated' if missing").
2. **`FEWSHOT_NOTE` + `FEWSHOT_OUTPUT`** — one paired example.
3. **`build_messages(note)`** — assembles the chat messages list.

**Key concepts explained:**
- **System message** — like setting the scene before the conversation starts.
  Instruct models pay extra attention to it.
- **Few-shot vs zero-shot** — *zero-shot* = just ask. *Few-shot* = show
  examples first. Few-shot dramatically improves small models on structured tasks.
- **One example is often enough** — adding more rarely helps a 1B model and
  uses up your context window.

### Step 2.2 — Run the extraction

```bash
python scripts/phase2_extract.py samples/note1.txt
```

You should see all patient fields, diagnoses, and medications pulled out —
roughly the right text, in roughly the right shape.

### Step 2.3 — Observe the imperfections

The model will probably:
- Not stick perfectly to the pipe-delimited medication format.
- Sometimes keep generating extra content past the medications list.
- Occasionally mis-split dose vs frequency.

**This is the whole point.** Free-text output is fragile. In **Phase 3** we'll
switch to **JSON schema mode** so the model is *forced* to emit valid JSON
matching a strict schema. Then downstream code can trust the shape.

### Phase 2 checklist

- [ ] You can run `python scripts/phase2_extract.py samples/note1.txt`.
- [ ] Output includes Patient name, MRN, DOB, Sex, dates, diagnoses, meds.
- [ ] You can explain why we set `temperature=0` for extraction.
- [ ] You can point to the few-shot example in `prompts.py`.

When all four are true, you're ready for Phase 3.

---

## Phase 3: Structured output (JSON schema)

### What you'll learn

- **JSON Schema** — a small JSON document describing the *shape* of valid JSON.
- **Grammar-constrained sampling** — the model is mathematically prevented
  from emitting tokens that would break the schema. The output is
  **guaranteed** parseable.
- **`response_format`** — the `llama-cpp-python` parameter that turns
  grammar mode on.

### Why this matters

In Phase 2 the model output was free text. Downstream code couldn't trust it.
A single trailing comma or stray newline broke everything. With schema mode:

```
┌────────────────────────────────────────────────────────────┐
│  Phase 2 (text):   model can write ANYTHING.               │
│                    Downstream code must defend itself.     │
│                                                            │
│  Phase 3 (JSON):   model can ONLY write valid JSON         │
│                    matching the schema. Downstream code    │
│                    can just `json.loads(...)` and trust.   │
└────────────────────────────────────────────────────────────┘
```

How it works under the hood: at each step, the sampler asks "given the
schema and what we've generated so far, which next tokens would be legal?"
Illegal tokens get probability 0 — they cannot be chosen.

### Files added in this phase

```
extractor/schema.py             ← EXTRACTION_SCHEMA (the JSON Schema dict)
extractor/extract.py            ← new function extract_json()
extractor/prompts.py            ← build_messages_json() + JSON few-shot
scripts/phase3_extract_json.py  ← demo: prints parsed JSON
```

### Step 3.1 — Read the schema

Open `extractor/schema.py`. Notice:
- Every property has `"type"` declaring what's allowed.
- Optional fields use `"type": ["string", "null"]` — meaning "string OR null".
- `"required"` lists the property keys that MUST appear in the output.

**Key concepts explained:**
- **Nullable** — distinguish "I looked and it's missing" (`null`) from
  "I never even tried" (key absent). The schema requires every key — the
  model fills missing data with `null`.
- **Schema as contract** — once this file exists, downstream code knows
  exactly what shape to expect. No defensive coding needed.

### Step 3.2 — Read the new extract function

```python
def extract_json(llm, note, max_tokens=600, temperature=0.0) -> dict:
    response = llm.create_chat_completion(
        messages=build_messages_json(note),
        max_tokens=max_tokens,
        temperature=temperature,
        response_format={"type": "json_object", "schema": EXTRACTION_SCHEMA},
    )
    return json.loads(response["choices"][0]["message"]["content"])
```

The only new piece is `response_format`. That single argument flips on
grammar-constrained sampling.

### Step 3.3 — Run the JSON extraction

```bash
python scripts/phase3_extract_json.py samples/note1.txt
```

You should see a parsed `dict` printed as indented JSON.

### Step 3.4 — Observe the *new* imperfections

Even with valid JSON, the *content* still needs work. On `note1.txt` you'll
likely see:
- **DOB still as `"03/15/1957"`** — not ISO. The schema doesn't enforce date
  format, only that it's a string.
- **`"Hypertension, well-controlled"` split into two diagnoses.** Comma in
  the source confused the model.
- **`"40 mg PO daily for 5 days"` jammed into the `dose` field.** Route and
  frequency duplicated.

**Phase 4** ("Cleanup & normalization") fixes these with a mix of small
regex/rule passes and targeted re-prompting.

### Phase 3 checklist

- [ ] `python scripts/phase3_extract_json.py samples/note1.txt` prints JSON.
- [ ] `json.loads(...)` works without errors (already happens inside `extract_json`).
- [ ] You can explain what `response_format={"type": "json_object", "schema": ...}` does.
- [ ] You spotted at least one *content* problem the JSON shape can't fix.

When all four are true, you're ready for Phase 4.

---

## Phase 4: Cleanup & normalization

### What you'll learn

- **Why rules beat the LLM** for small, deterministic transformations.
- **`datetime.strptime`** — parse strings into date objects with format codes.
- **`re` (regex)** — match patterns of text. We use small regexes for dose
  and modifier trimming.
- **Idempotency** — running cleanup twice gives the same result as once.
  Important so re-running the pipeline never makes things worse.

### When LLM, when rules?

```
┌────────────────────────────────┬───────────────────────────────────────────┐
│ Use the LLM for…               │  Use rules/regex for…                     │
├────────────────────────────────┼───────────────────────────────────────────┤
│  Reading natural language      │  Reformatting dates                       │
│  Deciding what IS a diagnosis  │  Mapping "by mouth" → "PO"                │
│  Tying a med to a dose         │  Mapping "twice a day" → "BID"            │
│  Inference + reasoning         │  Stripping suffix junk from a dose string │
└────────────────────────────────┴───────────────────────────────────────────┘
```

Rules are **free, fast, deterministic, and testable**. Save the LLM for the
parts that actually need language understanding.

### Files added in this phase

```
extractor/cleanup.py          ← all normalizers + clean_extraction()
scripts/phase4_cleanup.py     ← demo: prints RAW and CLEANED side by side
```

### Step 4.1 — Read the cleanup module

Open `extractor/cleanup.py`. Five small functions:

```
normalize_date(value)        → "03/15/1957" → "1957-03-15"
normalize_route(value)       → "by mouth"   → "PO"
normalize_frequency(value)   → "as needed"  → "PRN"
normalize_dose(value)        → "40 mg PO daily for 5 days" → "40 mg"
merge_modifier_diagnoses([]) → ["Hypertension","well-controlled"] → ["Hypertension, well-controlled"]
```

Plus a top-level `clean_extraction(data)` that calls them in the right
places on the LLM's JSON.

**Key concepts explained:**
- **Lookup table** — a dict from messy form → canonical form. The shortest
  possible "normalizer".
- **`re.sub(pattern, replacement, text)`** — find pattern, replace it.
  We use it to strip trailing route/frequency words off dose strings.
- **`copy.deepcopy`** — clone the entire nested dict before editing, so
  callers' data isn't accidentally mutated.

### Step 4.2 — Run the before/after demo

```bash
python scripts/phase4_cleanup.py samples/note1.txt
```

You'll see the raw LLM JSON first, then the cleaned version. Compare:

| Field            | RAW                                         | CLEANED                       |
|------------------|---------------------------------------------|-------------------------------|
| DOB              | `03/15/1957`                                | `1957-03-15`                  |
| Diagnoses        | `[..., "Hypertension", "well-controlled"]`  | `[..., "Hypertension, well-controlled"]` |
| Prednisone dose  | `40 mg PO daily for 5 days`                 | `40 mg`                       |
| Albuterol freq   | `as needed`                                 | `PRN`                         |

### Phase 4 checklist

- [ ] `python scripts/phase4_cleanup.py samples/note1.txt` shows RAW + CLEANED.
- [ ] Cleaned DOB is ISO format.
- [ ] Modifier-only diagnoses are merged into the previous diagnosis.
- [ ] Doses no longer carry route/frequency/duration suffixes.

When all four are true, you're ready for Phase 5.

---

## Phase 5: Document ingestion (.txt + .pdf)

### What you'll learn

- **File-format dispatch** — pick a reader based on file extension.
- **`pypdf`** — pure-Python PDF text extractor.
- **Chunking with overlap** — splitting a long document into pieces small
  enough to fit in `n_ctx`, with a sliding window so fields don't get cut.
- **Merging strategies** — combining per-chunk extractions into one record.

### The pipeline so far

```
┌──────────┐  read   ┌──────────┐ chunk  ┌──────────┐  per-chunk  ┌──────────┐  merge  ┌──────────┐  cleanup ┌──────────┐
│  .txt    │────────►│   text   │───────►│ chunks[] │────────────►│ JSON[]   │────────►│ merged   │─────────►│ FINAL    │
│  .pdf    │         │          │ slide  │          │ extract_json│          │  union  │ extract  │   rules  │  JSON    │
└──────────┘         └──────────┘        └──────────┘             └──────────┘         └──────────┘          └──────────┘
```

### Files added in this phase

```
extractor/ingest.py         ← read_document() + chunk_text() + merge_extractions()
scripts/phase5_ingest.py    ← demo: full pipeline on any .txt or .pdf
```

### Step 5.1 — Read the ingest module

Three small functions:

- **`read_document(path)`** — looks at the file extension, returns plain text.
- **`chunk_text(text, max_chars=6000, overlap_chars=400)`** — sliding-window split.
- **`merge_extractions([...])`** — union dx and meds, first-non-null for scalars.

**Key concepts explained:**
- **Overlap** — when you split a document, a sentence may straddle the
  boundary. Including ~400 chars of the previous chunk at the start of the
  next chunk guarantees no field gets cut in half.
- **Lazy import** — `pypdf` is `import`-ed only inside `_read_pdf`, so if you
  never touch a PDF, you don't pay the import cost.
- **De-duping** — when merging meds across chunks, the same medication
  often appears twice. We de-dupe by lowercased name; first occurrence wins.

### Step 5.2 — Run on the second sample

```bash
python scripts/phase5_ingest.py samples/note2.txt
```

This one has no encounter dates (a clinic note, not a discharge) — those
fields should come back as `null`.

### Step 5.3 — Try a PDF (optional)

Drop any clinical-ish PDF (a guideline, a sample note, anything) into
`samples/` and run the same script on it. Lots of warnings from `pypdf`
about fonts are normal — extraction still works.

### Phase 5 checklist

- [ ] `python scripts/phase5_ingest.py samples/note2.txt` produces a full JSON.
- [ ] `encounter.admit_date` and `encounter.discharge_date` are `null` for note2.
- [ ] You can explain why chunks overlap.
- [ ] You can read `merge_extractions` and predict the dedup strategy.

When all four are true, you're ready for Phase 6.

---

## Phase 6: Batch CLI

### What you'll learn

- **`argparse`** — Python's standard library for parsing command-line
  arguments. Each `add_argument` call defines one flag.
- **`python -m <package>.<module>`** — running a module as a script. Better
  than `python path/to/cli.py` because it works regardless of where you `cd`.
- **`Path.rglob`** — recursively glob a folder for files matching a pattern.
- **`csv.DictWriter`** — writing rows as dicts into a CSV file.

### Files added in this phase

```
extractor/pipeline.py   ← extract_from_file(llm, path) — one-call pipeline
extractor/cli.py        ← the argparse-driven batch processor
```

### Step 6.1 — Read the pipeline shim

`extractor/pipeline.py` is six lines. It composes everything we built so far:

```python
def extract_from_file(llm, path):
    text     = read_document(path)
    chunks   = chunk_text(text)
    per      = [extract_json(llm, c) for c in chunks]
    merged   = merge_extractions(per)
    return     clean_extraction(merged)
```

The CLI just calls this and writes the result to disk.

### Step 6.2 — Read the CLI

Open `extractor/cli.py`. The four argparse flags:

| Flag        | Default        | What it does                                  |
|-------------|----------------|-----------------------------------------------|
| `--input`   | (required)     | A file or folder of notes.                    |
| `--output`  | `outputs`      | Where to write per-file JSON + summary.csv.   |
| `--model`   | (default GGUF) | Use a different .gguf file.                   |
| `--n-ctx`   | `2048`         | Context window. Raise for very long notes.    |

### Step 6.3 — Run on the whole sample folder

```bash
python -m extractor.cli --input samples --output outputs
```

You'll see:

```
Found 8 file(s) to process.
[1/8] samples/note1.txt
  -> outputs/note1.json
[2/8] samples/note2.txt
  -> outputs/note2.json
...
[8/8] samples/note8.txt
  -> outputs/note8.json
Summary: outputs/summary.csv
```

And `outputs/summary.csv` is a tidy spreadsheet-ready file with one row per
input note. Open it in any tool — patient name, MRN, DOB, sex, encounter
dates, diagnosis count, medication count.

### Phase 6 checklist

- [ ] `python -m extractor.cli --input samples --output outputs` succeeds.
- [ ] `outputs/note1.json` … `outputs/note8.json` exist and parse with `jq`/`json.tool`.
- [ ] `outputs/summary.csv` has a header row plus one row per input.
- [ ] You can explain what `--input` does when pointed at a folder vs a file.

When all four are true, you're ready for Phase 7.

---

## Phase 7: Tests

### What you'll learn

- **`pytest`** — the de-facto Python test runner. Test functions just start
  with `test_`.
- **`@pytest.mark.parametrize`** — one test function, many `(input, expected)`
  rows. Each row gets its own pass/fail line.
- **`tmp_path` fixture** — a temporary folder pytest creates per test and
  cleans up after. Lets us write to disk without worrying about cleanup.
- **`unittest.mock.MagicMock`** — fake objects that record calls and return
  whatever you tell them to. We mock the Llama model so the pipeline test
  runs in milliseconds, not minutes.

### Why we mock the LLM

```
┌─────────────────────────────┬─────────────────────────────────────────────┐
│  Without mocks              │  With mocks                                 │
├─────────────────────────────┼─────────────────────────────────────────────┤
│  Each test loads the model  │  Tests run in 0.3 s total                   │
│  (~3 s) and runs inference  │  Pipeline test pins the *shape* of the      │
│  (~10 s)                    │  contract between extract → merge → clean   │
│  Output is non-deterministic│  Output is deterministic and asserted exactly│
└─────────────────────────────┴─────────────────────────────────────────────┘
```

You still test the *real* LLM end-to-end in Phase 8 — but only once, against
the full pipeline.

### Files added in this phase

```
tests/__init__.py
tests/conftest.py                 ← adds project root to sys.path
tests/test_cleanup.py             ← 43 tests for the rule normalizers
tests/test_ingest.py              ← 9  tests for chunk/merge/read
tests/test_pipeline_mocked.py     ← 2  end-to-end tests with a MagicMock model
```

### Step 7.1 — Read one parametrized test

From `tests/test_cleanup.py`:

```python
@pytest.mark.parametrize("raw, expected", [
    ("03/15/1957", "1957-03-15"),
    ("June 22, 1980", "1980-06-22"),
    ("", None),
    ("not stated", None),
])
def test_normalize_date(raw, expected):
    assert normalize_date(raw) == expected
```

Each row becomes a separate test case in the report. You'll see them as
`test_normalize_date[03/15/1957-1957-03-15] PASSED`, etc.

### Step 7.2 — Read the mocked pipeline test

```python
@pytest.fixture
def fake_llm():
    llm = MagicMock()
    llm.create_chat_completion.return_value = {
        "choices": [{"message": {"content": json.dumps(canned_data)}}]
    }
    return llm
```

The fake `llm` looks exactly like a real Llama instance to the pipeline, but
returns a fixed answer instantly. The test asserts cleanup ran (ISO date,
merged dx, normalized route/freq).

### Step 7.3 — Run the suite

```bash
pytest -v
```

Expect 55 passing tests in well under a second.

### Phase 7 checklist

- [ ] `pytest -v` exits 0 with all green.
- [ ] You can explain what `parametrize` does and why it's useful here.
- [ ] You can explain why we mock `Llama` for unit tests.
- [ ] You can describe what `tmp_path` is.

When all four are true, you're ready for the final phase.

---

## Phase 8: Agent validation

### What you'll learn

- **End-to-end validation** — the kind that catches what unit tests can't:
  the actual model's accuracy on realistic input.
- **Dimensional grading** — score each capability (D1: patient IDs, D2:
  encounter dates, D3: diagnoses, D4: medications, D5: robustness, D6:
  output shape) separately, so failures are diagnosable.
- **Honest reporting** — record both PASS and FAIL (and PARTIAL), and
  explain *why* each failure happened.

### How the report is built

I (Claude, acting as an agent) did this:

1. Wrote two more synthetic notes covering edge cases: an ED note (med list
   buried in narrative) and a pediatric well-child note (no obvious dx).
2. Wrote a stub "no identifiers" note to test graceful nulls.
3. Ran `python -m extractor.cli --input samples --output outputs`.
4. Read each `outputs/note*.json` against its `samples/note*.txt`.
5. Recorded every field's grade in `VALIDATION.md`.

### Results headline (see `VALIDATION.md` for the full grid)

```
                       D1   D2   D3   D4   D5
Patient IDs            ✅
Encounter dates             🟡
Diagnoses                        🟡
Medications                            🟡
Robustness                                  ✅
Overall                24 / 28 fields = 86%
```

The 1B model nails patient identifiers and well-structured medication
sections, but misses meds buried in narrative and occasionally produces
empty/garbage diagnosis lists when phrasing is unusual ("Healthy 8-year-old").

### What this teaches

```
┌─────────────────────────────────────────────────────────────────────┐
│  Tests give you confidence the code is CORRECT.                     │
│  Validation gives you confidence the model is USEFUL.               │
│  Both matter. Neither replaces the other.                           │
└─────────────────────────────────────────────────────────────────────┘
```

### Phase 8 checklist

- [ ] `VALIDATION.md` exists at the project root.
- [ ] You can read the dimension-by-dimension grid and explain each result.
- [ ] You know at least two follow-up improvements (e.g., upgrade to 3B,
      expand date normalizer for ISO datetimes).
- [ ] You can re-run the validation: `rm -rf outputs && python -m extractor.cli --input samples --output outputs`.

---

## Done

You shipped a complete offline clinical data extraction pipeline:

```
offline-llm/
├── extractor/                       library
│   ├── model.py        prompts.py
│   ├── schema.py       extract.py
│   ├── cleanup.py      ingest.py
│   ├── pipeline.py     cli.py
├── samples/            8 synthetic notes (5 scored + 3 edge-case)
├── scripts/            per-phase demos
├── tests/              58 pytest tests
├── INSTRUCTIONS.md     this guide
├── EXTRACTOR_EXPLAINED.md
├── VALIDATION.md
├── PROGRESS.md
├── CLAUDE.md
├── README.md
└── requirements.txt
```

Open `EXTRACTOR_EXPLAINED.md` for the visual cheat sheet — every concept
from the 8 phases in one place.

---

## Want to keep going?

Open **`EXERCISES.md`** — per-phase improvisations (🟢 easy → 🔴 stretch),
plus three capstone challenges that pull multiple phases together.
