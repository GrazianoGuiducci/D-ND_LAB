# Finance Lab Roadmap — 2026-05-17

Status: roadmap after finance reference E2E and trajectory observability repair
Domain: `finance`
Current policy: `REFERENCE_E2E_READY_FOR_META_LAB_COMPARISON`

## Where We Are

The finance Lab has closed the first useful synthetic phase and one
value-facing real-market E2E:

- score threshold: `matched_filter_score_at_candidate_split >= 0.55`;
- admitted positives: `26/36`;
- admitted robust positives: `21/26`;
- rejected positives: `10/36`;
- rejected robust positives: `2/10`;
- selected controls: `0/108`;
- control robust all-null: `1/108`;
- UI exposes the boundary in `Campo -> Lente finance -> Soglia di promozione`.

Meaning:

```text
The threshold is a provisional synthetic promotion boundary, not a hard
evidence boundary and not a market signal.
```

The real-market lane then narrowed an apparent SPY/QQQ signal into a
non-operational SPY locality artifact:

- exact-window transfer: SPY iid/block5 pass, block21 fail; QQQ and controls
  reject;
- recurrence: current SPY iid/block5 pass, block21 fail; three prior exact
  windows reject;
- class: `current_iid_partial`;
- public claim: `false`;
- trading signal: `false`.

Reference doc:

```text
docs/FINANCE_REFERENCE_E2E_20260517.md
```

## Tabella Di Marcia

| Step | Goal | Entry Gate | Work | Exit Gate | Output |
|---:|---|---|---|---|---|
| 1 | Close synthetic promotion boundary | Cycle `20260517_1050` complete; falsifier correction applied | Preserve gate, survivor counts and non-hard-boundary rule in contracts/UI/docs | Audit returns `CRYSTALLIZE_PROMOTION_BOUNDARY`; dashboard shows gate and survivors | Current state, done |
| 2 | Check THIA/Lab Assistant context grounding | Dashboard card visible; `/precondition_contract` returns `200` | Ask the THIA/Lab Dashboard Assistant about gate, survivor exceptions, and what is not promotable | THIA/Lab Assistant answers: provisional threshold, `2/10` survivors visible, no trading signal | Done via deterministic boundary fallback |
| 3 | Choose next branch | Step 1 done; Step 2 acceptable or explicitly skipped | Decide one branch: real-market transfer, meta-lab comparison, or new synthetic object | Branch documented before execution | Selected: 4A real-market transfer before meta-lab comparison |
| 4A | Real-market transfer | Branch chosen; no synthetic ambiguity hidden | Test SPY/BTC/FX with data-card, iid/block nulls, VaR/RV baselines | No market claim unless real-data nulls and baselines pass | Done as negative E2E: `current_iid_partial`, no market claim |
| 4B | Meta-lab comparison | Finance reference stable; no stale SPY rerun pending | Ask meta-lab to regenerate finance-like Lab from intent/domain | Generated Lab preserves contracts, nulls, UI boundary, survivor handling and trajectory observability | Next recommended comparison report and meta-lab improvements |
| 4C | New synthetic object | Branch chosen; new mechanism predeclared | Define target variable and falsifier before running a cycle | New object beats controls without rescuing old rejected cases silently | New synthetic candidate or rejection |
| 5 | Product/readiness gate | One branch produces replicated value | Add cost/slippage, double replication, review and packaging gates | Product-stage evidence exists | Candidate kernel or explicit stop |

## Recommended Next Step

Step 2 is now done for the **THIA/Lab Dashboard Assistant** runtime path. The
dashboard chat speaks as THIA/Lab Assistant and has a deterministic finance
boundary fallback, so the finance card can be explained even when the dashboard
LLM adapter is not configured.

This does **not** verify or modify the public THIA/DOMUS widget runtime path.
The public widget exists as another THIA-facing surface and must be checked
separately if the next task concerns public navigation or public assistant
behavior.

Step 4A is complete as a negative/constraint E2E:

```text
current_iid_partial; operational=false; public_claim=false; trading_signal=false.
```

Verified THIA/Lab Assistant/UI answer:

