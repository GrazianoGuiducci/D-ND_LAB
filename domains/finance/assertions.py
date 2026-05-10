"""Assertions del finance lab.

Le asserzioni sono numeriche, sandboxed e senza rete. Testano invarianti
D-ND proiettate sui regime shift: orientamento det!=0, collasso dopo shuffle,
baseline naive dichiarata, residuo Cassini computabile e tool eseguibile.
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
    path = ROOT / "tools" / "exp_regime_shift.py"
    spec = importlib.util.spec_from_file_location("finance_exp_regime_shift", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load exp_regime_shift.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _synthetic_returns(n: int = 512, seed: int = 17) -> np.ndarray:
    rng = np.random.default_rng(seed)
    first = rng.normal(0.0012, 0.008, n // 2)
    second = rng.normal(-0.0014, 0.018, n - n // 2)
    shock = np.zeros(n)
    shock[n // 2:n // 2 + 8] = np.linspace(-0.015, -0.04, 8)
    return np.concatenate([first, second]) + shock


def _orientation_score(returns: np.ndarray) -> float:
    split = len(returns) // 2
    left = returns[:split]
    right = returns[split:]
    mean_gap = float(np.mean(left) - np.mean(right))
    vol_gap = float(np.std(right, ddof=1) - np.std(left, ddof=1))
    transition_gap = float(np.mean(returns[split:split + min(12, len(right))]) - np.mean(left))
    return mean_gap * vol_gap - transition_gap * abs(mean_gap)


def _cassini_residue(returns: np.ndarray) -> float:
    lags = [1, 2, 3, 5, 8, 13, 21]
    ac = []
    centered = returns - returns.mean()
    denom = float(np.dot(centered, centered))
    for lag in lags:
        ac.append(float(np.dot(centered[:-lag], centered[lag:]) / denom))
    residues = []
    for i in range(1, len(ac) - 1):
        residues.append(abs(ac[i + 1] * ac[i - 1] - ac[i] ** 2))
    return float(np.mean(residues))


def _check_dipole_det_nonzero() -> dict[str, Any]:
    returns = _synthetic_returns()
    ordered = abs(_orientation_score(returns))
    return _result(
        "F_DND_01",
        "PASS" if ordered > 1e-7 else "FAIL",
        f"ordered_orientation_abs={ordered:.9f}",
        ordered,
    )


def _check_shuffle_collapse() -> dict[str, Any]:
    returns = _synthetic_returns()
    ordered = abs(_orientation_score(returns))
    rng = np.random.default_rng(23)
    shuffled = []
    for _ in range(64):
        s = returns.copy()
        rng.shuffle(s)
        shuffled.append(abs(_orientation_score(s)))
    baseline = float(np.mean(shuffled))
    ratio = ordered / baseline if baseline else math.inf
    return _result(
        "F_DND_02",
        "PASS" if ratio > 2.0 else "FAIL",
        f"ordered/shuffle_mean={ratio:.3f}",
        ratio,
    )


def _check_naive_baseline_numeric() -> dict[str, Any]:
    returns = _synthetic_returns()
    var_95 = float(np.quantile(returns, 0.05))
    realized_vol = float(np.std(returns) * math.sqrt(252))
    ok = var_95 < 0 and realized_vol > 0
    return _result(
        "F_DND_03",
        "PASS" if ok else "FAIL",
        f"VaR_95={var_95:.5f}; realized_vol={realized_vol:.4f}",
        {"var_95": var_95, "realized_vol": realized_vol},
    )


def _check_cassini_residue_computable() -> dict[str, Any]:
    residue = _cassini_residue(_synthetic_returns())
    ok = math.isfinite(residue) and residue >= 0
    return _result(
        "F_DND_04",
        "PASS" if ok else "FAIL",
        f"cassini_residue={residue:.9f}",
        residue,
    )


def _check_tool_summary() -> dict[str, Any]:
    """Sanity check: il tool gira e produce summary completo.

    Usa mode='ideal' (engineered bull/bear con hard transition) per
    garantire DND_DELTA stabile come sanity check del pipeline.
    Nel run operativo, l'agent userà mode='realistic' (default CLI).
    """
    module = _load_exp_module()
    summary = module.run_experiment(n=512, seed=17, shuffles=64, mode="ideal")
    required = {"ordered", "shuffle_mean", "effect_z", "var_95", "realized_vol", "verdict"}
    missing = sorted(required - set(summary))
    ok = not missing and summary["verdict"] in {"DND_DELTA", "NO_DELTA"}
    return _result(
        "F_DND_05",
        "PASS" if ok else "FAIL",
        "tool returned required summary (mode=ideal sanity check)" if ok else f"missing={missing}",
        {k: summary.get(k) for k in sorted(required)},
    )


def verifica_asserzioni() -> list[dict[str, Any]]:
    checks = [
        _check_dipole_det_nonzero,
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
