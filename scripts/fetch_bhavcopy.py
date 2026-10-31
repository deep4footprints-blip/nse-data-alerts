#!/usr/bin/env python3
"""Backfill + daily update of NSE equity bhavcopy (EQ/BE series), one parquet per trading day.
Idempotent and resumable: skips days already stored or known to be holidays."""
import argparse
import datetime as dt
import io
import sys
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
DAILY = ROOT / "data" / "daily"
UNIV = ROOT / "data" / "universe"
HOLIDAYS = ROOT / "data" / "holidays.txt"

DAY_URL = "https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{d:%d%m%Y}.csv"
UNIV_URL = "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "text/csv,application/octet-stream,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/all-reports",
}
KEEP_SERIES = {"EQ", "BE"}
RENAME = {
    "SYMBOL": "symbol", "SERIES": "series", "DATE1": "date", "PREV_CLOSE": "prev_close",
    "OPEN_PRICE": "open", "HIGH_PRICE": "high", "LOW_PRICE": "low", "CLOSE_PRICE": "close",
    "TTL_TRD_QNTY": "volume", "TURNOVER_LACS": "turnover_lacs", "NO_OF_TRADES": "trades",
    "DELIV_QTY": "deliv_qty", "DELIV_PER": "deliv_pct",
}
NUMERIC = [k for k in RENAME if k not in ("SYMBOL", "SERIES", "DATE1")]


def get(session, url, tries=4):
    """Return Response on 200, None on 404, raise after repeated failures (e.g. 403 block)."""
    err = ""
    for i in range(tries):
        try:
            r = session.get(url, timeout=30)
        except requests.RequestException as e:
            err = str(e)
        else:
            if r.status_code == 200:
                return r
            if r.status_code == 404:
                return None
            err = f"HTTP {r.status_code}"
        time.sleep(3 * (i + 1))
    raise RuntimeError(f"{url} -> {err}")


def parse_day(text, d):
    df = pd.read_csv(io.StringIO(text), skipinitialspace=True)
    df.columns = [c.strip() for c in df.columns]
    for c in ("SYMBOL", "SERIES"):
        df[c] = df[c].astype(str).str.strip()
    df = df[df["SERIES"].isin(KEEP_SERIES)].copy()
    df["DATE1"] = pd.to_datetime(df["DATE1"].astype(str).str.strip(), format="%d-%b-%Y", errors="coerce")
    for c in NUMERIC:
        df[c] = pd.to_numeric(df[c].astype(str).str.strip(), errors="coerce")
    out = df.rename(columns=RENAME)[list(RENAME.values())].reset_index(drop=True)
    out["date"] = out["date"].dt.date
    if len(out) < 500 or set(out["date"]) != {d}:
        return None  # stale / wrong-date / partial file: treat as not available
    return out


def snapshot_universe(session, today):
    r = get(session, UNIV_URL)
    if r is None:
        print("WARN: Nifty 500 list not found")
        return
    df = pd.read_csv(io.StringIO(r.text))
    syms = set(df["Symbol"].astype(str).str.strip())
    UNIV.mkdir(parents=True, exist_ok=True)
    snaps = sorted(UNIV.glob("nifty500_*.csv"))
    if snaps and set(pd.read_csv(snaps[-1])["Symbol"].astype(str).str.strip()) == syms:
        return
    df.to_csv(UNIV / f"nifty500_{today:%Y-%m-%d}.csv", index=False)
    print(f"Universe snapshot saved ({len(syms)} symbols)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=float, default=5)
    ap.add_argument("--max-minutes", type=float, default=300)
    ap.add_argument("--delay", type=float, default=0.8)
    a = ap.parse_args()

    t0 = time.time()
    today = dt.date.today()
    start = today - dt.timedelta(days=int(a.years * 365))
    DAILY.mkdir(parents=True, exist_ok=True)
    holidays = set(HOLIDAYS.read_text().split()) if HOLIDAYS.exists() else set()
    existing = {p.stem for p in DAILY.glob("*.parquet")}

    days = [start + dt.timedelta(days=i) for i in range((today - start).days + 1)]
    todo = [d for d in days
            if d.weekday() < 5 and d.isoformat() not in existing and d.isoformat() not in holidays]
    print(f"{len(todo)} days to fetch ({start} -> {today})")

    s = requests.Session()
    s.headers.update(HEADERS)
    try:
        s.get("https://www.nseindia.com", timeout=15)  # cookie warm-up; failure is non-fatal
    except requests.RequestException:
        pass

    fails = saved = 0
    try:
        snapshot_universe(s, today)
        for d in todo:
            if (time.time() - t0) / 60 > a.max_minutes:
                print("Time budget reached; re-run to resume.")
                break
            try:
                r = get(s, DAY_URL.format(d=d))
                fails = 0
            except RuntimeError as e:
                fails += 1
                print(f"FAIL {d}: {e}")
                if fails >= 5:
                    print("5 consecutive failures: NSE is probably blocking this runner's IP.")
                    sys.exit(1)
                continue
            df = parse_day(r.text, d) if r is not None else None
            if df is None:
                if d < today - dt.timedelta(days=4):
                    holidays.add(d.isoformat())  # old and absent => market holiday
                time.sleep(a.delay)
                continue
            df.to_parquet(DAILY / f"{d.isoformat()}.parquet", index=False)
            saved += 1
            if saved % 50 == 0:
                print(f"  saved {saved} (at {d})")
            time.sleep(a.delay)
    finally:
        HOLIDAYS.parent.mkdir(parents=True, exist_ok=True)
        HOLIDAYS.write_text("\n".join(sorted(holidays)) + "\n")
    print(f"Done: saved {saved} new days in {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()
