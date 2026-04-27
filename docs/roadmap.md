# Roadmap

D-ND_LAB shipped its first public release at the close of Phase 5
(this milestone). Everything below is what the lab can become next.

## Phase 5+ — what's next

### Cost/quality benchmark CLI

`dndlab benchmark --domain X --models a,b,c` runs the same cycle
across N models and produces a comparison matrix:

| model | success | turns | tokens | cost | duration | report bytes | quality |
|---|---|---|---|---|---|---|---|

Quality scoring via a separate "judge" LLM that reads the report +
refiner output and scores against rubric criteria. Skeleton already
shipped (`core/benchmark.py`); implementation pending real-world
demand.

### MCP tool servers

Replace the inline tools (`core/tools.py`) with MCP server processes.
Same OpenAI-format schemas, but each tool runs in its own subprocess
with proper isolation. Useful when:

- Tools need different runtime environments (e.g. R, Julia, Rust)
- Tools come from a third-party MCP marketplace
- Multi-tenant deployments need stronger sandboxing

The OpenAI schemas D-ND_LAB ships are already MCP-compatible, so
migration is a wiring change in `core/agent.py` (point the LLM
adapter at MCP URLs instead of inline callables).

### More domains

Two domains are in the seed; many more are possible. Candidates:

- **financial** — apply the M-spectroscopy + two-channel analysis
  to market returns. Needs adapters for the data sources, not new
  orchestrator logic.
- **operational** — apply the lab to the operator's own system
  (THIA/lab/sites). Self-observation as a service. The corpus is
  the system's own logs + commits + Sinapsi messages.
- **research_X** — any structured research field with falsifiable
  claims and a body of work. Computational biology, theoretical CS,
  history of mathematics, …

Each new domain is a directory under `domains/`, no `core/` change.

### Web dashboard

Local dashboard for cycle inspection — view the current seed, latest
report, refiner output, trajectory log, cost over time. Currently
exposed as static markdown via the nginx service; a thin React +
nginx setup would make it interactive without expanding the surface
area meaningfully.

### Streaming output

Live stream of agent turns to a log/console while the cycle runs.
The OpenAI SDK supports stream=True; the adapter doesn't currently
use it because cycle runs are background-friendly. If interactive
operation becomes a use case (developer running cycles attached to
a terminal), streaming makes the wait less opaque.

### Per-domain registry

Right now domains live in the same repo. A registry pattern (separate
git repos for domains, pulled in via config) would let users share
domains without forking. Lower priority — the in-tree pattern is
simpler and works for the foreseeable horizon.

## Feedback wanted

If you build something with D-ND_LAB, what works and what doesn't is
the highest-value signal for prioritizing the above. Issues + PRs
welcome at
[github.com/GrazianoGuiducci/D-ND_LAB](https://github.com/GrazianoGuiducci/D-ND_LAB).

## What's NOT planned

- **Built-in publishing** — the lab drafts; the operator decides when
  to publish. Publishing hooks are easy to add per-domain via a
  custom tool, but the core stays opinionated about not auto-publishing.
- **Multi-tenant SaaS** — the project is a template. Hosted multi-
  tenant offerings can be built on top, but the open-source core stays
  single-tenant.
- **GUI domain editor** — domains are markdown + JSON, edited in any
  editor. A GUI doesn't add value over a text editor with JSON
  Schema validation.
