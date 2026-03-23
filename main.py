"""Paper trading loop — v0.2.0."""

import math
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
from logging.activity_log import init_activity_log, log_activity
from logging.trade_log import init_db, log_trade
from risk.gate import BasicRiskGate, GateResult, RedisUnavailableError
from risk.position_sizer import calculate_position_size


def _print_trading_halted(reason: str) -> None:
    bar = "=" * 60
    print(f"\n{bar}\n⛔ TRADING HALTED: {reason}\nExiting paper loop. Fix the issue and restart.\n{bar}\n")


def run():
    init_db()
    init_activity_log()
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
    print("(Press Ctrl+C to stop. Gate BLOCK = skip order, loop continues. HALT = exit.)\n")
    log_activity(
        "loop_start",
        symbol=PAPER_SYMBOL,
        equity=equity,
        check_interval_sec=PAPER_CHECK_INTERVAL,
    )

    # Match Redis duplicate-order state to Alpaca (safe after restart with a live position)
    _positions = broker.get_positions()
    _sync = next((p for p in _positions if p["asset"] == PAPER_SYMBOL), None)
    if _sync is not None:
        gate.set_position_direction(PAPER_SYMBOL, "buy" if _sync["qty"] > 0 else "sell")
        side = "long" if _sync["qty"] > 0 else "short"
        print(f"Gate ↔ broker sync: open {side} {PAPER_SYMBOL} (position restored if restarting)\n")
    else:
        gate.set_position_direction(PAPER_SYMBOL, None)
        print("Gate ↔ broker sync: flat (no open position in broker)\n")

    try:
        while True:
            try:
                clock = broker.get_clock()
                is_open = clock["is_open"]

                if not is_open:
                    print(f"{datetime.utcnow()} | Market closed (next open: {clock.get('next_open', '?')})")
                    log_activity("market_closed", next_open=clock.get("next_open"))
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
                    log_activity("daily_reset", equity=equity, trading_day=today)

                df = fetch_ohlcv(PAPER_SYMBOL, period=PAPER_PERIOD, interval=PAPER_INTERVAL)
                df["ATR_14"] = atr(df["High"], df["Low"], df["Close"], 14)

                signal = agent.generate(df)
                equity = broker.get_account_equity()

                positions = broker.get_positions()
                pos = next((p for p in positions if p["asset"] == PAPER_SYMBOL), None)
                in_trade = pos is not None
                position_side = (
                    "long" if pos["qty"] > 0 else "short" if in_trade else None
                )

                print(
                    f"{datetime.utcnow()} | {signal.direction.value} | "
                    f"strength={signal.strength:.2f} confidence={signal.confidence:.2f}"
                )
                log_activity(
                    "signal",
                    symbol=PAPER_SYMBOL,
                    direction=signal.direction.value,
                    strength=signal.strength,
                    confidence=signal.confidence,
                    equity=equity,
                    in_trade=in_trade,
                    position_side=position_side,
                )

                if signal.strength * signal.confidence < 0.4:
                    print("Signal too weak — skipping")
                    log_activity(
                        "signal_weak_skip",
                        symbol=PAPER_SYMBOL,
                        product=signal.strength * signal.confidence,
                        threshold=0.4,
                    )
                    time.sleep(PAPER_CHECK_INTERVAL)
                    continue

                is_long = in_trade and pos["qty"] > 0
                is_short = in_trade and pos["qty"] < 0

                # --- ENTRY: flat → open long or short ---
                if not in_trade and signal.direction == Direction.LONG:
                    price = float(df["Close"].iloc[-1])
                    atr_val = float(df["ATR_14"].iloc[-1]) if "ATR_14" in df.columns else price * 0.01
                    stop_loss = price - (2 * atr_val)
                    size = calculate_position_size(equity, price, stop_loss, risk_pct=0.01)
                    size = min(size, round((equity * 0.10) / price, 4))  # Cap at gate's 10% max

                    if size <= 0:
                        print("Position size zero — skipping")
                        log_activity("entry_skip_zero_size", side="long", symbol=PAPER_SYMBOL)
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

                    if decision.result == GateResult.HALT:
                        log_activity("gate_halt", reason=decision.reason, rule=decision.rule)
                        _print_trading_halted(decision.reason or "unknown")
                        return
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
                        log_activity(
                            "entry_filled",
                            side="long",
                            symbol=PAPER_SYMBOL,
                            size=size,
                            order_id=result.order_id,
                            entry_price=entry_price,
                        )
                        print(f"✅ Opened LONG {size} {PAPER_SYMBOL} @ ${entry_price:.2f}")
                    else:
                        print(
                            f"🚫 Gate blocked: {decision.reason} — loop continues, "
                            f"next check in {PAPER_CHECK_INTERVAL}s"
                        )
                        log_activity(
                            "gate_blocked",
                            side="long",
                            symbol=PAPER_SYMBOL,
                            reason=decision.reason,
                            rule=decision.rule,
                            size=size,
                            price=price,
                        )

                elif not in_trade and signal.direction == Direction.SHORT:
                    price = float(df["Close"].iloc[-1])
                    atr_val = float(df["ATR_14"].iloc[-1]) if "ATR_14" in df.columns else price * 0.01
                    stop_loss = price + (2 * atr_val)
                    size = calculate_position_size(equity, price, stop_loss, risk_pct=0.01)
                    size = min(size, round((equity * 0.10) / price, 4))  # Cap at gate's 10% max
                    # Alpaca: fractional orders cannot be sold short — whole shares only
                    size_before_floor = size
                    size = float(math.floor(size))
                    if size < 1:
                        print("Short entry requires at least 1 whole share — skipping")
                        log_activity(
                            "short_skip_whole_shares",
                            symbol=PAPER_SYMBOL,
                            size_before_floor=size_before_floor,
                            reason="fractional_short_not_allowed",
                        )
                        time.sleep(PAPER_CHECK_INTERVAL)
                        continue

                    if size <= 0:
                        print("Position size zero — skipping")
                        log_activity("entry_skip_zero_size", side="short", symbol=PAPER_SYMBOL)
                        time.sleep(PAPER_CHECK_INTERVAL)
                        continue

                    order = {
                        "asset": PAPER_SYMBOL,
                        "direction": "sell",
                        "action": "enter",
                        "size": size,
                        "price": price,
                    }
                    decision = gate.check(order, equity)

                    if decision.result == GateResult.HALT:
                        log_activity("gate_halt", reason=decision.reason, rule=decision.rule)
                        _print_trading_halted(decision.reason or "unknown")
                        return
                    if decision.result == GateResult.PASS:
                        result = broker.place_market_order(PAPER_SYMBOL, size, "sell")
                        fill = broker.wait_for_fill(result.order_id)
                        entry_price = (fill["avg_price"] if fill and fill.get("avg_price") else None) or price
                        gate.set_position_direction(PAPER_SYMBOL, "sell")
                        log_trade({
                            **order,
                            "entry_price": entry_price,
                            "stop_loss": stop_loss,
                            "order_id": result.order_id,
                            "status": "open",
                            "indicators": signal.indicators,
                        })
                        log_activity(
                            "entry_filled",
                            side="short",
                            symbol=PAPER_SYMBOL,
                            size=size,
                            order_id=result.order_id,
                            entry_price=entry_price,
                        )
                        print(f"✅ Opened SHORT {size} {PAPER_SYMBOL} @ ${entry_price:.2f}")
                    else:
                        print(
                            f"🚫 Gate blocked: {decision.reason} — loop continues, "
                            f"next check in {PAPER_CHECK_INTERVAL}s"
                        )
                        log_activity(
                            "gate_blocked",
                            side="short",
                            symbol=PAPER_SYMBOL,
                            reason=decision.reason,
                            rule=decision.rule,
                            size=size,
                            price=price,
                        )

                # --- EXIT: close long when FLAT or SHORT; close short when FLAT or LONG ---
                elif is_long and signal.direction in (Direction.FLAT, Direction.SHORT):
                    qty = pos["qty"]
                    entry_price = pos["avg_price"]
                    result = broker.place_market_order(PAPER_SYMBOL, qty, "sell")
                    fill = broker.wait_for_fill(result.order_id)
                    exit_price = (fill["avg_price"] if fill and fill.get("avg_price") else None) or float(
                        df["Close"].iloc[-1]
                    )
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
                    log_activity(
                        "exit_filled",
                        closed_side="long",
                        symbol=PAPER_SYMBOL,
                        qty=qty,
                        order_id=result.order_id,
                        exit_price=exit_price,
                        pnl=pnl,
                    )
                    print(f"✅ Closed LONG {PAPER_SYMBOL} @ ${exit_price:.2f} | P&L: ${pnl:,.2f}")

                elif is_short and signal.direction in (Direction.FLAT, Direction.LONG):
                    qty = abs(pos["qty"])
                    entry_price = pos["avg_price"]
                    result = broker.place_market_order(PAPER_SYMBOL, qty, "buy")
                    fill = broker.wait_for_fill(result.order_id)
                    exit_price = (fill["avg_price"] if fill and fill.get("avg_price") else None) or float(
                        df["Close"].iloc[-1]
                    )
                    pnl = (entry_price - exit_price) * qty
                    gate.set_position_direction(PAPER_SYMBOL, None)
                    log_trade({
                        "asset": PAPER_SYMBOL,
                        "direction": "buy",
                        "action": "exit",
                        "size": qty,
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "pnl": pnl,
                        "order_id": result.order_id,
                        "status": "closed",
                        "indicators": signal.indicators,
                    })
                    log_activity(
                        "exit_filled",
                        closed_side="short",
                        symbol=PAPER_SYMBOL,
                        qty=qty,
                        order_id=result.order_id,
                        exit_price=exit_price,
                        pnl=pnl,
                    )
                    print(f"✅ Closed SHORT {PAPER_SYMBOL} @ ${exit_price:.2f} | P&L: ${pnl:,.2f}")

            except Exception as e:
                print(f"⚠️  Error: {e}")
                log_activity("error", message=str(e), exc_type=type(e).__name__)

            time.sleep(PAPER_CHECK_INTERVAL)

    except KeyboardInterrupt:
        bar = "=" * 60
        print(f"\n{bar}\n🛑 Paper trading loop stopped by user (Ctrl+C).\n{bar}\n")
        log_activity("loop_stop", reason="keyboard_interrupt")


if __name__ == "__main__":
    run()
