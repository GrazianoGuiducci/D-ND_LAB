# AI-Lab D-ND Bitcoin Regime Lab

Generated candidate from `domain_request`.

Status: reference candidate only. Run strict M1-M8 before install.

Intent:

```text
Monitor BTC regime hypotheses and falsify weak operational interpretations before they become operational claims, starting from Alipio's timeframe question and derived POC/Kumo/feed-robustness method candidates.
```

## First Value Artifact

Generate a BTC context data-card for the dashboard:

```bash
python3 domains/bitcoin-regime-lab/tools/btc_market_card.py --write --json
```

The artifact is written under `data/bitcoin-regime-lab/value/` and appears in
Campo through `latest_value_artifacts`. It is an observe-only context card:
price, 1d/7d/30d changes, realized-volatility proxy, source and retrieval
timestamp. It is not a trading signal and does not authorize buy/sell/target
language.

Refresh all value-facing Bitcoin artifacts without running a cognitive cycle:

```bash
bash tools/bitcoin-refresh-value.sh
```

This wrapper runs the market context card and the exchange-native OHLCV
robustness card, then builds the first falsifiable hypothesis card. It is safe
for cron because it uses only public no-key APIs and writes only
`data/bitcoin-regime-lab/value/*`.

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
