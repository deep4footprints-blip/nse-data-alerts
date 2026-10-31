# Backtest `v2`

Window: 2022-11-10 to 2026-10-30 (4.0 years, after the 252-session RS warm-up). Capital Rs 1,000,000. Params: risk 0.50%, stop 8%, MA exit 50-sma, max 10 positions, cost 0.30%/side, min turnover Rs 1.0 cr, multi-year vol x1.5.

| Run | Trades | Win rate | Avg win / loss (R) | Expectancy R [90% CI] | Profit factor | CAGR | Max DD | Exposure |
|---|---|---|---|---|---|---|---|---|
| vcp | 366 | 25.1% | 2.89 / -0.90 | +0.052 [-0.141, +0.266] | 1.04 | 1.3% | -24.4% | 63.4% |

Universe equal-weight benchmark (liquid stocks, daily rebalanced): CAGR 16.8%, max drawdown -25.9%.

## vcp
- signals 3492, trades taken 366; median entry gap above pivot 2.2%; stop-outs 46% of trades; avg hold 25 sessions; median trade return -6.6%
- concentration: top-5 trades = 578% of net profit; expectancy without them -0.103R
- stability: expectancy +0.124R before 2024-11-05, -0.021R after

| Year | Strategy return | Universe equal-weight | Trades | Expectancy R |
|---|---|---|---|---|
| 2022 | -6.4% | 1.6% | 17 | -0.694 |
| 2023 | 12.9% | 50.3% | 79 | +0.612 |
| 2024 | 8.4% | 28.0% | 100 | -0.195 |
| 2025 | -0.8% | -4.4% | 84 | +0.149 |
| 2026 | -7.4% | -1.0% | 86 | -0.125 |

## Random-entry null (40 seeds; same signals per day, same exits and sizing)

| Screen | Screen expectancy R | Null mean R [5-95%] | Null profit factor | Seeds >= screen |
|---|---|---|---|---|
| vcp | +0.052 | +0.136 [-0.104, +0.345] | 1.15 | 70% |

## Sensitivity (same signals; each row changes one setting; for robustness, not for picking winners)

| Run | Trades | Win rate | Avg win / loss (R) | Expectancy R [90% CI] | Profit factor | CAGR | Max DD | Exposure |
|---|---|---|---|---|---|---|---|---|
| vcp: stop 6% | 398 | 22.9% | 4.30 / -1.03 | +0.188 [-0.071, +0.462] | 1.17 | 6.9% | -28.8% | 83.3% |
| vcp: stop 10% | 306 | 27.1% | 2.55 / -0.81 | +0.103 [-0.087, +0.314] | 1.14 | 3.1% | -17.4% | 50.7% |
| vcp: cost 0.15%/side | 366 | 25.7% | 2.87 / -0.87 | +0.089 [-0.103, +0.304] | 1.10 | 3.0% | -23.8% | 63.4% |
| vcp: cost 0.5%/side | 366 | 24.3% | 2.93 / -0.94 | +0.001 [-0.191, +0.216] | 0.97 | -0.9% | -26.1% | 63.6% |
| vcp: max 5 positions | 187 | 24.6% | 3.08 / -0.90 | +0.081 [-0.201, +0.372] | 1.07 | 1.2% | -18.8% | 33.0% |
| vcp: max 20 positions | 676 | 24.9% | 2.73 / -0.93 | -0.023 [-0.162, +0.126] | 0.97 | -1.2% | -32.6% | 92.2% |
| vcp: risk 1% | 358 | 24.9% | 3.17 / -0.93 | +0.093 [-0.117, +0.314] | 1.11 | 5.6% | -31.8% | 94.4% |
| vcp: exit 20-sma | 567 | 30.5% | 1.91 / -0.85 | -0.009 [-0.142, +0.125] | 0.95 | -1.8% | -26.1% | 56.9% |
| vcp: exit 100-sma | 216 | 25.9% | 4.23 / -1.02 | +0.344 [-0.040, +0.744] | 1.34 | 7.4% | -24.3% | 68.7% |
| vcp: exit 21-ema | 577 | 27.7% | 2.08 / -0.83 | -0.024 [-0.157, +0.110] | 0.94 | -2.5% | -28.4% | 57.5% |