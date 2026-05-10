#!/usr/bin/env python3
"""HRV regime-shift experiment for the D-ND bio-rhythms lab.

Standalone CLI. It compares an ordered HRV regime-shift series against
shuffled surrogates and a naive RMSSD/SDNN baseline.

Modes:
- "realistic" (default): AR-1 + lognormal RR-intervals + sigmoid
  transition (rest → activity / normal → arrhythmia). Effect_z is in
  the 3-15 range — informative but not implausibly perfect, similar
  to what real HRV recordings look like under shuffle null.
- "ideal" (legacy): hardcoded normal/arrhythmia with hard transition.
  Useful only as sanity check that the pipeline produces a clear
  DND_DELTA verdict on a known-engineered case. NOT evidence of real
  regime.

Real-data path (cycle 2+): use --from-physionet to pull RR-interval
sequences via tools/biosignal_data.py.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from typing import Any

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def synthetic_rr_intervals(n: int, seed: int, mode: str = "realistic") -> np.ndarray:
    """Generate synthetic RR-interval series in milliseconds.

    Realistic mode: AR-1 noise around regime mean with sigmoid
    transition. Two regimes: 'rest' (mean ~900ms, low variability)
    → 'activity' (mean ~600ms, higher variability).

    Ideal mode: hardcoded hard-transition rest → arrhythmia (effect_z
    enormous, tautological).
    """
    rng = np.random.default_rng(seed)
    split = n // 2

    if mode == "ideal":
        rest = rng.normal(900.0, 25.0, split)
        arrhythmia = rng.normal(700.0, 80.0, n - split)
        # hard transition with strong directional shock
        shock = np.zeros(n)
        width = min(8, n - split)
        shock[split:split + width] = np.linspace(-100, -200, width)
        return np.concatenate([rest, arrhythmia]) + shock

    # realistic
    t = np.arange(n)
    transition_center = split
    transition_width = max(15, n // 30)
    blend = 1.0 / (1.0 + np.exp((t - transition_center) / transition_width))
    # blend = 1 in rest, 0 in activity, smooth between
    mu_rest, mu_active = 900.0, 650.0
    sigma_rest, sigma_active = 30.0, 70.0
    mu = blend * mu_rest + (1 - blend) * mu_active
    base_sigma = blend * sigma_rest + (1 - blend) * sigma_active

    # AR-1 noise + lognormal-ish heavy tail via Student-t innovations
    df = 6.0
    innov = rng.standard_t(df, size=n)
    rr = np.zeros(n)
    rr[0] = mu[0]
    persistence = 0.55
    for i in range(1, n):
        target = mu[i]
        drift = persistence * (rr[i - 1] - target)
        rr[i] = target + drift + base_sigma[i] * innov[i] / np.sqrt(df / (df - 2))

    # RR-intervals must be positive (clip)
    return np.maximum(rr, 250.0)


def orientation_score(rr: np.ndarray) -> float:
    """Ordered split orientation: collapses when temporal order is destroyed.

    Two-regime sequence: rest (high mean RR, low variability) →
    activity (low mean RR, high variability). Shuffle preserves the
    marginal distribution but destroys the first-half/second-half
    split.
    """
    if len(rr) < 4:
        return 0.0
    split = len(rr) // 2
    left = rr[:split]
    right = rr[split:]
    mean_gap = float(np.mean(left) - np.mean(right))  # positive in rest→activity
    vol_gap = float(np.std(right, ddof=1) - np.std(left, ddof=1))  # positive
    transition_gap = float(np.mean(rr[split:split + min(12, len(right))]) - np.mean(left))
    return mean_gap * vol_gap - transition_gap * abs(mean_gap)


def cassini_residue(rr: np.ndarray) -> float:
    lags = [1, 2, 3, 5, 8, 13, 21]
    centered = rr - rr.mean()
    denom = float(np.dot(centered, centered))
    if denom == 0:
        return math.nan
    ac = [float(np.dot(centered[:-lag], centered[lag:]) / denom) for lag in lags]
    residues = [
        abs(ac[i + 1] * ac[i - 1] - ac[i] ** 2)
        for i in range(1, len(ac) - 1)
    ]
    return float(np.mean(residues))


def rmssd(rr: np.ndarray) -> float:
    """Root mean square of successive differences (ms). Standard HRV."""
    if len(rr) < 2:
        return math.nan
    diffs = np.diff(rr)
    return float(np.sqrt(np.mean(diffs ** 2)))


def sdnn(rr: np.ndarray) -> float:
    """Standard deviation of NN intervals (ms). Standard HRV."""
    if len(rr) < 2:
        return math.nan
    return float(np.std(rr, ddof=1))


def run_experiment(
    n: int = 600,
    seed: int = 42,
    shuffles: int = 128,
    mode: str = "realistic",
    real_rr: np.ndarray | None = None,
    real_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run ordered-vs-shuffle protocol on RR-interval series.

    Synthetic mode (default): generates RR via synthetic_rr_intervals().
    Real mode: caller passes real_rr (np.ndarray, ms) + real_meta
    (data_card from biosignal_data.fetch).
    """
    if real_rr is not None:
        rr = np.asarray(real_rr, dtype=float)
        n = len(rr)
        mode = "real"
    else:
        rr = synthetic_rr_intervals(n=n, seed=seed, mode=mode)

    ordered = abs(orientation_score(rr))

    rng = np.random.default_rng(seed + 1000)
    shuffle_scores = []
    shuffle_cassini = []
    for _ in range(shuffles):
        s = rr.copy()
        rng.shuffle(s)
        shuffle_scores.append(abs(orientation_score(s)))
        shuffle_cassini.append(cassini_residue(s))

    shuffle_arr = np.array(shuffle_scores, dtype=float)
    shuffle_mean = float(np.mean(shuffle_arr))
    shuffle_std = float(np.std(shuffle_arr, ddof=1)) if shuffles > 1 else 0.0
    effect_z = (ordered - shuffle_mean) / shuffle_std if shuffle_std > 0 else math.inf

    naive_rmssd = rmssd(rr)
    naive_sdnn = sdnn(rr)
    ordered_cassini = cassini_residue(rr)
    shuffle_cassini_mean = float(np.mean(shuffle_cassini))
    cassini_delta = float(shuffle_cassini_mean - ordered_cassini)

    verdict = "DND_DELTA" if effect_z > 3.0 and ordered > shuffle_mean else "NO_DELTA"

    out: dict[str, Any] = {
        "n": n,
        "seed": seed,
        "shuffles": shuffles,
        "mode": mode,
        "ordered": ordered,
        "shuffle_mean": shuffle_mean,
        "shuffle_std": shuffle_std,
        "effect_z": float(effect_z),
        "rmssd_ms": naive_rmssd,
        "sdnn_ms": naive_sdnn,
        "cassini_residue": ordered_cassini,
        "shuffle_cassini_mean": shuffle_cassini_mean,
        "cassini_delta": cassini_delta,
        "verdict": verdict,
        "null_baseline": "shuffle RR: same distribution, destroyed order",
        "naive_baseline": "RMSSD + SDNN time-domain HRV",
    }
    if mode == "real":
        out["data_card"] = real_meta
        out["_caveat"] = (
            "Real biosignal. Verdict applies to the specific record/window in "
            "data_card. Shuffle null is sample-conditional; significance must "
            "hold across multiple records/subjects to support a regime claim. "
            "Single-record DND_DELTA is necessary, not sufficient. NESSUN "
            "claim diagnostico — il lab misura struttura nel segnale."
        )
    else:
        out["_caveat"] = (
            "Synthetic data, NOT evidence of regime in any real subject. "
            "Use mode='realistic' (default) for AR-1 + Student-t HRV. "
            "mode='ideal' is a sanity check on engineered hard-transition — "
            "produces enormous effect_z but is tautological by construction. "
            "Real evidence requires running on PhysioNet data in cycle 2+."
        )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--n", type=int, default=600,
                        help="number of RR-intervals (default 600 ≈ 10 min)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--shuffles", type=int, default=128)
    parser.add_argument(
        "--mode",
        choices=["realistic", "ideal"],
        default="realistic",
        help="realistic: AR-1 + Student-t (default). ideal: engineered hard transition (tautological).",
    )
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--from-physionet", metavar="DB/RECORD",
                        help="Use real RR via biosignal_data. Example: nsr2db/sel100. "
                             "Overrides --mode and --n.")
    args = parser.parse_args()

    real_rr = None
    real_meta = None
    if args.from_physionet:
        from biosignal_data import fetch  # type: ignore[import-not-found]
        d = fetch("physionet", args.from_physionet, signal="RR")
        real_rr = d["rr_ms"]
        real_meta = d["data_card"]

    summary = run_experiment(
        n=args.n, seed=args.seed, shuffles=args.shuffles, mode=args.mode,
        real_rr=real_rr, real_meta=real_meta,
    )
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True, default=str))
        return

    print("D-ND bio-rhythms HRV regime-shift experiment")
    print(f"mode:                    {summary['mode']}")
    print(f"n RR-intervals:          {summary['n']}")
    print(f"ordered_orientation_abs: {summary['ordered']:.3f}")
    print(f"shuffle_mean:            {summary['shuffle_mean']:.3f}")
    print(f"shuffle_std:             {summary['shuffle_std']:.3f}")
    print(f"effect_z:                {summary['effect_z']:.3f}")
    print(f"RMSSD (ms):              {summary['rmssd_ms']:.2f}")
    print(f"SDNN (ms):               {summary['sdnn_ms']:.2f}")
    print(f"cassini_residue:         {summary['cassini_residue']:.6f}")
    print(f"verdict:                 {summary['verdict']}")


if __name__ == "__main__":
    main()
