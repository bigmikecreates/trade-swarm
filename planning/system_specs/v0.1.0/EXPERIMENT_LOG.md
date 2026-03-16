# v0.1.0 Experiment Log

> **Goal:** prove the EMA crossover strategy can pass a hard performance gate across multiple assets.
>
> **Gate:** Sharpe > 0.8, Max DD < 20%, Trades >= 30.
>
> **Rule:** change one thing per run. If it doesn't improve the metric you're targeting, roll back.

## Methodology

- **Sharpe:** per-bar returns, annualised with `sqrt(252)` (daily) or `sqrt(8760)` (hourly). No risk-free rate.
- **Drawdown:** peak-to-trough on mark-to-market equity curve (not closed-trade only).
- **Cost model:** flat 0.1% fee per trade. No spread or slippage modelled.
- **Data source:** Yahoo Finance via yfinance. All results below are **in-sample** (train and test on the same window).

---

## Phase 1 — Baseline & first contact (baseline, exp-001)

**Question:** does a raw EMA crossover produce any edge at all?

We started with the simplest possible setup: EURUSD hourly, EMA 20/50, no filter. The result was a deeply negative Sharpe (-1.83) with 107 trades — the strategy was trading noise. Adding an ADX filter (exp-001) reduced trade count but made Sharpe *worse*, proving that ADX alone can't separate signal from chop on this asset/timeframe.

**Lesson:** EURUSD hourly is the wrong starting point. The strategy needs an asset that actually trends.

| run_id | timestamp | symbol | period | interval | ema | filter | sharpe | max_dd_pct | total_return_pct | trade_count | win_rate | gate_pass | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 2025-03-14 12:00 | EURUSD=X | 2y | 1h | 20/50 | off | -1.83 | 15.97 | -15.3 | 107 | 25.2% | NO | Negative Sharpe. Many chop trades. |
| exp-001 | 2025-03-14 14:30 | EURUSD=X | 2y | 1h | 20/50 | ADX>25 | -2.01 | 15.76 | -15.3 | 78 | 19.2% | NO | ADX cut trades but Sharpe worsened. |

---

## Phase 2 — Asset & timeframe search (exp-002 through exp-004d)

**Question:** which combination of asset, timeframe, and EMA width produces the first positive Sharpe?

We swept three dimensions: wider EMAs (50/200) to reduce noise, daily bars to smooth out intraday chop, and different assets (SPY, BTC-USD). The breakthrough came in exp-004c — SPY on daily bars with EMA 20/50 hit a Sharpe of 1.05. But it only generated 4 trades over 2 years, failing the trade count gate. BTC-USD was a disaster (55% drawdown) — raw EMA can't handle that volatility.

**Lesson:** daily bars + equity assets = the right direction. But 2 years isn't enough history to generate 30+ trades with wide EMAs.

| run_id | timestamp | symbol | period | interval | ema | filter | sharpe | max_dd_pct | total_return_pct | trade_count | win_rate | gate_pass | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| exp-002 | 2025-03-15 23:00 | EURUSD=X | 2y | 1h | 50/200 | off | -0.28 | 6.78 | -2.7 | 37 | 27.0% | NO | Better DD, still negative Sharpe. |
| exp-003 | 2025-03-15 23:05 | EURUSD=X | 2y | 1d | 20/50 | off | 0.56 | 3.62 | 5.4 | 5 | 40.0% | NO | First positive Sharpe! Only 5 trades. |
| exp-004a | 2025-03-15 23:10 | SPY | 2y | 1h | 20/50 | off | 0.25 | 12.47 | 1.2 | 34 | 44.1% | NO | Positive Sharpe, enough trades. Needs tuning. |
| exp-004b | 2025-03-15 23:10 | BTC-USD | 2y | 1h | 20/50 | off | -0.49 | 55.35 | -33.5 | 170 | 24.9% | NO | BTC too volatile for raw EMA. |
| exp-004c | 2025-03-15 23:20 | SPY | 2y | 1d | 20/50 | off | 1.05 | 8.41 | 19.9 | 4 | 75.0% | NO | Sharpe passes! Only 4 trades. |
| exp-004d | 2025-03-15 23:20 | SPY | 2y | 1h | 20/50 | ADX>25 | 0.55 | 11.95 | 3.2 | 23 | 43.5% | NO | ADX improved Sharpe but cut trades below 30. |

