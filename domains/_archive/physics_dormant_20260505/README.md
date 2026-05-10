# Physics Domain — D-ND Physics Lab

The original autonomous research lab. Studies mathematical physics through
the D-ND model: primes, zeta function, GUE, dynamical systems, theory
crossing TQGE+R (Thermodynamics × Quantum × Gravity × Electromagnetism +
Relativity / Reference frame).

## Status

**Phase 0 — placeholder.** Real content (context.md, tension_to_category.json,
seed_tensions.json, domain tools) ports from `/opt/MM_D-ND/tools/` in Phase 1.

The original physics lab continues to run in production at
[lab.d-nd.com](https://lab.d-nd.com) — this directory will become the
portable, refactored version once Phase 1 is complete. Until then, the
production lab is the source of truth.

## What goes here (target structure)

```
physics/
├── config.json              # this domain's wiring (current file)
├── context.md               # axioms + condensate + anti-patterns + bicono examples
├── tension_to_category.json # mapping: tension → TQGE+R category for semantic bridge
├── seed_tensions.json       # initial tensions for first cycle
├── tools/                   # domain-specific tools (dnd_*.py)
│   ├── dnd_scenario.py      # projector P¹
│   ├── dnd_autoricerca.py   # domain exploration with null baseline
│   ├── dnd_incrocio.py      # theory crossing
│   ├── m_spectro.py         # M-matrix spectroscopy on sequences
│   └── ...
└── corpus/                  # reference papers, condensate (gitignored if private)
```
