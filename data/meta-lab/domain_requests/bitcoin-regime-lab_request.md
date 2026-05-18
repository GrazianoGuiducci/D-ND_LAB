# Domain Request — bitcoin-regime-lab

Status: request captured, candidate only.

## Intent

Monitor BTC regime hypotheses and falsify weak operational interpretations
before they become signals. The first useful public question is Alipio's
timeframe question:

```text
Which timeframe makes the candidate BTC methods observable, stable and
falsifiable: monthly, weekly, daily, 4h, 1h, 45m, 30m, 15m, 10m, 5m or 1m?
```

The Lab must answer through a validation matrix, not by opinion.

## Candidate Methods

- POC / Naked POC lifecycle.
- Volume Profile POC, VAH, VAL, LVN/HVN.
- Inefficiency / FVG / CME gap closure.
- Trendline retest and momentum change.
- Kumo confirmation/failure gate.
- Feed robustness across Bitstamp, Binance, Coinbase and optional Kraken.

## Boundary

No buy/sell, entry/exit, price-target, alpha, profit or financial advice.
Methods from Alipio/Massimo Rea are source language until translated into:

```text
observable -> data-card -> baseline/null -> falsifier -> UI status
```

## First Candidate Output

The first generated candidate should expose:

- data-card contract;
- timeframe matrix;
- POC/Naked POC first-touch event contract;
- feed robustness gate;
- nulls: matched random levels, shuffled volume profile, equal-width zone
  fill-rate, adjacent-window control and walk-forward split;
- UI modules for Overview, Timeframe Matrix, Chart, POC/Naked POC, Kumo/Regime,
  Feed Robustness, Validation and Sources.
