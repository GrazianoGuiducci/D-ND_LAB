"""LLM adapter — OpenAI-compatible client over any provider.

Single interface across providers (OpenRouter / OpenAI / Anthropic compat /
Ollama). Provider chosen via env vars (LLM_BASE_URL + LLM_API_KEY +
LLM_MODEL). No provider-specific code in core — quirks are absorbed here.

Architecture:
  - run_agent() does the multi-turn tool-use loop.
  - Tools are passed in as a list of (schema, callable) pairs registered
    by the caller. The schema is OpenAI tool format; the callable is what
    actually executes. See core.tools for the built-in set.
  - Cost tracking is best-effort: usage tokens come from the provider
    response, pricing is fetched lazily from OpenRouter /models endpoint
    if the base URL is OpenRouter (cached in-process for the cycle).
  - Safety: per-call timeout from config; whole-loop budget enforced
    by elapsed seconds; max_turns hard cap; max_cost hard cap.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# Imported lazily so the rest of the codebase can be loaded without openai installed
# (e.g. during scaffolding tests). run_agent() imports openai at call time.


@dataclass
class AgentResult:
    """Result of a single agent run (one cycle's reasoning + tool use)."""
    final_text: str
    turns: int
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    stop_reason: str = ""
    raw_messages: list[dict[str, Any]] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    cost_usd: float | None = None
    duration_s: float = 0.0


@dataclass
class AdapterConfig:
    """Loaded from env vars. Constructed once per cycle."""
    base_url: str
    api_key: str
    model: str
    max_turns: int = 25
    timeout_seconds: int = 1200
    max_cost_usd: float | None = None  # None = no cost cap

    @classmethod
    def from_env(cls) -> AdapterConfig:
        return cls(
            base_url=os.environ.get("LLM_BASE_URL", "https://openrouter.ai/api/v1"),
            api_key=os.environ.get("LLM_API_KEY", ""),
            model=os.environ.get("LLM_MODEL", ""),
            max_turns=int(os.environ.get("LLM_MAX_TURNS", "25")),
            timeout_seconds=int(os.environ.get("LLM_TIMEOUT_SECONDS", "1200")),
            max_cost_usd=_parse_optional_float(os.environ.get("LLM_MAX_COST_USD")),
        )

    def validate(self) -> None:
        """Raise ValueError if config is incomplete."""
        if not self.api_key:
            raise ValueError(
                "LLM_API_KEY is empty. Set it in .env (see .env.example)."
            )
        if not self.model:
            raise ValueError(
                "LLM_MODEL is empty. Set it in .env. "
                "See .env.example for current model recommendations, "
                "or browse available models at the LLM_BASE_URL provider."
            )


# ---------------------------------------------------------------------------
# CLI provider chain (refactor 01/05): replicare in D-ND_LAB il pattern di
# MM_D-ND lab_agent.sh — claude CLI subprocess primary, codex CLI fallback,
# OpenRouter HTTP fallback. Per uso personale interno (subscription OAuth =
# gratis, tool use nativo). Per chi installa D-ND_LAB altrove: configurabile
# tramite LLM_PROVIDER_CHAIN env var. Default = "claude-cli,codex-cli,openrouter".
# ---------------------------------------------------------------------------


# Pre-flight cache (refactor 04/05 — speculare a lab_agent.sh):
# evita timeout intero per ogni chiamata quando un provider è auth-failed.
# Reset a None per forzare ricontrollo (es. dopo codex login interattivo).
_CODEX_PREFLIGHT_OK: bool | None = None
_CLAUDE_PREFLIGHT_OK: bool | None = None


def _claude_preflight_check() -> bool:
    """30s ping a claude per detect 401/hung silenzioso. Cached."""
    global _CLAUDE_PREFLIGHT_OK
    if _CLAUDE_PREFLIGHT_OK is not None:
        return _CLAUDE_PREFLIGHT_OK
    if not shutil.which("claude"):
        _CLAUDE_PREFLIGHT_OK = False
        return False
    try:
        r = subprocess.run(
            ["claude", "--print", "Reply only: ok"],
            capture_output=True, text=True, timeout=30,
        )
        out = (r.stdout or "") + (r.stderr or "")
        if any(s.lower() in out.lower() for s in (
            "401", "unauthorized", "sign in", "please log in", "invalid_grant",
        )):
            _CLAUDE_PREFLIGHT_OK = False
            return False
        if r.returncode == 0 and not (r.stdout or "").strip():
            _CLAUDE_PREFLIGHT_OK = False
            return False
        _CLAUDE_PREFLIGHT_OK = True
        return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        _CLAUDE_PREFLIGHT_OK = False
        return False


def _codex_preflight_check() -> bool:
    """30s ping a codex per detect 401/refresh_token_reused. Cached."""
    global _CODEX_PREFLIGHT_OK
    if _CODEX_PREFLIGHT_OK is not None:
        return _CODEX_PREFLIGHT_OK
    if not shutil.which("codex"):
        _CODEX_PREFLIGHT_OK = False
        return False
    try:
        r = subprocess.run(
            ["codex", "exec", "--skip-git-repo-check", "echo ok"],
            capture_output=True, text=True, timeout=30,
        )
        out = (r.stdout or "") + (r.stderr or "")
        if any(s in out for s in (
            "401 Unauthorized", "refresh_token_reused",
            "token_invalidated", "sign in again",
        )):
            _CODEX_PREFLIGHT_OK = False
            return False
        _CODEX_PREFLIGHT_OK = True
        return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        _CODEX_PREFLIGHT_OK = False
        return False


def _run_via_claude_cli(
    system_prompt: str,
    user_message: str,
    config: AdapterConfig,
) -> AgentResult:
    """Provider claude CLI subprocess.

    Pattern identico a /opt/MM_D-ND/tools/lab_agent.sh — claude CLI in
    OAuth subscription mode (gratis). Tool use nativo (Bash, Read, Write,
    Edit, ...) gestito internamente dal CLI.

    NOTA: tool schemas custom passati a run_agent NON vengono registrati
    qui — claude CLI usa i suoi builtin. Per il lab cycle questo va bene
    (i movement usano filesystem / python_exec / shell_exec, tutti coperti
    dai tools nativi).
    """
    if not shutil.which("claude"):
        raise RuntimeError("claude CLI not found in PATH")
    if not _claude_preflight_check():
        raise RuntimeError("claude CLI pre-flight failed (auth/hung)")

    full_prompt = (
        f"{system_prompt}\n\n---\n\n{user_message}" if system_prompt else user_message
    )

    args = [
        "claude",
        "-p", full_prompt,
        "--max-turns", str(config.max_turns),
        "--permission-mode", "acceptEdits",
    ]

    t0 = time.time()
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=config.timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise TimeoutError(
            f"claude CLI exceeded {config.timeout_seconds}s"
        ) from e

    duration = time.time() - t0

    if result.returncode != 0:
        stderr_preview = (result.stderr or "")[:500]
        raise RuntimeError(
            f"claude CLI exit {result.returncode}: {stderr_preview}"
        )

    return AgentResult(
        final_text=result.stdout or "",
        turns=0,  # gestito internamente dal CLI
        tool_calls=[],  # non esposto via subprocess
        stop_reason="claude-cli-complete",
        duration_s=duration,
    )


def _run_via_codex_cli(
    system_prompt: str,
    user_message: str,
    config: AdapterConfig,
) -> AgentResult:
    """Provider codex CLI subprocess.

    Pattern simile a /opt/THIA/services/tm3_bridge.js — codex CLI con OAuth
    ChatGPT account (subscription, no paid API key richiesta). Stesso
    tradeoff di claude-cli su tool schemas custom.
    """
    if not shutil.which("codex"):
        raise RuntimeError("codex CLI not found in PATH")
    if not _codex_preflight_check():
        raise RuntimeError("codex CLI pre-flight failed (auth: refresh_token_reused?)")

    full_prompt = (
        f"{system_prompt}\n\n---\n\n{user_message}" if system_prompt else user_message
    )

    # codex CLI accepts the prompt via stdin (-) for non-interactive mode
    args = ["codex", "exec", "-", "--non-interactive"]

    t0 = time.time()
    try:
        result = subprocess.run(
            args,
            input=full_prompt,
            capture_output=True,
            text=True,
            timeout=config.timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise TimeoutError(
            f"codex CLI exceeded {config.timeout_seconds}s"
        ) from e

    duration = time.time() - t0

    if result.returncode != 0:
        stderr_preview = (result.stderr or "")[:500]
        raise RuntimeError(
            f"codex CLI exit {result.returncode}: {stderr_preview}"
        )

    return AgentResult(
        final_text=result.stdout or "",
        turns=0,
        tool_calls=[],
        stop_reason="codex-cli-complete",
        duration_s=duration,
    )


# Tool registry passed to run_agent. Each entry:
#   {
#     "schema": {...},        # OpenAI tools schema
#     "fn": callable,          # called with parsed args dict, returns string
#   }
ToolEntry = dict[str, Any]


def run_agent(
    system_prompt: str,
    user_message: str,
    tools: list[ToolEntry] | None = None,
    config: AdapterConfig | None = None,
    early_stop: Callable[[], bool] | None = None,
) -> AgentResult:
    """Run the agent for one cycle. Multi-turn tool-use loop.

    Args:
        early_stop: optional callable. After each turn (post tool dispatch),
            if early_stop() returns True, the loop terminates with the most
            recent assistant text as final_text. Useful when the agent's
            output is in a side-effect file (e.g. report.md) and continued
            tool calls are wasteful exploration past the goal.

    Returns AgentResult with final text, traces, usage, cost.

    Raises:
        ValueError: missing config / API key.
        TimeoutError: total elapsed > config.timeout_seconds.
        RuntimeError: max_turns reached without final answer; or budget cap hit.
    """
    config = config or AdapterConfig.from_env()

    # Provider chain (refactor 01/05): se LLM_PROVIDER_CHAIN configurata,
    # prova in ordine ogni provider. Default chain: claude-cli → codex-cli
    # → openrouter (= comportamento legacy se i CLI non sono disponibili).
    # Per disabilitare: LLM_PROVIDER_CHAIN=openrouter (solo HTTP).
    chain_str = os.environ.get("LLM_PROVIDER_CHAIN", "codex-cli,claude-cli,openrouter")
    chain = [p.strip().lower() for p in chain_str.split(",") if p.strip()]

    # CLI providers (claude-cli, codex-cli) gestiscono tool use nativamente
    # via builtin, NON via tool_schemas custom. Sono adatti per i lab cycle
    # che usano filesystem/python_exec/shell_exec. Per use case che richiedono
    # tool schemas custom registrati, usare openrouter/openai diretto.
    last_err: Exception | None = None
    cli_providers = {"claude-cli", "codex-cli"}
    has_cli_in_chain = any(p in cli_providers for p in chain)

    if has_cli_in_chain:
        for provider in chain:
            if provider == "claude-cli":
                try:
                    logger.info("provider chain: trying claude-cli")
                    return _run_via_claude_cli(system_prompt, user_message, config)
                except (RuntimeError, TimeoutError) as e:
                    logger.warning(f"claude-cli failed: {e} — falling back")
                    last_err = e
                    continue
            if provider == "codex-cli":
                try:
                    logger.info("provider chain: trying codex-cli")
                    return _run_via_codex_cli(system_prompt, user_message, config)
                except (RuntimeError, TimeoutError) as e:
                    logger.warning(f"codex-cli failed: {e} — falling back")
                    last_err = e
                    continue
            if provider in ("openrouter", "openai"):
                # falls through to OpenAI-compat HTTP path below
                logger.info(f"provider chain: falling through to {provider} (HTTP)")
                break

    # Bridge route for bare (no-tools) calls — uses operator subscription
    # (codex/claude CLI via THIA tm3_bridge), zero marginal cost.
    # Activated by env vars THIA_LLM_BASE_URL + THIA_LLM_TOKEN. Only applies
    # when tools is None (bridge is bare-mode, no tool support).
    # Aggiunto 29/04: TM7 ha messo la stessa catena codex→claude→openrouter
    # in piu' punti del sito. Riuso del pattern per i movement bare del demo
    # (bias_corrector, report_falsifier, refiner, trajectory_evaluator).
    bridge_url = os.environ.get("THIA_LLM_BASE_URL", "").rstrip("/")
    bridge_token = os.environ.get("THIA_LLM_TOKEN", "")
    use_bridge = bool(tools is None and bridge_url and bridge_token)

    if use_bridge:
        effective_base_url = bridge_url
        effective_api_key = bridge_token  # placeholder, real auth via header
        default_headers = {"X-THIA-Token": bridge_token}
    else:
        effective_base_url = config.base_url
        effective_api_key = config.api_key
        default_headers = None
        # Validate only when NOT using bridge (bridge has its own auth path)
        config.validate()

    # Lazy import — keeps openai out of import graph for scaffolding.
    try:
        import openai
    except ImportError as e:
        raise RuntimeError(
            "openai package required. Install with: pip install openai"
        ) from e

    client_kwargs: dict[str, Any] = {
        "base_url": effective_base_url,
        "api_key": effective_api_key or "x",  # SDK requires non-empty key
    }
    if default_headers:
        client_kwargs["default_headers"] = default_headers
    client = openai.OpenAI(**client_kwargs)

    messages: list[dict[str, Any]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_message})

    tool_schemas: list[dict[str, Any]] = []
    tool_fns: dict[str, Callable[..., str]] = {}
    if tools:
        for entry in tools:
            schema = entry.get("schema")
            fn = entry.get("fn")
            if schema and fn:
                tool_schemas.append(schema)
                tool_fns[schema["function"]["name"]] = fn

    cumulative_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    tool_call_log: list[dict[str, Any]] = []
    final_text = ""
    stop_reason = ""
    turns = 0
    cycle_t0 = time.time()

    # Cost lookup (lazy, cached per process)
    pricing_cache = _get_pricing_cache(config)

    for turn in range(config.max_turns):
        turns = turn + 1
        elapsed = time.time() - cycle_t0
        if elapsed > config.timeout_seconds:
            raise TimeoutError(
                f"Agent exceeded budget: {elapsed:.0f}s > {config.timeout_seconds}s"
            )

        # Build request kwargs
        kwargs: dict[str, Any] = {
            "model": config.model,
            "messages": messages,
            "timeout": max(30.0, config.timeout_seconds - elapsed),
        }
        if tool_schemas:
            kwargs["tools"] = tool_schemas
            kwargs["tool_choice"] = "auto"

        try:
            response = client.chat.completions.create(**kwargs)
        except openai.APIError as e:
            raise RuntimeError(f"LLM API error on turn {turns}: {e}") from e

        # Track usage + cost
        if response.usage:
            cumulative_usage["prompt_tokens"] += response.usage.prompt_tokens or 0
            cumulative_usage["completion_tokens"] += response.usage.completion_tokens or 0
            cumulative_usage["total_tokens"] += response.usage.total_tokens or 0
            current_cost = _compute_cost(cumulative_usage, config.model, pricing_cache)
            if config.max_cost_usd and current_cost and current_cost > config.max_cost_usd:
                raise RuntimeError(
                    f"Cost cap exceeded: ${current_cost:.4f} > ${config.max_cost_usd}"
                )

        choice = response.choices[0]
        msg = choice.message
        stop_reason = choice.finish_reason or ""

        # Append assistant message (preserve tool_calls if present)
        assistant_msg: dict[str, Any] = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ]
        # OpenRouter reasoning models (DeepSeek thinking, Anthropic extended,
        # Gemini 3 thinking, etc.): preserve reasoning_details unmodified
        # when sending back in multi-turn. Per OpenRouter docs:
        # "Preserve the complete reasoning_details when passing back"
        # https://openrouter.ai/docs/guides/best-practices/reasoning-tokens
        reasoning_details = getattr(msg, "reasoning_details", None)
        if reasoning_details:
            assistant_msg["reasoning_details"] = reasoning_details
        # Some providers also use a plain `reasoning` string field
        reasoning = getattr(msg, "reasoning", None)
        if reasoning and not reasoning_details:
            assistant_msg["reasoning"] = reasoning
        messages.append(assistant_msg)

        if not msg.tool_calls:
            # Final answer
            final_text = msg.content or ""
            break

        # Dispatch tool calls
        for tc in msg.tool_calls:
            tool_name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            tool_call_log.append({
                "turn": turns,
                "tool": tool_name,
                "args_preview": str(args)[:200],
            })

            fn = tool_fns.get(tool_name)
            if fn is None:
                tool_result = f"ERROR: tool '{tool_name}' not registered"
            else:
                try:
                    tool_result = fn(**args)
                except TypeError as e:
                    tool_result = f"ERROR: bad args for {tool_name}: {e}"
                except Exception as e:
                    tool_result = f"ERROR: {tool_name} raised: {e}"

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": str(tool_result)[:50000],
            })

        # Early stop check: after dispatching this turn's tools, did the
        # agent achieve its side-effect goal (e.g. wrote the report file)?
        # Some agents continue to validate/explore past the goal — we let
        # the caller decide that further turns are wasteful.
        if early_stop and early_stop():
            final_text = msg.content or "[completed via side-effect; no final assistant text]"
            stop_reason = "early_stop"
            break
    else:
        # Loop exhausted without final answer
        raise RuntimeError(f"max_turns ({config.max_turns}) reached without final answer")

    duration = time.time() - cycle_t0
    cost = _compute_cost(cumulative_usage, config.model, pricing_cache)

    return AgentResult(
        final_text=final_text,
        turns=turns,
        tool_calls=tool_call_log,
        stop_reason=stop_reason,
        raw_messages=messages,
        usage=cumulative_usage,
        cost_usd=cost,
        duration_s=round(duration, 2),
    )


