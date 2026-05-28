# Extractor — Visual Explainer

ASCII diagrams of every concept in the project, in the order you meet them
in `INSTRUCTIONS.md`. Open this file when something feels abstract.

---

## 1. Big picture

```
   ┌─────────────────┐    read    ┌─────────────┐  chunk   ┌───────────────┐
   │ clinical note   │───────────►│  full text  │─────────►│ overlapping   │
   │ .txt or .pdf    │            │  (str)      │  slide   │ chunks[]      │
   └─────────────────┘            └─────────────┘          └──────┬────────┘
                                                                   │ per chunk
                                                                   ▼
   ┌─────────────────┐  cleanup    ┌─────────────┐  merge   ┌───────────────┐
   │  final JSON     │◄───rules────│  merged     │◄─────────│ per-chunk     │
   │  (cleaned)      │ dates+routes│  JSON       │  union   │ JSON dicts    │
   └────────┬────────┘             └─────────────┘          └───────▲───────┘
            │                                                       │ grammar-
            │ write                                       extract   │ constrained
            ▼                                                       │ JSON
   ┌─────────────────┐                                   ┌──────────┴──────┐
   │ outputs/        │                                   │  Llama 3.2 1B   │
   │   *.json        │                                   │  (local GGUF,   │
   │   summary.csv   │                                   │   CPU-only)     │
   └─────────────────┘                                   └─────────────────┘
```

---

## 2. What "load a model" looks like (Phase 1)

```
 Llama-3.2-1B-Instruct-Q4_K_M.gguf            ≈ 770 MB on disk
                  │
                  │  Llama(model_path=..., n_ctx=2048)
                  ▼
       ┌────────────────────────┐
       │  Llama object in RAM   │
       │  ──────────────────    │   weights now live in ~1 GB of RAM
       │  weights (4-bit ints)  │   tokenizer + chat template included
       │  tokenizer             │
       │  chat template         │
       └────────────────────────┘
                  │
                  │  llm("The patient is a 67-year-old male with")
                  ▼
       "  hypertension and a history of smoking. He presents..."
```

---

## 3. Quantization, plain

```
 16-bit float weights  ─────►  4-bit integer weights
       (full precision)             (Q4_K_M format)

   ┌────────────────┐    JPEG       ┌──────────────────┐
   │  1.2 GB        │  the photo    │   ~770 MB        │
   │  perfect copy  │ ────────────► │   "good enough"  │
   │  slow on CPU   │               │   fast on CPU    │
   └────────────────┘               └──────────────────┘

   You trade a little quality for a lot of speed + smaller file.
```

---

## 4. Phase 2 vs Phase 3 — why JSON-mode matters

```
   Phase 2: free-text few-shot                     Phase 3: JSON schema
   ─────────────────────────────                   ─────────────────────

   ┌──────────────────────────┐                    ┌──────────────────────────┐
   │ Patient name: John Smith │                    │ {                        │
   │ MRN: 12345678            │                    │   "patient": {           │
   │ DOB: 03/15/1957          │                    │     "name": "John Smith",│
   │ Sex: M                   │                    │     "mrn": "12345678",   │
   │ Diagnoses:               │                    │     "dob": "03/15/1957", │
   │ - COPD exacerbation      │   ⇒  grammar  ⇒    │     "sex": "M"           │
   │ - Pneumonia              │                    │   },                     │
   │ HOSPITAL COURSE:         │ ← model rambled    │   "diagnoses": [...],    │
   │   Mr. Smith is a 69 yo...│   past the format  │   "medications": [...]   │
   └──────────────────────────┘                    │ }                        │
        ↑                                          └──────────────────────────┘
        Downstream code must                            ↑
        defend against any shape.                       json.loads() is safe.
                                                        Shape is guaranteed.
```

How grammar-constrained sampling works at every step:

```
   model thinks:   "next token could be { , } , : , string , number, ..."
                                                              │
   grammar says:   "given the schema and what's already        │
                    been generated, ONLY these tokens are       │
                    valid right now"                            │
                                                              ▼
   result:         illegal tokens get probability 0
                   → the model literally cannot break the schema.
```

---

## 5. Cleanup — LLM vs rules

