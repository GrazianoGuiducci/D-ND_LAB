# Bitcoin Regime Lab

`bitcoin-regime-lab` is a generated D-ND domain for BTC regime monitoring.

It does not provide financial advice, buy/sell signals, price targets, profit
claims or alpha. Its first purpose is to translate trader/domain language into:

- observable event schemas;
- data-cards;
- baselines and nulls;
- falsifier outcomes;
- UI states such as `observe`, `watch`, `test` and `reject`.

## First Boundary

The installed Lab is a reference boundary. Its smoke tool proves that the
domain is executable and keeps the no-claim contract:

```bash
python3 domains/bitcoin-regime-lab/tools/exp_request_smoke.py --json
```

Expected boundary:

```text
public_claim=false
trading_signal=false
operational=false
```

## Candidate Method Families

The seed contains method families only as hypotheses:

- volume profile POC / Naked POC lifecycle;
- LVN/HVN and FVG/imbalance zones;
- CME gap status;
- trendline retest and momentum change;
- Kumo confirmation/failure gates;
- feed robustness across Bitstamp, Binance, Coinbase and optional Kraken;
- timeframe matrix for Alipio's question.

None of these is authority before it becomes an observable with data source,
baseline, null and falsifier.

Detailed public-safe intake from Alipio's first annotated screenshots and
Massimo Rea-derived method notes is in:

```text
docs/BITCOIN_ALIPIO_METHOD_INTAKE_20260518.md
```

Use it as a question and method-card bridge for THIA and the Lab. It is not a
trading rule and does not include private raw images.

## Validation

Use:

```bash
python3 -m core.cli inspect --domain bitcoin-regime-lab
python3 -m core.cli dry-run --domain bitcoin-regime-lab
```

The first real cycle should add one domain-native experiment with a data-card
and matched null before any operational interpretation.
