# v0.2.0 Experiment Log

> **Goal:** Run the validated EMA crossover strategy in paper trading for 4 continuous weeks with no critical bugs.
>
> **Gate to exit:** All orders logged to SQLite; P&L dashboard accurate; kill switch tested.
>
> **Rule:** Log each significant run, configuration change, or incident. One row per observation.

## Methodology

- **Broker:** Alpaca paper trading (no real money)
- **Asset:** SPY (validated in v0.1.0 walk-forward)
- **EMA:** 8/21 (validated for SPY)
- **Interval:** Daily bars, 60d lookback
- **Check frequency:** Every 5 minutes (configurable)
- **Risk:** 1% per trade, max position 10%, daily loss limit 3%

---

## Phase 1 — Setup & first run

**Question:** Does the paper trading loop start, connect to Alpaca, and place at least one order?

| run_id | timestamp | action | result | notes |
|--------|-----------|--------|--------|-------|
| exp-001 | — | Alpaca account created | — | Sign up, generate paper keys |
| exp-002 | — | Redis started | — | `redis-server` or Docker |
| exp-003 | — | `pip install -e .` | — | All deps install cleanly |
| exp-004 | — | `trade-swarm-paper` first run | — | Loop starts, fetches data, prints signal |
| exp-005 | — | First order placed | — | LONG SPY when signal triggers |
| exp-006 | — | Kill switch test | — | Run `activate_kill_switch.py`, confirm no new orders |
| exp-007 | — | Kill switch reset | — | `redis-cli DEL kill_switch`, confirm trading resumes |

---

## Phase 2 — Trade logging & dashboard

**Question:** Are all orders correctly logged to SQLite and reflected in the P&L dashboard?

| run_id | timestamp | trades_logged | dashboard_pnl | alpaca_equity | match | notes |
|--------|-----------|---------------|---------------|---------------|-------|-------|
| exp-008 | — | — | — | — | — | First trade logged |
| exp-009 | — | — | — | — | — | Exit trade logged with pnl |
| exp-010 | — | — | — | — | — | Dashboard cumulative P&L vs Alpaca |

---

## Phase 3 — Risk gate validation

**Question:** Do the 4 risk rules fire correctly when triggered?

| run_id | timestamp | rule_tested | triggered | expected | notes |
|--------|-----------|-------------|-----------|----------|-------|
| exp-011 | — | kill_switch | — | HALT | Manual test |
| exp-012 | — | daily_loss_3pct | — | HALT | Simulate or wait for bad day |
| exp-013 | — | max_position_10pct | — | BLOCK | Large order blocked |
| exp-014 | — | duplicate_order | — | BLOCK | Second LONG when already LONG blocked |

---

## Phase 4 — Continuous run (weeks 1–4)

**Question:** Does the system run for 4 continuous weeks without critical bugs?

| week | start_date | end_date | uptime | trades | bugs | notes |
|------|------------|----------|--------|--------|------|-------|
| 1 | — | — | — | — | — | |
| 2 | — | — | — | — | — | |
| 3 | — | — | — | — | — | |
| 4 | — | — | — | — | — | |

---

## Incidents & fixes

| incident_id | timestamp | description | resolution |
|-------------|-----------|-------------|------------|
| — | — | — | — |

---

## Open questions

- [ ] How does live fill price compare to backtest close price?
- [ ] Does 5-minute check interval miss intraday reversals? (Daily strategy — likely fine.)
- [ ] Should we add market-hours check to avoid placing orders pre/post market?