```
   ┌────────────────────────────┬───────────────────────────────────────────────┐
   │  Use the LLM for…          │  Use rules/regex for…                         │
   ├────────────────────────────┼───────────────────────────────────────────────┤
   │  Reading natural language  │  Reformatting dates  03/15/1957 → 1957-03-15  │
   │  Deciding what IS a dx     │  Mapping "by mouth" → "PO"                    │
   │  Tying a med to its dose   │  Mapping "twice a day" → "BID"                │
   │  Inference + reasoning     │  Stripping suffix junk from a dose string     │
   └────────────────────────────┴───────────────────────────────────────────────┘

   Rules are cheap, deterministic, and testable.
   The LLM is reserved for the parts that need language understanding.
```

The 5 cleanup functions:

```
 normalize_date("03/15/1957")             ───►  "1957-03-15"
 normalize_route("by mouth")              ───►  "PO"
 normalize_frequency("at bedtime")        ───►  "QHS"
 normalize_dose("40 mg PO daily 5 days")  ───►  "40 mg"
 merge_modifier_diagnoses([
     "Hypertension", "well-controlled"])  ───►  ["Hypertension, well-controlled"]
```

---

## 6. Chunking with overlap (Phase 5)

```
   long note (say 13,000 chars):
   ──────────────────────────────────────────────────────────────────────────────
                                                                                   ↑
   max_chars = 5000, overlap_chars = 500                                            │
                                                                                    │ end
   chunk 1:   [────────────────────────────────────────────]                        │
              0                                          5000                        │
   chunk 2:                                    [────────────────────────────────]   │
                                              4500                              9500│
   chunk 3:                                                            [───────────]│
                                                                       9000     14000

   Why overlap?  A med line straddling 4998..5005 would be cut in half.
                 With 500-char overlap, every field appears whole in at least
                 one chunk.
```

Merging per-chunk extractions:

```
   chunk-1 JSON ─┐
   chunk-2 JSON ─┼──► merge_extractions ──► one JSON
   chunk-3 JSON ─┘                            ▲
                                              │
   Rules:                                     │
   • scalar field (name, mrn, dates) → first non-null wins
   • diagnoses                        → union, case-insensitive
   • medications                      → de-dupe by lowercased name
```

---

## 7. The dependency graph of the modules

```
   ┌──────────────┐
   │ cli.py       │  argparse + driver
   └──────┬───────┘
          │ calls
          ▼
   ┌──────────────┐      ┌──────────────┐
   │ pipeline.py  │─────►│ ingest.py    │  read + chunk + merge
   │              │      └──────────────┘
   │              │      ┌──────────────┐
   │              │─────►│ extract.py   │  extract_text / extract_json
   │              │      └──────┬───────┘
   │              │             │ uses
   │              │             ▼
   │              │      ┌──────────────┐    ┌──────────────┐
   │              │      │ prompts.py   │    │ schema.py    │
   │              │      └──────────────┘    └──────────────┘
   │              │      ┌──────────────┐
   │              │─────►│ cleanup.py   │  dates/units/routes/freq
   │              │      └──────────────┘
   │              │      ┌──────────────┐
   │              │─────►│ model.py     │  load_model / generate
   │              │      └──────────────┘
   └──────────────┘
```

---

## 8. End-to-end real-world walk-through — Note 1

```
  step                what happens                                  what we see
  ─────────────────── ──────────────────────────────────────────── ───────────────────────
  1. cli              user runs `python -m extractor.cli`           "Found 8 file(s)..."
  2. read_document    samples/note1.txt → str                       ~700 chars
  3. chunk_text       fits in one chunk                              len(chunks)==1
  4. load_model       opens GGUF, allocates RAM                      ~3 s first time
  5. extract_json     LLM produces grammar-constrained JSON          patient, dx, meds
  6. merge_extractions only one chunk → returns it unchanged         same dict
  7. clean_extraction  date → ISO, dx merged, doses stripped, etc.   final JSON
  8. write             outputs/note1.json + summary.csv row          on disk
```

---

## 9. Cheat sheet

