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

import os
import logging
from contextlib import contextmanager
from typing import Any

from core import config as cfg
from core import llm_adapter, paths, skill_loader, tools
from core.lab_agent import CycleContext, register_movement

logger = logging.getLogger(__name__)


@contextmanager
def _temporary_env(updates: dict[str, str]):
    old = {key: os.environ.get(key) for key in updates}
    try:
        for key, value in updates.items():
            os.environ[key] = value
        yield
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


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


def _cli_provider_from_stop_reason(stop_reason: str) -> str | None:
    if stop_reason == "codex-cli-complete":
        return "codex-cli"
    if stop_reason == "claude-cli-complete":
        return "claude-cli"
    return None


def _write_repair_report(
    ctx: CycleContext,
    expected_report,
    result: llm_adapter.AgentResult,
    reason: str,
) -> None:
    """Write a deterministic no-claim report when the agent misses its contract.

    This keeps the cycle observable without pretending that a domain experiment
    succeeded. Downstream falsifier/seed movements can then absorb the runtime
    failure as a constraint instead of losing the cycle entirely.
    """
    expected_report.parent.mkdir(parents=True, exist_ok=True)
    text = f"""# Agent Runtime Repair Report — {ctx.domain} {ctx.timestamp}

**verdict**: CYCLE_REPAIR_NO_CLAIM

## Runtime Contract

The agent movement must produce this report file:

```text
{expected_report}
```

The provider completed or returned control, but the expected report artifact
was not present after the autonomous step.

## Repair Applied

The cycle wrote this deterministic repair report locally so the rest of the Lab
can observe, falsify and integrate the failure. This report is not a scientific
finding, not a domain result, not a promotion candidate and not evidence for any
claim in the domain.

## Provider Outcome

- stop_reason: `{result.stop_reason}`
- turns: `{result.turns}`
- tool_calls: `{len(result.tool_calls)}`
- duration_s: `{round(result.duration_s, 2)}`
- repair_reason: `{reason}`

## Constraint For Next Cycle

The next cycle should treat this as a runtime contract failure:

- the provider can complete without satisfying the side-effect contract;
- the field/prompt/tooling must make the report-write step non-optional;
- paid HTTP fallback must not be used automatically to compensate for a missing
  report side effect;
- if a domain experiment is needed, rerun from the same seed after the report
  contract is made observable.

## Bicono Section

- Root A: provider completed.
- Root B: report artifact missing.
- Singular: cycle observability, not domain knowledge.
- Invariant of passage: no claim is admitted without the expected artifact.
- Field of possibility: repair the movement contract before interpreting the
  domain.

## Seed Update Proposal

```json
{{
  "tipo": "vincolo",
  "id": "AGENT_REPORT_SIDE_EFFECT_CONTRACT",
  "claim": "The agent movement is not complete until agent_<timestamp>.md exists and is non-trivial; provider completion alone is not authority.",
  "intensita": 0.9,
  "porta": "runtime",
  "condensato_ref": "A8,A15"
}}
```
"""
    expected_report.write_text(text, encoding="utf-8")


