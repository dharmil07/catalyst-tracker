"""Fetch BSE corporate actions from BSE's API and write them as a CSV in the
exact column format pipeline/parsers/bse_corpactions.py expects.

BSE's DefaultData endpoint returns structured corporate actions (dividends, 
bonus, splits, buybacks, mergers, etc.) with no cookies or session required.

Usage:  python3 pipeline/fetch_bse_corpactions.py
        (or via ./update.sh --fetch, once wired in)
"""
from __future__ import annotations

import csv
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "raw" / "corporate_actions" / "bse"

BSE_URL = (
    "https://api.bseindia.com/BseIndiaAPI/api/DefaultData/w"
    "?scripcode=&Fdate=&Purposecode=&TDate=&ddlcategorys=E&ddlindustrys=&segment=0&strSearch=D"
)

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.bseindia.com/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
    ),
}

# CSV columns, in the exact names pipeline/parsers/bse_corpactions.py expects.
# Each maps to one field from BSE's JSON or a fixed default.
FIELDS = [
    "Company Name",
    "Security Code",
    "Security Name",
    "Ex Date",
    "Record Date",
    "BC Start",
    "BC End",
    "ND Start",
    "ND End",
    "Actual Payment",
    "Purpose",
]


def _fmt_date(raw: str | None) -> str:
    """'21 Jul 2026' is already in correct format, pass through as-is.
    If it's empty or None, return ''."""
    if not raw:
        return ""
    return raw.strip()


def _fetch(max_retries: int = 3) -> list[dict]:
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(BSE_URL, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            # BSE returns either a dict with "Table" key or a list directly
            if isinstance(data, dict):
                records = data.get("Table", [])
            else:
                records = data if isinstance(data, list) else []
            if not records:
                print("⚠ BSE returned zero corporate action records — page may be "
                      "empty today, or the response shape changed. Not writing a file.")
            return records
        except (requests.RequestException, ValueError) as e:
            last_err = e
            print(f"  attempt {attempt}/{max_retries} failed: {e}")
            if attempt < max_retries:
                time.sleep(2 * attempt)
    print(f"✗ BSE corporate actions fetch failed after {max_retries} attempts: {last_err}")
    return []


def _to_row(r: dict) -> dict:
    """Map BSE's JSON fields to CSV columns the parser expects."""
    return {
        "Company Name": r.get("long_name", ""),
        "Security Code": r.get("scrip_code", ""),
        "Security Name": r.get("short_name", ""),
        "Ex Date": _fmt_date(r.get("Ex_date", "")),
        "Record Date": _fmt_date(r.get("RD_Date", "")),
        "BC Start": _fmt_date(r.get("BCRD_FROM", "")),
        "BC End": _fmt_date(r.get("BCRD_TO", "")),
        "ND Start": _fmt_date(r.get("ND_START_DATE", "")),
        "ND End": _fmt_date(r.get("ND_END_DATE", "")),
        "Actual Payment": _fmt_date(r.get("payment_date", "")),
        "Purpose": r.get("Purpose", ""),
    }


def main() -> int:
    print("▶ Fetching BSE corporate actions")
    records = _fetch()
    if not records:
        # Not a hard failure — update.sh's git-status check means "no new
        # file" just results in "no changes to commit", same as any other
        # day with nothing new.
        return 0

    dates = sorted(r.get("Ex_date", "") for r in records if r.get("Ex_date"))
    span = f"{dates[0].replace(' ', '-')}_to_{dates[-1].replace(' ', '-')}" if dates else datetime.now().strftime("%Y-%m-%d")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"BSE_CORPACTIONS_{span}.csv"

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for r in records:
            writer.writerow(_to_row(r))

    print(f"✓ Wrote {len(records)} records → {out_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
