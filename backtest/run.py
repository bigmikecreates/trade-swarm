"""Run Trade-Swarm backtest for EMA crossover strategy on a single asset."""

import pandas as pd
import numpy as np

from config import (
    DEFAULT_SYMBOL, DEFAULT_PERIOD, DEFAULT_INTERVAL, INIT_CASH, FEE_RATE,
    EMA_FAST, EMA_SLOW, ADX_PERIOD, ADX_THRESHOLD,
    GATE_MIN_SHARPE, GATE_MAX_DRAWDOWN_PCT, GATE_MIN_TRADES,
)
from data.fetcher import fetch_ohlcv
from data.indicators import ema, adx
from data.regime import Regime, detect_regimes

try:
    import vectorbt as vbt
    USE_VECTORBT = True
except ImportError:
    USE_VECTORBT = False


def build_signals(df: pd.DataFrame, ema_fast: int = EMA_FAST, ema_slow: int = EMA_SLOW,
                  adx_period: int = ADX_PERIOD, adx_threshold: int = ADX_THRESHOLD,
                  use_regime: bool = False) -> tuple:
    """Compute EMA crossover entries/exits with optional regime filter.

    Filters (applied in priority order):
      - use_regime=True: HMM regime detector — only enter in 'trending' regime
      - adx_threshold>0: ADX indicator — only enter when ADX >= threshold

    Returns (df_with_indicators, entries, exits).
    """
    df = df.copy()
    close = df["Close"]
    df[f"EMA_{ema_fast}"] = ema(close, ema_fast)
    df[f"EMA_{ema_slow}"] = ema(close, ema_slow)

    if adx_threshold > 0 and not use_regime:
        df[f"ADX_{adx_period}"] = adx(df["High"], df["Low"], close, adx_period)

    if use_regime:
        regimes = detect_regimes(df)
        df = df.loc[regimes.index]
        df["regime"] = regimes

    df.dropna(inplace=True)

    ema_long = df[f"EMA_{ema_fast}"] > df[f"EMA_{ema_slow}"]
    ema_short = df[f"EMA_{ema_fast}"] < df[f"EMA_{ema_slow}"]

    if use_regime:
        trending = df["regime"] == Regime.TRENDING
        entries = ema_long & trending
        exits = ema_short
    elif adx_threshold > 0:
        trending = df[f"ADX_{adx_period}"] >= adx_threshold
        entries = ema_long & trending
        exits = ema_short
    else:
        entries = ema_long
        exits = ema_short

    return df, entries, exits


def backtest_pandas(df: pd.DataFrame, entries: pd.Series, exits: pd.Series,
                    init_cash: float = INIT_CASH, fees: float = FEE_RATE) -> dict:
    """Pure pandas backtest. Returns metrics + equity_curve Series."""
    position = 0
    cash = init_cash
    shares = 0.0
    equity_curve = []
    trade_pairs = []

    for i in range(len(df)):
        price = df.iloc[i]["Close"]
        prev_entry = entries.iloc[i - 1] if i > 0 else False
        prev_exit = exits.iloc[i - 1] if i > 0 else False

        if position == 0 and entries.iloc[i] and not prev_entry:
            position = 1
            shares = (cash * (1 - fees)) / price
            cash = 0
            entry_price = price

        elif position == 1 and exits.iloc[i] and not prev_exit:
            cash = shares * price * (1 - fees)
            trade_pairs.append((entry_price, price))
            shares = 0
            position = 0

        equity = cash + shares * price
        equity_curve.append(equity)

    equity_series = pd.Series(equity_curve, index=df.index)
    returns = equity_series.pct_change().dropna()

    total_return = (equity_series.iloc[-1] - init_cash) / init_cash
    n_trades = len(trade_pairs)
    winning = sum(1 for ep, xp in trade_pairs if xp > ep)
    win_rate = winning / n_trades if n_trades > 0 else 0

    cummax = equity_series.cummax()
    drawdown = (equity_series - cummax) / cummax
    max_drawdown = drawdown.min()

    if len(returns) > 1 and returns.std() > 0:
        sharpe = returns.mean() / returns.std() * np.sqrt(8760)
    else:
        sharpe = 0.0

    return {
        "metrics": {
            "Total Return [%]": round(total_return * 100, 2),
            "Sharpe Ratio": round(sharpe, 4),
            "Max Drawdown [%]": round(abs(max_drawdown) * 100, 2),
            "Win Rate [%]": round(win_rate * 100, 2),
            "Total Trades": n_trades,
        },
        "equity_curve": equity_series,
    }


def check_gate(sharpe: float, max_dd_pct: float, n_trades: int) -> dict:
    """Evaluate results against gate thresholds."""
    return {
        "sharpe_pass": sharpe >= GATE_MIN_SHARPE,
        "drawdown_pass": max_dd_pct <= GATE_MAX_DRAWDOWN_PCT,
        "trades_pass": n_trades >= GATE_MIN_TRADES,
        "gate_pass": (
            sharpe >= GATE_MIN_SHARPE
            and max_dd_pct <= GATE_MAX_DRAWDOWN_PCT
            and n_trades >= GATE_MIN_TRADES
        ),
        "thresholds": {
            "min_sharpe": GATE_MIN_SHARPE,
            "max_drawdown_pct": GATE_MAX_DRAWDOWN_PCT,
            "min_trades": GATE_MIN_TRADES,
        },
    }