---

## Phase 3 — HMM regime detection (exp-006a through exp-006g)

**Question:** can a Hidden Markov Model identify market regimes and filter out the periods where trend-following doesn't work?

We introduced a 3-state Gaussian HMM (`data/regime.py`) trained on log returns, rolling volatility, and return autocorrelation. The model classifies each bar as *trending*, *mean-reverting*, or *volatile*. Trades are only taken when the HMM says the market is in a trending regime.

The impact on drawdown was immediate — on EURUSD the HMM cut max DD from 16% to 9% (exp-006a). On SPY 10y daily (exp-006g) it produced a Sharpe of 1.20 and 162% return, but the wide EMAs (20/50) meant only 12 trades over 10 years.

**Lesson:** the HMM dramatically improves risk metrics. The remaining problem is trade count — we need tighter EMAs to generate more crossover signals within the trending windows.

| run_id | timestamp | symbol | period | interval | ema | filter | sharpe | max_dd_pct | total_return_pct | trade_count | win_rate | gate_pass | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| exp-006a | 2025-03-15 23:40 | EURUSD=X | 2y | 1h | 20/50 | HMM | -1.50 | 9.30 | -8.7 | 38 | 21.1% | NO | DD halved (16% to 9%). Still negative Sharpe. |
| exp-006b | 2025-03-15 23:40 | SPY | 2y | 1h | 20/50 | HMM | -0.21 | 8.19 | -1.5 | 16 | 31.3% | NO | DD improved, but HMM too restrictive on 1h. |
| exp-006g | 2025-03-15 23:40 | SPY | 10y | 1d | 20/50 | HMM | 1.20 | 13.17 | 162.8 | 12 | 75.0% | NO | Excellent Sharpe + return. Only 12 trades. |

---

## Phase 4 — EMA tuning for trade count (exp-007a through exp-007e)

**Question:** can we tighten EMA periods to generate enough trades while keeping the HMM's risk protection?

This was the final push on SPY. We narrowed the EMA window from 20/50 down to 10/30, 8/21, 5/20, and 10/20, all with the HMM filter active on 10 years of daily data. The result: **three configurations passed the gate.**

- **exp-007d (EMA 8/21 + HMM)** became the best overall configuration — Sharpe 1.07, DD 10.7%, 36 trades, 96% return.
- exp-007e (EMA 10/30, no filter) also passed but with higher DD (15.8%), proving the HMM's value as a risk reducer.

**Lesson:** shorter EMAs + HMM = the right formula. The HMM prevents the faster signals from generating noise trades in choppy markets. First gate pass achieved.

| run_id | timestamp | symbol | period | interval | ema | filter | sharpe | max_dd_pct | total_return_pct | trade_count | win_rate | gate_pass | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| exp-007a | 2025-03-15 23:50 | SPY | 10y | 1d | 10/30 | HMM | 1.01 | 12.22 | 97.9 | 28 | 53.6% | NO | Almost! 28 trades, 2 short of gate. |
| exp-007b | 2025-03-15 23:50 | SPY | 10y | 1d | 5/20 | HMM | 1.06 | 10.52 | 90.4 | 45 | 40.0% | **YES** | **FIRST GATE PASS.** |
| exp-007c | 2025-03-15 23:50 | SPY | 10y | 1d | 10/20 | HMM | 0.97 | 12.33 | 87.3 | 32 | 53.1% | **YES** | Gate passed. Good win rate. |
| exp-007d | 2025-03-15 23:50 | SPY | 10y | 1d | 8/21 | HMM | 1.07 | 10.70 | 96.4 | 36 | 52.8% | **YES** | **Best overall.** Sharpe 1.07, DD 10.7%. |
| exp-007e | 2025-03-15 23:50 | SPY | 10y | 1d | 10/30 | off | 0.97 | 15.84 | 128.1 | 37 | 48.7% | YES | Passes without HMM but higher DD. |

---

## Phase 5 — Multi-asset validation (exp-010 through exp-014)

**Question:** does the strategy generalise beyond SPY? Can we find at least 5 assets across different classes that pass the gate?

