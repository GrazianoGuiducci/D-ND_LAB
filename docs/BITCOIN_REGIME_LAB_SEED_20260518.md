# Bitcoin Regime Lab Seed — 2026-05-18

Status: continuity note, not an installed Lab.
Candidate slug: `bitcoin-regime-lab`.

## Intent

Build a public-facing Lab that monitors Bitcoin as a regime object and
falsifies operational hypotheses before they become decisions.

The Lab should not start as a trading-signal system. Its first value is:

```text
Show what can and cannot be inferred about BTC regime state under current
data, baselines, nulls, friction and falsifier pressure.
```

## Why Bitcoin

Bitcoin is a useful first public domain after physics/finance because:

- it has high public attention;
- data is accessible and auditable enough for a first Lab;
- regime changes are intuitive to humans;
- simple baselines are available;
- the domain can attract expert/human review without promising advice.

## Human Continuity

Operator note: Alipio may be willing to follow the Bitcoin Lab once there is a
working object to monitor and falsify.

Role suggestion for Alipio:

- domain observer, not authority over the seed;
- helps identify real questions, sources, techniques and interpretive mistakes;
- reviews whether reports are useful to a human following BTC;
- may contribute methods or references after the Lab has an intake path.

Operator also mentioned Massimo Rea as a possible source of methods discussed
by Alipio. This is currently unverified context, not a Lab source. Before any
method enters the seed, the Lab must ask:

- what is the method exactly?
- where is it documented?
- what observable does it claim to expose?
- what null/baseline attacks it?
- what failure mode would falsify it?

## Boundary

Forbidden early labels:

- buy;
- sell;
- guaranteed profit;
- price target;
- trading signal;
- financial advice;
- alpha.

Allowed early labels:

- regime hypothesis;
- stress condition;
- watch condition;
- rejected pattern;
- baseline comparison;
- non-admissible inference;
- next test.

Public disclaimer should be structural, not decorative:

```text
This Lab does not provide financial advice or buy/sell signals. It tests and
falsifies hypotheses about BTC regime conditions and shows when evidence is
not sufficient for an operational claim.
```

## First Useful Questions

The Lab should initially answer questions like:

- Is the current BTC movement distinguishable from simple return baselines?
- Is a perceived regime shift robust across window choices?
- Does a signal survive shuffled returns and block-preserving nulls?
- Does it disappear under cost, spread or latency assumptions?
- Is the current observation a repeatable regime or a local artifact?
- What should not be inferred from this cycle?

## Initial Observables

Starter observables:

- log returns;
- realized volatility;
- drawdown and recovery path;
- range/trend persistence;
- volume or liquidity proxy, if source quality is acceptable;
- volatility clustering;
- correlation to broad risk proxy, if data source is auditable;
- event/date card when a window is chosen.

Every data artifact needs a data-card:

- source;
- retrieval timestamp;
- asset symbol;
- timeframe;
- granularity;
- window start/end;
- missing data handling;
- timezone;
- whether prices are adjusted or raw;
- known limitations.

## Baselines And Nulls

Minimum starter baseline family:

- random walk / naive drift;
- shuffled returns;
- circular block shuffle;
- adjacent-window control;
- prior-window recurrence check;
- transaction-cost/friction baseline;
- no-lookahead split.

No public claim is allowed unless it beats claim-appropriate baselines and the
falsifier confirms the exact data-card.

## UI Contract

The UI should be more domain-native than generic finance.

Core modules:

- Regime State: current hypothesis and confidence band.
- Evidence vs Baseline: what survives and what collapses.
- Watch / Reject / Test: actionable status without buy/sell language.
- Data Card: source and window.
- Non-Admissible: what the Lab refuses to infer.
- Runtime Dynamics: how the last cycle moved.

The default card should speak human language:

```text
BTC is being monitored for regime evidence. The Lab does not predict price; it
tests whether a perceived pattern survives baseline, null and falsifier checks.
```

## Meta-Lab Request Shape

When ready, create a domain request with:

- slug: `bitcoin-regime-lab`;
- family/preset: `bitcoin_regime.v1` if available, otherwise
  `finance_regime.v1` with explicit crypto adaptation;
- intent: monitor and falsify BTC regime hypotheses;
- movement_class: `regime_monitoring_with_falsification`;
- exclusions: trading advice, buy/sell signal, price forecast, profit claim;
- success_condition: first cycle produces a data-card, one rejected or watched
  hypothesis, baseline comparison and clear next test;
- human_review: Alipio as possible observer after first working cycle.

## Next Step

Do not install this Lab yet.

After the provider/install boundaries are stable:

1. finish the meta-lab E2E on an isolated candidate;
2. decide whether Bitcoin is generated from the meta-lab or from a predeclared
   request file;
3. generate candidate only;
4. validate M1-M8 plus finance/crypto boundary;
5. run one supervised first cycle;
6. show Alipio a working dashboard and ask for concrete critique.
