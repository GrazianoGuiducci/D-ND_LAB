"""LLM adapter — OpenAI-compatible client over any provider.

Phase 0: skeleton only. Real implementation in Phase 2.

Design intent:
  - Single interface across providers (OpenRouter / OpenAI / Anthropic compat / Ollama).
  - Provider chosen via env vars (LLM_BASE_URL + LLM_API_KEY + LLM_MODEL).
  - Tool calling via MCP (Phase 2). Built-in tools fallback for Phase 1.
  - No provider-specific code in core/. If a provider needs a quirk,
    handle it inside this module behind the unified interface.

The lab agent uses run_agent() — given a system prompt, user message, and
a list of tools, it returns the final assistant message (after multi-turn
tool use loop) and a structured trace.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentResult:
    """Result of a single agent run (one cycle's reasoning + tool use)."""
    final_text: str
    turns: int
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    stop_reason: str = ""
    raw_messages: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class AdapterConfig:
    """Loaded from env vars. Constructed once per cycle."""
    base_url: str
    api_key: str
    model: str
    max_turns: int = 25
    timeout_seconds: int = 1200

    @classmethod
    def from_env(cls) -> AdapterConfig:
        """Construct from environment variables.

        LLM_MODEL is required and has no in-code default — provider model
        names change (deprecations, new releases). The recommended starting
        model lives in .env.example, where it can be updated without a code
        change. Phase 2 run_agent() validates that LLM_MODEL is non-empty.
        """
        return cls(
            base_url=os.environ.get("LLM_BASE_URL", "https://openrouter.ai/api/v1"),
            api_key=os.environ.get("LLM_API_KEY", ""),
            model=os.environ.get("LLM_MODEL", ""),
            max_turns=int(os.environ.get("LLM_MAX_TURNS", "25")),
            timeout_seconds=int(os.environ.get("LLM_TIMEOUT_SECONDS", "1200")),
        )


def run_agent(
    system_prompt: str,
    user_message: str,
    tools: list[dict[str, Any]] | None = None,
    config: AdapterConfig | None = None,
) -> AgentResult:
    """Run the lab agent for one cycle.

    Phase 0: NotImplementedError. Phase 2 implementation will:
      1. Initialize OpenAI client with config.base_url + config.api_key.
      2. Construct messages list with system + user.
      3. Loop: call chat.completions.create(model=..., tools=..., stream=...).
         a. If finish_reason == 'tool_calls': dispatch each tool call,
            append result to messages, continue.
         b. Else: return final assistant text.
      4. Hard limit at config.max_turns.
      5. Hard timeout at config.timeout_seconds (whole loop, not per call).

    Returns AgentResult with text + traces for the lab post-processing.
    """
    raise NotImplementedError("Phase 2 — see core/llm_adapter.py docstring for spec.")


def estimate_cost(result: AgentResult, config: AdapterConfig) -> float | None:
    """Estimate cost of a cycle in USD. Optional — None if pricing unavailable.

    Phase 2: query provider's pricing API or read from a cached map updated
    on lab boot (so we don't hardcode pricing in source — pricing changes).
    """
    return None
