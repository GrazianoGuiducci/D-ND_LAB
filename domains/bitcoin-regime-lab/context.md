# AI-Lab D-ND Bitcoin Regime Lab — Context

## Intent in movement

Monitor BTC regime hypotheses and falsify weak operational interpretations
before they become claims, using timeframe, Volume Profile, POC/LVN/HVN, FVG,
Kumo, feed robustness and paper-trading outcomes as observable method surfaces.

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
- classify outputs as observe, watch, test, reject or simulated-decision before
  any promotion from hypothesis to method
- use paper trading / live simulation as a valid measurement surface: if the
  Lab cannot say what it would have done, it cannot measure whether a method
  works
- require feed robustness across Bitstamp, Binance, Coinbase and optional Kraken before accepting event labels

## Exclusions

- real-money order execution unless explicitly configured and separately
  authorized
- public financial advice or presenting paper-trading output as instruction
- manual chart annotations treated as evidence without mechanical definitions
- external BTC method material treated as authority before observable/null/falsifier translation
- current/open candle backtests unless explicitly declared as live-only observation
- single-exchange wick or volume-profile result promoted without feed robustness

## Cycle contract

The lab moves through seed -> tension -> field -> agent -> baseline/null ->
falsifier -> report -> seed_integrator -> trajectory. Each cycle must make its
runtime trace visible. A finding is not promoted because it is interesting; it
is promoted only after the falsifier and baseline/null contract survive.

## Cognitive/autological process

The Bitcoin Lab must expose how it thinks, not only what it measured.

Minimum cognitive loop:

1. intent becomes a field of observable BTC objects;
2. the field becomes a test contract with data, baseline and null;
3. the test is attacked by controls and falsifier;
4. the result becomes learning: advance, watch, redesign, reject or retain;
5. the next cycle reads that learning before changing policy or seed;
6. reusable capability is marked as cascade candidate, not silently promoted.

The active BTC implementation is partial but now explicit:

- `falsifier` is the current veritas-like gate;
- `trajectory_state.json` is the current kairos-like movement decision;
- `seed.json` and `seed_archive/` are the current mnemos-like memory substrate;
- `btc_policy_simulator.py` is the current research simulator for method
  behavior versus the ordinary BTC chart path;
- `btc_cognitive_state.py` is the observability artifact that shows the loop,
  the gaps and the next mutation without running a cognitive cycle.

Next structural closure: make retention/decay, regime selection and policy
mutation first-class artifacts instead of leaving them implicit in reports.

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
- `simulation_reality_confusion`
- `signal_without_ledger`
- `signal_language_before_measurement`

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
- `Which BTC method surface should be translated first into observable, null and falsifier?`

Human method intake:

- Use the BTC method-intake source note before accepting
  BTC method material into a cycle.
- Treat screenshots and video-derived notes as method cards, not evidence.
- Ask for exact profile window, binning, tolerance, fill rule, trendline
  construction, MM52 definition and invalidation rule.
- Current value path: daily field gate passed, daily timeframe is the first
  testable surface, weekly/monthly are watch surfaces, intraday is blocked
  until native intraday OHLCV/feed robustness exists.
- Next movement should expose one daily method specification or daily-computable
  FVG/inefficiency candidate with matched null. A paper signal is admissible
  when it has explicit entry/exit/invalidation/cost assumptions and lands in a
  simulation ledger; it is not admissible as public advice.
- BTC policy simulator v1 is manual-only research infrastructure. It measures
  declared historical method policies against controls, walk-forward splits and
  parameter perturbations. Lab value can be positive or negative: stable
  underperformance versus controls is useful evidence for redesign/falsification.
  Useful negative evidence should be labelled as redesign, not as a positive
  method edge.
  The artifact should show how event windows behave against the ordinary BTC
  daily chart path, so a human can compare method structure with normal chart
  movement instead of reading isolated closure counts.
  In refresh hooks it remains artifact generation only: it may produce
  paper-trading evidence, but does not execute real orders or public advice.

## Trading-simulation frame

Operator correction 2026-05-26: the BTC Lab must accept trading as the
simulation frame. We are not trading with capital because that is not the
current interest, but the Lab must behave as if it had to decide in order to
measure whether something works.

Therefore valid internal objects include:

- paper buy/sell/hold decision;
- entry, exit, invalidation and sizing assumptions;
- fees, slippage, latency and execution model;
- hit-rate, expectancy, drawdown, PnL and error versus baseline;
- decision ledger and post-decision falsification.

