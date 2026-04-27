"""Movement 2 — agent.

The autonomous LLM cycle. Reads agent_field_live.md (built by movement 1),
makes ONE choice, runs ONE experiment, writes the report file.

Phase 1: stub — calls llm_adapter.run_agent() which raises
NotImplementedError. Movement degrades by recording the failure in
ctx.errors. Since 'agent' is in CRITICAL_MOVEMENTS, the orchestrator
aborts the cycle when this fails.

Phase 2 implementation will:
  1. Read field_live_path(domain) — system message
  2. Read domain_context_path(domain) — system message
  3. Construct user message: "Run one experiment for cycle {timestamp}"
  4. tools=[filesystem, python_exec, shell_exec] via MCP servers
  5. llm_adapter.run_agent(...) with timeout = config.timeout_seconds
  6. Capture stdout to <reports>/agent_{ts}_raw.log
  7. Verify report file <reports>/agent_{ts}.md was written by the agent
  8. ctx.report_path = path; ctx.metrics["agent"]["turns"] = result.turns
"""

from __future__ import annotations

import logging
from typing import Any

from core import config as cfg
from core import llm_adapter, paths, tools
from core.lab_agent import CycleContext, register_movement

logger = logging.getLogger(__name__)


def agent(ctx: CycleContext) -> None:
    """Run the autonomous LLM cycle.

    Phase 1: raises NotImplementedError via llm_adapter.run_agent.
    The orchestrator catches; cycle aborts (agent is CRITICAL).
    """
    params = cfg.movement_params(ctx.config, "agent")

    field_path = paths.field_live_path(ctx.domain)
    context_path = paths.domain_context_path(ctx.domain)
    if not field_path.exists():
        raise RuntimeError(f"agent_field_live.md missing at {field_path} — build_field must run first")

    system_prompt_parts: list[str] = []
    if context_path.exists():
        system_prompt_parts.append(context_path.read_text())
    system_prompt_parts.append(field_path.read_text())
    system_prompt = "\n\n---\n\n".join(system_prompt_parts)

    user_message = (
        f"Run one experiment for cycle {ctx.timestamp}. "
        f"Pick ONE tension with high discriminating power. Formulate ONE question. "
        f"Run the experiment. Write the report to "
        f"{paths.reports_dir(ctx.domain)}/agent_{ctx.timestamp}.md. "
        f"Update {paths.seed_path(ctx.domain)} with what you found. "
        f"Include the bicono section in the report."
    )

    adapter_config = llm_adapter.AdapterConfig.from_env()

    # Default tool set: filesystem ops + python_exec + bash_exec, sandboxed
    # to the domain's data dir + read-only access to domain dir.
    tool_set = tools.build_default_tools(ctx.domain)

    result = llm_adapter.run_agent(
        system_prompt=system_prompt,
        user_message=user_message,
        tools=tool_set,
        config=adapter_config,
    )

    # Verify the agent wrote the expected report file
    expected_report = paths.reports_dir(ctx.domain) / f"agent_{ctx.timestamp}.md"
    if not expected_report.exists():
        raise RuntimeError(
            f"agent did not write report file at {expected_report} "
            f"(turns={result.turns}, stop_reason={result.stop_reason})"
        )

    ctx.report_path = expected_report
    ctx.metrics.setdefault("agent", {}).update(
        turns=result.turns,
        stop_reason=result.stop_reason,
        tool_calls=len(result.tool_calls),
        usage=result.usage,
        cost_usd=result.cost_usd,
        duration_s=result.duration_s,
    )
    logger.info(
        "agent: %d turns, %d tool calls, %d total tokens, $%s, report → %s",
        result.turns,
        len(result.tool_calls),
        result.usage.get("total_tokens", 0),
        f"{result.cost_usd:.4f}" if result.cost_usd is not None else "?",
        expected_report,
    )


register_movement("agent", agent)
