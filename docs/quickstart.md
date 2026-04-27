# Quickstart

From zero to a running cycle in 5 minutes.

## Prerequisites

- **Docker** + **Docker Compose** plugin
- **Git**
- An LLM API key — recommended: [OpenRouter](https://openrouter.ai/keys)
  (one key, 360+ models, no lock-in)

That's it. No Python setup, no venv, no system dependencies.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/GrazianoGuiducci/D-ND_LAB/main/install.sh | bash
```

The installer:

1. Verifies Docker + Docker Compose
2. Clones the repo to `~/.d-nd-lab`
3. Prompts for your API key, model, and starting domain
4. Builds the image
5. Runs a smoke test (a *dry-run* cycle — no API calls, validates config)

After install:

```bash
cd ~/.d-nd-lab
```

## Run your first cycle

```bash
docker compose run --rm lab
```

The default domain is **physics** — a port of the D-ND research lab
that explores tensions in mathematical physics (primes, zeta, GUE,
theory crossing). A typical first cycle:

- 5–15 minutes of compute
- 5–25 LLM turns
- One scientific report written to `data/physics/reports/agent_<ts>.md`
- Seed updated (piano++, direction rotates)
- Refiner + trajectory_evaluator observations logged

Cost varies with the model. The adapter records `usage` (tokens) and
`cost_usd` (computed from the provider's live pricing) in
`data/<domain>/lab_data.json` after each cycle, so you always know
what a run cost. Browse current models and prices at
[openrouter.ai/models](https://openrouter.ai/models). Free-tier
models (suffix `:free`) are zero-cost but rate-limited and struggled
with longer reasoning chains in our internal tests.

## See what happened

```bash
docker compose run --rm lab status --domain physics
```

Shows current seed (piano + direction), recent reports, recent
trajectory decisions.

To browse reports as static markdown over HTTP:

```bash
docker compose up -d nginx
# Open http://localhost:8080/data/reports/
```

## Switch model

Edit `~/.d-nd-lab/.env`:

```bash
LLM_MODEL=anthropic/claude-opus-4.7   # premium quality
# or
LLM_MODEL=moonshotai/kimi-k2.6        # large ctx, balanced cost
# or
LLM_MODEL=ollama/<your-local-model>   # self-hosted
```

No code change. The adapter is OpenAI-compatible; any model exposed
through that surface works.

## Run on schedule

Enable cron-mode profile:

```bash
docker compose --profile cron up -d
```

This runs `LAB_CRON_SCHEDULE` (default `30 3 * * *` — nightly at 03:30
UTC). Each cycle picks up where the last left off — the seed evolves,
the cimitero accumulates, the trajectory evaluator decides whether to
keep going or surface a stop.

## Try the editorial domain

```bash
# 1. Edit ~/.d-nd-lab/.env  →  LAB_DOMAIN=editorial
# 2. Add some markdown notes to ~/.d-nd-lab/domains/editorial/corpus/
# 3. Run a cycle
docker compose run --rm lab
```

The editorial lab reads your archive, identifies convergences (where
multiple entries point at the same unstated thing), and produces a
draft. See [Editorial](domains/editorial.md) for what to put in the
corpus.

## When something goes wrong

```bash
# Validate config without spending API credits
docker compose run --rm lab dry-run --domain physics

# Inspect a domain's wiring
docker compose run --rm lab inspect --domain physics

# Read the lab's autopsy of the last failed run
cat data/physics/lab_health.json
```

The `lab_health.json` file always tells you what the previous run did
and where it stopped — even if the run itself didn't write a final
report. The autopsy never crashes the cycle; if its analysis fails, it
writes `status=autopsy_failed` and the next cycle can read that.
