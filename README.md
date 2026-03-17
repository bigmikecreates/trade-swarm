# Trade-Swarm

Trade-Swarm is a multi-agent trading system designed to deliver disciplined, risk-aware performance in live market conditions. Instead of relying on a single strategy, it coordinates multiple decision-making agents—each responsible for signal generation, risk control, and execution—to produce more robust and adaptive trading outcomes.

Every component within the system is introduced only after meeting strict performance and risk standards **(gates)**, ensuring that improvements translate into real, measurable results rather than added complexity.

---

## v0.1.0 — Prove the signal

The goal of v0.1.0: prove the EMA crossover strategy can pass a hard performance gate with genuine out-of-sample edge.

**The gate:**

| Metric | Threshold |
|---|---|
| Sharpe Ratio | > 0.8 |
| Max Drawdown | < 20% |
| Total Trades | >= 30 |

**Walk-forward validated — 3 assets pass out-of-sample:**

| Asset | Class | EMA | OOS Sharpe | OOS Max DD | OOS Trades | OOS Return |
|---|---|---|---|---|---|---|
| SPY | US Equity (Large Cap) | 8/21 | 0.88 | 16.4% | 35 | 110% |
| QQQ | US Equity (Tech) | 8/25 | 0.96 | 17.6% | 33 | 171% |
| GLD | Commodity (Gold) | 7/18 | 0.85 | 18.7% | 33 | 79% |

These results use rolling 5y-train / 1y-test windows — no look-ahead bias. The unfiltered EMA crossover has a genuine edge on assets with persistent trends. The HMM regime filter, while effective in-sample, overfits and does not survive walk-forward validation. Full experiment history in `planning/system_specs/v0.1.0/EXPERIMENT_LOG.md`.

### Cost model

All v0.1.0 backtests use a **flat 0.1% fee per trade** — no spread, slippage, commissions, or swap fees modeled. This is intentional.

**Why it's sufficient for v0.1.0:** The goal was to prove the signal, not to model execution realism. The question was: does EMA crossover have genuine out-of-sample edge? The 0.1% fee is a simple, consistent assumption that lets us compare strategies and assets fairly. For liquid ETFs like SPY, QQQ, and GLD, it's a reasonable upper bound — spreads are tight and retail brokers often offer commission-free ETF trading.

**Why spread, slippage, commissions, and swap are deferred:** v0.1.0 is backtest-only. Spread and slippage depend on broker, venue, and order type — modeling them in detail without execution context would be speculative. Commission and swap fees matter more for forex and leveraged positions (assets that failed the gate in v0.1.0). The methodology explicitly defers cost validation to later versions: v0.2.0 paper trading will surface real execution costs, and R6 (open research question) targets v0.4.0 for comparing live slippage against the 0.1% model.

The flat fee is a deliberate simplification for the research phase — conservative enough to be useful, simple enough to keep focus on signal quality. Execution costs are validated when we actually execute.

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
