# Architecture

A lab cycle is the dispatch of **16 movements**. Each one is a small
function that reads and mutates a `CycleContext`. The orchestrator
runs them in order, handling failures per a per-movement policy.

## The 16 movements

```
0.  autopsy              ← Pure I/O. Reads previous run's session log + report,
                          classifies outcome, identifies regressive node where
                          the relational condition was missing. Writes lab_health.json.

1.  build_field          ← Assembles agent_field_live.md from: domain context,
                          last 3 reports, active tensions, convergence map,
                          knowledge graph topology, optional projector output.

2.  agent                ← The autonomous LLM cycle. Picks one tension, formulates
                          one question, runs one experiment, writes one report.
                          Tools sandboxed to domain data dir.

3.  validate_seed        ← Integrity check. First cycle: bootstraps from
                          domains/<d>/seed_tensions.json. Subsequent cycles:
                          restore from backup if corrupted.

4.  verify_assertions    ← Runs domain-declared assertions (PASS/FAIL/SKIP).
                          Used for testing claims in the condensate.

5.  structural_check     ← Scans modified Python files for D-ND anti-patterns
                          (numbers binding concepts, thresholds on qualitative
                          states, weighted aggregations of structural qualities).
                          Injects META tensions for the next cycle to address.

6.  build_lab_data       ← Snapshot piano + tensions + last report into JSON
                          for downstream consumers (sites, dashboards).

7.  build_graph          ← Knowledge graph nodes (tensions, reports, theories)
                          + edges (covers, bridges, ghosts). Domains can extend
                          via params.graph_module.

8.  sync                 ← Propagate state to declared targets: filesystem
                          mirror, HTTP POST, etc. Disabled by default.

9.  verify_endpoints     ← Health-check downstream consumers. Disabled by default.

10. refiner              ← LLM separate from producer. Observes the STEP, not
                          the result. Writes evolution_<ts>.md with structural
                          proposals (Riparazione Regressiva applied to the lab).

11. semantic_bridge      ← Maps numerical findings to semantic annotations on
                          the knowledge structure (e.g. theory pairs). Reads
                          tension_to_category.json from the domain.

12. refresh_detector     ← Event-driven trigger: runs heavy regen (e.g. theory
                          crossing) only when enough new material has accumulated
                          since last refresh, or staleness > threshold.

13. seed_integrator      ← Crystallizes the new seed: sorts tensions by
                          intensity, archives previous, derives new direction
                          from priority. Closes the autopoietic loop A5.

14. trajectory_eval      ← Separate LLM with free mandate. Decides STOP_FOR_REVIEW
                          / NEXT_CYCLE / REDESIGN / ESCALATE / CRYSTALLIZE / OTHER.
                          Log-only by default; execute=true enables side-effects.

15. notify               ← POST a summary to NOTIFY_WEBHOOK_URL.
```

## Pattern f(f(x))

Movements 0, 5, 10, 14 are **reflective** — they observe the system,
not the experiment:

- *autopsy* observes the previous cycle (retrospective)
- *structural_check* observes the code (auto-corrective)
- *refiner* observes the step (concurrent)
- *trajectory_evaluator* observes the trajectory (prospective)

This is what makes the lab self-improving: each cycle inherits the
observations of the previous one, and the seed evolves toward higher
discriminating power across cycles.

## Failure handling

Movements have a per-movement policy:

| Policy | Movements | Behavior on failure |
|---|---|---|
| Critical | `build_field`, `agent` | Cycle aborts |
| Reflective | `autopsy`, `refiner`, `trajectory_evaluator` | Mark pending, continue |
| Validation | `validate_seed`, `structural_check` | Tracked but non-blocking |
| Side-effect | `sync`, `notify`, `verify_endpoints` | Log error, continue |

The autopsy NEVER crashes the cycle. If autopsy itself errors, it
writes `status=autopsy_failed` and the next cycle reads that as a
signal to investigate the autopsy code.

## Skeleton vs domain content

The `core/` directory contains **only universal logic** — the
orchestrator, adapter, tools, paths, config, and the 16 movement
implementations. None of it knows about physics or editorial.

