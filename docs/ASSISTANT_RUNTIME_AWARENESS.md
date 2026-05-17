# Assistant Runtime Awareness

Status: active dashboard pattern, public demo safe by default.

## Topology

The Lab currently has two assistant runtime paths/surfaces that must not
collapse into one ambiguous role.

- `THIA/Lab Dashboard Assistant`: dashboard-local assistant path for
  `/dashboard/`.
  It owns dashboard grounding: active domain, active tab, visible section,
  selected graph node, selected SSP discovery/product, report/cemetery tools,
  contribution pre-report collection and read-only demo boundaries. It speaks
  as THIA/Lab Assistant when the dashboard chat endpoint is used.
- `THIA/DOMUS public widget`: public orientation surface on `lab.d-nd.com`.
  It owns navigation, narrative pages, funnel explanation, site-level context,
  human/contact routing and general orientation across the Lab subdomain.

Routing rule:

```text
Use the THIA/Lab Dashboard Assistant for domain/dashboard/cycle/report/SSP details.
Use THIA/DOMUS for public orientation, page navigation and system-level context.
Do not duplicate ownership between the two.
```

The boundary is not "THIA vs no THIA". The boundary is which runtime path was
grounded and verified. If the dashboard LLM adapter is not configured, the
finance promotion-boundary card can still be answered by a deterministic local
fallback before the public THIA fallback is attempted for broader demo chat.

For the broader ecosystem boundary between the main-site physics Lab, the Lab
subdomain, the installable repo/meta-lab and concrete domain Labs, see
[LAB_SURFACE_TOPOLOGY.md](LAB_SURFACE_TOPOLOGY.md).

## Runtime Context

The dashboard sends a structured `context_view` with:

- `focus_marker`: the section the user is likely seeing;
- `visible_markers`: compact stack of nearby perceptual sections;
- `open_elements`: chat panel, selected graph node, selected SSP discovery or
  product;
- `surface_history`: last session surfaces, so the assistant can infer what the
  user may already have seen;
- `assistant_topology`: explicit double-assistant boundary.

The backend injects those fields into the chat system prompt. They are grounding
signals, not proof of hidden UI state. If evidence matters, the assistant must
use read tools or ask a targeted question.

## Demo Boundary

In public demo mode the assistant may:

- explain current state;
- read reports/falsifier/seed through server-side read tools;
- collect and organize proposals as candidate pre-reports.

It must not:

- save structural changes;
- run cycles;
- activate email automations;
- promote a visitor proposal without operator review.

## Installable Direction

For external Lab installations, the same runtime contract can become the DOMUS
or Lab Assistant adapter:

```text
page marker + visible section + selected object + session history + assistant
topology -> prompt context -> safe action boundary
```

The provider chain remains a separate concern:

```text
Codex -> Claude Code -> OpenRouter/OpenAI-compatible HTTP fallback
```
