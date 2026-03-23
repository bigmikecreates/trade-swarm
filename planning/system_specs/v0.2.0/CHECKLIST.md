# v0.2.0 Checklist

> **Gate to exit:** 4 continuous weeks of paper trading with no critical bugs; all orders logged to SQLite; P&L dashboard accurate; kill switch tested.
>
> **Scope:** Single asset (SPY), TrendSignalAgent only, Alpaca paper, Redis for kill switch.

---

## 1. Alpaca Paper Account

- [x] Signed up at alpaca.markets
- [x] Paper API keys generated
- [x] Keys added to `config.py` (or loaded from env — do not commit secrets)
- [x] `ALPACA_BASE_URL = "https://paper-api.alpaca.markets"` confirmed
- [x] Test connection: `broker.get_account_equity()` returns a value

---

## 2. Broker Adapter (`brokers/alpaca_adapter.py`)

- [x] `AlpacaAdapter` class with `__init__(api_key, secret, base_url)`
- [x] `place_market_order(asset, qty, side)` → `OrderResult`
- [x] `get_order_status(order_id)` → dict with status, filled_qty, avg_price
- [x] `cancel_order(order_id)`
- [x] `get_positions()` → list of {asset, qty, avg_price}
- [x] `get_account_equity()` → float
- [x] `get_clock()` → market hours (is_open, next_open, next_close)
- [x] `wait_for_fill(order_id, timeout=30)` → polls until filled, returns {filled_qty, avg_price}
- [x] **Verify fractional shares** — Alpaca paper supports fractional; confirm qty format for small accounts

---

## 3. Position Sizing (`risk/position_sizer.py`)

- [x] `calculate_position_size(account_equity, entry_price, stop_loss_price, risk_pct=0.01)` implemented
- [x] Max loss = (entry - stop) × units = account × risk_pct
- [x] Returns 0 when risk_per_unit == 0
- [x] Rounds to 4 decimal places
- [ ] **Validate** — Run with sample values; confirm size is reasonable for SPY

---

## 4. Basic Risk Gate (`risk/gate.py`)

- [x] `BasicRiskGate` with Redis backend
- [x] Rule 1: Kill switch — `redis.get("kill_switch") == "1"` → HALT
- [x] Rule 2: Daily loss limit (3%) → HALT
- [x] Rule 3: Max position size (10% of account) → BLOCK
- [x] Rule 4: Duplicate order check (`position_direction:{asset}`) → BLOCK
- [x] `activate_kill_switch()` method
- [x] `reset_daily(current_equity)` for market-open reset
- [x] `set_position_direction(asset, direction)` for duplicate tracking
- [x] **Redis failure handling** — Graceful: init raises RedisUnavailableError; mid-run Redis failure → HALT (kill switch) or block (duplicate)
- [x] **Redis running** — `redis-cli ping` returns PONG
- [ ] **Kill switch tested** — Activate, confirm loop stops placing new orders
- [x] **Daily reset wired** — `reset_daily()` called when market opens (date change from Alpaca clock)

---

## 5. Trade Logger (`logging/trade_log.py`)

- [x] `init_db()` creates `data/trades.db` with trades table
- [x] `log_trade(trade)` inserts row with all fields
- [x] Handles numpy types in indicators (JSON serialization)
- [x] `data/trades.db` in `.gitignore`
- [ ] **Verify** — Run loop, place one trade, confirm row in SQLite
- [x] **P&L on exit** — Exit trades log pnl = (exit_price - entry_price) × qty from fill

---

## 6. Main Trading Loop (`main.py`)

- [x] Fetches OHLCV, computes ATR, runs TrendSignalAgent
- [x] Uses validated EMA params (8/21 for SPY) from config
- [x] Signal strength × confidence threshold (0.4)
- [x] Entry: LONG signal, not in trade, gate passes → place order, log, set position_direction
- [x] Exit: FLAT or SHORT signal, in trade → place sell, log, clear position_direction
- [x] Position lookup by symbol (not `positions[0]`)
- [x] Skips when size <= 0
- [x] **Market hours** — Loop skips trading when `clock.is_open` is False
- [x] **Daily reset** — `gate.reset_daily(equity)` at market open (date change from Alpaca clock)

---

## 7. Streamlit Dashboard (`dashboard/app.py`)

- [x] Connects to `data/trades.db`
- [x] Total P&L, Win Rate, Total Trades metrics
- [x] Trade history table
- [x] Cumulative P&L line chart
- [ ] **Accuracy check** — After 1 week, compare dashboard P&L to Alpaca paper account equity change

---

## 8. Kill Switch Script

