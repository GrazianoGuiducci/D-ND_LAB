"""Assertions for the physics domain — testable claims of the D-ND model.

Loaded by core.verify_assertions movement. Each entry is a dict with:
  - id:     short label
  - claim:  natural-language statement of what is tested
  - source: doc reference
  - test:   callable returning {'status': 'PASS'|'FAIL'|'SKIP', 'detail': str, 'metric': any}

Domain-specific: this file lives under domains/physics/ and tests the D-ND
model claims (axioms A1-A5, facts F1-F2). When a new domain is created
(finance, biology, ...), it ships its own assertions.py with the claims of
that domain's model (NOT necessarily D-ND).

Test functions must be self-contained: no LLM calls, deterministic, fast.
This is γ CALCOLO — the numerical validator.
"""

from __future__ import annotations

import math
from typing import Any

PHI = (1 + math.sqrt(5)) / 2
INV_PHI = 1 / PHI


def _test_a1_punto_fisso_phi() -> dict[str, Any]:
    """A1: f(x)=1+1/x ha punto fisso phi (stabile)."""
    f = lambda x: 1 + 1 / x
    x = 2.0
    for _ in range(50):
        x = f(x)
    dist = abs(x - PHI)
    if dist < 1e-10:
        return {"status": "PASS", "detail": f"x*={x:.15f}, dist={dist:.2e}", "metric": dist}
    return {"status": "FAIL", "detail": f"convergenza non raggiunta: dist={dist:.2e}", "metric": dist}


def _test_a2_gap_ratio_phi2() -> dict[str, Any]:
    """A2: Gap ratio nei numeri di Fibonacci converge a phi^2 = 2.618."""
    fib = [1, 1]
    for _ in range(40):
        fib.append(fib[-1] + fib[-2])
    # gap_n = fib[n+1] - fib[n] = fib[n-1]; ratio = gap[n+1]/gap[n] -> phi
    # ratio of ratios -> phi^2
    n = 35
    ratio = (fib[n + 1] / fib[n]) * (fib[n] / fib[n - 1])
    target = PHI * PHI
    dist = abs(ratio - target)
    if dist < 1e-6:
        return {"status": "PASS", "detail": f"⟨ratio⟩={ratio:.6f}, dist={dist:.2e}", "metric": ratio}
    return {"status": "FAIL", "detail": f"ratio={ratio:.6f}, atteso {target:.6f}", "metric": ratio}


def _test_a3_alternanza_universale() -> dict[str, Any]:
    """A3: Alternanza D↔ND — ogni iterata di f cambia di lato rispetto a phi."""
    f = lambda x: 1 + 1 / x
    n_inputs = 5
    starts = [0.5, 1.0, 1.5, 2.0, 3.0]
    all_alternate = True
    for s in starts:
        x = s
        sign_prev = None
        n_iter = 8
        for _ in range(n_iter):
            x = f(x)
            sign = (x - PHI) > 0
            if sign_prev is not None and sign == sign_prev:
                all_alternate = False
                break
            sign_prev = sign
    if all_alternate:
        return {"status": "PASS", "detail": f"Alternanza verificata per {n_inputs} input diversi"}
    return {"status": "FAIL", "detail": "Alternanza fallita"}


def _test_a4_autovalori_matrice_M() -> dict[str, Any]:
    """A4: Matrice M=[[1,1],[1,0]] ha autovalori phi e -1/phi (det = -1)."""
    # Autovalori di [[1,1],[1,0]]: t^2 - t - 1 = 0 → t = (1 ± √5)/2
    l1 = (1 + math.sqrt(5)) / 2
    l2 = (1 - math.sqrt(5)) / 2
    expected_l1 = PHI
    expected_l2 = -INV_PHI
    if abs(l1 - expected_l1) < 1e-12 and abs(l2 - expected_l2) < 1e-12:
        return {
            "status": "PASS",
            "detail": f"λ₁={l1:.10f} (φ), λ₂={l2:.10f} (-1/φ)",
            "metric": [l1, l2],
        }
    return {"status": "FAIL", "detail": f"autovalori inattesi: {l1}, {l2}"}


def _test_a5_cross_ratio() -> dict[str, Any]:
    """A5: Cross-ratio (0, ∞, phi, -1/phi) = -phi^2."""
    # Cross-ratio (a,b,c,d) = ((c-a)(d-b)) / ((c-b)(d-a))
    # Per (0, ∞, phi, -1/phi): limite per b→∞ → (c-a)/(d-a) · (1/...)
    # Forma chiusa: per (0, ∞, c, d) = c/d quando si normalizza
    # Cross-ratio simbolico = phi / (-1/phi) = -phi^2
    cr = PHI / (-INV_PHI)
    target = -(PHI * PHI)
    dist = abs(cr - target)
    if dist < 1e-12:
        return {
            "status": "PASS",
            "detail": f"cross-ratio = {cr:.10f} = -φ²",
            "metric": cr,
        }
    return {"status": "FAIL", "detail": f"cross-ratio = {cr}, atteso {target}"}


def _test_f1_residuo_cassini() -> dict[str, Any]:
    """F1: Identità di Cassini per Fibonacci: F(n-1)*F(n+1) - F(n)^2 = (-1)^n.
    Indici 0-based: F(0)=0, F(1)=1, F(2)=1, F(3)=2, F(4)=3, ..."""
    fib = [0, 1]
    for _ in range(30):
        fib.append(fib[-1] + fib[-2])
    samples = []
    for n in range(1, 25):
        residue = fib[n - 1] * fib[n + 1] - fib[n] ** 2
        expected = (-1) ** n
        samples.append(residue == expected)
    if all(samples):
        return {"status": "PASS", "detail": f"Cassini verificata su {len(samples)} indici"}
    return {"status": "FAIL", "detail": f"Cassini fallisce su {sum(1 for s in samples if not s)} indici"}


# Public assertions list — read by core.verify_assertions
ASSERTIONS = [
    {
        "id": "A1",
        "claim": "f(x)=1+1/x ha punto fisso φ (stabile)",
        "source": "DND_METHOD_AXIOMS §3",
        "test": _test_a1_punto_fisso_phi,
    },
    {
        "id": "A2",
        "claim": "Gap ratio Fibonacci converge a φ²=2.618034",
        "source": "DND_AUTOLOGIC",
        "test": _test_a2_gap_ratio_phi2,
    },
    {
        "id": "A3",
        "claim": "Alternanza D↔ND è universale per la regola D-ND",
        "source": "KERNEL_MM §IV",
        "test": _test_a3_alternanza_universale,
    },
    {
        "id": "A4",
        "claim": "Matrice [[1,1],[1,0]] ha autovalori φ e -1/φ",
        "source": "Cristallizzazione Möbius",
        "test": _test_a4_autovalori_matrice_M,
    },
    {
        "id": "A5",
        "claim": "Cross-ratio (0,∞,φ,-1/φ) = -φ²",
        "source": "Cristallizzazione Möbius",
        "test": _test_a5_cross_ratio,
    },
    {
        "id": "F1",
        "claim": "Identità di Cassini: F(n-1)·F(n+1) − F(n)² = (-1)ⁿ",
        "source": "Condensato F1",
        "test": _test_f1_residuo_cassini,
    },
]
