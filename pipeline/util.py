"""Shared I/O helpers for the pipeline."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterator


def read_csv_dicts(path: str | Path) -> Iterator[dict[str, str]]:
    """Yield each CSV data row as a dict keyed by its (stripped) header name.

    Handles:
    - UTF-8 BOM (utf-8-sig).
    - Header names containing embedded newlines/extra whitespace (NSE exports do
      this) — keys are whitespace-collapsed and stripped.
    - Values are stripped; missing trailing columns are treated as "".
    """
    path = Path(path)
    with path.open(newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return
        keys = [" ".join(h.split()).strip() for h in header]
        for row in reader:
            if not any(cell.strip() for cell in row):
                continue
            rec = {}
            for i, key in enumerate(keys):
                rec[key] = row[i].strip() if i < len(row) else ""
            yield rec


def col(rec: dict[str, str], *needles: str) -> str:
    """Return the value of the first column whose header contains all `needles`.

    Case-insensitive substring match. Lets parsers target columns by a few
    distinctive words instead of the exact (and inconsistently spaced) header
    text, so minor wording/spacing drift in future exports won't break parsing.
    Returns "" if no column matches.
    """
    nl = [n.lower() for n in needles]
    for key, value in rec.items():
        kl = key.lower()
        if all(n in kl for n in nl):
            return value
    return ""


def find_files(folder: str | Path, pattern: str) -> list[Path]:
    """Return all files matching a glob under a folder (sorted), or []."""
    folder = Path(folder)
    if not folder.exists():
        return []
    return sorted(p for p in folder.rglob(pattern) if p.is_file())


def find_csvs(folder: str | Path) -> list[Path]:
    """Return all .csv files under a folder (sorted), or [] if it doesn't exist."""
    return find_files(folder, "*.csv")
