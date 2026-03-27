# Changelog

All notable changes to this project will be documented in this file.

## [v0.3.0] - 2026-03-27

### Added
- **Agent Laboratory** (`lab/`): Complete backtesting framework
  - Signal agents: trend_signal, momentum, breakout, mean_reversion
  - RiskAgent: VaR, drawdown, position heat evaluation
  - RegimeAgent: Rule-based (ADX+ATR) and HMM classifiers
  - ExecutionAgent: Market/limit/stop orders, volatility sizing
  - SentimentAgent: Placeholder for FinBERT/news APIs
- Metrics layer: signal, risk, regime, execution, sentiment metrics
- PostgreSQL persistence: table-per-strategy schema
- Flask dashboard: 6 pages (Overview, Experiments, Detail, Compare, Trades, Signals)
- CLI: Better help text, examples, agent validation
- Cleanup job: argparse, --ttl, --dry-run options
- Playwright as dev dependency for dashboard testing

### Changed
- Replaced Streamlit dashboard with Flask
- Updated version references from v0.2.0 to v0.3.0

### Fixed
- Critical backtest runner bugs (duplicate short entry, cash flow, exit fees)
- Synthetic GBM price scale ($1 → $100)
- datetime.utcnow() deprecation
- pd.concat FutureWarning

## [v0.2.0] - 2026-01-XX

### Added
- Paper trading loop via Alpaca
- Redis kill switch
- Basic 4-rule risk gate
- SQLite trade log
- Streamlit P&L dashboard

### Changed
- Docker Compose for Redis

## [v0.1.0] - 2025-XX-XX

### Added
- EMA crossover strategy
- Walk-forward validation
- HMM regime filter (overfit - disabled)

---

*Note: Full version history available on GitHub releases.*
