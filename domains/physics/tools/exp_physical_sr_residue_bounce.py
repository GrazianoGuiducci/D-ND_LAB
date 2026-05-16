#!/usr/bin/env python3
"""
Physical bounce for the prime-minus-mod6 selective residue.

Route:
  physical A: quantum-chaotic GUE spectra
  mathematical transducer: span-matched Poisson counter-boundary
  physical B: 1D Anderson tight-binding spectra across disorder

The experiment asks whether the component split exposed by the prime/mod6
deposit has a concrete spectral analogue: SR can be absorbed by a span-matched
counter-boundary at a localized endpoint, while chaotic spectra keep SR active.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from observables_registry import OBSERVABLES_CANONICAL, OBSERVABLES_REGISTRY_VERSION


FOCUS_OBS = ["SR", "L1", "triple_var"]
DEFAULT_OUT = Path("tools/data/physical_sr_residue_bounce_20260514_1612.json")
DEFAULT_FIT_READY_OUT = Path("tools/data/component_state_fit_ready_20260514_1649.json")


def normalize_gaps(levels: np.ndarray, central_fraction: float) -> np.ndarray:
    levels = np.sort(np.asarray(levels, dtype=float))
    n = len(levels)
    keep = max(8, int(n * central_fraction))
    start = (n - keep) // 2
    central = levels[start : start + keep]
    gaps = np.diff(central)
    gaps = gaps[np.isfinite(gaps) & (gaps > 1e-12)]
    if len(gaps) == 0:
        return gaps
    return gaps / float(np.mean(gaps))


def gue_levels(n: int, rng: np.random.Generator) -> np.ndarray:
    real = rng.normal(size=(n, n))
    imag = rng.normal(size=(n, n))
    mat = (real + 1j * imag)
    hermitian = (mat + mat.conj().T) / (2.0 * np.sqrt(n))
    return np.linalg.eigvalsh(hermitian)


def goe_levels(n: int, rng: np.random.Generator) -> np.ndarray:
    mat = rng.normal(size=(n, n))
    symmetric = (mat + mat.T) / (2.0 * np.sqrt(n))
    return np.linalg.eigvalsh(symmetric)


def anderson_levels(n: int, disorder: float, rng: np.random.Generator) -> np.ndarray:
    diagonal = rng.uniform(-disorder / 2.0, disorder / 2.0, size=n)
    matrix = np.diag(diagonal)
    off = np.ones(n - 1)
    matrix += np.diag(off, 1) + np.diag(off, -1)
    return np.linalg.eigvalsh(matrix)


def span_matched_poisson_gaps(level_count: int, rng: np.random.Generator) -> np.ndarray:
    levels = np.sort(rng.random(level_count))
    gaps = np.diff(levels)
    gaps = gaps[gaps > 1e-12]
    if len(gaps) == 0:
        return gaps
    return gaps / float(np.mean(gaps))


def compute_obs(gaps: np.ndarray) -> dict[str, float]:
    return {name: float(fn(gaps)) for name, fn in OBSERVABLES_CANONICAL.items()}


def load_spectrum_records(path: Path, expected_class: str | None = None) -> list[dict[str, Any]]:
    """Load a single spectrum or a small record set for the fit-ready interface."""
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list) and all(isinstance(item, (int, float)) for item in payload):
            return [{"label": path.stem, "expected_class": expected_class, "levels": payload}]
        if isinstance(payload, dict):
            if "spectra" in payload:
                records = payload["spectra"]
            elif "levels" in payload or "spectrum" in payload:
                records = [payload]
            else:
                raise ValueError("JSON input must contain levels, spectrum, or spectra")
            normalized = []
            for index, record in enumerate(records):
                levels = record.get("levels", record.get("spectrum"))
                if levels is None:
                    raise ValueError(f"spectrum record {index} has no levels/spectrum field")
                normalized.append(
                    {
                        "label": record.get("label", f"{path.stem}_{index}"),
                        "expected_class": record.get("expected_class", expected_class),
                        "levels": levels,
                    }
                )
            return normalized
        raise ValueError("unsupported JSON spectrum payload")

    levels = np.loadtxt(path, dtype=float)
    return [{"label": path.stem, "expected_class": expected_class, "levels": levels.tolist()}]


def sign_swap_p(values: np.ndarray, rng: np.random.Generator, trials: int) -> float:
    if len(values) == 0:
        return 1.0
    observed = abs(float(np.mean(values)))
    null = []
    for _ in range(trials):
        signs = rng.choice(np.array([-1.0, 1.0]), size=len(values), replace=True)
        null.append(abs(float(np.mean(values * signs))))
    null_arr = np.array(null, dtype=float)
    return float((np.sum(null_arr >= observed) + 1) / (len(null_arr) + 1))


def summarize(label: str, rows: list[dict[str, Any]], rng: np.random.Generator, trials: int) -> dict[str, Any]:
    deltas = {
        obs: np.array([row["delta"][obs] for row in rows], dtype=float)
        for obs in OBSERVABLES_CANONICAL
    }
    summary: dict[str, Any] = {
        "label": label,
        "sample_count": len(rows),
        "component_state": {},
        "mean_real": {},
        "mean_null": {},
        "mean_delta": {},
        "p_two_sided": {},
        "cohen_d_delta": {},
    }
    for obs, values in deltas.items():
        real_values = np.array([row["real"][obs] for row in rows], dtype=float)
        null_values = np.array([row["null"][obs] for row in rows], dtype=float)
        mean_delta = float(np.mean(values))
        sd = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
        p_value = sign_swap_p(values, rng, trials)
        effect = mean_delta / sd if sd > 1e-12 else 0.0
        active = p_value <= 0.01 and abs(effect) >= 0.5
        summary["mean_real"][obs] = float(np.mean(real_values))
        summary["mean_null"][obs] = float(np.mean(null_values))
        summary["mean_delta"][obs] = mean_delta
        summary["p_two_sided"][obs] = p_value
        summary["cohen_d_delta"][obs] = effect
        summary["component_state"][obs] = "active" if active else "absorbed"
    summary["focus_signature"] = [
        obs for obs in FOCUS_OBS if summary["component_state"][obs] == "active"
    ]
    return summary


def contrast(
    label: str,
    left_rows: list[dict[str, Any]],
    right_rows: list[dict[str, Any]],
    rng: np.random.Generator,
    trials: int,
) -> dict[str, Any]:
    paired = min(len(left_rows), len(right_rows))
    result: dict[str, Any] = {
        "label": label,
        "paired_count": paired,
        "mean_left_minus_right": {},
        "p_two_sided": {},
        "cohen_d": {},
        "state": {},
    }
    for obs in OBSERVABLES_CANONICAL:
        values = np.array(
            [
                left_rows[i]["real"][obs] - right_rows[i]["real"][obs]
                for i in range(paired)
            ],
            dtype=float,
        )
        mean_delta = float(np.mean(values)) if len(values) else 0.0
        sd = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
        p_value = sign_swap_p(values, rng, trials)
        effect = mean_delta / sd if sd > 1e-12 else 0.0
        active = p_value <= 0.01 and abs(effect) >= 0.5
        result["mean_left_minus_right"][obs] = mean_delta
        result["p_two_sided"][obs] = p_value
        result["cohen_d"][obs] = effect
        result["state"][obs] = "separated" if active else "not_separated"
    return result


def evaluate_input_spectra(args: argparse.Namespace) -> dict[str, Any]:
    rng = np.random.default_rng(args.seed)
    records = load_spectrum_records(args.input_spectrum, args.expected_class)
    trace_path = Path(str(args.output).replace(".json", ".trace.jsonl"))
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    rows_by_class: dict[str, list[dict[str, Any]]] = {}
    direct_rows_by_class: dict[str, list[dict[str, Any]]] = {}

    with trace_path.open("w", encoding="utf-8") as trace:
        for record in records:
            levels = np.asarray(record["levels"], dtype=float)
            gaps = normalize_gaps(levels, args.central_fraction)
            if len(gaps) < 12:
                raise ValueError(f"spectrum {record['label']} has fewer than 12 usable central gaps")
            real_obs = compute_obs(gaps)
            class_key = record.get("expected_class") or record["label"]
            direct_rows_by_class.setdefault(class_key, []).append(
                {
                    "event": "input_spectrum_direct",
                    "label": record["label"],
                    "expected_class": record.get("expected_class"),
                    "n_levels": int(len(levels)),
                    "n_gaps": int(len(gaps)),
                    "real": real_obs,
                }
            )
            for null_rep in range(args.null_reps):
                null_gaps = span_matched_poisson_gaps(len(gaps) + 1, rng)
                null_obs = compute_obs(null_gaps)
                row = {
                    "event": "input_spectrum_pair",
                    "label": record["label"],
                    "expected_class": record.get("expected_class"),
                    "null_rep": null_rep,
                    "n_levels": int(len(levels)),
                    "n_gaps": int(len(gaps)),
                    "real": real_obs,
                    "null": null_obs,
                    "delta": {obs: real_obs[obs] - null_obs[obs] for obs in OBSERVABLES_CANONICAL},
                }
                rows_by_class.setdefault(class_key, []).append(row)
                trace.write(json.dumps(row, sort_keys=True) + "\n")

    poisson_contrast = {
        label: summarize(label, rows, rng, args.sign_trials)
        for label, rows in sorted(rows_by_class.items())
    }
    direct_contrasts: dict[str, Any] = {}
    class_labels = sorted(rows_by_class)
    if len(class_labels) >= 2:
        for i, left in enumerate(class_labels):
            for right in class_labels[i + 1 :]:
                direct_contrasts[f"{left}_minus_{right}"] = contrast(
                    f"{left}_minus_{right}",
                    direct_rows_by_class[left],
                    direct_rows_by_class[right],
                    rng,
                    args.sign_trials,
                )

    result = {
        "tester_id": "component_state_SR_L1_triple_var_fit_ready_20260514_1649",
        "interface_mode": "input_spectrum",
        "input_contract": {
            "accepted_payloads": [
                "JSON list of ordered levels",
                "JSON object with levels or spectrum",
                "JSON object with spectra records: label, expected_class, levels",
                "plain text/CSV numeric levels readable by numpy.loadtxt",
            ],
            "required": "ordered spectrum levels; sorting is applied defensively",
            "optional": "expected_class, label",
            "central_fraction": args.central_fraction,
        },
        "output_contract": {
            "component_state": "active iff sign-swap p<=0.01 and |cohen_d_delta|>=0.5",
            "poisson_contrast": "span-matched Poisson null for each class/label",
            "direct_contrast": "pairwise class contrast when at least two classes/labels are present",
            "trace_schema": "event,label,expected_class,null_rep,n_levels,n_gaps,real,null,delta",
        },
        "thresholds": {
            "sign_swap_p_max": 0.01,
            "abs_cohen_d_min": 0.5,
            "min_usable_central_gaps": 12,
        },
        "observables_used": list(OBSERVABLES_CANONICAL.keys()),
        "focus_observables": FOCUS_OBS,
        "seed": args.seed,
        "null_reps": args.null_reps,
        "poisson_contrast": poisson_contrast,
        "direct_contrasts": direct_contrasts,
        "trace_jsonl": str(trace_path),
        "not_promoted_as_physics_law": True,
    }
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def write_fit_ready_artifact(path: Path) -> dict[str, Any]:
    artifact = {
        "tester_id": "component_state_SR_L1_triple_var_fit_ready_20260514_1649",
        "source_cycle": "20260514_1649",
        "input_contract": {
            "interface": "tools/exp_physical_sr_residue_bounce.py --input-spectrum SPECTRUM.json --expected-class CLASS --output OUT.json",
            "spectrum": "ordered level spectrum; script sorts defensively before central-window gap normalization",
            "optional_expected_class": "class label used for grouped Poisson contrast and direct class contrast",
            "payloads": [
                "JSON list of levels",
                "JSON object with levels or spectrum",
                "JSON object with spectra records: label, expected_class, levels",
                "plain text/CSV numeric levels",
            ],
        },
        "output_contract": {
            "component_state": "per observable active/absorbed",
            "poisson_contrast": "real spectrum versus span-matched Poisson null",
            "direct_contrast": "pairwise class contrast when at least two classes are present",
            "trace": "JSONL rows preserving real/null/delta per null replicate",
        },
        "thresholds": {
            "sign_swap_p_max": 0.01,
            "abs_cohen_d_min": 0.5,
            "min_usable_central_gaps": 12,
            "default_null_reps": 64,
            "default_central_fraction": 0.5,
        },
        "component_states": {
            "GOE_time_reversal_symmetric": {
                "expected": {"SR": "active", "L1": "active", "triple_var": "active"},
                "source": "tools/data/physical_sr_residue_bounce_20260514_1640_goe_gue_ncurve.json",
            },
            "GUE_unitary_no_time_reversal": {
                "expected": {"SR": "active", "L1": "active", "triple_var": "active"},
                "source": "tools/data/physical_sr_residue_bounce_20260514_1640_goe_gue_ncurve.json",
            },
            "Anderson_1D_W6": {
                "expected": {"SR": "absorbed", "L1": "absorbed", "triple_var": "active"},
                "source": "tools/data/physical_sr_residue_bounce_20260514_1640_goe_gue_ncurve.json",
            },
        },
        "transfer_blank_fall": {
            "transfer": "SR,L1,triple_var pass from the mathematical deposit into a physical spectrum tester as component states against Poisson and, when classes exist, direct class contrast.",
            "blank": "No graph edge is integrated; no experimental spectra, GSE, Anderson 3D, many-body localization, unfolding-specific contract, or asymptotic claim is added.",
            "fall": "Tester falls if GOE/GUE direct SR separation disappears, if Poisson contrast absorbs all focus observables in chaotic classes, or if Anderson W6 keeps SR active under the declared threshold.",
        },
        "counter_perimeter": {
            "declared": "single ordered spectrum or small class-labeled set; no new physical domain generation",
            "falsifier": [
                "unordered/degenerate spectrum with fewer than 12 usable central gaps",
                "class-labeled input where direct_contrast is not separated on SR despite declared GOE/GUE classes",
                "attempt to promote the artifact as a physics law instead of a tool contract",
            ],
        },
        "trace_ref": {
            "source_result": "tools/data/physical_sr_residue_bounce_20260514_1640_goe_gue_ncurve.json",
            "source_trace": "tools/data/physical_sr_residue_bounce_20260514_1640_goe_gue_ncurve.trace.jsonl",
            "interface_trace_schema": "event,label,expected_class,null_rep,n_levels,n_gaps,real,null,delta",
        },
        "graph_candidate_ref": "tools/data/graph_completion/graph_completion_20260514_1640.json",
        "not_promoted_as_physics_law": True,
        "graph_integration": "not_integrated_operator_decision_required",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact, indent=2, sort_keys=True), encoding="utf-8")
    return artifact


def run(args: argparse.Namespace) -> dict[str, Any]:
    rng = np.random.default_rng(args.seed)
    sizes = args.ns if args.ns else [args.n]
    trace_path = Path(str(args.output).replace(".json", ".trace.jsonl"))
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    rows_by_label: dict[str, list[dict[str, Any]]] = {}
    rows_by_size_label: dict[str, list[dict[str, Any]]] = {}

    with trace_path.open("w", encoding="utf-8") as trace:
        for n in sizes:
            for i in range(args.reps):
                specs: list[tuple[str, str, np.ndarray]] = [
                    ("GOE_time_reversal_symmetric", "beta_1_real_symmetric", goe_levels(n, rng)),
                    ("GUE_unitary_no_time_reversal", "beta_2_complex_hermitian", gue_levels(n, rng)),
                ]
                for disorder in args.disorders:
                    specs.append(
                        (
                            f"Anderson_1D_W{disorder:g}",
                            "disordered_real_tight_binding_finite_size",
                            anderson_levels(n, disorder, rng),
                        )
                    )
                for label, symmetry, levels in specs:
                    gaps = normalize_gaps(levels, args.central_fraction)
                    if len(gaps) < 12:
                        continue
                    null_gaps = span_matched_poisson_gaps(len(gaps) + 1, rng)
                    real_obs = compute_obs(gaps)
                    null_obs = compute_obs(null_gaps)
                    row = {
                        "event": "spectrum_pair",
                        "label": label,
                        "symmetry": symmetry,
                        "rep": i,
                        "n": int(n),
                        "n_gaps": int(len(gaps)),
                        "real": real_obs,
                        "null": null_obs,
                        "delta": {obs: real_obs[obs] - null_obs[obs] for obs in OBSERVABLES_CANONICAL},
                    }
                    size_label = f"N{n}:{label}"
                    rows_by_label.setdefault(label, []).append(row)
                    rows_by_size_label.setdefault(size_label, []).append(row)
                    trace.write(json.dumps(row, sort_keys=True) + "\n")

    summaries = {
        label: summarize(label, rows, rng, args.sign_trials)
        for label, rows in sorted(rows_by_label.items())
    }
    size_summaries = {
        label: summarize(label, rows, rng, args.sign_trials)
        for label, rows in sorted(rows_by_size_label.items())
    }
    symmetry_contrasts = {}
    for n in sizes:
        gue_key = f"N{n}:GUE_unitary_no_time_reversal"
        goe_key = f"N{n}:GOE_time_reversal_symmetric"
        symmetry_contrasts[f"N{n}:GUE_minus_GOE"] = contrast(
            f"N{n}:GUE_minus_GOE",
            rows_by_size_label.get(gue_key, []),
            rows_by_size_label.get(goe_key, []),
            rng,
            args.sign_trials,
        )
    source = summaries["GUE_unitary_no_time_reversal"]
    localized = summaries[f"Anderson_1D_W{args.disorders[-1]:g}"]
    result = {
        "experiment_id": "physical_sr_residue_bounce_20260514_1640",
        "observables_registry": OBSERVABLES_REGISTRY_VERSION,
        "observables_used": list(OBSERVABLES_CANONICAL.keys()),
        "seed": args.seed,
        "sizes": sizes,
        "reps": args.reps,
        "central_fraction": args.central_fraction,
        "null": "span_matched_poisson_same_level_count",
        "physical_source": "quantum-chaotic spectra modeled by GOE and GUE symmetry classes",
        "mathematical_transducer": "span-matched counter-boundary on canonical gap observables",
        "physical_return_candidate": "1D Anderson tight-binding spectra across disorder/localization",
        "component_gate": "active iff sign-swap p<=0.01 and |cohen_d_delta|>=0.5",
        "classical_baselines": {
            "GOE": "Wigner-Dyson beta=1, real symmetric, time-reversal symmetric",
            "GUE": "Wigner-Dyson beta=2, complex Hermitian, no time-reversal symmetry",
            "Poisson": "independent levels, span-matched finite sample null",
            "Anderson_1D_W6": "finite-size disorder/localization boundary, not a universal transition",
        },
        "summaries": summaries,
        "size_summaries": size_summaries,
        "symmetry_contrasts": symmetry_contrasts,
        "bounce_test": {
            "source_SR_state": source["component_state"]["SR"],
            "localized_SR_state": localized["component_state"]["SR"],
            "localized_focus_signature": localized["focus_signature"],
            "rimbalzo_fisico_presente": (
                source["component_state"]["SR"] == "active"
                and localized["component_state"]["SR"] == "absorbed"
            ),
        },
        "trace_jsonl": str(trace_path),
    }
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--input-spectrum", type=Path, default=None)
    parser.add_argument("--expected-class", default=None)
    parser.add_argument("--null-reps", type=int, default=64)
    parser.add_argument("--write-fit-ready", type=Path, default=None)
    parser.add_argument("--seed", type=int, default=202605141612)
    parser.add_argument("--n", type=int, default=192)
    parser.add_argument("--ns", type=int, nargs="+", default=None)
    parser.add_argument("--reps", type=int, default=48)
    parser.add_argument("--central-fraction", type=float, default=0.5)
    parser.add_argument("--disorders", type=float, nargs="+", default=[0.5, 2.0, 6.0, 12.0])
    parser.add_argument("--sign-trials", type=int, default=4096)
    args = parser.parse_args()
    if args.write_fit_ready:
        result = write_fit_ready_artifact(args.write_fit_ready)
        print(json.dumps({"fit_ready_artifact": str(args.write_fit_ready), "tester_id": result["tester_id"]}, indent=2, sort_keys=True))
        return
    if args.input_spectrum:
        result = evaluate_input_spectra(args)
        print(json.dumps({"tester_id": result["tester_id"], "classes": sorted(result["poisson_contrast"])}, indent=2, sort_keys=True))
        return
    result = run(args)
    print(json.dumps(result["bounce_test"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