- gate is `score >= 0.55`;
- it is provisional and synthetic;
- admitted robust positives are `21/26`;
- below-gate survivors are `2/10`;
- survivors stay visible;
- no buy/sell/forecast/profit/alpha labels;
- no sub-gate rescue without a new predeclared mechanism.

Rationale: finance has now completed one autonomous value-facing E2E before the
meta-lab generator is judged against it. The next recommended step is 4B:
meta-lab comparison against `docs/FINANCE_REFERENCE_E2E_20260517.md`.

## Branch Details

### Branch 4A — Real-Market Transfer

Purpose: test whether the admitted-gate behavior survives real market data.

Current artifact:

```text
data/finance/diagnostics/finance_recurrence_diagnostic_20260517_134619.json
```

Exact-window transfer result (`2026-02-09..2026-05-09`, 4096 shuffles):

- SPY: iid `DND_DELTA`, block5 `DND_DELTA`, block21 `NO_DELTA`;
- QQQ: same exact window `NO_DELTA` at iid/block5/block21;
- IWM/EFA/TLT/GLD/BTC-USD: `NO_DELTA`;
- class: `single_or_partial_window`;
- boundary: `operational=false`, `public_claim=false`, `trading_signal=false`.

This corrects the previous adjacent-window narrative: QQQ adjacent-window pass
is useful history, but it is not authority for exact-date transfer. The next
cycle must cite the exact-window JSON and explain the collapse without
promoting a market claim.

SPY recurrence result (`current` plus three previous 3-month exact windows,
4096 shuffles):

- current SPY: iid/block5 pass, block21 rejects;
- previous three SPY windows: iid/block5/block21 reject;
- class: `current_iid_partial`;
- boundary: `operational=false`, `public_claim=false`, `trading_signal=false`.

This means Branch 4A has produced value as a negative/constraint E2E: the lab
found and then narrowed an apparent opportunity until only a non-operational
method limit remained. The limit is crystallized in
`docs/FINANCE_REFERENCE_E2E_20260517.md`.

Do not relaunch transfer or recurrence on the same SPY current-window premise.
If a future runtime surface still says `REAL_MARKET_TRANSFER_DIAGNOSTIC`, read
it as policy context only: the actual next movement must be either a materially
new object/mechanism with predeclared falsifier or the meta-lab comparison.

Minimum test:

- assets: at least `SPY`, `BTC`, and one FX major pair if data tool supports it;
- data-card required: provider, source, retrieval timestamp, window, n_obs;
- nulls: iid shuffle and block-preserving null;
- baselines: realized volatility, VaR/RV, random walk where available;
- output: `NO_DELTA`, `REVIEW_REQUIRED`, or synthetic-to-real `DND_DELTA_CANDIDATE`;
- forbidden: trading signal language.

### Branch 4B — Meta-Lab Comparison

Purpose: test whether the meta-lab can regenerate a finance Lab from intent
without copying results or losing the movement logic.

Comparison lenses:

- does it define an intent as decision-constraint, not prediction?
- does it preserve baseline/null first?
- does it create a precondition before tuning?
- does it keep survivor exceptions visible?
- does its UI contract show boundary, data-card, falsifier and runtime?
- does it avoid copying the exact `0.55` metric unless justified by generated
  tools?

### Branch 4C — New Synthetic Object

Purpose: continue synthetic research only if a new mechanism is defined.

Allowed only if the cycle states before testing:

- what new object/target variable is being measured;
- why it is not a rescue of the rejected `10/36`;
- what null falsifies it;
- what result would stop the branch.

## Stop Rules

Stop or redesign if:

- controls exceed the 5% selection/robust ceiling;
- below-gate survivors are hidden or reinterpreted away;
- a report uses hard-boundary language again;
- a real-data test lacks data-card or baseline/null;
- the THIA/Lab Assistant runtime cannot explain what is not promotable.

## Standing Boundary

No finance output is a trading signal. Do not use `buy`, `sell`, `forecast`,
`profit`, or `alpha signal` labels until a product-stage verification exists
with real-data gates, robust nulls, slippage/cost baselines, and explicit
review.
