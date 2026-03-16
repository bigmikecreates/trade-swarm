"""Run a batch of experiments and print results."""

import warnings
warnings.filterwarnings("ignore")

from backtest.run import run_backtest

EXPERIMENTS = [
    # QQQ: DD was 20.69% at EMA 15/40. Try HMM + wider EMAs to tighten DD.
    ("exp-014-01", "QQQ", "10y", "1d", 15, 40, True,  "QQQ 10y 1d EMA15/40 HMM"),
    ("exp-014-02", "QQQ", "10y", "1d", 20, 50, True,  "QQQ 10y 1d EMA20/50 HMM"),
    ("exp-014-03", "QQQ", "10y", "1d", 12, 35, False, "QQQ 10y 1d EMA12/35 no filter"),
    ("exp-014-04", "QQQ", "10y", "1d", 10, 30, True,  "QQQ 10y 1d EMA10/30 HMM"),
    # AAPL: DD was 24%. Try HMM + wider EMAs.
    ("exp-014-05", "AAPL", "10y", "1d", 10, 30, True,  "AAPL 10y 1d EMA10/30 HMM"),
    ("exp-014-06", "AAPL", "10y", "1d", 15, 40, True,  "AAPL 10y 1d EMA15/40 HMM"),
    ("exp-014-07", "AAPL", "10y", "1d", 5, 20, True,  "AAPL 10y 1d EMA5/20 HMM"),
    # MSFT: already passes. Try 5/20 for more trades.
    ("exp-014-08", "MSFT", "10y", "1d", 5, 20, True,  "MSFT 10y 1d EMA5/20 HMM"),
    # GLD: try HMM configs that might improve Sharpe
    ("exp-014-09", "GLD", "10y", "1d", 8, 21, True,  "GLD 10y 1d EMA8/21 HMM"),
    ("exp-014-10", "GLD", "10y", "1d", 5, 15, False,  "GLD 10y 1d EMA5/15 no filter"),
    # XLV (Healthcare): Sharpe 0.53 + HMM, DD 11.8%. Try tighter EMAs to boost Sharpe.
    ("exp-014-11", "XLV", "10y", "1d", 3, 13, True,   "XLV 10y 1d EMA3/13 HMM"),
    ("exp-014-12", "XLV", "10y", "1d", 3, 13, False,  "XLV 10y 1d EMA3/13 no filter"),
]


def main():
    print(f"{'ID':<10} {'Description':<32} {'Sharpe':>8} {'MaxDD%':>8} {'Trades':>7} {'Return%':>9} {'WinRate%':>9} {'Gate':>6}")
    print("-" * 100)

    for eid, sym, per, intv, ef, es, regime, desc in EXPERIMENTS:
        try:
            r = run_backtest(
                symbol=sym, period=per, interval=intv,
                ema_fast=ef, ema_slow=es, adx_threshold=0,
                use_regime=regime,
            )
            m = r["metrics"]
            gp = "PASS" if r["gate"]["gate_pass"] else "FAIL"
            print(f"{eid:<10} {desc:<32} {m['Sharpe Ratio']:>8.4f} {m['Max Drawdown [%]']:>7.2f}% {m['Total Trades']:>7} {m['Total Return [%]']:>8.2f}% {m['Win Rate [%]']:>8.2f}% {gp:>6}")
        except Exception as e:
            print(f"{eid:<10} {desc:<32} ERROR: {e}")


if __name__ == "__main__":
    main()
