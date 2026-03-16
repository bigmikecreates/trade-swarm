# Trade-Swarm Research Methodology

> Cross-version protocols and standards. Established during v0.1.0, updated as the system evolves.

---

## Walk-forward validation protocol

Every strategy must pass this protocol before being considered proven:

1. Download full history (minimum 10 years daily, or equivalent bar count)
2. Split into rolling windows: 5-year train, 1-year test, 1-year step
3. On each fold: fit any models on train only, freeze, evaluate on test
4. Concatenate all test-period equity curves
5. Compute aggregate metrics on the concatenated OOS curve
6. Gate check on the aggregate: Sharpe > 0.8, DD < 20%, Trades >= 30

No exceptions. In-sample results are for exploration only.

## Indicator implementation policy

Pure pandas, no external indicator libraries (pandas-ta, ta-lib). Reasons:
- Zero dependency risk (no numba/LLVM chain)
- Works on all Python versions including 3.14+
- Implementations are mathematically identical (ewm-based)
- Full control over edge cases

If an exotic indicator is needed in future versions, implement it in `data/indicators.py` and add a verification test against a reference implementation.

## Cost model

All backtests use a flat 0.1% fee per trade, no spread or slippage. This is optimistic for:
- Illiquid assets (small-cap, commodities ETFs)
- High-frequency strategies (intraday)

For v0.2.0 (paper trading), compare actual execution costs against the modeled 0.1% and adjust if the gap is significant.

## Experiment logging

Each version maintains its own `EXPERIMENT_LOG.md` in `planning/system_specs/<version>/`. Logs are organized into narrative phases, each answering a specific research question. Every experiment records: ID, timestamp, asset, parameters, metrics, and a pass/fail verdict against the gate.

## Research journal conventions

Each version maintains its own `RESEARCH.md` in `planning/research/<version>/`. Structure:

1. **The question we set out to answer** — the core hypothesis for this version
2. **What we tried** — phases of experimentation, in order
3. **What we learned** — numbered findings with analysis
4. **Final results** — the validated metrics table
5. **Open questions** — forward-looking research threads tagged with target versions
