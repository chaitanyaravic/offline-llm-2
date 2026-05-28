"""High-level extraction entry points.

- `extract_text`  (Phase 2): free-text output from few-shot prompt.
- `extract_json`  (Phase 3): grammar-constrained JSON matching `EXTRACTION_SCHEMA`.
"""

import json

from llama_cpp import Llama

from extractor.prompts import build_messages, build_messages_json
from extractor.schema import EXTRACTION_SCHEMA


def extract_text(llm: Llama, note: str, max_tokens: int = 400, temperature: float = 0.0) -> str:
    """Run the model on a clinical note and return its text answer.

    Args:
        llm:         A loaded Llama instance from `extractor.model.load_model()`.
        note:        The clinical note text to extract from.
        max_tokens:  Hard cap on output length.
        temperature: 0.0 → deterministic (same input always gives same output).
                     Higher values add randomness; bad for extraction.
    """
    messages = build_messages(note)
    response = llm.create_chat_completion(
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return response["choices"][0]["message"]["content"]


def extract_json(
    llm: Llama,
    note: str,
    max_tokens: int = 600,
    temperature: float = 0.0,
) -> dict:
    """Extract a clinical note into a dict matching EXTRACTION_SCHEMA.

    Uses llama.cpp's grammar-constrained sampling so the model can ONLY emit
    tokens that produce valid JSON conforming to the schema.
    """
    messages = build_messages_json(note)
    response = llm.create_chat_completion(
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        response_format={
            "type": "json_object",
            "schema": EXTRACTION_SCHEMA,
        },
    )
    raw = response["choices"][0]["message"]["content"]
    return json.loads(raw)
