# Assistant Runtime Context

Status: active pattern for Lab Assistant non-structural updates

## Purpose

The Lab Assistant already rebuilds its system prompt on every chat request from
the live Lab filesystem: domain context, seed, latest reports, cimitero and SSP
state.

For non-structural updates that should affect the assistant without a code
change, use runtime overlays:

- `data/assistant_runtime.md` — all domains
- `data/<domain>/assistant_runtime.md` — one domain

These files are ignored runtime data. They are read as advisory context only.

## Boundary

Runtime overlays do not grant side effects. The assistant must not use them to:

- modify seed;
- run cycles;
- inject tensions;
- promote a domain;
- schedule email or newsletter;
- bypass operator review.

Public demo mode remains read-only except for explicit contribution preports.

## Visibility

Use:

```bash
curl http://127.0.0.1:5050/api/domains/finance/assistant_context
```

The endpoint returns freshness metadata, source fingerprints and overlay
presence. It does not expose overlay text.

## Update Rule

Use overlays for temporary orientation, current CTA wording, operator notes or
cycle-specific guidance. Promote repeated or structural rules into docs/code
only after they stabilize.
