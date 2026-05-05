"""Lab agent — 13-movement orchestrator.

The orchestrator dispatches the cycle. Each movement is a callable
in MOVEMENTS that reads + mutates the CycleContext. Movements live in
their own modules under core/ and get registered here.

The 13 movements (in order):
   0.  autopsy              — observe previous run, identify regressive node
   1.  build_field          — assemble agent_field_live.md (tensions + context)
   2.  agent                — autonomous LLM cycle: pick one tension, run experiment
   3.  validate_seed        — integrity check + restore from backup if corrupted
   4.  verify_assertions    — run condensate claims, mark PASS/FAIL
   5.  structural_check     — scan touched code, inject META tensions on anti-patterns
   6.  build_lab_data       — snapshot piano + tensions + last report
   7.  build_graph          — knowledge graph nodes/edges
   8.  sync                 — propagate state (filesystem / external endpoints)
   9.  verify_endpoints     — health-check downstream consumers
   10. refiner              — second LLM observes the step (not the result) — A8
   11. semantic_bridge      — map findings to domain category mapping
   12. refresh_detector     — event-driven regen of derivative views
   13. seed_integrator      — crystallize: tensions → filtered → direction rotates
   14. trajectory_evaluator — separate LLM decides STOP/NEXT/REDESIGN/etc (log-only)
   15. notify               — webhook to operator

Pattern f(f(x)): movements 0, 5, 10, 14 are reflective — the system
observes the system. Movement 13 (seed_integrator) closes the autopoietic
loop A5.

Failure handling:
  - Critical movements (build_field, agent): if they fail, cycle aborts.
  - Reflective movements (autopsy, refiner, trajectory_evaluator) and
    side-effect movements (sync, notify): degrade gracefully, log error,
    continue.
  - Validation movements (validate_seed, structural_check): non-critical
    but tracked — multiple failures across cycles trigger an alert.
"""

from __future__ import annotations

import json
import logging
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core import config as cfg
from core import paths

logger = logging.getLogger(__name__)


# ─── CycleContext ────────────────────────────────────────────────────


@dataclass
class CycleContext:
    """Per-cycle state passed between movements.

    Movements read/write this object instead of touching files directly,
    so testing is easier and side effects are localized.
    """
    domain: str
    timestamp: str
    data_dir: Path
    config: dict[str, Any]
    seed: dict[str, Any] = field(default_factory=dict)
    health: dict[str, Any] = field(default_factory=dict)
    agent_output_path: Path | None = None
    report_path: Path | None = None
    errors: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    movement_status: dict[str, str] = field(default_factory=dict)

    def record_error(self, movement: str, error: str) -> None:
        self.errors.append(f"[{movement}] {error}")
        self.movement_status[movement] = "error"

    def record_success(self, movement: str, **metrics: Any) -> None:
        self.movement_status[movement] = "ok"
        if metrics:
            self.metrics.setdefault(movement, {}).update(metrics)

    def record_skipped(self, movement: str, reason: str) -> None:
        self.movement_status[movement] = f"skipped: {reason}"


# ─── Movement registry ──────────────────────────────────────────────
# Each movement is a callable: (ctx: CycleContext) -> None
# Movements raise on critical failure; non-critical failures are logged
# in ctx.errors and the orchestrator decides whether to continue.

# Ordered list — the dispatch sequence.
MOVEMENT_ORDER: list[str] = [
    "autopsy",
    "trajectory_apply",   # NEW (05/05) — chiude loop A8+A15: legge ultima trajectory_evaluator decision e applica al seed prima di build_field
    "build_field",
    "agent",
    "bias_corrector",     # NEW (29/04) — A8 autologica interna: rewrite biased claims pre-falsifier
    "report_falsifier",   # asymmetric counter-pole, checks report internal coherence
    "bicono_extractor",   # NEW (29/04) — parse "Bicono della scoperta" section → structured JSON
    "validate_seed",
    "verify_assertions",
    "structural_check",
    "build_lab_data",
    "build_graph",
    "sync",
    "verify_endpoints",
    "refiner",
    "semantic_bridge",
    "refresh_detector",
    "seed_integrator",
    "trajectory_evaluator",
    "promotion_proposer",  # NEW (05/05) — G3 Fine B: estrae proposte di promozione finding → skill/hook/regola sistemica (no apply automatico, atto Approve operatore)
    "ssp_pipeline",        # NEW (01/05) — chiude scoperta → prodotto: crystallize+eligibility+designer+stage4
    "notify",
]

