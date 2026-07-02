"""Catalyst Tracker ingestion entry point.

Reads the raw exchange CSVs under data/raw/, runs the full normalize -> sanitize
-> dedup -> cross-feed-merge pipeline, and writes the JSON that the static site
loads from docs/data/.

Usage:  python3 pipeline/ingest.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from . import aggregate, match, normalize as nz, sanitize
from .parsers import bse_corpactions, bse_insider, nse_insider, nse_pref
from .util import find_csvs, find_files

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "docs" / "data"


def _parse_all(folder: Path, parser) -> list[dict]:
    records: list[dict] = []
    for csv_path in find_csvs(folder):
        records.extend(parser(csv_path))
    return records


def run() -> dict:
    nz.reset_unmapped()

    bse = _parse_all(RAW / "insider" / "bse", bse_insider.parse)
    nse = _parse_all(RAW / "insider" / "nse", nse_insider.parse)
    corp = _parse_all(RAW / "corporate_actions" / "bse", bse_corpactions.parse)
    pref, pref_raw = _load_preferential()
    raw_counts = {"bse": len(bse), "nse": len(nse), "corp": len(corp),
                  "pref": pref_raw}

    # Sanitize values across the combined pool so twin-repair can borrow a sane
    # value from either feed before any rows are collapsed.
    value_stats = sanitize.sanitize(bse + nse)

    bse, bse_dedup = match.dedupe_within_source(bse)
    nse, nse_dedup = match.dedupe_within_source(nse)
    insider, merge_stats = match.merge_cross_feed(bse, nse)

    for i, rec in enumerate(insider):
        rec["id"] = i

    meta = aggregate.build_meta(
        insider=insider, corp=corp, pref=pref, raw_counts=raw_counts,
        dedup={"bse": bse_dedup, "nse": nse_dedup}, merge=merge_stats,
        value_stats=value_stats, unmapped=nz.unmapped(),
    )

    OUT.mkdir(parents=True, exist_ok=True)
    _write(OUT / "insider.json", insider)
    _write(OUT / "corporate_actions.json", corp)
    _write(OUT / "preferential.json", pref)
    # Scaffolded category — empty until the user supplies exports.
    _write(OUT / "open_offers.json", [])
    _write(OUT / "meta.json", meta)

    return meta


def _load_preferential() -> tuple[list[dict], int]:
    """Parse all fetched NSE PREF payloads, dedupe on appId across files.

    Overlapping fetch windows produce identical filings in multiple files; the
    last-parsed copy wins (files sort by name, so the newest window prevails
    for any filing whose stage advanced between fetches).
    """
    by_id: dict[str, dict] = {}
    raw = 0
    for path in find_files(RAW / "preferential" / "nse", "*.json"):
        for rec in nse_pref.parse(path):
            raw += 1
            by_id[rec["app_id"] or f"noid-{raw}"] = rec
    records = sorted(by_id.values(),
                     key=lambda r: (r["date_allotment"] or "", r["company"]),
                     reverse=True)
    for i, rec in enumerate(records):
        rec["id"] = i
    return records, raw


def _write(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")),
                    encoding="utf-8")


def _print_summary(meta: dict) -> None:
    ins = meta["insider"]
    print("Catalyst Tracker ingest complete")
    print(f"  Insider records:      {ins['records']}  {ins['by_source']}")
    print(f"  Within-BSE collapsed: {ins['within_bse']}")
    print(f"  Cross-feed:           {ins['cross_feed']}")
    print(f"  Value status:         {ins['value_status']}")
    print(f"  Insider date range:   {ins['transaction_dates']}")
    ca = meta["corporate_actions"]
    print(f"  Corp actions:         {ca['records']}  {ca['buckets']}")
    pf = meta["preferential"]
    print(f"  Preferential issues:  {pf['records']}  "
          f"(₹{pf['issue_size_total'] / 1e7:,.0f} cr, "
          f"amounts {pf['amount_status']})")
    if meta["warnings"]:
        print(f"  WARNINGS:             {meta['warnings']}")


if __name__ == "__main__":
    meta = run()
    _print_summary(meta)
    if meta["warnings"]:
        # Unmapped vocabulary won't break the build but should be addressed.
        print("\nNote: unmapped values fell back to OTHER; extend the maps in "
              "pipeline/normalize.py to classify them.", file=sys.stderr)
