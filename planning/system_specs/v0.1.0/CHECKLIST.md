# v0.1.0 Checklist

> **Gate:** Sharpe > 0.8, Max Drawdown < 20%, Minimum 30 trades.
> Do not move to v0.2.0 until walk-forward validation confirms the gate holds out-of-sample.
> Sharpe: `mean(returns) / std(returns) * sqrt(252)` (daily), no risk-free rate. Drawdown: mark-to-market equity curve.

---

## 1. Project Scaffold

- [x] `agents/signal/trend_agent.py` exists
- [x] `data/fetcher.py` exists
- [x] `data/indicators.py` exists
- [x] `data/regime.py` exists
- [x] `backtest/run.py` exists
- [x] `config.py` exists
- [x] `ui/app.py` exists (Flask dashboard)
- [x] `scripts/generate_mmd_diagrams.py` exists
- [x] `scripts/run_experiments.py` exists
- [x] `requirements.txt` exists
- [x] `pyproject.toml` exists with CLI entry points (`trade-swarm-backtest`, `trade-swarm-ui`, `trade-swarm-diagrams`)
- [x] `__init__.py` in all packages: `agents/`, `agents/signal/`, `backtest/`, `data/`, `ui/`, `scripts/`
- [x] `pip install -e .` works cleanly (no `sys.path` hacks)

---

## 2. Data Fetcher (`data/fetcher.py`)

- [x] `fetch_ohlcv(symbol, period, interval)` implemented using `yfinance`
- [x] Drops NaN rows before returning
- [x] Handles MultiIndex columns from yfinance (flattens to single level)

---

## 3. Indicators (`data/indicators.py`)

> Spec originally called for `pandas-ta`. Decision: **keep pure-pandas.** The implementations are mathematically equivalent (`ewm`-based), have zero external dependencies, and work on all Python versions including 3.14+. `pandas-ta` would only be needed for exotic indicators not used in v0.1.0. Deviation documented in CHANGELOG.

- [x] `ema(series, length)` implemented
- [x] `rsi(series, length)` implemented
- [x] `adx(high, low, close, length)` implemented
- [ ] **Verify indicator values match `pandas-ta` output** — spot-check EMA_20, EMA_50, ADX_14, RSI_14 on a known dataset

---

## 4. HMM Regime Detector (`data/regime.py`)

- [x] `Regime` enum: `TRENDING`, `MEAN_REVERTING`, `VOLATILE`
- [x] `_build_features(df)` computes log returns, rolling volatility (20-bar), and return autocorrelation (20-bar)
- [x] `detect_regimes(df, n_states=3)` fits a `GaussianHMM` on the feature matrix and returns a `Series[Regime]`
- [x] `_label_states(model, n_states)` heuristically maps HMM state indices to `Regime` labels based on learned means and covariances
- [x] Handles non-convergence gracefully (hmmlearn warns but returns best-effort fit)
- [x] Integrated into `build_signals()` in `backtest/run.py` via `use_regime` flag
- [x] Integrated into `TrendSignalAgent.generate()` — forces `FLAT` when regime is not `TRENDING`

---

## 5. Signal Agent (`agents/signal/trend_agent.py`)

- [x] `Direction` enum: `LONG`, `SHORT`, `FLAT`
- [x] `SignalEvent` dataclass: `asset`, `direction`, `strength`, `confidence`, `timestamp`, `indicators`
- [x] `TrendSignalAgent.__init__(symbol, use_regime=False)` accepts optional regime filter
- [x] `TrendSignalAgent.generate(df)` computes EMA_20, EMA_50, ADX_14, RSI_14
- [x] Direction logic: EMA_20 > EMA_50 → LONG, < → SHORT, = → FLAT
- [x] Regime override: if `use_regime=True` and regime != TRENDING, direction forced to FLAT
- [x] Strength: normalised EMA spread (capped at 1.0)
- [x] Confidence: ADX / 50 (capped at 1.0)
- [x] `regime` value included in `indicators` dict when regime filter is active

---

## 6. Backtest (`backtest/run.py`)

- [x] `run_backtest(symbol, period, interval, ema_fast, ema_slow, use_regime)` — main entry point
- [x] `build_signals(df, ema_fast, ema_slow, use_regime)` — computes EMAs, optionally runs HMM, returns (df, entries, exits)
- [x] `backtest_pandas(df, entries, exits, cash, fees)` — pure-pandas bar-by-bar loop with equity tracking
- [x] `_check_gate(metrics)` — evaluates Sharpe, DD, trade count against gate thresholds
- [x] Computes: Total Return, Sharpe Ratio, Max Drawdown, Win Rate, Total Trades
- [x] Max Drawdown reported as positive percentage (`abs(max_drawdown) * 100`)
- [x] `vectorbt` used as optional accelerator when available; pure-pandas fallback is primary path
- [x] Gate evaluation printed after every run
- [x] Returns `config_used` dict with all parameters for experiment logging

### Current best results (in-sample, 10y daily)

| Asset | EMA | Filter | Sharpe | Max DD | Trades | Return | Gate |
|---|---|---|---|---|---|---|---|
| SPY | 8/21 | HMM | 1.07 | 10.7% | 36 | 96% | **PASS** |
| DIA | 5/20 | None | 0.86 | 19.8% | 64 | 98% | **PASS** |
| QQQ | 12/35 | None | 0.89 | 19.9% | 31 | 164% | **PASS** |
| MSFT | 8/21 | HMM | 0.97 | 19.3% | 39 | 202% | **PASS** |
| AAPL | 5/20 | HMM | 1.17 | 19.8% | 48 | 312% | **PASS** |
| GLD | 10/30 | None | 0.86 | 18.8% | 43 | 139% | **PASS** |

