#!/usr/bin/env python3
"""End-of-day features and breakout signals for the VCP and Multi-year screens.

All signals are known at the CLOSE of the signal day (no look-ahead); trading happens on the next open.

Definitions (published BananaPatterns thresholds where they exist, our own choices elsewhere - see PARAMS):
  Liquid universe : series EQ and median daily turnover (63 sessions) >= min_turn_cr crore.
  RS (1-99)       : percentile rank across the liquid universe of 0.4*r63 + 0.2*r126 + 0.2*r189 + 0.2*r252
                    (r_k = k-session return). Needs 252 sessions of history. [our formula; site's is unpublished]
  Base / pivot    : pivot = highest close in the base; base starts at the latest session of that close.
                    Breakout = close above the pivot (first time).
  VCP             : replicates the BananaPatterns VCP screen preset (read from the live screen, Oct 2026). All
                    conditions are measured at the close BEFORE the breakout day, the breakout is a close above the pivot:
                      RS>=70; close>=50-DMA and >=200-DMA; close within 30% of the 52-week high and >=15% above the
                      52-week low; median 20-day turnover>=1 cr; base age>=3 weeks (15 sessions); base depth<=35%;
                      ATR% 2nd half / 1st half <= 0.9; volume 2nd half / 1st half <= 0.9.
                    Bases are nested: every earlier close that is the highest close since then is a candidate pivot
                    (the site lists several bases per stock, e.g. a 3-week and a 7-week base with different pivots).
                    The lowest candidate pivot that clears the close and passes every test is reported.
                    Market cap >= Rs 300 cr (site filter) cannot be applied - no market-cap data.
  Multi-year      : 52-week (252-session) closing-high breakout, range depth<=35%, close>200-DMA, RS>=60,
                    breakout volume >= vol_mult x prior-20-session median. [depth & volume rule are our choices]
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from numba import njit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prices import load_adjusted  # noqa: E402

PARAMS = dict(
    min_turn_cr=1.0,             # median daily turnover floor, Rs crore
    # VCP
    vcp_min_rs=70, vcp_min_len=15, vcp_max_depth=0.35, vcp_max_atr=0.9, vcp_max_vol=0.9,
    vcp_max_from_high=0.30, vcp_min_above_low=0.15, vcp_max_look=300,  # site: within 30% of 52w high, >=15% above low
    # Multi-year
    my_min_rs=60, my_win=252, my_max_depth=0.35, my_vol_mult=1.5,
)


def build_panel(start=None, min_turn_cr=None):
    """Long dataframe sorted by (symbol, date) with all features needed by the kernels."""
    min_turn_cr = PARAMS["min_turn_cr"] if min_turn_cr is None else min_turn_cr
    df = load_adjusted(series=("EQ",), start=start)
    df = df.drop_duplicates(["symbol", "date"]).sort_values(["symbol", "date"]).reset_index(drop=True)
    for c in ["open", "high", "low", "close", "volume", "turnover_lacs"]:
        df[c] = df[c].astype("float64")
    df["turn_cr"] = df["turnover_lacs"] / 100.0  # 100 lakh = 1 crore
    g = df.groupby("symbol", sort=False)

    pc = g["close"].shift(1)
    tr = np.maximum.reduce([(df["high"] - df["low"]).to_numpy(),
                            (df["high"] - pc).abs().to_numpy(),
                            (df["low"] - pc).abs().to_numpy()])
    df["trp"] = tr / df["close"].to_numpy()  # ATR% building block (true range / close)

    for k in (63, 126, 189, 252):
        df[f"r{k}"] = df["close"] / g["close"].shift(k) - 1.0
    df["sma200"] = g["close"].transform(lambda s: s.rolling(200, min_periods=200).mean())
    df["med20"] = g["volume"].transform(lambda s: s.shift(1).rolling(20, min_periods=15).median())
    df["med_turn"] = g["turn_cr"].transform(lambda s: s.rolling(20, min_periods=15).median())  # site: 20-day median
    df["sma50"] = g["close"].transform(lambda s: s.rolling(50, min_periods=50).mean())
    df["hi52"] = g["high"].transform(lambda s: s.rolling(252, min_periods=200).max())
    df["lo52"] = g["low"].transform(lambda s: s.rolling(252, min_periods=200).min())
    df["liquid"] = (df["med_turn"] >= min_turn_cr)

    comp = 0.4 * df["r63"] + 0.2 * df["r126"] + 0.2 * df["r189"] + 0.2 * df["r252"]
    comp = comp.where(df["liquid"])
    pct = comp.groupby(df["date"]).rank(pct=True)
    df["rs"] = np.round(1 + 98 * pct)  # NaN where not ranked
    return df


@njit(cache=True)
def _vcp(close, high, low, vol, trp, rs, sma50, sma200, hi52, lo52, liquid, starts,
         min_rs, min_len, max_depth, max_atr, max_vol, max_hi, min_lo, max_look):
    """Signal on day i = close above a pivot; every filter is read at the previous close (i-1)."""
    n = close.shape[0]
    flag = np.zeros(n, np.int8)
    o_len = np.full(n, np.nan)
    o_depth = np.full(n, np.nan)
    o_atr = np.full(n, np.nan)
    o_vol = np.full(n, np.nan)
    o_piv = np.full(n, np.nan)
    o_nc = np.zeros(n, np.int8)  # number of qualifying nested bases cleared that day
    for k in range(starts.shape[0] - 1):
        a = starts[k]
        b = starts[k + 1]
        for i in range(a + 1, b):
            p = i - 1
            if not liquid[p] or not (rs[p] >= min_rs):
                continue
            if not (close[p] >= sma50[p] and close[p] >= sma200[p]):
                continue
            if not (close[p] >= (1.0 - max_hi) * hi52[p] and close[p] >= (1.0 + min_lo) * lo52[p]):
                continue
            ci = close[i]
            m = -1.0
            ml = 1e18
            lim = p - max_look
            if lim < a:
                lim = a
            for j in range(p, lim - 1, -1):
                if low[j] < ml:
                    ml = low[j]
                if close[j] > m:
                    m = close[j]
                    if m >= ci:
                        break
                    L = p - j
                    if L < min_len:
                        continue
                    depth = 1.0 - ml / m
                    if not (depth <= max_depth):
                        continue
                    nb = L + 1
                    mid = j + nb // 2
                    n1 = mid - j
                    n2 = p + 1 - mid
                    if n1 < 1 or n2 < 1:
                        continue
                    sa = 0.0
                    sb = 0.0
                    va = 0.0
                    vb = 0.0
                    for q in range(j, mid):
                        sa += trp[q]
                        va += vol[q]
                    for q in range(mid, p + 1):
                        sb += trp[q]
                        vb += vol[q]
                    if not (sa > 0) or not (va > 0):
                        continue
                    atr_r = (sb / n2) / (sa / n1)
                    vol_r = (vb / n2) / (va / n1)
                    if not (atr_r <= max_atr and vol_r <= max_vol):
                        continue
                    if flag[i] == 0:
                        flag[i] = 1
                        o_len[i] = L
                        o_depth[i] = depth
                        o_atr[i] = atr_r
                        o_vol[i] = vol_r
                        o_piv[i] = m
                    o_nc[i] += 1
    return flag, o_len, o_depth, o_atr, o_vol, o_piv, o_nc


@njit(cache=True)
def _multi(close, low, vol, med20, sma200, rs, liquid, starts, W, min_rs, max_depth, vol_mult):
    n = close.shape[0]
    flag = np.zeros(n, np.int8)
    o_len = np.full(n, np.nan)
    o_depth = np.full(n, np.nan)
    o_piv = np.full(n, np.nan)
    for k in range(starts.shape[0] - 1):
        a = starts[k]
        b = starts[k + 1]
        for i in range(a + W, b):
            if not liquid[i] or not (rs[i] >= min_rs):
                continue
            pk = -1.0
            s = -1
            ml = low[i - W]
            for j in range(i - W, i):
                if close[j] >= pk:
                    pk = close[j]
                    s = j
                if low[j] < ml:
                    ml = low[j]
            if not (close[i] > pk):
                continue
            depth = 1.0 - ml / pk
            if not (depth <= max_depth):
                continue
            if not (close[i] > sma200[i]):
                continue
            if not (vol[i] >= vol_mult * med20[i]):
                continue
            flag[i] = 1
            o_len[i] = i - s
            o_depth[i] = depth
            o_piv[i] = pk
    return flag, o_len, o_depth, o_piv


def _starts(df):
    sym = df["symbol"].to_numpy()
    cuts = np.flatnonzero(sym[1:] != sym[:-1]) + 1
    return np.concatenate([[0], cuts, [len(sym)]]).astype(np.int64)


def _signals(df, flag, extra):
    idx = np.flatnonzero(flag)
    out = df.iloc[idx][["symbol", "date", "close", "rs", "volume", "med20"]].copy()
    out["brk_vol_x"] = out["volume"] / out["med20"]
    for k, v in extra.items():
        out[k] = v[idx]
    return out.drop(columns=["volume", "med20"]).reset_index(drop=True)


def vcp_signals(df, p=PARAMS):
    f = _vcp(df["close"].to_numpy(), df["high"].to_numpy(), df["low"].to_numpy(), df["volume"].to_numpy(),
             df["trp"].to_numpy(), df["rs"].to_numpy(), df["sma50"].to_numpy(), df["sma200"].to_numpy(),
             df["hi52"].to_numpy(), df["lo52"].to_numpy(), df["liquid"].to_numpy(), _starts(df),
             p["vcp_min_rs"], p["vcp_min_len"], p["vcp_max_depth"], p["vcp_max_atr"], p["vcp_max_vol"],
             p["vcp_max_from_high"], p["vcp_min_above_low"], int(p["vcp_max_look"]))
    flag, ln, dp, atr, vr, piv, nc = f
    # rs reported is the previous-close RS (what the screen would have shown while forming)
    out = _signals(df, flag, dict(base_len=ln, depth=dp, atr_ratio=atr, vol_ratio=vr, pivot=piv, n_bases=nc))
    return out


def multi_signals(df, p=PARAMS):
    f = _multi(df["close"].to_numpy(), df["low"].to_numpy(), df["volume"].to_numpy(), df["med20"].to_numpy(),
               df["sma200"].to_numpy(), df["rs"].to_numpy(), df["liquid"].to_numpy(), _starts(df),
               int(p["my_win"]), p["my_min_rs"], p["my_max_depth"], p["my_vol_mult"])
    flag, ln, dp, piv = f
    return _signals(df, flag, dict(base_len=ln, depth=dp, pivot=piv))


if __name__ == "__main__":
    d = build_panel()
    v, m = vcp_signals(d), multi_signals(d)
    print("panel rows", len(d), "| liquid rows", int(d.liquid.sum()), "| rs ranked rows", int(d.rs.notna().sum()))
    for name, s in (("VCP", v), ("MULTI", m)):
        s = s.assign(year=pd.to_datetime(s.date).dt.year)
        print(name, "signals", len(s), "| per year:", s.groupby("year").size().to_dict())
