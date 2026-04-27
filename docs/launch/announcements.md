# Announcement drafts

> **Status: drafts for operator review.** Not published. Each platform
> has its own register; the operator picks which (if any) go live and
> when. All drafts pass the non-dual-copy filter — no apologetic
> hedging, no first-person THIA, no dominant-frame tautologies.

## LinkedIn (operator-personal)

```
We open-sourced D-ND_LAB.

It is the autonomous research lab template that has been running
nightly on lab.d-nd.com — now extracted into a portable scaffold
that runs on any structured domain.

What it does on a cycle: reads a seed of tensions, runs one
experiment via an autonomous LLM agent, writes one report through
a structural filter (the bicono — radii · singular · invariant ·
field of possibility), updates the seed with what was found.
Sixteen movements total, four of them reflective: autopsy of the
previous run, refiner of the step, structural-check on the code,
trajectory evaluator on the direction. The lab observes the lab.

What it is not: a chat agent, a writing assistant, a code generator.
It does not optimize for engagement. The output is a structured
artifact that compounds across cycles.

Two domains in the seed:
— physics (the original D-ND research lab)
— editorial (the lab that reads your archive and discriminates source
  from echo)

Provider-agnostic. One environment variable changes the LLM. Tested
end-to-end with DeepSeek V4 Pro through OpenRouter; the adapter is
OpenAI-compatible so any provider exposing that surface works,
including Ollama for self-hosted.

MIT license. Docker compose up to run.

[link to repo]
```

## Bluesky (technical, researcher-leaning)

Two posts (300 char each, threadable):

```
[1/2] Open-sourced D-ND_LAB — autonomous research lab template.
Sixteen-movement cycle: autopsy → build_field → agent → ... →
seed_integrator → trajectory_eval. Four of the movements are
reflective (system observes system). f(f(x)).
github.com/GrazianoGuiducci/D-ND_LAB
```

```
[2/2] Provider-agnostic via OpenRouter (or OpenAI/Anthropic/Ollama).
reasoning_details preserved across multi-turn for thinking-mode models.
Tested with DeepSeek V4 Pro on a physics cycle ($0.07, 9 turns)
and an editorial cycle (drafts publishable copy from a corpus).
MIT.
```

## Hacker News — "Show HN"

```
Title: Show HN: D-ND_LAB – an autonomous research lab template that
observes its own cycles

Body:

I've been running a research lab nightly at lab.d-nd.com for several
months. It's an autonomous cycle: pick one tension from a seed of
hypotheses, run an experiment, write a report through a structural
filter, update the seed. The interesting part is the four reflective
movements — autopsy of the previous run, refiner that observes the
step (not the result), structural-check that scans code for
anti-patterns and injects corrective tensions, trajectory evaluator
that decides where to go next.

I extracted the orchestrator into a portable template. The skeleton
is universal (16 movements, no domain logic in core/); the content
plugs in via domains/<name>/. Two domains ship: physics (the original
mathematical research lab) and editorial (which reads an operator's
archive and discriminates source from echo, drafts copy through a
non-dual-copy filter).

Provider-agnostic by design. The LLM adapter is OpenAI-compatible, so
OpenRouter / OpenAI / Anthropic compat / Ollama all work without code
changes. Cost tracked per cycle and persisted with the report.

Docker compose up for full deployment, or pip install for standalone.
First cycle ~5-15 minutes, ~$0.05-$0.20 with DeepSeek V4 Pro through
OpenRouter (free-tier models like tencent/hy3-preview:free work but
struggle with longer reasoning chains).

MIT licensed. Built on the D-ND framework (d-nd.com) — the model is
public, the lab is the operational template.

GitHub: https://github.com/GrazianoGuiducci/D-ND_LAB
Live original: https://lab.d-nd.com

Feedback specifically wanted on: (a) whether the 16-movement breakdown
makes sense for fields outside research/editorial, (b) whether the
plug-in domain pattern is the right granularity, (c) what other
domains people would want to see ship in the seed.
```

## README badge text (if we decide to add a "what runs on it" badge)

```markdown
[![Live](https://img.shields.io/badge/Live-lab.d--nd.com-purple)](https://lab.d-nd.com)
```

## Reply templates for likely first comments

These are pre-written so the operator can paste-adapt rather than
write fresh under deadline pressure. Each passes voice-check.

**"Why not just use [LangChain / AutoGen / CrewAI / etc]?"**

```
Different layer. LangChain et al. are framework primitives — you
assemble agents from chains, tools, memory. D-ND_LAB is an opinionated
*orchestrator* — sixteen specific movements, four of them reflective,
that together implement the modus expand → observe → cut → resultant
across cycles. You could implement it on top of LangChain. We didn't
because the orchestrator's value is in the discipline of those
specific sixteen movements, not in framework reuse.
```

**"What's the bicono?"**

```
A four-part structural filter every finding passes through before it
counts. Two roots (the dipole the finding lives in), singular (the
state before the dipole), invariant of passage (what survives the
cut), field of possibility (what becomes possible / not-possible
after). It comes from the D-ND framework — d-nd.com has the math.
The lab uses it as a publish-gate: if a finding can't compile a
bicono, it's not yet ready.
```

**"Does it work with [specific LLM]?"**

```
If your LLM has an OpenAI-compatible chat completions endpoint with
tool use, yes. Set LLM_BASE_URL + LLM_API_KEY + LLM_MODEL in .env,
done. Works tested with OpenRouter (360+ models behind one API),
should work with OpenAI, Anthropic compat shim, Ollama, and any
provider following the spec. Reasoning models (DeepSeek thinking,
Anthropic extended thinking, Gemini 3 thinking) are supported via
OpenRouter's standard reasoning_details preservation.
```

**"Is the corpus uploaded somewhere?"**

```
No — domains/*/corpus/ is gitignored by default. The editorial
domain's corpus is the operator's archive and stays local. The
lab reads it; the lab's drafts may reference entries; the lab
doesn't republish corpus content.
```

**"What about cost?"**

```
Adapter records usage and cost_usd in lab_data.json after each
cycle. Hard caps via LLM_MAX_COST_USD env var. With economy models
(DeepSeek V4 Pro, Qwen 3.6 Plus), expect a few cents per cycle.
With premium (Claude Opus 4.7, GPT-5.5 Pro), expect higher.
Free-tier models (suffix :free on OpenRouter) are zero-cost but
rate-limited and struggled to close complex tasks in our tests.
```
