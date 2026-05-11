# Lab Domain Roadmap — 2026-05-11

Status: operating plan for public Lab expansion and cron preparation.

## Current Position

The Lab dashboard is no longer only a graph viewer. It is becoming a public
evidence surface:

- `Info` is the orientation entry;
- `Campo` exposes the resultant state;
- `Grafo`, `Bicono`, `Agente`, `Tassonomia`, `Prodotti` are lenses;
- the Lab Assistant receives tab/viewport/selection context;
- visitor proposals can be collected as preports, not promoted automatically.

## Rule

Each Lab must show:

1. what question it is testing;
2. what data/source it used;
3. what survived;
4. what failed;
5. what cannot be claimed yet;
6. what the next cycle should test.

No Lab should be put on cron just because it can run. Cron starts only after a
domain has useful visible output, a clear falsification gate, and no public
claim ambiguity.

## Finance Lab Preparation

Finance is useful as a value-facing demo because it produces concrete tables and
clear boundaries.

Current verified posture:

- Assertions: 5/5 PASS.
- Latest controlled diagnostic: SPY shifted-window report.
- Maturity: `local_robust`.
- Public/trading claim: `false`.
- Operational: `false`.

Fresh controlled run on 2026-05-11:

- `finance_diagnostic_report.py --shuffles 1024 --seed 42`
- output:
  `data/finance/diagnostics/finance_diagnostic_20260511_185107.md`
- result:
  current SPY 3mo `DND_DELTA`; three adjacent shifted 3mo windows `NO_DELTA`.

Additional comparison:

- SPY 3mo: `DND_DELTA`, `effect_z=3.1911`.
- QQQ 3mo: `NO_DELTA`, `effect_z=2.8208`.
- SPY 6mo: `NO_DELTA`, `effect_z=-0.5918`.

Interpretation:

Finance can show the value of the Lab because it demonstrates separation and
collapse in the same view. It is not ready for an operational market claim.

## Finance Before Cron

Before enabling cron:

- add a dashboard card for latest diagnostic reports;
- expose maturity and caveat beside the table;
- make `NO_DELTA` visually valuable, not a failure;
- add a cycle profile for finance that runs diagnostics/reporting first;
- keep autonomous agent cycles supervised until positive-control calibration
  improves and false positives are lower;
- add a public footer note: research method demo, not investment advice.

Suggested cron readiness gate:

```text
ready_for_cron = visible_report
              && explicit_public_caveat
              && no_auto_promotion
              && latest_cycle_status_ok
              && operator_reviewed_seed_direction
```

## Next Lab Candidates

1. `bio-rhythms`
   - Strength: already has data and cycle outputs.
   - Public value: biological time-series as visible signal/noise demo.
   - Risk: medical interpretation boundary must be strict.

2. `editorial`
   - Strength: easy for visitors to understand.
   - Public value: copy/narrative improvement with before/after examples.
   - Risk: can look subjective unless the falsification criteria are explicit.

3. `finance`
   - Strength: strongest perceived value, clear tables, strong caveat.
   - Public value: shows why falsification matters.
   - Risk: must never read as trading signal.

Recommended order:

```text
finance visible diagnostics -> editorial readable demo -> bio-rhythms with strict caveat
```

## Assistant CTA Pattern

The assistant should not ask generic questions. It should induce context-aware
entry:

- On `Info`: "Vuoi capire come leggere questo Lab o proporre un miglioramento?"
- On `Campo`: "Vuoi leggere la risultante o capire cosa manca al prossimo ciclo?"
- On `Grafo`: "Vuoi analizzare un nodo o proporre una relazione da testare?"
- On `Agente`: "Vuoi vedere come il report è stato corretto/falsificato?"
- On `Prodotti`: "Vuoi trasformare una scoperta in candidatura applicativa?"

If the visitor proposes a change, the assistant collects:

- domain;
- data/source;
- hypothesis;
- falsification test;
- constraints;
- expected value;
- contact preference if offered voluntarily.

The output remains a preport until operator review.