| Concept                       | One-liner                                                              |
|-------------------------------|------------------------------------------------------------------------|
| GGUF                          | Single-file model format used by `llama.cpp`.                          |
| Quantization (Q4_K_M)         | 4-bit weights with k-quants, medium accuracy. ~4x smaller, ~4x faster. |
| `n_ctx`                       | Max tokens (prompt + output) the model holds in mind.                  |
| Instruct-tuned model          | Fine-tuned to *follow instructions* (different from raw GPT).          |
| Chat template                 | Special-token wrapping the model expects around each turn.             |
| Few-shot prompt               | Show 1-2 worked examples in the prompt.                                |
| `temperature=0`               | Deterministic sampling. What you want for extraction.                  |
| `response_format` JSON schema | Constrain the sampler so output MUST parse and MUST match the schema.  |
| Grammar-constrained sampling  | Illegal next-tokens get probability 0.                                 |
| Idempotency                   | Running cleanup twice = once. Safe to re-run anything.                 |
| Overlap chunking              | Sliding-window splits so fields don't get cut in half.                 |
| Pytest parametrize            | One test function, many `(input, expected)` rows.                      |
| Mocking the LLM               | Replace `Llama` with a `MagicMock` so unit tests run in milliseconds.  |

---

## 10. Core LLM concepts — explained plainly

### Tokens
A model doesn't read letters or words — it reads **tokens**. A token is roughly
a common word or word-fragment. "Hypertension" might be 1 token; "antihypertensive"
might be 3. Spaces, punctuation, and numbers are tokens too.

Why this matters here: `n_ctx=2048` means the model can hold 2048 tokens in
mind at once — not 2048 words, not 2048 characters. A clinical note of ~1500
characters is roughly 300–400 tokens, so it fits comfortably.

```
   "Patient: John Smith"  →  ["Patient", ":", " John", " Smith"]
                               token 1    2      3         4
```

### Context window (`n_ctx`)
The model has a fixed "working memory". Everything — the system prompt, the
few-shot example, and the real note — must fit inside it. If the total tokens
exceed `n_ctx`, the model truncates and loses part of the input silently.

That's why we chunk long notes: each chunk is small enough to fit, and we merge
the results afterwards.

### Weights / parameters
A neural network is just a huge table of numbers (weights). During training,
billions of examples adjust these numbers until the network can predict language
well. At inference time (our use case), the weights are **frozen** — we just
load them and run forward passes.

The 1B in "Llama 3.2 1B" means 1 billion weights.

### Training vs inference
- **Training** — feeding vast text into the model and adjusting weights.
  Done by Meta. We never do this.
- **Inference** — loading frozen weights and generating output for a given input.
  Everything this project does is inference.

### Base model vs instruct-tuned model
A **base model** just predicts "what token comes next?" given any text. If you
give it a clinical note it might continue it like a story rather than extract
from it.

An **instruct-tuned** model has been further trained to follow instructions
("Extract the patient name from the note below"). The `Instruct` in the filename
tells you this model has been fine-tuned that way. That's why our prompts work.

### Chat template
Instruct-tuned models expect their input wrapped in special tokens:

```
<|system|> You are a clinical assistant… <|end|>
<|user|>   Clinical note: … <|end|>
<|assistant|>
```

When we call `llm.create_chat_completion(messages=[...])`, llama-cpp applies
the correct template automatically from the model file. We never write these
tokens ourselves.

### Few-shot prompting
Instead of just giving the model instructions, we also show it one worked
example (input → expected output) inside the prompt itself. The model picks up
the pattern and applies it to the real input.

```
   system:    "Extract fields from clinical notes."
   user:      [example note]        ← the worked example
   assistant: [example output]      ← what good output looks like
   user:      [real note]           ← now do this one
```

One example is "one-shot". More examples = more tokens used, but better
consistency. This project uses one example (one-shot).

### Temperature
Controls how random the model's token choices are.

```
   temperature = 0.0  →  always pick the single most likely token  (deterministic)
   temperature = 0.7  →  sample from the top likely tokens          (creative)
   temperature = 1.0  →  fully random according to the distribution
```

For data extraction you always want `0` — the same note should always produce
the same output. Randomness is the enemy of a reliable pipeline.

### Quantization
Full-precision (32-bit or 16-bit float) weights give the model perfect numerical
accuracy but are large and slow on CPU. Quantization rounds each weight down to
fewer bits.

```
   32-bit float  →  4.7 GB model,  exact numbers
    4-bit int    →  ~770 MB model,  only 16 possible values per weight
```

The quality loss is real but small for extraction tasks. `Q4_K_M` = 4-bit
k-quants, medium quality variant. Higher letter (e.g. `Q8`) = better quality,
bigger file.

### GGUF file format
GGUF is a single-file format that bundles the model weights **and** the
tokenizer and chat template into one file. `llama.cpp` (and `llama-cpp-python`)
loads GGUF directly. Before GGUF, you needed separate tokenizer files and config
files — GGUF simplified that.

