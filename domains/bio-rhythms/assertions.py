"""Assertions del bio-rhythms lab.

Le asserzioni sono numeriche, sandboxed e senza rete. Testano invarianti
D-ND proiettate sui regime cardiaci/circadiani: orientamento det!=0,
collasso dopo shuffle, baseline naive HRV (RMSSD/SDNN) dichiarata,
residuo Cassini computabile e tool eseguibile.
"""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parent


def _result(assertion_id: str, status: str, detail: str, metric: Any) -> dict[str, Any]:
    return {"id": assertion_id, "status": status, "detail": detail, "metric": metric}


def _load_exp_module():
    path = ROOT / "tools" / "exp_hrv_regime.py"
    spec = importlib.util.spec_from_file_location("bio_rhythms_exp_hrv", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load exp_hrv_regime.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _synthetic_rr(n: int = 400, seed: int = 17) -> np.ndarray:
    """Synthetic RR-intervals: rest (900±25) → activity (650±70), hard split."""
    rng = np.random.default_rng(seed)
    rest = rng.normal(900.0, 25.0, n // 2)
    active = rng.normal(650.0, 70.0, n - n // 2)
    shock = np.zeros(n)
    shock[n // 2:n // 2 + 8] = np.linspace(-50, -150, 8)
    return np.concatenate([rest, active]) + shock


def _orientation_score(rr: np.ndarray) -> float:
    split = len(rr) // 2
    left = rr[:split]
    right = rr[split:]
    mean_gap = float(np.mean(left) - np.mean(right))
    vol_gap = float(np.std(right, ddof=1) - np.std(left, ddof=1))
    transition_gap = float(np.mean(rr[split:split + min(12, len(right))]) - np.mean(left))
    return mean_gap * vol_gap - transition_gap * abs(mean_gap)


def _cassini_residue(rr: np.ndarray) -> float:
    lags = [1, 2, 3, 5, 8, 13, 21]
    centered = rr - rr.mean()
    denom = float(np.dot(centered, centered))
    ac = [float(np.dot(centered[:-lag], centered[lag:]) / denom) for lag in lags]
    residues = [
        abs(ac[i + 1] * ac[i - 1] - ac[i] ** 2)
        for i in range(1, len(ac) - 1)
    ]
    return float(np.mean(residues))


def _check_hrv_dipole_det_nonzero() -> dict[str, Any]:
    rr = _synthetic_rr()
    ordered = abs(_orientation_score(rr))
    return _result(
        "B_DND_01",
        "PASS" if ordered > 1e-3 else "FAIL",
        f"ordered_orientation_abs={ordered:.6f} (rr in ms)",
        ordered,
    )


def _check_shuffle_collapse() -> dict[str, Any]:
    rr = _synthetic_rr()
    ordered = abs(_orientation_score(rr))
    rng = np.random.default_rng(23)
    shuffled = []
    for _ in range(64):
        s = rr.copy()
        rng.shuffle(s)
        shuffled.append(abs(_orientation_score(s)))
    baseline = float(np.mean(shuffled))
    ratio = ordered / baseline if baseline else math.inf
    return _result(
        "B_DND_02",
        "PASS" if ratio > 2.0 else "FAIL",
        f"ordered/shuffle_mean={ratio:.3f}",
        ratio,
    )


def _check_naive_baseline_numeric() -> dict[str, Any]:
    rr = _synthetic_rr()
    diffs = np.diff(rr)
    rmssd = float(np.sqrt(np.mean(diffs ** 2)))
    sdnn = float(np.std(rr, ddof=1))
    ok = rmssd > 0 and sdnn > 0 and math.isfinite(rmssd) and math.isfinite(sdnn)
    return _result(
        "B_DND_03",
        "PASS" if ok else "FAIL",
        f"RMSSD={rmssd:.2f}ms; SDNN={sdnn:.2f}ms",
        {"rmssd_ms": rmssd, "sdnn_ms": sdnn},
    )


def _check_cassini_residue_computable() -> dict[str, Any]:
    residue = _cassini_residue(_synthetic_rr())
    ok = math.isfinite(residue) and residue >= 0
    return _result(
        "B_DND_04",
        "PASS" if ok else "FAIL",
        f"cassini_residue={residue:.9f}",
        residue,
    )


def _check_tool_summary() -> dict[str, Any]:
    """Sanity check: il tool gira e produce summary completo.

    Usa mode='ideal' (engineered hard-transition) per garantire DND_DELTA
    stabile come sanity check del pipeline. Nel run operativo, l'agent
    userà mode='realistic' (default CLI) o --from-physionet.
    """
    module = _load_exp_module()
    summary = module.run_experiment(n=400, seed=17, shuffles=64, mode="ideal")
    required = {"ordered", "shuffle_mean", "effect_z", "rmssd_ms", "sdnn_ms", "verdict"}
    missing = sorted(required - set(summary))
    ok = not missing and summary["verdict"] in {"DND_DELTA", "NO_DELTA"}
    return _result(
        "B_DND_05",
        "PASS" if ok else "FAIL",
        "tool returned required summary (mode=ideal sanity check)" if ok else f"missing={missing}",
        {k: summary.get(k) for k in sorted(required)},
    )


def verifica_asserzioni() -> list[dict[str, Any]]:
    checks = [
        _check_hrv_dipole_det_nonzero,
        _check_shuffle_collapse,
        _check_naive_baseline_numeric,
        _check_cassini_residue_computable,
        _check_tool_summary,
    ]
    out = []
    for check in checks:
        try:
            out.append(check())
        except Exception as exc:
            out.append(_result(check.__name__, "FAIL", repr(exc), 0))
    return out


if __name__ == "__main__":
    print(json.dumps(verifica_asserzioni(), indent=2, ensure_ascii=False))
