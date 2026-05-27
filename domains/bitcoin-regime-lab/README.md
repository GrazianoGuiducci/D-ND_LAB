# AI-Lab D-ND Bitcoin Regime Lab

Generated candidate from `domain_request`.

Status: reference candidate only. Run strict M1-M8 before install.

Intent:

```text
Monitor BTC regime hypotheses and falsify weak operational interpretations before they become operational claims, using timeframe, Volume Profile, POC/LVN/HVN, FVG, Kumo and feed robustness as observable method surfaces.
```

## First Value Artifact

Generate a BTC context data-card for the dashboard:

```bash
python3 domains/bitcoin-regime-lab/tools/btc_market_card.py --write --json
```

The artifact is written under `data/bitcoin-regime-lab/value/` and appears in
Campo through `latest_value_artifacts`. It is a context card: price,
1d/7d/30d changes, realized-volatility proxy, source and retrieval timestamp.
Paper-trading decisions are valid Lab objects when they are logged in a
simulation ledger; this card itself is not a decision ledger.

Refresh all value-facing Bitcoin artifacts without running a cognitive cycle:

```bash
bash tools/bitcoin-refresh-value.sh
```

This wrapper runs the market/feed cards, method/test artifacts, policy
simulator, paper ledger, producer-lineage artifact, autological artifacts and
cognitive state. It is safe for cron because it uses only public no-key APIs,
writes only `data/bitcoin-regime-lab/value/*`, and executes no real orders.

Build the producer trace sink directly:

```bash
python3 domains/bitcoin-regime-lab/tools/btc_producer_trace_sink.py --write --json
```

This indexes the BTC value-artifact producers, latest/stamped outputs,
sessions, cycle/refresh refs and trace/log/report pointers. It is telemetry
for process reliability and can index paper-trading evidence.

Build the BTC policy-mutation contract directly:

```bash
python3 domains/bitcoin-regime-lab/tools/btc_policy_mutation_contract.py --write --json
```

This exposes the exact self-adjustment contract for method/policy mutation.
It does not apply mutation. Under an open daily candle it remains readable and
binding, but reports `policy_mutation_allowed=false`.

Build the BTC retention/regime selector directly:

```bash
python3 domains/bitcoin-regime-lab/tools/btc_retention_regime_selector.py --write --json
```

This reads Mnemos/Kairos, the daily gate, policy contract, paper ledger and
trajectory state, then returns explicit `retain/decay/reject/watch` decisions.
It applies no hard decay, no method-policy mutation and no orders.

Build the daily-method pressure test directly:

```bash
python3 domains/bitcoin-regime-lab/tools/btc_daily_method_pressure_test.py --write --json
```

This checks the current `daily_inefficiency` surface through the policy
contract, retention/regime selector and paper ledger. It validates Lab behavior;
it is not trading advice and does not mutate policy.

Compare daily fill-rule sensitivity directly:

```bash
python3 domains/bitcoin-regime-lab/tools/btc_fill_rule_sensitivity.py --write --json
```

This runs the same daily inefficiency deposit through wick, close and
full-traversal fill semantics. It helps decide whether the next useful pressure
belongs to fill-rule semantics, zone construction or denominator. It does not
replace active method policy.

Compare zone construction and denominator sensitivity directly:

```bash
python3 domains/bitcoin-regime-lab/tools/btc_zone_denominator_sensitivity.py --write --json
```

This runs baseline, narrow/wide zone-width, short/long denominator-horizon and
shallow/deep fill-threshold variants against the same strict null. It identifies
whether the next redesign has a promising axis before any method-policy
mutation.

Build the redesigned closed-daily event/null family directly:

```bash
python3 domains/bitcoin-regime-lab/tools/btc_closed_daily_event_null.py --write --json
```

This tests range-expansion candles with directional close-location against a
deterministic matched-date null. It is the next functional substrate after the
daily FVG/inefficiency proxy failed strict-null pressure; it remains paper/lab
measurement only and does not create entries, exits, advice or real orders.

Pressure-test that event/null family directly:

```bash
python3 domains/bitcoin-regime-lab/tools/btc_closed_daily_event_null_pressure.py --write --json
```

This varies forward-window denominator, matched-null density and event
thresholds. It tells the Lab whether the family is stable enough to keep as a
watch/test/reject surface before any policy mutation.

Predeclare the strict-close paper contract directly:

```bash
python3 domains/bitcoin-regime-lab/tools/btc_closed_daily_strict_close_contract.py --write --json
```

This freezes the selected `strict_close` axis as the next-cycle paper contract
and records denominator/null admissibility without mutating method policy.

Prepare the strict-close paper ledger directly:

```bash
python3 domains/bitcoin-regime-lab/tools/btc_strict_close_paper_ledger.py --json
```

This turns the predeclared strict-close closed-daily contract into simulated
paper rows: paper long/short decision, entry/exit basis, round-trip cost,
net directional return, matched-date null comparison and boundary readback. It
is prepared but not wired into refresh until the night-run evidence is reviewed.

Run the read-only night-run smoke guard:

```bash
python3 domains/bitcoin-regime-lab/tools/btc_night_run_smoke.py --json
```

Use `--require-extra-cron` only when a temporary extra-night cron is currently
intended to be active. The 2026-05-27 extra cron was one-shot and is expected
to be absent after review.

After scheduled runs, require new traces for a date:

```bash
python3 domains/bitcoin-regime-lab/tools/btc_night_run_smoke.py --json --date 20260527 --min-cycles-for-date 2 --after-cycle 20260526_1853
```

This checks operational health, latest artifact count, cycle trace, assertions,
post-cycle closure, falsifier flags, the strict-close paper contract boundary
and cron presence. It is read-only: no market fetch, no cognitive cycle, no
orders and no public advice.

