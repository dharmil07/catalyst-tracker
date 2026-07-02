"""Parse NSE preferential-issue API payloads into canonical records.

Input files are the raw JSON saved by pipeline/fetch_nse_pref.py (the API
response verbatim). Unlike the insider feeds this is a per-filing dataset with
a stable unique id (appId), so cross-file dedup is a simple key lookup — done
in ingest, not here, because it spans files.

Value sanitization (same spirit as the insider feed, different failure mode):
`amountRaised` is filer-entered and in ~10% of real filings is inflated by a
clean 10^4–10^5 factor (amounts typed in lakhs). `shares × offer price` is
computed from listing-verified fields, so that product is the canonical
`issue_size`. amountRaised legitimately sits BELOW issue_size for partly-paid
warrants (25%/10% upfront), so only amounts materially ABOVE the product are
treated as errors and repaired to the product.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

from .. import normalize as nz


def _value_fields(price, shares, amount) -> dict:
    issue_size = price * shares if price and shares else None
    if issue_size:
        if not amount:
            status, amount = "novalue", None
        elif amount > issue_size * 1.05:
            status, amount = "repaired", issue_size
        elif amount < issue_size * 0.95:
            status = "partial"  # partly-paid warrants: upfront money only
        else:
            status = "ok"
    else:
        # No cross-check possible; a bare amountRaised can't be trusted enough
        # to total, so it is display-only.
        issue_size = None
        status = "unverified" if amount else "novalue"
    return {"issue_size": issue_size, "amount_raised": amount,
            "amount_status": status}


def parse(path: str | Path) -> Iterator[dict]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    for r in payload.get("data", []):
        company = (r.get("nameOfTheCompany") or "").strip()
        price = nz.parse_num(r.get("offerPricePerSecurity"))
        shares = nz.parse_num(r.get("totalNumOfSharesAllotted"))
        amount = nz.parse_num(r.get("amountRaised"))
        yield {
            "source": "NSE",
            "app_id": str(r.get("appId") or ""),
            "company": company,
            "company_norm": nz.normco(company),
            "symbol": (r.get("nseSymbol") or "").strip(),
            "isin": (r.get("isin") or "").strip(),
            "issue_type": (r.get("issueType") or "").strip(),
            "stage": (r.get("stage") or "").strip(),
            "offer_price": price,
            "shares_allotted": shares,
            **_value_fields(price, shares, amount),
            "date_board_res": nz.iso(nz.parse_date(r.get("boardResDate") or "")),
            "date_allotment": nz.iso(nz.parse_date(r.get("dateOfAllotmentOfShares") or "")),
            "date_submission": nz.iso(nz.parse_date(r.get("dateOfSubmission") or "")),
            "date_listing": nz.iso(nz.parse_date(r.get("dateOfListing") or "")),
            "xbrl": (r.get("xmlFileName") or "").strip(),
        }
