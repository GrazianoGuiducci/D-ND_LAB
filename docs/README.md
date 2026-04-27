# Documentation

This directory will host the GitHub Pages docs site (Phase 5). Phase 0
ships only a placeholder.

## Planned structure

```
docs/
├── index.md            # landing — what is D-ND_LAB
├── quickstart.md       # 30-second install + first cycle
├── architecture.md     # the 13 movements + the modus
├── domains/
│   ├── physics.md
│   ├── editorial.md
│   └── extending.md    # how to write your own domain
├── config.md           # config.schema.json walkthrough
├── tools/              # built-in + MCP tool reference
│   └── ...
└── roadmap.md          # phases 0-5 + post-launch
```

## How docs get published

Phase 5 wires GitHub Pages with a static generator (MkDocs Material
candidate — fast, search built-in, dark mode, callouts).