Generate the exchange-native feed robustness card directly:

```bash
python3 domains/bitcoin-regime-lab/tools/btc_exchange_ohlcv.py --write --json
```

The artifact compares daily OHLCV from Bitstamp BTC/USD, Coinbase BTC/USD and
Binance BTC/USDT. It measures provider availability and close dispersion before
any POC/FVG/timeframe hypothesis is allowed to become testable. It is not a
signal and does not aggregate venue volume into a trading conclusion.

Build the first falsifiable BTC hypothesis directly:

```bash
python3 domains/bitcoin-regime-lab/tools/btc_first_hypothesis.py --write --json
```

This consumes `btc_exchange_ohlcv_latest.json` and decides only whether the
daily BTC field is admissible for the next hypothesis test. Default thresholds:
3 providers, 30 common daily candles, latest close dispersion <= 0.5%, max
window dispersion <= 0.75%. Passing this gate does not create a signal; it only
allows the Lab to define one mechanical POC/FVG/timeframe observable next.

Build the first timeframe matrix directly:

```bash
python3 domains/bitcoin-regime-lab/tools/btc_timeframe_matrix.py --write --json
```

This translates the "best timeframe" question into a matrix: monthly, weekly,
daily, 4h, 1h, 45m, 30m, 15m, 10m, 5m and 1m are classified as `testable`,
`watch` or `blocked` from current artifacts. It does not emit a trading signal;
it selects the next admissible test surface.

Build the BTC method-intake cards directly:

```bash
python3 domains/bitcoin-regime-lab/tools/btc_method_intake_card.py --write --json
```

This turns POC, LVN/Volume Profile voids, inefficiency, trendline, MM52 and
timeframe language into missing definitions, THIA questions, data requirements
and null/falsifier contracts. The default focus is now the
`volume_profile_lvn_void` card. It is not a signal tool.

Build the first daily-computable inefficiency candidate directly:

```bash
python3 domains/bitcoin-regime-lab/tools/btc_daily_inefficiency_candidate.py --write --json
```

This consumes `btc_exchange_ohlcv_latest.json`, creates a conservative daily
three-candle FVG/inefficiency proxy, and compares each zone with a matched
adjacent equal-width control. It is a test object for the Lab, not a target,
entry, exit or trading signal.

Build the first auto-ignition contract directly:

```bash
python3 domains/bitcoin-regime-lab/tools/btc_auto_ignite.py --write --json
```

This gathers the current BTC value artifacts, generates explicit provisional
assumptions for the LVN/Volume Profile method and writes
`dndlab.bitcoin.auto_ignite.v1`. The artifact includes a daily OHLCV
Volume Profile proxy, nearest LVN zones, baseline/null plan and simulator
candidate scope. It does not run a cognitive cycle and does not produce a
target, entry, exit or signal.

Test the generated LVN/Volume Profile proxy directly:

```bash
python3 domains/bitcoin-regime-lab/tools/btc_volume_profile_lvn_proxy.py --write --json
```

This performs a no-lookahead proxy backtest. For each event it builds the
profile from prior daily candles only, selects the nearest LVN zone and compares
forward closure against adjacent, opposite-distance and shuffled-volume
controls. It measures whether the proxy phenomenon is stronger than controls;
it does not define a buy/sell rule.

Default test profile: 45 prior daily candles, 10-day forward window, stride 3,
close-based closure. This gives enough events on the current 180-candle data
card and keeps the result conservative.

Run the first BTC Lab policy simulator manually:

```bash
python3 domains/bitcoin-regime-lab/tools/btc_policy_simulator.py --write --json
```

This writes `dndlab.bitcoin.policy_simulator.v1`. v0 starts from the LVN /
Volume Profile proxy and measures a declared historical zone-closure policy
against adjacent, opposite-distance, shuffled-volume, deterministic random
matched and strict union controls. It also reports walk-forward stability,
parameter sensitivity, a Lab-value score and a normal-chart comparison against
ordinary BTC daily forward returns over the same horizon. The score is research
usefulness, not PnL alone: a stable negative edge is useful evidence for
redesign/falsification and is labelled `decision=redesign`. In refresh hooks it
remains artifact generation only: it does not execute policy mutation, public
claims or operational action.

Build the daily closed-evidence gate:

```bash
python3 domains/bitcoin-regime-lab/tools/btc_daily_closed_evidence_gate.py --write --json
```

This writes `dndlab.bitcoin.daily_closed_evidence_gate.v1`. It separates the
current UTC daily candle from the latest fully closed common provider date.
The Lab may keep refreshing live context, but policy mutation or
LVN/FVG/timeframe reinterpretation must read the latest closed common date,
not the current open daily candle.

Build the first-class autological artifacts:

```bash
python3 domains/bitcoin-regime-lab/tools/btc_autology_artifacts.py --write --json
```

This writes three value artifacts:

- `dndlab.bitcoin.mnemos_memory.v1`: what the Lab retains, decays or sends to
  redesign.
- `dndlab.bitcoin.kairos_phase.v1`: the current admissible Lab phase/action.
- `dndlab.bitcoin.coherence_check.v1`: drift checks between gate, artifacts
  and no-operational boundary.

The tool reads local artifacts only. It does not fetch market data and does not
run a cognitive cycle.

Build the current cognitive/autological state:

```bash
python3 domains/bitcoin-regime-lab/tools/btc_cognitive_state.py --write --json
```

This writes `dndlab.bitcoin.cognitive_state.v1`. It does not fetch market data
and does not run a cycle. It reads the current seed, trajectory, MML and value
artifacts to show how the Lab is learning, where it is redesigning itself, and
which cognitive layers are still partial.
