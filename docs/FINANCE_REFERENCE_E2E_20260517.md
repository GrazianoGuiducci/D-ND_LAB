# Finance Reference E2E — 2026-05-17

Status: reference surface for the finance Lab and future meta-lab comparison.
Domain: `finance`

## Intent

The finance Lab is not a trading system and does not predict prices. Its value
is to detect when a market-regime hypothesis is not admissible before it
becomes an exposure decision.

Operational question:

```text
What claim is alive, what claim is dead, and what decision is not allowed?
```

## Reference Movement

The current finance E2E is useful because it produced a constrained negative
result rather than a market story.

1. Synthetic detector work found a provisional promotion boundary.
2. Real-market transfer narrowed an apparent signal to SPY only.
3. Exact-window transfer rejected the correlated-equity cluster narrative.
4. Recurrence testing rejected the SPY locality as recurring evidence.
5. Trajectory observability was repaired so stale continuation can be audited.

This makes finance a reference Lab for the meta-lab: it shows how a domain Lab
must preserve failure, boundary, nulls, runtime trace and next allowed motion.

## Crystallized Boundary

Source cycle: `20260517_1050`

Current synthetic precondition:

```text
matched_filter_score_at_candidate_split >= 0.55
```

Meaning:

- provisional promotion boundary;
- not a hard evidence boundary;
- not a market claim;
- not a trading signal.

Counts to preserve:

- admitted positives: `26/36`;
- admitted robust positives: `21/26`;
- rejected positives: `10/36`;
- rejected robust positives: `2/10`;
- selected controls: `0/108`;
- control robust all-null: `1/108`.

Below-gate robust survivors must remain visible. They cannot be tuned away or
rescued by another layer unless a new measurable mechanism is declared before
testing.

## Real-Market Transfer Result

Reference artifacts in the live runtime:

```text
data/finance/diagnostics/finance_transfer_diagnostic_20260517_133933.json
data/finance/diagnostics/finance_recurrence_diagnostic_20260517_134619.json
```

Transfer result:

- SPY passes iid/block5 but fails block21;
- QQQ exact same-window rejects;
- IWM, EFA, TLT, GLD and BTC-USD reject;
- classification: `single_or_partial_window`;
- `public_claim=false`;
- `trading_signal=false`.

Recurrence result:

- current SPY passes iid/block5 but fails block21;
- three prior exact windows reject across iid/block5/block21;
- classification: `current_iid_partial`;
- `operational=false`;
- `public_claim=false`;
- `trading_signal=false`.

Conclusion:

```text
The same SPY current-window premise is exhausted.
```

The next finance work must not relaunch transfer or recurrence on the same SPY
premise. It must either crystallize the detector locality limit as a reference
constraint or predeclare a materially new object/mechanism with its own
falsifier.

## Trajectory Observability

Source cycle: `20260517_1409`

The finance reference audit now emits path/state evidence:

- seed path;
- trajectory log path;
- trajectory state path;
- latest diagnostic path;
- latest consumed log cycle;
- latest state cycle;
- resolved next direction source.

This matters because `REAL_MARKET_TRANSFER_DIAGNOSTIC` is a policy name, not
permission to repeat a stale branch. Future cycles must inspect the resolved
direction and the diagnostic artifact before selecting the next movement.

If the live trajectory state is `pending`, it is live runtime state and should
not be rewritten by documentation work. The installable reference is the
contract above: no stale SPY recurrence relaunch, no market claim, and no
single-window authority.

## Next Allowed Finance Movement

Allowed:

- a new object or mechanism declared before the run;
- a new target variable with explicit nulls and stop rule;
- a meta-lab comparison using this finance E2E as reference;
- a documentation or UI pass that makes the boundary legible.

Not allowed:

- rerunning the same SPY current-window transfer;
- promoting `current_iid_partial`;
- interpreting iid/block5 without block21 as operational;
- hiding below-gate survivors;
- using buy/sell/forecast/profit/alpha language.

## Meta-Lab Comparison Lenses

When the meta-lab regenerates a finance-like Lab, compare against this
reference:

- intent is a decision constraint, not a prediction;
- every claim has data-card, baseline and null;
- synthetic boundaries stay provisional;
- exceptions remain visible;
- stale trajectory continuation is observable;
- UI exposes regime gate, baseline/null, data-card, non-admissible decision,
  promotion boundary, runtime trace and cemetery.

Passing this comparison does not mean the generated Lab is correct. It means it
preserved the movement logic that made the reference finance Lab useful.
