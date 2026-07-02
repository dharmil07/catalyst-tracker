"""Download NSE preferential-issue filings via the exchange's JSON API.

Source page: https://www.nseindia.com/companies-listing/corporate-filings-PREF
API:         https://www.nseindia.com/api/corporate-further-issues-pref

NSE's API sits behind bot protection that requires browser-like headers and the
session cookies handed out by a normal page load, so the fetch is two steps:
warm up on the HTML page to collect cookies, then call the API with them. The
date window filters on listing/approval date, DD-MM-YYYY.

The response is saved verbatim (plus a small _fetched envelope) under
data/raw/preferential/nse/, where ingest picks it up. Files accumulate like the
CSV drops do; overlapping windows are fine because ingest dedupes on appId.

Usage:
    python3 pipeline/fetch_nse_pref.py                # trailing 180 days
    python3 pipeline/fetch_nse_pref.py --days 365
    python3 pipeline/fetch_nse_pref.py --from 01-01-2026 --to 02-07-2026
"""
from __future__ import annotations

import argparse
import gzip
import http.cookiejar
import json
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw" / "preferential" / "nse"

PAGE_URL = "https://www.nseindia.com/companies-listing/corporate-filings-PREF"
API_URL = "https://www.nseindia.com/api/corporate-further-issues-pref"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def _opener() -> urllib.request.OpenerDirector:
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def _get(opener, url: str, *, accept: str, referer: str | None = None) -> bytes:
    headers = {
        "User-Agent": UA,
        "Accept": accept,
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip",
    }
    if referer:
        headers["Referer"] = referer
    with opener.open(urllib.request.Request(url, headers=headers), timeout=30) as resp:
        body = resp.read()
        if resp.headers.get("Content-Encoding") == "gzip":
            body = gzip.decompress(body)
        return body


def fetch(from_date: str, to_date: str) -> dict:
    """Fetch preferential-issue filings for a DD-MM-YYYY window -> API payload."""
    opener = _opener()
    _get(opener, PAGE_URL, accept="text/html,application/xhtml+xml")  # cookies
    query = urllib.parse.urlencode(
        {"index": "FIPREF", "from_date": from_date, "to_date": to_date})
    body = _get(opener, f"{API_URL}?{query}", accept="application/json",
                referer=PAGE_URL)
    payload = json.loads(body)
    if "data" not in payload or not isinstance(payload["data"], list):
        raise RuntimeError(f"Unexpected API response shape: {str(payload)[:200]}")
    return payload


def save(payload: dict, from_date: str, to_date: str) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out = RAW_DIR / f"NSE_PREF_{from_date}_to_{to_date}.json"
    payload["_fetched"] = {
        "at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "from_date": from_date,
        "to_date": to_date,
        "url": API_URL,
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--days", type=int, default=180,
                    help="trailing window in days (default 180)")
    ap.add_argument("--from", dest="from_date", metavar="DD-MM-YYYY",
                    help="explicit window start (overrides --days)")
    ap.add_argument("--to", dest="to_date", metavar="DD-MM-YYYY",
                    help="explicit window end (default today)")
    args = ap.parse_args(argv)

    today = date.today()
    to_date = args.to_date or today.strftime("%d-%m-%Y")
    from_date = args.from_date or (today - timedelta(days=args.days)).strftime("%d-%m-%Y")

    print(f"Fetching NSE preferential issues {from_date} → {to_date} …")
    try:
        payload = fetch(from_date, to_date)
    except Exception as e:  # noqa: BLE001 — always explain, exchange APIs are moody
        print(f"Fetch failed: {e}\n"
              "NSE sometimes blocks non-browser clients; retry in a minute, or "
              "download the page's export manually into data/raw/preferential/nse/.",
              file=sys.stderr)
        return 1
    out = save(payload, from_date, to_date)
    print(f"✓ {len(payload['data'])} filings → {out.relative_to(ROOT)}")
    print("Run  python3 pipeline/ingest.py  (or ./update.sh) to rebuild the site data.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
