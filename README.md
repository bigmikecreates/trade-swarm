# Trade-Swarm

Trade-Swarm is a multi-agent trading system designed to deliver disciplined, risk-aware performance in live market conditions. Instead of relying on a single strategy, it coordinates multiple decision-making agents—each responsible for signal generation, risk control, and execution—to produce more robust and adaptive trading outcomes.

Every component within the system is introduced only after meeting strict performance and risk standards **(gates)**, ensuring that improvements translate into real, measurable results rather than added complexity.

---

## v0.1.0 — Prove the signal (summary)

Walk-forward validated EMA crossover on SPY, QQQ, GLD. Gate: Sharpe > 0.8, Max DD < 20%, Trades ≥ 30. HMM regime filter overfits; unfiltered crossover passes. Full details: `planning/system_specs/v0.1.0/`, `planning/research/v0.1.0/RESEARCH.md`.

---

## v0.2.0 — Paper trading loop (current)

Take the validated backtest live against real market data via Alpaca paper trading. No real money.

**Prerequisites:**
1. [Alpaca](https://alpaca.markets) paper account — sign up, generate API keys
2. [Docker](https://docker.com) (for Redis via Docker Compose)

**Setup:**
```bash
# 1. Start Redis
docker compose up -d

# 2. Copy .env.example to .env and add your Alpaca keys (or export them)
cp .env.example .env
# Edit .env: ALPACA_API_KEY=..., ALPACA_SECRET_KEY=...

# 3. Install and run
pip install -e .
trade-swarm-paper                    # start the paper trading loop
streamlit run dashboard/app.py       # P&L dashboard
python scripts/activate_kill_switch.py   # emergency halt
```

**4-week gate:** Test locally for ~1 day first. For the full 4-week run, deploy to a VPS — see `planning/system_specs/v0.2.0/VPS_DEPLOYMENT.md` for the step-by-step guide (DigitalOcean, Linode, etc.).

The loop skips trading when the market is closed, resets daily equity at market open, waits for order fills before logging, and computes P&L on exit.

**Gate to exit v0.2.0:** 4 continuous weeks of paper trading, all orders logged to SQLite, P&L dashboard accurate, kill switch tested.

---

## Quick start

```bash
pip install -e .
```

```bash
trade-swarm-backtest              # run the backtest
trade-swarm-ui                    # Flask dashboard → http://localhost:5000
trade-swarm-paper                 # paper trading loop (v0.2.0)
streamlit run dashboard/app.py   # Streamlit P&L dashboard (v0.2.0)
trade-swarm-diagrams --src-only   # generate Mermaid .mmd files
```

> `vectorbt` and `pandas-ta` are optional and require Python 3.10–3.13. On Python 3.14+, a pure-pandas fallback is used automatically.

---

## What's in the box

**Core** — the pieces that do the work:

| Module | Purpose |
|---|---|
| `data/fetcher.py` | OHLCV download via yfinance |
| `data/indicators.py` | EMA, RSI, ADX, ATR — pure pandas, no numba |
| `data/regime.py` | 3-state HMM regime detector (trending / mean-reverting / volatile) |
| `agents/signal/trend_agent.py` | EMA crossover signal agent with optional HMM regime filter |
| `backtest/run.py` | Backtest runner with gate evaluation and regime-aware entry logic |
| `brokers/alpaca_adapter.py` | Alpaca order execution (v0.2.0) |
| `risk/gate.py` | Basic risk gate — kill switch, daily loss limit, position size, duplicate check |
| `risk/position_sizer.py` | 1% risk per trade sizing |
| `logging/trade_log.py` | SQLite trade audit trail |
| `config.py` | All tunables in one place |

**Dashboards:**
- **Flask** (`trade-swarm-ui`) — Backtest, Signal, Experiments, Diagrams
- **Streamlit** (`streamlit run dashboard/app.py`) — P&L, trade history, cumulative returns (v0.2.0)

**Planning & tooling:**

| Path | Purpose |
|---|---|
| `planning/system_specs/` | Version specs, checklists, experiment logs |
| `planning/system_specs/v0.2.0/VPS_DEPLOYMENT.md` | Step-by-step VPS deployment for 4-week gate |
| `planning/diagrams/` | Generated Mermaid diagrams (`.mmd` + `.svg`) |
| `scripts/generate_mmd_diagrams.py` | Four diagram types — Structure, Movement, Runtime, Spec Plan |

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
