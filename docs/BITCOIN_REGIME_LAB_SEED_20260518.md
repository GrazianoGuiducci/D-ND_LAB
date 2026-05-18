# Bitcoin Regime Lab Seed — 2026-05-18

Status: installed reference Lab after isolated meta-lab candidate validation.
Domain slug: `bitcoin-regime-lab`.

Installed on 2026-05-18 after:

- isolated candidate generation through `domain_request_runner.py`;
- strict template generator dry-run;
- `core.cli inspect --domain bitcoin-regime-lab`;
- `core.cli dry-run --domain bitcoin-regime-lab` with LLM movements disabled;
- public API check through `https://lab.d-nd.com/api/domains`.

The installed surface is still a reference boundary, not an operational
trading system. Its smoke tool returns `public_claim=false`,
`trading_signal=false` and `operational=false`.

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

Derived visual-method intake from the first Alipio screenshots is preserved in
`docs/BITCOIN_ALIPIO_METHOD_INTAKE_20260518.md`. That document is the
THIA/Lab bridge for questions, method cards and tool design; it is not seed
authority and contains no raw private screenshots.

Operator also mentioned Massimo Rea as a possible source of methods discussed
by Alipio. TM7-local recovered derived method material from two transcripts and
metadata from four other videos; raw transcripts are not stored in the public
repo. Treat this as method-intake substrate, not as authority. Before any
method enters the seed, the Lab must ask:

- what is the method exactly?
- where is it documented?
- what observable does it claim to expose?
- what null/baseline attacks it?
- what failure mode would falsify it?

Derived Massimo Rea / Alipio method candidates now in scope:

- Naked POC lifecycle: a completed-period POC remains active until first future
  touch, then retires.
- Timeframe hierarchy: daily/weekly/monthly POCs appear more central; 4h/12h
  are candidate extensions, not default authority.
- Kumo confirmation/failure: close inside cloud, hold/reject boundary and
  opposite-boundary target can become mechanical regime gates.
- Feed disagreement: a BTC swing/touch can differ between Bitstamp, Binance,
  Coinbase or Kraken; event labels need feed robustness before promotion.
- Timeframe matrix: Alipio's question ("monthly, weekly, day, 4h, 1h, 45m,
  30m, 15m, 10m, 5m, 1m?") becomes a validation matrix, not an opinion answer.

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
- Which timeframe makes a method observable, stable and falsifiable without
  becoming too sparse, too noisy, feed-sensitive or overfit?
- Does a Naked POC first-touch lifecycle survive matched random levels and
  adjacent-window controls?
- Does Kumo add confirmation value after ablation, or only re-label the same
  visible move?

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
- naked POC lifecycle state: active, first_touch, retired, invalidated;
- timeframe matrix status: usable, fragile, too_sparse, too_noisy,
  feed_sensitive, overfit_risk;
- Kumo regime state: outside, boundary_test, close_inside, hold, rejection,
  opposite_boundary_target;
- exchange agreement score: whether an event label is stable across Bitstamp,
  Binance, Coinbase and Kraken.

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
- timeframe denominator control: reject timeframe comparisons without event
  counts, active windows and open-candle policy;
- POC-only vs confluence ablation: POC, trendline, VAH/VAL, Fibonacci, FVG and
  Kumo must each prove added value, not only appear together on a chart;
- feed robustness null: if the event label changes by exchange feed, downgrade
  to feed-sensitive instead of promoting;
- open-candle exclusion: default tests must exclude current/open candles unless
  explicitly marked live and non-backtest.

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
- Timeframe Matrix: rows are method/event families; columns are timeframes and
  statuses (`usable`, `fragile`, `too_sparse`, `too_noisy`, `feed_sensitive`,
  `overfit_risk`).
- POC / Naked POC Queue: open levels, first touch, retired levels and forward
  outcomes.
- Feed Robustness: Bitstamp/Binance/Coinbase/Kraken event agreement.
- Sources: Alipio inputs, Massimo Rea derived method cards, extraction status
  and rights boundary.

Suggested first technical stack:

- UI: React/TypeScript, current D-ND Lab dashboard shell, TanStack Table,
  Lightweight Charts for candlesticks, ECharts/Plotly for matrices and
  forward-window distributions.
- Backend/data: Python, FastAPI, CCXT after source-specific adapters are
  explicit, pandas or polars, DuckDB/Parquet, pydantic schemas.
- Feeds: Bitstamp first for Alipio screenshot replay; Binance/Coinbase as
  cross-feed checks; Kraken as additional OHLC feed; Coin Metrics as normalized
  reference, not replacement for exchange-specific volume.

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

## Current Operational State

The Lab is installed under `domains/bitcoin-regime-lab/` and visible to the
dashboard. Runtime bootstrap has one dry-run trace in `data/bitcoin-regime-lab/`
on the VPS, but runtime data is not part of the public install artifact.

Useful checks:

```bash
python3 -m core.cli inspect --domain bitcoin-regime-lab
python3 -m core.cli dry-run --domain bitcoin-regime-lab
python3 domains/bitcoin-regime-lab/tools/exp_request_smoke.py --json
```

## Next Step

Before a real cycle, replace the smoke boundary with the first reviewed
domain-native experiment:

1. choose one data source and timeframe policy;
2. create a data-card schema for BTC OHLCV/source provenance;
3. implement one small observable, preferably timeframe matrix or POC first
   touch, with matched baseline/null;
4. run one supervised cycle;
5. show Alipio a working dashboard and ask for critique on usefulness, not for
   trading direction.

After the first field and timeframe gates, the next reviewed experiment should
start from the Alipio intake contract: define one daily method card or one
daily-computable FVG/inefficiency candidate with matched null. Do not jump
directly to a Volume Profile POC target unless the profile window, binning,
source and tolerance have been declared.
