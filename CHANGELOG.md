# Changelog

All notable changes to this project are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased] -- v0.1.0 in progress

### Status

**Gate passed (in-sample) across 6 assets.** Next step: walk-forward out-of-sample validation.

| Asset | EMA | Filter | Sharpe | Max DD | Trades | Return | Gate |
|---|---|---|---|---|---|---|---|
| SPY | 8/21 | HMM | 1.07 | 10.7% | 36 | 96% | PASS |
| DIA | 5/20 | None | 0.86 | 19.8% | 64 | 98% | PASS |
| QQQ | 12/35 | None | 0.89 | 19.9% | 31 | 164% | PASS |
| MSFT | 8/21 | HMM | 0.97 | 19.3% | 39 | 202% | PASS |
| AAPL | 5/20 | HMM | 1.17 | 19.8% | 48 | 312% | PASS |
| GLD | 10/30 | None | 0.86 | 18.8% | 43 | 139% | PASS |

### Added
- `data/fetcher.py` -- OHLCV fetcher via yfinance with MultiIndex column flattening
- `data/indicators.py` -- pure-pandas EMA, RSI, ADX (no numba dependency; compatible with Python 3.14+)
- `agents/signal/trend_agent.py` -- `TrendSignalAgent` using EMA crossover + ADX confidence; emits `SignalEvent` dataclass
- `backtest/run.py` -- EMA crossover backtest with configurable ADX regime filter; uses vectorbt when available, falls back to pure-pandas loop
- `config.py` -- centralised defaults: symbol, period, interval, cash, fees, EMA params, ADX filter, gate thresholds
- `scripts/generate_mmd_diagrams.py` -- generates four Mermaid diagram types:
  - **Structure** (`class_model/`) -- static codebase shape
  - **Movement** (`dataflow/`) -- data flow through the system
  - **Runtime** (`instance_flow/`) -- step-by-step backtest execution
  - **Spec Plan** (`spec_diagrams/`) -- auto-discovered from YAML front-matter in version spec files
- `planning/system_specs/v0.1.0/v0.1.0.md` -- version specification with `spec_diagram:` YAML front-matter
- `planning/system_specs/v0.1.0/CHECKLIST.md` -- v0.1.0 readiness checklist
- `planning/system_specs/v0.1.0/EXPERIMENT_LOG.md` -- structured experiment tracking with baseline + exp-001
- `pyproject.toml` and `requirements.txt` with core dependencies

### Changed
- `config.py` -- added configurable EMA params (`EMA_FAST`, `EMA_SLOW`), ADX regime filter (`ADX_PERIOD`, `ADX_THRESHOLD`), and gate thresholds (`GATE_MIN_SHARPE`, `GATE_MAX_DRAWDOWN_PCT`, `GATE_MIN_TRADES`)
- `backtest/run.py` -- refactored into composable functions: `_build_signals()`, `_backtest_pandas()`, `_check_gate()`; ADX filter wired into entry logic; gate evaluation printed after every run
- `generate_mmd_diagrams.py` -- added `--src-only` flag, YAML front-matter spec parser (stdlib only), outputs organised by diagram type under `planning/diagrams/`
- Gate definition tightened: added minimum trade count (>= 30) to prevent overfitting on thin results

### Fixed
- Max Drawdown sign bug in `backtest/run.py` -- now reported as a positive percentage
- Mermaid diagram output path corrected to `planning/diagrams/`
- README diagram command corrected from `generate_diagram.py` to `scripts/generate_mmd_diagrams.py`
- Script encoding fixed for Windows terminals (removed non-ASCII box-drawing characters)

### Renamed
- Project renamed from `trading_agent` to **Trade-Swarm** across README, pyproject.toml, UI, scripts, and backtest docstrings

### Added (UI & project structure)
- `ui/` -- Flask dashboard with five tabs: Dashboard, Backtest, Signal, Experiments, Diagrams
- CLI entry points via `pip install -e .`: `trade-swarm-backtest`, `trade-swarm-ui`, `trade-swarm-diagrams`
- `.gitignore` -- comprehensive Python, Node, IDE, and OS ignores; generated diagrams excluded (reproducible)
- `__init__.py` for `ui/` and `scripts/` packages

### Changed (project structure)
- `pyproject.toml` -- proper setuptools config with package discovery, `py-modules`, CLI entry points, and `requires-python`
- Removed `sys.path` hacks from `backtest/run.py` and `ui/app.py`; imports now work via editable install
- `httpx`, `langgraph`, `langchain` moved to `[project.optional-dependencies]` under `orchestrator` (not needed until v0.2.0+)
- Spec diagram discovery restricted to files matching `v<major>.<minor>.<patch>.md` only
- README restructured for human readability: objective-first, quick start, grouped tables