Domain content lives entirely under `domains/<name>/`:

```
domains/<name>/
├── config.json                  # wiring (which movements, which params)
├── context.md                   # axioms + condensate + anti-patterns + bicono examples
├── tension_to_category.json     # mapping for semantic_bridge
├── seed_tensions.json           # bootstrap for first cycle
├── tools/                       # domain-specific tools (each module exposes build(domain) → ToolEntry)
└── corpus/                      # private content (gitignored)
```

When a movement needs a domain plugin (e.g. `build_field` reading the
projector output, `trajectory_evaluator` reading enrichment sources),
the domain config declares it as a Python module path in
`movements.<name>.params.<plugin_module>`. The movement imports it
dynamically and calls a contract method.

This split is the test of the abstract template: the same `core/` ran
both the physics domain (numerical research) and the editorial domain
(semantic content) without modification.

## The cycle context

`CycleContext` is a dataclass passed between movements:

```python
@dataclass
class CycleContext:
    domain: str                    # e.g. "physics"
    timestamp: str                 # YYYYMMDD_HHMM
    data_dir: Path                 # <LAB_DATA_DIR>/<domain>/
    config: dict                   # validated domain config
    seed: dict                     # current seed (mutated by structural_check, seed_integrator)
    health: dict                   # autopsy output for this cycle
    agent_output_path: Path | None
    report_path: Path | None
    errors: list[str]
    metrics: dict[str, Any]        # per-movement metrics + cycle totals
    movement_status: dict[str, str]
```

Movements read what they need, mutate what they own, append errors,
record metrics. No global state, no implicit coupling — each movement
is testable in isolation given a context fixture.

## Adapter + tools

The LLM adapter (`core/llm_adapter.py`) wraps the OpenAI Python SDK.
It accepts:

- `system_prompt`, `user_message` — message history scaffolding
- `tools` — list of `ToolEntry` (schema + Python callable)
- `config` — `AdapterConfig.from_env()` reads `LLM_*` env vars
- `early_stop` — optional callable; loop terminates when it returns True

Multi-turn loop:
1. POST `/chat/completions` with messages + tools
2. If `finish_reason == "tool_calls"`: dispatch each call, append
   tool results to messages, continue
3. Else: return final assistant text
4. After each turn, check `early_stop` — agents that achieve the cycle
   goal as a side effect (file written) can stop early

Reasoning models (DeepSeek thinking, Anthropic extended thinking,
Gemini 3 thinking, etc.): `reasoning_details` and `reasoning` fields
on the assistant message are preserved when sent back, per OpenRouter
spec — so multi-turn works without breaking thinking chains.

Cost tracking: usage tokens come from the provider response;
pricing is fetched lazily from `/models` (cached per process).
`cost_usd` is recorded in `AgentResult` and persisted to
`lab_data.json` for status reporting.

## Sandbox

Built-in tools (`core/tools.py`):

- `read_file(path)` — read inside the sandbox
- `write_file(path, content)` — write inside data dir
- `list_dir(path)` — list inside the sandbox
- `run_python(code, timeout_s=60)` — subprocess Python with timeout
- `run_bash(command, timeout_s=60)` — subprocess bash with timeout

Sandbox roots:
- `data_dir` — read+write (reports, seed, graph, cimitero)
- `domain_dir` — read-only (configs, contexts, tools)

Anything outside raises `PermissionError`. Subprocess env strips
`LLM_*`, `*TOKEN*`, `*API_KEY*`, `*SECRET*` so agent code can't leak
credentials. Output capped at 50 KB to prevent flood.

## When the lab evolves

Every commit to a domain's `context.md`, `tension_to_category.json`,
or `tools/*.py` immediately changes how the next cycle runs — no
rebuild needed. Changes to `core/*` require rebuilding the Docker
image (or just `git pull` if running standalone).

The seed evolves *across cycles* via `seed_integrator`. The cimitero
(falsified claims registry) accumulates *forever*. The trajectory log
(evaluator decisions) is append-only.

This is the operational interpretation of *the system that studies the
system*: the artifacts persist, the orchestrator stays still, the LLM
choice is a flag.
