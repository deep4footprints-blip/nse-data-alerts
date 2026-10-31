# Backtest `run`

Window: 2022-11-10 to 2026-10-30 (4.0 years, after the 252-session RS warm-up). Capital Rs 1,000,000. Params: risk 0.50%, stop 8%, MA exit 50-sma, max 10 positions, cost 0.30%/side, min turnover Rs 1.0 cr, multi-year vol x1.5.

| Run | Trades | Win rate | Avg win / loss (R) | Expectancy R [90% CI] | Profit factor | CAGR | Max DD | Exposure |
|---|---|---|---|---|---|---|---|---|
| vcp | 361 | 22.2% | 2.77 / -0.95 | -0.123 [-0.298, +0.070] | 0.83 | -5.5% | -32.0% | 60.8% |
| multi | 198 | 33.8% | 3.95 / -0.80 | +0.805 [+0.295, +1.379] | 2.10 | 17.0% | -16.7% | 63.4% |

Universe equal-weight benchmark (liquid stocks, daily rebalanced): CAGR 15.9%, max drawdown -26.0%.

## vcp
- signals 2410, trades taken 361; median entry gap above pivot 2.6%; stop-outs 53% of trades; avg hold 25 sessions; median trade return -8.0%
- concentration: top-5 trades = n/a (net loss); expectancy without them -0.277R
- stability: expectancy +0.025R before 2024-11-05, -0.247R after

| Year | Strategy return | Universe equal-weight | Trades | Expectancy R |
|---|---|---|---|---|
| 2022 | -5.5% | 1.4% | 21 | -0.483 |
| 2023 | 9.6% | 49.4% | 76 | +0.398 |
| 2024 | -5.2% | 27.0% | 89 | -0.358 |
| 2025 | -9.1% | -5.2% | 98 | -0.104 |
| 2026 | -10.4% | -1.7% | 77 | -0.291 |
## multi
- signals 3632, trades taken 198; median entry gap above pivot 2.7%; stop-outs 35% of trades; avg hold 47 sessions; median trade return -3.6%
- concentration: top-5 trades = 79% of net profit; expectancy without them +0.157R
- stability: expectancy +1.130R before 2024-11-05, +0.271R after

| Year | Strategy return | Universe equal-weight | Trades | Expectancy R |
|---|---|---|---|---|
| 2022 | -0.3% | 1.4% | 15 | -0.311 |
| 2023 | 62.0% | 49.4% | 57 | +2.447 |
| 2024 | 7.2% | 27.0% | 64 | +0.004 |
| 2025 | 10.5% | -5.2% | 41 | +0.774 |
| 2026 | -2.3% | -1.7% | 21 | -0.356 |

## Random-entry null (40 seeds; same signals per day, same exits and sizing)

| Screen | Screen expectancy R | Null mean R [5-95%] | Null profit factor | Seeds >= screen |
|---|---|---|---|---|
| vcp | -0.123 | +0.191 [-0.009, +0.538] | 1.24 | 100% |
| multi | +0.805 | +0.200 [+0.020, +0.379] | 1.25 | 0% |

## Sensitivity (same signals; each row changes one setting; for robustness, not for picking winners)

| Run | Trades | Win rate | Avg win / loss (R) | Expectancy R [90% CI] | Profit factor | CAGR | Max DD | Exposure |
|---|---|---|---|---|---|---|---|---|
| vcp: stop 6% | 442 | 19.9% | 3.82 / -1.06 | -0.089 [-0.301, +0.147] | 0.89 | -5.3% | -37.4% | 82.0% |
| vcp: stop 10% | 327 | 26.0% | 2.18 / -0.84 | -0.053 [-0.231, +0.134] | 0.90 | -2.3% | -26.0% | 49.7% |
| vcp: cost 0.15%/side | 361 | 22.4% | 2.78 / -0.91 | -0.085 [-0.261, +0.108] | 0.87 | -3.9% | -30.5% | 60.7% |
| vcp: cost 0.5%/side | 361 | 21.3% | 2.83 / -0.99 | -0.173 [-0.348, +0.020] | 0.78 | -7.4% | -35.4% | 61.1% |
| vcp: max 5 positions | 180 | 21.7% | 2.97 / -0.96 | -0.106 [-0.363, +0.181] | 0.86 | -2.4% | -19.3% | 32.1% |
| vcp: max 20 positions | 630 | 23.8% | 2.34 / -0.96 | -0.177 [-0.307, -0.038] | 0.78 | -10.1% | -45.0% | 90.4% |
| vcp: risk 1% | 353 | 21.8% | 2.83 / -0.95 | -0.123 [-0.305, +0.073] | 0.88 | -5.5% | -37.7% | 92.4% |
| multi: stop 6% | 250 | 29.2% | 4.71 / -0.94 | +0.714 [+0.249, +1.250] | 1.82 | 19.0% | -20.4% | 83.4% |
| multi: stop 10% | 183 | 35.0% | 3.51 / -0.69 | +0.780 [+0.318, +1.278] | 2.34 | 15.5% | -15.3% | 51.6% |
| multi: cost 0.15%/side | 198 | 33.8% | 3.99 / -0.77 | +0.843 [+0.333, +1.418] | 2.22 | 18.1% | -16.0% | 63.3% |
| multi: cost 0.5%/side | 198 | 33.8% | 3.89 / -0.85 | +0.753 [+0.244, +1.326] | 1.96 | 15.8% | -17.8% | 63.6% |
| multi: max 5 positions | 99 | 33.3% | 4.42 / -0.81 | +0.936 [+0.138, +1.882] | 2.27 | 10.5% | -11.1% | 34.0% |
| multi: max 20 positions | 406 | 35.7% | 3.17 / -0.80 | +0.620 [+0.327, +0.935] | 1.84 | 21.6% | -21.7% | 92.9% |
| multi: risk 1% | 201 | 34.8% | 3.42 / -0.79 | +0.675 [+0.236, +1.181] | 1.87 | 24.4% | -23.4% | 95.5% |
| vcp: exit 20-sma | 546 | 28.6% | 1.70 / -0.89 | -0.151 [-0.274, -0.017] | 0.76 | -9.0% | -43.3% | 54.7% |
| multi: exit 20-sma | 327 | 34.6% | 1.43 / -0.65 | +0.068 [-0.079, +0.234] | 1.16 | 2.6% | -17.1% | 53.0% |
| vcp: exit 100-sma | 223 | 19.7% | 3.74 / -0.96 | -0.031 [-0.319, +0.292] | 0.92 | -1.7% | -29.1% | 65.5% |
| multi: exit 100-sma | 123 | 35.0% | 6.77 / -0.91 | +1.775 [+0.560, +3.318] | 2.89 | 21.6% | -15.0% | 70.9% |
| vcp: exit 21-ema | 520 | 27.5% | 1.90 / -0.86 | -0.098 [-0.224, +0.035] | 0.83 | -6.0% | -39.7% | 55.0% |
| multi: exit 21-ema | 297 | 36.4% | 1.57 / -0.64 | +0.166 [-0.007, +0.367] | 1.38 | 5.8% | -12.8% | 54.7% |