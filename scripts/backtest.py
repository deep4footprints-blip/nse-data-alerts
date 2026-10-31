#!/usr/bin/env python3
"""Portfolio backtest for the VCP and Multi-year breakout screens.

Rules (defaults; every one is a CLI flag):
  Signal  : breakout close on day t (see screens.py). Entry at the OPEN of day t+1 (alerts come after the close).
  Stop    : entry * (1 - stop). Executes at the stop price, or at the open if the stock opens below it.
  Exit    : close below the N-day MA, only after the stock has first closed above it; exits at the next open.
  Sizing  : risk * equity / (entry * stop) shares, capped by pos_cap of equity, available cash and
            part x median daily turnover. Max `max_pos` positions; if more signals than slots, highest RS first.
  Costs   : `cost` per side on traded value (brokerage + STT/stamp/GST + slippage, all-in).
Results are hypothetical: fixed rules replayed on past data.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import screens  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"


def build_matrices(df, ma_n, ma_kind):
    dates = np.sort(df["date"].unique())
    syms = np.sort(df["symbol"].unique())
    ti = np.searchsorted(dates, df["date"].to_numpy())
    si = np.searchsorted(syms, df["symbol"].to_numpy())
    T, N = len(dates), len(syms)

    def mat(col):
        m = np.full((T, N), np.nan)
        m[ti, si] = df[col].to_numpy(dtype="float64")
        return m

    O, H, L, C, MT = mat("open"), mat("high"), mat("low"), mat("close"), mat("med_turn")
    LQ = np.zeros((T, N), bool)
    LQ[ti, si] = df["liquid"].to_numpy()
    CF = pd.DataFrame(C).ffill(limit=5).to_numpy()
    cf = pd.DataFrame(CF)
    MA = (cf.ewm(span=ma_n, adjust=False, min_periods=ma_n).mean() if ma_kind == "ema"
          else cf.rolling(ma_n, min_periods=ma_n).mean()).to_numpy()
    first_rs = int(ti[df["rs"].notna().to_numpy()].min())
    return dict(dates=dates, syms=syms, ti=ti, si=si, O=O, H=H, L=L, C=C, CF=CF, MA=MA, MT=MT, LQ=LQ,
                t0=first_rs)


def simulate(M, sig, *, risk, stop, max_pos, cost, capital, pos_cap, part, max_gap):
    dates, O, L, C, CF, MA, MT = M["dates"], M["O"], M["L"], M["C"], M["CF"], M["MA"], M["MT"]
    T, N = O.shape
    t0 = M["t0"]
    sigmap = {}
    tix = np.searchsorted(dates, sig["date"].to_numpy())
    six = np.searchsorted(M["syms"], sig["symbol"].to_numpy())
    for ti_, si_, rs_, pv_ in zip(tix, six, sig["rs"].to_numpy(), sig["pivot"].to_numpy()):
        sigmap.setdefault(int(ti_), []).append((float(rs_), int(si_), float(pv_)))

    cash = capital
    pos, pending, trades = {}, set(), []
    eq = np.full(T, np.nan)
    invested = np.zeros(T)
    gaps = []

    def close_pos(s, px, t, reason):
        nonlocal cash
        p = pos.pop(s)
        pending.discard(s)
        cash += p["sh"] * px * (1 - cost)
        pnl = p["sh"] * px * (1 - cost) - p["sh"] * p["entry"] * (1 + cost)
        trades.append(dict(symbol=M["syms"][s], entry_date=str(dates[p["t"]])[:10], exit_date=str(dates[t])[:10],
                           entry=p["entry"], exit=px, shares=p["sh"], pnl=pnl, R=pnl / p["risk"],
                           ret=px / p["entry"] - 1, days=t - p["t"], reason=reason, rs=p["rs"]))

    for t in range(t0, T):
        for s in list(pending):
            if s in pos and O[t, s] == O[t, s]:
                close_pos(s, O[t, s], t, "ma_exit")
        for s in list(pos):
            p = pos[s]
            lo = L[t, s]
            if p["t"] < t and lo == lo and lo <= p["stop"]:
                o = O[t, s]
                close_pos(s, o if (o == o and o < p["stop"]) else p["stop"], t, "stop")
        if t > t0 and (t - 1) in sigmap:
            marks = sum(p["sh"] * CF[t - 1, s] for s, p in pos.items() if CF[t - 1, s] == CF[t - 1, s])
            eq_open = cash + marks
            for rs, s, pivot in sorted(sigmap[t - 1], key=lambda x: -x[0]):
                if s in pos or len(pos) >= max_pos:
                    continue
                o = O[t, s]
                if not (o == o):
                    continue
                gap = o / pivot - 1
                if max_gap is not None and gap > max_gap:
                    continue
                sh = int(eq_open * risk / (o * stop))
                sh = min(sh, int(eq_open * pos_cap / o), int(cash / (o * (1 + cost))))
                mt = MT[t - 1, s]
                if mt == mt:
                    sh = min(sh, int(part * mt * 1e7 / o))
                if sh < 1:
                    continue
                cash -= sh * o * (1 + cost)
                pos[s] = dict(t=t, entry=o, sh=sh, stop=o * (1 - stop), above=False, risk=sh * o * stop, rs=rs)
                gaps.append(gap)
                if L[t, s] == L[t, s] and L[t, s] <= pos[s]["stop"]:
                    close_pos(s, pos[s]["stop"], t, "stop")
        for s, p in pos.items():
            c, ma = C[t, s], MA[t, s]
            if c == c and ma == ma:
                if c > ma:
                    p["above"] = True
                elif p["above"] and c < ma:
                    pending.add(s)
        val = 0.0
        for s, p in pos.items():
            px = CF[t, s]
            val += p["sh"] * (px if px == px else p["entry"])
        eq[t] = cash + val
        invested[t] = val / eq[t]
    for s in list(pos):
        px = CF[T - 1, s]
        close_pos(s, px if px == px else pos[s]["entry"], T - 1, "end")
    return pd.DataFrame(trades), eq, invested, np.array(gaps)


def null_model(df, M, sig, kw, n_seeds, min_rs, capital):
    """Random-entry baseline: same number of signals per day, drawn at random from liquid stocks with RS>=min_rs,
    run through the SAME exits and sizing. Tells us whether the screen's entry adds value beyond the exit rules."""
    pool = df[df["liquid"] & (df["rs"] >= min_rs)][["symbol", "date", "rs", "close"]].rename(columns={"close": "pivot"})
    by_day = {d: g for d, g in pool.groupby("date")}
    cnt = sig.groupby("date").size()
    res = []
    for seed in range(n_seeds):
        rng = np.random.default_rng(seed)
        parts = [by_day[d].sample(min(c, len(by_day[d])), random_state=int(rng.integers(1e9)))
                 for d, c in cnt.items() if d in by_day]
        t2, e2, i2, _ = simulate(M, pd.concat(parts), **kw)
        o2, _ = summarize(t2, e2, i2, M, capital, "null")
        if "win_rate" in o2:
            res.append((o2["expectancy_R"], o2["profit_factor"], o2["cagr"], o2["win_rate"]))
    return np.array(res)


