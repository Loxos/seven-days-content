"""Entrypoint: `python -m sevendays` runs one morning."""
from __future__ import annotations

import sys

from .engine import run

if __name__ == "__main__":
    sys.exit(run())
