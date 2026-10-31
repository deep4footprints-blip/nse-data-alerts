# VCP screen - what we replicate and how well it matches

Source: the BananaPatterns VCP screen preset and its built-in backtester, read from a logged-in free-trial session
on 30-31 Oct 2026 (data as of 30/10/2026). Thresholds below are the preset's filter values; no site data is stored here.

## Preset filters (all measured at the close BEFORE the breakout day)
| Filter | Site value | Ours |
|---|---|---|
| Median turnover (20 sessions) | >= Rs 1 cr | same (we use NSE only; the site adds BSE) |
| Market cap | >= Rs 300 cr | NOT applied (no market-cap data) |
| RS rating | >= 70 | >= 70 (our own composite; the site's formula is unpublished) |
| Price vs 50-DMA, 200-DMA | >= 0 | close >= SMA50, SMA200 |
| From 52-week high | <= 30% | <= 30% below 52w high (intraday highs) |
| Above 52-week low | >= 15% | >= 15% above 52w low (intraday lows) |
| Base age | >= 3 weeks | >= 15 sessions |
| Base max depth | <= 35% | pivot to lowest low in base <= 35% |
| Tightening (ATR ratio) | <= 0.9 (ATR% 2nd half / 1st half) | mean(TR/close) 2nd half / 1st half |
| Volume dry-up | <= 0.9 (volume 2nd half / 1st half) | mean volume 2nd half / 1st half |

Breakout = a close above the pivot (highest close of the base). Bases are nested: every earlier close that is the highest
close since then is a candidate pivot, so one stock can break out of several bases on the same day.

## Site backtester defaults (for comparison)
Stop 8% below entry, exit on a close below the 50-day average (only after a first close above it), cost 0.25% per order,
risk 1% per trade, 10 positions, 30% position cap, 10% of median turnover, by-risk sizing, ranked by RS when the book is full.
Entry option "as it breaks out" = buy at the pivot intraday (or the open if it gaps above); "next morning's open" = ours.

## Calibration results
Same window (10 Nov 2022 - 30 Sep 2026), same rules (next-open entry, 0.5% risk, 8% stop, 50-SMA exit, 0.30% cost, 20% cap, 5% turnover):

| | Trades | Win rate | Avg win / loss | PF | CAGR | Worst DD |
|---|---|---|---|---|---|---|
| Site backtester | 367 | 27.2% | +26.6% / -7.7% | 1.30 | 5.9% | -25.7% |
| Ours (this repo) | 366 | 25.1% | 2.89R / -0.90R | 1.04 | 1.3% | -24.4% |

Site, same window, buy at the pivot intraday: 403 trades, PF 1.36, CAGR 8.2%. Nifty 500 over the window: 1.41-1.43x.
Site, 2016-2026, risk 1%, 10 positions: pivot entry 31.4% CAGR / PF 2.22 (841 trades); next-open entry 17.3% CAGR / PF 1.54 (758 trades).

Last-week check (fresh VCP breakouts 26-30 Oct): site 3 names, ours 2 of them (the third fails our ATR/volume ratios).
Forming names on 30 Oct: site 13; 6 of these are inside our universe/RS set and we find 5 of the 6. We also flag ~9 names the site does not
(probable causes: RS formula differences, the market-cap floor, BSE/T2T names the site includes and we do not).