def max_dd(x):
    peak = np.maximum.accumulate(x)
    return float((x / peak - 1).min())


def summarize(tr, eq, inv, M, capital, label):
    t0 = M["t0"]
    dates = M["dates"]
    e = eq[t0:]
    years = (dates[-1] - dates[t0]).astype("timedelta64[D]").astype(float) / 365.25
    out = dict(label=label, trades=len(tr))
    if len(tr) == 0:
        return out, {}
    win = tr[tr.pnl > 0]
    loss = tr[tr.pnl <= 0]
    rng = np.random.default_rng(7)
    boot = np.array([rng.choice(tr.R.to_numpy(), len(tr)).mean() for _ in range(5000)])
    top5 = tr.pnl.nlargest(5).sum()
    out.update(
        total_return=e[-1] / capital - 1,
        cagr=(e[-1] / capital) ** (1 / years) - 1,
        max_dd=max_dd(e),
        exposure=float(inv[t0:].mean()),
        win_rate=len(win) / len(tr),
        avg_win_R=win.R.mean() if len(win) else np.nan,
        avg_loss_R=loss.R.mean() if len(loss) else np.nan,
        expectancy_R=tr.R.mean(),
        ci90_lo=np.percentile(boot, 5),
        ci90_hi=np.percentile(boot, 95),
        profit_factor=win.pnl.sum() / -loss.pnl.sum() if loss.pnl.sum() < 0 else np.inf,
        avg_days=tr.days.mean(),
        median_ret=tr.ret.median(),
        top5_share=top5 / tr.pnl.sum() if tr.pnl.sum() > 0 else np.nan,
        exp_R_ex_top5=tr.drop(tr.pnl.nlargest(5).index).R.mean(),
        stop_share=(tr.reason == "stop").mean(),
        years=years,
    )
    yr = pd.Series(e, index=pd.to_datetime(dates[t0:])).groupby(lambda d: d.year).last()
    yr = yr / yr.shift(1).fillna(capital) - 1
    tr = tr.assign(year=pd.to_datetime(tr.entry_date).dt.year)
    by_year = pd.DataFrame(dict(ret=yr, trades=tr.groupby("year").size(), exp_R=tr.groupby("year").R.mean()))
    half = pd.to_datetime(dates[t0 + (len(dates) - t0) // 2])
    first = tr[pd.to_datetime(tr.entry_date) < half]
    second = tr[pd.to_datetime(tr.entry_date) >= half]
    out["exp_R_first_half"] = first.R.mean() if len(first) else np.nan
    out["exp_R_second_half"] = second.R.mean() if len(second) else np.nan
    out["half_split"] = str(half)[:10]
    return out, dict(by_year=by_year)


def benchmark(M):
    CF, LQ, t0 = M["CF"], M["LQ"], M["t0"]
    r = CF[1:] / CF[:-1] - 1
    r = np.where(LQ[:-1] & np.isfinite(r), np.clip(r, -0.4, 0.4), np.nan)
    d = np.nanmean(r, axis=1)
    eq = np.concatenate([[1.0], np.cumprod(1 + np.nan_to_num(d))])
    return eq[t0:] / eq[t0]


def fmt(o):
    pct = lambda v: f"{v:.1%}"
    return (f"| {o['label']} | {o['trades']} | {pct(o['win_rate'])} | {o['avg_win_R']:.2f} / {o['avg_loss_R']:.2f} | "
            f"{o['expectancy_R']:+.3f} [{o['ci90_lo']:+.3f}, {o['ci90_hi']:+.3f}] | {o['profit_factor']:.2f} | "
            f"{pct(o['cagr'])} | {pct(o['max_dd'])} | {pct(o['exposure'])} |")


HEADER = ("| Run | Trades | Win rate | Avg win / loss (R) | Expectancy R [90% CI] | Profit factor | CAGR | Max DD | Exposure |\n"
          "|---|---|---|---|---|---|---|---|---|")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--screens", default="vcp,multi")
    ap.add_argument("--risk", type=float, default=0.005)
    ap.add_argument("--stop", type=float, default=0.08)
    ap.add_argument("--max-pos", type=int, default=10)
    ap.add_argument("--cost", type=float, default=0.003)
    ap.add_argument("--capital", type=float, default=1_000_000)
    ap.add_argument("--pos-cap", type=float, default=0.20)
    ap.add_argument("--part", type=float, default=0.05)
    ap.add_argument("--ma", type=int, default=50)
    ap.add_argument("--ma-kind", default="sma", choices=["sma", "ema"])
    ap.add_argument("--max-gap", type=float, default=None)
    ap.add_argument("--min-turn", type=float, default=1.0)
    ap.add_argument("--vol-mult", type=float, default=1.5)
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--null", type=int, default=0, help="number of random-entry seeds (0 = skip)")
    ap.add_argument("--tag", default="default")
    a = ap.parse_args()

    screens.PARAMS["min_turn_cr"] = a.min_turn
    screens.PARAMS["my_vol_mult"] = a.vol_mult
    df = screens.build_panel()
    M = build_matrices(df, a.ma, a.ma_kind)
    sigs = {"vcp": screens.vcp_signals(df), "multi": screens.multi_signals(df)}
    kw = dict(risk=a.risk, stop=a.stop, max_pos=a.max_pos, cost=a.cost, capital=a.capital,
              pos_cap=a.pos_cap, part=a.part, max_gap=a.max_gap)
    RESULTS.mkdir(exist_ok=True)

    lines = [f"# Backtest `{a.tag}`", "",
             f"Window: {str(M['dates'][M['t0']])[:10]} to {str(M['dates'][-1])[:10]} "
             f"({(M['dates'][-1] - M['dates'][M['t0']]).astype('timedelta64[D]').astype(int) / 365.25:.1f} years, "
             f"after the 252-session RS warm-up). Capital Rs {a.capital:,.0f}. "
             f"Params: risk {a.risk:.2%}, stop {a.stop:.0%}, MA exit {a.ma}-{a.ma_kind}, max {a.max_pos} positions, "
             f"cost {a.cost:.2%}/side, min turnover Rs {a.min_turn} cr, multi-year vol x{a.vol_mult}.", "",
             HEADER]
    detail = []
    bench = benchmark(M)
    yrs = pd.Series(bench, index=pd.to_datetime(M["dates"][M["t0"]:])).groupby(lambda d: d.year).last()
    byb = yrs / yrs.shift(1).fillna(1.0) - 1
    nyears = (M["dates"][-1] - M["dates"][M["t0"]]).astype("timedelta64[D]").astype(float) / 365.25
    for name in a.screens.split(","):
        sig = sigs[name]
        tr, eq, inv, gaps = simulate(M, sig, **kw)
        o, extra = summarize(tr, eq, inv, M, a.capital, name)
        if "win_rate" not in o:
            lines.append(f"| {name} | 0 trades | | | | | | | |")
            continue
        lines.append(fmt(o))
        tr.to_csv(RESULTS / f"trades_{name}_{a.tag}.csv", index=False)
        d = [f"## {name}", f"- signals {len(sig)}, trades taken {len(tr)}; median entry gap above pivot "
             f"{np.median(gaps):.1%}; stop-outs {o['stop_share']:.0%} of trades; avg hold {o['avg_days']:.0f} sessions; "
             f"median trade return {o['median_ret']:.1%}",
             f"- concentration: top-5 trades = {('n/a (net loss)' if o['top5_share'] != o['top5_share'] else format(o['top5_share'], '.0%') + ' of net profit')}; expectancy without them "
             f"{o['exp_R_ex_top5']:+.3f}R",
             f"- stability: expectancy {o['exp_R_first_half']:+.3f}R before {o['half_split']}, "
             f"{o['exp_R_second_half']:+.3f}R after", "",
             "| Year | Strategy return | Universe equal-weight | Trades | Expectancy R |", "|---|---|---|---|---|"]
        for y, r in extra["by_year"].iterrows():
            d.append(f"| {y} | {r['ret']:.1%} | {byb.get(y, np.nan):.1%} | {int(r['trades']) if r['trades'] == r['trades'] else 0} | "
                     f"{r['exp_R']:+.3f} |")
        detail.append("\n".join(d))
    lines += ["", f"Universe equal-weight benchmark (liquid stocks, daily rebalanced): CAGR "
              f"{bench[-1] ** (1 / nyears) - 1:.1%}, max drawdown {max_dd(bench):.1%}.", ""] + detail

    if a.null:
        lines += ["", f"## Random-entry null ({a.null} seeds; same signals per day, same exits and sizing)", "",
                  "| Screen | Screen expectancy R | Null mean R [5-95%] | Null profit factor | Seeds >= screen |", "|---|---|---|---|---|"]
        for name in a.screens.split(","):
            tr, eq, inv, _ = simulate(M, sigs[name], **kw)
            o, _ = summarize(tr, eq, inv, M, a.capital, name)
            if "win_rate" not in o:
                continue
            r = null_model(df, M, sigs[name], kw, a.null, 70 if name == "vcp" else 60, a.capital)
            lines.append(f"| {name} | {o['expectancy_R']:+.3f} | {r[:, 0].mean():+.3f} [{np.percentile(r[:, 0], 5):+.3f}, "
                         f"{np.percentile(r[:, 0], 95):+.3f}] | {r[:, 1].mean():.2f} | {(r[:, 0] >= o['expectancy_R']).mean():.0%} |")

    if a.sweep:
        lines += ["", "## Sensitivity (same signals; each row changes one setting; for robustness, not for picking winners)",
                  "", HEADER]
        grid = [("stop 6%", dict(stop=0.06)), ("stop 10%", dict(stop=0.10)), ("cost 0.15%/side", dict(cost=0.0015)),
                ("cost 0.5%/side", dict(cost=0.005)), ("max 5 positions", dict(max_pos=5)),
                ("max 20 positions", dict(max_pos=20)), ("risk 1%", dict(risk=0.01))]
        for name in a.screens.split(","):
            for lab, ch in grid:
                tr, eq, inv, _ = simulate(M, sigs[name], **{**kw, **ch})
                o, _ = summarize(tr, eq, inv, M, a.capital, f"{name}: {lab}")
                if "win_rate" in o:
                    lines.append(fmt(o))
        for ma_n, kind in ((20, "sma"), (100, "sma"), (21, "ema")):
            M2 = build_matrices(df, ma_n, kind)
            for name in a.screens.split(","):
                tr, eq, inv, _ = simulate(M2, sigs[name], **kw)
                o, _ = summarize(tr, eq, inv, M2, a.capital, f"{name}: exit {ma_n}-{kind}")
                if "win_rate" in o:
                    lines.append(fmt(o))
    text = "\n".join(lines)
    (RESULTS / f"summary_{a.tag}.md").write_text(text)
    for name, s in sigs.items():
        s.to_csv(RESULTS / f"signals_{name}_{a.tag}.csv", index=False)
    print(text)


if __name__ == "__main__":
    main()
