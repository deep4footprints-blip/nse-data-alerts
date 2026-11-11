#!/usr/bin/env python3
"""Stage 2 -> Stage 3 weekly strategy backtest for nse-data-alerts.

Models:
 A: close > rising 30-week SMA (first weekly transition).
 B: A + top-30% risk-adjusted 6/12m relative strength.
 C: B + 26-week closing-high breakout, 1.5x prior 20w median volume,
    and close no more than 15% above 30-week SMA.

Signals use completed weekly bars; orders execute at next daily open.
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from prices import load_adjusted

MODELS = ("stage_only", "stage_momentum", "stage_momentum_breakout")
LABELS = {
    "stage_only": "A — Stage 2 only",
    "stage_momentum": "B — Stage 2 + momentum",
    "stage_momentum_breakout": "C — Stage 2 + momentum + breakout",
}

def sector_map():
    p = ROOT / "data/universe/nifty500_2026-10-31.csv"
    if not p.exists():
        return {}
    u = pd.read_csv(p, dtype=str)
    sc = next((c for c in ("Industry", "industry", "Sector", "sector") if c in u), None)
    return dict(zip(u.Symbol.str.strip(), u[sc].fillna("Unknown").str.strip())) if sc else {}

def load_daily(min_turn_cr):
    d = load_adjusted(series=("EQ",))
    if d.empty:
        raise RuntimeError("No EQ data found by prices.load_adjusted().")
    required = {"date","symbol","open","high","low","close","volume","turnover_lacs"}
    if required - set(d):
        raise RuntimeError(f"Missing columns: {sorted(required-set(d))}")
    d["date"] = pd.to_datetime(d.date)
    for c in ("open","high","low","close","volume","turnover_lacs"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.drop_duplicates(["symbol","date"], keep="last").sort_values(["symbol","date"]).copy()
    d = d[(d.close > 0) & d.close.notna()].copy()
    g = d.groupby("symbol", sort=False)
    pc = g.close.shift()
    tr = pd.concat([d.high-d.low, (d.high-pc).abs(), (d.low-pc).abs()], axis=1).max(axis=1)
    d["atr14"] = tr.groupby(d.symbol).transform(
        lambda s: s.ewm(alpha=1/14, adjust=False, min_periods=14).mean())
    d["turn_cr"] = d.turnover_lacs / 100.0
    d["med_turn_cr"] = g.turn_cr.transform(lambda s: s.rolling(63, min_periods=40).median())
    d["med20_turn_rs"] = g.turnover_lacs.transform(
        lambda s: s.rolling(20, min_periods=15).median() * 100_000)
    d["liquid"] = d.med_turn_cr >= min_turn_cr
    d["liquid_prev"] = d.groupby("symbol").liquid.shift().fillna(False)
    d["daily_ret"] = d.groupby("symbol").close.pct_change()
    d["sector"] = d.symbol.map(sector_map()).fillna("Unknown")
    return d

def build_weekly(d, min_turn_cr):
    x = d.copy()
    x["week"] = x.date.dt.to_period("W-FRI").dt.end_time.dt.normalize()
    w = x.groupby(["symbol","week"], as_index=False, sort=False).agg(
        open=("open","first"), high=("high","max"), low=("low","min"),
        close=("close","last"), volume=("volume","sum"), last_date=("date","max"),
        atr14=("atr14","last"), med_turn_cr=("med_turn_cr","last"),
        med20_turn_rs=("med20_turn_rs","last"), sector=("sector","last"))
    w = w.sort_values(["symbol","week"]).reset_index(drop=True)

    # Do not use the unfinished current week for signals.
    last = d.date.max()
    week_end = last.to_period("W-FRI").end_time.normalize()
    holidays_path = ROOT / "data/holidays.txt"
    holidays = set(holidays_path.read_text().split()) if holidays_path.exists() else set()
    if last.weekday() != 4 and week_end.strftime("%Y-%m-%d") not in holidays:
        w = w[w.week < week_end].copy()

    g = w.groupby("symbol", sort=False)
    w["sma10"] = g.close.transform(lambda s: s.rolling(10,min_periods=10).mean())
    w["sma30"] = g.close.transform(lambda s: s.rolling(30,min_periods=30).mean())
    w["sma30_5"] = w.groupby("symbol").sma30.shift(5)
    w["sma30_4"] = w.groupby("symbol").sma30.shift(4)
    prev = w.groupby("symbol").close.shift()
    tr = pd.concat([w.high-w.low,(w.high-prev).abs(),(w.low-prev).abs()],axis=1).max(axis=1)
    w["atr10w"] = tr.groupby(w.symbol).transform(
        lambda s:s.ewm(alpha=1/10,adjust=False,min_periods=10).mean())
    w["wret"] = w.groupby("symbol").close.pct_change()
    w["ret26"] = w.groupby("symbol").close.pct_change(26)
    w["ret52"] = w.groupby("symbol").close.pct_change(52)
    w["vol26"] = w.groupby("symbol").wret.transform(
        lambda s:s.rolling(26,min_periods=20).std()*np.sqrt(52))

    # Dynamic equal-weight liquid-EQ benchmark. It is a proxy, not an official TRI.
    liquid_prev = w.groupby("symbol").med_turn_cr.shift() >= min_turn_cr
    br = w.loc[liquid_prev & w.wret.notna()].groupby("week").wret.mean()
    weeks = pd.Index(sorted(w.week.unique()), name="week")
    blevel = (1+br.reindex(weeks).fillna(0)).cumprod()
    b = pd.DataFrame({"week":weeks, "bench":blevel.to_numpy()})
    b["bret26"] = b.bench.pct_change(26)
    b["bret52"] = b.bench.pct_change(52)
    w = w.merge(b,on="week",how="left",validate="many_to_one")
    w["rs6"] = w.ret26-w.bret26
    w["rs12"] = w.ret52-w.bret52
    w["score"] = (.5*w.rs6+.5*w.rs12)/w.vol26.clip(lower=.01)
    w.loc[w.med_turn_cr < min_turn_cr,"score"] = np.nan
    w["rank"] = w.groupby("week").score.rank(pct=True)
    w["prior_high26"] = w.groupby("symbol").close.transform(
        lambda s:s.shift().rolling(26,min_periods=26).max())
    w["prior_vol20"] = w.groupby("symbol").volume.transform(
        lambda s:s.shift().rolling(20,min_periods=15).median())
    ready = w.ret52.notna() & w.bret52.notna() & w.vol26.notna() & w.atr14.notna()
    stage = (w.close>w.sma30)&(w.sma30>w.sma30_5)&ready&(w.med_turn_cr>=min_turn_cr)
    mom = stage & (w["rank"]>=.70)
    breakout = mom & (w.close>w.prior_high26) & (w.volume>=1.5*w.prior_vol20) & ((w.close/w.sma30-1)<=.15)
    for name, q in zip(MODELS,(stage,mom,breakout)):
        w["entry_"+name] = q & ~q.groupby(w.symbol).shift().fillna(False)
    below10 = w.close<w.sma10
    below30 = w.close<w.sma30
    w["stage3"] = below10 & below10.groupby(w.symbol).shift().fillna(False) & (w.sma30<=w.sma30_4)
    w["emergency"] = below30 & below30.groupby(w.symbol).shift().fillna(False)
    return w

def daily_arrays(d):
    dates = pd.DatetimeIndex(sorted(d.date.unique()))
    symbols = np.array(sorted(d.symbol.unique()), dtype=object)
    arrays = {}
    for col in ("open","low","close"):
        p = d.pivot(index="date",columns="symbol",values=col)
        arrays[col] = p.reindex(index=dates,columns=symbols).to_numpy(float)
    return dates,symbols,arrays

def simulate(model,w,dates,symbols,a,start,args):
    O,L,C = a["open"],a["low"],a["close"]
    di = {pd.Timestamp(x):i for i,x in enumerate(dates)}
    si = {s:i for i,s in enumerate(symbols)}
    n,m = O.shape
    entries=[[] for _ in range(n)]; exits=[[] for _ in range(n)]; updates=[[] for _ in range(n)]
    for r in w.itertuples(index=False):
        s=si.get(r.symbol); i=di.get(pd.Timestamp(r.last_date))
        if s is None or i is None: continue
        j=i+1
        if i>=start: updates[i].append((s,r.close,r.atr10w))
        if j>=n: continue
        if getattr(r,"entry_"+model):
            entries[j].append((s,float(r.close),float(r.atr14) if pd.notna(r.atr14) else np.nan,
                               float(r.med20_turn_rs) if pd.notna(r.med20_turn_rs) else 0,
                               float(r.score) if pd.notna(r.score) else -np.inf,
                               float(r["rank"]) if False else (float(r.rank) if pd.notna(r.rank) else 0),
                               str(r.sector),pd.Timestamp(r.last_date)))
        if r.emergency or r.stage3:
            exits[j].append((s,"emergency_2w_below_30w" if r.emergency else "stage3_2w_below_10w"))

    cash=float(args.capital); pos={}; trades=[]; eq=np.full(n,np.nan); exp=np.full(n,np.nan)
    marks=np.full(m,np.nan); skipped=dict(gap=0,open=0,atr=0,capacity=0,sizing=0); signals=0
    def close_pos(s,px,t,reason):
        nonlocal cash
        p=pos.pop(s); proceeds=p["shares"]*px*(1-args.cost)
        cash+=proceeds; pnl=proceeds-p["entry_cost"]
        trades.append(dict(model=model,symbol=symbols[s],sector=p["sector"],
            signal_date=p["signal_date"].date(),entry_date=dates[p["entry_i"]].date(),
            exit_date=dates[t].date(),entry_price=p["entry"],exit_price=px,shares=p["shares"],
            pnl_net=pnl,return_net=pnl/p["entry_cost"],R_multiple=pnl/p["risk_cash"],
            holding_days=t-p["entry_i"],exit_reason=reason,momentum_rank=p["rank"],score=p["score"]))
    for t in range(start,n):
        exited=set()
        for s,reason in exits[t]:
            if s in pos: pos[s]["pending"]=reason
        for s,p in list(pos.items()):
            if p.get("pending") and np.isfinite(O[t,s]):
                close_pos(s,O[t,s],t,p["pending"]); exited.add(s)
        for s,p in list(pos.items()):
            stop=max(p["stop"],p["trail"])
            if np.isfinite(O[t,s]) and O[t,s]<=stop:
                close_pos(s,O[t,s],t,"stop_gap"); exited.add(s)
            elif np.isfinite(L[t,s]) and L[t,s]<=stop:
                close_pos(s,stop,t,"initial_or_trailing_stop"); exited.add(s)
        for e in sorted(entries[t],key=lambda z:z[4],reverse=True):
            signals+=1
            s,signal_close,atr,turnover,score,rank,sector,signal_date=e
            if s in pos or s in exited: skipped["capacity"]+=1; continue
            op=O[t,s]
            if not np.isfinite(op) or op<=0: skipped["open"]+=1; continue
            if op/signal_close-1>args.max_gap: skipped["gap"]+=1; continue
            if not np.isfinite(atr) or atr<=0: skipped["atr"]+=1; continue
            dist=2.5*atr; stop=op-dist
            if stop<=0: skipped["atr"]+=1; continue
            marked=np.where(np.isfinite(O[t]),O[t],marks)
            mv=sum(p["shares"]*(marked[s0] if np.isfinite(marked[s0]) else p["entry"]) for s0,p in pos.items())
            nav=cash+mv
            if len(pos)>=args.max_positions or nav<=0: skipped["capacity"]+=1; continue
            secval=sum(p["shares"]*(marked[s0] if np.isfinite(marked[s0]) else p["entry"])
                       for s0,p in pos.items() if p["sector"]==sector)
            secroom=max(0,nav*args.sector_cap-secval)
            shares=min(int(nav*args.risk/dist),int(nav*args.max_stock/op),
                       int(secroom/op),int(cash/(op*(1+args.cost))),
                       int(args.participation*turnover/op))
            if shares<1: skipped["sizing"]+=1; continue
            entry_cost=shares*op*(1+args.cost); cash-=entry_cost
            pos[s]=dict(shares=shares,entry=op,entry_cost=entry_cost,entry_i=t,
                signal_date=signal_date,stop=stop,trail=-np.inf,high_close=op,
                risk_cash=shares*dist,sector=sector,rank=rank,score=score)
            if np.isfinite(L[t,s]) and L[t,s]<=stop:
                close_pos(s,op if op<=stop else stop,t,"entry_day_stop"); exited.add(s)
        good=np.isfinite(C[t]); marks[good]=C[t,good]
        for s,weekly_close,atr10 in updates[t]:
            if s in pos and pd.notna(atr10) and atr10>0:
                pos[s]["high_close"]=max(pos[s]["high_close"],weekly_close)
                pos[s]["trail"]=pos[s]["high_close"]-3*atr10
        total=cash; invested=0
        for s,p in pos.items():
            px=marks[s] if np.isfinite(marks[s]) else p["entry"]
            v=p["shares"]*px; total+=v; invested+=v
        eq[t]=total; exp[t]=invested/total if total>0 else 0
    open_rows=[]
    for s,p in pos.items():
        px=marks[s] if np.isfinite(marks[s]) else p["entry"]
        open_rows.append(dict(model=model,symbol=symbols[s],sector=p["sector"],
            entry_date=dates[p["entry_i"]].date(),entry_price=p["entry"],last_price=px,
            shares=p["shares"],market_value=p["shares"]*px,initial_stop=p["stop"],trailing_stop=p["trail"]))
    return dict(equity=eq,exposure=exp,trades=pd.DataFrame(trades),
                open=pd.DataFrame(open_rows),signals=signals,skipped=skipped)

def mdd(x):
    return float(np.min(x/np.maximum.accumulate(x)-1)) if len(x) else np.nan

def metrics(name,res,dates,start,args):
    e=res["equity"][start:]; e=e[np.isfinite(e)]
    t=res["trades"]; years=max((dates[-1]-dates[start]).days/365.25,1/365.25)
    dr=pd.Series(e).pct_change().dropna()
    wins=t[t.pnl_net>0] if len(t) else t; losses=t[t.pnl_net<=0] if len(t) else t
    gl=-losses.pnl_net.sum() if len(losses) else 0
    dd=mdd(e); cagr=(e[-1]/e[0])**(1/years)-1 if len(e)>1 else np.nan
    return dict(model=name,trades=len(t),signals=res["signals"],CAGR=cagr,
        total_return=e[-1]/e[0]-1 if len(e)>1 else np.nan,max_drawdown=dd,
        Sharpe=dr.mean()/dr.std()*np.sqrt(252) if dr.std()>0 else np.nan,
        Calmar=cagr/abs(dd) if dd<0 else np.nan,
        win_rate=len(wins)/len(t) if len(t) else np.nan,
        profit_factor=wins.pnl_net.sum()/gl if gl>0 else np.nan,
        expectancy_R=t.R_multiple.mean() if len(t) else np.nan,
        median_trade_return=t.return_net.median() if len(t) else np.nan,
        avg_holding_days=t.holding_days.mean() if len(t) else np.nan,
        exposure=np.nanmean(res["exposure"][start:]),open_positions=len(res["open"]),
        **{"skip_"+k:v for k,v in res["skipped"].items()})

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--models",default="all")
    p.add_argument("--capital",type=float,default=1_000_000)
    p.add_argument("--risk",type=float,default=.005)
    p.add_argument("--max-positions",type=int,default=10)
    p.add_argument("--max-stock",type=float,default=.10)
    p.add_argument("--sector-cap",type=float,default=.25)
    p.add_argument("--participation",type=float,default=.05)
    p.add_argument("--cost",type=float,default=.003)
    p.add_argument("--max-gap",type=float,default=.05)
    p.add_argument("--min-turn-cr",type=float,default=1.0)
    args=p.parse_args()
    if args.capital<=0 or args.max_positions<1: p.error("capital must be positive and max-positions >= 1")
    d=load_daily(args.min_turn_cr); w=build_weekly(d,args.min_turn_cr)
    dates,symbols,a=daily_arrays(d)
    warm=w.loc[w.bret52.notna(),"last_date"]
    if warm.empty: raise RuntimeError("Insufficient 52-week warm-up history.")
    start=int(np.searchsorted(dates.to_numpy(),np.datetime64(pd.Timestamp(warm.min()))))
    if start>=len(dates)-1: raise RuntimeError("Insufficient data after warm-up.")
    selected=list(MODELS) if args.models=="all" else [x.strip() for x in args.models.split(",")]
    if set(selected)-set(MODELS): p.error(f"Unknown models: {set(selected)-set(MODELS)}")
    OUT.mkdir(exist_ok=True)
    all_results={}; rows=[]
    for model in selected:
        r=simulate(model,w,dates,symbols,a,start,args); all_results[model]=r
        rows.append(metrics(model,r,dates,start,args))
        r["trades"].to_csv(OUT/f"stage2_trades_{model}.csv",index=False)
        r["open"].to_csv(OUT/f"stage2_open_positions_{model}.csv",index=False)
    # Price-return equal-weight proxy: prior-session liquid securities.
    b=d[d.liquid_prev & d.daily_ret.notna()].groupby("date").daily_ret.mean().reindex(dates).fillna(0).to_numpy()
    beq=args.capital*np.cumprod(1+b); beq=beq[start:]
    br=pd.Series(beq).pct_change().dropna(); bd=mdd(beq)
    by=max((dates[-1]-dates[start]).days/365.25,1/365.25)
    bc=(beq[-1]/beq[0])**(1/by)-1
    rows.append(dict(model="benchmark_equal_weight_liquid_eq",trades=0,signals=0,CAGR=bc,
        total_return=beq[-1]/beq[0]-1,max_drawdown=bd,
        Sharpe=br.mean()/br.std()*np.sqrt(252) if br.std()>0 else np.nan,
        Calmar=bc/abs(bd) if bd<0 else np.nan,win_rate=np.nan,profit_factor=np.nan,
        expectancy_R=np.nan,median_trade_return=np.nan,avg_holding_days=np.nan,exposure=1.0,open_positions=0))
    pd.DataFrame(rows).to_csv(OUT/"stage2_metrics.csv",index=False)
    eq=pd.DataFrame({"date":dates[start:],"benchmark_equal_weight_liquid_eq":beq})
    for model,r in all_results.items(): eq[model]=r["equity"][start:]
    eq.to_csv(OUT/"stage2_equity.csv",index=False)
    summary=["# Stage 2 → Stage 3 backtest","",f"Window: {dates[start].date()} to {dates[-1].date()}",
        f"Symbols: {d.symbol.nunique():,}; daily rows: {len(d):,}; weekly bars: {len(w):,}",
        f"Capital Rs {args.capital:,.0f}; per-side cost {args.cost:.2%}; risk/trade {args.risk:.2%}.","",
        "| Model | Trades | CAGR | Max DD | Sharpe | Calmar | Win rate | PF | Expectancy R | Exposure |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        label=LABELS.get(r["model"],"Equal-weight liquid-EQ proxy")
        f=lambda v:"n/a" if pd.isna(v) else f"{v:.1%}"
        n=lambda v:"n/a" if pd.isna(v) else f"{v:.2f}"
        summary.append(f"| {label} | {r['trades']} | {f(r['CAGR'])} | {f(r['max_drawdown'])} | {n(r['Sharpe'])} | {n(r['Calmar'])} | {f(r['win_rate'])} | {n(r['profit_factor'])} | {n(r['expectancy_R'])} | {f(r['exposure'])} |")
    summary += ["","## Rules","",
        "- A: first weekly close above a rising 30-week SMA.",
        "- B: A plus top-30% risk-adjusted 6/12-month relative strength versus the liquid-EQ proxy.",
        "- C: B plus 26-week closing-high breakout, weekly volume >=1.5x prior 20-week median, and <=15% extension above 30-week SMA.",
        "- Stage 3: two weekly closes below 10-week SMA while 30-week SMA is flat/down vs four weeks ago; next-session open exit.",
        "- Emergency exit: two weekly closes below 30-week SMA; next-session open exit.",
        "- Initial stop 2.5x daily ATR(14); trailing stop highest weekly close minus 3x weekly ATR(10).",
        "- Risk 0.5% equity/trade; max 10% stock, 25% sector, 10 positions; 5% median daily turnover participation; 0.3% cost/side; skip >5% positive opening gap.",
        "","## Caveats","",
        "- Universe is all EQ securities in the available archive, filtered point-in-time by 63-session median turnover >= Rs "
        f"{args.min_turn_cr:.2f} crore. Not historical Nifty 200 constituents.",
        "- Benchmark is a dynamic equal-weight liquid-EQ price-return proxy, not Nifty 200 TRI/Nifty 500 TRI.",
        "- Current Nifty 500 sector labels are used retrospectively for sector caps; unmatched symbols are Unknown.",
        "- Uses repository price adjustments: split/bonus adjusted; dividends and rights not adjusted; demerger estimates may be approximate.",
        "- Archive begins in 2019; 52-week warm-up means the test begins around 2020. No 2010-2019 results.",
        "- This is an exploratory backtest; no optimisation or walk-forward validation is included."]
    (OUT/"stage2_summary.md").write_text("\n".join(summary)+"\n")
    print("\n".join(summary))
    print(f"\nResults written to {OUT}")

if __name__=="__main__": main()