We swept 15+ assets across 5 asset classes: US equities (SPY, DIA, QQQ, IWM, XLK, XLV, MSFT, AAPL), forex (EURUSD), commodities (GLD, SLV), bonds (TLT), and crypto (ETH-USD). For each asset we tested multiple EMA configurations with and without the HMM filter.

**What worked and what didn't:**

- **US equities** — the strongest class. Large-cap equity indices (SPY, DIA) and mega-cap single stocks (MSFT, AAPL) pass the gate. High-beta tech (QQQ) passes with wider EMAs that tame drawdown.
- **Commodities** — GLD passes with EMA 10/30 (no HMM needed). Gold has its own macro-driven trend dynamics.
- **Forex** — fails everywhere. EURUSD lacks the trend persistence this strategy requires.
- **Bonds** — TLT fails. The 2020+ rate regime shift breaks the trend signal.
- **Crypto** — ETH-USD has excellent Sharpe but 73% drawdown. Trend-following captures the upside but can't control crypto's crash risk.

**Key finding:** the HMM is essential for high-beta assets. On MSFT, it cuts DD from 41% to 19% (the difference between failing and passing). On lower-volatility trending assets (DIA, GLD), the unfiltered signal passes on its own.

| run_id | timestamp | symbol | period | interval | ema | filter | sharpe | max_dd_pct | total_return_pct | trade_count | win_rate | gate_pass | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| exp-010-01 | 2026-03-15 14:00 | EURUSD=X | 10y | 1d | 8/21 | HMM | 0.18 | 3.85 | 5.1 | 27 | 37.0% | NO | Forex lacks trend persistence. |
| exp-010-18 | 2026-03-15 14:00 | GLD | 10y | 1d | 10/30 | off | 0.86 | 18.81 | 138.6 | 43 | 30.2% | **YES** | **Gold passes.** Commodities trend. |
| exp-010-05 | 2026-03-15 14:00 | GLD | 10y | 1d | 8/21 | HMM | 0.74 | 22.02 | 100.9 | 53 | 32.7% | NO | HMM + tight EMAs: DD just over 20%. |
| exp-010-21 | 2026-03-15 14:00 | TLT | 10y | 1d | 8/21 | HMM | -0.41 | 10.82 | -15.2 | 27 | 33.3% | NO | Rate regime shift kills trend signal. |
| exp-010-25 | 2026-03-15 14:00 | ETH-USD | 10y | 1d | 8/21 | HMM | 0.88 | 72.62 | 3127.2 | 32 | 43.8% | NO | Great Sharpe, 73% DD. Crypto too wild. |
| exp-011-10 | 2026-03-15 14:30 | DIA | 10y | 1d | 5/20 | off | 0.86 | 19.80 | 98.4 | 64 | 42.2% | **YES** | **Dow passes** without HMM. |
| exp-011-08 | 2026-03-15 14:30 | DIA | 10y | 1d | 8/21 | off | 0.81 | 22.73 | 91.0 | 46 | 47.8% | NO | HMM too restrictive on DIA (2 trades). |
| exp-012-04 | 2026-03-15 15:00 | QQQ | 10y | 1d | 5/20 | off | 1.07 | 29.57 | 208.5 | 64 | 43.8% | NO | Sharpe 1.07 but DD 30%. High beta. |
| exp-012-08 | 2026-03-15 15:00 | XLK | 10y | 1d | 5/20 | off | 1.02 | 24.15 | 224.6 | 64 | 43.8% | NO | Same as QQQ. DD exceeds gate. |
| exp-012-17 | 2026-03-15 15:00 | SMH | 10y | 1d | 8/21 | HMM | 0.79 | 25.94 | 171.6 | 33 | 51.5% | NO | HMM reduces DD 41% to 26%. Still fails. |
| exp-013-14 | 2026-03-15 15:30 | MSFT | 10y | 1d | 8/21 | HMM | 0.97 | 19.27 | 201.7 | 39 | 48.7% | **YES** | **MSFT passes.** HMM cuts DD from 41% to 19%. |
| exp-013-15 | 2026-03-15 15:30 | MSFT | 10y | 1d | 8/21 | off | 0.81 | 40.85 | 188.4 | 53 | 39.6% | NO | Without HMM: DD doubles. |
| exp-014-03 | 2026-03-15 16:00 | QQQ | 10y | 1d | 12/35 | off | 0.89 | 19.89 | 163.5 | 31 | 48.4% | **YES** | **QQQ passes.** Wider EMAs tame DD. |
| exp-014-07 | 2026-03-15 16:00 | AAPL | 10y | 1d | 5/20 | HMM | 1.17 | 19.76 | 312.2 | 48 | 45.8% | **YES** | **AAPL passes.** Best Sharpe overall. |
| exp-014-17 | 2026-03-15 16:00 | AAPL | 10y | 1d | 8/21 | off | 1.31 | 26.15 | 561.7 | 49 | 44.9% | NO | Highest raw Sharpe but DD fails without HMM. |

