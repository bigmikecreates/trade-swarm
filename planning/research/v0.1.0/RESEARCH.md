# v0.1.0 Research — Prove the signal

> What was tried, what was learned, and what questions emerged.

---

## The question we set out to answer

Can a simple EMA crossover strategy, with appropriate filtering, pass a hard performance gate (Sharpe > 0.8, Max DD < 20%, Trades >= 30) on multiple assets with genuine out-of-sample edge?

## What we tried

**5 phases of experimentation, 80+ runs across 15+ assets:**

1. **Baseline (EURUSD hourly, EMA 20/50)** — no edge. Forex mean-reverts; EMA crossover trades noise.
2. **Asset/timeframe search** — SPY daily showed the first positive Sharpe (1.05), but too few trades on 2 years of data.
3. **HMM regime detection** — a 3-state Gaussian Hidden Markov Model trained on log returns, rolling volatility, and return autocorrelation. Halved drawdowns in-sample by filtering trades to only the "trending" regime.
4. **EMA tuning** — tighter EMAs (8/21, 5/20) generated enough crossover signals within HMM-identified trending windows. First gate pass on SPY.
5. **Multi-asset validation** — swept equities, forex, commodities, bonds, crypto. Six assets passed in-sample.
6. **Walk-forward validation** — rolling 5y-train / 1y-test windows. HMM regime filter did not survive. Three assets passed with unfiltered EMA crossover.

## What we learned

### Finding 1: EMA crossover works — but only on specific asset types

The strategy has a genuine edge on **diversified, structurally trending instruments with moderate volatility**:

- **SPY** (S&P 500) — 500 underlying stocks smooth idiosyncratic noise; corporate earnings growth provides structural upward drift
- **QQQ** (NASDAQ 100) — tech sector secular growth trend, 100 stocks provide diversification
- **GLD** (Gold) — macro-driven trends (real rates, inflation, risk aversion) that shift slowly and persistently

Assets that fail share common traits: too narrow (DIA = 30 stocks), too volatile (single stocks like MSFT/AAPL with earnings gaps), or structurally non-trending (forex, bonds in rate transition, natural gas with contango decay).

### Finding 2: The HMM regime filter overfits

In-sample, the HMM was transformative — it halved drawdowns on SPY, MSFT, and AAPL, turning failures into passes. But walk-forward validation revealed it doesn't generalize: regime patterns learned on 5 years of history don't reliably predict the next year's regimes. Trade count collapsed to near zero on most assets when the HMM was trained on training data only.

**The lesson is subtle:** the HMM is an excellent *research tool* (it guided us toward daily timeframes and equity assets) but a poor *production filter*. The regime concept is sound — the implementation needs to be simpler and more robust.

### Finding 3: In-sample results are meaningless without walk-forward

Our in-sample results showed 6 assets passing with Sharpe up to 1.17. Walk-forward cut that to 3 assets with Sharpe topping out at 0.96. The gap isn't small — it's the difference between a portfolio you'd fund and one you'd pass on. Every future version of this system must include walk-forward validation before any result is considered proven.

### Finding 4: Asset class diversification requires strategy diversification

Attempting to force EMA crossover onto forex, energy, crypto, and bonds failed comprehensively. Each asset class has its own microstructure:

| Asset class | Dominant behavior | Why EMA crossover fails | Strategy that fits |
|---|---|---|---|
| Forex | Mean-reverting (central bank anchoring, carry) | Generates chop trades with no directional edge | Mean-reversion (Bollinger fade, RSI extremes) |
| Energy/NatGas | Supply shock jumps + long flat periods | Enters after the jump, gets chopped in flats | Breakout/momentum ignition (Donchian channel) |
| Crypto | Massive trends + massive crashes | Good Sharpe but 40-70% drawdowns | Volatility harvesting, or trend + aggressive risk mgmt |
| Bonds | Carry + rate regime shifts | Trend signal breaks during regime transitions | Carry + roll-down, or macro factor models |
| Metals (Silver) | Gold-like macro + 2-3x industrial vol | Signal drowns in noise | Pairs trading (gold/silver ratio), or vol-adjusted trend |

This table is the foundation of the multi-agent architecture planned for v0.3.0.

### Finding 5: Drawdown is the binding constraint

Across all experiments, Sharpe was achievable on many assets — the gate that killed most configurations was Max Drawdown < 20%. This points to risk management as the highest-leverage improvement area. Three approaches worth exploring:

1. **Volatility-scaled position sizing** — size inversely to realized vol so volatile periods automatically get smaller positions
2. **ATR trailing stops** — exit earlier during sharp reversals instead of waiting for EMA crossover
3. **Volatility filtering** — block entries when realized vol exceeds a percentile threshold

## Walk-forward validated results (final)

| Asset | EMA | OOS Sharpe | OOS Max DD | OOS Trades | OOS Return |
|---|---|---|---|---|---|
| SPY | 8/21 | 0.88 | 16.4% | 35 | 110% |
| QQQ | 8/25 | 0.96 | 17.6% | 33 | 171% |
| GLD | 7/18 | 0.85 | 18.7% | 33 | 79% |

---

## Open questions born from v0.1.0

These are research threads identified during v0.1.0 work. Each is tagged with the version where it's expected to be addressed.

### R1: Volatility-scaled position sizing (target: v0.2.0)

**Question:** Does sizing positions inversely to realized volatility improve risk-adjusted returns and enable currently-failing assets to pass the gate?