Invalid objects are:

- unlogged signals;
- paper results presented as public instruction;
- real-money execution without an explicit separate runtime contract;
- method promotion without baseline/null/falsifier and ledger evidence.

## Typed adjustment boundary

`can_adjust_now` is a scoped signal, not a blanket authorization.

Allowed under an open daily candle:

- refresh/autology updates that write Lab artifacts;
- paper decisions that are recorded in the paper-simulation ledger and attacked
  by baseline/null/falsifier checks.

Blocked while `mutation_allowed=false`:

- method or policy mutation;
- reinterpretation of LVN/FVG/timeframe evidence as if the current daily candle
  were closed;
- real-money execution without a separate explicit runtime contract.

The cognitive-state artifact must expose `can_adjust_now_scopes`,
`policy_mutation_allowed` and `typed_adjustment` so dashboard and health checks
cannot confuse paper/live-sim measurement with method mutation.

`btc_policy_mutation_contract.py` is the binding self-adjustment contract. It
is regenerated before autology/cognitive state and lists prerequisites, blocked
states, allowed evidence inputs, ledger requirements, baseline/null obligations
and promotion/falsification outcomes. Under `HOLD_OPEN_DAILY_CANDLE` it must be
readable but return `policy_mutation_allowed=false`; trajectory apply may still
absorb structural Lab directions, but BTC method/policy mutation is blocked by
the contract until the daily gate and evidence contract allow it.

`btc_retention_regime_selector.py` reads Mnemos/Kairos, the daily gate, policy
contract, paper ledger and trajectory state and returns explicit
`retain/decay/reject/watch` decisions. It is the self-adjustment selector for
memory/regime state: it may recommend what should be retained, watched, decayed
or rejected, but it applies zero hard decay and zero method-policy mutation
while the contract blocks mutation.

`btc_daily_method_pressure_test.py` pressure-tests the concrete
`daily_inefficiency` method surface through the policy contract, selector and
paper ledger. It should pass when the method is correctly held as watch under a
strict null and open-daily mutation block; it must not turn paper/live-sim
measurement into public advice or real execution.

`btc_fill_rule_sensitivity.py` compares the current daily inefficiency deposit
under wick, close and full-traversal fill rules. It is the first pressure on
the fill-rule assumption: it reports whether the method is invariant, rule
dependent, or has a rule-specific edge against strict null, without replacing
active method policy.

`btc_zone_denominator_sensitivity.py` compares the current daily inefficiency
deposit across zone-width, forward-window denominator and fill-threshold
variants. It is the next redesign pressure after fill-rule invariance: it
reports whether any zone/denominator axis beats strict null before the Lab
changes method policy.

`btc_closed_daily_event_null.py` is the first redesigned event/null family after
the current daily inefficiency proxy failed strict-null and parameter pressure.
It uses only closed daily candles, declares range-expansion + directional
close-location events, and compares their forward directional return against a
deterministic matched-date null. It is paper/lab measurement: no entries, exits,
targets, advice, real orders or method-policy mutation.

`btc_closed_daily_event_null_pressure.py` decides whether that event/null family
has enough denominator and null stability to keep testing. It varies the
forward window, matched-null density and event thresholds, then reports whether
forward-10 and the matched-date null are admissible enough for watch/test/reject.
It is still an evidence card only, not policy mutation.

`btc_closed_daily_strict_close_contract.py` takes the current pressure result
and predeclares the `strict_close` axis as a paper contract for the next
closed-daily cycle when its denominator and matched-date null are readable. It
records event count, null comparison, forward denominator, paper-decision
admissibility and the non-admissible boundary for policy mutation.


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

Runtime lineage closure:

- Value artifacts are born in the pre-cycle host-side refresh and may point to
  the active cycle's future report and cycle trace before those files exist.
- `btc_producer_trace_sink.py` makes producer telemetry first-class: it indexes
  the expected BTC value producers, their latest/stamped outputs, sessions,
  cycle/refresh refs, input counts and trace/log/report refs. It is process
  telemetry only, not BTC interpretation.
- Standalone value refreshes are not cognitive cycles: their lineage uses
  `session=btc_value_refresh`, a `refresh_ts`, `cycle_ts=null`, and may keep
  only `last_cycle_ref` pointers for continuity.
