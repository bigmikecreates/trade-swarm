"""Flask dashboard for the Trade-Swarm Agent Laboratory."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from flask import Flask, render_template, request, redirect, url_for

from lab.config import lab_config
from lab.data.persistence.directory_store import DirectoryStore

app = Flask(__name__)

store = None
try:
    store = DirectoryStore(lab_config.EXPERIMENTS_DIR)
except Exception:
    pass


def get_store():
    global store
    if store is None:
        store = DirectoryStore(lab_config.EXPERIMENTS_DIR)
    return store


def load_experiments(strategy: str | None = None, limit: int = 50):
    try:
        return get_store().list_experiments(strategy=strategy, limit=limit)
    except Exception:
        return []


def load_experiment_data(run_id: str):
    try:
        s = get_store()
        exp = s.get_experiment(run_id)
        trades = s.get_trades(run_id)
        signals = s.get_signals(run_id)
        equity = s.get_equity_curve(run_id)
        return exp, trades, signals, equity
    except Exception:
        return None, [], [], []


def trades_to_list(trades):
    if not trades:
        return []
    return [
        {
            "trade_id": t.trade_id,
            "run_id": t.run_id,
            "asset": t.asset,
            "direction": t.direction,
            "action": t.action,
            "size": t.size,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "pnl": t.pnl,
            "stop_loss": t.stop_loss,
            "status": t.status,
            "created_at": t.created_at.strftime("%Y-%m-%d %H:%M:%S") if t.created_at else "",
        }
        for t in trades
    ]


def signals_to_list(signals):
    if not signals:
        return []
    return [
        {
            "signal_id": s.signal_id,
            "run_id": s.run_id,
            "agent_id": s.agent_id,
            "asset": s.asset,
            "direction": s.direction,
            "strength": s.strength,
            "confidence": s.confidence,
            "timestamp": s.timestamp.strftime("%Y-%m-%d %H:%M:%S") if s.timestamp else "",
        }
        for s in signals
    ]


def equity_to_list(equity):
    if not equity:
        return []
    return [
        {
            "run_id": e.run_id,
            "timestamp": e.timestamp.strftime("%Y-%m-%d %H:%M:%S") if e.timestamp else "",
            "equity": e.equity,
            "drawdown": e.drawdown,
        }
        for e in equity
    ]


@app.route("/")
def overview():
    experiments = load_experiments(limit=100)
    return render_template(
        "overview.html",
        experiments=experiments,
        agents=lab_config.AVAILABLE_AGENTS,
        sources=lab_config.AVAILABLE_DATA_SOURCES,
        store_connected=store is not None,
    )


@app.route("/experiments")
def experiments():
    strategy_filter = request.args.get("strategy", "All")
    strategy = None if strategy_filter == "All" else strategy_filter
    experiments = load_experiments(strategy=strategy, limit=100)
    
    completed = len([e for e in experiments if e.status.value == "completed"])
    failed = len([e for e in experiments if e.status.value == "failed"])
    
    return render_template(
        "experiments.html",
        experiments=experiments,
        strategies=["All"] + lab_config.AVAILABLE_STRATEGIES,
        selected_strategy=strategy_filter,
        completed=completed,
        failed=failed,
        total=len(experiments),
    )


@app.route("/experiment/<run_id>")
def experiment_detail(run_id):
    exp, trades, signals, equity = load_experiment_data(run_id)
    
    if not exp:
        return "Experiment not found", 404
    
    trades_list = trades_to_list(trades)
    signals_list = signals_to_list(signals)
    equity_list = equity_to_list(equity)
    
    closed_trades = [t for t in trades_list if t["action"] == "exit"]
    total_pnl = sum(t["pnl"] for t in closed_trades if t["pnl"])
    
    equity_df = equity_list
    initial_equity = 10000
    final_equity = equity_df[-1]["equity"] if equity_df else initial_equity
    return_pct = ((final_equity - initial_equity) / initial_equity) * 100
    
    return render_template(
        "experiment_detail.html",
        experiment=exp,
        trades=trades_list,
        signals=signals_list,
        equity=equity_list,
        total_pnl=total_pnl,
        return_pct=return_pct,
    )


@app.route("/compare")
def compare():
    selected_runs = request.args.getlist("runs")
    
    if not selected_runs:
        experiments = load_experiments(limit=20)
        return render_template(
            "compare_select.html",
            experiments=experiments,
        )
    
    comparison_data = []
    for run_id in selected_runs:
        exp, trades, signals, equity = load_experiment_data(run_id)
        
        trades_list = trades_to_list(trades)
        equity_list = equity_to_list(equity)
        
        closed_trades = [t for t in trades_list if t["action"] == "exit"]
        total_pnl = sum(t["pnl"] for t in closed_trades if t["pnl"])
        num_trades = len(closed_trades)
        wins = len([t for t in closed_trades if t.get("pnl", 0) > 0])
        win_rate = wins / num_trades if num_trades > 0 else 0
        
        initial_equity = 10000
        final_equity = equity_list[-1]["equity"] if equity_list else initial_equity
        return_pct = ((final_equity - initial_equity) / initial_equity) * 100
        
        comparison_data.append({
            "run_id": run_id,
            "strategy": exp.strategy if exp else "unknown",
            "total_pnl": total_pnl,
            "return_pct": return_pct,
            "win_rate": win_rate,
            "num_trades": num_trades,
        })
    
    return render_template(
        "compare.html",
        comparisons=comparison_data,
    )


@app.route("/trades")
def trades():
    run_id = request.args.get("run_id")
    
    experiments = load_experiments(limit=20)
    
    if not run_id and experiments:
        run_id = experiments[0].run_id
    
    if run_id:
        exp, trades_list, signals, equity = load_experiment_data(run_id)
        trades_list = trades_to_list(trades_list)
    else:
        trades_list = []
        exp = None
    
    closed = [t for t in trades_list if t["action"] == "exit"]
    wins = len([t for t in closed if t.get("pnl", 0) > 0])
    losses = len([t for t in closed if t.get("pnl", 0) < 0])
    total_pnl = sum(t.get("pnl", 0) for t in closed)
    
    direction_counts = {}
    for t in trades_list:
        d = t["direction"]
        direction_counts[d] = direction_counts.get(d, 0) + 1
    
    return render_template(
        "trades.html",
        experiments=experiments,
        selected_run=run_id,
        trades=trades_list,
        closed_count=len(closed),
        wins=wins,
        losses=losses,
        total_pnl=total_pnl,
        direction_counts=direction_counts,
    )


@app.route("/signals")
def signals():
    run_id = request.args.get("run_id")
    
    experiments = load_experiments(limit=20)
    
    if not run_id and experiments:
        run_id = experiments[0].run_id
    
    if run_id:
        exp, trades, signals_list, equity = load_experiment_data(run_id)
        signals_list = signals_to_list(signals_list)
    else:
        signals_list = []
        exp = None
    
    longs = len([s for s in signals_list if s["direction"] == "long"])
    shorts = len([s for s in signals_list if s["direction"] == "short"])
    
    return render_template(
        "signals.html",
        experiments=experiments,
        selected_run=run_id,
        signals=signals_list,
        total=len(signals_list),
        longs=longs,
        shorts=shorts,
    )


@app.route("/agents")
def agents():
    return render_template(
        "agents.html",
        agents=lab_config.AVAILABLE_AGENTS,
        sources=lab_config.AVAILABLE_DATA_SOURCES,
    )


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
