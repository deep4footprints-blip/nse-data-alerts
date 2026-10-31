#!/usr/bin/env python3
"""QC: coverage, recent row counts, Nifty 500 completeness, corporate-action candidates."""
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
daily = ROOT / "data" / "daily"
if not list(daily.glob("*.parquet")):
    raise SystemExit("No data yet")

con = duckdb.connect()
con.execute(f"create view px as select * from read_parquet('{daily.as_posix()}/*.parquet')")

print(con.sql("""
    select count(distinct date) as n_days,
           min(date) as first_day,
           max(date) as last_day,
           count(*) as n_rows,
           count(distinct symbol) as n_symbols
    from px
""").df().to_string(index=False))

print(con.sql("""
    select date, count(*) as n
    from px group by date order by date desc limit 5
""").df().to_string(index=False))

snaps = sorted((ROOT / "data" / "universe").glob("nifty500_*.csv"))
if snaps:
    uni = set(pd.read_csv(snaps[-1])["Symbol"].astype(str).str.strip())
    last = con.sql("select max(date) as d from px").df()["d"].iloc[0]
    have = set(con.sql(f"select symbol from px where date = '{last}'").df()["symbol"])
    missing = sorted(uni - have)
    print(f"Nifty 500 coverage on {last}: {len(uni) - len(missing)}/{len(uni)}; missing: {missing[:20]}")
else:
    print("WARN: no Nifty 500 universe snapshot found")

ca = con.sql("""
    with x as (
      select symbol, date, close, prev_close,
             lag(close) over (partition by symbol order by date) as c1
      from px)
    select symbol, date, c1 as prior_close, prev_close as nse_prev_close,
           round(prev_close / c1, 4) as ratio
    from x
    where c1 > 0 and abs(prev_close / c1 - 1) > 0.02
    order by date
""").df()
out = ROOT / "data" / "ca_candidates.csv"
ca.to_csv(out, index=False)
print(f"{len(ca)} corporate-action candidates -> {out}")