def _final_text_looks_like_report(final_text: str, min_report_bytes: int) -> bool:
    text = (final_text or "").strip()
    if len(text.encode("utf-8")) < min(512, max(128, min_report_bytes // 2)):
        return False
    lower = text.lower()
    report_markers = (
        "# ",
        "verdict",
        "bicono",
        "claim",
        "experiment",
        "risult",
        "report",
    )
    return sum(1 for marker in report_markers if marker in lower) >= 2


def _materialize_final_text_report(
    *,
    ctx: CycleContext,
    expected_report,
    result: llm_adapter.AgentResult,
    min_report_bytes: int,
) -> bool:
    """Persist a provider's final answer when it is a report but not a file.

    This is the provider-agnostic bridge for API/local LLM installs: tools may
    be unavailable or the model may answer with the report body instead of
    writing the expected side-effect file. The Lab still requires the artifact,
    so it materializes only sufficiently report-shaped text and lets the
    downstream falsifier judge content quality.
    """
    if not _final_text_looks_like_report(result.final_text, min_report_bytes):
        return False
    expected_report.parent.mkdir(parents=True, exist_ok=True)
    text = result.final_text.strip()
    if not text.startswith("#"):
        text = f"# Agent Report — {ctx.domain} {ctx.timestamp}\n\n{text}"
    expected_report.write_text(text + "\n", encoding="utf-8")
    return True


def _attempt_same_cli_report_repair(
    *,
    ctx: CycleContext,
    result: llm_adapter.AgentResult,
    system_prompt: str,
    expected_report,
    report_written,
    adapter_config: llm_adapter.AdapterConfig,
) -> llm_adapter.AgentResult | None:
    provider = _cli_provider_from_stop_reason(result.stop_reason)
    if not provider:
        return None

    repair_config = llm_adapter.AdapterConfig(
        base_url=adapter_config.base_url,
        api_key=adapter_config.api_key,
        model=adapter_config.model,
        max_turns=3,
        timeout_seconds=min(adapter_config.timeout_seconds, 240),
        max_cost_usd=adapter_config.max_cost_usd,
    )
    repair_message = (
        f"Runtime repair for cycle {ctx.timestamp}. "
        f"You completed the previous agent step without writing the required report. "
        f"Do not run a new experiment. Write a concise report now to "
        f"{expected_report}. The report must state what was attempted, what is "
        f"verifiable from the current field, what is not a claim, and include a "
        f"Bicono section. This is a same-provider repair, not a fallback."
    )
    logger.warning(
        "agent: expected report missing after %s; attempting same-provider repair",
        provider,
    )
    with _temporary_env({
        "LLM_PROVIDER_CHAIN": provider,
        "LLM_FALLBACK_ON_CLI_SIDE_EFFECT_MISS": "",
    }):
        repaired = llm_adapter.run_agent(
            system_prompt=system_prompt,
            user_message=repair_message,
            tools=None,
            config=repair_config,
            early_stop=report_written,
        )
    return repaired


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

    user_message = (
        f"Run one experiment for cycle {ctx.timestamp}. "
        f"Pick ONE tension with high discriminating power. Formulate ONE question. "
        f"Run the experiment. Required artifact contract: write the report to "
        f"{expected_report}. The report file is the cycle output; provider "
        f"completion alone is not success. If your runtime cannot write files, "
        f"return the complete markdown report as your final answer and the Lab "
        f"will persist it to that path. Update {paths.seed_path(ctx.domain)} "
        f"with what you found only when you have evidence. Include the bicono "
        f"section in the report."
    )

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
    repair_applied = False
    repair_stop_reason = ""
    report_materialized_from_final_text = False
    if not report_written():
        if _materialize_final_text_report(
            ctx=ctx,
            expected_report=expected_report,
            result=result,
            min_report_bytes=min_report_bytes,
        ):
            report_materialized_from_final_text = True
        else:
            repaired = _attempt_same_cli_report_repair(
                ctx=ctx,
                result=result,
                system_prompt=system_prompt,
                expected_report=expected_report,
                report_written=report_written,
                adapter_config=adapter_config,
            )
            if repaired and report_written():
                repair_applied = True
                repair_stop_reason = repaired.stop_reason
                result = repaired
            elif repaired and _materialize_final_text_report(
                ctx=ctx,
                expected_report=expected_report,
                result=repaired,
                min_report_bytes=min_report_bytes,
            ):
                repair_applied = True
                repair_stop_reason = "same-provider-final-text-materialized"
                report_materialized_from_final_text = True
                result = repaired
            else:
                _write_repair_report(
                    ctx,
                    expected_report,
                    result,
                    reason="same-provider repair did not produce report" if repaired else "no same-provider repair available",
                )
                repair_applied = True
                repair_stop_reason = "deterministic-no-claim-report"

    if not expected_report.exists():
        raise RuntimeError(
            f"agent did not write report file at {expected_report} "
            f"(turns={result.turns}, stop_reason={result.stop_reason})"
        )

    ctx.report_path = expected_report
    ctx.metrics.setdefault("agent", {}).update(
        turns=result.turns,
        stop_reason=result.stop_reason,
        repair_applied=repair_applied,
        repair_stop_reason=repair_stop_reason,
        report_materialized_from_final_text=report_materialized_from_final_text,
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
