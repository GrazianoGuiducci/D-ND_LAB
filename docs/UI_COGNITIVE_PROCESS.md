# UI Cognitive Process

> Persistenza della consapevolezza per costruire UI di Lab senza perdere il
> movimento del dominio.
>
> Stato: v1, 2026-05-16.

## Purpose

The dashboard is not a set of tabs to copy into every domain. It is a
three-column cognitive frame that each domain fills with the modules needed to
observe, manage and falsify its own movement.

The common dashboard frame stays stable:

```text
left column   -> field state, counters, tensions, alerts, filters
center column -> primary movement view
right column  -> detail, runtime explanation, THIA/context assistant
```

What changes is the domain contract: which modules appear in the frame, which
observables they read, which actions are allowed, and which labels are
forbidden because they would turn a suspension into a false signal.

## Principle

Do not create a different UI by hand for every Lab. Create a cognitive process
that lets the meta-lab choose and generate the right UI contract for the domain.

```text
domain intent
-> domain-native observables
-> tensions and falsifiers
-> null/baseline
-> what the operator must see
-> what the admin may do
-> modules
-> three-column placement
-> E2E: cycle produces data and UI surfaces it
```

The UI must show the Lab's movement, not decorate its output.

## Common Modules

These modules are useful across domains and should remain available to every
Lab, even when a domain chooses not to surface all of them on the first screen.

| module | role |
|---|---|
| `SeedStatus` | current plane, direction, freshness, accepted surface |
| `ActiveTensions` | current tensions and intensities |
| `CycleTimeline` | cycle history, current run, runtime trace links |
| `AgentReports` | generated reports and report state |
| `RuntimeDynamics` | how the cycle moved, tools called, blocked/suspended steps |
| `FalsifierPanel` | flags by lens, veto/suspension reason |
| `NullBaselinePanel` | baseline/null evidence before interpretation |
| `Cemetery` | falsified claims and assumptions that must remain visible |
| `DiscoveryProductPanel` | findings/products only after gates |
| `THIAContextAssistant` | domain-aware assistant grounded in current view |

## Domain-Native Modules

A generated Lab may add modules that only make sense in its domain. These are
not tabs invented from copy; they are surfaces derived from observables and
failure modes.

Examples:

| domain | modules |
|---|---|
| finance | `RegimeMap`, `RiskConstraints`, `BaselineComparison`, `DecisionBounds`, `DataCard` |
| physics | `TheoryCrossing`, `BridgeAudit`, `ZeroPoints`, `ObservableContract` |
| bio-rhythms | `SignalQuality`, `ArtifactFilter`, `SubjectState`, `ClinicalBoundary` |
| ops-decisions | `DecisionTree`, `FailureModes`, `ActionConstraints`, `EscalationMap` |
| editorial | `SourceEchoMap`, `PublishabilityGate`, `NoveltyDensity`, `AudienceFit` |

## UI Contract File

Each new domain should include:

```text
domains/<domain>/ui_contract.json
```

The file is not a visual mockup. It is a machine-readable declaration of how the
domain should be seen and managed inside the shared three-column template.

Minimum fields:

- `schema`: currently `ui_contract.v1`.
- `domain`: domain slug.
- `intent_movement`: what movement the UI must make visible.
- `frame`: `left`, `center`, `right` module placements.
- `common_modules`: common modules used by this domain.
- `domain_modules`: domain-native modules with observables and purpose.
- `admin_actions`: actions allowed from admin surfaces.
- `forbidden_labels`: labels that must not appear before product/legal review.
- `e2e`: checks proving cycle data reaches the UI contract.

Template: `docs/templates/ui_contract.v1.json`.

## Placement Rules

### Left Column

Use for compressed field awareness:

- counters;
- freshness;
- active tensions;
- falsifier counts;
- cimitero count;
- domain-specific alerts;
- filters that change the center view.

The left column should answer: "where is this Lab right now?"

### Center Column

Use for the primary movement of the domain:

- graph if relationships are primary;
- regime map if state shifts are primary;
- timeline if temporal movement is primary;
- crossing/bicono view if oppositions are primary;
- baseline comparison if evidence-vs-null is primary.

The center column should answer: "what movement is being observed?"

### Right Column

Use for detail and explanation:

- selected node/module detail;
- current hypothesis;
- runtime dynamics;
- falsifier reason;
- data card;
- THIA assistant grounded in the selected view.

The right column should answer: "why did the Lab arrive here, and what is not
allowed yet?"

## Admin Actions

Admin actions must be domain-aware and narrow. Examples:

- run a cycle;
- inspect runtime;
- open report;
- ask THIA about the selected state;
- mark a proposal for review;
- inject a reviewed tension only when allowed by the domain contract.

Do not expose broad mutation actions just because the user is admin. A Lab
should be able to correct itself; admin actions should provide observation and
review, not continuous manual steering.

## Anti-Patterns

- Adding one tab per domain without a contract.
- Copying physics labels into finance or another domain.
- Showing a suspension as a signal.
- Showing product language before falsifier/baseline gates.
- Hiding the cimitero because it looks negative.
- Letting THIA answer from generic site context when a domain view is selected.
- Building UI before deciding what the domain must make observable.

## Meta-Lab Requirement

When the meta-lab generates a new domain, it must generate the UI contract after
it has identified:

1. domain-native observables;
2. null/baseline;
3. falsifiers;
4. runtime awareness needs;
5. admin boundaries.

The UI contract is part of M7 transduction integrity. A Lab can run without a
custom UI contract, but it is not yet fully transduced.
