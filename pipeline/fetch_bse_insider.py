"""Fetch BSE insider-trading (SEBI PIT) disclosures from BSE's API and write
them as a CSV in the exact column format pipeline/parsers/bse_insider.py
already expects — so no changes to the parser or ingest pipeline are needed.

BSE's endpoint returns a rolling window (observed: ~104 days) when called with
Isdefault=1 and blank filters. No cookies or session are required — just a
browser-like User-Agent, Referer, and Accept header.

Usage:  python3 pipeline/fetch_bse_insider.py
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
OUT_DIR = ROOT / "data" / "raw" / "insider" / "bse"

BSE_URL = (
    "https://api.bseindia.com/BseIndiaAPI/api/getCorp_Regulation_ng/w"
    "?scripCode=&Regulation=&fromDT=&ToDate=&Isdefault=1"
)

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.bseindia.com/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
    ),
}

# CSV columns, in the exact names pipeline/parsers/bse_insider.py's col()
# lookups expect. Each maps to one field (or a fixed default) from BSE's JSON.
FIELDS = [
    "Security Code",
    "Security Name",
    "Name of Person",
    "Category of person",
    "Transaction Type",
    "Mode of Acquisition",
    "Type of Securities Acquired",
    "Number of Securities Acquired",
    "Value of Securities Acquired",
    "Number of Securities held Prior",
    "% of Securities held Prior",
    "Number of Securities held Post",
    "Post-Transaction % of Shareholding",
    "From date",
    "To date",
    "Date of Intimation",
    "Exchange on which",
]


def _fmt_date(raw: str | None) -> str:
    """'2026-06-30T00:00:00' -> '30 Jun 2026' (a format normalize.parse_date
    already handles). Empty/None passes through as ''."""
    if not raw:
        return ""
    try:
        return datetime.strptime(raw.split("T")[0], "%Y-%m-%d").strftime("%d %b %Y")
    except ValueError:
        return ""


def _fetch(max_retries: int = 3) -> list[dict]:
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(BSE_URL, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            records = data.get("Table", [])
            if not records:
                print("⚠ BSE returned zero records — page may be empty today, "
                      "or the response shape changed. Not writing a file.")
            return records
        except (requests.RequestException, ValueError) as e:
            last_err = e
            print(f"  attempt {attempt}/{max_retries} failed: {e}")
            if attempt < max_retries:
                time.sleep(2 * attempt)
    print(f"✗ BSE insider fetch failed after {max_retries} attempts: {last_err}")
    return []


def _to_row(r: dict) -> dict:
    return {
        "Security Code": r.get("Fld_ScripCode", ""),
        "Security Name": r.get("Companyname", ""),
        "Name of Person": r.get("Fld_PromoterName", ""),
        "Category of person": r.get("Fld_PersonCatgName", ""),
        "Transaction Type": r.get("Fld_TransactionType", ""),
        "Mode of Acquisition": r.get("ModeOfAquisation", ""),
        "Type of Securities Acquired": r.get("Fld_SecurityTypeName", ""),
        "Number of Securities Acquired": r.get("Fld_SecurityNo", ""),
        "Value of Securities Acquired": r.get("Fld_SecurityValue", ""),
        "Number of Securities held Prior": r.get("Fld_SecurityNoPrior", ""),
        "% of Securities held Prior": r.get("Fld_PercentofShareholdingPre", ""),
        "Number of Securities held Post": r.get("Fld_SecurityNoPost", ""),
        "Post-Transaction % of Shareholding": r.get("Fld_PercentofShareholdingPost", ""),
        "From date": _fmt_date(r.get("Fld_FromDate")),
        "To date": _fmt_date(r.get("Fld_ToDate")),
        "Date of Intimation": _fmt_date(r.get("Fld_DateIntimation")),
        "Exchange on which": r.get("Fld_TradeExchange", ""),
    }


def main() -> int:
    print("▶ Fetching BSE insider trading disclosures")
    records = _fetch()
    if not records:
        # Not a hard failure — update.sh's git-status check means "no new
        # file" just results in "no changes to commit", same as any other
        # day with nothing new.
        return 0

    dates = sorted(r.get("Fld_DateIntimation", "") for r in records if r.get("Fld_DateIntimation"))
    span = f"{dates[0][:10]}_to_{dates[-1][:10]}" if dates else datetime.now().strftime("%Y-%m-%d")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"BSE_INSIDER_{span}.csv"

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for r in records:
            writer.writerow(_to_row(r))

    print(f"✓ Wrote {len(records)} records → {out_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
