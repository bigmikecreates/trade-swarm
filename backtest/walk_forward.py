"""Walk-forward validation for the EMA crossover + HMM regime strategy.

Splits a long history into rolling train/test windows. On each fold the HMM
is fitted on the training window only, then frozen and used to generate
regime labels on the unseen test window. The backtest runs on the test window
with those out-of-sample regime predictions.

This prevents look-ahead bias that exists in the in-sample results where the
HMM is fitted and evaluated on the same data.
"""

import numpy as np
import pandas as pd

from config import INIT_CASH, FEE_RATE, GATE_MIN_SHARPE, GATE_MAX_DRAWDOWN_PCT, GATE_MIN_TRADES
from data.fetcher import fetch_ohlcv
from data.indicators import ema
from data.regime import Regime, fit_regime_model, predict_regimes
from backtest.run import backtest_pandas, check_gate


def _build_signals_with_frozen_model(
    df: pd.DataFrame,
    ema_fast: int,
    ema_slow: int,
    model,
    label_map,
    use_regime: bool,
) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Build entry/exit signals using a pre-fitted HMM (no re-fitting)."""
    df = df.copy()
    close = df["Close"]
    df[f"EMA_{ema_fast}"] = ema(close, ema_fast)
    df[f"EMA_{ema_slow}"] = ema(close, ema_slow)

    if use_regime and model is not None:
        regimes = predict_regimes(df, model, label_map)
        df = df.loc[regimes.index]
        df["regime"] = regimes

    df.dropna(inplace=True)

    ema_long = df[f"EMA_{ema_fast}"] > df[f"EMA_{ema_slow}"]
    ema_short = df[f"EMA_{ema_fast}"] < df[f"EMA_{ema_slow}"]

    if use_regime and "regime" in df.columns:
        trending = df["regime"] == Regime.TRENDING
        entries = ema_long & trending
        exits = ema_short
    else:
        entries = ema_long
        exits = ema_short

    return df, entries, exits


def walk_forward(
    symbol: str,
    ema_fast: int,
    ema_slow: int,
    use_regime: bool,
    total_years: int = 10,
    train_years: int = 5,
    test_years: int = 1,
    init_cash: float = INIT_CASH,
    fee_rate: float = FEE_RATE,
) -> dict:
    """Run walk-forward validation with rolling train/test windows.

    Returns aggregate out-of-sample metrics across all test folds.
    """
    period = f"{total_years}y"
    full_df = fetch_ohlcv(symbol, period=period, interval="1d")

    start_date = full_df.index.min()
    end_date = full_df.index.max()

    folds = []
    fold_metrics = []
    all_oos_equity = []
    all_oos_trades = []
    running_cash = init_cash

    train_start = start_date
    while True:
        train_end = train_start + pd.DateOffset(years=train_years)
        test_start = train_end
        test_end = test_start + pd.DateOffset(years=test_years)

        if test_end > end_date + pd.DateOffset(days=30):
            break

        train_df = full_df.loc[train_start:train_end]
        test_df = full_df.loc[test_start:test_end]

        if len(train_df) < 100 or len(test_df) < 20:
            train_start += pd.DateOffset(years=test_years)
            continue

        model, label_map = None, None
        if use_regime:
            model, label_map = fit_regime_model(train_df)

        test_with_signals, entries, exits = _build_signals_with_frozen_model(
            test_df, ema_fast, ema_slow, model, label_map, use_regime,
        )

        if len(test_with_signals) < 5:
            train_start += pd.DateOffset(years=test_years)
            continue

        result = backtest_pandas(
            test_with_signals, entries, exits,
            init_cash=running_cash, fees=fee_rate,
        )

        m = result["metrics"]
        eq = result["equity_curve"]
        running_cash = eq.iloc[-1]

        n_trades = m["Total Trades"]
        winning = 0
        if "trade_pairs" in result:
            winning = sum(1 for ep, xp in result["trade_pairs"] if xp > ep)

        fold_info = {
            "fold": len(folds) + 1,
            "train": f"{train_start.date()} to {train_end.date()}",
            "test": f"{test_start.date()} to {test_end.date()}",
            "test_bars": len(test_with_signals),
            "trades": n_trades,
            "return_pct": m["Total Return [%]"],
            "sharpe": m["Sharpe Ratio"],
            "max_dd_pct": m["Max Drawdown [%]"],
        }
        folds.append(fold_info)
        fold_metrics.append(m)

        all_oos_equity.append(eq)
        all_oos_trades.append(n_trades)

        train_start += pd.DateOffset(years=test_years)

    if not folds:
        return {"error": f"No valid folds for {symbol}", "folds": []}

    combined_equity = pd.concat(all_oos_equity)
    oos_returns = combined_equity.pct_change().dropna()

    total_trades = sum(all_oos_trades)
    total_return = (combined_equity.iloc[-1] - init_cash) / init_cash

    cummax = combined_equity.cummax()
    drawdown = (combined_equity - cummax) / cummax
    max_drawdown = abs(drawdown.min())

    if len(oos_returns) > 1 and oos_returns.std() > 0:
        sharpe = oos_returns.mean() / oos_returns.std() * np.sqrt(252)
    else:
        sharpe = 0.0

    total_winning = sum(
        m.get("Win Rate [%]", 0) * m.get("Total Trades", 0) / 100
        for m in fold_metrics
    )
    win_rate = (total_winning / total_trades * 100) if total_trades > 0 else 0.0

    gate = check_gate(sharpe, max_drawdown * 100, total_trades)

    return {
        "symbol": symbol,
        "ema": f"{ema_fast}/{ema_slow}",
        "use_regime": use_regime,
        "filter": "HMM" if use_regime else "None",
        "n_folds": len(folds),
        "total_trades": total_trades,
        "total_return_pct": round(total_return * 100, 2),
        "sharpe": round(sharpe, 4),
        "max_dd_pct": round(max_drawdown * 100, 2),
        "win_rate": round(win_rate, 1),
        "gate": gate,
        "folds": folds,
    }


WALK_FORWARD_CONFIGS = [
    ("SPY",  8, 21, True),
    ("DIA",  5, 20, False),
    ("QQQ", 12, 35, False),
    ("MSFT", 8, 21, True),
    ("AAPL", 5, 20, True),
    ("GLD", 10, 30, False),
]


def main():
    print("=" * 80)
    print("  Walk-Forward Validation (exp-008)")
    print("  Train: 5y | Test: 1y | Step: 1y | Data: 10y daily")
    print("=" * 80)

    results = []
    for symbol, ema_f, ema_s, use_regime in WALK_FORWARD_CONFIGS:
        filt = "HMM" if use_regime else "None"
        print(f"\n--- {symbol} EMA {ema_f}/{ema_s} filter={filt} ---")

        r = walk_forward(symbol, ema_f, ema_s, use_regime)
        results.append(r)

        if "error" in r:
            print(f"  ERROR: {r['error']}")
            continue

        print(f"  Folds: {r['n_folds']}")
        for f in r["folds"]:
            status = "+" if f["return_pct"] > 0 else "-"
            print(f"    [{status}] {f['test']}  trades={f['trades']}  "
                  f"ret={f['return_pct']:+.1f}%  sharpe={f['sharpe']:.2f}  dd={f['max_dd_pct']:.1f}%")

        g = "PASS" if r["gate"]["gate_pass"] else "FAIL"
        print(f"  Aggregate: Sharpe={r['sharpe']:.4f}  MaxDD={r['max_dd_pct']:.2f}%  "
              f"Trades={r['total_trades']}  Return={r['total_return_pct']:.1f}%  "
              f"WinRate={r['win_rate']:.1f}%  Gate={g}")

    print(f"\n{'=' * 80}")
    print(f"{'Asset':<8} {'EMA':<8} {'Filter':<8} {'Sharpe':>8} {'MaxDD%':>8} "
          f"{'Trades':>8} {'Return%':>10} {'WinRate':>8} {'Gate':>6}")
    print("-" * 80)
    for r in results:
        if "error" in r:
            print(f"{r['symbol']:<8} ERROR")
            continue
        g = "PASS" if r["gate"]["gate_pass"] else "FAIL"
        print(f"{r['symbol']:<8} {r['ema']:<8} {r['filter']:<8} "
              f"{r['sharpe']:>8.4f} {r['max_dd_pct']:>7.2f}% "
              f"{r['total_trades']:>8} {r['total_return_pct']:>9.1f}% "
              f"{r['win_rate']:>7.1f}% {g:>6}")
    print("=" * 80)


if __name__ == "__main__":
    main()
