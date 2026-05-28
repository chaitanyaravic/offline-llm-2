"""Shared pytest fixtures."""

import sys
from pathlib import Path

# Make the `extractor` package importable in tests.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
