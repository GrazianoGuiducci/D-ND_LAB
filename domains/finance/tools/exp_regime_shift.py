#!/usr/bin/env python3
"""Synthetic regime-shift experiment for the D-ND finance lab.

Standalone CLI, no network. It compares an ordered bull/bear synthetic return
series against shuffled surrogates and a naive VaR/realized-vol baseline.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from typing import Any

import numpy as np

# Permetti import di market_data quando il tool è chiamato dalla sua dir.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def synthetic_returns(n: int, seed: int, mode: str = "realistic") -> np.ndarray:
    """Return synthetic series.

    Modes:
    - "ideal" (legacy): hardcoded bull/bear with linear shock transition.
      Effect_z under D-ND orientation score is enormous (~50-60). Useful
      ONLY as sanity check that the pipeline produces a clear DND_DELTA
      verdict on a known-engineered case. NOT evidence of real regime.
    - "realistic" (default): heteroskedastic GARCH-like noise + smooth
      sigmoid transition + Student-t fat tails. Effect_z falls to ~3-15
      range — informative but not implausibly perfect. Closer to what
      real markets look like in finite samples.
    """
    rng = np.random.default_rng(seed)
    split = n // 2

    if mode == "ideal":
        bull = rng.normal(0.0011, 0.0075, split)
        bear = rng.normal(-0.0016, 0.0185, n - split)
        transition = np.zeros(n)
        width = min(12, n - split)
        transition[split:split + width] = np.linspace(-0.012, -0.045, width)
        return np.concatenate([bull, bear]) + transition

    # "realistic" mode (default)
    # Smooth sigmoid transition between regimes (no hard step)
    t = np.arange(n)
    transition_center = split
    transition_width = max(20, n // 25)
    blend = 1.0 / (1.0 + np.exp((t - transition_center) / transition_width))
    # blend = 1 in bull region, 0 in bear region, smooth in between
    mu_bull, mu_bear = 0.0008, -0.0011
    sigma_bull, sigma_bear = 0.0080, 0.0165
    mu = blend * mu_bull + (1 - blend) * mu_bear
    base_sigma = blend * sigma_bull + (1 - blend) * sigma_bear

    # GARCH-like heteroskedasticity: vol cluster around shocks
    df = 5.0  # Student-t degrees of freedom (fat tails)
    innov = rng.standard_t(df, size=n)
    # Vol clustering: |innov_{t-1}| influences sigma_t
    sigma = np.zeros(n)
    sigma[0] = base_sigma[0]
    persistence = 0.85
    arch_effect = 0.10
    for i in range(1, n):
        sigma[i] = np.sqrt(
            (1 - persistence - arch_effect) * base_sigma[i] ** 2
            + persistence * sigma[i - 1] ** 2
            + arch_effect * (innov[i - 1] * sigma[i - 1]) ** 2
        )
    returns = mu + sigma * innov / np.sqrt(df / (df - 2))  # t-scaled to unit-ish var

    return returns


def orientation_score(returns: np.ndarray) -> float:
    """Ordered split orientation: collapses when temporal order is destroyed.

    The synthetic regime is intentionally a two-state sequence: low-vol positive
    drift followed by high-vol negative drift. A shuffle preserves the marginal
    return distribution but destroys the first-half/second-half split.
    """
    if len(returns) < 4:
        return 0.0
    split = len(returns) // 2
    left = returns[:split]
    right = returns[split:]
    mean_gap = float(np.mean(left) - np.mean(right))
    vol_gap = float(np.std(right, ddof=1) - np.std(left, ddof=1))
    transition_gap = float(np.mean(returns[split:split + min(12, len(right))]) - np.mean(left))
    return mean_gap * vol_gap - transition_gap * abs(mean_gap)


def cassini_residue(returns: np.ndarray) -> float:
    lags = [1, 2, 3, 5, 8, 13, 21]
    centered = returns - returns.mean()
    denom = float(np.dot(centered, centered))
    if denom == 0:
        return math.nan
    ac = [float(np.dot(centered[:-lag], centered[lag:]) / denom) for lag in lags]
    residues = [
        abs(ac[i + 1] * ac[i - 1] - ac[i] ** 2)
        for i in range(1, len(ac) - 1)
    ]
    return float(np.mean(residues))


def run_experiment(
    n: int = 768,
    seed: int = 42,
    shuffles: int = 128,
    mode: str = "realistic",
    real_returns: np.ndarray | None = None,
    real_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run ordered-vs-shuffle protocol.

    Synthetic mode (default): generates returns via synthetic_returns().
    Real mode: caller passes `real_returns` (np.ndarray) + `real_meta`
    (data_card from market_data.fetch). This is the cycle 2+ path.
    """
    if real_returns is not None:
        returns = np.asarray(real_returns, dtype=float)
        n = len(returns)
        mode = "real"
    else:
        returns = synthetic_returns(n=n, seed=seed, mode=mode)
    ordered = abs(orientation_score(returns))

    rng = np.random.default_rng(seed + 1000)
    shuffle_scores = []
    shuffle_cassini = []
    for _ in range(shuffles):
        s = returns.copy()
        rng.shuffle(s)
        shuffle_scores.append(abs(orientation_score(s)))
        shuffle_cassini.append(cassini_residue(s))

    shuffle_arr = np.array(shuffle_scores, dtype=float)
    shuffle_mean = float(np.mean(shuffle_arr))
    shuffle_std = float(np.std(shuffle_arr, ddof=1)) if shuffles > 1 else 0.0
    effect_z = (ordered - shuffle_mean) / shuffle_std if shuffle_std > 0 else math.inf

    var_95 = float(np.quantile(returns, 0.05))
    realized_vol = float(np.std(returns, ddof=1) * math.sqrt(252))
    ordered_cassini = cassini_residue(returns)
    shuffle_cassini_mean = float(np.mean(shuffle_cassini))
    cassini_delta = float(shuffle_cassini_mean - ordered_cassini)

    verdict = "DND_DELTA" if effect_z > 3.0 and ordered > shuffle_mean else "NO_DELTA"

    out = {
        "n": n,
        "seed": seed,
        "shuffles": shuffles,
        "mode": mode,
        "ordered": ordered,
        "shuffle_mean": shuffle_mean,
        "shuffle_std": shuffle_std,
        "effect_z": float(effect_z),
        "var_95": var_95,
        "realized_vol": realized_vol,
        "cassini_residue": ordered_cassini,
        "shuffle_cassini_mean": shuffle_cassini_mean,
        "cassini_delta": cassini_delta,
        "verdict": verdict,
        "null_baseline": "shuffle returns: same distribution, destroyed order",
        "naive_baseline": "static VaR 95% + realized volatility",
    }
    if mode == "real":
        out["data_card"] = real_meta
        out["_caveat"] = (
            "Real-market data. Verdict applies to the specific window in "
            "data_card. Shuffle null is sample-conditional; significance "
            "must hold across multiple windows/eras to support a regime "
            "claim. A single-window DND_DELTA is necessary, not sufficient."
        )
    else:
        out["_caveat"] = (
            "Synthetic data, NOT real-market evidence of regime. "
            "Use mode='realistic' (default) for GARCH+t-noise+sigmoid "
            "transition. mode='ideal' is a sanity check on engineered "
            "bull/bear with hard transition — produces enormous effect_z "
            "(~50-60) but is tautological by construction. Real evidence "
            "requires running on yfinance/CoinGecko data in cycle 2+."
        )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=768)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--shuffles", type=int, default=128)
    parser.add_argument(
        "--mode",
        choices=["realistic", "ideal"],
        default="realistic",
        help="realistic: GARCH+t-noise+sigmoid (default, informative). ideal: engineered bull/bear sanity check (tautological).",
    )
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--from-market", metavar="PROVIDER:SYMBOL",
                        help="Use real OHLCV from market_data. Examples: "
                             "yfinance:SPY, yfinance:QQQ, coingecko:bitcoin. "
                             "Overrides --mode and --n (uses full available window).")
    parser.add_argument("--market-period", default="1y",
                        help="Period for yfinance (default 1y); ignored for coingecko")
    parser.add_argument("--market-start",
                        help="Explicit yfinance start date YYYY-MM-DD; requires --market-end")
    parser.add_argument("--market-end",
                        help="Explicit yfinance end date YYYY-MM-DD; requires --market-start")
    parser.add_argument("--market-days", type=int, default=365,
                        help="Days for coingecko (default 365); ignored for yfinance")
    args = parser.parse_args()

    real_returns = None
    real_meta = None
    if args.from_market:
        try:
            provider, symbol = args.from_market.split(":", 1)
        except ValueError:
            print(f"--from-market expects PROVIDER:SYMBOL, got {args.from_market!r}",
                  file=sys.stderr)
            sys.exit(2)
        from market_data import fetch  # type: ignore[import-not-found]
        kwargs: dict[str, Any] = {}
        if provider == "yfinance":
            kwargs["period"] = args.market_period
            if args.market_start or args.market_end:
                if not (args.market_start and args.market_end):
                    print("--market-start and --market-end must be provided together",
                          file=sys.stderr)
                    sys.exit(2)
                kwargs["start"] = args.market_start
                kwargs["end"] = args.market_end
        else:
            kwargs["days"] = args.market_days
        d = fetch(provider, symbol, **kwargs)
        real_returns = d["returns"]
        real_meta = d["data_card"]

    summary = run_experiment(n=args.n, seed=args.seed, shuffles=args.shuffles, mode=args.mode,
                             real_returns=real_returns, real_meta=real_meta)
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
        return

    print("D-ND finance regime-shift synthetic experiment")
    print(f"ordered_orientation_abs: {summary['ordered']:.9f}")
    print(f"shuffle_mean:            {summary['shuffle_mean']:.9f}")
    print(f"shuffle_std:             {summary['shuffle_std']:.9f}")
    print(f"effect_z:                {summary['effect_z']:.3f}")
    print(f"VaR_95:                  {summary['var_95']:.5f}")
    print(f"realized_vol:            {summary['realized_vol']:.4f}")
    print(f"cassini_residue:         {summary['cassini_residue']:.9f}")
    print(f"shuffle_cassini_mean:    {summary['shuffle_cassini_mean']:.9f}")
    print(f"verdict:                 {summary['verdict']}")


if __name__ == "__main__":
    main()
