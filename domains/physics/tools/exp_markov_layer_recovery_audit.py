#!/usr/bin/env python3
"""
exp_markov_layer_recovery_audit.py - META audit for the Markov-layer classifier.

Question:
  If a sequence is generated with known Markov order k, does the existing
  Mk0/Mk1/Mk2 classifier recover layer <= k?

Why this matters:
  Recent reports used Mk surrogate capture to claim two visible memory layers.
  This audit tests the opposite: whether the classifier itself creates apparent
  higher layers on finite Markov controls.

Controls:
  - prime_gaps: unknown real target, reported for comparison only
  - empirical_Mk0: shuffled prime gaps; known order 0
  - empirical_Mk1: prime-trained Mk1 surrogate; known order 1
  - empirical_Mk2: prime-trained Mk2 surrogate; known order 2
  - poisson_iid: independent exponential spacings; known order 0

Verdict rule:
  A control fails recovery when any observable is assigned layer > known order.
"""

import argparse
import json
from pathlib import Path

import numpy as np

from exp_two_layer_universality import (
    OBSERVABLES,
    classify_layer,
    gen_prime_gaps,
    generate_markov_surrogate,
)


def measure_all(gaps):
    out = {}
    for name, fn in OBSERVABLES.items():
        try:
            value = float(fn(gaps))
        except Exception:
            value = float("nan")
        out[name] = value
    return out


def classifier_pass(gaps, n_surr, rng):
    real_obs = measure_all(gaps)
    z_scores = {}

    for mk in (0, 1, 2):
        surr_obs = {name: [] for name in OBSERVABLES}
        for _ in range(n_surr):
            if mk == 0:
                surr = rng.permutation(gaps)
            else:
                surr = generate_markov_surrogate(gaps, mk, rng=rng)
            for obs_name, obs_fn in OBSERVABLES.items():
                try:
                    surr_obs[obs_name].append(float(obs_fn(surr)))
                except Exception:
                    pass

        z_mk = {}
        for obs_name in OBSERVABLES:
            vals = np.asarray(surr_obs[obs_name], dtype=float)
            vals = vals[np.isfinite(vals)]
            if len(vals) > 2 and np.std(vals) > 1e-12 and np.isfinite(real_obs[obs_name]):
                z = (real_obs[obs_name] - np.mean(vals)) / np.std(vals)
            else:
                z = 0.0
            z_mk[obs_name] = round(float(z), 2)
        z_scores[f"Mk{mk}"] = z_mk

    layers = {}
    for obs_name in OBSERVABLES:
        layers[obs_name] = classify_layer(
            z_scores["Mk0"][obs_name],
            z_scores["Mk1"][obs_name],
            z_scores["Mk2"][obs_name],
        )

    return real_obs, z_scores, layers


def build_controls(prime_gaps, rng):
    return {
        "prime_gaps": {
            "known_order": None,
            "gaps": prime_gaps,
        },
        "empirical_Mk0": {
            "known_order": 0,
            "gaps": rng.permutation(prime_gaps),
        },
        "empirical_Mk1": {
            "known_order": 1,
            "gaps": generate_markov_surrogate(prime_gaps, 1, rng=rng),
        },
        "empirical_Mk2": {
            "known_order": 2,
            "gaps": generate_markov_surrogate(prime_gaps, 2, rng=rng),
        },
        "poisson_iid": {
            "known_order": 0,
            "gaps": rng.exponential(1.0, len(prime_gaps)),
        },
    }


def summarize_failure(layers, known_order):
    if known_order is None:
        return {
            "status": "target_only",
            "over_layer_observables": [],
            "max_layer": int(max(layers.values())),
        }

    over = [name for name, layer in layers.items() if layer > known_order]
    return {
        "status": "PASS" if not over else "FAIL",
        "over_layer_observables": over,
        "max_layer": int(max(layers.values())),
    }


def run(N=60000, n_surr=20, seed=20260504):
    rng = np.random.default_rng(seed)
    prime_gaps = gen_prime_gaps(N).astype(float)
    controls = build_controls(prime_gaps, rng)

    results = {
        "N": int(N),
        "n_surr": int(n_surr),
        "seed": int(seed),
        "controls": {},
    }

    print(f"N={N}, n_surr={n_surr}, seed={seed}")
    print(f"{'sequence':<16} {'known':<7} {'status':<8} {'maxL':<5} over-layer observables")
    print("-" * 82)

    for name, spec in controls.items():
        real_obs, z_scores, layers = classifier_pass(spec["gaps"], n_surr, rng)
        summary = summarize_failure(layers, spec["known_order"])
        known = "target" if spec["known_order"] is None else f"L{spec['known_order']}"
        over = ", ".join(summary["over_layer_observables"]) or "-"
        print(f"{name:<16} {known:<7} {summary['status']:<8} L{summary['max_layer']:<4} {over}")

        results["controls"][name] = {
            "known_order": spec["known_order"],
            "n_gaps": int(len(spec["gaps"])),
            "real_obs": {k: round(v, 6) for k, v in real_obs.items()},
            "z_scores": z_scores,
            "layers": layers,
            "recovery": summary,
        }

    out_path = Path("tools/data/markov_layer_recovery_audit.json")
    with out_path.open("w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved to {out_path}")
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--N", type=int, default=60000)
    parser.add_argument("--n_surr", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260504)
    args = parser.parse_args()
    run(N=args.N, n_surr=args.n_surr, seed=args.seed)


if __name__ == "__main__":
    main()
