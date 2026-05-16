"""observables_registry.py — Source of Truth per gli observables del lab D-ND.

Cristallizzato 2026-05-06 dalla **consecutio del cycle agent_20260506_0625**:

> "What opens now: the lab needs an observable registry. Labels like SR
>  cannot travel between reports unless they bind to a function definition.
>  Without that, META flags are not philosophical: the same label can
>  silently change the object under test."

## Il problema che ha creato il registry

Il cycle 06:25 ha auto-falsificato il finding del cycle 03:30 ("secondo asse
GUE") e nel farlo ha trovato **collision di nomi observable** tra script:

- `SR` in `exp_selective_layer_decoupling.py` = `spacing_ratio` (mean min/max
  ratio of consecutive gaps) — convention dominante (~6 script)
- `SR` in `exp_scale_selective_perturbation.py` = `spectral_rigidity(gaps)`
  (Δ₃(L) rigidity) — variante usata SOLO in 1 script

- `triple_var` in 3 script = `np.var(triple_sums)` (raw) — convention dominante
- `triple_var` in `exp_perturbation_dimensionality_audit.py` =
  `np.var(triples) / np.var(gaps)` (normalizzato) — variante in 1 script

Il lab autonomo che compara report tra script con osservabili "stesso nome,
funzione diversa" stava confrontando mele con arance.

## La soluzione (minimal, non invasiva)

Questo registry stabilisce il **nome canonico**: ciò che la maggioranza degli
script chiama già `SR`/`triple_var`/etc. Le varianti restano disponibili ma
con nomi ESPLICITI (`SR_local_rigidity`, `triple_var_normalized`) per evitare
mascheramento semantico.

## Come usarlo

```python
from observables_registry import OBSERVABLES_CANONICAL, OBSERVABLES_REGISTRY_VERSION

# Compute canonical observable suite for a sequence of gaps
results = {name: fn(gaps) for name, fn in OBSERVABLES_CANONICAL.items()}

# Or import individual canonical observable
from observables_registry import SR, triple_var, L1, L2, SR2

# For variants, import explicitly with disambiguating name
from observables_registry import SR_local_rigidity, triple_var_normalized
```

## Convention per i report

Ogni report agent (cycle) che usa observables DEVE includere nel suo header:

```
observables_registry: 1.0.0-2026-05-06
observables_used: [SR, SR2, L1, L2, triple_var]
```

Cycle che mescola canonical + variant DEVE indicare entrambi:

```
observables_used: [SR, SR_local_rigidity, ...]
```

Senza questo, i confronti cross-cycle sono inattendibili.

## Versioning

Cambiare una definizione canonica = bump del registry version e nota nel
changelog. Le definizioni canoniche sono **immutabili dentro una versione**.
"""
from __future__ import annotations

import numpy as np


OBSERVABLES_REGISTRY_VERSION = "1.0.0-2026-05-06"


# ─── Canonical observables (convention dominante nel codebase 2026-05-06) ───

def SR(gaps: np.ndarray) -> float:
    """**SR — Spacing Ratio** (canonical).

    Mean of `min(g_i, g_{i+1}) / max(g_i, g_{i+1})` over consecutive gaps.
    Range: (0, 1]. GUE → ~0.60. Poisson → ~0.39. Picket-fence → 1.

    NOTE: questa è la convention dominante in 6+ script del lab.
    Per la variante "local spectral rigidity Δ₃(L)" usare `SR_local_rigidity`.
    """
    if len(gaps) < 2:
        return 0.0
    s, s1 = gaps[:-1], gaps[1:]
    r = np.minimum(s, s1) / np.maximum(s, s1)
    r = r[np.isfinite(r) & (r > 0)]
    return float(np.mean(r)) if len(r) else 0.0


def SR2(gaps: np.ndarray) -> float:
    """**SR2 — Next-nearest Spacing Ratio** (canonical).

    Mean of `min(g_i, g_{i+2}) / max(g_i, g_{i+2})` skipping one gap.
    Probes lag-2 spacing structure.
    """
    if len(gaps) < 3:
        return 0.0
    s, s2 = gaps[:-2], gaps[2:]
    r = np.minimum(s, s2) / np.maximum(s, s2)
    r = r[np.isfinite(r) & (r > 0)]
    return float(np.mean(r)) if len(r) else 0.0


def L1(gaps: np.ndarray) -> float:
    """**L1 — Lag-1 Autocorrelation** (canonical).

    Standard ACF at lag 1 of the gap sequence.
    """
    if len(gaps) < 3:
        return 0.0
    g = gaps - np.mean(gaps)
    c0 = float(np.mean(g ** 2))
    if c0 <= 1e-15:
        return 0.0
    return float(np.mean(g[:-1] * g[1:]) / c0)


def L2(gaps: np.ndarray) -> float:
    """**L2 — Lag-2 Autocorrelation** (canonical)."""
    if len(gaps) < 4:
        return 0.0
    g = gaps - np.mean(gaps)
    c0 = float(np.mean(g ** 2))
    if c0 <= 1e-15:
        return 0.0
    return float(np.mean(g[:-2] * g[2:]) / c0)


