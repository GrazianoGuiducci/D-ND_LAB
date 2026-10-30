# Physics domain in the installable D-ND_LAB engine

This domain preserves the earlier D-ND mathematical-physics research line in
an installable domain contract. It is separate from the current regenerative
MM-DND Lab at [d-nd.com/ai-lab](https://d-nd.com/ai-lab).
The [public companion](https://github.com/GrazianoGuiducci/dnd-lab-physics)
explains the current Lab and provides offline corpus tools.

## Shipped domain and historical research

`domains/physics/` contains configuration, context, seed tensions, category
mapping, assertions, experiment tools and a dated May 2026 bootstrap.
Historical subjects include prime gaps, zeta and spectral statistics,
dynamical systems and theory-crossing questions. Claims and vocabulary in
the preserved context belong to those historical sources; they are not a
new blanket validation of their mathematical or physical interpretation.

The earlier guide described this as a minimal placeholder and listed tools
that were not yet ported. At the inspected source, `tools/dnd_autoricerca.py`
and many experiment scripts are shipped. The directory itself is the
authoritative inventory. Historical plan language does not describe the
current package's file coverage.

## Configuration

`domains/physics/config.json` names this engine domain and its input files.
At the 30 October 2026 reconciliation:

- `sync` and `verify_endpoints` are disabled;
- structural checking is configured to inject META tensions;
- the trajectory evaluator is configured with `execute: false, log_only: true`;
- `verify_assertions` is enabled without an explicit `assertions_module`
  parameter in this domain config.

These are configuration facts, not evidence of an executed provider cycle or
of the current MM-DND regenerative implementation. Changes to engine execution
must follow the engine's own code and installation contracts.

## Bootstrap and installation

The tracked `bootstrap_20260516/` snapshot contains evidence from five dated
historical cycles. The [repository README](../../README.md) and
[installation procedure](../INSTALL_PROCEDURE.md) describe restoration and
engine setup. Preserve those records as historical evidence; do not overwrite
an existing operational domain to compare it with another distribution.

The engine expects `domains/<domain>/config.json`. Its own shipped physics
domain meets that layout. A clone of the standalone dnd-lab-physics repository
has a nested `domain/config.json` and is not a drop-in replacement at the
clone root. See [reconciliation](../PHYSICS_LAB_RECONCILIATION.md).

## Scientific and operational scope

A domain installation, schema check or script PASS does not establish a
physical law. Independent reproduction requires the actual input, method,
controls, scope and invalidators. The current regenerative Lab's field,
occurrence and memory contracts have a different source owner and are not
activated by running this engine.