# Movements that abort the cycle if they fail.
CRITICAL_MOVEMENTS: set[str] = {"build_field", "agent"}

# Implementation registry — populated by registering each movement module.
# A None value means "stub: skip with a warning". Movements get implemented
# incrementally across Phase 1 commits.
MOVEMENTS: dict[str, Callable[[CycleContext], None] | None] = {
    name: None for name in MOVEMENT_ORDER
}


def register_movement(name: str, fn: Callable[[CycleContext], None]) -> None:
    """Register a movement implementation. Called by movement modules at import."""
    if name not in MOVEMENT_ORDER:
        raise ValueError(f"Unknown movement: {name}. Add it to MOVEMENT_ORDER first.")
    MOVEMENTS[name] = fn


# ─── Orchestrator ───────────────────────────────────────────────────


def run_cycle(domain: str) -> CycleContext:
    """Run one full cycle for the given domain.

    Steps:
      1. Load + validate domain config.
      2. Ensure per-domain data dirs exist.
      3. Load existing seed (if any) and last health snapshot.
      4. Dispatch the movements in order, handling failures per the policy:
         - Critical movements abort the cycle.
         - Non-critical failures log + continue.
         - Disabled movements (per config) are skipped.
      5. Return the final context (caller can serialize / inspect).
    """
    config = cfg.load_domain_config(domain)
    paths.ensure_domain_dirs(domain)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    data_dir = paths.domain_data_dir(domain)

    ctx = CycleContext(
        domain=domain,
        timestamp=timestamp,
        data_dir=data_dir,
        config=config,
    )

    # Load existing seed (best-effort — first cycle has no seed)
    seed_p = paths.seed_path(domain)
    if seed_p.exists():
        try:
            ctx.seed = json.loads(seed_p.read_text())
        except json.JSONDecodeError as e:
            logger.warning("seed.json corrupted, starting empty: %s", e)
            ctx.seed = {}

    # Load last health snapshot (autopsy will refresh it)
    health_p = paths.health_path(domain)
    if health_p.exists():
        try:
            ctx.health = json.loads(health_p.read_text())
        except json.JSONDecodeError:
            ctx.health = {}

    logger.info("Cycle starting: domain=%s timestamp=%s", domain, timestamp)
    cycle_t0 = time.time()

    for movement in MOVEMENT_ORDER:
        if not cfg.is_movement_enabled(config, movement):
            ctx.record_skipped(movement, "disabled in config")
            logger.info("[skip] %s — disabled in config", movement)
            continue

        impl = MOVEMENTS.get(movement)
        if impl is None:
            ctx.record_skipped(movement, "not yet implemented")
            logger.info("[skip] %s — not yet implemented (Phase 1 stub)", movement)
            continue

        t0 = time.time()
        try:
            impl(ctx)
            elapsed = time.time() - t0
            ctx.record_success(movement, duration_s=round(elapsed, 2))
            logger.info("[ok]   %s (%.1fs)", movement, elapsed)
        except Exception as e:
            elapsed = time.time() - t0
            tb = traceback.format_exc()
            err = f"{type(e).__name__}: {e}"
            ctx.record_error(movement, err)
            logger.error("[fail] %s (%.1fs): %s\n%s", movement, elapsed, err, tb)
            if movement in CRITICAL_MOVEMENTS:
                logger.error("Critical movement failed — aborting cycle.")
                break

    total_elapsed = time.time() - cycle_t0
    ctx.metrics["cycle_total_s"] = round(total_elapsed, 2)
    logger.info("Cycle ended: %.1fs, %d errors", total_elapsed, len(ctx.errors))

    # Trace dump — persiste sequenza movements + durations + status + metrics
    # in cycle_trace_<ts>.json (consumato da /api/domains/<d>/cycle_trace + UI timeline).
    try:
        trace = _build_cycle_trace(ctx, total_elapsed)
        trace_path = ctx.data_dir / f"cycle_trace_{timestamp}.json"
        trace_path.write_text(json.dumps(trace, indent=2))
        logger.info("Cycle trace written: %s", trace_path)
    except Exception as e:
        logger.warning("Failed to write cycle trace: %s", e)

    return ctx