- During an in-cycle/pre-report audit, missing `agent_<cycle>.md` or
  `cycle_trace_<cycle>.json` is `pending`, not proof that the cycle failed.
- The closure authority is the deterministic post-cycle audit:
  `data/bitcoin-regime-lab/closure/btc_runtime_lineage_closure_<cycle>.json`.
- A post-cycle audit with `status=pass` means current-cycle binding, raw log,
  report and cycle trace materialization are closed for the value artifacts.
- Reports must cite stamped closure artifacts for historical claims. Do not use
  `btc_runtime_lineage_closure_latest.json` as evidence for a previous cycle,
  because the post-cycle hook advances it to the current cycle.
- Evidence authority has two explicit layers: stamped artifacts kept by the
  post-cycle closure audit are authoritative for current-cycle binding claims;
  `*_latest.json` artifacts are authoritative only for current readback after a
  declared refresh or rerun. If a report uses both, it must state which layer
  supports each numeric claim.
- If old standalone refresh artifacts accidentally reused a cycle timestamp,
  closure audit groups by expected output artifact and ignores duplicate cycle
  bindings after the first stamped artifact for that output.
- Do not use filename globs alone for counts; use
  `runtime_lineage.cycle_ts` and `runtime_lineage.output_artifact_stamped`.

Quando il ciclo viene lanciato da `tools/dnd-cycle.sh`, la raccolta dati BTC
deve avvenire nel pre-ciclo host-side tramite:

```bash
domains/bitcoin-regime-lab/tools/pre_cycle_value_refresh.sh
```

Standalone value refreshes end with:

```bash
python3 domains/bitcoin-regime-lab/tools/btc_operational_health.py --write
```

This guard checks that latest value artifacts remain refresh-bound
(`cycle_ts=null`), the last cognitive cycle has a passing post-cycle closure
audit, and the cognitive-state card no longer regresses to stale implicit
Mnemos/Kairos/Coherence language. It also fails if Mnemos lacks first-class
decay classification, if hard decay / policy mutation counters are non-zero,
or if the producer trace sink reports missing producers, lineage or stamped
outputs.

Night-run smoke guard:

```bash
python3 domains/bitcoin-regime-lab/tools/btc_night_run_smoke.py --json --require-extra-cron
```

For the 2026-05-27 review after the canonical and temporary extra runs:

```bash
python3 domains/bitcoin-regime-lab/tools/btc_night_run_smoke.py --json --date 20260527 --min-cycles-for-date 2 --after-cycle 20260526_1853
```

This is a read-only runtime guard. It checks operational health, latest value
artifact count, latest cycle trace, assertions, post-cycle closure, falsifier,
strict-close paper-contract boundary and cron presence. It must not fetch
market data, run a cycle, mutate method policy, execute real orders or publish
advice.

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

La domanda sul timeframe ottimale entra come matrice di
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

Il ponte operativo con THIA e' una scheda metodo, non un segnale:

```bash
python3 domains/bitcoin-regime-lab/tools/btc_method_intake_card.py --write --json
```

Output atteso: JSON `dndlab.bitcoin.method_intake.v1` scritto in
`data/bitcoin-regime-lab/value/`. Consuma, se presenti, field gate e timeframe
matrix; poi produce card per POC/Volume Profile, POC sotto, chiusura
inefficienza, LVN/Volume Profile void, trendline+POC, MM52 e timeframe. Dopo
l'intake metodo BTC 2026-05-24, il focus default e' `volume_profile_lvn_void`.
Ogni card espone definizioni mancanti, dati richiesti, null/falsifier, domande
che THIA deve chiarire e boundary `trading_signal=false`.

Questa scheda e' il modo corretto per far raccogliere a THIA definizioni e
critica utile, ma non modifica il seed e non promuove target.

Autoaccensione BTC: il sistema puo' generare una specifica provvisoria quando i
parametri umani mancano, ma deve dichiarare le assunzioni e chiamare proxy cio'
che non replica TradingView:

```bash
python3 domains/bitcoin-regime-lab/tools/btc_auto_ignite.py --write --json
```

