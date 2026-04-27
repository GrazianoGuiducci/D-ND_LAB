# D-ND_LAB

> **Tagline placeholder — da decidere insieme in Phase 5**
>
> Candidati: "An autonomous research lab — for any domain you can structure" /
> "f(f(x)) — the system that improves the system that improves itself" /
> "Plant the modus. Watch the field cycle."

[![Status](https://img.shields.io/badge/Status-Phase%200%20scaffold-yellow)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## What this is

D-ND_LAB is an autonomous research lab that runs as a nightly cycle on any
domain you can structure. It is not a chat agent. It is not a script. It is
an orchestration of 13 movements — autopsy, field assembly, autonomous
reasoning, structural verification, semantic bridging, seed crystallization,
trajectory evaluation — that together produce one resultant per cycle.

The lab uses the D-ND modus: **expand → observe → cut → resultant**. Every
cycle reads the seed, runs an experiment via an autonomous LLM agent, and
updates the seed with what was found. The discovery passes through the
**bicono filter** (radii · singular · invariant · field of possibility) before
crystallizing.

The system improves itself. Each cycle observes the previous run (autopsy),
the step itself (refiner), and the trajectory (evaluator). Anti-patterns
detected automatically inject corrective tensions into the seed for the next
cycle.

## Status

**Phase 0 — Scaffold (current).** Repository structure only. No operational
code yet. See [docs/roadmap.md](docs/roadmap.md) (TBD) for the 5-phase plan
toward public launch.

## Architecture (target)

```
D-ND_LAB/
├── core/              # template engine (universal across domains)
│   ├── lab_agent.py          # 13-movement orchestrator
│   ├── llm_adapter.py        # OpenAI-compatible client (OpenRouter / Ollama)
│   ├── lab_context_template.md  # placeholder template populated by domain
│   └── connectors/           # optional integrations (MCP servers)
│
├── domains/           # domain-specific content
│   ├── physics/              # the original D-ND physics lab
│   ├── editorial/            # publishing-aware lab (insight archive → resultant)
│   └── financial/            # markets / m-spectro on returns (Phase 2)
│
├── docs/              # GitHub Pages documentation
└── examples/          # runnable demos for each domain
```

## Quick Install (target — Phase 3)

```bash
# Coming in Phase 3
curl -fsSL https://raw.githubusercontent.com/GrazianoGuiducci/D-ND_LAB/main/install.sh | bash
```

## Provider-agnostic by design

Configurable via single environment variable. Default uses OpenRouter
(360+ models, no lock-in). Switch model with one flag:

```bash
LLM_MODEL=deepseek/deepseek-v4-pro       # default — economy
LLM_MODEL=anthropic/claude-opus-4.7      # premium quality
LLM_MODEL=tencent/hy3-preview:free       # free for dev
LLM_MODEL=ollama/<local-model>           # self-hosted (Phase 2.5)
```

## License

MIT — see [LICENSE](LICENSE).

## Origin

D-ND_LAB grew out of the D-ND research framework. It is a reified instance
of the model: the system that studies the system. The original physics lab
(the seed of this codebase) continues to run as the public showcase at
[lab.d-nd.com](https://lab.d-nd.com).
