"""Single experiment runner — executes one experiment from start to finish."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd

from lab.data.fetcher import DataFetcher
from lab.data.persistence.interfaces import (
    DataStore,
    ExperimentRecord,
    ExperimentStatus,
    TradeRecord,
    SignalRecord,
    EquityPoint,
    MetricRecord,
)
from lab.harness.factory import AgentFactory
from lab.agents.signal import register as register_signal_agents
register_signal_agents


@dataclass
class ExperimentConfig:
    name: str
    strategy: str
    data_source: str
    symbol: str = "SYNTHETIC"
    timeframe: str = "M1"
    period: str | None = None
    start: str | None = None
    end: str | None = None
    train_test_split: str | None = None
    agents: list[str] = field(default_factory=lambda: ["trend_signal"])
    mode: str = "isolated"
    config: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "strategy": self.strategy,
            "data_source": self.data_source,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "period": self.period,
            "start": self.start,
            "end": self.end,
            "train_test_split": self.train_test_split,
            "agents": self.agents,
            "mode": self.mode,
            "config": self.config,
        }


class ExperimentRunner:
    """Executes a single experiment.

    Steps:
        1. Fetch data from source
        2. Split into train/test if configured
        3. Initialise agents via factory
        4. Run the backtest loop
        5. Compute metrics
        6. Save results to store
    """

    def __init__(self, store: DataStore, fetcher: DataFetcher | None = None):
        self.store = store
        self.fetcher = fetcher or DataFetcher()
        self.factory = AgentFactory()

    def run(self, config: ExperimentConfig) -> ExperimentRecord:
        """Run a single experiment."""
        run_id = self.store.create_experiment(
            name=config.name,
            strategy=config.strategy,
            config=config.to_dict(),
            data_source=config.data_source,
        )

        try:
            df = self.fetcher.get_ohlcv(
                symbol=config.symbol,
                source=config.data_source,
                timeframe=config.timeframe,
                start=config.start,
                end=config.end,
                period=config.period,
            )

            if config.train_test_split:
                df = self._split_data(df, config.train_test_split)

            result = self._run_backtest(config, df, run_id)
            metrics = self._compute_metrics(result, config)

            for metric_name, metric_value in metrics.items():
                self.store.save_metric(MetricRecord(
                    metric_id=None,
                    run_id=run_id,
                    metric_name=metric_name,
                    metric_value=metric_value,
                ))

            self.store.update_experiment_status(run_id, ExperimentStatus.COMPLETED)

        except Exception as e:
            self.store.update_experiment_status(run_id, ExperimentStatus.FAILED, error=str(e))
            raise

        return self.store.get_experiment(run_id)

    def _run_backtest(
        self, config: ExperimentConfig, df: pd.DataFrame, run_id: str
    ) -> dict:
        init_cash = config.config.get("init_cash", 10_000.0)
        fee_rate = config.config.get("fee_rate", 0.001)
        risk_pct = config.config.get("risk_pct", 0.01)
        stop_loss_pct = config.config.get("stop_loss_pct", 0.02)
        min_trade_value = config.config.get("min_trade_value", 50.0)
        min_equity_pct = config.config.get("min_equity_pct", 0.02)
        min_equity = init_cash * min_equity_pct
        signal_agent_name = config.agents[0] if config.agents else "trend_signal"

        signal_agent = self.factory.build(signal_agent_name, symbol=config.symbol)
        min_bars_required = 50

        signals = signal_agent.generate_all(df)

        position = 0.0
        cash = init_cash
        shares = 0.0
        entry_price = 0.0
        entry_cost = 0.0
        stop_loss = 0.0
        equity_curve = []
        trade_count = 0
        winning_trades = 0
        signals_generated = 0
        max_equity = init_cash

        for i in range(len(df)):
            close = float(df["Close"].iloc[i])
            equity = cash + shares * close
            max_equity = max(max_equity, equity)
            drawdown = (max_equity - equity) / max_equity if max_equity > 0 else 0.0

            self.store.append_equity(EquityPoint(
                run_id=run_id,
                timestamp=df.index[i],
                equity=equity,
                drawdown=drawdown,
            ))
            equity_curve.append(equity)

            if i < min_bars_required:
                continue

            if equity < min_equity:
                continue

            signal_dir = signals.iloc[i].value
            if signal_dir != "flat":
                signals_generated += 1

            price = close

            if position == 0 and signal_dir in ("long", "short"):
                risk_agent_active = "risk" in config.agents
                if risk_agent_active:
                    max_loss = init_cash * risk_pct
                    risk_per_unit = abs(price * stop_loss_pct)
                    if risk_per_unit > 0:
                        size = min(max_loss / risk_per_unit, (cash * 0.1) / price)
                    else:
                        size = 0.0
                else:
                    size = (cash * 0.95) / price

                trade_value = size * price
                if size > 0 and trade_value >= min_trade_value:
                    cost = price * size * (1 + fee_rate)
                    if signal_dir == "long" and cost <= cash:
                        position = 1
                        shares = size
                        entry_price = price
                        entry_cost = cost
                        stop_loss = price * (1 - stop_loss_pct)
                        cash -= cost
                        trade_count += 1
                        self.store.log_trade(TradeRecord(
                            trade_id=None,
                            run_id=run_id,
                            asset=config.symbol,
                            direction="buy",
                            action="enter",
                            size=shares,
                            entry_price=entry_price,
                            stop_loss=stop_loss,
                            status="open",
                        ))
                    elif signal_dir == "short":
                        position = -1
                        shares = size
                        entry_price = price
                        entry_cost = price * size * (1 - fee_rate)
                        stop_loss = price * (1 + stop_loss_pct)
                        cash += entry_cost
                        trade_count += 1
                        self.store.log_trade(TradeRecord(
                            trade_id=None,
                            run_id=run_id,
                            asset=config.symbol,
                            direction="sell",
                            action="enter",
                            size=shares,
                            entry_price=entry_price,
                            stop_loss=stop_loss,
                            status="open",
                        ))

            elif position != 0:
                exit_triggered = False
                exit_price = price

                if position == 1:
                    if signal_dir == "short" or price <= stop_loss:
                        exit_triggered = True
                        exit_price = min(price, stop_loss)
                elif position == -1:
                    if signal_dir == "long" or price >= stop_loss:
                        exit_triggered = True
                        exit_price = max(price, stop_loss)

                if exit_triggered:
                    if position == 1:
                        pnl = (exit_price - entry_price) * shares
                        pnl -= exit_price * shares * fee_rate
                    else:
                        pnl = (entry_price - exit_price) * shares
                        pnl -= exit_price * shares * fee_rate
                        pnl -= entry_price * shares * fee_rate

                    cash += pnl
                    winning_trades += 1 if pnl > 0 else 0

                    self.store.log_trade(TradeRecord(
                        trade_id=None,
                        run_id=run_id,
                        asset=config.symbol,
                        direction="sell" if position == 1 else "buy",
                        action="exit",
                        size=shares,
                        entry_price=entry_price,
                        exit_price=exit_price,
                        pnl=pnl,
                        status="closed",
                    ))

                    shares = 0.0
                    position = 0

        self.store.flush_equity(run_id)

        return {
            "init_cash": init_cash,
            "final_equity": cash + shares * float(df["Close"].iloc[-1]),
            "trade_count": trade_count,
            "winning_trades": winning_trades,
            "equity_curve": equity_curve,
            "signals_generated": signals_generated,
        }

    def _compute_metrics(self, result: dict, config: ExperimentConfig) -> dict:
        import numpy as np

        init_cash = result["init_cash"]
        final_equity = result["final_equity"]
        equity_curve = result["equity_curve"]

        total_return = (final_equity - init_cash) / init_cash
        trade_count = result["trade_count"]
        winning = result["winning_trades"]
        win_rate = winning / trade_count if trade_count > 0 else 0.0

        if len(equity_curve) > 1:
            returns = pd.Series(equity_curve).pct_change().dropna()
            if returns.std() > 0:
                sharpe = returns.mean() / returns.std() * math.sqrt(8760)
            else:
                sharpe = 0.0
        else:
            sharpe = 0.0

        return {
            "total_return": round(total_return, 4),
            "sharpe_ratio": round(sharpe, 4),
            "win_rate": round(win_rate, 4),
            "total_trades": trade_count,
            "winning_trades": winning,
            "signals_generated": result.get("signals_generated", 0),
        }

    def _split_data(self, df: pd.DataFrame, split: str) -> pd.DataFrame:
        if "/" not in split:
            return df

        train_pct = int(split.split("/")[0])
        split_idx = int(len(df) * train_pct / 100)
        return df.iloc[split_idx:]