# ─── Cost tracking ───────────────────────────────────────────────────


def _parse_optional_float(s: str | None) -> float | None:
    if s is None or s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


_PRICING_CACHE: dict[str, dict[str, float]] = {}


def _get_pricing_cache(config: AdapterConfig) -> dict[str, dict[str, float]]:
    """Lazy lookup of pricing from OpenRouter /models endpoint.

    Returns a dict {model_id: {"prompt": $/token, "completion": $/token}}.
    Only fetches once per process. If base_url is not OpenRouter, returns
    an empty dict (cost will be None).
    """
    global _PRICING_CACHE
    if _PRICING_CACHE:
        return _PRICING_CACHE

    if "openrouter.ai" not in config.base_url:
        _PRICING_CACHE = {"_unknown": {}}  # marker so we don't retry
        return _PRICING_CACHE

    try:
        with urllib.request.urlopen(
            f"{config.base_url}/models", timeout=10
        ) as r:
            data = json.loads(r.read())
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as e:
        logger.warning("pricing fetch failed: %s", e)
        _PRICING_CACHE = {"_unknown": {}}
        return _PRICING_CACHE

    for m in data.get("data", []):
        mid = m.get("id")
        pricing = m.get("pricing", {})
        if mid and pricing:
            try:
                _PRICING_CACHE[mid] = {
                    "prompt": float(pricing.get("prompt", 0) or 0),
                    "completion": float(pricing.get("completion", 0) or 0),
                }
            except (ValueError, TypeError):
                continue
    return _PRICING_CACHE


def _compute_cost(
    usage: dict[str, int],
    model: str,
    pricing_cache: dict[str, dict[str, float]],
) -> float | None:
    """USD cost for the cumulative usage. None if pricing unavailable."""
    pricing = pricing_cache.get(model)
    if not pricing:
        return None
    return (
        usage.get("prompt_tokens", 0) * pricing.get("prompt", 0)
        + usage.get("completion_tokens", 0) * pricing.get("completion", 0)
    )


def estimate_cost(result: AgentResult, config: AdapterConfig) -> float | None:
    """Returns the cost stored in the result, or recomputes if missing."""
    if result.cost_usd is not None:
        return result.cost_usd
    pricing = _get_pricing_cache(config)
    return _compute_cost(result.usage, config.model, pricing)
