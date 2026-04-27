# Changelog

All notable changes to D-ND_LAB. The format follows [Keep a Changelog](https://keepachangelog.com/).

## [0.1.0-alpha] — 2026-04-27 — first public release

The first public alpha. Five development phases compressed into a
single release; subsequent versions follow regular semver.

### Added

**Phase 0 — scaffold**
- Repository structure: `core/`, `domains/`, `docs/`, `examples/`, `tests/`
- LICENSE (MIT), `.gitignore`, `pyproject.toml` (uv-managed)
- `.env.example`, `config.schema.json`, placeholder `Dockerfile` +
  `docker-compose.yml`

**Phase 1 — refactor (16-movement orchestrator in `core/`)**
- `core/lab_agent.py` — orchestrator: dispatches the 16 movements,
  CycleContext dataclass, register_movement API, critical/non-critical
  failure policy
- `core/paths.py` — central path resolution via env vars + per-domain
  data dirs (replaces hardcoded `/opt/MM_D-ND` in 7 source files)
- `core/config.py` — domain config loader + JSON Schema validation
- `core/cli.py` — `dndlab list / inspect / run / dry-run / status / benchmark`
- Movements: `autopsy`, `build_field`, `agent`, `validate_seed`,
  `verify_assertions`, `structural_check`, `build_lab_data`, `build_graph`,
  `sync`, `verify_endpoints`, `refiner`, `semantic_bridge`,
  `refresh_detector`, `seed_integrator`, `trajectory_evaluator`, `notify`
- `core/lab_context_template.md` with placeholders populated per domain
- `domains/physics/` populated (context.md ported from
  `MM_D-ND/tools/LAB_AGENT_CONTEXT.md`, tension_to_category.json
  flattened from physics tension_to_theory.json, seed_tensions.json
  derived from current physics seme)
- Bootstrap: validate_seed reads `seed_tensions.json` on first cycle

**Phase 2 — LLM adapter + tools + safety**
- `core/llm_adapter.py` — OpenAI-compatible client wrapping `openai`
  Python SDK. Multi-turn tool-use loop. `reasoning_details` preservation
  for thinking-mode models (DeepSeek thinking, Anthropic extended,
  Gemini 3 thinking) per OpenRouter spec. `early_stop` callback for
  agents that achieve the cycle goal as side-effect (file written).
  Cost tracking via lazy `/models` pricing fetch (cached per process).
  Hard caps: `LLM_MAX_TURNS`, `LLM_TIMEOUT_SECONDS`, optional
  `LLM_MAX_COST_USD`.
- `core/tools.py` — built-in tools (read_file, write_file, list_dir,
  run_python, run_bash). Sandboxed to `<data>/<domain>/` (read-write)
  + `<repo>/domains/<domain>/` (read-only). Outside paths raise
  PermissionError. Subprocess env strips `LLM_*`, `*TOKEN*`,
  `*API_KEY*`, `*SECRET*` to prevent agent code leaking credentials.
  Output capped at 50 KB.
- End-to-end validated: physics cycle with `deepseek/deepseek-v4-pro`
  through OpenRouter — 9 turns, 16 tool calls, ~150K tokens, scientific
  report produced (BOUNDARY tension explored, claim falsified, ordering
  fraction identified as third-included operator). Cost recorded by the
  adapter at run time; provider pricing changes over time, see
  `data/<domain>/lab_data.json` after your own runs for current numbers.

**Phase 3 — containerization + installer**
- `Dockerfile` — multi-stage (builder uses uv, runtime is slim Python
  3.13 with tini PID 1), non-root user UID 1001, HEALTHCHECK
  (Python imports), VOLUME `/data`
- `docker-compose.yml` — `lab` service (one-shot or `--profile cron`
  for scheduled), `nginx` service serving reports + state
- `docker/nginx.conf` — autoindex on `/data/reports/`, JSON state
  exposed, healthcheck endpoint
- `install.sh` — interactive one-liner installer: prereq verify, clone,
  prompt for API key + model + domain, write `.env` with chmod 600,
  build + smoke-test (dry-run cycle)

**Phase 4 — second domain (editorial)**
- `domains/editorial/context.md` — editorial model: source-vs-echo +
  transferable-vs-idiosyncratic dipoles, four publishing quadrants, 7
  editorial anti-patterns, bicono filter applied to a draft, output
  format with worked example
- `domains/editorial/tension_to_category.json` — 12 editorial tensions
  → 6 structural categories (SRC, ECHO, TRANS, IDIO, REG_INT, REG_EXT)
- `domains/editorial/seed_tensions.json` — 8 starting tensions, top
  three at intensities 0.95/0.9/0.85
- `domains/editorial/tools/archive_search.py` — full-text search over
  corpus dir with multi-keyword scoring + snippet extraction
- `domains/editorial/tools/voice_check.py` — non-dual-copy filter:
  modal/temporal/epistemic/comparative hedges, first-person-THIA
  violations, dominant-frame tautologies
- `domains/editorial/corpus/` — gitignored except README + .gitkeep
- `core/agent.py` — domain tools loader: `type=domain` entries
  dynamically import + register
- End-to-end validated: editorial cycle on a 3-entry mini-corpus
  identified the structural dipole **Accumulation (det=+1) vs
  Compounding (det=0)** across AI infrastructure / Seed installation /
  defensive code, drafted the essay "The Addition Bias" (~7.8 KB).
  The same modus produces the same output shape on numeric and
  semantic content. The abstract template is no longer a hypothesis.

**Phase 5 — public release prep**
- README curated: tagline, badges, 16-movement diagram, install
  one-liner, provider matrix, domain matrix, architecture, safety,
  status
- Docs site: `mkdocs.yml` (Material theme), `docs/index.md`,
  `quickstart.md`, `architecture.md`, `domains/{index,physics,editorial,extending}.md`,
  `config.md`, `roadmap.md`
- Announcement drafts: LinkedIn (operator-personal), Bluesky (technical),
  Hacker News Show HN, README badge text, 5 reply templates for likely
  first comments — all passing voice-check
- `core/benchmark.py` — skeleton + contract for `dndlab benchmark
  --domain X --models a,b,c` (Phase 5+ implementation)
- `.env.example` model list expanded: 9 candidates documented by group
  (tested / not yet benchmarked / free tier), no hardcoded prices

### Notes

- The original physics lab at `lab.d-nd.com` continues to run nightly
  on the legacy codebase in `MM_D-ND/`. D-ND_LAB is the portable
  template; the production lab will migrate over once the template is
  deemed stable.
- Domain-specific tools from the production lab (`dnd_scenario.py`,
  `dnd_autoricerca.py`, `m_spectro.py`, etc.) have NOT been ported
  yet. The physics domain ships as "minimal viable physics" — the
  production tools can be added per `domains/physics/tools/` as
  needed.
