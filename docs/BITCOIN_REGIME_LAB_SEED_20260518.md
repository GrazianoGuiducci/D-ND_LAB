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

First concrete input from Alipio:

- TradingView screenshots with annotated BTC weekly structure;
- red horizontal lines described as POC of the volume profile;
- terms used: `chiusura inefficienza`, POC, volume profile, FVG/imbalance,
  LVN/HVN, CME gap, retest trendline, momentum change.

These inputs are valuable as domain language and candidate method family. They
are not yet evidence and not yet rules. The Lab must translate them into
observables, data requirements and falsifiers before using them.

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
- When a chart marks a POC/FVG/LVN/CME gap, what exact data condition makes it
  active, filled, invalidated or irrelevant?
- Does a claimed "inefficiency closure" happen more often than a naive baseline
  after accounting for selected-window bias?
- Does a POC retest have different behavior from random adjacent price levels
  with similar volatility and volume context?

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

Alipio-derived candidate observables:

- volume profile POC: price level with maximum traded volume in a declared
  profile window;
- POC position relative to current price: above, below, crossed, retested;
- POC drift: whether successive profile windows move upward, downward or
  compress;
- LVN/HVN zones: low/high volume nodes computed from a declared binning
  method;
- FVG/imbalance zone: candle pattern with an explicit mechanical definition,
  not manual drawing only;
- gap fill / inefficiency closure: distance-to-zone and whether price traded
  through a defined percentage of the zone;
- CME gap: futures close/open gap with timestamp, size and fill status;
- trendline/retest: line construction rule plus retest tolerance;
- momentum change: predeclared metric such as moving-average slope, return
  acceleration, breakout failure or volatility-adjusted impulse.

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

For any volume-profile claim, the data-card must also specify:

- exchange/source;
- whether real traded volume, tick volume or proxy volume is used;
- profile window start/end;
- bin size or binning rule;
- session/timezone rule;
- whether POC/LVN/HVN are computed or manually annotated;
- tolerance used to decide retest/fill.

## Baselines And Nulls

Minimum starter baseline family:

- random walk / naive drift;
- shuffled returns;
- circular block shuffle;
- adjacent-window control;
- prior-window recurrence check;
- transaction-cost/friction baseline;
- no-lookahead split.

Specific countertests for POC/inefficiency methods:

- matched random levels with same distance from current price;
- adjacent-window POC computed before the event, not after;
- shuffled-volume baseline that preserves price path but breaks volume profile;
- block-preserving return null around FVG/LVN zones;
- fill-rate comparison versus arbitrary equal-width price zones;
- out-of-sample forward window after the zone is declared.

No public claim is allowed unless it beats claim-appropriate baselines and the
falsifier confirms the exact data-card.

## Signal Ladder

The Lab can eventually support signal-like workflows, but only through staged
promotion:

1. `observe`: a method marks a level/zone.
2. `watch`: the level has a valid data-card and active condition.
3. `test`: a forward condition is declared before outcome.
4. `reject`: the hypothesis fails baseline/null/falsifier.
5. `decision_support`: surviving classes become alerts or constraints.
6. `signal_candidate`: only after walk-forward, costs/slippage, drawdown,
   recurrence and disclaimer gates.

Before stage 6, the UI must avoid buy/sell language. The useful output is:

- active zone;
- invalidation;
- confidence/status;
- next test;
- what not to infer.

## UI Contract

The UI should be more domain-native than generic finance.

Core modules:

- Regime State: current hypothesis and confidence band.
- Evidence vs Baseline: what survives and what collapses.
- Watch / Reject / Test: actionable status without buy/sell language.
- Data Card: source and window.
- Non-Admissible: what the Lab refuses to infer.
- Runtime Dynamics: how the last cycle moved.
- Volume Profile Map: POC/LVN/HVN zones with computed window and tolerance.
- Inefficiency Map: FVG/LVN/CME gap candidates with fill/invalidation status.
- Hypothesis Card: "if price reaches X, hypothesis expects Y; invalidated by Z".

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
- method_family: volume profile POC, inefficiency closure, FVG/LVN/CME gap,
  trendline retest and momentum change as candidate methods only;
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
