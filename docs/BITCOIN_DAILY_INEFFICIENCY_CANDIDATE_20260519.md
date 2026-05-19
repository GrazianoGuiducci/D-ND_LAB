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
declared forward fill window, and compares every candidate zone with:

- a matched adjacent equal-width control;
- a stricter dual-adjacent equal-width control that counts the null as filled
  when either the primary adjacent zone or the opposite adjacent zone fills in
  the same forward window.

## Current Verified Result

Latest refresh/cycle on 2026-05-19 wrote the daily inefficiency artifact with:

- decision: `watch`
- verdict: `DAILY_INEFFICIENCY_PROXY_STRICT_NULL_NOT_BEATEN`
- zones_total: `31`
- zones_evaluable: `31`
- zones_filled: `22`
- controls_evaluable: `31`
- controls_filled: `18`
- strict_controls_evaluable: `31`
- strict_controls_filled: `28`
- zone_fill_rate: `0.7097`
- control_fill_rate: `0.5806`
- strict_control_fill_rate: `0.9032`
- denominator_ready: `true`
- trading_signal: `false`

Interpretation: the simple daily FVG proxy is visible and useful for the Lab
surface, but it does not beat the stricter dual-adjacent null. It remains a
`watch` object and should not be re-promoted without a tighter mechanical
definition.

This result is compatible with the Alipio intake: the phrase "chiudere
l'inefficienza" appears to cover FVG/imbalance, LVN/Volume Profile void and CME
gap. The current tool tests only the daily FVG subtype. The next method work
should split the phrase into typed contracts before another cycle.

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
    "strict dual-adjacent null comparison",
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
