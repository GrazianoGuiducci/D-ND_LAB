"""Movement 7 — build lab_graph.

Builds the knowledge graph: nodes (tensions, discoveries, reports +
domain-specific entities like theories) + edges (which report covers
which tension, which discovery connects which entities).

Phase 1 minimal:
  - Universal nodes: active tensions from seed, agent reports
  - Universal edges: report→tension citation
  - Stats: counts + simple centrality

Domain extensions (via params.graph_module):
  A domain plugin can extend the graph with domain-specific entities.
  Example: physics adds T/Q/G/E/R theory nodes + bridge edges + ghost
  detection. Phase 4 wires this for physics from the original
  build_lab_graph.py logic (843 lines), without polluting the core
  with physics-specific concepts.

Output: <data>/<domain>/lab_graph.json (consumed by build_field topology
and downstream visualizations).
"""

from __future__ import annotations

import importlib
import json
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from core import config as cfg
from core import paths
from core.lab_agent import CycleContext, register_movement

logger = logging.getLogger(__name__)


def build_lab_graph(ctx: CycleContext) -> None:
    """Assemble the lab graph for the domain.

    Mutates: writes <data>/<domain>/lab_graph.json
             ctx.metrics["build_graph"] (nodes/edges/stats counts)
    """
    params = cfg.movement_params(ctx.config, "build_graph")

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    # 1. Tension nodes from current seed
    tension_ids = set()
    for t in ctx.seed.get("tensioni", []):
        if not isinstance(t, dict):
            continue
        tid = t.get("id")
        if not tid:
            continue
        tension_ids.add(tid)
        nodes.append({
            "id": tid,
            "type": "tensione",
            "label": (t.get("claim") or "")[:200],
            "intensity": t.get("intensita") or t.get("intensità"),
            "stato": t.get("stato", ""),
        })

    # 2. Recent agent reports as nodes
    reports_dir = paths.reports_dir(ctx.domain)
    if reports_dir.exists():
        report_files = sorted(
            reports_dir.glob("agent_*.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:20]
        for rp in report_files:
            content = ""
            try:
                content = rp.read_text()
            except Exception:
                continue
            m = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
            title = (m.group(1).strip() if m else rp.name)[:200]
            verdict_match = re.search(
                r"##\s*Verdict[^\n]*\n([^\n]+)", content,
            )
            verdict = (verdict_match.group(1).strip() if verdict_match else "")[:100]
            report_id = rp.stem  # agent_YYYYMMDD_HHMM
            nodes.append({
                "id": report_id,
                "type": "report",
                "label": title,
                "verdict": verdict,
                "file": rp.name,
            })

            # Edge: report → tension(s) it covers
            for tid in tension_ids:
                if re.search(rf"\b{re.escape(tid)}\b", content):
                    edges.append({
                        "source": report_id,
                        "target": tid,
                        "type": "covers",
                    })

    # 3. Domain-specific extension (theories, bridges, ghosts, etc.)
    domain_module_name = params.get("graph_module")
    if domain_module_name:
        try:
            mod = importlib.import_module(domain_module_name)
            if hasattr(mod, "extend_graph"):
                mod.extend_graph(ctx, nodes, edges)
        except ImportError as e:
            logger.warning("graph_module %s not importable: %s", domain_module_name, e)
        except Exception as e:
            logger.warning("graph_module %s failed: %s", domain_module_name, e)

    # 4. Stats (universal — counts + degree distribution)
    stats = _compute_stats(nodes, edges)

    out = {
        "graph": {"nodes": nodes, "edges": edges},
        "stats": stats,
        "generated_at": ctx.timestamp,
        "domain": ctx.domain,
    }

    out_path = paths.lab_graph_path(ctx.domain)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))

    ctx.metrics.setdefault("build_graph", {}).update(
        nodes=len(nodes),
        edges=len(edges),
        path=str(out_path),
    )
    logger.info("build_lab_graph: %d nodes, %d edges → %s",
                len(nodes), len(edges), out_path)


def _compute_stats(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, int]:
    by_type: dict[str, int] = defaultdict(int)
    for n in nodes:
        by_type[n.get("type", "unknown")] += 1
    deg: dict[str, int] = defaultdict(int)
    for e in edges:
        deg[e.get("source", "")] += 1
        deg[e.get("target", "")] += 1
    return {
        "n_nodes": len(nodes),
        "n_edges": len(edges),
        "by_type": dict(by_type),
        # Slots filled in by domain extensions if relevant:
        "ponti": by_type.get("ponte", 0),
        "vuoti": by_type.get("vuoto", 0),
        "scoperte": by_type.get("scoperta", 0),
        "ghost_high_urgency": by_type.get("ghost", 0),
    }


# ─── Movement registration ─────────────────────────────────────────

register_movement("build_graph", build_lab_graph)
