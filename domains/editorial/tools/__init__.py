"""Editorial domain tools — exposed to the agent during cycles.

Each tool module exposes build(domain) -> ToolEntry, which the orchestrator
imports and registers alongside the core built-in tools.
"""
