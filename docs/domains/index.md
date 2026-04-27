# Domains

A *domain* is everything the orchestrator needs to study a specific
field. It lives entirely under `domains/<name>/` and is loaded via
`config.json`.

The lab ships two domains:

- **[Physics](physics.md)** — mathematical physics through D-ND.
  Studies primes, zeta function, GUE, dynamical systems, theory
  crossing TQGE+R. Origin of the codebase.

- **[Editorial](editorial.md)** — the operator's archive. Discriminates
  source from echo, surfaces convergences not yet written, drafts
  publishable copy through the bicono filter and non-dual-copy gate.
  Test that the abstract template works on non-numeric content.

To write your own, see [Extending](extending.md).

## What a domain contains

```
domains/<name>/
├── config.json                  # wiring — which movements, which params, which tools
├── context.md                   # the model — axioms, condensate, anti-patterns, bicono
├── tension_to_category.json     # mapping for semantic_bridge
├── seed_tensions.json           # bootstrap for first cycle
├── tools/                       # domain-specific tools (optional)
│   ├── __init__.py
│   └── <tool>.py                # each exposes build(domain) → ToolEntry
└── corpus/                      # private content (gitignored)
    ├── README.md
    └── .gitkeep
```

The orchestrator loads `config.json`, reads the rest as the config
declares it, and dispatches the cycle. Nothing in `core/` knows
about the domain — domains plug in.