def _build_cycle_trace(ctx: CycleContext, total_elapsed: float) -> dict:
    """Costruisce il trace serializzabile del cycle: sequenza movements
    con durata, status, metrics. Source of truth per /api/cycle_trace.
    """
    movements = []
    for name in MOVEMENT_ORDER:
        status = ctx.movement_status.get(name, "not_run")
        m_metrics = ctx.metrics.get(name, {}) or {}
        movements.append({
            "name": name,
            "status": status,
            "duration_s": m_metrics.get("duration_s"),
            "metrics": {k: v for k, v in m_metrics.items() if k != "duration_s"},
            "is_critical": name in CRITICAL_MOVEMENTS,
        })
    return {
        "schema_version": "0.1",
        "cycle_ts": ctx.timestamp,
        "domain": ctx.domain,
        "total_s": round(total_elapsed, 2),
        "n_movements": len(MOVEMENT_ORDER),
        "n_ok": sum(1 for m in movements if m["status"] == "ok"),
        "n_skipped": sum(1 for m in movements if str(m["status"]).startswith("skipped")),
        "n_pending": sum(1 for m in movements if str(m["status"]).startswith("pending")),
        "n_errors": len(ctx.errors),
        "errors": ctx.errors,
        "movements": movements,
        "ssp_pipeline_status": ctx.metrics.get("ssp_pipeline_status"),
        "cycle_total_s": ctx.metrics.get("cycle_total_s"),
    }


# ─── Movement imports — register implementations ────────────────────
# Each movement module calls register_movement() at import time. Modules
# are imported here so registration happens when lab_agent is loaded.
# Phase 1 commits add these one by one. Until imported, MOVEMENTS[name]
# remains None and the orchestrator skips with "not yet implemented".

from core import autopsy as _autopsy  # noqa: E402, F401
from core import build_field as _build_field  # noqa: E402, F401
from core import structural_check as _structural_check  # noqa: E402, F401
from core import refiner as _refiner  # noqa: E402, F401
from core import semantic_bridge as _semantic_bridge  # noqa: E402, F401
from core import lab_graph as _lab_graph  # noqa: E402, F401
from core import seed_integrator as _seed_integrator  # noqa: E402, F401
from core import refresh_detector as _refresh_detector  # noqa: E402, F401
from core import trajectory_evaluator as _trajectory_evaluator  # noqa: E402, F401
from core import agent as _agent  # noqa: E402, F401
from core import io_movements as _io_movements  # noqa: E402, F401
from core import report_falsifier as _report_falsifier  # noqa: E402, F401
from core import bias_corrector as _bias_corrector  # noqa: E402, F401  # NEW 29/04
from core import bicono_extractor as _bicono_extractor  # noqa: E402, F401  # NEW 29/04
from core import verify_assertions as _verify_assertions  # noqa: E402, F401  # NEW 29/04
from core import ssp_pipeline as _ssp_pipeline  # noqa: E402, F401  # NEW 01/05 — scoperta→prodotto
from core import trajectory_apply as _trajectory_apply  # noqa: E402, F401  # NEW 05/05 — chiude loop A8+A15
from core import promotion_proposer as _promotion_proposer  # noqa: E402, F401  # NEW 05/05 — G3 promotion pipeline
# 19 movements registered (added promotion_proposer 05/05 — extracts cycle finding → system rules/skills/hooks).