def triple_var(gaps: np.ndarray) -> float:
    """**triple_var — Variance of consecutive gap triples** (canonical).

    Variance of `g_i + g_{i+1} + g_{i+2}` over the sequence (RAW, no
    normalization). Convention used in 3+ scripts. For the normalized
    version (variance ratio `var(triples) / var(gaps)`) use
    `triple_var_normalized`.
    """
    if len(gaps) < 3:
        return 0.0
    t = gaps[:-2] + gaps[1:-1] + gaps[2:]
    return float(np.var(t))


# Set canonico per uso "compute all" da report
OBSERVABLES_CANONICAL: dict[str, callable] = {
    "SR": SR,
    "SR2": SR2,
    "L1": L1,
    "L2": L2,
    "triple_var": triple_var,
}


# ─── Variants (esplicitamente nominate, no collision con canonical) ───

def SR_local_rigidity(gaps: np.ndarray, L: int = 10) -> float:
    """**SR_local_rigidity — Δ₃(L) Spectral Rigidity** (variant).

    Different observable than canonical `SR` (spacing ratio). Measures the
    average squared deviation of the cumulative spacing function from the
    best-fit straight line in a window of size L.

    Originated from `exp_scale_selective_perturbation.py` where it was
    locally named `SR` — registered here as `SR_local_rigidity` to avoid
    collision with canonical spacing-ratio definition.

    Use when explicitly studying spectral rigidity, NOT as alias for SR.
    """
    if len(gaps) < 5:
        return 0.0
    cumulative = np.cumsum(gaps)
    if cumulative[-1] <= 1e-15:
        return 0.0
    cumulative = cumulative / cumulative[-1] * len(cumulative)
    n = np.arange(1, len(cumulative) + 1, dtype=float)
    window = int(min(L * len(gaps) / cumulative[-1], len(gaps) // 2))
    if window < 5:
        return 0.0
    residuals = []
    for start in range(0, len(cumulative) - window, max(1, window // 2)):
        end = start + window
        x = n[start:end]
        y = cumulative[start:end]
        a, b = np.polyfit(x, y, 1)
        residuals.append(np.mean((y - (a * x + b)) ** 2))
    return float(np.mean(residuals)) if residuals else 0.0


def triple_var_normalized(gaps: np.ndarray) -> float:
    """**triple_var_normalized — Variance of triples / variance of gaps** (variant).

    Originated from `exp_perturbation_dimensionality_audit.py` where it was
    locally named `triple_var` — registered here as `triple_var_normalized`
    to avoid collision with canonical raw triple variance.

    Use when explicitly studying triple-variance scaling relative to
    single-gap variance, NOT as alias for triple_var.
    """
    if len(gaps) < 3:
        return 0.0
    triples = gaps[:-2] + gaps[1:-1] + gaps[2:]
    v = float(np.var(gaps))
    if v <= 1e-15:
        return 0.0
    return float(np.var(triples) / v)


# Set varianti, importabile esplicitamente
OBSERVABLES_VARIANTS: dict[str, callable] = {
    "SR_local_rigidity": SR_local_rigidity,
    "triple_var_normalized": triple_var_normalized,
}


# ─── Public API ───────────────────────────────────────────────────────

def compute_canonical(gaps: np.ndarray) -> dict[str, float]:
    """Compute all canonical observables for a gap sequence.

    Returns dict {name: value} ready for inclusion in cycle reports.
    """
    return {name: fn(gaps) for name, fn in OBSERVABLES_CANONICAL.items()}


def report_header() -> str:
    """Suggested markdown header line for cycle reports using this registry."""
    canonical_list = ", ".join(OBSERVABLES_CANONICAL.keys())
    return (
        f"observables_registry: {OBSERVABLES_REGISTRY_VERSION}\n"
        f"observables_used: [{canonical_list}]"
    )


__all__ = [
    "OBSERVABLES_REGISTRY_VERSION",
    "OBSERVABLES_CANONICAL",
    "OBSERVABLES_VARIANTS",
    "SR",
    "SR2",
    "L1",
    "L2",
    "triple_var",
    "SR_local_rigidity",
    "triple_var_normalized",
    "compute_canonical",
    "report_header",
]


if __name__ == "__main__":
    # Smoke test: canonical observables on a simple gap series
    rng = np.random.default_rng(42)
    gue_like = rng.gamma(shape=2.0, scale=0.5, size=200)
    res = compute_canonical(gue_like)
    print(f"Registry version: {OBSERVABLES_REGISTRY_VERSION}")
    print(f"\nGUE-like 200 gaps:")
    for name, val in res.items():
        print(f"  {name:12s} = {val:.6f}")
    print(f"\nVariants (explicit naming, not aliases):")
    print(f"  SR_local_rigidity     = {SR_local_rigidity(gue_like):.6f}")
    print(f"  triple_var_normalized = {triple_var_normalized(gue_like):.6f}")
