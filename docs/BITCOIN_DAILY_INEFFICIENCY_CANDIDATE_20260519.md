# Bitcoin Daily Inefficiency Candidate - 2026-05-19

Status: BTC Lab capability candidate, not public claim and not trading system.

## Position In The Movement

This capability continues the path opened by the Bitcoin method-intake cards:

```text
Alipio/Rea method language
  -> method card
  -> daily-computable observable
  -> data-card / matched null
  -> falsifier
  -> watch/test/reject
```

It exists because `inefficiency_closure` is the first method family that can be
tested with the current daily OHLCV field. Volume Profile POC remains blocked
until profile window, binning, source and tolerance are declared.

## Implemented Surface

- Tool: `domains/bitcoin-regime-lab/tools/btc_daily_inefficiency_candidate.py`
- Schema: `dndlab.bitcoin.daily_inefficiency.v1`
- Input: `data/bitcoin-regime-lab/value/btc_exchange_ohlcv_latest.json`
- Output: `data/bitcoin-regime-lab/value/btc_daily_inefficiency_latest.json`
- UI module: `InefficiencyMap` in `domains/bitcoin-regime-lab/ui_contract.json`
- Dashboard section: `Inefficienza daily BTC`

The tool builds a median daily OHLC series across available exchange-native
feeds, detects a conservative three-candle FVG/inefficiency proxy, evaluates a
declared forward fill window, and compares every candidate zone with an
adjacent equal-width control.

## Current Verified Result

Refresh run on 2026-05-19 wrote the daily inefficiency artifact with:

- decision: `watch`
- zones_total: `3`
- zones_evaluable: `3`
- zones_filled: `2`
- controls_evaluable: `3`
- controls_filled: `2`
- zone_fill_rate: `0.6667`
- control_fill_rate: `0.6667`
- denominator_ready: `false`
- trading_signal: `false`

Interpretation: the proxy is visible and useful for the Lab surface, but the
matched control currently fills at the same rate. It is a watch/test object, not
evidence that an inefficiency method has predictive value.

## Capability Cascade

```json
{
  "capability_id": "btc_daily_inefficiency_proxy",
  "source_domain": "bitcoin-regime-lab",
  "source_cycle": "value-refresh-20260519",
  "new_affordance": "Turn human FVG/inefficiency language into daily-computable zones with matched adjacent controls.",
  "immediate_domain": "bitcoin-regime-lab",
  "transferable_domains": ["finance", "research-radar", "monitoring"],
  "affected_surfaces": [
    "context",
    "mml",
    "tools",
    "ui_contract",
    "dashboard",
    "installer",
    "docs"
  ],
  "required_checks": [
    "denominator readiness",
    "matched control comparison",
    "no-lookahead forward window",
    "domain-native observable translation",
    "no-signal boundary"
  ],
  "non_admissible_transfer": [
    "BTC price zones",
    "buy/sell or target language",
    "manual FVG annotations as authority",
    "promotion to general meta-lab preset before another domain validates the movement"
  ],
  "next_question": "Can the meta-lab expose a generic gap/inefficiency capability pattern without copying BTC-specific content?"
}
```

## Meta-lab Boundary

This is a candidate for the meta-lab/installer as a pattern:

```text
human method phrase -> computable proxy -> matched control -> UI lens
```

It is not yet a general template. Promotion to the public installer should wait
until at least one other domain receives the same movement with its own
observables, nulls and UI lens.
