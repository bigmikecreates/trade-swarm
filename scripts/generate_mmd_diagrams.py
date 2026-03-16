"""Generate Mermaid diagrams for each version of the Trade-Swarm system.

Diagram types
-------------
  Structure  (class_model)   - static shape of the codebase: modules, classes, methods
  Movement   (dataflow)      - how data moves: Yahoo Finance -> indicators -> agent / backtest
  Runtime    (instance_flow) - step-by-step execution of backtest/run.py
  Spec Plan  (spec_diagrams) - high-level build plan extracted from each version spec file

Output layout under plans/diagrams/:
  plans/diagrams/
  ├── class_model/       ← Structure
  ├── dataflow/          ← Movement
  ├── instance_flow/     ← Runtime
  └── spec_diagrams/     ← Spec Plan (one diagram per version)

Spec diagrams are driven by YAML front-matter in plans/system_specs/<version>/<version>.md:

  ---
  spec_diagram:
    title: "v0.1.0 - Spec Plan"
    direction: LR          # optional, default TD
    steps:
      - id: scaffold
        label: "Project Scaffold"
        shape: rect        # optional, default rect
      - id: fetcher
        label: "Data Fetcher"
        depends_on: scaffold          # single id
      - id: backtest
        label: "Backtest"
        depends_on: [fetcher, agent]  # multiple ids
  ---

Usage:
  python scripts/generate_mmd_diagrams.py            # generate .mmd + render .svg
  python scripts/generate_mmd_diagrams.py --src-only # generate .mmd only (no Node.js needed)
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import argparse
import re
import subprocess
import sys


# ---------------------------------------------------------------------------
# YAML front-matter parser (no external dependency - stdlib only)
# ---------------------------------------------------------------------------

def _parse_simple_yaml_value(raw: str) -> Any:
    """Parse a scalar YAML value: quoted string, list, or bare string."""
    raw = raw.strip()
    # Inline list: [a, b, c]
    if raw.startswith("[") and raw.endswith("]"):
        return [v.strip().strip('"').strip("'") for v in raw[1:-1].split(",") if v.strip()]
    # Quoted string
    if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
        return raw[1:-1]
    return raw


def _parse_front_matter(text: str) -> Optional[Dict]:
    """
    Extract and parse the spec_diagram block from YAML front-matter.
    Returns a dict of the spec_diagram key, or None if not present.
    """
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not match:
        return None

    yaml_block = match.group(1)

    # Only process if spec_diagram key is present
    if "spec_diagram:" not in yaml_block:
        return None

    result: Dict = {}
    current_step: Optional[Dict] = None
    steps: List[Dict] = []
    in_spec = False
    in_steps = False

    for line in yaml_block.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue

        indent = len(line) - len(line.lstrip())
        stripped = line.strip()

        if stripped == "spec_diagram:":
            in_spec = True
            continue

        if not in_spec:
            continue

        if indent == 2 and not stripped.startswith("-"):
            key, _, val = stripped.partition(":")
            val = val.strip()
            if key == "steps":
                in_steps = True
            else:
                result[key.strip()] = _parse_simple_yaml_value(val) if val else None

        elif in_steps and stripped.startswith("- "):
            if current_step is not None:
                steps.append(current_step)
            key, _, val = stripped[2:].partition(":")
            current_step = {key.strip(): _parse_simple_yaml_value(val.strip())}

        elif in_steps and indent >= 4 and not stripped.startswith("-") and current_step is not None:
            key, _, val = stripped.partition(":")
            current_step[key.strip()] = _parse_simple_yaml_value(val.strip())

    if current_step is not None:
        steps.append(current_step)

    if steps:
        result["steps"] = steps

    return result


def diagram_from_spec_file(spec_path: Path) -> Optional["Diagram"]:
    """
    Build a Diagram from the YAML front-matter of a spec markdown file.
    Returns None if the file has no spec_diagram block.
    """
    text = spec_path.read_text(encoding="utf-8")
    meta = _parse_front_matter(text)
    if not meta:
        return None

    steps = meta.get("steps", [])
    title = meta.get("title", spec_path.stem)
    direction = meta.get("direction", "TD")

    nodes = [
        Node(
            id=s["id"],
            label=s.get("label", s["id"]),
            shape=s.get("shape", "rect"),
        )
        for s in steps
    ]

    edges = []
    for s in steps:
        deps = s.get("depends_on")
        if deps is None:
            continue
        if isinstance(deps, str):
            deps = [deps]
        for dep in deps:
            edges.append(Edge(source=dep, target=s["id"]))

    return Diagram(title=title, direction=direction, nodes=nodes, edges=edges)


# ---------------------------------------------------------------------------
# Core diagram model
# ---------------------------------------------------------------------------

@dataclass
class Node:
    id: str
    label: str
    shape: str = "rect"  # rect | round | stadium | subroutine | cyl | circle | diamond


@dataclass
class Edge:
    source: str
    target: str
    label: str = ""


@dataclass
class Subgraph:
    id: str
    label: str
    node_ids: List[str] = field(default_factory=list)


@dataclass
class Diagram:
    title: str
    direction: str = "TD"  # TD | LR | BT | RL
    nodes: List[Node] = field(default_factory=list)
    edges: List[Edge] = field(default_factory=list)
    subgraphs: List[Subgraph] = field(default_factory=list)

    def _mermaid_node(self, node: Node) -> str:
        label = node.label.replace('"', '\\"')
        shape_map = {
            "rect":      f'{node.id}["{label}"]',
            "round":     f'{node.id}("{label}")',
            "stadium":   f'{node.id}(["{label}"])',
            "subroutine":f'{node.id}[["{label}"]]',
            "cyl":       f'{node.id}[("{label}")]',
            "circle":    f'{node.id}(("{label}"))',
            "diamond":   f'{node.id}{{"{label}"}}',
        }
        return shape_map.get(node.shape, f'{node.id}["{label}"]')

    def to_mermaid(self) -> str:
        lines = [
            "---",
            f"title: {self.title}",
            "---",
            f"flowchart {self.direction}",
        ]

        # Nodes that belong to a subgraph
        subgraph_nodes: set[str] = set()
        for sg in self.subgraphs:
            subgraph_nodes.update(sg.node_ids)

        # Standalone nodes first
        node_map = {n.id: n for n in self.nodes}
        for node in self.nodes:
            if node.id not in subgraph_nodes:
                lines.append(f"    {self._mermaid_node(node)}")

        # Subgraphs
        for sg in self.subgraphs:
            lines.append(f"")
            lines.append(f"    subgraph {sg.id}[{sg.label}]")
            for nid in sg.node_ids:
                if nid in node_map:
                    lines.append(f"        {self._mermaid_node(node_map[nid])}")
            lines.append(f"    end")

        lines.append("")

        # Edges
        for edge in self.edges:
            if edge.label:
                lines.append(f"    {edge.source} -->|{edge.label}| {edge.target}")
            else:
                lines.append(f"    {edge.source} --> {edge.target}")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Source 1: Version specification → data flow diagram
# ---------------------------------------------------------------------------

def diagram_from_v010_spec() -> Diagram:
    """
    Data flow for the v0.1.0 system:
    Yahoo Finance -> fetcher -> OHLCV -> {indicators, regime detector}
                                      -> agent (EMA crossover + HMM filter)
                                      -> backtest -> gate
    """
    return Diagram(
        title="v0.1.0 - Data Flow",
        direction="LR",
        nodes=[
            Node("YF",      "Yahoo Finance",                     "cyl"),
            Node("FE",      "fetch_ohlcv()",                     "subroutine"),
            Node("DF",      "OHLCV DataFrame",                   "rect"),
            Node("IND",     "indicators.py\nEMA fast / slow",    "rect"),
            Node("HMM",     "regime.py\nGaussianHMM (3 states)", "round"),
            Node("FEAT",    "HMM Features\nlog ret, vol, autocorr", "rect"),
            Node("STATES",  "Regime Labels\ntrending | mean_rev | volatile", "stadium"),
            Node("AGENT",   "TrendSignalAgent\nEMA crossover + regime filter", "round"),
            Node("SIG",     "SignalEvent\ndirection, strength, confidence", "stadium"),
            Node("BT",      "backtest/run.py\nbuild_signals + pandas loop", "rect"),
            Node("GATE",    "Gate Check\nSharpe > 0.8\nDD < 20%, Trades >= 30", "diamond"),
            Node("METRICS", "Metrics\nSharpe, Max DD, Win Rate", "cyl"),
        ],
        edges=[
            Edge("YF",     "FE",      "download OHLCV"),
            Edge("FE",     "DF",      "DataFrame"),
            Edge("DF",     "IND",     "Close"),
            Edge("DF",     "FEAT",    "OHLCV"),
            Edge("FEAT",   "HMM",     "feature matrix"),
            Edge("HMM",    "STATES",  "predict states"),
            Edge("IND",    "AGENT",   "EMA fast, EMA slow"),
            Edge("STATES", "AGENT",   "regime == trending?"),
            Edge("AGENT",  "SIG",     "SignalEvent"),
            Edge("DF",     "BT",      "DataFrame"),
            Edge("IND",    "BT",      "EMA signals"),
            Edge("STATES", "BT",      "regime filter"),
            Edge("BT",     "METRICS", "equity curve"),
            Edge("METRICS","GATE",    "evaluate"),
        ],
        subgraphs=[
            Subgraph("data_layer",   "Data Layer",    ["FE", "DF", "IND"]),
            Subgraph("regime_layer", "Regime Detection", ["FEAT", "HMM", "STATES"]),
            Subgraph("signal_layer", "Signal Layer",  ["AGENT", "SIG"]),
            Subgraph("bt_layer",     "Backtest",      ["BT", "METRICS", "GATE"]),
        ],
    )


# ---------------------------------------------------------------------------
# Source 2a: Python objects → class-level diagram
# ---------------------------------------------------------------------------

def diagram_from_class_model() -> Diagram:
    """
    Class-level structure derived from the v0.1.0 Python source.
    Includes data layer (fetcher, indicators, regime), signal agent,
    backtest runner, and config.
    """
    return Diagram(
        title="v0.1.0 - Class Model",
        direction="TD",
        nodes=[
            # data/fetcher.py
            Node("fetch_ohlcv",      "fetch_ohlcv(symbol, period, interval)\n-> DataFrame", "subroutine"),

            # data/indicators.py
            Node("ind_ema",          "ema(series, length) -> Series",    "subroutine"),
            Node("ind_rsi",          "rsi(series, length) -> Series",    "subroutine"),
            Node("ind_adx",          "adx(high, low, close, length) -> Series", "subroutine"),

            # data/regime.py
            Node("Regime",           "Regime\nTRENDING | MEAN_REVERTING | VOLATILE", "stadium"),
            Node("detect_regimes",   "detect_regimes(df, n_states=3)\n-> Series[Regime]", "subroutine"),
            Node("build_features",   "_build_features(df)\nlog ret, rolling vol, autocorr", "subroutine"),
            Node("label_states",     "_label_states(model, n_states)\n-> Dict[int, Regime]", "subroutine"),

            # agents/signal/trend_agent.py
            Node("Direction",        "Direction\nLONG | SHORT | FLAT",   "stadium"),
            Node("SignalEvent",      "SignalEvent\nasset, direction\nstrength, confidence\ntimestamp, indicators", "rect"),
            Node("TrendSignalAgent", "TrendSignalAgent\n__init__(symbol, use_regime)\ngenerate(df) -> SignalEvent", "round"),

            # backtest/run.py
            Node("build_signals",    "build_signals(df, ema_fast, ema_slow,\nuse_regime) -> (df, entries, exits)", "subroutine"),
            Node("bt_pandas",        "backtest_pandas(df, entries, exits,\ncash, fees) -> dict", "subroutine"),
            Node("run_backtest",     "run_backtest(symbol, period, interval,\nema_fast, ema_slow, use_regime)\n-> dict", "rect"),
            Node("check_gate",       "_check_gate(metrics) -> bool", "diamond"),

            # config.py
            Node("config",           "config.py\nDEFAULT_SYMBOL, EMA_FAST/SLOW\nGATE thresholds, INIT_CASH", "rect"),
        ],
        edges=[
            # fetcher -> indicators
            Edge("fetch_ohlcv", "ind_ema", "Close"),
            Edge("fetch_ohlcv", "ind_rsi", "Close"),
            Edge("fetch_ohlcv", "ind_adx", "High, Low, Close"),

            # fetcher -> regime
            Edge("fetch_ohlcv",    "build_features", "OHLCV"),
            Edge("build_features", "detect_regimes", "feature matrix"),
            Edge("detect_regimes", "label_states",   "HMM model"),
            Edge("label_states",   "Regime",         "maps to"),

            # agent deps
            Edge("ind_ema",          "TrendSignalAgent", "EMA fast/slow"),
            Edge("Regime",           "TrendSignalAgent", "regime state"),
            Edge("Direction",        "SignalEvent",       "direction field"),
            Edge("TrendSignalAgent", "SignalEvent",       "returns"),

            # backtest deps
            Edge("config",         "run_backtest",   "params"),
            Edge("fetch_ohlcv",    "run_backtest",   "OHLCV"),
            Edge("run_backtest",   "build_signals",  "delegates"),
            Edge("ind_ema",        "build_signals",  "EMA fast/slow"),
            Edge("detect_regimes", "build_signals",  "regime series"),
            Edge("build_signals",  "bt_pandas",      "entries, exits"),
            Edge("bt_pandas",      "check_gate",     "metrics"),
        ],
        subgraphs=[
            Subgraph("mod_data",    "data/",           ["fetch_ohlcv", "ind_ema", "ind_rsi", "ind_adx"]),
            Subgraph("mod_regime",  "data/regime.py",  ["Regime", "detect_regimes", "build_features", "label_states"]),
            Subgraph("mod_agent",   "agents/signal/",  ["Direction", "SignalEvent", "TrendSignalAgent"]),
            Subgraph("mod_bt",      "backtest/",       ["build_signals", "bt_pandas", "run_backtest", "check_gate"]),
            Subgraph("mod_config",  "config.py",       ["config"]),
        ],
    )


# ---------------------------------------------------------------------------
# Source 2b: Python objects → instance-level call graph
# ---------------------------------------------------------------------------

def diagram_from_instance_flow() -> Diagram:
    """
    Runtime call graph: what happens step-by-step when run_backtest() executes.
    Includes the HMM regime detection branch.
    """
    return Diagram(
        title="v0.1.0 - Runtime Call Graph",
        direction="TD",
        nodes=[
            Node("start",       "run_backtest()",              "circle"),
            Node("cfg",         "load config\nsymbol, period, interval\nema_fast, ema_slow, use_regime", "rect"),
            Node("fetch",       "fetch_ohlcv(symbol, period, interval)", "subroutine"),
            Node("yf",          "yf.download()",               "cyl"),
            Node("df",          "OHLCV DataFrame",             "rect"),
            Node("build_sig",   "build_signals()",             "rect"),
            Node("ema_f",       "ema(close, fast)",            "subroutine"),
            Node("ema_s",       "ema(close, slow)",            "subroutine"),
            Node("check_hmm",   "use_regime?",                 "diamond"),
            Node("hmm_feat",    "_build_features(df)\nlog ret, vol, autocorr", "subroutine"),
            Node("hmm_fit",     "GaussianHMM.fit()\n3 states", "round"),
            Node("hmm_label",   "_label_states()\nmap to Regime enum", "subroutine"),
            Node("hmm_filter",  "filter: regime == TRENDING",  "rect"),
            Node("crossover",   "EMA crossover\nentries & exits", "rect"),
            Node("bt_loop",     "backtest_pandas()\niterate bars, track equity", "subroutine"),
            Node("equity",      "equity_curve",                "cyl"),
            Node("metrics",     "compute metrics\nSharpe, Max DD, Win Rate", "rect"),
            Node("gate",        "gate check\nSharpe > 0.8?\nDD < 20%?\nTrades >= 30?", "diamond"),
            Node("result",      "return results",              "stadium"),
        ],
        edges=[
            Edge("start",      "cfg",        ""),
            Edge("cfg",        "fetch",      ""),
            Edge("fetch",      "yf",         "download"),
            Edge("yf",         "df",         "raw OHLCV"),
            Edge("df",         "build_sig",  ""),
            Edge("build_sig",  "ema_f",      "Close"),
            Edge("build_sig",  "ema_s",      "Close"),
            Edge("build_sig",  "check_hmm",  ""),
            Edge("check_hmm",  "hmm_feat",   "yes"),
            Edge("hmm_feat",   "hmm_fit",    "feature matrix"),
            Edge("hmm_fit",    "hmm_label",  "model + states"),
            Edge("hmm_label",  "hmm_filter", "Regime series"),
            Edge("hmm_filter", "crossover",  "trending bars only"),
            Edge("check_hmm",  "crossover",  "no (all bars)"),
            Edge("crossover",  "bt_loop",    "entries, exits"),
            Edge("bt_loop",    "equity",     "mark-to-market"),
            Edge("equity",     "metrics",    "pct change, drawdown"),
            Edge("metrics",    "gate",       "evaluate"),
            Edge("gate",       "result",     "PASS / FAIL"),
        ],
    )


# ---------------------------------------------------------------------------
# Branch version detection
# ---------------------------------------------------------------------------

def _detect_branch_version() -> Optional[str]:
    """Extract semver (e.g. 'v0.1.0') from the current git branch name.

    Looks for patterns like v0.1.0, v0.1.0-feature, release/v0.2.0, etc.
    Returns None on main/master or branches without a version.
    """
    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

    m = re.search(r"v(\d+\.\d+\.\d+)", branch)
    return f"v{m.group(1)}" if m else None


# ---------------------------------------------------------------------------
# CLI rendering
# ---------------------------------------------------------------------------

def render_mermaid(input_file: Path, output_file: Path) -> None:
    cmd = ["npx", "mmdc", "-i", str(input_file), "-o", str(output_file)]
    result = subprocess.run(cmd, capture_output=True, text=True, shell=(sys.platform == "win32"))
    if result.returncode != 0:
        print(f"  [ERROR] Mermaid render failed for {input_file.name}", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

# Each entry: (version, output subfolder, stem name, diagram factory)
DIAGRAM_REGISTRY: List[tuple] = [
    ("v0.1.0", "class_model",   "v010_class_model",    diagram_from_class_model),
    ("v0.1.0", "dataflow",      "v010_spec_dataflow",  diagram_from_v010_spec),
    ("v0.1.0", "instance_flow", "v010_instance_flow",  diagram_from_instance_flow),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Mermaid diagrams for the trading system.")
    parser.add_argument(
        "--src-only",
        action="store_true",
        help="Write .mmd source files only; skip SVG rendering (no Node.js required).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Generate diagrams for all versions (ignore branch detection).",
    )
    parser.add_argument(
        "--version",
        type=str,
        default=None,
        help="Target version (e.g. v0.1.0). Overrides branch auto-detection.",
    )
    args = parser.parse_args()

    repo_root  = Path(__file__).resolve().parents[1]
    base_dir   = repo_root / "planning" / "diagrams"
    specs_root = repo_root / "planning" / "system_specs"

    # --- Resolve target version ---
    if args.all:
        target_version = None
    elif args.version:
        target_version = args.version
    else:
        target_version = _detect_branch_version()

    if target_version:
        print(f"\nBranch version detected: {target_version}")
        print(f"Generating diagrams for {target_version} only (use --all for everything)\n")
    else:
        print(f"\nNo version branch detected (or --all specified). Generating all diagrams.\n")

    print(f"Output root: {base_dir}\n")

    # --- Hardcoded Python-object diagrams ---
    registry = DIAGRAM_REGISTRY
    if target_version:
        registry = [r for r in registry if r[0] == target_version]

    if registry:
        print("-- Python diagrams ------------------------------------------")
        for _ver, subfolder, stem, factory in registry:
            type_dir = base_dir / subfolder
            type_dir.mkdir(parents=True, exist_ok=True)

            diagram  = factory()
            mmd_file = type_dir / f"{stem}.mmd"
            svg_file = type_dir / f"{stem}.svg"

            mmd_file.write_text(diagram.to_mermaid(), encoding="utf-8")
            print(f"  [mmd] {mmd_file.relative_to(repo_root)}")

            if not args.src_only:
                render_mermaid(mmd_file, svg_file)
                print(f"  [svg] {svg_file.relative_to(repo_root)}")
    else:
        print(f"-- Python diagrams: none registered for {target_version} --")

    # --- Spec-file diagrams (auto-discovered via YAML front-matter) ---
    spec_files = sorted(
        p for p in specs_root.glob("**/*.md")
        if re.match(r"^v\d+\.\d+\.\d+\.md$", p.name)
    ) if specs_root.exists() else []

    if target_version:
        spec_files = [p for p in spec_files if p.parent.name == target_version]

    if spec_files:
        print("\n-- Spec diagrams --------------------------------------------")
        spec_dir = base_dir / "spec_diagrams"
        spec_dir.mkdir(parents=True, exist_ok=True)

        for spec_path in spec_files:
            diagram = diagram_from_spec_file(spec_path)
            if diagram is None:
                print(f"  [skip] {spec_path.relative_to(repo_root)}  (no spec_diagram front-matter)")
                continue

            version_slug = spec_path.parent.name.replace(".", "").replace("-", "_")
            stem     = f"{version_slug}_spec_plan"
            mmd_file = spec_dir / f"{stem}.mmd"
            svg_file = spec_dir / f"{stem}.svg"

            mmd_file.write_text(diagram.to_mermaid(), encoding="utf-8")
            print(f"  [mmd] {mmd_file.relative_to(repo_root)}")

            if not args.src_only:
                render_mermaid(mmd_file, svg_file)
                print(f"  [svg] {svg_file.relative_to(repo_root)}")

    print("\nDone." if not args.src_only else "\nDone (source files only - run without --src-only to render SVGs).")


if __name__ == "__main__":
    main()
