# Backtest `s7`

Window: 2020-10-07 to 2026-10-30 (6.1 years, after the 252-session RS warm-up). Capital Rs 1,000,000. Params: risk 0.50%, stop 8%, MA exit 50-sma, max 10 positions, cost 0.30%/side, min turnover Rs 1.0 cr, multi-year vol x1.5.

| Run | Trades | Win rate | Avg win / loss (R) | Expectancy R [90% CI] | Profit factor | CAGR | Max DD | Exposure |
|---|---|---|---|---|---|---|---|---|
| vcp | 458 | 26.2% | 3.96 / -0.98 | +0.313 [+0.012, +0.668] | 1.26 | 9.4% | -25.9% | 61.8% |
| multi | 267 | 32.6% | 3.36 / -0.85 | +0.520 [+0.156, +0.945] | 1.73 | 9.1% | -17.3% | 49.2% |

Universe equal-weight benchmark (liquid stocks, daily rebalanced): CAGR 23.7%, max drawdown -26.0%.

## vcp
- signals 3578, trades taken 458; median entry gap above pivot 2.6%; stop-outs 53% of trades; avg hold 30 sessions; median trade return -8.0%
- concentration: top-5 trades = 114% of net profit; expectancy without them +0.039R
- stability: expectancy +0.971R before 2023-10-17, -0.153R after

| Year | Strategy return | Universe equal-weight | Trades | Expectancy R |
|---|---|---|---|---|
| 2020 | 15.4% | 21.8% | 20 | +4.595 |
| 2021 | 41.0% | 61.0% | 49 | +1.528 |
| 2022 | 3.8% | 4.5% | 68 | -0.153 |
| 2023 | 20.9% | 49.4% | 70 | +0.602 |
| 2024 | 2.6% | 27.0% | 76 | -0.295 |
| 2025 | -8.4% | -5.2% | 98 | -0.104 |
| 2026 | -10.3% | -1.7% | 77 | -0.291 |
## multi
- signals 4015, trades taken 267; median entry gap above pivot 2.9%; stop-outs 40% of trades; avg hold 41 sessions; median trade return -4.4%
- concentration: top-5 trades = 85% of net profit; expectancy without them +0.094R
- stability: expectancy +0.813R before 2023-10-17, +0.215R after

| Year | Strategy return | Universe equal-weight | Trades | Expectancy R |
|---|---|---|---|---|
| 2020 | 2.5% | 21.8% | 3 | +1.601 |
| 2021 | 0.2% | 61.0% | 1 | +0.255 |
| 2022 | -4.3% | 4.5% | 77 | -0.179 |
| 2023 | 48.0% | 49.4% | 60 | +2.051 |
| 2024 | 7.9% | 27.0% | 64 | +0.004 |
| 2025 | 10.6% | -5.2% | 41 | +0.774 |
| 2026 | -2.3% | -1.7% | 21 | -0.356 |

## Random-entry null (40 seeds; same signals per day, same exits and sizing)

| Screen | Screen expectancy R | Null mean R [5-95%] | Null profit factor | Seeds >= screen |
|---|---|---|---|---|
| vcp | +0.313 | +0.331 [+0.148, +0.552] | 1.39 | 50% |
| multi | +0.520 | +0.102 [-0.050, +0.256] | 1.11 | 0% |

## Sensitivity (same signals; each row changes one setting; for robustness, not for picking winners)

| Run | Trades | Win rate | Avg win / loss (R) | Expectancy R [90% CI] | Profit factor | CAGR | Max DD | Exposure |
|---|---|---|---|---|---|---|---|---|
| vcp: stop 6% | 409 | 24.7% | 4.84 / -1.11 | +0.361 [+0.062, +0.670] | 1.29 | 9.4% | -26.9% | 67.9% |
| vcp: stop 10% | 404 | 30.4% | 3.41 / -0.85 | +0.443 [+0.148, +0.782] | 1.46 | 12.4% | -19.2% | 51.6% |
| vcp: cost 0.15%/side | 458 | 26.4% | 3.97 / -0.95 | +0.351 [+0.049, +0.706] | 1.31 | 10.7% | -24.5% | 61.7% |
| vcp: cost 0.5%/side | 458 | 25.5% | 4.00 / -1.02 | +0.263 [-0.038, +0.616] | 1.20 | 7.6% | -29.4% | 61.9% |
| vcp: max 5 positions | 199 | 27.1% | 5.18 / -0.96 | +0.708 [+0.118, +1.460] | 1.68 | 10.2% | -23.6% | 33.6% |
| vcp: max 20 positions | 747 | 26.6% | 3.53 / -1.00 | +0.204 [-0.004, +0.438] | 1.16 | 8.1% | -37.1% | 90.7% |
| vcp: risk 1% | 444 | 27.0% | 4.04 / -0.99 | +0.371 [+0.054, +0.744] | 1.26 | 16.8% | -34.4% | 92.6% |
| multi: stop 6% | 332 | 28.3% | 4.18 / -0.98 | +0.481 [+0.117, +0.909] | 1.56 | 10.0% | -23.2% | 64.5% |
| multi: stop 10% | 247 | 34.0% | 2.86 / -0.74 | +0.485 [+0.155, +0.847] | 1.85 | 8.2% | -15.5% | 39.8% |
| multi: cost 0.15%/side | 267 | 33.0% | 3.37 / -0.82 | +0.558 [+0.194, +0.984] | 1.83 | 9.9% | -16.6% | 49.1% |
| multi: cost 0.5%/side | 267 | 32.2% | 3.35 / -0.90 | +0.469 [+0.105, +0.893] | 1.61 | 8.0% | -18.1% | 49.3% |
| multi: max 5 positions | 145 | 31.0% | 3.39 / -0.86 | +0.460 [-0.035, +1.064] | 1.64 | 4.7% | -12.8% | 26.9% |
| multi: max 20 positions | 494 | 34.8% | 2.85 / -0.83 | +0.452 [+0.215, +0.711] | 1.64 | 11.9% | -20.9% | 70.7% |
| multi: risk 1% | 266 | 33.1% | 3.26 / -0.85 | +0.506 [+0.148, +0.906] | 1.61 | 12.5% | -32.0% | 75.3% |
| vcp: exit 20-sma | 681 | 32.3% | 2.29 / -0.94 | +0.104 [-0.039, +0.252] | 1.14 | 5.7% | -35.2% | 53.8% |
| multi: exit 20-sma | 416 | 35.1% | 1.47 / -0.68 | +0.072 [-0.060, +0.210] | 1.15 | 2.3% | -17.1% | 41.0% |
| vcp: exit 100-sma | 282 | 23.4% | 6.32 / -1.00 | +0.711 [+0.172, +1.315] | 1.50 | 12.5% | -29.5% | 67.4% |
| multi: exit 100-sma | 187 | 29.9% | 4.46 / -0.94 | +0.680 [+0.099, +1.348] | 1.80 | 8.3% | -19.0% | 54.1% |
| vcp: exit 21-ema | 671 | 31.1% | 2.47 / -0.91 | +0.145 [-0.011, +0.312] | 1.16 | 6.8% | -36.5% | 54.3% |
| multi: exit 21-ema | 382 | 36.4% | 1.61 / -0.68 | +0.153 [+0.005, +0.320] | 1.33 | 4.4% | -13.7% | 42.3% |