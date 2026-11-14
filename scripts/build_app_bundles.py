#!/usr/bin/env python3
"""Build the two compact files the Market Pulse app downloads.

  data/app/dead.json       split/bonus-adjusted daily bars for stocks that STOPPED trading (delisted, merged,
                           suspended for good), so a backtest can hold them and take the loss.
  data/app/audit_ref.json  month-end adjusted closes for stocks still trading, so the app can compare its own
                           (Dhan) prices against NSE bhavcopy and spot adjustment errors (a 5x price, say).

Run from the repo root:  python scripts/build_app_bundles.py
Prices are price-return (splits and bonuses adjusted, dividends not), as in scripts/prices.py.
Day numbers are days since 1970-01-01, the same convention the app uses.
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from prices import load_adjusted  # noqa: E402

OUT = ROOT / "data" / "app"
MIN_DAYS = 120            # a dead stock needs this many sessions to be worth including
GONE_SESSIONS = 15        # no bar for this many sessions at the end = no longer trading
ETF_RE = re.compile(r"(BEES$|ETF|IETF|NETF|LIQUID|GILT|SENSEX$|^SETF|^LICMF|^NV20|^MON100|^MAFANG|^HDFCSML|^CPSE|^PSUBNK)", re.I)
MERGE_RE = re.compile(r"amalgamation|merger|scheme of arrangement|arrangement|demerger", re.I)
DELIST_RE = re.compile(r"delist", re.I)


def day_num(d: pd.Series) -> np.ndarray:
    return (d.values.astype("datetime64[D]").astype("int64")).astype(int)


def corp_info() -> tuple[dict, dict, dict]:
    """isin and company name per symbol, plus the text of its last corporate actions"""
    p = ROOT / "data" / "corp_actions_raw.json"
    isin: dict[str, str] = {}
    name: dict[str, str] = {}
    subj: dict[str, list] = {}
    if not p.exists():
        return isin, name, subj
    for e in json.loads(p.read_text()):
        s = e.get("symbol")
        if not s:
            continue
        if e.get("isin") and e["isin"] != "-":
            isin[s] = e["isin"]
        if e.get("comp"):
            name[s] = e["comp"]
        ex = pd.to_datetime(e.get("exDate"), format="%d-%b-%Y", errors="coerce")
        if pd.notna(ex):
            subj.setdefault(s, []).append((ex, e.get("subject", "")))
    return isin, name, subj


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    df = load_adjusted(start="2019-08-01")
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)
    df["r"] = df.groupby("symbol")["close"].pct_change() + 1
    sessions = np.sort(df["date"].unique())
    last_session = pd.Timestamp(sessions[-1])
    cutoff = pd.Timestamp(sessions[-1 - GONE_SESSIONS])
    isin, name, subj = corp_info()

    life = df.groupby("symbol").agg(d0=("date", "min"), d1=("date", "max"), n=("date", "size"),
                                    turn=("turnover_lacs", "median"), maxj=("r", "max"), minj=("r", "min"))
    life["suspect"] = (life["maxj"] > 1.8) | (life["minj"] < 0.55)  # an unadjusted event may remain in the series
    life["gone"] = life["d1"] < cutoff

    # A ticker that vanished because the company carried on under a new one is a rename, not a delisting.
    # Test: a new symbol first trades within 10 days of the old one's last bar, and NSE sets its reference
    # price to the old close (first-row prev_close within 0.5% of the last close), or the ISIN is the same.
    first_row = df.groupby("symbol", as_index=False).head(1).set_index("symbol")
    last_row = df.groupby("symbol", as_index=False).tail(1).set_index("symbol")
    starts = first_row[first_row["date"] > pd.Timestamp(sessions[0]) + pd.Timedelta(days=5)]
    succ: dict[str, tuple[str, float]] = {}
    for sym in life[life["gone"]].index:
        d1, lc = life.loc[sym, "d1"], float(last_row.loc[sym, "close"])
        lraw = float(last_row.loc[sym, "raw_close"])
        cand = starts[(starts["date"] > d1) & (starts["date"] <= d1 + pd.Timedelta(days=10))]
        for ns, row in cand.iterrows():
            if ns == sym:
                continue
            rawprev = float(row["prev_close"]) * float(row["raw_close"]) / float(row["close"]) if row["close"] else 0.0
            same_isin = isin.get(sym) and isin.get(sym) == isin.get(ns)
            if same_isin or (lraw > 0 and abs(rawprev / lraw - 1) <= 0.005):
                succ[sym] = (ns, float(row["prev_close"]) / lc if lc else 1.0)
                break

    dead_syms = []
    for s, r in life[life["gone"]].iterrows():
        if r["n"] < MIN_DAYS:
            continue
        if isin.get(s, "").startswith("INF") or ETF_RE.search(s):
            continue
        dead_syms.append(s)

    dead = []
    for s in dead_syms:
        g = df[df["symbol"] == s]
        t = day_num(g["date"])
        texts = [x[1] for x in subj.get(s, []) if abs((x[0] - life.loc[s, "d1"]).days) <= 150]
        kind = "merged" if any(MERGE_RE.search(x) for x in texts) else "delisted"
        if any(DELIST_RE.search(x) for x in texts):
            kind = "delisted"
        rec = {
            "sym": s, "name": name.get(s, s), "isin": isin.get(s, ""), "kind": kind,
            "suspect": bool(life.loc[s, "suspect"]), "last": str(life.loc[s, "d1"].date()),
            "t0": int(t[0]), "dt": np.diff(t).astype(int).tolist(),
            "o": g["open"].round(2).tolist(), "h": g["high"].round(2).tolist(), "l": g["low"].round(2).tolist(),
            "c": g["close"].round(2).tolist(), "v": g["volume"].round(0).astype(int).tolist(),
        }
        if s in succ:
            rec["kind"] = "renamed"
            rec["succ"], rec["ratio"] = succ[s][0], round(succ[s][1], 5)
        dead.append(rec)
    meta = {"built": str(last_session.date()), "firstDay": str(pd.Timestamp(sessions[0]).date()), "count": len(dead)}
    (OUT / "dead.json").write_text(json.dumps({"meta": meta, "stocks": dead}, separators=(",", ":")))
    (OUT / "meta.json").write_text(json.dumps({"built": meta["built"], "dead": len(dead)}))

    # reference closes: last session of each month, only for stocks still trading with a clean adjusted series
    live = life[(~life["gone"]) & (life["n"] >= 250) & (~life["suspect"])].index
    d = df[df["symbol"].isin(live)].copy()
    d["ym"] = d["date"].dt.year * 12 + d["date"].dt.month - 1
    first_m = int(d["ym"].min())
    nm = int(d["ym"].max()) - first_m + 1
    pick = d.groupby(["symbol", "ym"], as_index=False).tail(1)
    ref = {}
    for s, g in pick.groupby("symbol"):
        arr = [0.0] * nm
        for ym, c in zip(g["ym"], g["close"]):
            arr[int(ym) - first_m] = round(float(c), 2)
        ref[s] = arr
    # the split and bonus events the repo itself adjusted for: the app only trusts a price-level difference that one of these explains
    ev: dict[str, list] = {}
    adjf = ROOT / "data" / "adj_factors.csv"
    if adjf.exists():
        a = pd.read_csv(adjf)
        a = a[a["kind"].isin(["bonus", "split", "bonus+split", "consolidation"]) & a["symbol"].isin(ref.keys())]
        for r in a.itertuples():
            d = int(pd.Timestamp(r.ex_date).to_datetime64().astype("datetime64[D]").astype("int64"))
            ev.setdefault(r.symbol, []).append([d, round(float(r.factor), 6)])
    refmeta = {"built": str(last_session.date()), "m0": f"{first_m // 12}-{first_m % 12 + 1:02d}", "months": nm, "count": len(ref)}
    (OUT / "audit_ref.json").write_text(json.dumps({"meta": refmeta, "close": ref, "events": ev}, separators=(",", ":")))

    k = {n: sum(1 for x in dead if x["kind"] == n) for n in ("delisted", "merged", "renamed")}
    print(f"dead stocks {len(dead)} {k} suspect {sum(1 for x in dead if x['suspect'])}")
    print(f"audit reference {len(ref)} stocks x {nm} months")
    for f in ("dead.json", "audit_ref.json"):
        print(f, round((OUT / f).stat().st_size / 1e6, 2), "MB")


if __name__ == "__main__":
    main()