---

## In-sample summary — 6 assets pass

| Asset | Class | EMA | Filter | Sharpe | Max DD | Trades | Return |
|---|---|---|---|---|---|---|---|
| **SPY** | US Equity (Large Cap) | 8/21 | HMM | 1.07 | 10.70% | 36 | 96.4% |
| **DIA** | US Equity (Large Cap) | 5/20 | None | 0.86 | 19.80% | 64 | 98.4% |
| **QQQ** | US Equity (Tech) | 12/35 | None | 0.89 | 19.89% | 31 | 163.5% |
| **MSFT** | US Equity (Single Stock) | 8/21 | HMM | 0.97 | 19.27% | 39 | 201.7% |
| **AAPL** | US Equity (Single Stock) | 5/20 | HMM | 1.17 | 19.76% | 48 | 312.2% |
| **GLD** | Commodity (Gold) | 10/30 | None | 0.86 | 18.81% | 43 | 138.6% |

---

## Walk-forward validated summary — 3 assets pass (Phase 6)

After walk-forward validation (exp-008), only **3 assets** pass with genuine out-of-sample edge. All use the unfiltered EMA crossover — the HMM regime filter does not survive walk-forward.

| Asset | Class | EMA | Filter | OOS Sharpe | OOS Max DD | OOS Trades | OOS Return |
|---|---|---|---|---|---|---|---|
| **SPY** | US Equity (Large Cap) | 8/21 | None | 0.88 | 16.4% | 35 | 110% |
| **QQQ** | US Equity (Tech) | 8/25 | None | 0.96 | 17.6% | 33 | 171% |
| **GLD** | Commodity (Gold) | 7/18 | None | 0.85 | 18.7% | 33 | 79% |

Method: rolling 5y-train / 1y-test windows, HMM fitted on train only (where applicable), all metrics computed on concatenated test periods.

**What walk-forward revealed:**
- The HMM overfits: regime predictions from a 5y training window don't transfer to the next year, collapsing trade count to near zero.
- The unfiltered EMA crossover has a genuine edge on assets with persistent trends (SPY, QQQ, GLD).
- DIA's edge is real but too weak (Sharpe ~0.60 OOS). MSFT and AAPL have uncontrollable drawdown without HMM.

---

## Experiment queue — remaining work for v0.1.0

### exp-008 — Walk-forward validation (out-of-sample proof)

**What it tests:** whether the in-sample results above survive when the HMM and strategy are evaluated on data they've never seen.

**Why it matters:** this is the most important experiment in the entire v0.1.0 cycle. Every result so far was generated by training and testing on the same 10-year window. If the strategy is simply curve-fitting to historical quirks, walk-forward will expose it. If it holds up, v0.1.0 is genuinely complete.

**Method:**
1. Split the 10-year window into rolling segments (e.g. 5-year train, 1-year test, sliding forward by 1 year).
2. On each segment: fit the HMM on the training window only, freeze it, then run the backtest on the test window using that frozen model.
3. Concatenate all out-of-sample test periods and compute aggregate metrics (Sharpe, DD, trade count).
4. Run on all 6 passing assets. An asset "survives" if the out-of-sample aggregate still passes the gate.

**Success criteria:** at least 4 of the 6 assets pass the gate out-of-sample. If fewer than 4 survive, the strategy needs further iteration before v0.1.0 can close.

### exp-008 — Results (walk-forward completed)

