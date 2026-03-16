# Trade-Swarm

A multi-agent trading system built around a simple idea: no feature ships until the strategy proves it works.

Trade-Swarm grows version by version. Each version has a **gate** — a set of performance thresholds the strategy must pass before new capabilities are unlocked. This keeps the system honest and experiment-driven.

---

## v0.1.0 — Prove the signal

The goal of v0.1.0: prove the EMA crossover strategy can pass a hard performance gate across multiple assets, using an HMM regime filter to trade only in trending markets.

**The gate:**

| Metric | Threshold |
|---|---|
| Sharpe Ratio | > 0.8 |
| Max Drawdown | < 20% |
| Total Trades | >= 30 |

**Where we stand — 6 assets pass (in-sample, 10y daily):**

| Asset | Class | EMA | Filter | Sharpe | Max DD | Trades | Return |
|---|---|---|---|---|---|---|---|
| SPY | US Equity (Large Cap) | 8/21 | HMM | 1.07 | 10.7% | 36 | 96% |
| DIA | US Equity (Large Cap) | 5/20 | None | 0.86 | 19.8% | 64 | 98% |
| QQQ | US Equity (Tech) | 12/35 | None | 0.89 | 19.9% | 31 | 164% |
| MSFT | US Equity (Single Stock) | 8/21 | HMM | 0.97 | 19.3% | 39 | 202% |
| AAPL | US Equity (Single Stock) | 5/20 | HMM | 1.17 | 19.8% | 48 | 312% |
| GLD | Commodity (Gold) | 10/30 | None | 0.86 | 18.8% | 43 | 139% |

The HMM regime filter is essential for high-beta assets (SPY, MSFT, AAPL) where it halves drawdown. Lower-volatility trending assets (DIA, QQQ, GLD) pass without it. Full experiment history in `planning/system_specs/v0.1.0/EXPERIMENT_LOG.md`.

**Next:** walk-forward validation on the top configurations to confirm out-of-sample robustness.

---

## Quick start

```bash
pip install -e .
```

```bash
trade-swarm-backtest              # run the backtest
trade-swarm-ui                    # launch the dashboard → http://localhost:5000
trade-swarm-diagrams --src-only   # generate Mermaid .mmd files
```

> `vectorbt` and `pandas-ta` are optional and require Python 3.10–3.13. On Python 3.14+, a pure-pandas fallback is used automatically.

---

## What's in the box

**Core** — the pieces that do the work:

| Module | Purpose |
|---|---|
| `data/fetcher.py` | OHLCV download via yfinance |
| `data/indicators.py` | EMA, RSI, ADX — pure pandas, no numba |
| `data/regime.py` | 3-state HMM regime detector (trending / mean-reverting / volatile) |
| `agents/signal/trend_agent.py` | EMA crossover signal agent with optional HMM regime filter |
| `backtest/run.py` | Backtest runner with gate evaluation and regime-aware entry logic |
| `config.py` | All tunables in one place (symbol, EMA params, gate thresholds) |

**Dashboard** — a Flask UI with five tabs:

| Tab | What it does |
|---|---|
| Dashboard | Strategy config and gate status at a glance |
| Backtest | Run backtests with custom parameters; equity curve and price+signal charts |
| Signal | Generate a live signal from `TrendSignalAgent` for any symbol |
| Experiments | View the experiment log from `EXPERIMENT_LOG.md` |
| Diagrams | Browse and render Mermaid `.mmd` diagrams |

**Planning & tooling:**

| Path | Purpose |
|---|---|
| `planning/system_specs/` | Version specs, checklists, and experiment logs |
| `planning/diagrams/` | Generated Mermaid diagrams (`.mmd` + `.svg`) |
| `scripts/generate_mmd_diagrams.py` | Generates four diagram types — Structure, Movement, Runtime, Spec Plan |

---

## Generating diagrams

Diagrams are **branch-aware** — the generator auto-detects the current git branch's version and only produces diagrams for that version. On `main` or unversioned branches, all versions are generated.

```bash
trade-swarm-diagrams --src-only          # current branch's version only
trade-swarm-diagrams --src-only --all    # all versions
trade-swarm-diagrams --version v0.2.0    # explicit version override
trade-swarm-diagrams                     # .mmd + .svg (needs Node.js + mermaid-cli)
```

To add diagrams for a new version, put a `spec_diagram:` YAML front-matter block in `planning/system_specs/<version>/<version>.md` and register any hardcoded Python diagram functions in `DIAGRAM_REGISTRY` with the version tag.

| Diagram type | Folder | Shows |
|---|---|---|
| Structure | `class_model/` | Modules, classes, methods |
| Movement | `dataflow/` | Data flow through the system |
| Runtime | `instance_flow/` | Step-by-step backtest execution |
| Spec Plan | `spec_diagrams/` | High-level build plan per version |