- [x] `scripts/activate_kill_switch.py` sets Redis key
- [x] Prints reset instruction
- [ ] **Tested** — Run script, confirm paper loop stops placing orders
- [ ] **Reset tested** — `redis-cli DEL kill_switch` restores trading

---

## 9. Config (`config.py`)

- [x] `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `ALPACA_BASE_URL`
- [x] `PAPER_SYMBOL`, `PAPER_EMA_FAST`, `PAPER_EMA_SLOW`
- [x] `PAPER_CHECK_INTERVAL`, `PAPER_PERIOD`, `PAPER_INTERVAL`
- [x] `REDIS_URL`
- [x] **Secrets** — Env vars via `os.environ.get()`; `.env.example`; python-dotenv loads `.env` if present

---

## 10. Dependencies

- [x] `alpaca-trade-api` in pyproject.toml
- [x] `redis` in pyproject.toml
- [x] `streamlit` in pyproject.toml
- [x] `trade-swarm-paper` CLI entry point
- [x] `brokers`, `risk`, `logging`, `dashboard` in packages.find

---

## 11. Documentation

- [x] README v0.2.0 section with setup steps
- [x] Prerequisites: Alpaca, Docker (Redis via Compose)
- [x] Commands: `trade-swarm-paper`, `streamlit run dashboard/app.py`, kill switch
- [x] VPS deployment guide: `planning/system_specs/v0.2.0/VPS_DEPLOYMENT.md`
- [x] **CHANGELOG** — v0.2.0 section added (Unreleased)

---

## 12. VPS Deployment (for 4-week gate)

> Full guide: `planning/system_specs/v0.2.0/VPS_DEPLOYMENT.md`

### Phase 1 — Provision

- [ ] Chosen provider (DigitalOcean, Linode, Hetzner, Vultr)
- [ ] Created instance: Ubuntu 22.04, US region, 1 GB RAM
- [ ] Noted VPS IP address
- [ ] SSH access confirmed: `ssh root@YOUR_VPS_IP`

### Phase 2 — Server setup

- [ ] `apt update && apt upgrade -y`
- [ ] (Optional) Created non-root user
- [ ] (Optional) Set timezone

### Phase 3 — Dependencies

- [ ] Docker installed: `curl -fsSL https://get.docker.com | sh`
- [ ] Python 3.10+ installed
- [ ] tmux installed: `apt install -y tmux`

### Phase 4 — Deploy app

- [ ] Cloned repo: `git clone ... trade-swarm && cd trade-swarm`
- [ ] Checkout branch: `git checkout release/v0.2.0`
- [ ] Created `.env` from `.env.example`
- [ ] Added Alpaca keys to `.env`
- [ ] Virtual env: `python3 -m venv .venv && source .venv/bin/activate`
- [ ] Installed: `pip install -e .`
- [ ] Verified: `trade-swarm-paper` runs

### Phase 5 — Run

- [ ] Redis: `docker compose up -d`
- [ ] Tmux session: `tmux new -s trading`
- [ ] Started loop: `trade-swarm-paper`
- [ ] Detached: Ctrl+B, D
- [ ] (Alternative) Systemd service configured and started

### Phase 6 — Kill switch (remote)

- [ ] Tested: SSH in, run `python scripts/activate_kill_switch.py`
- [ ] Tested reset: `docker compose exec redis redis-cli DEL kill_switch`

### Phase 7 — Monitoring

- [ ] Confirmed loop running: `tmux ls` or `systemctl status trade-swarm-paper`
- [ ] Checked Alpaca paper account for activity during market hours

---

## 13. Gate Sign-off

- [ ] 4 continuous weeks of paper trading with no critical bugs
- [ ] All orders logged correctly to SQLite
- [ ] P&L dashboard matches Alpaca paper account (within rounding)
- [ ] Kill switch tested and confirmed working
- [ ] Daily checklist completed each morning for 4 weeks (see v0.2.0 spec)
- [ ] **Tag commit as `v0.2.0`** and move to v0.3.0
- [ ] VPS deployment completed (Section 12) for 4-week run

---

## Known Gaps (deferred or optional)

| Item | Status | Notes |
|------|--------|-------|
| Market hours check | Done | Loop skips trading when market closed. |
| Daily equity reset | Done | Reset at market open via Alpaca clock date. |
| Order fill polling | Done | `wait_for_fill()` before logging. |
| P&L on exit | Done | Computed from fill prices. |
| Env vars for secrets | Done | `.env.example`, python-dotenv, os.environ. |
| Stop-loss enforcement | Out of scope | Exit on signal only; stop_loss used for position sizing only. |
