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
