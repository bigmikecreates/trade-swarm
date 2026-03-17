"""Paper trading loop — v0.2.0."""

import time
from datetime import datetime

from agents.signal.trend_agent import Direction, TrendSignalAgent
from brokers.alpaca_adapter import AlpacaAdapter
from config import (
    ALPACA_API_KEY,
    ALPACA_SECRET_KEY,
    ALPACA_BASE_URL,
    PAPER_SYMBOL,
    PAPER_EMA_FAST,
    PAPER_EMA_SLOW,
    PAPER_CHECK_INTERVAL,
    PAPER_PERIOD,
    PAPER_INTERVAL,
    REDIS_URL,
)
from data.fetcher import fetch_ohlcv
from data.indicators import atr
from logging.trade_log import init_db, log_trade
from risk.gate import BasicRiskGate, GateResult, RedisUnavailableError
from risk.position_sizer import calculate_position_size


def run():
    init_db()
    broker = AlpacaAdapter(ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL)

    try:
        gate = BasicRiskGate(account_equity=broker.get_account_equity(), redis_url=REDIS_URL)
    except RedisUnavailableError as e:
        print(f"❌ {e}")
        return

    agent = TrendSignalAgent(
        PAPER_SYMBOL,
        use_regime=False,
        ema_fast=PAPER_EMA_FAST,
        ema_slow=PAPER_EMA_SLOW,
    )

    equity = broker.get_account_equity()
    last_reset_date = None

    print(f"Starting paper trading loop. Symbol: {PAPER_SYMBOL} | Equity: ${equity:,.2f}")

    while True:
        try:
            clock = broker.get_clock()
            is_open = clock["is_open"]

            if not is_open:
                print(f"{datetime.utcnow()} | Market closed (next open: {clock.get('next_open', '?')})")
                time.sleep(PAPER_CHECK_INTERVAL)
                continue

            # Daily equity reset at market open (once per trading day)
            ts = clock.get("timestamp") or datetime.utcnow().isoformat()
            today = ts[:10]  # YYYY-MM-DD
            if last_reset_date != today:
                equity = broker.get_account_equity()
                gate.reset_daily(equity)
                last_reset_date = today
                print(f"{datetime.utcnow()} | Daily reset | Equity: ${equity:,.2f}")

            df = fetch_ohlcv(PAPER_SYMBOL, period=PAPER_PERIOD, interval=PAPER_INTERVAL)
            df["ATR_14"] = atr(df["High"], df["Low"], df["Close"], 14)

            signal = agent.generate(df)
            equity = broker.get_account_equity()

            print(
                f"{datetime.utcnow()} | {signal.direction.value} | "
                f"strength={signal.strength:.2f} confidence={signal.confidence:.2f}"
            )

            if signal.strength * signal.confidence < 0.4:
                print("Signal too weak — skipping")
                time.sleep(PAPER_CHECK_INTERVAL)
                continue

            positions = broker.get_positions()
            pos = next((p for p in positions if p["asset"] == PAPER_SYMBOL), None)
            in_trade = pos is not None

            if not in_trade and signal.direction == Direction.LONG:
                price = float(df["Close"].iloc[-1])
                atr_val = float(df["ATR_14"].iloc[-1]) if "ATR_14" in df.columns else price * 0.01
                stop_loss = price - (2 * atr_val)
                size = calculate_position_size(equity, price, stop_loss, risk_pct=0.01)

                if size <= 0:
                    print("Position size zero — skipping")
                    time.sleep(PAPER_CHECK_INTERVAL)
                    continue

                order = {
                    "asset": PAPER_SYMBOL,
                    "direction": "buy",
                    "action": "enter",
                    "size": size,
                    "price": price,
                }
                decision = gate.check(order, equity)

                if decision.result == GateResult.PASS:
                    result = broker.place_market_order(PAPER_SYMBOL, size, "buy")
                    fill = broker.wait_for_fill(result.order_id)
                    entry_price = (fill["avg_price"] if fill and fill.get("avg_price") else None) or price
                    gate.set_position_direction(PAPER_SYMBOL, "buy")
                    log_trade({
                        **order,
                        "entry_price": entry_price,
                        "stop_loss": stop_loss,
                        "order_id": result.order_id,
                        "status": "open",
                        "indicators": signal.indicators,
                    })
                    print(f"✅ Opened LONG {size} {PAPER_SYMBOL} @ ${entry_price:.2f}")
                else:
                    print(f"🚫 Gate blocked: {decision.reason}")

            elif in_trade and signal.direction in (Direction.FLAT, Direction.SHORT):
                qty = pos["qty"]
                entry_price = pos["avg_price"]
                result = broker.place_market_order(PAPER_SYMBOL, qty, "sell")
                fill = broker.wait_for_fill(result.order_id)
                exit_price = (fill["avg_price"] if fill and fill.get("avg_price") else None) or float(df["Close"].iloc[-1])
                pnl = (exit_price - entry_price) * qty
                gate.set_position_direction(PAPER_SYMBOL, None)
                log_trade({
                    "asset": PAPER_SYMBOL,
                    "direction": "sell",
                    "action": "exit",
                    "size": qty,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "pnl": pnl,
                    "order_id": result.order_id,
                    "status": "closed",
                    "indicators": signal.indicators,
                })
                print(f"✅ Closed position in {PAPER_SYMBOL} @ ${exit_price:.2f} | P&L: ${pnl:,.2f}")

        except Exception as e:
            print(f"⚠️  Error: {e}")

        time.sleep(PAPER_CHECK_INTERVAL)


if __name__ == "__main__":
    run()
