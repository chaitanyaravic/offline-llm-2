"""Phase 1 demo: load the model and print one generated continuation.

Run from the project root with the venv activated:

    python scripts/phase1_hello.py
"""

import sys
from pathlib import Path

# Make `extractor` importable when this script is run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from extractor.model import generate, load_model


def main() -> None:
    print("Loading model... (first load may take a few seconds)")
    llm = load_model()
    print("Model loaded.\n")

    prompt = "The patient is a 67-year-old male with"
    print(f"PROMPT:     {prompt!r}")

    completion = generate(llm, prompt, max_tokens=40)
    print(f"COMPLETION: {completion!r}")


if __name__ == "__main__":
    main()
