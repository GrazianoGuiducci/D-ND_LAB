# Physics Domain

The original D-ND research lab. Studies mathematical physics through
the model: f(x) = 1 + 1/x, M = [[1,1],[1,0]], det(M) = -1, the spiral,
the third included as formal operator. The fixed point is φ.

## What it studies

- **Primes** — gap distributions, residue cosets, GUE-like spectral statistics
- **Zeta** — non-trivial zeros, signature of the zero, phi-crossings
- **Dynamical systems** — convergence, attractor classification, null baselines
- **Theory crossing TQGE+R** — Thermodynamics × Quantum × Gravity ×
  Electromagnetism + Relativity, with 10 fundamental questions
  ("how do A and B coexist?") and one void (Q×G — continuous vs discrete)

The condensate (in `domains/physics/context.md`) tracks what has been
verified vs falsified. The cimitero registers claims that fell.

## Configuration

`domains/physics/config.json` enables most movements with default
parameters. Notable settings:

- `movements.structural_check.params.inject_meta_tensions: true` —
  detected anti-patterns become META tensions in the seed
- `movements.trajectory_evaluator.params.execute: false, log_only: true` —
  trajectory decisions logged but not executed (operator review default)
- `movements.sync.enabled: false` — sync is wired off in the public
  template; the original lab syncs to `/opt/THIA/data/` (THIA-specific)
- `movements.verify_assertions.assertions_module` — *not set*; the
  original lab has a rich set of assertions in MM_D-ND/tools/dipartimento.py
  that haven't been ported to the portable template yet

## Seed tensions

Eight starting tensions in `domains/physics/seed_tensions.json`,
ported from the production lab's seme.json (excluding transient
STRUCTURAL_CHECK_* entries). Top three by intensity:

- **TRASCENDENZA_LIMITE** (0.9) — the transcendence and the current
  limit of the model. Relational fixed points may reveal the rule
  beyond convergence to phi.
- **DUALITA_DIPOLARE_VS_ILLUSORIA** (0.9) — dipolar duality
  (generative, det=-1) vs illusory duality (dispersive, det=+1).
- **METRIC_TENSOR** (0.9) — the metric tensor of primes is g=(p/2)².
  In log time, it is de Sitter 1+1D. z-statistics: -8.8 curvature vs
  +22.5 ratio.

## tension_to_category

Maps 21 physics tensions to TQGE+R categories. Crossings with ≥2
categories produce annotations on theory pairs in
`conoscenza_teorie.json`. Examples:

- `BOUNDARY` → `[G]` (geometric boundary)
- `DUALITA_DIPOLARE_VS_ILLUSORIA` → `[Q, T]` (quantum + thermal)
- `M_tensore_metrico_primi_L0` → `[G, Q]`
- `TWO_CHANNEL_DECOMPOSITION` → `[Q, T]`

## What's NOT in the portable template (yet)

The production lab in `/opt/MM_D-ND/` includes domain-specific tools
that haven't been ported — `dnd_scenario.py` (projector P¹),
`dnd_autoricerca.py` (domain exploration with null baseline),
`m_spectro.py` (M-matrix spectroscopy), `dnd_incrocio.py` (theory
crossing), and a richer `verify_assertions` set.

Phase 4 of the lab refactor decided to ship the **template** first
and let the physics domain remain a "minimal viable physics" until
needed. Adding any of the above is straightforward: drop the file
into `domains/physics/tools/` and reference it in `config.json`.

## First cycle

Once the install completes:

```bash
docker compose run --rm lab
```

Expect ~5–15 minutes of compute, 5–25 LLM turns. The agent picks one
tension by discriminating power, runs an experiment with code
execution + null baseline, writes a structured report including the
**bicono della scoperta** (radii · singular · invariant · field), and
updates the seed.

A clean cycle output looks like the [example archived in the
production lab](https://lab.d-nd.com/data/lab/reports/) — that's
the same orchestrator doing its work nightly.
