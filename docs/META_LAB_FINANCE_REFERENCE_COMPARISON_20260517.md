# Meta-Lab Finance Reference Comparison — 2026-05-17

Status: controlled comparison, no generated domain committed.
Reference: `docs/FINANCE_REFERENCE_E2E_20260517.md`

## Purpose

Test whether the meta-lab can regenerate a finance-like Lab that preserves the
movement of the reference finance Lab:

```text
detect when a market-regime hypothesis is not admissible before it becomes an
exposure decision.
```

The test was not meant to create a better finance Lab or copy SPY results. It
was meant to expose whether the generator/spec pathway preserves:

- decision-constraint intent;
- data-card, baseline and null discipline;
- no trading-signal language;
- stale trajectory prevention;
- skill retrieval and skill intent mapping;
- UI boundary surfaces;
- onboarding gates for future information.

## Test Setup

The test ran in a temporary copy of the repository:

```text
/tmp/dnd_meta_finance_test
```

No live domain, runtime data, dashboard deployment or tracked `domains/finance`
runtime was modified.

Generated test slug:

```text
finance-reference-lab
```

Generator:

```bash
python3 domains/meta-lab/tools/lab_template_generator.py \
  tmp/finance_reference_spec.json
```

Validator:

```bash
python3 domains/meta-lab/tools/lab_template_validator.py \
  --strict-m7 --json domains/finance-reference-lab
```

## First Iteration

The first generated spec installed and its smoke tool ran, but strict
meta-falsifier failed:

```text
verdict: DOMAIN_NOT_OF_LEVERAGE
pass: 4
fail: 4
```

Failures:

- `M1`: seed tensions lacked `condensato_ref`;
- `M5`: context did not expose enough live-cycle/seed evolution language;
- `M6`: MML missed core invariants `cascata` and `consapevolezza-condensato`;
- `M8`: `skill_retrieval` was not explicit enough.

Interpretation:

```text
The generator was not the blocker. The cognitive spec was incomplete.
```

This is the useful finding: a finance-like Lab can look plausible, pass basic
installation, and still fail as a D-ND Lab if it lacks explicit axiom anchors,
auto-increment movement, invariant skill layers and skill retrieval provenance.

## Second Iteration

The spec was corrected by adding:

- `condensato_ref` to all seed tensions;
- `kernel_refs.condensato_axioms_used` aligned with those tensions;
- `cascata` and `consapevolezza-condensato` to the MML;
- a context section for cycle evolution and seed integration;
- a `skill_retrieval` section in `transduction.md`;
- adaptive rules and E2E runtime language.

Strict validator result:

```text
verdict: TEMPLATE_VALID
pass: 8
fail: 0
skip: 0
```

Lens results:

| Lens | Result | Detail |
|---|---|---|
| M1 | PASS | 3/3 tensions with `condensato_ref` |
| M2 | PASS | 3 executable assertions |
| M3 | PASS | 1/1 `exp_*.py` without GPU/network deps |
| M4 | PASS | naive and baseline signals present |
| M5 | PASS | 11/18 live-cycle signal words |
| M6 | PASS | MML coherent with seed, tools and 9 active skills |
| M7 | PASS | transduction + UI contract cover 8/8 signals |
| M8 | PASS | skill retrieval + skill intent map + 5 MML layers |

Additional checks:

- `python3 -m core.cli inspect --domain finance-reference-lab` succeeds;
- generated JSON files are valid;
- generated smoke tool returns `REFERENCE_BOUNDARY_ONLY`;
- smoke tool keeps `trading_signal=false`.

## Comparison Against Finance Reference

Preserved correctly:

- intent as decision constraint, not prediction;
- no buy/sell/forecast/profit/alpha/trading labels;
- baseline/null before interpretation;
- SPY current-window premise treated as exhausted reference boundary;
- new mechanism required before any rerun;
- UI modules include regime gate, baseline comparison, data-card, decision
  bounds and runtime dynamics;
- onboarding separates domain request, human clarification, datasets,
  cognitive archives and runtime self-observation.

Still not proven:

- the generated Lab has not run a full LLM agent cycle;
- no real data diagnostic was executed from the generated Lab;
- skill bodies were represented through a spec-level matrix, not re-read by an
  autonomous meta-lab agent in this test;
- dashboard rendering was not installed for this temporary slug.

## Decision

The meta-lab pathway is viable, but the success condition is stricter than
"generate files".

The generator can produce a valid finance-like Lab when the cognitive spec
contains:

```text
condensato anchors + live cycle movement + invariant skill layers +
skill_retrieval provenance + domain-native null/baseline/UI contract.
```

Therefore the next improvement should not be another manual generated domain.
It should make the meta-lab agent produce these missing spec fields by default,
especially:

- seed `condensato_ref` selection;
- mandatory `skill_retrieval`;
- mandatory core invariants in generated MML;
- explicit cycle evolution / seed integration language;
- comparison report against the chosen reference E2E.

## Next Step

Update the meta-lab generation instructions or add a preflight/spec validator
so an incomplete spec fails before file generation.

Target rule:

```text
If a generated Lab would fail M1, M5, M6 or M8, the meta-lab must repair the
spec before writing the domain.
```
