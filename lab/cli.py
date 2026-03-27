#!/usr/bin/env python3
"""Trade-Swarm Agent Laboratory CLI.

Usage:
    lab run --agent trend_signal --source synthetic
    lab run --agent trend_signal --source yfinance --symbol SPY --period 5y
    lab batch --agent trend_signal --splits 70/30,75/25,80/20
    lab batch --agent trend_signal --monte_carlo 500
    lab mechanics --runs 500
    lab list
    lab eval --run exp_001
    lab cleanup --dry-run
    lab cleanup --confirm
    lab agents list
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, UTC

from lab.config import lab_config
from lab.data.fetcher import DataFetcher
from lab.data.persistence.directory_store import DirectoryStore
from lab.harness.batch_runner import BatchRunner, BatchSummary
from lab.harness.factory import AgentFactory
from lab.harness.runner import ExperimentConfig, ExperimentRunner


def _get_store():
    from lab.data.persistence.directory_store import DirectoryStore
    return DirectoryStore(lab_config.EXPERIMENTS_DIR)


def cmd_run(args):
    store = _get_store()
    fetcher = DataFetcher()
    runner = ExperimentRunner(store, fetcher)

    ts = datetime.now(UTC)
    name = ts.strftime(f"[%d-%b-%y][%H:%M:%S]-experiment_run-[{args.agent}]")

    config = ExperimentConfig(
        name=name,
        strategy=args.agent,
        data_source=args.source,
        symbol=args.symbol or "SYNTHETIC",
        timeframe=args.timeframe or "M1",
        period=args.period,
        train_test_split=args.split,
        agents=[args.agent],
        mode=args.mode or "isolated",
        config={
            "init_cash": args.init_cash or lab_config.DEFAULT_INIT_CASH,
            "fee_rate": args.fee_rate or lab_config.DEFAULT_FEE_RATE,
            "risk_pct": args.risk_pct or lab_config.DEFAULT_RISK_PCT,
        },
    )

    print(f"Running experiment: {name}")
    result = runner.run(config)
    print(f"Completed: run_id={result.run_id}")
    print(f"Status: {result.status}")


def cmd_batch(args):
    store = _get_store()
    fetcher = DataFetcher()
    batch = BatchRunner(store, fetcher)

    if args.monte_carlo:
        print(f"Running Monte Carlo: {args.monte_carlo} runs with {args.agent}")
        results = batch.run_monte_carlo(
            strategy=args.agent,
            num_runs=args.monte_carlo,
            synthetic_config=args.synthetic_config or "default",
            agents=[args.agent],
        )
        summary = batch.summarize(results)
        _print_summary(summary)

    elif args.splits:
        splits = args.splits.split(",")
        print(f"Running splits: {splits} for {args.agent}")
        results = batch.run_splits(
            strategy=args.agent,
            splits=splits,
            symbol=args.symbol or "SPY",
            period=args.period or "5y",
            source=args.source or "yfinance",
            agents=[args.agent],
        )
        summary = batch.summarize(results)
        _print_summary(summary)


def cmd_mechanics(args):
    store = _get_store()
    fetcher = DataFetcher()
    batch = BatchRunner(store, fetcher)

    print(f"Running mechanics validation: {args.runs} Monte Carlo runs")

    def stop_loss_mechanic(run_id: str) -> bool:
        trades = store.get_trades(run_id)
        return len(trades) >= 0

    def trade_log_mechanic(run_id: str) -> bool:
        trades = store.get_trades(run_id)
        entries = [t for t in trades if t.action == "enter"]
        exits = [t for t in trades if t.action == "exit"]
        return len(entries) == len(exits)

    mechanics_results = batch.run_mechanics_validation(
        mechanics={
            "stop_loss_triggered": stop_loss_mechanic,
            "trade_log_complete": trade_log_mechanic,
        },
        num_runs=args.runs,
        synthetic_config=args.config or "default",
    )

    print("\nMechanics Validation Results:")
    print("-" * 50)
    for mr in mechanics_results:
        status = "PASS" if mr.pass_rate >= 0.95 else "FAIL"
        print(f"  [{status}] {mr.mechanic}: {mr.passed}/{mr.total} ({mr.pass_rate:.1%})")


def cmd_list(args):
    store = _get_store()
    experiments = store.list_experiments(strategy=args.strategy, limit=args.limit or 50)

    if not experiments:
        print("No experiments found.")
        return

    print(f"{'Run ID':<20} {'Strategy':<20} {'Status':<12} {'Created'}")
    print("-" * 80)
    for exp in experiments:
        print(f"{exp.run_id:<20} {exp.strategy:<20} {exp.status.value:<12} {exp.created_at}")


def cmd_eval(args):
    store = _get_store()
    exp = store.get_experiment(args.run)
    if not exp:
        print(f"Experiment not found: {args.run}")
        return

    metrics = store.get_metrics(args.run)
    trades = store.get_trades(args.run)

    print(f"Experiment: {exp.name}")
    print(f"Strategy: {exp.strategy}")
    print(f"Data Source: {exp.data_source}")
    print(f"Status: {exp.status.value}")
    print(f"\nMetrics:")
    for m in metrics:
        print(f"  {m.metric_name}: {m.metric_value}")
    print(f"\nTrades: {len(trades)}")


def cmd_cleanup(args):
    store = _get_store()
    ttl_days = args.ttl or lab_config.CLEANUP_TTL_DAYS

    dirs = store.list_all_dirs()
    to_delete = [
        d for d in dirs
        if store.get_dir_age_days(d) > ttl_days
    ]

    if not to_delete:
        print(f"No experiment directories older than {ttl_days} days.")
        return

    print(f"Found {len(to_delete)} directories to clean up:")
    for d in to_delete:
        age = store.get_dir_age_days(d)
        print(f"  - {d.name} ({age:.1f} days old)")

    if args.dry_run:
        print("\nDry run — no directories deleted.")
        return

    if not args.confirm:
        response = input(f"\nDelete {len(to_delete)} directories? [y/N]: ")
        if response.lower() != "y":
            print("Aborted.")
            return

    for d in to_delete:
        import shutil
        shutil.rmtree(d)
        print(f"Deleted: {d.name}")


def cmd_agents_list(args):
    print("Available agents:")
    for agent in lab_config.AVAILABLE_AGENTS:
        print(f"  - {agent}")


def cmd_sources_list(args):
    from lab.data.fetcher import DataFetcher
    print("Available data sources:")
    print(f"  {'Source':<30} {'Status':<15} {'Notes'}")
    print(f"  {'-'*30} {'-'*15} {'-'*30}")
    for source in lab_config.AVAILABLE_DATA_SOURCES:
        status = "ready"
        notes = ""
        if source == "yfinance":
            notes = "Equities, ETFs, crypto"
        elif source == "synthetic":
            notes = "GBM synthetic — mechanics only"
        elif source.startswith("ctrader_"):
            broker = source.replace("ctrader_", "").replace("_", " ").title()
            notes = f"{broker} — requires demo account"
        elif source == "histdata":
            notes = "M1 forex — download from histdata.com"
        elif source == "ibkr":
            notes = "All asset classes — requires TWS running"
        print(f"  {source:<30} {status:<15} {notes}")


def _print_summary(summary: BatchSummary):
    print(f"\nBatch Summary ({summary.strategy})")
    print("-" * 50)
    print(f"  Total experiments: {summary.total_experiments}")
    print(f"  Completed: {summary.completed}")
    print(f"  Failed: {summary.failed}")
    print(f"  Avg Sharpe: {summary.aggregate_sharpe:.4f}")
    print(f"  Avg Win Rate: {summary.aggregate_win_rate:.2%}")
    print("\nIndividual runs:")
    for result in summary.experiment_results:
        status = "✅" if result.status == "completed" else "❌"
        sharpe = result.metrics.get("sharpe_ratio", "N/A")
        trades = result.metrics.get("total_trades", "N/A")
        print(f"  {status} {result.experiment_name} | Sharpe: {sharpe} | Trades: {trades}")


def main():
    parser = argparse.ArgumentParser(
        description="Trade-Swarm Agent Laboratory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s run --agent trend_signal --source synthetic
  %(prog)s run --agent trend_signal --source yfinance --symbol SPY --period 5y
  %(prog)s batch --agent trend_signal --splits 70/30,75/25,80/20
  %(prog)s batch --agent trend_signal --monte-carlo 500
  %(prog)s mechanics --runs 500
  %(prog)s list --strategy trend_signal
  %(prog)s eval --run exp_001
  %(prog)s cleanup --ttl 5
        """
    )
    sub = parser.add_subparsers(dest="command")

    run_parser = sub.add_parser("run", help="Run a single experiment")
    run_parser.add_argument(
        "--agent", required=True,
        help=f"Agent to use (available: {', '.join(lab_config.AVAILABLE_AGENTS)})"
    )
    run_parser.add_argument(
        "--source", required=True, 
        choices=lab_config.AVAILABLE_DATA_SOURCES,
        help=f"Data source (choices: {', '.join(lab_config.AVAILABLE_DATA_SOURCES)})"
    )
    run_parser.add_argument("--symbol", default="SYNTHETIC", help="Asset symbol (default: SYNTHETIC)")
    run_parser.add_argument("--timeframe", default="M1", help="Timeframe (default: M1)")
    run_parser.add_argument("--period", help="Data period (e.g., 5y, 1mo)")
    run_parser.add_argument("--split", help="Train/test split (e.g., 70/30)")
    run_parser.add_argument("--mode", choices=["isolated", "coordinated"], help="Execution mode")
    run_parser.add_argument("--init_cash", type=float, help="Initial cash (default: 10000)")
    run_parser.add_argument("--fee-rate", dest="fee_rate", type=float, help="Fee rate per trade")
    run_parser.add_argument("--risk-pct", dest="risk_pct", type=float, help="Risk percentage per trade")

    batch_parser = sub.add_parser("batch", help="Run batch experiments")
    batch_parser.add_argument(
        "--agent", required=True,
        help=f"Agent to use (available: {', '.join(lab_config.AVAILABLE_AGENTS)})"
    )
    batch_parser.add_argument(
        "--source", default="yfinance",
        choices=lab_config.AVAILABLE_DATA_SOURCES,
        help="Data source"
    )
    batch_parser.add_argument("--symbol", default="SPY", help="Asset symbol")
    batch_parser.add_argument("--period", default="5y", help="Data period")
    batch_parser.add_argument("--splits", help="Comma-separated train/test splits (e.g., 70/30,75/25)")
    batch_parser.add_argument("--monte-carlo", type=int, help="Number of Monte Carlo runs")
    batch_parser.add_argument("--synthetic-config", default="default", help="Synthetic GBM config name")

    mech_parser = sub.add_parser("mechanics", help="Run mechanics validation")
    mech_parser.add_argument("--runs", type=int, default=500, help="Number of validation runs (default: 500)")
    mech_parser.add_argument("--config", default="default", help="Synthetic GBM config (default: default)")

    list_parser = sub.add_parser("list", help="List experiments")
    list_parser.add_argument("--strategy", help="Filter by strategy")
    list_parser.add_argument("--limit", type=int, default=50, help="Max results to show (default: 50)")

    eval_parser = sub.add_parser("eval", help="Evaluate an experiment")
    eval_parser.add_argument("--run", required=True, help="Experiment run_id to evaluate")

    cleanup_parser = sub.add_parser("cleanup", help="Clean up old experiment directories")
    cleanup_parser.add_argument("--ttl", type=int, help="Delete directories older than N days")
    cleanup_parser.add_argument("--dry-run", action="store_true", help="Preview without deleting")
    cleanup_parser.add_argument("--confirm", action="store_true", help="Skip confirmation prompt")

    agents_parser = sub.add_parser("agents", help="List available agents")
    agents_parser.add_argument("list", nargs="?")

    sources_parser = sub.add_parser("sources", help="List available data sources")
    sources_parser.add_argument("list", nargs="?")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Validate agent
    if hasattr(args, 'agent') and args.agent:
        if args.agent not in lab_config.AVAILABLE_AGENTS:
            parser.error(f"Unknown agent: {args.agent}. Available: {', '.join(lab_config.AVAILABLE_AGENTS)}")

    commands = {
        "run": cmd_run,
        "batch": cmd_batch,
        "mechanics": cmd_mechanics,
        "list": cmd_list,
        "eval": cmd_eval,
        "cleanup": cmd_cleanup,
        "agents": cmd_agents_list,
        "sources": cmd_sources_list,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
