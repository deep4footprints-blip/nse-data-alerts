#!/usr/bin/env python3
"""Capture raw NSE corporate actions (equities) as JSON, in 180-day chunks."""
import datetime as dt
import json
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "corp_actions_raw.json"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-actions",
}


def main():
    s = requests.Session()
    s.headers.update(HEADERS)
    for u in ("https://www.nseindia.com",
              "https://www.nseindia.com/companies-listing/corporate-filings-actions"):
        s.get(u, timeout=20)  # cookie warm-up

    today = dt.date.today()
    cur = today - dt.timedelta(days=int(11.3 * 365))
    end = today + dt.timedelta(days=60)
    seen, rows = set(), []
    while cur < end:
        nxt = min(cur + dt.timedelta(days=180), end)
        url = ("https://www.nseindia.com/api/corporates-corporateActions?index=equities"
               f"&from_date={cur:%d-%m-%Y}&to_date={nxt:%d-%m-%Y}")
        for i in range(4):
            r = s.get(url, timeout=40)
            if r.status_code == 200:
                break
            time.sleep(3 * (i + 1))
        else:
            raise SystemExit(f"FAIL {url} -> HTTP {r.status_code}: {r.text[:200]!r}")
        data = r.json()
        data = data if isinstance(data, list) else data.get("data", [])
        new = 0
        for row in data:
            k = json.dumps(row, sort_keys=True)
            if k not in seen:
                seen.add(k)
                rows.append(row)
                new += 1
        print(f"{cur} -> {nxt}: {len(data)} rows, {new} new")
        cur = nxt + dt.timedelta(days=1)
        time.sleep(1.5)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, indent=0))
    print(f"Saved {len(rows)} actions -> {OUT}")


if __name__ == "__main__":
    main()
