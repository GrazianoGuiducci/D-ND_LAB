# Domain Presets

> Preset riusabili per accelerare la nascita di nuovi Lab senza sostituire la
> transduzione del meta-lab.
>
> Stato: v1, 2026-05-16.

## Purpose

A domain preset is not a generated Lab. It is a starter grammar for a family of
domains: typical observables, null/baseline, falsifiers, UI modules, admin
boundaries and E2E checks.

The preset accelerates installation, but the meta-lab must still transform it
through the concrete domain request and produce:

- `context.md`;
- `seed_tensions.json`;
- `transduction.md`;
- `ui_contract.json`;
- `assertions.py`;
- initial tools;
- `mml.json`.

The validator remains the authority. A preset that passes through unchanged is
usually a contamination signal.

## Contract

Template:

```text
docs/templates/domain_preset.v1.json
```

Preset directory:

```text
docs/templates/domain_presets/
```

Minimum fields:

- `schema`: currently `domain_preset.v1`.
- `preset_id`: stable identifier, e.g. `finance_regime.v1`.
- `domain_family`: broad family, not final slug.
- `use_when`: when this preset is a good accelerator.
- `do_not_use_when`: cases where the preset would contaminate the request.
- `starter_observables`: typical measurements or domain objects.
- `starter_baselines`: nulls, naive baselines or control groups.
- `starter_falsifiers`: common ways a claim should fail.
- `starter_ui_modules`: common and domain-native UI modules to consider.
- `admin_boundaries`: allowed/forbidden admin operations.
- `forbidden_labels`: words/actions to avoid before gates.
- `e2e_checks`: minimum operational checks.
- `adaptation_questions`: questions the meta-lab must answer before generation.

## Existing Presets

| preset | use |
|---|---|
| `finance_regime.v1` | regime shift, risk constraints, baseline-vs-null |
| `physics_bridge.v1` | theory crossings, bridge audits, observable contracts |
| `bio_signal.v1` | biosignal regimes, artifact filtering, subject state |
| `ops_decision.v1` | complex decisions, failure modes, action constraints |
| `editorial_discovery.v1` | insight mining, source echo, publishability gates |

## Rule

Use a preset only as a hypothesis about useful structure. The actual Lab must
derive its movement from the request, data and domain constraints.

Good use:

```text
domain_request + preset -> adapted transduction -> ui_contract -> validator
```

Bad use:

```text
preset -> copied Lab
```

If the preset vocabulary becomes more visible than the domain's own
observables, the meta-lab should suspend generation and ask for more context or
produce a narrower first cycle.
