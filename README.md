# Trade-Swarm

Trade-Swarm is a multi-agent trading system designed to deliver disciplined, risk-aware performance in live market conditions. Instead of relying on a single strategy, it coordinates multiple decision-making agents—each responsible for signal generation, risk control, and execution—to produce more robust and adaptive trading outcomes.

Every component within the system is introduced only after meeting strict performance and risk standards **(gates)**, ensuring that improvements translate into real, measurable results rather than added complexity.

---

## v0.1.0 — Prove the signal (summary)

Walk-forward validated EMA crossover on SPY, QQQ, GLD. Gate: Sharpe > 0.8, Max DD < 20%, Trades ≥ 30. HMM regime filter overfits; unfiltered crossover passes. Full details: `planning/system_specs/v0.1.0/`, `planning/research/v0.1.0/RESEARCH.md`.

---

## v0.2.0 — Paper trading loop (current)

Take the validated backtest live against real market data via Alpaca paper trading. No real money.

**What this is (and isn’t):** One process, **one symbol at a time** (default **SPY**), **daily** bars — matching the v0.1.0 validated EMA crossover on SPY. The loop is intentionally small so fills, Redis gate state, and logs are easy to reason about before adding multi-asset or intraday complexity.

**Why not SPY + QQQ + GLD all at once?** Those three were validated **independently** in backtests; v0.2.0 is a **single-symbol** paper harness. Running everything in parallel would need per-symbol positions, caps, and gate keys (or a portfolio layer) — planned for later versions. You can still paper **each** symbol by changing `PAPER_SYMBOL` in `.env` and running separate sessions (or sequential test windows), not by trading all three in one loop today.

**Why it can feel “slow”:** With **daily** data, the signal mostly updates when the **latest daily bar** moves (and at the day boundary). The **`PAPER_CHECK_INTERVAL`** (default **300s**) is how often the loop **re-polls** — it does not make daily EMAs react faster. Lowering the interval only increases checks/API churn; use **shorter bar intervals** (e.g. 5m / 15m) when the codebase supports them if you want intraday-style updates.

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

**Configuration (env / `config.py`):**

| Variable | Role |
|----------|------|
| `PAPER_SYMBOL` | Ticker to trade (default `SPY`). QQQ/GLD were validated in v0.1.0; tune EMAs in `config.py` if you switch symbols. |
| `PAPER_CHECK_INTERVAL` | Seconds between loop iterations (default `300`). |
| `PAPER_INTERVAL` / `PAPER_PERIOD` | yfinance bar size and lookback (default daily `1d`, `60d`). |

**Logs:** `data/agent_activity.jsonl` (append-only JSONL: signals, gate, errors) and `data/trades.db` (SQLite: fills / PnL). See `logging/activity_log.py` and `logging/trade_log.py`.

**Restarting with an open position:** Safe. Alpaca holds the real position; on startup the loop syncs Redis’s duplicate-order flag with the broker and resumes managing the same symbol (entries/exits from live positions).

**Gate to exit v0.2.0:** 4 continuous weeks of paper trading, all orders logged to SQLite, P&L dashboard accurate, kill switch tested.

**Day trading / intraday (roadmap):** Daily paper is for **execution plumbing** and **discipline** with the validated strategy. **Intraday** has different noise, costs, and statistics; it’s useful for practicing **order flow, sizing, and emotional cadence**, but it does **not** automatically transfer the edge from a daily EMA strategy. A sensible path is: stabilize daily paper → validate intraday rules in backtest → paper with **short bars + wider caps** (future work).

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

### Two UIs — why both?

| | **Flask** (`trade-swarm-ui` → port **5000**) | **Streamlit** (`streamlit run dashboard/app.py`) |
|---|----------------|------------|
| **Purpose** | **Research & backtests** (v0.1.0 workflow): run historical simulations, inspect gate metrics, signals, experiments, diagrams. | **Live paper P&L** (v0.2.0): reads **`data/trades.db`** filled by the Alpaca paper loop (`log_trade` on fills). |
| **Data source** | yfinance + `backtest/run.py` — whatever symbol/interval you POST from the UI (defaults in `config.py`, e.g. `EURUSD=X` / `1h`). | **SQLite only** — same `trades.db` as `logging/trade_log.py`. Not wired to Flask. |
| **“No data”** | Normal until you open **Backtest** and run one (Dashboard then shows metrics). | Normal until the **paper loop** has logged at least one row (entries/exits). Activity without fills lives in **`agent_activity.jsonl`**, not here. |

They solve different problems: **Flask = offline strategy lab**; **Streamlit = paper trading journal / P&L view**. Neither replaces the other.

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
| `logging/activity_log.py` | Append-only JSONL loop audit (`data/agent_activity.jsonl`) |
| `config.py` | All tunables in one place (paper keys via `.env`) |

**Dashboards:**
- **Flask** (`trade-swarm-ui`) — Backtest, Signal, Experiments, Diagrams (historical research; not Alpaca live state)
- **Streamlit** (`streamlit run dashboard/app.py`) — P&L, trade history, cumulative returns from **`data/trades.db`** (v0.2.0 paper fills)

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
