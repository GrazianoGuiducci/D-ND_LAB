# D-ND_LAB

**An autonomous research lab for any domain you can structure.**

Built on the D-ND modus: *expand → observe → cut → resultant*. Each cycle
reads a seed of tensions, runs one experiment, writes one report, and
updates the seed with what was found. The system observes itself: autopsy
of the previous run, refiner on the step, evaluator on the trajectory.
*f(f(x))* — the lab improves the lab that improves itself.

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status: alpha](https://img.shields.io/badge/Status-alpha-orange.svg)](#status)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](#)
[![Provider-agnostic](https://img.shields.io/badge/LLM-OpenRouter%20%7C%20OpenAI%20%7C%20Anthropic%20%7C%20Ollama-purple.svg)](#provider-agnostic-by-design)

---

## What it is — and what it isn't

D-ND_LAB **is** an orchestrator of 16 movements that together produce
one resultant per cycle. The orchestrator is universal; the content
of a cycle (axioms, tensions, condensate, anti-patterns, tools) is
plug-in via a *domain* directory.

D-ND_LAB **is not** a chat agent, a writing assistant, a code
generator, or an LLM wrapper. It is a research scaffold whose output
is a structured artifact (report + bicono filter + seed update) — and
whose value compounds because the system observes its own steps.

| | Tool / chat agent | D-ND_LAB |
|---|---|---|
| Per call | One question, one answer | One cycle: expand → cut → resultant |
| Memory | Session-bound | Seed evolves across cycles |
| Self-correction | None or post-hoc | Built in: autopsy + refiner + structural-check |
| Output shape | Free text | Report + bicono + seed delta + falsified registry |
| Output domain | Whatever the user prompts | Whatever the operator structured |

## The 16 movements

```
0. autopsy            ← observes previous run, identifies regressive node
1. build_field        ← assembles the live agent context
2. agent              ← the LLM cycle (one tension, one experiment)
3. validate_seed      ← integrity + bootstrap from seed_tensions on first run
4. verify_assertions  ← runs domain assertions (pass/fail)
5. structural_check   ← scans code for D-ND anti-patterns, injects META tensions
6. build_lab_data     ← snapshot piano + tensions + last report
7. build_graph        ← knowledge graph nodes + edges
8. sync               ← propagate state to declared targets
9. verify_endpoints   ← health-check downstream consumers
10. refiner           ← second LLM observes the step (not the result)
11. semantic_bridge   ← maps findings to domain category mapping
12. refresh_detector  ← event-driven trigger for derivative regen
13. seed_integrator   ← crystallizes new seed (piano++, direction rotates)
14. trajectory_eval   ← LLM decides STOP/NEXT/REDESIGN/ESCALATE/CRYSTALLIZE
15. notify            ← webhook to operator
```

Each movement is small, registered with the orchestrator, and graceful
under failure. Critical failures abort; non-critical ones log and
continue. Domains can disable individual movements via config.

## Quick install

```bash
curl -fsSL https://raw.githubusercontent.com/GrazianoGuiducci/D-ND_LAB/main/install.sh | bash
```

The installer:
1. Verifies Docker + Docker Compose
2. Clones to `~/.d-nd-lab`
3. Prompts for your LLM API key + model + domain
4. Builds the image and starts a smoke test (dry-run cycle, no API calls)

After install, run a real cycle:

```bash
cd ~/.d-nd-lab
docker compose run --rm lab     # one cycle, ~5-15 min, $0.03-$0.15 typical
```

Or schedule nightly cycles:

```bash
docker compose --profile cron up -d
```

## Provider-agnostic by design

Single environment variable controls the entire LLM choice. The
adapter is OpenAI-compatible, so any of the following work without
code changes:

```bash
LLM_BASE_URL=https://openrouter.ai/api/v1   # 360+ models, no lock-in
LLM_BASE_URL=https://api.openai.com/v1      # OpenAI direct
LLM_BASE_URL=https://api.anthropic.com/v1   # Anthropic compat shim
LLM_BASE_URL=http://localhost:11434/v1      # Ollama (self-hosted)
```

```bash
LLM_MODEL=deepseek/deepseek-v4-pro          # economy default
LLM_MODEL=anthropic/claude-opus-4.7         # premium quality
LLM_MODEL=tencent/hy3-preview:free          # free dev tier
LLM_MODEL=moonshotai/kimi-k2.6              # large ctx, balanced
LLM_MODEL=xiaomi/mimo-v2.5-pro              # 1M ctx, mid-tier
LLM_MODEL=ollama/<local-model>              # self-hosted
```

`reasoning_details` for thinking-mode models (DeepSeek, Anthropic
extended, Gemini 3) is preserved across multi-turn loops automatically.

## Domains shipped

| domain | what it studies |
|---|---|
| `physics` | mathematical physics through D-ND: primes, zeta, GUE, theory crossing TQGE+R |
| `editorial` | the operator's archive — discriminates source from echo, drafts publishable copy through the bicono filter and non-dual-copy gate |

Each domain is a directory with `config.json`, `context.md`,
`tension_to_category.json`, `seed_tensions.json`, `tools/`, and
optionally `corpus/` (gitignored). See
[docs/extending.md](docs/extending.md) for how to write your own.

## Architecture

```
D-ND_LAB/
├── core/                       # universal orchestrator + adapter + tools
│   ├── lab_agent.py            # 16-movement dispatcher
│   ├── llm_adapter.py          # OpenAI-compatible, reasoning-aware
│   ├── tools.py                # default sandboxed tool set
│   ├── paths.py + config.py    # path resolution + JSON Schema validation
│   ├── autopsy / refiner / trajectory_evaluator / ...
│   └── benchmark.py            # cost/quality matrix across N models (Phase 5+)
├── domains/                    # plug-in content
│   ├── physics/
│   └── editorial/
├── docs/                       # GitHub Pages site
├── examples/                   # runnable demos
├── Dockerfile + docker-compose.yml + install.sh
└── config.schema.json          # validates each domain's wiring
```

Movements live as small modules under `core/` and register with the
dispatcher at import. Domain content lives entirely under `domains/<name>/`
and is loaded via the domain's `config.json`. The two never mix.

## Safety

- **Sandbox**: agent tools (read_file, write_file, run_python, run_bash)
  are restricted to the domain's data dir + read-only domain dir. Outside
  paths raise `PermissionError`.
- **Env stripping**: subprocess env strips `LLM_*`, `*TOKEN*`, `*API_KEY*`,
  `*SECRET*` so agent code cannot leak credentials.
- **Hard caps**: per-cycle `LLM_MAX_TURNS`, `LLM_TIMEOUT_SECONDS`, optional
  `LLM_MAX_COST_USD` — each enforced inside the adapter loop.
- **Non-root container**: image runs as UID 1001, healthcheck via Python
  imports only.
- **Corpus privacy**: `domains/*/corpus/*` is gitignored; only the
  README + `.gitkeep` placeholders are tracked. User content stays local.

## Status

Alpha — first public release. The physics domain ports the original
research lab that runs nightly at [lab.d-nd.com](https://lab.d-nd.com).
The editorial domain is the test that the abstract template works on
non-numeric content. Both have produced clean cycles end-to-end.

The roadmap (Phase 5+):
- benchmark CLI implementation (cost/quality matrix across models)
- MCP tool servers replacing inline tools
- additional domains (financial, operational)
- web dashboard for cycle inspection

## Origin

D-ND_LAB is a reified instance of the [D-ND framework](https://d-nd.com)
— the system that studies the system. The original physics lab (the
seed of this codebase) keeps running as a public showcase at
[lab.d-nd.com](https://lab.d-nd.com).

## License

MIT — see [LICENSE](LICENSE).

## Contributing

Issues and PRs welcome. Note that the repo direction is **MM_D-ND →
D-ND_LAB** for upstream changes, not the other way around (the
research framework remains the source of truth for the model;
D-ND_LAB is its operational template).
