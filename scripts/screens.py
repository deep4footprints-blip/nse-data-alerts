#!/usr/bin/env python3
"""End-of-day features and breakout signals for the VCP and Multi-year screens.

All signals are known at the CLOSE of the signal day (no look-ahead); trading happens on the next open.

Definitions (published BananaPatterns thresholds where they exist, our own choices elsewhere - see PARAMS):
  Liquid universe : series EQ and median daily turnover (63 sessions) >= min_turn_cr crore.
  RS (1-99)       : percentile rank across the liquid universe of 0.4*r63 + 0.2*r126 + 0.2*r189 + 0.2*r252
                    (r_k = k-session return). Needs 252 sessions of history. [our formula; site's is unpublished]
  Base / pivot    : pivot = highest close in the base; base starts at the latest session of that close.
                    Breakout = close above the pivot (first time).
  VCP             : RS>=70, base length>=15 sessions (3 weeks), depth<=35%, ATR% 2nd half / 1st half <= 0.9,
                    volume 2nd half / 1st half <= 0.9. Base searched over several lookbacks (largest that qualifies).
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
    vcp_wins=(252, 130, 65, 40),  # base lookbacks (sessions), tried largest first
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
    df["med_turn"] = g["turn_cr"].transform(lambda s: s.rolling(63, min_periods=40).median())
    df["liquid"] = (df["med_turn"] >= min_turn_cr)

    comp = 0.4 * df["r63"] + 0.2 * df["r126"] + 0.2 * df["r189"] + 0.2 * df["r252"]
    comp = comp.where(df["liquid"])
    pct = comp.groupby(df["date"]).rank(pct=True)
    df["rs"] = np.round(1 + 98 * pct)  # NaN where not ranked
    return df


@njit(cache=True)
def _vcp(close, high, low, vol, trp, rs, liquid, starts, wins, min_rs, min_len, max_depth, max_atr, max_vol):
    n = close.shape[0]
    flag = np.zeros(n, np.int8)
    o_w = np.full(n, np.nan)
    o_len = np.full(n, np.nan)
    o_depth = np.full(n, np.nan)
    o_atr = np.full(n, np.nan)
    o_vol = np.full(n, np.nan)
    o_piv = np.full(n, np.nan)
    for k in range(starts.shape[0] - 1):
        a = starts[k]
        b = starts[k + 1]
        for i in range(a, b):
            if not liquid[i] or not (rs[i] >= min_rs):
                continue
            for wi in range(wins.shape[0]):
                W = wins[wi]
                if i - a < W:
                    continue
                pk = -1.0
                s = -1
                for j in range(i - W, i):
                    if close[j] >= pk:
                        pk = close[j]
                        s = j
                if not (close[i] > pk):
                    continue
                L = i - s
                if L < min_len:
                    continue
                ml = low[s]
                for j in range(s, i):
                    if low[j] < ml:
                        ml = low[j]
                depth = 1.0 - ml / pk
                if not (depth <= max_depth):
                    continue
                mid = s + L // 2
                n1 = mid - s
                n2 = i - mid
                sa = 0.0
                sb = 0.0
                va = 0.0
                vb = 0.0
                for j in range(s, mid):
                    sa += trp[j]
                    va += vol[j]
                for j in range(mid, i):
                    sb += trp[j]
                    vb += vol[j]
                if n1 < 1 or n2 < 1 or not (sa > 0) or not (va > 0):
                    continue
                atr_r = (sb / n2) / (sa / n1)
                vol_r = (vb / n2) / (va / n1)
                if not (atr_r <= max_atr and vol_r <= max_vol):
                    continue
                flag[i] = 1
                o_w[i] = W
                o_len[i] = L
                o_depth[i] = depth
                o_atr[i] = atr_r
                o_vol[i] = vol_r
                o_piv[i] = pk
                break
    return flag, o_w, o_len, o_depth, o_atr, o_vol, o_piv


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
             df["trp"].to_numpy(), df["rs"].to_numpy(), df["liquid"].to_numpy(), _starts(df),
             np.array(p["vcp_wins"], dtype=np.int64), p["vcp_min_rs"], p["vcp_min_len"],
             p["vcp_max_depth"], p["vcp_max_atr"], p["vcp_max_vol"])
    flag, w, ln, dp, atr, vr, piv = f
    return _signals(df, flag, dict(win=w, base_len=ln, depth=dp, atr_ratio=atr, vol_ratio=vr, pivot=piv))


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