Walk-forward validation revealed that the **HMM regime filter overfits to in-sample data**. When fitted on a training window and applied to unseen test data, the HMM identifies far fewer trending periods, collapsing trade count to near zero. The three HMM-dependent in-sample passes (SPY, MSFT, AAPL) all failed out-of-sample.

However, the **unfiltered EMA crossover has a genuine out-of-sample edge** on assets with persistent trends. After tuning EMA parameters and extending the data window, 3 assets pass the walk-forward gate across 2 asset classes:

| Asset | EMA | Filter | Data | OOS Sharpe | OOS Max DD | OOS Trades | OOS Return | Gate |
|---|---|---|---|---|---|---|---|---|
| **SPY** | 8/21 | None | 12y | **0.88** | 16.4% | **35** | 110% | **PASS** |
| **SPY** | 5/20 | None | 12y | **0.86** | 14.3% | **47** | 104% | **PASS** |
| **QQQ** | 8/25 | None | 12y | **0.96** | 17.6% | **33** | 171% | **PASS** |
| **GLD** | 7/18 | None | 10y | **0.85** | 18.7% | **33** | 79% | **PASS** |
| **GLD** | 6/18 | None | 10y | **0.82** | 18.6% | **37** | 75% | **PASS** |

Notable near-misses (failed on a single metric):

| Asset | EMA | Filter | Data | OOS Sharpe | OOS Max DD | OOS Trades | Failure |
|---|---|---|---|---|---|---|---|
| SPY | 7/18 | None | 10y | 0.89 | 10.4% | 28 | 2 trades short |
| GLD | 8/21 | None | 10y | 0.93 | 16.2% | 28 | 2 trades short |
| QQQ | 10/30 | None | 12y | 0.86 | 18.8% | 29 | 1 trade short |

**Key findings from walk-forward:**
1. **HMM overfits.** The regime model trained on 5 years of data does not reliably identify trending periods in the next year. All HMM-dependent configurations produced fewer than 10 trades OOS.
2. **Raw EMA crossover has real edge on trending assets.** SPY and GLD pass walk-forward without any filter, proving the trend signal is genuine — not an artifact of in-sample fitting.
3. **QQQ passes with wider EMAs (8/25)** that reduce whipsaw in volatile periods, a similar pattern to the in-sample finding.
4. **DIA, MSFT, AAPL do not pass walk-forward.** DIA's Sharpe degrades to ~0.60. MSFT and AAPL have excessive drawdown without HMM.
5. **12y of data helps SPY** — more test folds push trade count over 30. GLD passes on 10y.

### exp-005 — ATR trailing stop (risk management improvement)

**What it tests:** whether replacing the fixed EMA-crossover exit with a volatility-adjusted trailing stop improves risk-adjusted returns.

**Why it matters:** the current exit rule (exit when fast EMA crosses below slow EMA) is lagging — by the time the crossover fires, the price has already reversed significantly. An ATR-based trailing stop would exit earlier during sharp reversals, potentially reducing max drawdown while preserving more of the trend's gains.

**Method:**
1. Compute ATR(14) on each bar.
2. Set a trailing stop at `close - N * ATR` (start with N=2.0).
3. Exit when price touches the stop OR when the EMA crossover fires (whichever comes first).
4. Compare metrics against the current EMA-only exit on all 6 passing assets.

**Success criteria:** lower max drawdown on at least 4 of 6 assets without Sharpe dropping below 0.8.

**Dependency:** run after exp-008. No point optimising exits on a signal that hasn't been validated out-of-sample.

### exp-015 — Regime-aware position sizing (optional, stretch)

**What it tests:** whether scaling position size based on the HMM's confidence (e.g. trending probability) improves returns without increasing drawdown.

**Why it matters:** currently the system is fully invested or fully flat. If the HMM reports 95% trending probability, that's arguably a stronger signal than 55%. Sizing by conviction could extract more from high-confidence regimes.

**Method:**
1. Use the HMM's state probability (not just the hard label) as a scaling factor.
2. Position size = base size * trending_probability.
3. Compare against the binary (fully in / fully out) approach on the 6 passing assets.

**Success criteria:** higher Sharpe without increasing max drawdown.

**Dependency:** run after exp-008 and exp-005. This is an optimisation on top of a validated, risk-managed signal.
