# Diagrams

Mermaid source (`.mmd`) for the architecture and flow diagrams in this project.
These are the editable companions to the ASCII art in
[`../EXTRACTOR_EXPLAINED.md`](../EXTRACTOR_EXPLAINED.md) — change a diagram here
and re-render rather than hand-editing ASCII.

| File | Diagram | Ported from |
|------|---------|-------------|
| [`big-picture.mmd`](big-picture.mmd) | A note's full journey: read → chunk → extract → merge → clean → write | EXPLAINED §1 |
| [`module-dependencies.mmd`](module-dependencies.mmd) | One-way module dependency chain composed by `cli.py` | EXPLAINED §7 |
| [`chunk-merge.mmd`](chunk-merge.mmd) | Overlap chunking of long notes + the merge rules | EXPLAINED §6 |
| [`end-to-end-walkthrough.mmd`](end-to-end-walkthrough.mmd) | Sequence of `note1.txt` through every module | EXPLAINED §8 |
| [`grammar-constrained-sampling.mmd`](grammar-constrained-sampling.mmd) | How the JSON schema masks the sampler so invalid JSON is impossible | EXPLAINED §4, §10 |
| [`inference-pipeline.mmd`](inference-pipeline.mmd) | The per-token generation loop | EXPLAINED §10 |

## Rendering

These render automatically on GitHub inside a ` ```mermaid ` code fence, and in
any Mermaid-aware Markdown viewer. To render locally to SVG/PNG with the
Mermaid CLI:

```bash
npx @mermaid-js/mermaid-cli -i diagrams/big-picture.mmd -o diagrams/big-picture.svg
```

Or paste a file's contents into the live editor at <https://mermaid.live>.