**Hypothesis:** The single biggest failure mode is drawdown from volatility spikes. If position size = `target_vol / realized_vol`, then high-vol periods automatically get smaller positions, capping drawdown contribution. This could bring MSFT and AAPL (which have good Sharpe but blow through DD limits) into passing range.

**Why it matters:** This is the industry standard approach (risk parity, managed futures, CTAs). It's parameter-light (one knob: target vol), doesn't require model fitting, and is inherently walk-forward safe since it only uses backward-looking vol.

**Implementation notes:**
- Compute 20-day realized vol (annualized)
- Position size = `min(target_vol / realized_vol, 1.0)` (cap at 100%)
- Target vol ~15% is typical for equity-like strategies
- Apply to all assets, including the 3 that already pass (should improve them too)

### R2: ATR trailing stop (target: v0.2.0)

**Question:** Does replacing the EMA-crossover exit with a volatility-adjusted trailing stop reduce max drawdown without sacrificing Sharpe?

**Hypothesis:** The EMA crossover exit is a lagging indicator — by the time fast EMA crosses below slow EMA, price has already dropped significantly. An ATR-based trailing stop (`close - N * ATR`) exits earlier during sharp reversals while letting profits run during smooth trends.

**Why it matters:** This directly attacks the DD constraint. If it works, it could:
- Improve the 3 passing assets (tighter DD -> higher risk-adjusted return)
- Rescue near-misses like DIA (DD is fine, Sharpe needs a boost from better exits)

**Key risk:** trailing stops can trigger premature exits during normal pullbacks within a trend, reducing trade profitability. The ATR multiplier (N) needs tuning — too tight = whipsawed out, too loose = no improvement over EMA exit.

### R3: Mean-reversion agent for forex (target: v0.3.0)

**Question:** Can a mean-reversion strategy (Bollinger Band fade, RSI overbought/oversold) pass the gate on forex pairs where trend-following fails?

**Hypothesis:** Forex pairs are structurally mean-reverting due to central bank policy anchoring, carry trade dynamics, and purchasing power parity. A strategy that fades moves to Bollinger Band extremes (enter when price touches the outer band, exit at the mean) should capture this behavior.

**Why it matters:** This is how Trade-Swarm becomes a genuine multi-strategy system. One strategy can't cover all asset classes — but different strategies deployed on their native asset classes can. The v0.3.0 spec already outlines a `MeanReversionAgent` with RSI + Bollinger Bands + ATR.

**Assets to test:** EURUSD, GBPUSD, USDJPY, EURGBP, AUDUSD

**Research needed:**
- What timeframe works best for forex mean-reversion? (4h and daily are common)
- What's the right lookback for Bollinger Bands? (20 is standard, but forex may need longer)
- How to handle trending forex periods (USD strength 2022-2023)?

### R4: Regime detection — simpler alternatives to HMM (target: v0.3.0)

**Question:** Can a simpler, more robust regime detection method replace the HMM for production use?

The HMM taught us that regime awareness matters, but the implementation overfits. Simpler alternatives that don't require model fitting:

| Approach | How it works | Walk-forward safe? |
|---|---|---|
| **Volatility percentile** | Current vol vs. rolling 1y percentile. High vol = volatile regime, low = trending/quiet. | Yes — no fitting, pure rolling calculation |
| **ADX threshold** | ADX > 25 = trending. Simple, well-known. | Yes — indicator-based, no fitting |
| **Trend strength composite** | Combine ADX + price > 200-day SMA + vol below median. Score 0-3. | Yes — rule-based |
| **Correlation regime** | Rolling correlation between asset and broad market. High corr = risk-on, low = idiosyncratic. | Yes — no fitting |

**Key insight from v0.1.0:** the best regime filter for walk-forward was *no filter at all*. Any future regime detection must prove it improves OOS results, not just in-sample. The bar is: does it improve walk-forward Sharpe or DD compared to unfiltered baseline?

### R5: Portfolio-level risk management (target: v0.4.0+)

**Question:** When running multiple agents on multiple assets, how should portfolio-level risk be managed?

Individual asset gates are necessary but not sufficient. With SPY and QQQ both in the portfolio (~0.90 correlation), a broad equity selloff hits both simultaneously. Portfolio-level concerns:

- **Correlation-aware sizing** — reduce combined equity exposure when SPY/QQQ are highly correlated
- **Max portfolio drawdown** — cap total portfolio DD at e.g. 15%, even if individual assets are within limits
- **Strategy allocation** — how much capital to trend-following vs. mean-reversion vs. other strategies
- **Rebalancing frequency** — daily? weekly? event-driven?

This becomes critical once v0.3.0 adds multiple agents. The orchestrator (LangGraph in v0.3.0 spec) needs a risk management layer above the individual signal agents.

### R6: Breakout strategy for commodities and energy (target: v0.3.0+)

**Question:** Can a breakout/momentum strategy (Donchian channel, N-bar high/low) capture the sharp directional moves in energy and industrial commodities?

**Hypothesis:** Energy prices (XLE, UNG, crude oil) move in sudden regime jumps driven by supply shocks, OPEC decisions, and geopolitical events. EMA crossover enters too late (after the jump). A breakout strategy that enters when price exceeds the N-day high would capture these moves at inception.

**Assets to test:** XLE, USO (crude oil), UNG (natural gas), COPX (copper miners), DBA (agriculture)

**Key risk:** breakout strategies have low win rates (many false breakouts) — they depend on large wins from the real breakouts to compensate. This makes them psychologically difficult and requires robust position sizing.
