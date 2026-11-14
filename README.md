# Stage 2 → Stage 3 backtest bundle

Copy `scripts/stage2_backtest.py` into the repository's `scripts/` folder.

Run from repository root:

```bash
python scripts/stage2_backtest.py
```

Optional:
```bash
python scripts/stage2_backtest.py --models stage_momentum,stage_momentum_breakout
python scripts/stage2_backtest.py --min-turn-cr 2.0 --cost 0.005
python scripts/stage2_backtest.py --capital 1000000 --risk 0.005 --max-positions 10
```

Outputs in `results/`:
- `stage2_summary.md`
- `stage2_metrics.csv`
- `stage2_equity.csv`
- `stage2_trades_<model>.csv`
- `stage2_open_positions_<model>.csv`

## Three models
A. Stage 2: weekly close above a rising 30-week SMA.
B. A + top-30% risk-adjusted 6/12-month relative strength.
C. B + 26-week closing-high breakout, 1.5x prior 20-week median volume, and <=15% extension above 30-week SMA.

Common exits: two weekly closes below 10-week SMA with 30-week SMA flat/down; emergency exit after two closes below 30-week SMA. Initial stop 2.5x daily ATR(14); trailing stop highest weekly close less 3x weekly ATR(10).

## Important limitations
- Uses all EQ symbols in the archive and a point-in-time 63-session median-turnover filter; it is not a historical Nifty 200 universe.
- Benchmark is an equal-weight liquid-EQ price-return proxy, not Nifty 200 TRI.
- Existing price adjustment caveats remain: dividends/rights not adjusted and demerger estimates may be approximate.
- Archive begins in 2019; the 52-week warm-up means the actual test starts around 2020.
- Treat output as exploratory until independently validated.

## App bundles
`python scripts/build_app_bundles.py` writes `data/app/dead.json` (adjusted bars of stocks that stopped trading, with renames linked to the new ticker), `data/app/audit_ref.json` (month-end adjusted closes of live stocks) and `data/app/meta.json`. The daily workflow runs it after the bhavcopy update; the Market Pulse app downloads them from raw.githubusercontent.com.
