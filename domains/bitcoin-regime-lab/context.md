# AI-Lab D-ND Bitcoin Regime Lab — Context

## Intent in movement

Monitor BTC regime hypotheses and falsify weak operational interpretations before they become operational claims, starting from Alipio's timeframe question and derived POC/Kumo/feed-robustness method candidates.

The intent lives in the cycle movement, not in a prescribed result. The first
seed prepares the field; it does not authorize a public claim.

## Domain request

- slug: `bitcoin-regime-lab`
- kind: `bitcoin-regime`
- movement_class: `regime_monitoring_with_falsification`
- success_condition: A generated candidate passes generator preflight and strict M1-M8, exposes custom tools in context.md, and defines a first cycle that produces a data-card plus one timeframe/POC/Kumo/feed hypothesis classified as watch, test or reject with baseline/null evidence.

## Use dynamics

- turn trader language into observable event schemas, data-cards, baseline/nulls and falsifiers
- answer the optimal-timeframe question through a validation matrix instead of opinion
- test POC/Naked POC, inefficiency/FVG/LVN/CME gap, trendline retest and Kumo gates against matched nulls
- classify outputs as observe, watch, test or reject before any decision-support or signal-candidate promotion
- require feed robustness across Bitstamp, Binance, Coinbase and optional Kraken before accepting event labels

## Exclusions

- buy/sell/entry/exit/price-target/profit/alpha/trading-signal language
- manual chart annotations treated as evidence without mechanical definitions
- Massimo Rea or Alipio methods treated as authority before observable/null/falsifier translation
- current/open candle backtests unless explicitly declared as live-only observation
- single-exchange wick or volume-profile result promoted without feed robustness

## Cycle contract

The lab moves through seed -> tension -> field -> agent -> baseline/null ->
falsifier -> report -> seed_integrator -> trajectory. Each cycle must make its
runtime trace visible. A finding is not promoted because it is interesting; it
is promoted only after the falsifier and baseline/null contract survive.

## Baseline and null

The first experiment is a reference smoke only. A domain-native baseline,
shuffle/permutation or control null, and explicit stop condition are required
before interpretation.

## Domain preset possibilities

Preset `bitcoin_regime.v1` (`docs/templates/domain_presets/bitcoin_regime.v1.json`) is loaded
as possibility field, not as final domain truth.

Starter observables:

- `btc_log_return`
- `realized_volatility`
- `drawdown_recovery_path`
- `range_trend_persistence`
- `volume_or_liquidity_proxy`
- `volume_profile_poc`
- `low_volume_node_lvn`
- `fvg_or_imbalance_zone`
- `cme_gap_status`
- `trendline_retest_event`
- `naked_poc_lifecycle_state`
- `timeframe_matrix_status`
- `kumo_regime_state`
- `exchange_event_agreement`

Starter baselines:

- `random_walk_or_naive_drift`
- `shuffled_returns`
- `circular_block_shuffle`
- `adjacent_window_control`
- `friction_baseline`
- `matched_random_level`
- `shuffled_volume_profile`
- `equal_width_zone_fill_rate`
- `predeclared_forward_window`
- `timeframe_denominator_control`
- `poc_confluence_ablation`
- `feed_robustness_null`
- `open_candle_exclusion`

Starter falsifiers:

- `lookahead_bias`
- `selected_window_artifact`
- `baseline_collapse`
- `method_without_observable`
- `manual_annotation_drift`
- `fill_rate_without_denominator`
- `volume_proxy_confusion`
- `signal_language_before_promotion`

Domain-native UI modules:

- `RegimeState`
- `EvidenceVsBaseline`
- `WatchRejectTest`
- `DataCard`
- `NonAdmissibleInference`
- `VolumeProfileMap`
- `InefficiencyMap`
- `HypothesisCard`
- `InvalidationRules`
- `TimeframeMatrix`
- `NakedPOCQueue`
- `KumoRegimeMap`
- `FeedRobustness`
- `SourceMethodCards`

Adaptation questions:

- `Which BTC data source is acceptable for the first public cycle?`
- `Which timeframe and granularity should be monitored first?`
- `Which human question should the Lab constrain rather than predict?`
- `Which expert method, if any, is documented enough to be translated into observable, null and falsifier?`
- `What should a human observer see in the dashboard after one useful cycle?`
- `Which volume-profile source and binning rule are acceptable for a first POC/LVN cycle?`
- `How is an inefficiency considered filled, partially filled or invalidated?`
- `Which Alipio/Massimo Rea method should be translated first into observable, null and falsifier?`


## Skill retrieval

Use `skill_retrieval` before operational work. Start from portable capsules in
`docs/cognitive_archives/`, then escalate to BODY/BODY_PLUS_REFS only when the
request needs operational authority. Map intent -> movement_class ->
use_dynamics -> skills through `skill_intent_map`.


## Tools custom del lab — come invocarli

Il primo tool custom e' uno smoke test strutturale. Non usa rete, non legge
segreti e non produce claim pubblici:

```bash
python3 /opt/D-ND_LAB/domains/bitcoin-regime-lab/tools/exp_request_smoke.py --json
```

Durante la fase isolata del meta-lab, prima dell'installazione in `domains/`,
il tool puo' essere invocato dalla candidate dir generata:

```bash
python3 <candidate_dir>/tools/exp_request_smoke.py --json
```

Output atteso: JSON con `schema`, `verdict`, `baseline`, `null`, `boundary`,
`public_claim=false` e `trading_signal=false`. Se il tool non e' eseguibile o
non espone baseline/null, il candidato resta non installabile.
