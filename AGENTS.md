# Trade-Swarm Agent Laboratory — Agent Guidelines

## Overview

Trade-Swarm is a quantitative trading research lab with a focus on agentic trading systems. The `lab/` directory contains the experimentation framework for testing trading strategies on synthetic and real market data.

**IMPORTANT**: All Python commands must use the virtualenv (`.venv`), NOT system Python.

## Project Structure

```
trade-swarm/
├── .venv/                    # Virtual environment (created via make venv)
├── Makefile                  # All CLI commands
├── lab/
│   ├── agents/               # Trading agents (signal, execution, risk, regime, sentiment)
│   ├── harness/              # Backtest runner, batch runner, coordinator
│   ├── synthetic/            # Synthetic GBM generator & configs
│   ├── data/                 # Data fetching, sources, persistence
│   ├── config/              # Lab configuration
│   ├── metrics/             # Performance metrics
│   ├── dashboard/           # Streamlit dashboard
│   └── cli.py               # Main CLI entry point
```

## Commands

### Setup

```bash
make venv           # Create .venv virtualenv
make install-deps  # Install dependencies from lab/requirements.txt
```

### Running Experiments

```bash
# Single experiment with synthetic data
make test

# Single experiment with custom settings
make run AGENT=trend_signal SOURCE=synthetic

# Single experiment with real data (yfinance)
make run AGENT=trend_signal SOURCE=yfinance SYMBOL=SPY PERIOD=5y

# Batch experiments with train/test splits
make batch AGENT=trend_signal SPLITS="70/30,75/25,80/20"

# Monte Carlo batch (500 runs)
make batch AGENT=trend_signal MONTE_CARLO=500

# Mechanics validation (500 runs)
make mechanics RUNS=500

# List experiments
make list

# Evaluate specific experiment
make eval RUN=exp_20260327190135
```

### Cleanup

```bash
make clean              # Remove experiment directories
make clean-all          # Remove experiments + __pycache__
make cleanup-dry TTL=5  # Preview directories older than 5 days
make cleanup TTL=5      # Delete directories older than 5 days
```

### Dashboard

```bash
make dashboard  # Run Streamlit dashboard
```

## Code Style Guidelines

### General

- Use Python 3.12+ with type hints
- Use `from __future__ import annotations` for forward references
- Use dataclasses for data structures
- Use `typing.Protocol` for interfaces

### Imports

- Standard library first, then third-party, then local
- Use absolute imports: `from lab.harness.runner import ...`
- Never use relative imports like `from .module import ...`
- Local imports inside functions when circular imports are a problem

### Naming Conventions

- **Classes**: `PascalCase` (e.g., `ExperimentRunner`)
- **Functions/variables**: `snake_case` (e.g., `run_experiment`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `MAX_POSITION_SIZE`)
- **Private methods**: `_private_method(self)`
- **Type aliases**: `PascalCase` ending in `Type` or just the type name

### Type Hints

- Always use type hints for function parameters and return types
- Use `X | None` over `Optional[X]`
- Use `X | Y` over `Union[X, Y]`
- Use `list[X]`, `dict[K, V]` over `List[X]`, `Dict[K, V]`
- Use `Path` from `pathlib` over string paths

### Error Handling

- Use specific exception types
- Prefer "Easier to Ask Forgiveness than Permission" (EAFP) with try/except for expected errors
- Log errors before re-raising
- Never swallow exceptions silently

### Data Handling

- Use pandas DataFrames for time series data
- Use numpy arrays for numerical computations
- Use dataclasses for structured records
- Filter empty DataFrames before `pd.concat` to avoid FutureWarning

### DateTime

- Use `datetime.now(datetime.UTC)` instead of deprecated `datetime.utcnow()`
- Use timezone-aware datetimes throughout
- Use `pandas.Timestamp` for pandas datetime operations

### Strings

- Use f-strings for string formatting
- Use `str.format()` only when necessary
- Use f-strings with `<`, `>` alignment for formatted output

### CLI

- Use `argparse` for CLI tools
- Use hyphenated args in CLI (`--init-cash`) but convert to snake_case internally (`args.init_cash` becomes `init_cash`)

### Testing

- There is no formal test framework yet
- Use `make test` to run a synthetic experiment as a smoke test
- Verify changes by running: `.venv/bin/python lab/cli.py run --agent trend_signal --source synthetic`

### Code Comments

- Avoid unnecessary comments (code should be self-documenting)
- Use docstrings for public APIs and complex functions
- Keep comments up-to-date with code changes

### Logging

- Use standard `logging` module
- Log at appropriate levels: DEBUG, INFO, WARNING, ERROR
- Include context in log messages (run_id, symbol, etc.)

## Known Issues / Technical Notes

1. **Virtualenv is required** — The project uses `.venv` to avoid PEP 668 system Python restrictions
2. **Synthetic GBM is random walk** — EMA crossover on pure random walk loses money (expected behavior)
3. **Initial price 100.0** — Synthetic configs use `initial_price: 100.0` to avoid micro-share issues
4. **Experiment storage** — Experiments stored in `lab/experiments/` with timestamp directories

## Adding New Agents

1. Create agent in appropriate subdirectory: `lab/agents/<type>/`
2. Subclass `SignalAgent` (or appropriate base class)
3. Register in `lab/agents/<type>/register.py`
4. Import in `lab/cli.py` or factory

## Data Sources

- `synthetic`: Synthetic GBM for mechanics validation only
- `yfinance`: Real market data (stocks, ETFs, crypto)
- `ctrader_*`: cTrader brokers (requires demo account)
- `ibkr`: Interactive Brokers (requires TWS running)
- `histdata`: Forex M1 data

## Metrics

Key metrics computed: Sharpe ratio, win rate, max drawdown, total return, trade count.

## Caveats

- Never commit secrets, API keys, or credentials
- Use `.gitignore` to exclude `.venv/`, `lab/experiments/`, and `__pycache__/`
- Always use `.venv/bin/python` for any Python commands
