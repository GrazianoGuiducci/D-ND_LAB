#!/usr/bin/env python3
"""Synthetic regime-shift experiment for the D-ND finance lab.

Standalone CLI, no network. It compares an ordered bull/bear synthetic return
series against shuffled surrogates and a naive VaR/realized-vol baseline.
"""

from __future__ import annotations

import argparse
import json
import math
from typing import Any

import numpy as np


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
) -> dict[str, Any]:
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

    return {
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
        "_caveat": (
            "Synthetic data, NOT real-market evidence of regime. "
            "Use mode='realistic' (default) for GARCH+t-noise+sigmoid "
            "transition. mode='ideal' is a sanity check on engineered "
            "bull/bear with hard transition — produces enormous effect_z "
            "(~50-60) but is tautological by construction. Real evidence "
            "requires running on yfinance/CoinGecko data in cycle 2+."
        ),
    }


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
    args = parser.parse_args()

    summary = run_experiment(n=args.n, seed=args.seed, shuffles=args.shuffles, mode=args.mode)
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
