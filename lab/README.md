# Trade-Swarm Agent Laboratory

A comprehensive framework for validating trading agent strategies before live deployment. Enables backtesting, batch experiments, and mechanics validation on both synthetic and real market data.

## Quick Start

```bash
# Setup
make venv          # Create virtual environment
make install-deps  # Install dependencies

# Run experiments
make test                           # Quick synthetic test
make run AGENT=trend_signal SOURCE=synthetic
make run AGENT=trend_signal SOURCE=yfinance SYMBOL=SPY PERIOD=5y

# Batch experiments
make batch AGENT=trend_signal SPLITS="70/30,75/25,80/20"
make batch AGENT=trend_signal MONTE_CARLO=500

# Mechanics validation
make mechanics RUNS=500

# Other commands
make list                # List experiments
make eval RUN=exp_001   # Evaluate experiment
make dashboard           # Flask dashboard
make clean              # Clean experiment directories
```

## Project Structure

```
lab/
├── agents/              # Trading agents
│   ├── signal/        # Signal generation
│   ├── risk/          # Risk management
│   ├── regime/        # Market regime detection
│   ├── execution/      # Order execution
│   └── sentiment/     # Sentiment analysis
├── harness/            # Backtest execution
│   ├── runner.py      # Single experiment runner
│   ├── batch_runner.py # Monte Carlo & split batches
│   ├── coordinator.py  # Multi-agent coordination
│   └── factory.py     # Agent factory
├── synthetic/          # Synthetic GBM generator
│   ├── generator.py
│   └── configs/       # GBM configurations
├── data/              # Data sources & persistence
│   ├── fetcher.py     # Unified data interface
│   ├── sources/       # yfinance, cTrader, IBKR, etc.
│   └── persistence/   # Directory, Redis, PostgreSQL
├── dashboard/         # Flask dashboard
│   ├── app.py
│   └── templates/    # HTML templates
├── metrics/           # Performance metrics
│   ├── signal_metrics.py
│   ├── risk_metrics.py
│   ├── regime_metrics.py
│   ├── execution_metrics.py
│   └── sentiment_metrics.py
└── cli.py            # CLI entry point
```

## Data Sources

| Source | Status | Description |
|--------|--------|-------------|
| `synthetic` | Ready | GBM for mechanics validation |
| `yfinance` | Ready | Equities, ETFs, crypto |
| `ctrader_*` | Ready | cTrader brokers (demo account) |
| `ibkr` | Ready | Interactive Brokers (TWS) |
| `histdata` | Ready | Forex M1 data |

## Available Agents

**Signal Agents:**
- `trend_signal` — EMA crossover strategy
- `momentum` — Momentum-based signals
- `breakout` — Donchian breakout
- `mean_reversion` — RSI + Bollinger Bands

**Risk Agents:**
- `risk` — VaR, drawdown, position heat

**Regime Agents:**
- `regime` — Rule-based + HMM classifiers

**Execution Agents:**
- `execution` — Market/limit/stop orders

**Sentiment Agents:**
- `sentiment` — Placeholder for FinBERT

## Configuration

Edit `requirements.in` to add dependencies, then run `make lock` to regenerate `requirements.txt`.

## Documentation

- [AGENTS.md](../AGENTS.md) — Agentic coding guidelines
- [LAB_SUMMARY.md](./LAB_SUMMARY.md) — Implementation details & phase tracking
- [CHANGELOG.md](../CHANGELOG.md) — Version history
