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
    config.validate()

    # Lazy import — keeps openai out of import graph for scaffolding.
    try:
        import openai
    except ImportError as e:
        raise RuntimeError(
            "openai package required. Install with: pip install openai"
        ) from e

    client = openai.OpenAI(base_url=config.base_url, api_key=config.api_key)

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