### Grammar-constrained sampling
Normally the model assigns a probability to every token in its vocabulary at
each step. Grammar constraints intersect those probabilities with what the
grammar (derived from the JSON schema) allows right now.

```
   vocabulary:  { , } " : [ ] null true false 0-9 a-z …  (50k+ tokens)
   grammar:     at this point only " or } are valid
   result:      all other tokens get probability = 0
                → the model CANNOT produce invalid JSON
```

This is enforced mathematically inside the sampler, not by post-processing.

### Inference pipeline (what happens per token)
Each generated token involves:
1. Tokenize input
2. Run input through all model layers (the forward pass) → get logits (raw scores for each vocabulary token)
3. Apply temperature, grammar mask
4. Sample the next token
5. Append it to the output and repeat until `max_tokens` or the stop token

For a 1B model on CPU, one forward pass takes ~50–200 ms. A 600-token response
= ~60 forward passes = several seconds. That's why a single note takes 5–15 s.

---

## 11. Interview prep

These are the questions most likely to come up if you explain this project.

---

**Q: Why run a model locally instead of calling the OpenAI API?**

The notes contain PHI (patient health information). Sending them to a third-party
API would be a HIPAA violation. Running locally means data never leaves the
machine.

---

**Q: What is quantization and what do you trade away?**

Quantization reduces weight precision from 32/16-bit floats to 4-bit integers.
You trade a small amount of model quality for roughly 4× smaller file size and
4× faster CPU inference. For extraction tasks — where the model mostly needs to
copy structured fields from text — the quality loss is negligible.

---

**Q: What is a context window and why does it force you to chunk?**

The context window (`n_ctx`) is the maximum number of tokens the model can
process in one call. We load with `n_ctx=2048` for speed. If a clinical note
exceeds that budget, we split it into overlapping chunks and run the model once
per chunk. The overlap prevents a field straddling a chunk boundary from being
cut in half.

---

**Q: Why overlapping chunks instead of just splitting evenly?**

A sentence or medication line that lands exactly at a chunk boundary would be
split across two chunks, and neither chunk would see the complete field. Overlap
(400 chars here) ensures every piece of text appears whole in at least one
chunk.

---

**Q: How do you guarantee the model always returns valid JSON?**

We pass `response_format={"type":"json_object","schema":EXTRACTION_SCHEMA}` to
`create_chat_completion`. llama-cpp converts the JSON Schema into a GBNF grammar
and applies it as a mask on the token sampler at every step. Tokens that would
produce invalid JSON are given probability zero — the model is mathematically
prevented from breaking the schema.

---

**Q: Why not let the LLM normalize dates and routes too?**

Rule-based normalization (regex, lookup tables) is deterministic, cheap, and
testable. The LLM output varies slightly with phrasing and can hallucinate. For
a transformation as simple as `"by mouth" → "PO"` or `"03/15/1957" → "1957-03-15"`,
a lookup table is strictly better. We use the LLM only where language
understanding is actually needed.

---

**Q: How do you test code that depends on an LLM without loading the model?**

We replace the `Llama` object with a `unittest.mock.MagicMock` that returns
canned JSON from `create_chat_completion`. The full pipeline (ingest → extract →
merge → clean) runs against this fake LLM in milliseconds. The grammar constraint
and model inference are the only things not tested this way — those are covered
by end-to-end runs documented in `VALIDATION.md`.

---

**Q: What is temperature=0 and why is it important for extraction?**

Temperature controls sampling randomness. At 0, the model always picks the
highest-probability next token — the output is fully deterministic. For a
production data pipeline, the same input must always produce the same output.
Any randomness makes the pipeline unreliable and hard to debug.

---

**Q: What is few-shot prompting?**

Instead of just instructing the model, you show it one (or more) complete
examples of input → expected output inside the prompt. The model learns the
pattern from the example and applies it to the real input. It requires no
fine-tuning — the learning happens entirely inside the context window.

---

**Q: What would you do if the model's accuracy on a field was too low?**

Options in rough order of effort:
1. Improve the few-shot example (more representative note)
2. Add more few-shot examples
3. Add field-specific instructions to the system prompt
4. Try a larger model (3B instead of 1B)
5. Fine-tune on labeled examples (big lift; last resort)