def run_backtest(symbol: str = DEFAULT_SYMBOL, period: str = DEFAULT_PERIOD,
                 interval: str = DEFAULT_INTERVAL, ema_fast: int = EMA_FAST,
                 ema_slow: int = EMA_SLOW, adx_threshold: int = ADX_THRESHOLD,
                 use_regime: bool = False,
                 init_cash: float = INIT_CASH, fee_rate: float = FEE_RATE) -> dict:
    """Run a full backtest and return all data needed by the UI.

    Returns dict with keys: config, metrics, gate, equity_curve, price_data.
    All values are JSON-serialisable (lists/dicts of primitives).
    """
    config_used = {
        "symbol": symbol, "period": period, "interval": interval,
        "ema_fast": ema_fast, "ema_slow": ema_slow,
        "adx_threshold": adx_threshold, "use_regime": use_regime,
        "init_cash": init_cash, "fee_rate": fee_rate,
    }

    raw_df = fetch_ohlcv(symbol, period=period, interval=interval)
    df, entries, exits = build_signals(
        raw_df, ema_fast, ema_slow, ADX_PERIOD, adx_threshold, use_regime=use_regime,
    )

    ema_fast_col = f"EMA_{ema_fast}"
    ema_slow_col = f"EMA_{ema_slow}"

    if USE_VECTORBT:
        pf = vbt.Portfolio.from_signals(
            df["Close"], entries=entries, exits=exits,
            freq=interval, init_cash=init_cash, fees=fee_rate,
        )
        stats = pf.stats()
        sharpe = float(stats.get("Sharpe Ratio", 0.0))
        max_dd = float(stats.get("Max Drawdown [%]", 0.0))
        n_trades = int(stats.get("Total Trades", 0))
        total_ret = float(stats.get("Total Return [%]", 0.0))
        win_rate = float(stats.get("Win Rate [%]", 0.0))

        equity = pf.value()
        equity_timestamps = [str(t) for t in equity.index]
        equity_values = [round(float(v), 2) for v in equity.values]

        metrics = {
            "Total Return [%]": round(total_ret, 2),
            "Sharpe Ratio": round(sharpe, 4),
            "Max Drawdown [%]": round(max_dd, 2),
            "Win Rate [%]": round(win_rate, 2),
            "Total Trades": n_trades,
        }
    else:
        result = backtest_pandas(df, entries, exits, init_cash, fee_rate)
        metrics = result["metrics"]
        sharpe = metrics["Sharpe Ratio"]
        max_dd = metrics["Max Drawdown [%]"]
        n_trades = metrics["Total Trades"]

        eq = result["equity_curve"]
        equity_timestamps = [str(t) for t in eq.index]
        equity_values = [round(float(v), 2) for v in eq.values]

    gate = check_gate(sharpe, max_dd, n_trades)

    timestamps = [str(t) for t in df.index]
    price_data = {
        "timestamps": timestamps,
        "close": [round(float(v), 5) for v in df["Close"].values],
        "ema_fast": [round(float(v), 5) for v in df[ema_fast_col].values],
        "ema_slow": [round(float(v), 5) for v in df[ema_slow_col].values],
        "entries": [bool(v) for v in entries.values],
        "exits": [bool(v) for v in exits.values],
    }

    if use_regime and "regime" in df.columns:
        price_data["regime"] = [r.value for r in df["regime"].values]

    return {
        "config": config_used,
        "metrics": metrics,
        "gate": gate,
        "equity_curve": {"timestamps": equity_timestamps, "values": equity_values},
        "price_data": price_data,
    }


def _print_config():
    print(f"\n{'=' * 55}")
    print(f"  Strategy Config")
    print(f"{'=' * 55}")
    print(f"  Symbol:       {DEFAULT_SYMBOL}")
    print(f"  Period:       {DEFAULT_PERIOD}   Interval: {DEFAULT_INTERVAL}")
    print(f"  EMA:          {EMA_FAST}/{EMA_SLOW}")
    print(f"  ADX filter:   {'ADX > ' + str(ADX_THRESHOLD) if ADX_THRESHOLD > 0 else 'disabled'}")
    print(f"  Init cash:    {INIT_CASH:,.0f}   Fees: {FEE_RATE * 100:.1f}%")
    print(f"{'=' * 55}")


def _print_gate(gate: dict):
    p = lambda v: "PASS" if v else "FAIL"
    print(f"\n{'=' * 55}")
    print(f"  Gate Evaluation")
    print(f"{'=' * 55}")
    print(f"  Sharpe >= {GATE_MIN_SHARPE}:          {p(gate['sharpe_pass'])}")
    print(f"  Max DD <= {GATE_MAX_DRAWDOWN_PCT}%:        {p(gate['drawdown_pass'])}")
    print(f"  Trades >= {GATE_MIN_TRADES}:           {p(gate['trades_pass'])}")
    print(f"  ----------------------------------------")
    print(f"  OVERALL:              {'GATE PASSED' if gate['gate_pass'] else 'GATE FAILED'}")
    print(f"{'=' * 55}")


def main():
    _print_config()
    result = run_backtest()
    metrics = result["metrics"]

    print("\nBacktest Results")
    print("-" * 50)
    for k, v in metrics.items():
        if isinstance(v, float):
            print(f"  {k}: {v:.2f}")
        else:
            print(f"  {k}: {v}")
    print("-" * 50)

    _print_gate(result["gate"])


if __name__ == "__main__":
    main()
