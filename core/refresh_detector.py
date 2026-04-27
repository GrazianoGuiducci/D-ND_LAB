"""Movement 12 — refresh_detector.

Event-driven trigger: decides if a heavy regeneration (e.g. theory
crossing) should run, based on whether enough new material has accumulated
since the last refresh.

Observation: the underlying knowledge structure (e.g. theory pairs) is
fixed. The lab produces deltas (insights, ghosts, evolved bridges). A
refresh that runs on every cron is cosmetic and wastes budget. Refresh
only when there is real new material — or as a failsafe after N days
without refresh.

Universal thresholds (overridable via params):
  - ≥1 new ghost since last refresh → TRIGGER
  - ≥2 new evolved bridges since last refresh → TRIGGER
  - ≥1 new insight_dal_lab since last refresh → TRIGGER
  - ≥14 days since last refresh → TRIGGER (failsafe)

The actual regeneration is domain-specific (theory crossing for physics,
glossary regen for editorial, etc.) — wired via params.regen_module.
Without a regen_module, this movement only logs the decision.
"""

from __future__ import annotations

import importlib
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from core import config as cfg
from core import paths
from core.lab_agent import CycleContext, register_movement

logger = logging.getLogger(__name__)


def refresh_detector(ctx: CycleContext) -> None:
    """Check thresholds, decide refresh, optionally call regen_module."""
    params = cfg.movement_params(ctx.config, "refresh_detector")
    staleness_days = int(params.get("staleness_days", 14))
    ghost_threshold = int(params.get("ghost_threshold", 1))
    bridges_threshold = int(params.get("bridges_threshold", 2))
    insights_threshold = int(params.get("insights_threshold", 1))
    force = bool(params.get("force", False))

    state_path = paths.domain_data_dir(ctx.domain) / "refresh_detector_state.json"
    state = _load_json(state_path) or {}
    last_refresh_iso = state.get("last_refresh")
    last_counts = state.get("last_counts", {})

    # Count current state
    counts = _count_current_state(ctx.domain)

    # Compute deltas
    new_ghosts = counts.get("ghosts", 0) - last_counts.get("ghosts", 0)
    new_bridges = counts.get("bridges", 0) - last_counts.get("bridges", 0)
    new_insights = counts.get("insights", 0) - last_counts.get("insights", 0)

    # Check thresholds
    reasons: list[str] = []
    if force:
        reasons.append("force=true")
    if new_ghosts >= ghost_threshold:
        reasons.append(f"new_ghosts={new_ghosts} ≥ {ghost_threshold}")
    if new_bridges >= bridges_threshold:
        reasons.append(f"new_bridges={new_bridges} ≥ {bridges_threshold}")
    if new_insights >= insights_threshold:
        reasons.append(f"new_insights={new_insights} ≥ {insights_threshold}")

    # Staleness failsafe
    stale = False
    if last_refresh_iso:
        try:
            last_dt = datetime.fromisoformat(last_refresh_iso.replace("Z", "+00:00"))
            stale = (datetime.now(timezone.utc) - last_dt) > timedelta(days=staleness_days)
        except Exception:
            stale = True
    else:
        stale = True

    if stale:
        reasons.append(f"staleness ≥ {staleness_days}d")

    should_refresh = bool(reasons)
    ctx.metrics.setdefault("refresh_detector", {}).update(
        should_refresh=should_refresh,
        reasons=reasons,
        deltas={"ghosts": new_ghosts, "bridges": new_bridges, "insights": new_insights},
    )

    if not should_refresh:
        logger.info("refresh_detector: skip (no thresholds reached)")
        return

    logger.info("refresh_detector: TRIGGER — %s", "; ".join(reasons))

    # Call domain regen module if configured
    regen_module = params.get("regen_module")
    if regen_module:
        try:
            mod = importlib.import_module(regen_module)
            if hasattr(mod, "regenerate"):
                regen_result = mod.regenerate(ctx)
                ctx.metrics.setdefault("refresh_detector", {})["regen_result"] = regen_result
        except ImportError as e:
            logger.warning("regen_module %s not importable: %s", regen_module, e)
        except Exception as e:
            logger.warning("regen_module %s failed: %s", regen_module, e)

    # Update state
    new_state = {
        "last_refresh": datetime.now(timezone.utc).isoformat(),
        "last_counts": counts,
        "last_reasons": reasons,
    }
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(new_state, indent=2, ensure_ascii=False))


def _count_current_state(domain: str) -> dict[str, int]:
    """Count current ghosts / bridges / insights from canonical files."""
    counts = {"ghosts": 0, "bridges": 0, "insights": 0}

    # Insights from conoscenza.json
    conoscenza_p = paths.domain_data_dir(domain) / "conoscenza.json"
    c = _load_json(conoscenza_p) or {}
    il = c.get("insights_dal_lab", {})
    if isinstance(il, dict):
        counts["insights"] = sum(
            len(v) for v in il.values() if isinstance(v, list)
        )

    # Ghosts + bridges from lab_graph.json (universal node types)
    graph_p = paths.lab_graph_path(domain)
    g = _load_json(graph_p) or {}
    nodes = g.get("graph", {}).get("nodes", [])
    for n in nodes:
        if not isinstance(n, dict):
            continue
        t = n.get("type", "")
        if t == "ghost":
            counts["ghosts"] += 1
        elif t == "ponte":
            counts["bridges"] += 1

    return counts


def _load_json(p: Path) -> dict[str, Any] | None:
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


# ─── Movement registration ─────────────────────────────────────────

register_movement("refresh_detector", refresh_detector)
