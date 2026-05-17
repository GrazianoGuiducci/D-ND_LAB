# Finance Lab — Practical Use Case

> Status: alpha contract, 2026-05-17.
> Purpose: make the finance Lab usable as a pragmatic, self-evolving system
> without turning it into trading advice or narrative prediction.

## Intent

The Finance Lab does not predict prices and does not produce buy/sell signals.

Its intent is:

```text
detect when a market-regime hypothesis fails before it becomes an exposure
decision.
```

The useful output is not "the market will go up/down". It is a falsifiable
decision constraint:

- this regime hypothesis is not admissible;
- this detector has no recoverable power yet;
- this baseline/null defeated the claim;
- this precondition must be measured before another cycle;
- this candidate survived enough controls to become a research object.

## Practical User Value

The Lab is valuable when an operator, researcher or risk team has a question
such as:

```text
Does this asset/window show a structural bull/bear regime shift, or are we
reading delayed volatility and hindsight noise?
```

The Lab answers by comparing ordered market data against nulls and naive
baselines. It should help users avoid false regime stories before they become
portfolio, research or product decisions.

## How To Use It

1. Define a hypothesis.

   Example: "SPY over the last 6 months has entered a structural downside
   regime."

2. Declare the decision boundary.

   Example: "This must not become an exposure signal unless it survives
   ordered-vs-null, VaR/RV baseline and at least one adjacent-window check."

3. Load data through a data-carded source.

   Current sources: `yfinance` for stocks/ETF/indices and `coingecko` for
   crypto, both through `tools/market_data.py`. Synthetic fallback remains
   valid for method checks.

4. Run a detector or a full cycle.

   Current detector: `tools/exp_regime_shift.py`.
   Reference audit before cycle: `tools/finance_reference_audit.py`.

5. Read the verdict as a constraint, not as a trade.

   - `NO_DELTA`: do not treat the hypothesis as regime evidence.
   - `DND_DELTA`: candidate structural delta; replicate before promotion.
   - `REVIEW_REQUIRED`: data, null or precondition missing.
   - `NON_ADMISSIBLE`: the claim must not be promoted.

6. Let the failure update the next question.

   Repeated `NO_DELTA` does not mean "add a parameter". It means the Lab must
   identify the measurable precondition that could make recoverable power
   possible.

## Information Consumed

Required or useful inputs:

- ordered time series: close prices, log returns, dates, volume when useful;
- data-card: provider, source, retrieval time, window, frequency, n_obs,
  license or usage boundary;
- baseline: static VaR, realized volatility, random walk or naive detector;
- null: shuffle, block-preserving null, adjacent shifted windows, target-minus
  controls;
- operator constraints: horizon, asset universe, cost/slippage assumptions,
  prohibited decisions and acceptable evidence;
- Lab memory: previous reports, falsifier flags, runtime traces, cemetery,
  trajectory and seed state;
- optional corpus/contributions: only through onboarding, quarantine and
  pre-report gates.

## What Counts As Useful

Useful finance output has one of these forms:

- a rejected hypothesis with a clear reason;
- a detector precondition that can be tested next;
- a comparison where D-ND adds measurable value over VaR/RV/null;
- a data or leakage flaw that blocks promotion;
- a candidate kernel component that survives replication.

Not useful:

- price forecasts;
- unsupported regime labels;
- single-window authority;
- language implying financial advice;
- parameter tuning that hides a failed assumption.

## Autological Rule

The Lab improves when it converts its own failure into a sharper constraint.

```text
If the cycle produces more interpretation than constraints, it is drifting.
If the cycle turns a failed detector into a measurable precondition, it is
evolving.
```

Current reference policy:

```text
DESIGN_PRECONDITION_FIRST
```

Therefore the next strong finance cycle should not tune the same score family.
It should design and test the missing precondition for recoverable power
against VaR/RV and block-preserving nulls.

Current precondition tool:

```bash
python3 domains/finance/tools/lag_memory_precondition.py --json
```

This tool asks whether `lag_memory_const_vol` has enough local matched-filter
structure before another block21 admission or aggregation cycle is allowed. It
does not authorize a market claim.

Current selected precondition:

```text
matched_filter_score_at_candidate_split >= 0.55
```

Source: `domains/finance/precondition_contract.json`. The next allowed
movement is to test this as an admission gate, not to broaden tuning.

## UI Implications

The finance dashboard should make these surfaces visible before any narrative:

- Regime Gate: current verdict and admissibility;
- Baseline / Null: what defeated or supported the claim;
- Data-card: source, window and leakage boundary;
- Non ammissibile: what the user must not infer;
- Cycle trace: how the Lab reached the result;
- Cemetery: useful false positives and retired assumptions.

The UI is successful when a domain user can answer:

```text
What claim is alive, what claim is dead, and what decision is not allowed?
```
