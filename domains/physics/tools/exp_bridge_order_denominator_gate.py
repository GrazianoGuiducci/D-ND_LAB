#!/usr/bin/env python3
"""
exp_bridge_order_denominator_gate.py

Falsification attempt for ORDER_DENOMINATOR_GATE on bridge/perimeter sequences
already present in the D-ND lab context:

- prime metric connection fluctuations from g=(p/2)^2
- prime metric curvature fluctuations dR
- zeta trace-bridge nonlinear residuals
- hydrogen bound-level spacings from the QxE bridge

The coherent endpoint is the observed/generated bridge order. The illusory
endpoint is a marginal-preserving permutation. Canonical observables come from
observables_registry.py.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

from exp_semireal_order_denominator_gate import analyze_sequence, compact, normalize
from observables_registry import OBSERVABLES_REGISTRY_VERSION, OBSERVABLES_CANONICAL


OBS_NAMES = list(OBSERVABLES_CANONICAL.keys())
PHI = (1.0 + math.sqrt(5.0)) / 2.0
LAMBDA = -1.0 / PHI**2
DATA_DIR = Path(__file__).parent / "data"


def sieve_primes_for_count(n_primes: int) -> np.ndarray:
    if n_primes < 6:
        limit = 20
    else:
        limit = int(n_primes * (math.log(n_primes) + math.log(math.log(n_primes))) * 1.35)
    while True:
        sieve = np.ones(limit + 1, dtype=bool)
        sieve[:2] = False
        for p in range(2, int(limit**0.5) + 1):
            if sieve[p]:
                sieve[p * p : limit + 1 : p] = False
        primes = np.flatnonzero(sieve)
        if len(primes) >= n_primes:
            return primes[:n_primes].astype(float)
        limit *= 2


def positive_bridge_values(values: np.ndarray) -> np.ndarray:
    """Map a signed bridge observable to positive values without changing order."""
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    values = np.abs(values)
    return normalize(values + 1e-12)


def prime_metric_delta_gamma(n_values: int) -> np.ndarray:
    primes = sieve_primes_for_count(n_values + 3)
    p = primes.astype(float)
    tau = np.log(p)
    metric = (p / 2.0) ** 2
    dg = np.diff(metric)
    dtau = np.diff(tau)
    mid = (metric[:-1] + metric[1:]) / 2.0
    gamma = dg / (2.0 * mid * dtau)
    delta_gamma = np.diff(gamma)
    return positive_bridge_values(delta_gamma[:n_values])


def prime_metric_dR(n_values: int) -> np.ndarray:
    primes = sieve_primes_for_count(n_values + 3)
    seq = primes.astype(float)
    t = np.log(seq)
    a = seq / 2.0
    dt = np.diff(t)
    dt_mid = (dt[:-1] + dt[1:]) / 2.0
    da = np.diff(a)
    a_prime = da / dt
    da_prime = np.diff(a_prime)
    a_double_prime = da_prime / dt_mid
    r_n = 2.0 * a_double_prime / a[1:-1]
    d_r = r_n - 2.0
    return positive_bridge_values(d_r[:n_values])


def load_zeta_zeros(n_zeros: int) -> np.ndarray:
    zeros_file = DATA_DIR / "odlyzko_cache" / "zeros1.txt"
    if not zeros_file.exists():
        raise RuntimeError(f"{zeros_file} not found")
    zeros: list[float] = []
    with zeros_file.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            zeros.append(float(line))
            if len(zeros) >= n_zeros:
                break
    if len(zeros) < n_zeros:
        raise RuntimeError(f"only {len(zeros)} zeta zeros available, need {n_zeros}")
    return np.array(zeros, dtype=float)


def dnd_map_trajectory(x0: float, n_iter: int) -> np.ndarray:
    x = float(x0)
    traj = [x]
    for _ in range(n_iter):
        if abs(x) < 1e-15:
            break
        x = 1.0 + 1.0 / x
        if not np.isfinite(x):
            break
        traj.append(x)
    return np.array(traj, dtype=float)


def zeta_trace_residual(n_values: int, step: int = 5) -> np.ndarray:
    zeros = load_zeta_zeros(n_values)
    residuals = []
    for x0 in zeros:
        traj = dnd_map_trajectory(float(x0), max(step + 2, 15))
        if len(traj) <= step:
            continue
        linear = PHI + (float(x0) - PHI) * (LAMBDA**step)
        residuals.append(traj[step] - linear)
    return positive_bridge_values(np.array(residuals[:n_values], dtype=float))


def hydrogen_bound_level_spacings(n_values: int) -> np.ndarray:
    # Atomic units: E_n = -1/(2n^2). Positive adjacent spacings shrink smoothly.
    n = np.arange(1, n_values + 2, dtype=float)
    energy = -1.0 / (2.0 * n**2)
    spacings = np.diff(energy)
    return normalize(spacings)


def build_sequences(args: argparse.Namespace) -> dict[str, np.ndarray]:
    return {
        "prime_metric_delta_gamma_abs": prime_metric_delta_gamma(args.n_gaps),
        "prime_metric_dR_abs": prime_metric_dR(args.n_gaps),
        "zeta_trace_residual_step5_abs": zeta_trace_residual(args.zeta_values, step=5),
        "hydrogen_bound_level_spacings": hydrogen_bound_level_spacings(args.n_gaps),
    }


def run(args: argparse.Namespace) -> dict:
    root_rng = np.random.default_rng(args.seed)
    sequences = build_sequences(args)
    perimeters = {}
    for name, base in sequences.items():
        perimeters[name] = analyze_sequence(name, base, args, root_rng)

    output = {
        "experiment": "bridge_order_denominator_gate",
        "category": "gate_falsification_bridge",
        "question": "Does ORDER_DENOMINATOR_GATE survive on D-ND bridge sequences beyond prime/zeta/logistic gaps?",
        "observables_registry": OBSERVABLES_REGISTRY_VERSION,
        "observables_used": OBS_NAMES,
        "params": vars(args),
        "matrix": compact(perimeters),
        "perimeters": perimeters,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        json.dump(output, f, indent=2)

    print(f"observables_registry={OBSERVABLES_REGISTRY_VERSION}")
    print(f"observables_used={OBS_NAMES}")
    print("perimeter n one_sided stable0 stable1 dist_gate ambiguous_gate")
    for name, row in output["matrix"].items():
        print(
            f"{name:>34s} "
            f"{row['n_gaps']:>5d} "
            f"{','.join(row['coherent_one_sided_observables']) or '[]':>22s} "
            f"{row['stable_count_coherent']:>7.3f} "
            f"{row['stable_count_illusory']:>7.3f} "
            f"{row['endpoint_distance_one_sided_gated']:>9.3f} "
            f"{row['ambiguous_beta_one_sided_gated']}"
        )
    print(f"saved {out_path}")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-gaps", type=int, default=4096)
    parser.add_argument("--zeta-values", type=int, default=2000)
    parser.add_argument("--n-replicates", type=int, default=20)
    parser.add_argument("--n-beta", type=int, default=11)
    parser.add_argument("--n-baseline", type=int, default=32)
    parser.add_argument("--z-min", type=float, default=2.0)
    parser.add_argument("--seed", type=int, default=202605070942)
    parser.add_argument("--out", default="tools/data/bridge_order_denominator_gate_20260507_0942.json")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
