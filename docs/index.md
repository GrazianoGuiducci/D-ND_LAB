# D-ND_LAB

> **An autonomous research lab for any domain you can structure.**

Built on the D-ND modus: *expand → observe → cut → resultant*.

## What it does

Every cycle, D-ND_LAB:

1. **Reads** the domain's seed (active tensions, last reports, observations)
2. **Runs** one experiment via an autonomous LLM agent
3. **Writes** one report (with the bicono filter applied)
4. **Updates** the seed — direction rotates, falsified claims go to the
   cimitero, new tensions emerge
5. **Observes itself** — the autopsy reads the previous cycle, the refiner
   observes the step quality, the trajectory evaluator decides where to go next

The lab improves itself. *f(f(x))*: the system that observes the system.

## Why

Most LLM workflows are session-bound — every chat starts from zero. The
lab keeps the thread:

- **Memory of decisions** in the seed
- **Memory of failures** in the cimitero
- **Memory of structure** in the bicono of each finding
- **Memory of the operator's voice** via the corpus (in the editorial domain)

What you get back is not a chat reply. It's a structured artifact that
compounds across cycles.

## Where to go from here

- New here? → [Quickstart](quickstart.md) gets you a running lab in 5 min.
- Want to understand how it works? → [Architecture](architecture.md)
- Building a new lab? → [Meta-lab Capability Stack](META_LAB_CAPABILITY_STACK.md)
- Exploring the next public domain? →
  [Bitcoin Regime Lab Seed](BITCOIN_REGIME_LAB_SEED_20260518.md)
- Want to use the physics or editorial domain? → [Domains](domains/index.md)
- Want to write your own domain? → [Extending](domains/extending.md)

## Built on D-ND

D-ND_LAB is the operational template of the D-ND framework. The
mathematical core (f(x)=1+1/x, M, det=−1, the spiral, the third
included as formal operator) lives at [d-nd.com](https://d-nd.com).
The original physics lab — the seed this codebase grew from — keeps
running publicly at [lab.d-nd.com](https://lab.d-nd.com).
