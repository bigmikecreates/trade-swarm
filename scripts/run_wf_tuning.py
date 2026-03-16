"""Targeted walk-forward tuning on assets that showed real OOS edge."""

from backtest.walk_forward import walk_forward

CONFIGS = [
    # QQQ 10/30 had 29 trades (1 short!). Try tighter for more signals.
    ("QQQ", 9, 28, False, 12),
    ("QQQ", 8, 25, False, 12),
    ("QQQ", 10, 25, False, 12),
    ("QQQ", 8, 21, False, 12),
]


def main():
    print(f"{'Asset':<8} {'EMA':<8} {'Filter':<8} {'Years':>5} {'Sharpe':>8} {'MaxDD%':>8} "
          f"{'Trades':>8} {'Return%':>10} {'WinRate':>8} {'Gate':>6}")
    print("-" * 85)

    for symbol, ema_f, ema_s, use_regime, years in CONFIGS:
        filt = "HMM" if use_regime else "None"
        r = walk_forward(symbol, ema_f, ema_s, use_regime, total_years=years)
        if "error" in r:
            print(f"{symbol:<8} {ema_f}/{ema_s:<5} {filt:<8} {years:>5} ERROR: {r['error']}")
            continue
        g = "PASS" if r["gate"]["gate_pass"] else "FAIL"
        print(f"{symbol:<8} {r['ema']:<8} {r['filter']:<8} {years:>5} "
              f"{r['sharpe']:>8.4f} {r['max_dd_pct']:>7.2f}% "
              f"{r['total_trades']:>8} {r['total_return_pct']:>9.1f}% "
              f"{r['win_rate']:>7.1f}% {g:>6}")


if __name__ == "__main__":
    main()
