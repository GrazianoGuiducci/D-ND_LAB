"""Movement 10 — refiner (originally lab_affinatore.py).

Reflective observer of the step (not the result). Corollary of Regressive
Repair, A8 applied: where the path produces unnecessary latency (works but
with friction), an observer separate from the producer analyzes the step
itself.

Runs AFTER the producer agent. Reads the session log + scientific report
+ health. Calls a separate LLM (short, reflective budget) to observe the
QUALITY of the path. Produces evolution_<ts>.md — structural proposals
about the system, not the experiment.

Degrade graceful: if LLM fails, the scientific report already exists. The
health file gets marked `affinatore_status=pending` so next cycle's
autopsy + build_field surface the missing reflection.

The prompt is universal (D-ND modus applied to the step) — kept in core/.
Domain-specific aspects of "the step" come from the cycle context that
the producer wrote.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from core import config as cfg
from core import llm_adapter, paths
from core.lab_agent import CycleContext, register_movement

logger = logging.getLogger(__name__)


REFINER_PROMPT = """You are the Refiner of the D-ND Lab. Your role is to observe the STEP, not the result.

The scientific report has already been written by the nightly producer. You do not evaluate it.
You observe the quality of the path: where it produced unnecessary latency, where it could
have inverted earlier, what relational condition was missing at the regressive node, what
possibilities emerge from the step itself.

Apply Regressive Repair: if you see a failure or friction, do NOT propose patches on the
present (raise timeout, retry, reactive guards = det=+1). Trace back to the node where the
condition was missing and propose there (det=-1).

Apply Refinement: evolutionary proposals enter as consecutio — they do not interrupt the
producer's cycle, they add direction for the next cycle.

Write a brief, clear evolution_report.md. Structure:

## Observation of the step
What the step did — as a trajectory, not as actions.

## Friction or unnecessary latency
Where the system spent energy without producing. If none: "none — clean step".

## Regressive node (if failure or friction)
Where the relational condition was missing. The fix lives there, not in the present of the bug.

## Emerging possibilities
New directions opened by the step — for the next cycle. Concrete, not generic.

## Consecutio
One line on where the next cycle could continue, if it chose to.

Be concise. Half a page is better than one page. Do not repeat the experiment — observe it.

---

Below is the context of the run just completed:

{context}

---

Write evolution_report.md:
"""


def refiner(ctx: CycleContext) -> None:
    """Run the refiner. Reads health from ctx + report file, calls LLM
    with reflective prompt, writes evolution_<ts>.md.

    Degrade graceful: any failure marks affinatore_status=pending in
    health.json and returns without raising.
    """
    params = cfg.movement_params(ctx.config, "refiner")
    max_turns = int(params.get("max_turns", 3))
    timeout_s = int(params.get("timeout_seconds", 300))

    # Find the run we're refining: the cycle that just produced (this cycle's
    # report or the previous run's, depending on when refiner is called)
    ts = _resolve_target_ts(ctx)
    if ts is None:
        logger.info("refiner: no target run found, skipping")
        ctx.metrics.setdefault("refiner", {}).update(skipped="no_target_run")
        return

    out_dir = paths.domain_data_dir(ctx.domain) / "evolution"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"evolution_{ts}.md"

    # Build context from the run's artifacts
    context = _build_context(ctx, ts)
    prompt = REFINER_PROMPT.format(context=context)

    # Call LLM with small budget (this is reflection, not generation).
    # Phase 1: llm_adapter.run_agent raises NotImplementedError → caught
    # below, marks pending. Phase 2: real call, writes evolution report.
    try:
        adapter_config = llm_adapter.AdapterConfig.from_env()
        adapter_config.max_turns = max_turns
        adapter_config.timeout_seconds = timeout_s

        result = llm_adapter.run_agent(
            system_prompt="",
            user_message=prompt,
            tools=None,  # reflection — no tools needed
            config=adapter_config,
        )
        if result.final_text and len(result.final_text) > 50:
            out_path.write_text(result.final_text)
            ctx.metrics.setdefault("refiner", {}).update(
                output_path=str(out_path),
                output_bytes=len(result.final_text.encode()),
                turns=result.turns,
            )
            logger.info("refiner: evolution report written → %s", out_path)
        else:
            _mark_pending(ctx, ts, reason="empty or too short output")

    except NotImplementedError:
        _mark_pending(ctx, ts, reason="llm_adapter not implemented (Phase 2)")
    except Exception as e:
        _mark_pending(ctx, ts, reason=f"refiner exception: {e}")


# ─── Internals ──────────────────────────────────────────────────────


def _resolve_target_ts(ctx: CycleContext) -> str | None:
    """Determine which run the refiner is observing.

    The refiner runs in the same cycle as the producer (movement 10 of 16).
    The current cycle's timestamp IS the run we just produced — so we
    refine ctx.timestamp.

    However: if the producer (movement 'agent') failed, there's nothing
    to refine yet. In that case we skip.
    """
    agent_status = ctx.movement_status.get("agent", "")
    if agent_status not in ("ok",):
        # Either skipped, errored, or not yet run — nothing to refine
        return None
    return ctx.timestamp


def _build_context(ctx: CycleContext, ts: str) -> str:
    """Assemble the context for the refiner: health + report + session stats."""
    parts: list[str] = []

    # Health (autopsy from this same cycle, written by movement 0)
    if ctx.health:
        parts.append("## Autopsy health\n\n```json\n" +
                     json.dumps(ctx.health, indent=2, ensure_ascii=False) +
                     "\n```\n")

    # Scientific report from this cycle
    report_md = paths.reports_dir(ctx.domain) / f"agent_{ts}.md"
    if report_md.exists():
        try:
            report_text = report_md.read_text()[:6000]
            parts.append(f"## Scientific report of the run\n\n{report_text}\n")
        except Exception:
            parts.append("## Scientific report\n\n_unreadable_\n")
    else:
        parts.append("## Scientific report\n\n_Not present — the run did not complete._\n")

    # Session stats summary
    stats = ctx.health.get("session_stats", {}) if ctx.health else {}
    if stats:
        parts.append(
            "## Session stats\n"
            f"- tool_use: {stats.get('tool_use')}\n"
            f"- tool_result: {stats.get('tool_result')}\n"
            f"- thinking: {stats.get('thinking')}\n"
            f"- text: {stats.get('text')}\n"
            f"- unanswered_tool_use: {stats.get('unanswered_tool_use')}\n"
            f"- duration: {stats.get('duration_s')}s\n"
        )
        last_text = stats.get("last_text")
        if last_text:
            parts.append(f"## Last text produced by the agent\n\n{last_text}\n")

    return "\n".join(parts)


def _mark_pending(ctx: CycleContext, ts: str, reason: str) -> None:
    """Mark refiner as pending in health.json — degrade graceful."""
    health_path = paths.health_path(ctx.domain)
    try:
        h = json.loads(health_path.read_text()) if health_path.exists() else {}
        h["affinatore_status"] = "pending"
        h["affinatore_reason"] = reason
        h["affinatore_ts"] = ts
        h["affinatore_marked_at"] = datetime.now(timezone.utc).isoformat()
        health_path.write_text(json.dumps(h, indent=2, ensure_ascii=False))
        ctx.health = h
    except Exception as e:
        logger.warning("could not mark refiner pending: %s", e)
    ctx.metrics.setdefault("refiner", {}).update(status="pending", reason=reason)
    logger.info("refiner: marked pending — %s", reason)


# ─── Movement registration ─────────────────────────────────────────

register_movement("refiner", refiner)
