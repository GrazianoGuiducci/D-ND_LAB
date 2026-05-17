# Meta-Lab Autonomous Finance Request — 2026-05-17

Status: observed runtime cycle, not yet full generated-domain install.
Domain request: `finance-reference-autogen`

## Purpose

Test the meta-lab in the mode we actually need: an operator provides a domain
request and the system must turn it into movement without relying on the
operator to hand-write the full spec.

The requested intent was:

```text
Detect when a market-regime hypothesis is not admissible before it becomes an
exposure decision, preserving data-card, baseline/null, trajectory
observability and no trading-signal boundary.
```

## What Happened

### Cycle `20260517_2033`

The first runtime cycle completed without errors, but it did not consume the
new domain request. It continued from the old meta-lab seed direction
`GENERATE_LAB_FINANCE` and retested the existing finance lab.

Observed cause:

```text
plan-domain wrote data/meta-lab/domain_requests/*, but build_field did not
surface pending domain requests in agent_field_live.md and the request was not
inserted into the active seed.
```

Result:

- `domains/finance` still validated as `TEMPLATE_VALID`, 8/8 M1-M8;
- realistic default `exp_regime_shift.py` returned `NO_DELTA`;
- ideal mode remained a sanity check only;
- seed gained the correct constraint:
  `FINANCE_REALISTIC_FALLBACK_COLLAPSE_20260517`.

This was useful as a finance check, but it was not yet an autonomous
domain-request generation test.

### Runtime Repair

The meta-lab request path was made visible to the live field:

- `core.cli plan-domain` now activates the request as a meta-lab seed tension
  by default;
- `core.build_field` can include pending domain requests through
  `domain_requests_path`;
- `domains/meta-lab/config.json` enables that section.

Verified field after repair:

```text
Plan 4 — Process domain request `finance-reference-autogen` ...
## Pending domain requests
- `finance-reference-autogen` ...
## Active tensions
- [DOMAIN_REQUEST_FINANCE_REFERENCE_AUTOGEN] ...
```

### Cycle `20260517_2045`

The second runtime cycle consumed the active request and produced a useful
intermediate result, but still did not create a new installable domain.

Result:

- explored `DOMAIN_REQUEST_FINANCE_REFERENCE_AUTOGEN`;
- tested `domains/finance/tools/lag_memory_precondition.py`;
- found `PRECONDITION_FOUND`;
- selected `score_min=0.50` as maximum-coverage admission gate;
- preserved `score_min=0.55` as conservative boundary;
- kept finance non-operational and non-promotional.

Independent verification:

```bash
python3 domains/finance/tools/lag_memory_precondition.py --json --shuffles 64
python3 domains/finance/tools/finance_reference_audit.py --json
python3 domains/meta-lab/tools/lab_template_validator.py --strict-m7 domains/finance --json
```

Verified outputs:

- precondition verdict: `PRECONDITION_FOUND`;
- selected gate `0.50`: `26` positives, `0` controls;
- conservative gate `0.55`: `19` positives, `0` controls,
  robust-after-precondition `0.8947`;
- finance audit: `reference_ready=true`, no blockers;
- finance validator: `TEMPLATE_VALID`, 8/8 PASS.

## Interpretation

The meta-lab now sees domain requests and can move from them, but the runtime
still behaves like a research cycle over the reference lab, not like an
installer/generator cycle that writes a complete candidate lab package.

Current boundary:

```text
Autonomous request awareness: present.
Autonomous installable-domain generation from request: not yet proven.
```

The 2045 result is still valuable: it confirms that the finance reference
should not tune a failed detector directly. It must use a precondition/admission
gate before any repair, transfer or packaging step.

## Regressive Node

The next gap is not scientific finance evidence. The gap is an orchestration
contract:

```text
domain_request -> spec draft -> preflight M1/M5/M6/M8 -> generator dry-run ->
strict validator -> install or block report
```

At the moment these pieces exist, but the meta-lab runtime does not yet execute
them as a single movement.

## Next Step

Add or wire an explicit meta-lab movement/tool that consumes the active
`domain_request` and produces one of two artifacts:

1. a generated candidate domain in an isolated output path, with strict M1-M8
   validation attached;
2. a block report explaining which M lenses fail and what data/skill/input is
   missing.

Do not judge the meta-lab as complete until a blind domain request can reach
that install-or-block artifact without a hand-written spec.
