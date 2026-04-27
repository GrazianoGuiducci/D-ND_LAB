"""Lab agent — 13-movement orchestrator.

Phase 0: skeleton only. Real implementation in Phase 1 (refactor from
the original /opt/MM_D-ND/tools/lab_agent.sh + Python tools).

The 13 movements (in order):
   0.  autopsy            — observe previous run, identify regressive node
   1.  build_field        — assemble agent_field_live.md (tensions + context)
   2.  agent              — autonomous LLM cycle: pick one tension, run experiment
   3.  validate_seed      — integrity check + restore from backup if corrupted
   4.  verify_assertions  — run condensate claims, mark PASS/FAIL
   5.  structural_check   — scan touched code, inject META tensions on anti-patterns
   6.  build_lab_data     — snapshot piano + tensions + last report
   7.  build_graph        — knowledge graph nodes/edges
   8.  sync               — propagate state (filesystem / external endpoints)
   9.  verify_endpoints   — health-check downstream consumers
   10. refiner            — second LLM observes the step (not the result) — A8
   11. semantic_bridge    — map findings to domain category mapping
   12. refresh_detector   — event-driven regen of derivative views
   13. seed_integrator    — crystallize: tensions → filtered → direction rotates
   14. trajectory_eval    — separate LLM decides STOP/NEXT/REDESIGN/etc (log-only)
   15. notify             — webhook to operator

Pattern f(f(x)): movements 0, 5, 10, 14 are reflective — the system observes
the system. Movement 13 (seed_integrator) closes the autopoietic loop A5.

Each movement is implemented as a small module/function. The orchestrator
dispatches them in order and handles graceful degradation: if a non-critical
movement fails, the cycle continues. Critical failures (movement 2 — agent)
abort the cycle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


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


def run_cycle(domain: str, config_path: Path) -> CycleContext:
    """Run one full cycle for the given domain.

    Phase 0: NotImplementedError. Phase 1 implementation will:
      1. Load config from domains/<domain>/config.json (validate against schema).
      2. Construct CycleContext with paths, timestamp, seed loaded.
      3. Dispatch the 13 movements in order.
      4. Each movement reads ctx, mutates it, returns. Errors are captured
         in ctx.errors but only critical ones (agent failure) abort.
      5. Return final ctx for inspection / serialization.

    See lab_agent.sh in the original /opt/MM_D-ND/tools/ for reference,
    but rewrite as Python (no subprocess to claude — uses llm_adapter).
    """
    raise NotImplementedError("Phase 1 — port from /opt/MM_D-ND/tools/lab_agent.sh")


# ─── Movement registry — populated in Phase 1 ────────────────────────
# Each movement is a callable: (ctx: CycleContext) -> None
# Registered here so domains can override / disable specific movements
# via their config.json (movements section in config.schema.json).

MOVEMENTS: dict[str, Any] = {
    "autopsy": None,
    "build_field": None,
    "agent": None,
    "validate_seed": None,
    "verify_assertions": None,
    "structural_check": None,
    "build_lab_data": None,
    "build_graph": None,
    "sync": None,
    "verify_endpoints": None,
    "refiner": None,
    "semantic_bridge": None,
    "refresh_detector": None,
    "seed_integrator": None,
    "trajectory_evaluator": None,
    "notify": None,
}
