"""Batch experiment runner — parallel execution of multiple experiments.
    
Handles:
    - Monte Carlo batches (synthetic GBM with random seeds)
    - Train/test split variations
    - Parallel execution via concurrent.futures
"""

from __future__ import annotations

import math
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd

from lab.data.fetcher import DataFetcher
from lab.data.persistence.interfaces import (
    DataStore,
    ExperimentStatus,
    TradeRecord,
    EquityPoint,
    MetricRecord,
)
from lab.harness.runner import ExperimentConfig, ExperimentRunner


@dataclass
class MechanicsTestResult:
    mechanic: str
    passed: int
    failed: int
    total: int
    pass_rate: float


@dataclass
class BatchResult:
    experiment_name: str
    strategy: str
    data_source: str
    run_id: str
    metrics: dict
    status: str
    error: str | None = None


@dataclass
class BatchSummary:
    strategy: str
    data_source: str
    mechanics_results: list[MechanicsTestResult]
    experiment_results: list[BatchResult]
    aggregate_sharpe: float
    aggregate_win_rate: float
    total_experiments: int
    completed: int
    failed: int


class BatchRunner:
    """Run multiple experiments in parallel.

    Usage:
        batch = BatchRunner(store, fetcher)

        # Monte Carlo: 500 synthetic GBM runs
        mc_results = batch.run_monte_carlo(
            strategy="trend_signal",
            num_runs=500,
            synthetic_config="default",
            agents=["trend_signal"],
        )

        # Train/test splits
        split_results = batch.run_splits(
            strategy="trend_signal",
            splits=["70/30", "75/25", "80/20"],
            symbol="SPY",
            period="5y",
        )

        summary = batch.summarize(mc_results + split_results)
    """

    def __init__(self, store: DataStore, fetcher: DataFetcher | None = None):
        self.store = store
        self.fetcher = fetcher or DataFetcher()
        self.runner = ExperimentRunner(store, fetcher)

    def run_monte_carlo(
        self,
        strategy: str,
        num_runs: int,
        synthetic_config: str = "default",
        agents: list[str] | None = None,
        max_workers: int | None = None,
    ) -> list[BatchResult]:
        """Run Monte Carlo batch with synthetic GBM data."""
        agents = agents or ["trend_signal"]
        results = []

        def run_single(seed: int) -> BatchResult:
            experiment_name = self._generate_experiment_name(strategy)
            config = ExperimentConfig(
                name=experiment_name,
                strategy=strategy,
                data_source="synthetic",
                synthetic_config=synthetic_config,
                agents=agents,
                mode="isolated",
                config={"monte_carlo_seed": seed},
            )

            try:
                exp = self.runner.run(config)
                metrics = {m.metric_name: m.metric_value for m in self.store.get_metrics(exp.run_id)}
                return BatchResult(
                    experiment_name=experiment_name,
                    strategy=strategy,
                    data_source="synthetic",
                    run_id=exp.run_id,
                    metrics=metrics,
                    status="completed",
                    error=None,
                )
            except Exception as e:
                return BatchResult(
                    experiment_name=experiment_name,
                    strategy=strategy,
                    data_source="synthetic",
                    run_id="",
                    metrics={},
                    status="failed",
                    error=str(e),
                )

        seeds = list(range(42, 42 + num_runs))
        max_workers = max_workers or min(8, math.ceil(num_runs / 10))

        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(run_single, seed): seed for seed in seeds}
            for future in as_completed(futures):
                results.append(future.result())

        return results

    def run_splits(
        self,
        strategy: str,
        splits: list[str],
        symbol: str = "SPY",
        period: str = "5y",
        source: str = "yfinance",
        agents: list[str] | None = None,
    ) -> list[BatchResult]:
        """Run experiments with different train/test splits in parallel."""
        agents = agents or ["trend_signal"]
        results = []

        def run_single(split: str) -> BatchResult:
            experiment_name = self._generate_experiment_name(strategy)
            config = ExperimentConfig(
                name=experiment_name,
                strategy=strategy,
                data_source=source,
                symbol=symbol,
                period=period,
                train_test_split=split,
                agents=agents,
                mode="isolated",
            )

            try:
                exp = self.runner.run(config)
                metrics = {m.metric_name: m.metric_value for m in self.store.get_metrics(exp.run_id)}
                return BatchResult(
                    experiment_name=experiment_name,
                    strategy=strategy,
                    data_source=source,
                    run_id=exp.run_id,
                    metrics=metrics,
                    status="completed",
                    error=None,
                )
            except Exception as e:
                return BatchResult(
                    experiment_name=experiment_name,
                    strategy=strategy,
                    data_source=source,
                    run_id="",
                    metrics={},
                    status="failed",
                    error=str(e),
                )

        with ProcessPoolExecutor(max_workers=len(splits)) as executor:
            futures = {executor.submit(run_single, split): split for split in splits}
            for future in as_completed(futures):
                results.append(future.result())

        return results

    def run_mechanics_validation(
        self,
        mechanics: dict[str, Any],
        num_runs: int = 500,
        synthetic_config: str = "default",
    ) -> list[MechanicsTestResult]:
        """Validate architecture mechanics via Monte Carlo.
        
        Args:
            mechanics: Dict of mechanic_name -> assertion_function(run_id)
                      Returns True if mechanic passed, False if failed.
            num_runs: Number of Monte Carlo runs
            synthetic_config: Synthetic config to use
            
        Returns:
            List of MechanicsTestResult per mechanic
        """
        results = self.run_monte_carlo(
            strategy="mechanics_validation",
            num_runs=num_runs,
            synthetic_config=synthetic_config,
            agents=["trend_signal"],
        )

        mechanics_results = []
        for mechanic_name, assertion_fn in mechanics.items():
            passed = 0
            failed = 0
            for result in results:
                if result.status == "failed":
                    failed += 1
                    continue
                try:
                    if assertion_fn(result.run_id):
                        passed += 1
                    else:
                        failed += 1
                except Exception:
                    failed += 1

            total = passed + failed
            pass_rate = passed / total if total > 0 else 0.0
            mechanics_results.append(MechanicsTestResult(
                mechanic=mechanic_name,
                passed=passed,
                failed=failed,
                total=total,
                pass_rate=round(pass_rate, 4),
            ))

        return mechanics_results

    def summarize(self, results: list[BatchResult]) -> BatchSummary:
        """Aggregate results across a batch."""
        completed = [r for r in results if r.status == "completed"]
        failed = [r for r in results if r.status == "failed"]

        shartes = [r.metrics.get("sharpe_ratio", 0) for r in completed if r.metrics]
        win_rates = [r.metrics.get("win_rate", 0) for r in completed if r.metrics]

        return BatchSummary(
            strategy=completed[0].strategy if completed else "unknown",
            data_source=completed[0].data_source if completed else "unknown",
            mechanics_results=[],
            experiment_results=results,
            aggregate_sharpe=round(sum(shartes) / len(shartes), 4) if shartes else 0.0,
            aggregate_win_rate=round(sum(win_rates) / len(win_rates), 4) if win_rates else 0.0,
            total_experiments=len(results),
            completed=len(completed),
            failed=len(failed),
        )

    def _generate_experiment_name(self, strategy: str) -> str:
        ts = datetime.utcnow()
        return ts.strftime(f"[%d-%b-%y][%H:%M:%S]-experiment_run-[{strategy}]")
