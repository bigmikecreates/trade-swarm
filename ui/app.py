"""Flask UI for Trade-Swarm dashboard."""

import re
import subprocess
from pathlib import Path

from flask import Flask, jsonify, render_template, request

import config as cfg
from backtest.run import run_backtest
from data.fetcher import fetch_ohlcv
from agents.signal.trend_agent import TrendSignalAgent

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SPECS_ROOT = PROJECT_ROOT / "planning" / "system_specs"

app = Flask(__name__)
app.json.sort_keys = False


def _detect_version() -> str | None:
    """Extract a semver version from the current git branch name.

    Looks for a v<major>.<minor>.<patch> pattern anywhere in the branch name.
    Returns the version string (e.g. 'v0.1.0') or None if not on a version branch.
    """
    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=PROJECT_ROOT, text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

    match = re.search(r"v\d+\.\d+\.\d+", branch)
    if match:
        return match.group(0)

    return None


def _resolve_experiment_log() -> tuple[str | None, Path | None]:
    """Return (version, log_path) for the current branch.

    Priority:
      1. Version extracted from the git branch name
      2. Fallback: the only version directory that has an EXPERIMENT_LOG.md
      3. None if nothing is found
    """
    version = _detect_version()

    if version:
        log = SPECS_ROOT / version / "EXPERIMENT_LOG.md"
        if log.exists():
            return version, log

    if not SPECS_ROOT.exists():
        return version, None

    logs = sorted(SPECS_ROOT.glob("*/EXPERIMENT_LOG.md"))
    if len(logs) == 1:
        return logs[0].parent.name, logs[0]

    return version, None


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/config")
def api_config():
    return jsonify({
        "symbol": cfg.DEFAULT_SYMBOL,
        "period": cfg.DEFAULT_PERIOD,
        "interval": cfg.DEFAULT_INTERVAL,
        "ema_fast": cfg.EMA_FAST,
        "ema_slow": cfg.EMA_SLOW,
        "adx_threshold": cfg.ADX_THRESHOLD,
        "adx_period": cfg.ADX_PERIOD,
        "init_cash": cfg.INIT_CASH,
        "fee_rate": cfg.FEE_RATE,
        "gate": {
            "min_sharpe": cfg.GATE_MIN_SHARPE,
            "max_drawdown_pct": cfg.GATE_MAX_DRAWDOWN_PCT,
            "min_trades": cfg.GATE_MIN_TRADES,
        },
    })


@app.route("/api/backtest", methods=["POST"])
def api_backtest():
    body = request.get_json(silent=True) or {}
    try:
        result = run_backtest(
            symbol=body.get("symbol", cfg.DEFAULT_SYMBOL),
            period=body.get("period", cfg.DEFAULT_PERIOD),
            interval=body.get("interval", cfg.DEFAULT_INTERVAL),
            ema_fast=int(body.get("ema_fast", cfg.EMA_FAST)),
            ema_slow=int(body.get("ema_slow", cfg.EMA_SLOW)),
            adx_threshold=int(body.get("adx_threshold", cfg.ADX_THRESHOLD)),
            use_regime=bool(body.get("use_regime", False)),
            init_cash=float(body.get("init_cash", cfg.INIT_CASH)),
            fee_rate=float(body.get("fee_rate", cfg.FEE_RATE)),
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/signal", methods=["POST"])
def api_signal():
    body = request.get_json(silent=True) or {}
    symbol = body.get("symbol", cfg.DEFAULT_SYMBOL)
    period = body.get("period", cfg.DEFAULT_PERIOD)
    interval = body.get("interval", cfg.DEFAULT_INTERVAL)
    try:
        df = fetch_ohlcv(symbol, period=period, interval=interval)
        use_regime = bool(body.get("use_regime", False))
        agent = TrendSignalAgent(symbol, use_regime=use_regime)
        sig = agent.generate(df)
        indicators = {}
        for k, v in sig.indicators.items():
            indicators[k] = v if isinstance(v, str) else round(float(v), 6)
        return jsonify({
            "asset": sig.asset,
            "direction": sig.direction.value,
            "strength": sig.strength,
            "confidence": sig.confidence,
            "timestamp": str(sig.timestamp),
            "indicators": indicators,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/version")
def api_version():
    version, log_path = _resolve_experiment_log()
    return jsonify({
        "branch_version": version,
        "has_experiment_log": log_path is not None,
    })


@app.route("/api/experiments")
def api_experiments():
    version, log_path = _resolve_experiment_log()

    if log_path is None or not log_path.exists():
        return jsonify({"version": version, "rows": [], "raw": ""})

    text = log_path.read_text(encoding="utf-8")
    rows = _parse_md_table(text)
    return jsonify({"version": version, "rows": rows, "raw": text})


@app.route("/api/diagrams")
def api_diagrams_list():
    diagrams_root = PROJECT_ROOT / "planning" / "diagrams"
    if not diagrams_root.exists():
        return jsonify([])

    files = []
    for mmd in sorted(diagrams_root.rglob("*.mmd")):
        rel = mmd.relative_to(diagrams_root)
        files.append({
            "name": mmd.stem.replace("_", " ").title(),
            "path": str(rel).replace("\\", "/"),
            "category": rel.parts[0] if len(rel.parts) > 1 else "other",
        })
    return jsonify(files)


@app.route("/api/diagrams/<path:filepath>")
def api_diagram_content(filepath):
    diagrams_root = PROJECT_ROOT / "planning" / "diagrams"
    target = diagrams_root / filepath
    if not target.exists() or not str(target).endswith(".mmd"):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"content": target.read_text(encoding="utf-8")})


def _parse_md_table(text: str) -> list:
    """Extract the first markdown table with a header row into a list of dicts."""
    lines = text.splitlines()
    table_lines = []
    in_table = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            if re.match(r"^\|[\s\-:|]+\|$", stripped):
                in_table = True
                continue
            if in_table:
                table_lines.append(stripped)
            elif not in_table and "|" in stripped:
                headers = [c.strip() for c in stripped.strip("|").split("|")]
                continue
        else:
            if in_table:
                break

    if not table_lines:
        return []

    # Re-scan for headers (first | row before separator)
    headers = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|") and not re.match(r"^\|[\s\-:|]+\|$", stripped):
            headers = [c.strip() for c in stripped.strip("|").split("|")]
            break

    rows = []
    for tl in table_lines:
        cells = [c.strip() for c in tl.strip("|").split("|")]
        if len(cells) == len(headers):
            rows.append(dict(zip(headers, cells)))
    return rows


def run_app():
    print(f"\n  Trade-Swarm Dashboard: http://localhost:5000\n")
    app.run(debug=True, port=5000)


if __name__ == "__main__":
    run_app()
