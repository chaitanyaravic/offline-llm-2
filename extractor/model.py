"""Phase 1: minimal wrapper around llama-cpp-python.

Goal: load a GGUF model from disk and produce ONE text completion.
Nothing else yet. No chat templates, no extraction, no JSON.
"""

from pathlib import Path

from llama_cpp import Llama


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL_PATH = PROJECT_ROOT / "models" / "Llama-3.2-1B-Instruct-Q4_K_M.gguf"


def load_model(
    model_path: str | Path = DEFAULT_MODEL_PATH,
    n_ctx: int = 2048,
    verbose: bool = False,
) -> Llama:
    """Load a GGUF model file into memory and return a ready-to-use Llama instance.

    Args:
        model_path: Path to the .gguf file on disk.
        n_ctx:      Maximum context window in tokens. 2048 is plenty for Phase 1.
        verbose:    If True, llama.cpp prints loading details to stderr.
    """
    path = Path(model_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Model file not found: {path}\n"
            f"Download it first (see INSTRUCTIONS.md, Phase 1, Step 1.3)."
        )
    return Llama(
        model_path=str(path),
        n_ctx=n_ctx,
        verbose=verbose,
    )


def generate(llm: Llama, prompt: str, max_tokens: int = 64) -> str:
    """Generate a continuation for `prompt`. Returns only the new text."""
    result = llm(prompt, max_tokens=max_tokens)
    return result["choices"][0]["text"]
