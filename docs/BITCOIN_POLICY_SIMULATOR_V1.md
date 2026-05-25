# Bitcoin Policy Simulator v1

Status: manual-only research contract.

`dndlab.bitcoin.policy_simulator.v1` is a BTC Lab research artifact for
measuring declared historical method policies against controls. It is not a
generic backtest layer: the simulator must preserve the Lab chain

```text
observable -> data-card -> baseline/null -> falsifier -> artifact -> value
```

## Current v0 Scope

Tool:

```bash
python3 domains/bitcoin-regime-lab/tools/btc_policy_simulator.py --write --json
```

Initial method:

```text
volume_profile_lvn_void
```

Initial policy:

```text
btc_policy_simulator_v0.lvn_close_policy
```

The policy builds a daily OHLCV Volume Profile proxy from prior candles,
selects the nearest LVN zone to the event close, then measures whether the zone
is closed inside a declared forward window. It compares that policy with
adjacent, opposite-distance, shuffled-volume, deterministic random matched and
strict union controls.

## Required Artifact Fields

- `schema`
- `generated_at`
- `domain`
- `version`
- `input_artifacts`
- `research_frame`
- `policy_contract`
- `summary`
- `card`
- `metrics`
- `lab_value`
- `walk_forward`
- `relation_slices`
- `parameter_sensitivity`
- `research_controls`
- `events`

## Required Research Controls

```json
{
  "closed_data_only": true,
  "open_candle_exclusion": true,
  "no_lookahead": true,
  "simulated_policy_declared": true,
  "historical_result": true,
  "research_metric": true,
  "deterministic_random_matched_controls": true
}
```

The simulator excludes the latest event by default because the current daily
candle can refresh without creating new closed evidence.

## Lab Value

`lab_value_score` is not a profit score. It measures research usefulness:

- enough denominator;
- separation from controls, positive or negative;
- walk-forward stability;
- parameter sensitivity;
- current/open candle exclusion.

A negative edge can still have high Lab value if it is stable, because it tells
the Lab that the current method-policy contract should be redesigned or
falsified rather than promoted.

When the evidence is useful but negative against the strict control, the card
uses `decision=redesign` and `research_decision=redesign`. This keeps useful
negative evidence distinct from both a weak result and a positive method edge.

## Integration Boundary

The simulator is manual-only until reviewed. Do not add it to
`tools/bitcoin-refresh-value.sh`, `pre_cycle_value_refresh.sh`, the cognitive
cycle, API-specific UI handling or cron until a manual artifact has been
inspected.
