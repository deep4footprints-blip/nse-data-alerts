# Stage 2 → Stage 3 backtest

Window: 2020-09-23 to 2026-11-09
Symbols: 3,500; daily rows: 3,246,004; weekly bars: 692,291
Capital Rs 1,000,000; per-side cost 0.30%; risk/trade 0.50%.

| Model | Trades | CAGR | Max DD | Sharpe | Calmar | Win rate | PF | Expectancy R | Exposure |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A — Stage 2 only | 165 | 13.1% | -16.9% | 1.29 | 0.77 | 33.3% | 2.32 | 1.10 | 43.4% |
| B — Stage 2 + momentum | 165 | 13.1% | -16.9% | 1.29 | 0.77 | 33.3% | 2.32 | 1.10 | 43.4% |
| C — Stage 2 + momentum + breakout | 121 | 6.1% | -12.8% | 0.76 | 0.48 | 30.6% | 1.81 | 0.53 | 51.1% |
| Equal-weight liquid-EQ proxy | 0 | 24.9% | -27.2% | 1.30 | 0.91 | n/a | n/a | n/a | 100.0% |

## Rules

- A: first weekly close above a rising 30-week SMA.
- B: A plus top-30% risk-adjusted 6/12-month relative strength versus the liquid-EQ proxy.
- C: B plus 26-week closing-high breakout, weekly volume >=1.5x prior 20-week median, and <=15% extension above 30-week SMA.
- Stage 3: two weekly closes below 10-week SMA while 30-week SMA is flat/down vs four weeks ago; next-session open exit.
- Emergency exit: two weekly closes below 30-week SMA; next-session open exit.
- Initial stop 2.5x daily ATR(14); trailing stop highest weekly close minus 3x weekly ATR(10).
- Risk 0.5% equity/trade; max 10% stock, 25% sector, 10 positions; 5% median daily turnover participation; 0.3% cost/side; skip >5% positive opening gap.

## Caveats

- Universe is all EQ securities in the available archive, filtered point-in-time by 63-session median turnover >= Rs 1.00 crore. Not historical Nifty 200 constituents.
- Benchmark is a dynamic equal-weight liquid-EQ price-return proxy, not Nifty 200 TRI/Nifty 500 TRI.
- Current Nifty 500 sector labels are used retrospectively for sector caps; unmatched symbols are Unknown.
- Uses repository price adjustments: split/bonus adjusted; dividends and rights not adjusted; demerger estimates may be approximate.
- Archive begins in 2019; 52-week warm-up means the test begins around 2020. No 2010-2019 results.
- This is an exploratory backtest; no optimisation or walk-forward validation is included.
