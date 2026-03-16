# Trade-Swarm

Multi-asset trading agent system built on walk-forward validated strategies and a gated version roadmap. Each version must pass quantitative performance gates before the next begins.

**Current version: v0.1.0** · [Release notes](https://github.com/bigmikecreates/trade-swarm/releases/tag/v0.1.0)

---

## System status

| Version | Branch | Status | Summary |
|---------|--------|--------|---------|
| **v0.1.0** | `v0.1.0` | **Complete** | Prove the signal — EMA crossover research |
| v0.2.0 | — | Planned | Paper trading loop + basic risk rules |
| v0.3.0 | — | Planned | Second signal agent + regime detection |
| v0.4.0 | — | Planned | Orchestrator + risk agent + sentiment |
| v0.5.0 | — | Planned | Infrastructure hardening (Docker, Postgres, Grafana) |
| v0.9.0 | — | Planned | Extended paper trading + ML confidence layer |
| v1.0.0 | — | Planned | Live trading with training wheels |

---

## v0.1.0 — Prove the signal (current)

**Question:** Can a simple EMA crossover strategy, with appropriate filtering, pass a hard performance gate on multiple assets with genuine out-of-sample edge?

**Gate criteria:** Sharpe > 0.8 · Max drawdown < 20% · Trades >= 30

### Research arc

80+ experiment runs across 15+ assets in 5 phases:

1. **Baseline** — EURUSD hourly, EMA 20/50. No edge; forex mean-reverts.
2. **Asset/timeframe search** — SPY daily showed the first positive Sharpe (1.05).
3. **HMM regime detection** — 3-state Gaussian HMM halved drawdowns in-sample.
4. **EMA tuning** — tighter EMAs (8/21, 5/20) passed gate on SPY.
5. **Multi-asset validation** — 6 assets passed in-sample.
6. **Walk-forward validation** — rolling 5y-train / 1y-test. HMM did not survive. 3 assets passed.

### Walk-forward validated results

| Asset | EMA | OOS Sharpe | OOS Max DD | OOS Trades | OOS Return |
|-------|-----|------------|------------|------------|------------|
| SPY | 8/21 | 0.88 | 16.4% | 35 | 110% |
| QQQ | 8/25 | 0.96 | 17.6% | 33 | 171% |
| GLD | 7/18 | 0.85 | 18.7% | 33 | 79% |

### Key findings

1. **EMA crossover works on diversified, structurally trending instruments** — SPY, QQQ, GLD pass. Narrow indices, single stocks, forex, and energy fail.
2. **HMM regime filter overfits** — transformative in-sample, doesn't generalize walk-forward. Useful as a research tool, not a production filter.
3. **In-sample results are meaningless without walk-forward** — 6 passed IS, only 3 survived OOS.
4. **Asset class diversification requires strategy diversification** — each asset class has distinct microstructure requiring its own strategy type.
5. **Drawdown is the binding constraint** — Sharpe is achievable; max DD < 20% is what kills most configurations.

### Generating diagrams

The v0.1.0 branch includes a diagram generator (`scripts/generate_mmd_diagrams.py`) that produces Mermaid flowcharts serving two roles in the spec-driven development process.

**Prescriptive — what we plan to build** (spec is the source of truth):

| Type | What it shows |
|------|---------------|
| **Spec plan** | High-level build plan extracted from YAML front-matter in each version spec |

Spec plan diagrams are generated directly from the `spec_diagram:` block in each version's spec file (e.g., `planning/system_specs/v0.1.0/v0.1.0.md`). The spec defines the build steps and dependencies; the diagram visualizes that plan. Adding a `spec_diagram:` block to any future version spec automatically generates its diagram — no code changes needed.

**Descriptive — what we built** (code is the source of truth):

| Type | What it shows |
|------|---------------|
| **Class model** | Static structure — modules, classes, methods, and their relationships |
| **Data flow** | How data moves: Yahoo Finance -> indicators -> agent -> backtest -> gate |
| **Runtime call graph** | Step-by-step execution when `run_backtest()` runs, including the HMM branch |

These three document the v0.1.0 codebase as-built. They are hand-authored in the script to match the actual implementation, providing architecture documentation for each completed version.

```bash
# Generate .mmd source files only (no Node.js required)
python scripts/generate_mmd_diagrams.py --src-only

# Generate .mmd + render .svg (requires Node.js + @mermaid-js/mermaid-cli)
python scripts/generate_mmd_diagrams.py

# Target a specific version, or generate all
python scripts/generate_mmd_diagrams.py --version v0.1.0
python scripts/generate_mmd_diagrams.py --all
```

The script auto-detects the current branch version, so running it on the `v0.1.0` branch generates only v0.1.0 diagrams. Output goes to `planning/diagrams/` organized by type.

### Open research questions

| ID | Question | Target |
|----|----------|--------|
| R1 | Can volatility-scaled position sizing improve DD and rescue near-misses? | v0.2.0 |
| R2 | Does an ATR trailing stop beat EMA crossover exits? | v0.2.0 |
| R3 | Can mean-reversion capture forex edge? | v0.3.0 |
| R4 | Can simpler regime proxies (ADX, vol percentile) replace the HMM? | v0.3.0 |
| R5 | What correlation threshold governs portfolio inclusion? | v0.2.0 |
| R6 | How does live slippage compare to the 0.1% cost model? | v0.4.0 |

---

## Version roadmap

### v0.2.0 — Paper trading loop + basic risk rules

Take the validated backtest live against real market data via Alpaca paper trading. No real money. Automated order placement, logging to SQLite, P&L dashboard, and a kill switch.

**Exit gate:** 4 continuous weeks of paper trading, all orders logged correctly, kill switch tested.

### v0.3.0 — Second signal agent + regime detection

Add a `MeanReversionAgent` (RSI + Bollinger Bands) for ranging markets alongside the existing `TrendSignalAgent`. Build a `RegimeAgent` to classify conditions and route to the appropriate strategy. Wire agents via Redis pub/sub.

**Exit gate:** Both agents individually profitable over 4+ weeks in paper trading, regime switching visible in logs.

### v0.4.0 — Orchestrator + risk agent + sentiment

Wire all specialist agents through a LangGraph orchestrator for final trade decisions. Add a `RiskAgent` with VaR and drawdown tracking. Add a `SentimentAgent` using FinBERT on Alpaca news. Expand to 2-3 assets.

**Exit gate:** 8 weeks paper trading, portfolio Sharpe > 1.0, max drawdown < 15%.

### v0.5.0 — Infrastructure hardening

Docker containers, Postgres (replacing SQLite), Grafana monitoring, Telegram kill switch, full audit log. The system must run 48 hours unattended on a VPS with no crashes or data loss.

**Exit gate:** 48h unattended run, Telegram kill switch reachable, all 16 risk gate rules active.

### v0.9.0 — Extended paper trading + ML layer

3 continuous months of paper trading across all target asset classes. XGBoost ML confidence layer on top of rule-based signals. Walk-forward parameter optimization. Stress testing against 2008, 2020, and 2022 scenarios.

**Exit gate:** 3 months paper trading, Sharpe > 1.0, max drawdown < 15%, stress tests passed.

### v1.0.0 — Live trading with training wheels

Deploy real capital at 1-2% of intended allocation. Shadow mode (paper + live simultaneously). Scale only after 30 consecutive live trading days with no critical incidents and performance matching paper.

**Exit gate:** 30 live days, performance within 20% of paper, max live drawdown < 10%.

---

## Project structure

```
trade-swarm/
├── agents/signal/          # Signal generation agents (TrendSignalAgent)
├── backtest/               # Backtesting engine + walk-forward validation
├── data/                   # Data fetching, indicators, regime detection
├── planning/
│   ├── research/           # Versioned research journals + methodology
│   └── system_specs/       # Version specs, checklists, experiment logs
├── scripts/                # Experiment runners and utilities
├── ui/                     # Dashboard (Flask + vanilla JS)
├── config.py               # Central configuration
├── pyproject.toml          # Package metadata
└── requirements.txt        # Dependencies
```

## Methodology

All strategies follow the walk-forward validation protocol defined in [`planning/research/METHODOLOGY.md`](planning/research/METHODOLOGY.md) (available on the `v0.1.0` branch):

- **Walk-forward:** 5-year train / 1-year test / 1-year step, rolling windows
- **Gate:** Sharpe > 0.8, Max DD < 20%, Trades >= 30 on concatenated OOS equity curve
- **Cost model:** flat 0.1% per trade (to be validated against live fills in v0.4.0)
- **Indicators:** pure pandas, no external indicator libraries

## License

MIT