Output atteso: JSON `dndlab.bitcoin.auto_ignite.v1` scritto in
`data/bitcoin-regime-lab/value/`. Consuma gli artifact BTC correnti, seleziona
`volume_profile_lvn_void`, costruisce un proxy Volume Profile daily da OHLCV
cross-feed, espone POC/LVN proxy, assunzioni, non verificati, null e prossimo
contratto. Questo e' il backend naturale per un futuro bottone `autoaccendi
Lab`: prima nasce consapevolezza/artifact, poi eventualmente il ciclo cognitivo
lo interpreta.

Il simulatore compra/vendi puo' essere costruito solo dopo questo strato: prima
simulare closure/watch-zone e confronto con zone random; poi, se viene definita
una regola esplicita di entrata/uscita/invalidation, misurare una strategia
ipotetica contro buy-and-hold, costi, slippage e drawdown.

Primo test proxy LVN:

```bash
python3 domains/bitcoin-regime-lab/tools/btc_volume_profile_lvn_proxy.py --write --json
```

Output atteso: JSON `dndlab.bitcoin.volume_profile_lvn_proxy.v1`. Il tool usa
solo candele precedenti alla data evento per costruire il profilo, poi misura
se la chiusura della zona LVN vicina batte controlli adiacenti, opposti e
shuffled-volume. Se non batte i controlli, il metodo resta `watch`.
Default corrente: finestra profilo 45 daily chiuse, forward 10 giorni, stride 3
e closure rule `close`, scelti per ottenere denominatore sufficiente senza
rendere il test piu permissivo con wick intraday.


Il primo tool daily-computable per la chiusura di inefficienza usa solo OHLCV
daily e produce zone/test/null, non segnali:

```bash
python3 domains/bitcoin-regime-lab/tools/btc_daily_inefficiency_candidate.py --write --json
```

Output atteso: JSON `dndlab.bitcoin.daily_inefficiency.v1` scritto in
`data/bitcoin-regime-lab/value/`. Consuma `btc_exchange_ohlcv_latest.json`,
costruisce una serie daily median across feed, rileva un proxy FVG a tre
candele, valuta fill su finestra forward dichiarata e confronta ogni zona con
un controllo adiacente di pari ampiezza. Il boundary resta
`trading_signal=false`, `advice=false`, `price_target=false`.

Gate evidenza daily chiusa:

```bash
python3 domains/bitcoin-regime-lab/tools/btc_daily_closed_evidence_gate.py --write --json
```

Output atteso: JSON `dndlab.bitcoin.daily_closed_evidence_gate.v1` scritto in
`data/bitcoin-regime-lab/value/`. Il gate legge il feed daily e distingue:

- `latest_common_date`: ultima data comune vista dai provider;
- `open_daily_date`: data daily corrente se coincide con oggi UTC;
- `latest_closed_common_date`: ultima data comune strettamente precedente a
  oggi UTC;
- `mutation_allowed`: vero solo quando la nuova evidenza e' chiusa e non
  dipende dalla candela daily aperta.

Questo e' il primo blocco di auto-aggiustamento: il Lab puo' aggiornare il
contesto live, ma non puo' reinterpretare policy LVN/FVG/timeframe usando
rumore di candela daily aperta.

Artifact autologici first-class:

```bash
python3 domains/bitcoin-regime-lab/tools/btc_autology_artifacts.py --write --json
```

Output atteso:

- `dndlab.bitcoin.mnemos_memory.v1`: decide cosa resta in memoria, cosa decade
  e cosa va a redesign;
- `dndlab.bitcoin.kairos_phase.v1`: sceglie la fase corrente del Lab
  (`observe_context_do_not_mutate`, redesign, review, watch);
- `dndlab.bitcoin.coherence_check.v1`: verifica coerenza tra gate daily chiuso,
  cutoff usato da FVG/LVN, boundary no-operational e simulatore.

Questi artifact chiudono il primo gap del processo cognitivo: memoria,
selezione fase e coerenza non sono piu' solo implicite in seed/trajectory, ma
sono leggibili da UI, cron e prossime istanze.

Stato cognitivo osservabile del Lab:

```bash
python3 domains/bitcoin-regime-lab/tools/btc_cognitive_state.py --write --json
```

Output atteso: JSON `dndlab.bitcoin.cognitive_state.v1` scritto in
`data/bitcoin-regime-lab/value/`. Legge seed, trajectory, MML e artifact BTC
correnti, poi espone ciclo cognitivo, layer attivi/parziali, apprendimento,
auto-aggiustamento, gap di chiusura autologica e prossima mutazione. Non usa
rete e non lancia un ciclo cognitivo.
