# Trade-Swarm Agent Laboratory — Implementation Summary

## Context

**Project:** Trade-Swarm Agent Laboratory  
**Goal:** A lab environment for validating specialist trading agents before integrating into live trading. Two modes:
- **Mechanics validation** — synthetic GBM data verifies architecture invariants (stop loss fires, P&L calculates, logs generate correctly)
- **Strategy validation** — real market data from multiple sources tests agent performance

---

## Completed Phases

### Phase 1 — Core Lab Structure ✅

Built and verified end-to-end.

**Files created:**
```
lab/
├── synthetic/
│   ├── configs/                        # 4 YAML configs
│   │   ├── default.yaml                # Standard GBM
│   │   ├── vol_spike.yaml              # Sudden vol expansion
│   │   ├── gap_event.yaml             # Overnight gaps
│   │   └── latency.yaml               # Network delay simulation
│   └── generator.py                   # GBM engine → DataFrame
├── data/
│   ├── fetcher.py                     # Unified interface (swappable sources)
│   ├── sources/
│   │   └── synthetic_gbm.py           # Synthetic data source
│   └── persistence/
│       ├── interfaces.py               # Abstract DataStore contract
│       ├── directory_store.py          # Canonical directories
│       ├── redis_stream.py            # Redis Streams (Phase 6 ready)
│       └── workers/                   # Idempotent workers (Phase 6 ready)
├── harness/
│   ├── factory.py                   # Agent registry + builder
│   ├── runner.py                     # Single experiment runner
│   ├── batch_runner.py               # Parallel Monte Carlo + splits
│   └── coordinator.py                # Multi-agent wiring
├── cli.py                           # lab run / batch / mechanics / eval / list / cleanup
├── cleanup_job.py                    # Auto-cleanup cron job
├── config/lab_config.py
├── dashboard/app.py                  # Streamlit shell
└── requirements.txt
```

**Makefile** created at repo root with commands:
```bash
make help                              # Show all commands
make agents                            # List agents
make run AGENT=trend_signal SOURCE=synthetic
make batch AGENT=trend_signal SPLITS="70/30,75/25"
make mechanics RUNS=500
make list STRATEGY=trend_signal
make eval RUN=exp_001
make cleanup-dry
make cleanup TTL=5
make dashboard
make clean
```

---

## Decisions Made

### Data Persistence Strategy
- **Redis Streams** (72h retention) → **PostgreSQL** (indefinite, tables per strategy) → **Canonical Directories** (5-7 day TTL, global sweep)
- Directories are canonical (fast-access), PostgreSQL is mirror (durable)
- Cleanup is automatic with global sweep every 5-7 days

### Data Sources (Priority Order)
| Priority | Source | Status |
|---|---|---|
| 1 | **yfinance** | Works now — equities, ETFs, crypto |
| 2 | **Synthetic GBM** | Works now — mechanics validation |
| 3 | **cTrader Open API** | After demo account setup |
| 4 | **HISTDATA.com** | Download once, use forever |
| 5 | **IBKR TWS** | When TWS is running |
| 6 | **MT5** | Deferred indefinitely (Windows VPS cost) |

### Experiment Naming
```
[DD-Mon-YY][HH:MM:SS]-experiment_run-[strategy_name]
Example: [27-Mar-26][14:32:05]-experiment_run-[mean_reversion]
```

### PostgreSQL Schema (Future)
- One database: `trade_swarm_lab`
- One **table per strategy** (not schema per strategy): `trend_signal_trades`, `mean_reversion_trades`, etc.
- Shared tables: `experiments`, `strategies`

### Synthetic GBM
- Used for **architecture mechanics validation only** — not strategy testing
- Single GBM config to validate invariants: stop loss fires, P&L calculates, logs generate
- Four configs available: default, vol_spike, gap_event, latency
- Monte Carlo batches (500 runs) for robustness testing

---

## Remaining Phases

### Phase 2 — Agents Implementation
Implement `lab/agents/`:
- [ ] `signal/trend_agent.py` — EMA crossover (from v0.2.0)
- [ ] `signal/mean_reversion.py` — RSI + Bollinger Bands
- [ ] `signal/breakout.py` — Donchian + ATR
- [ ] `signal/momentum.py` — Rate of change

### Phase 3 — Real Data Sources
Add `lab/data/sources/`:
- [ ] `yfinance_source.py`
- [ ] `ctrader/base.py` + `ic_markets.py` + `pepperstone.py` + `eightcap.py`
- [ ] `histdata_source.py`
- [ ] `ibkr_source.py`

### Phase 4 — Remaining Agents
- [ ] `risk/risk_agent.py` — Full RiskAgent (VaR, drawdown, position heat)
- [ ] `regime/rule_based.py` — ADX + ATR ratio classifier
- [ ] `regime/hmm.py` — HMM classifier (from v0.2.0)
- [ ] `execution/execution_agent.py` — ExecutionAgent
- [ ] `sentiment/sentiment_agent.py` — SentimentAgent (FinBERT)

### Phase 5 — Metrics Layer
Add `lab/metrics/`:
- [ ] `signal_metrics.py`
- [ ] `risk_metrics.py`
- [ ] `regime_metrics.py`
- [ ] `execution_metrics.py`
- [ ] `sentiment_metrics.py`

### Phase 6 — PostgreSQL + Redis
- [ ] `postgres_store.py` — Table per strategy
- [ ] Wire Redis Streams → PostgreSQL → Directories
- [ ] Idempotent workers (postgres_worker, directory_worker)
- [ ] `redis_stream.py` production config

### Phase 7 — Full Dashboard
- [ ] Streamlit charts for all agent types
- [ ] Experiment comparison view
- [ ] Equity curve visualization
- [ ] Trade log viewer
- [ ] Signal history

### Phase 8 — Polish
- [ ] CLI refinement
- [ ] Documentation
- [ ] cron setup for cleanup_job.py

---

## How to Continue After Context Limit

When context runs out, a new conversation can continue from this file. Key things to know:

1. **Everything built is in `/home/bigmike/bigmike/git-projects/trade-swarm/lab/`**
2. **Read `lab/README.md`** (if created) or this file for context
3. **Dependencies installed:** `numpy`, `pandas`, `pyyaml`, `pyarrow`, `redis`, `streamlit`, `yfinance`
4. **Next step:** Phase 2 — implement the agents
5. **To run:** `make test` from repo root or `python lab/cli.py run --agent trend_signal --source synthetic`

---

## Key Files Reference

| File | Purpose |
|---|---|
| `lab/synthetic/generator.py` | Generates synthetic OHLCV via GBM |
| `lab/data/fetcher.py` | Unified data source interface |
| `lab/harness/runner.py` | Single experiment execution |
| `lab/harness/batch_runner.py` | Monte Carlo + split batches |
| `lab/data/persistence/directory_store.py` | Canonical directory storage |
| `lab/data/persistence/interfaces.py` | Abstract storage contract |
| `Makefile` | All CLI commands at repo root |
| `lab/requirements.in` | Unpinned dependencies (edit here) |
| `lab/requirements.txt` | Pinned lockfile (auto-generated via `make lock`) |
| `lab/pyproject.toml` | Package metadata + optional deps (dev, postgres) |
