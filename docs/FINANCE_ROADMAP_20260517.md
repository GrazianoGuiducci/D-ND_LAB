# Finance Lab Roadmap — 2026-05-17

Status: roadmap after synthetic promotion-boundary crystallization
Domain: `finance`
Current policy: `CRYSTALLIZE_PROMOTION_BOUNDARY`

## Where We Are

The finance Lab has closed the first useful synthetic phase:

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

## Tabella Di Marcia

| Step | Goal | Entry Gate | Work | Exit Gate | Output |
|---:|---|---|---|---|---|
| 1 | Close synthetic promotion boundary | Cycle `20260517_1050` complete; falsifier correction applied | Preserve gate, survivor counts and non-hard-boundary rule in contracts/UI/docs | Audit returns `CRYSTALLIZE_PROMOTION_BOUNDARY`; dashboard shows gate and survivors | Current state, done |
| 2 | Check THIA/context grounding | Dashboard card visible; `/precondition_contract` returns `200` | Ask THIA about gate, survivor exceptions, and what is not promotable | THIA answers: provisional threshold, `2/10` survivors visible, no trading signal | Done via deterministic boundary fallback |
| 3 | Choose next branch | Step 1 done; Step 2 acceptable or explicitly skipped | Decide one branch: real-market transfer, meta-lab comparison, or new synthetic object | Branch documented before execution | Branch packet / direction |
| 4A | Real-market transfer | Branch chosen; no synthetic ambiguity hidden | Test SPY/BTC/FX with data-card, iid/block nulls, VaR/RV baselines | No market claim unless real-data nulls and baselines pass | Real-data report, likely `SOSPENSIONE` first |
| 4B | Meta-lab comparison | Branch chosen; finance reference stable | Ask meta-lab to regenerate finance-like Lab from intent/domain | Generated Lab preserves contracts, nulls, UI boundary, survivor handling | Comparison report and meta-lab improvements |
| 4C | New synthetic object | Branch chosen; new mechanism predeclared | Define target variable and falsifier before running a cycle | New object beats controls without rescuing old rejected cases silently | New synthetic candidate or rejection |
| 5 | Product/readiness gate | One branch produces replicated value | Add cost/slippage, double replication, review and packaging gates | Product-stage evidence exists | Candidate kernel or explicit stop |

## Recommended Next Step

Step 2 is now done. The dashboard chat has a deterministic boundary fallback,
so the finance card can be explained even when the LLM adapter is not
configured.

Next do **Step 3** before another Lab cycle:

```text
Choose one branch: real-market transfer, meta-lab comparison, or new synthetic object.
```

Verified THIA/UI answer:

- gate is `score >= 0.55`;
- it is provisional and synthetic;
- admitted robust positives are `21/26`;
- below-gate survivors are `2/10`;
- survivors stay visible;
- no buy/sell/forecast/profit/alpha labels;
- no sub-gate rescue without a new predeclared mechanism.

If this passes, choose between:

1. **Real-market transfer** if we want practical finance value now.
2. **Meta-lab comparison** if we want to test whether the meta-lab can
   regenerate this kind of Lab without losing fine logic.

## Branch Details

### Branch 4A — Real-Market Transfer

Purpose: test whether the admitted-gate behavior survives real market data.

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
- the dashboard/THIA cannot explain what is not promotable.

## Standing Boundary

No finance output is a trading signal. Do not use `buy`, `sell`, `forecast`,
`profit`, or `alpha signal` labels until a product-stage verification exists
with real-data gates, robust nulls, slippage/cost baselines, and explicit
review.
