"""Batch CLI: process a file or folder of clinical notes.

Run from the project root with the venv activated:

    python -m extractor.cli --input samples --output outputs
    python -m extractor.cli --input samples/note1.txt --output outputs

Produces:
    outputs/<note-stem>.json    ← per-file structured extraction
    outputs/summary.csv         ← one row per processed file
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from extractor.model import load_model
from extractor.pipeline import extract_from_file


SUPPORTED_EXTS = {".txt", ".md", ".pdf"}


def iter_inputs(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(p for p in path.rglob("*") if p.suffix.lower() in SUPPORTED_EXTS)


def write_outputs(output_dir: Path, stem: str, data: dict) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{stem}.json"
    out_path.write_text(json.dumps(data, indent=2))
    return out_path


def summary_row(source: Path, data: dict) -> dict:
    patient = data.get("patient") or {}
    return {
        "source_file": str(source),
        "patient_name": patient.get("name") or "",
        "mrn": patient.get("mrn") or "",
        "dob": patient.get("dob") or "",
        "sex": patient.get("sex") or "",
        "admit_date": (data.get("encounter") or {}).get("admit_date") or "",
        "discharge_date": (data.get("encounter") or {}).get("discharge_date") or "",
        "num_diagnoses": len(data.get("diagnoses") or []),
        "num_medications": len(data.get("medications") or []),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="extractor",
        description="Extract structured clinical data from .txt / .pdf files using a local LLM.",
    )
    p.add_argument("--input", "-i", required=True, type=Path,
                   help="Path to a file OR a folder containing notes.")
    p.add_argument("--output", "-o", default=Path("outputs"), type=Path,
                   help="Folder to write JSON results + summary.csv. Default: outputs/")
    p.add_argument("--model", default=None, type=Path,
                   help="Optional path to a different GGUF file.")
    p.add_argument("--n-ctx", default=2048, type=int,
                   help="Model context window. Increase for very long notes.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    inputs = iter_inputs(args.input)
    if not inputs:
        print(f"No supported files (.txt/.md/.pdf) found in {args.input}", file=sys.stderr)
        return 1

    print(f"Found {len(inputs)} file(s) to process.")
    llm = load_model(model_path=args.model) if args.model else load_model(n_ctx=args.n_ctx)

    summary_rows: list[dict] = []
    for i, path in enumerate(inputs, 1):
        print(f"[{i}/{len(inputs)}] {path}")
        try:
            data = extract_from_file(llm, path)
        except Exception as exc:
            print(f"  FAILED: {exc}", file=sys.stderr)
            continue
        out_path = write_outputs(args.output, path.stem, data)
        print(f"  -> {out_path}")
        summary_rows.append(summary_row(path, data))

    if summary_rows:
        summary_path = args.output / "summary.csv"
        with summary_path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
            writer.writeheader()
            writer.writerows(summary_rows)
        print(f"\nSummary: {summary_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
