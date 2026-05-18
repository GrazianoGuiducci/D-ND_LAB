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

Human method intake:

- Use `docs/BITCOIN_ALIPIO_METHOD_INTAKE_20260518.md` before accepting
  Alipio/Rea-derived methods into a cycle.
- Treat screenshots and video-derived notes as method cards, not evidence.
- Ask for exact profile window, binning, tolerance, fill rule, trendline
  construction, MM52 definition and invalidation rule.
- Current value path: daily field gate passed, daily timeframe is the first
  testable surface, weekly/monthly are watch surfaces, intraday is blocked
  until native intraday OHLCV/feed robustness exists.
- Next movement should expose one daily method specification or daily-computable
  FVG/inefficiency candidate with matched null. Do not promote POC/FVG/MM52
  language to target, entry, exit or signal.


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

Il primo tool value-facing usa rete pubblica e crea una data-card BTC per la
dashboard. Non produce segnali, target o consigli operativi:

```bash
python3 /opt/D-ND_LAB/domains/bitcoin-regime-lab/tools/btc_market_card.py --write --json
```

Output atteso: JSON `dndlab.bitcoin.market_context.v1` scritto in
`data/bitcoin-regime-lab/value/` con provider, source_url, retrieval_ts,
finestra dati, prezzo BTC/USD di riferimento, variazioni 1d/7d/30d,
volatilita realizzata proxy e boundary `trading_signal=false`.

Il tool feed-robustness usa API pubbliche exchange-native e confronta candele
daily prima che il lab legga POC/FVG/timeframe come ipotesi testabile:

```bash
python3 domains/bitcoin-regime-lab/tools/btc_exchange_ohlcv.py --write --json
```

Output atteso: JSON `dndlab.bitcoin.exchange_ohlcv.v1` scritto in
`data/bitcoin-regime-lab/value/` con Bitstamp BTC/USD, Coinbase BTC/USD,
Binance BTC/USDT, provider ok/error, latest_common_date,
latest_close_dispersion_pct e boundary `trading_signal=false`. Binance e'
BTC/USDT: usarlo come robustezza cross-feed, non come prezzo USD puro.

Refresh schedulabile senza ciclo cognitivo:

```bash
bash tools/bitcoin-refresh-value.sh
```

Questo comando non invoca LLM, non scrive report agente e non autorizza target
o segnali. Serve a tenere fresca la superficie `latest_value_artifacts` per UI,
THIA e futuri cicli del Bitcoin Lab.

Quando il ciclo viene lanciato da `tools/dnd-cycle.sh`, la raccolta dati BTC
deve avvenire nel pre-ciclo host-side tramite:

```bash
domains/bitcoin-regime-lab/tools/pre_cycle_value_refresh.sh
```

L'agente del ciclo **non deve rifare fetch di rete** come autorita' primaria:
deve leggere gli artifact `*_latest.json` gia' scritti nel `LAB_DATA_DIR` del
ciclo e, se servono controlli aggiuntivi, dichiararli come prossima ipotesi.
Motivo: il network dentro la shell dell'agente puo' differire dal network host;
il campo dati deve essere deterministico, tracciabile e visibile alla dashboard
prima del pensiero cognitivo.

La prima ipotesi falsificabile del Lab non riguarda il prezzo: riguarda
l'ammissibilita' del campo dati daily prima di qualunque POC/FVG/timeframe.

```bash
python3 domains/bitcoin-regime-lab/tools/btc_first_hypothesis.py --write --json
```

Output atteso: JSON `dndlab.bitcoin.first_hypothesis.v1` scritto in
`data/bitcoin-regime-lab/value/`. Consuma
`btc_exchange_ohlcv_latest.json` e verifica:

- provider daily ok >= 3;
- provider errors = 0;
- common_days_compared >= 30;
- latest_close_dispersion_pct <= 0.5;
- max_close_dispersion_pct <= 0.75;
- boundary no-signal conservato.

Se passa, il campo diventa `FIELD_ADMISSIBLE_FOR_NEXT_HYPOTHESIS`: il prossimo
ciclo puo' definire un solo osservabile meccanico POC/FVG/timeframe con null
matched. Se fallisce, il Lab deve riparare feed/sorgenti prima di interpretare.
In entrambi i casi `trading_signal=false`.

La domanda di Alipio sul "time free/timeframe ottimale" entra come matrice di
ammissibilita', non come risposta opinabile:

```bash
python3 domains/bitcoin-regime-lab/tools/btc_timeframe_matrix.py --write --json
```

Output atteso: JSON `dndlab.bitcoin.timeframe_matrix.v1` scritto in
`data/bitcoin-regime-lab/value/`. Consuma `btc_exchange_ohlcv_latest.json` e
`btc_first_hypothesis_latest.json`, poi classifica mensile, settimanale, daily,
4h, 1h, 45m, 30m, 15m, 10m, 5m e 1m come:

- `testable`: il campo dati e il denominatore sono sufficienti per il prossimo
  test meccanico;
- `watch`: osservabile, ma non ancora abbastanza robusto per test;
- `blocked`: mancano dati nativi o il field gate non regge.

Il primo risultato utile atteso e' conservativo: con soli feed daily, il Lab
puo' ammettere il daily come primo test e bloccare intraday finche' non
esistono OHLCV native con baseline/null. Questo e' valore per l'utente: sapere
cosa puo' essere guardato ora, cosa resta in watch e cosa non va interpretato.

Il ponte operativo con Alipio/THIA e' una scheda metodo, non un segnale:

```bash
python3 domains/bitcoin-regime-lab/tools/btc_method_intake_card.py --write --json
```

Output atteso: JSON `dndlab.bitcoin.method_intake.v1` scritto in
`data/bitcoin-regime-lab/value/`. Consuma, se presenti, field gate e timeframe
matrix; poi produce card per POC/Volume Profile, POC sotto, chiusura
inefficienza, trendline+POC, MM52 e timeframe. Ogni card espone definizioni
mancanti, dati richiesti, null/falsifier, domande che THIA deve fare ad Alipio
e boundary `trading_signal=false`.

Questa scheda e' il modo corretto per far parlare THIA con Alipio: raccoglie
definizioni e critica utile, ma non modifica il seed e non promuove target.
