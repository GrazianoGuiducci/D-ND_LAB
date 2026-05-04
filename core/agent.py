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
from core import llm_adapter, paths, skill_loader, tools
from core.lab_agent import CycleContext, register_movement

logger = logging.getLogger(__name__)


def _build_mml_section(domain: str) -> str:
    """Build a system_prompt section from the lab MML (mml.json).

    Reads skills_attive + tools_custom and renders a human-readable
    section telling the agent which skills/tools the lab declares as
    pertinent for its modus, with trigger and rationale. Tools custom
    are exposed as shell-invocable scripts (the agent uses shell_exec
    to run them — no MCP registration needed).

    Returns empty string if mml.json missing or malformed (silent).
    The cycle still works without MML — same as pre-2.A.7 behaviour.
    """
    try:
        skills = skill_loader.load_skills_for_lab(domain, runtime="auto")
    except Exception as e:
        logger.warning("MML wire skipped — skill_loader failed: %s", e)
        return ""

    mml_raw = skill_loader._read_mml(domain) or {}
    tools_custom = mml_raw.get("tools_custom", []) or []

    if not skills and not tools_custom:
        return ""

    lines: list[str] = ["## Lab MML — skills attive e tools custom", ""]

    if skills:
        lines.append(
            "Il MML del lab dichiara le skill seguenti come pertinenti al "
            "modus del lab. Applica ognuna al trigger indicato durante il "
            "cycle. Le skill vivono nei loro file sorgente — segui il "
            "rationale, non riformulare."
        )
        lines.append("")
        for s in skills:
            lines.append(f"- **{s.name}** (`{s.source_kind}`)")
            if s.trigger:
                lines.append(f"  - trigger: {s.trigger}")
            if s.rationale:
                lines.append(f"  - rationale: {s.rationale}")
            lines.append(f"  - source: `{s.source_path}`")
        lines.append("")

    if tools_custom:
        domain_dir = skill_loader.DOMAINS_DIR / domain
        lines.append(
            "Tools custom del lab (script CLI eseguibili via "
            "`shell_exec`, non tool MCP — l'agent li invoca direttamente "
            "quando serve evidenza eseguita anziché discorso):"
        )
        lines.append("")
        for t in tools_custom:
            name = t.get("name", "?")
            rel_path = t.get("path", "?")
            desc = t.get("description", "")
            full_path = domain_dir / rel_path
            lines.append(f"- **{name}** — {desc}")
            lines.append(f"  - path: `{full_path}`")
            lines.append(f"  - invoke: `python3 {full_path} [args]`")
        lines.append("")

    return "\n".join(lines).rstrip()


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
    mml_section = _build_mml_section(ctx.domain)
    if mml_section:
        system_prompt_parts.append(mml_section)
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
    # cycle_ts triggers auto-persistence of run_python/run_bash calls to
    # data/{domain}/artifacts/{cycle_ts}/ — read by the falsifier movement.
    tool_set = tools.build_default_tools(ctx.domain, cycle_ts=ctx.timestamp)

    # Domain-declared tools: each entry in config.tools with type="domain"
    # imports its module and calls module.build(domain) to get a ToolEntry.
    # This lets domains expose specialized tools (archive_search, voice_check,
    # m_spectro, etc.) without polluting core.
    #
    # Two declaration styles supported:
    #   1. Dotted module path ("domains.physics.tools.m_spectro") — Python
    #      module exposing build(domain) → MCP-style tool. Loaded into tool_set.
    #   2. Posix path ending in .py ("tools/exp_incident_regressor.py") —
    #      standalone CLI script. NOT registered as MCP tool — the agent
    #      invokes it via shell_exec, surfaced in the MML section above.
    for tool_decl in ctx.config.get("tools", []):
        if tool_decl.get("type") != "domain":
            continue
        module_name = tool_decl.get("module")
        if not module_name:
            logger.warning("domain tool without module: %s", tool_decl)
            continue
        # Style 2: standalone script — let the agent invoke via shell_exec.
        if "/" in module_name or module_name.endswith(".py"):
            logger.info(
                "domain tool %s is a standalone script (%s) — surfaced via MML, "
                "invoked by agent via shell_exec",
                tool_decl.get("name"), module_name,
            )
            continue
        # Style 1: dotted module — import and register as MCP tool.
        try:
            import importlib
            mod = importlib.import_module(module_name)
            if hasattr(mod, "build"):
                entry = mod.build(ctx.domain)
                if entry and entry.get("schema") and entry.get("fn"):
                    tool_set.append(entry)
                    logger.info("loaded domain tool: %s", tool_decl.get("name"))
            else:
                logger.warning("domain tool module %s has no build(domain) function", module_name)
        except ImportError as e:
            logger.warning("domain tool %s not importable: %s", module_name, e)
        except Exception as e:
            logger.warning("domain tool %s build() failed: %s", module_name, e)

    # Early stop: when the report file is written and not trivially short,
    # the agent has achieved the cycle goal. Continuing to call tools past
    # this point is exploration, not output — we cap it. Threshold 1 KB
    # avoids stopping on a stub/empty file.
    expected_report = paths.reports_dir(ctx.domain) / f"agent_{ctx.timestamp}.md"
    min_report_bytes = int(params.get("min_report_bytes", 1024))

    def report_written() -> bool:
        return expected_report.exists() and expected_report.stat().st_size >= min_report_bytes

    result = llm_adapter.run_agent(
        system_prompt=system_prompt,
        user_message=user_message,
        tools=tool_set,
        config=adapter_config,
        early_stop=report_written,
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
