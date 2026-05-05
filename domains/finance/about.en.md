# AI-Lab D-ND Finance

> **A regime exists only if it survives the shuffle.**

This lab studies market regime shifts as **structural objects**, not as after-the-fact labels. Its first boundary is direct: separate a generative bull/bear dipole from a sequence that only looks regime-like after interpretation.

## How it operates

Every cycle compares two poles:

- **ordered market data** — returns with local memory, state transitions, and measurable orientation under the M operator;
- **naive control** — static VaR, realized volatility, and shuffled surrogates with the same distribution but destroyed order.

If the signal survives the shuffle, the regime is not just a word: it is structure. If it does not, the lab **does not promote** the finding.

## What you get

- **A/B findings** that are verifiable: D-ND vs naive baseline, with measurable effect-size (z-score) against shuffle
- **Transparent verdict** at every cycle: `DND_DELTA` (real regime) or `NO_DELTA` (illusion)
- **Packaged kernel** (maturation target): `dnd_kernel_finance_regime_shift`, a replicable protocol for hedge funds, family offices, and financial advisory

## Epistemic boundary

The lab does not promise price prediction. It measures **regime structure** — one level above "guessing direction". Five conditions are necessary for any promoted finding: real metric + shuffle null baseline + explicit naive baseline (VaR + vol) + D-ND delta ≥ 3σ + declared failure when the delta is absent.

The first cycle runs **sandboxed without network** on synthetic data. Public APIs (yfinance, FRED, CoinGecko, World Bank) bring real data into subsequent cycles — they do not replace the null test.

---

*Status: alpha · Validated by meta-falsifier M1-M6 6/6 PASS · Ready for first real cycle.*
