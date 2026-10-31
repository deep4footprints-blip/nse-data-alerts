#!/usr/bin/env python3
"""Build per-symbol price-adjustment factors from NSE corporate actions.

Input : data/corp_actions_raw.json  (from capture_corp_actions.py), data/daily/*.parquet
Output: data/adj_factors.csv  columns: symbol, ex_date, factor, kind, note
        factor = multiplier applied to prices BEFORE ex_date (e.g. 1:1 bonus -> 0.5).
Handles: face-value splits, bonus issues, consolidations (exact, from the subject text) and
demergers (ESTIMATED from the observed ex-date price drop). Rights issues and dividends are NOT adjusted.
Validation: every split/bonus must show a matching price drop; big Nifty 500 drops must be explained.
"""
import glob
import json
import re
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "corp_actions_raw.json"
OUT = ROOT / "data" / "adj_factors.csv"
START, END = pd.Timestamp("2021-11-02"), pd.Timestamp.today().normalize()


def num(x):
    return float(x.replace(",", ""))


def parse(subject):
    s = subject.strip().lower()
    if s.startswith("face value split"):
        m = re.search(r"from\s+r[se]\.?\s*([\d.,]+).*?to\s+r[se]\.?\s*([\d.,]+)", s)
        return (num(m[2]) / num(m[1]), "split") if m else (None, "split_unparsed")
    m = re.match(r"^bonus\s+(\d+)\s*:\s*(\d+)", s)
    if m:
        a, b = int(m[1]), int(m[2])
        return b / (a + b), "bonus"
    if s.startswith("consolidation"):
        m = re.search(r"from\s+r[se]\.?\s*([\d.,]+).*?to\s+r[se]\.?\s*([\d.,]+)", s)
        return (num(m[2]) / num(m[1]), "consolidation") if m else (None, "consol_unparsed")
    if s.startswith("demerger"):
        return None, "demerger"
    return None, None


def main():
    raw = pd.DataFrame(json.loads(RAW.read_text()))
    raw["ex"] = pd.to_datetime(raw["exDate"], format="%d-%b-%Y", errors="coerce")
    parsed = raw["subject"].apply(parse)
    raw["factor"] = [p[0] for p in parsed]
    raw["kind"] = [p[1] for p in parsed]
    bad = raw[raw.kind.isin(["split_unparsed", "consol_unparsed"])]
    if len(bad):
        print("WARN unparsed:", bad.subject.tolist()[:5])

    con = duckdb.connect()
    con.execute(f"create view px as select * from read_parquet('{(ROOT / 'data' / 'daily').as_posix()}/*.parquet')")
    px = con.sql("select symbol, date, close from px where series in ('EQ','BE')").df()
    px["date"] = pd.to_datetime(px["date"])
    px = px.sort_values(["symbol", "date"])
    px["r"] = px["close"] / px.groupby("symbol")["close"].shift()

    def actual(sym, ex):
        sub = px[(px.symbol == sym) & (px.date >= ex) & (px.date <= ex + pd.Timedelta(days=5))].head(1)
        return (sub["r"].iloc[0], sub["date"].iloc[0]) if len(sub) else (None, None)

    ev = raw[raw.ex.between(START, END) & raw.kind.notna()].copy()
    ev = ev.drop_duplicates(["symbol", "ex", "subject"])

    rows = []
    for (sym, ex), g in ev.groupby(["symbol", "ex"]):
        exact = g[g.factor.notna()]
        r, d = actual(sym, ex)
        if len(exact):
            f = float(exact.factor.prod())
            kind = "+".join(sorted(set(exact.kind)))
            ok = None if r is None or pd.isna(r) else abs(r / f - 1) < 0.30
            rows.append(dict(symbol=sym, ex_date=(d if d is not None else ex).date(), factor=round(f, 6),
                             kind=kind, note="" if ok is not False else f"CHECK actual_ratio={r:.3f}",
                             _ok=ok))
        elif (g.kind == "demerger").any() and r is not None and 0.3 < r < 0.90:
            rows.append(dict(symbol=sym, ex_date=d.date(), factor=round(float(r), 6),
                             kind="demerger_est", note="estimated from observed price drop", _ok=None))
    out = pd.DataFrame(rows).sort_values(["symbol", "ex_date"])

    chk = out[out.kind != "demerger_est"]
    known = chk[chk._ok.notna()].copy()
    known["_ok"] = known["_ok"].astype(bool)
    print(f"factor events: {len(out)} (exact {len(chk)}, demerger est {len(out) - len(chk)})")
    print(f"exact events with price data: {len(known)}; price drop matches factor: {known._ok.mean():.1%}")
    print(known[~known._ok][["symbol", "ex_date", "factor", "note"]].head(10).to_string(index=False))

    # reverse check: large Nifty 500 overnight drops must be explained by an event within 5 days
    u = set(pd.read_csv(sorted(glob.glob(str(ROOT / "data" / "universe" / "nifty500_*.csv")))[-1])["Symbol"].str.strip())
    drops = px[(px.r < 0.62) & px.symbol.isin(u) & px.date.between(START, END)]
    o = out.assign(ex_date=pd.to_datetime(out.ex_date))
    unexpl = [r for r in drops.itertuples()
              if not ((o.symbol == r.symbol) & ((o.ex_date - r.date).abs() <= pd.Timedelta(days=5))).any()]
    share = 1 - len(unexpl) / max(len(drops), 1)
    print(f"Nifty 500 overnight drops >38%: {len(drops)}; explained by an event: {share:.1%}")
    for r in unexpl[:15]:
        print(f"  UNEXPLAINED {r.symbol} {r.date.date()} ratio={r.r:.3f}")

    out.drop(columns="_ok").to_csv(OUT, index=False)
    print(f"Wrote {OUT} ({len(out)} rows)")
    if share < 0.90:
        raise SystemExit("Validation failed: <90% of Nifty 500 drops explained")


if __name__ == "__main__":
    main()