> **Caveat:** all results are in-sample. Walk-forward validation (exp-008) is required before these can be considered proven.

---

## 7. Config (`config.py`)

> Note: `config.py` stores the *original* defaults from the v0.1.0 spec. The passing configurations discovered through experimentation use different values (passed as parameters to `run_backtest()`). The defaults below serve as the baseline starting point; they are not the tuned values.

- [x] `DEFAULT_SYMBOL = "EURUSD=X"` (baseline asset; experiments proved SPY/DIA/QQQ/MSFT/AAPL/GLD are better)
- [x] `DEFAULT_PERIOD = "2y"` (baseline; experiments use `10y` for sufficient trade count)
- [x] `DEFAULT_INTERVAL = "1h"` (baseline; experiments proved `1d` is superior)
- [x] `INIT_CASH = 10_000`
- [x] `FEE_RATE = 0.001`
- [x] `EMA_FAST = 20`, `EMA_SLOW = 50` (baseline; tuned values vary per asset)
- [x] `ADX_PERIOD = 14`, `ADX_THRESHOLD = 25` (superseded by HMM regime filter for most use cases)
- [x] `GATE_MIN_SHARPE = 0.8`, `GATE_MAX_DRAWDOWN_PCT = 20.0`, `GATE_MIN_TRADES = 30`

---

## 8. Dependencies

- [x] `yfinance` in `requirements.txt` and `pyproject.toml`
- [x] `pandas` in both
- [x] `numpy` in both
- [x] `flask` in both
- [x] `hmmlearn` in both
- [x] `scikit-learn` in both
- [x] `vectorbt` listed as optional comment (not a hard dependency; pure-pandas fallback is primary)
- [x] `pandas-ta` formally closed out — pure-pandas kept (see Section 3 note)
- [x] `httpx`, `langgraph`, `langchain` moved to `[project.optional-dependencies]` under `orchestrator` (not needed until v0.2.0+)

---

## 9. Dashboard (`ui/app.py`)

- [x] Flask app with five tabs: Dashboard, Backtest, Signal, Experiments, Diagrams
- [x] `/api/backtest` accepts `symbol`, `period`, `interval`, `ema_fast`, `ema_slow`, `use_regime`
- [x] `/api/signal` generates `SignalEvent` with optional regime filter
- [x] `/api/experiments` is version-aware — loads the experiment log matching the current git branch's semver
- [x] `/api/version` exposes detected branch version
- [x] `app.json.sort_keys = False` preserves column order in experiment tables
- [x] HMM Regime Filter checkbox in Backtest tab
- [x] Version label displayed in Experiments tab

---

## 10. Mermaid Diagrams (`scripts/generate_mmd_diagrams.py`)

- [x] Generates four diagram types: Structure, Movement, Runtime, Spec Plan
- [x] Outputs into `planning/diagrams/` with subfolders per type
- [x] `--src-only` flag (no Node.js required)
- [x] Branch-aware: auto-detects semver from current git branch, generates only matching version's diagrams
- [x] `--all` flag overrides branch filtering; `--version` flag for explicit targeting
- [x] `DIAGRAM_REGISTRY` entries tagged with version for filtering
- [x] YAML front-matter parser (stdlib only, no PyYAML)
- [x] `v0.1.0.md` front-matter updated: includes `indicators`, `regime` (HMM), `multi_asset` nodes
- [x] Dataflow diagram includes Regime Detection subgraph
- [x] Class model includes `data/regime.py` module
- [x] Runtime flow shows `use_regime?` branch and gate check
- [x] Spec plan discovery restricted to `v<major>.<minor>.<patch>.md` files only
- [ ] **Run full SVG render** (`trade-swarm-diagrams`) once Node.js + mermaid-cli confirmed available

---

## 11. Documentation

- [x] `README.md` covers v0.1.0 objective, gate, current status (6 passing assets), quick start, and module table
- [x] `README.md` documents HMM regime detector and branch-aware diagram generation
- [x] `CHANGELOG.md` records all additions, changes, fixes, renames, and experiment results
- [x] `EXPERIMENT_LOG.md` structured into 5 narrative phases with per-phase questions and lessons learned
- [x] Experiment queue documents exp-008, exp-005, exp-015 with method, success criteria, and dependencies

---

## 12. Gate Sign-off

- [x] Sharpe > 0.8 confirmed on 6 assets (in-sample)
- [x] Max Drawdown < 20% confirmed on 6 assets (in-sample)
- [x] Trades >= 30 confirmed on 6 assets (in-sample)
- [ ] **exp-008: Walk-forward validation** — confirm gate holds out-of-sample on at least 4 of 6 assets
- [ ] All checklist items above ticked (Section 3 indicator verification and Section 10 SVG render still open)
- [ ] **Tag commit as `v0.1.0`** and move to v0.2.0 (walk-forward + paper trading via Alpaca)

---

## Remaining work to close v0.1.0

| Priority | Item | Status |
|---|---|---|
| **P0** | exp-008: Walk-forward validation on 6 passing assets | Not started |
| P1 | Verify pure-pandas indicators match pandas-ta output (Section 3) | Not started |
| P1 | Run full SVG diagram render (Section 10) | Blocked on Node.js |
| P2 | exp-005: ATR trailing stop (depends on exp-008) | Not started |
| P3 | exp-015: Regime-aware position sizing (depends on exp-005) | Not started |
| P3 | Consider updating `config.py` defaults to reflect best-known values | Optional |
