#!/usr/bin/env python3
"""Load split/bonus-adjusted daily prices.

    from prices import load_adjusted
    df = load_adjusted(symbols=["TCS", "BAJFINANCE"], start="2022-01-01")

Adjusted columns: open, high, low, close, prev_close are multiplied by the cumulative factor of all
events with ex_date AFTER the row's date; volume is divided by it. Raw values stay as raw_close/raw_volume.
Dividends and rights issues are not adjusted (price-return series).
"""
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PRICE_COLS = ["open", "high", "low", "close", "prev_close"]


def load_adjusted(symbols=None, start=None, series=("EQ", "BE")):
    con = duckdb.connect()
    where = [f"series in ({','.join(repr(s) for s in series)})"]
    if symbols:
        where.append(f"symbol in ({','.join(repr(s) for s in symbols)})")
    if start:
        where.append(f"date >= '{start}'")
    glob = (ROOT / "data" / "daily").as_posix() + "/*.parquet"
    df = con.sql(f"select * from read_parquet('{glob}') where {' and '.join(where)} order by symbol, date").df()
    df["date"] = pd.to_datetime(df["date"])
    df["raw_close"], df["raw_volume"] = df["close"], df["volume"]

    fpath = ROOT / "data" / "adj_factors.csv"
    if not fpath.exists():
        return df
    f = pd.read_csv(fpath, parse_dates=["ex_date"])
    cum = np.ones(len(df))
    for sym, g in f.groupby("symbol"):
        mask = (df["symbol"] == sym).to_numpy()
        if not mask.any():
            continue
        d = df.loc[mask, "date"].to_numpy()
        c = np.ones(mask.sum())
        for ex, fac in zip(g["ex_date"], g["factor"]):
            c[d < np.datetime64(ex)] *= fac
        cum[mask] = c
    for col in PRICE_COLS:
        df[col] = df[col] * cum
    df["volume"] = df["volume"] / cum
    return df


if __name__ == "__main__":
    t = load_adjusted(["BAJFINANCE", "TATASTEEL", "SIEMENS"], start="2022-01-01")
    for sym, g in t.groupby("symbol"):
        r = (g["close"] / g["close"].shift()).dropna()
        print(sym, "rows", len(g), "worst 1-day ratio", round(r.min(), 3), "best", round(r.max(), 3))