### Changed (experiment log)
- `EXPERIMENT_LOG.md` -- removed `base_version` column (redundant; log lives inside the version directory), replaced `date` with `timestamp` column
- `/api/experiments` -- detects current git branch, extracts semver, loads the matching version's experiment log; falls back to single-log discovery on `main`
- Experiments tab shows which version's log is active

### Added (HMM regime detection)
- `data/regime.py` -- 3-state Gaussian HMM (trending, mean_reverting, volatile) fitted on log returns, rolling volatility, and return autocorrelation
- `use_regime` flag on `build_signals()`, `run_backtest()`, and `TrendSignalAgent` -- when enabled, only enters trades in HMM-detected trending regime
- HMM Regime Filter checkbox in dashboard Backtest tab
- `hmmlearn` and `scikit-learn` added to dependencies
- `scripts/run_experiments.py` -- batch experiment runner

### Experiments run
- **baseline** through **exp-001**: EURUSD 1h, no edge. ADX filter insufficient.
- **exp-002** through **exp-004d**: asset/timeframe sweep. SPY daily showed first positive Sharpe (1.05) but too few trades.
- **exp-006a** through **exp-006g**: HMM regime filter. Dramatically improved drawdowns. SPY 10y daily + HMM: Sharpe 1.20, 162% return, but 12 trades.
- **exp-007b**: SPY 10y daily, EMA 5/20 + HMM -- **GATE PASSED.** Sharpe 1.06, DD 10.5%, 45 trades.
- **exp-007d**: SPY 10y daily, EMA 8/21 + HMM -- **GATE PASSED (best).** Sharpe 1.07, DD 10.7%, 36 trades, 96% return.

### Changed (diagrams)
- `v0.1.0.md` YAML front-matter updated to reflect current architecture: added `indicators`, `regime` (HMM), and `multi_asset` nodes; updated gate criteria to include Trades >= 30; next version updated to "Walk-Forward + Paper Trading"
- `diagram_from_v010_spec()` (dataflow) -- added Regime Detection subgraph (features, GaussianHMM, regime labels) with dual path from OHLCV; added Gate Check node
- `diagram_from_class_model()` -- added `data/regime.py` subgraph (Regime enum, detect_regimes, _build_features, _label_states); updated backtest module to show build_signals/backtest_pandas/run_backtest/_check_gate decomposition; removed vectorbt references
- `diagram_from_instance_flow()` -- replaced vectorbt branch with `use_regime?` HMM branch; added gate check (PASS/FAIL) at end of flow
- Diagram generation is now **branch-aware**: auto-detects semver from current git branch, only generates diagrams for that version; `--all` flag overrides; `--version` flag for explicit targeting
- `DIAGRAM_REGISTRY` entries now carry a version tag for filtering

### Changed (experiment log structure)
- `EXPERIMENT_LOG.md` restructured into 5 narrative phases so readers can follow the progression from baseline to gate pass
- Each phase has a guiding question, summary of what was learned, and a focused results table
- Experiment queue expanded with full descriptions: exp-008 (walk-forward validation), exp-005 (ATR trailing stop), exp-015 (regime-aware position sizing), including method, success criteria, and dependencies
- In-sample caveat made explicit throughout

### Multi-asset sweep (exp-010 through exp-014)
- Swept 15+ assets across equities, forex, commodities, bonds, crypto, and equity sectors/singles.
- Forex (EURUSD), bonds (TLT), and REITs (VNQ) lack trend persistence -- no configurations pass.
- Crypto (ETH-USD) has excellent Sharpe but drawdown (>40%) fails the gate.
- High-beta tech (QQQ, XLK, SMH) has strong Sharpe but excessive DD -- wider EMAs tame QQQ just under 20%.
- HMM regime filter is essential for assets with high drawdown risk (SPY, MSFT, AAPL); it halves their DD.
- **6 assets now pass the v0.1.0 gate:**
  1. **SPY** EMA 8/21 + HMM -- Sharpe 1.07, DD 10.7%, 36 trades
  2. **DIA** EMA 5/20, no filter -- Sharpe 0.86, DD 19.8%, 64 trades
  3. **QQQ** EMA 12/35, no filter -- Sharpe 0.89, DD 19.9%, 31 trades
  4. **MSFT** EMA 8/21 + HMM -- Sharpe 0.97, DD 19.3%, 39 trades
  5. **AAPL** EMA 5/20 + HMM -- Sharpe 1.17, DD 19.8%, 48 trades
  6. **GLD** EMA 10/30, no filter -- Sharpe 0.86, DD 18.8%, 43 trades

---

## Next -- v0.2.0

Paper trading via Alpaca. See `planning/system_specs/v0.2.0/v0.2.0.md`.
