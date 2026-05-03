#!/usr/bin/env python3
"""blueprint_generator — genera blueprint markdown da manifest candidato.

Pattern (operatore 03/05 sera): "rendere disponibili con un click magari
in modale" + "report o blueprint che lo realizzi (in uno step successivo)".

Input: cycle_ts + candidate type (library/kernel/demo) di una soluzione
già promossa in published/<ts>_<slug>/manifest.json.

Output: markdown self-contained con tutti gli elementi necessari per un
implementatore umano per realizzare il prodotto manualmente:
  - Header: titolo, cycle, finding sorgente, status
  - Scope: what_it_does + verification spec
  - Implementation skeleton: required inputs, expected outputs
  - Acceptance criteria: success + falsification
  - Test plan template
  - Risk register
  - References: lab-note + cycle-report links

CLI:
  python -m core.triggers.blueprint_generator <cycle_ts> <type> [--domain physics]
                                                                [--out FILE]

Stdout = markdown se --out non specificato.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def _resolve_paths(domain: str | None = None) -> dict[str, Path]:
    lab_data = os.environ.get("LAB_DATA_DIR")
    if lab_data:
        dom = domain or os.environ.get("DOMAIN", "physics")
        base = Path(lab_data) / dom
    else:
        base = Path("/opt/MM_D-ND/applications")
    return {
        "published": base / "published",
        "domain": dom if lab_data else None,
    }


def find_published_dir(cycle_ts: str, published_base: Path) -> Path | None:
    matches = sorted(published_base.glob(f"{cycle_ts}_*"))
    return matches[0] if matches else None


def render_blueprint(manifest: dict, candidate: dict, source_meta: dict) -> str:
    """Render markdown blueprint for a single candidate."""
    name = candidate.get("name", "?")
    type_ = candidate.get("type", "?")
    finding_idx = candidate.get("discovery_finding_idx", "?")
    finding_title = candidate.get("discovery_finding_title", "")
    what = candidate.get("what_it_does", "")
    spec = candidate.get("verification_spec", {}) or {}
    verifier = spec.get("verifier_form", "?")
    status = spec.get("status", "SPEC_ONLY")

    inputs = spec.get("required_inputs") or []
    success = spec.get("success_criteria") or []
    falsification = spec.get("falsification_criteria") or []
    artifacts = spec.get("expected_artifacts") or []
    risks = spec.get("risks") or []

    cycle_ts = source_meta.get("cycle_ts", "?")
    lab_instance = source_meta.get("lab_instance", "?")
    seed_version = source_meta.get("seme_version", "?")
    falsifier_verdict = source_meta.get("falsifier_verdict", "?")
    valutatore = source_meta.get("valutatore_decision", "?")

    discovery_summary = manifest.get("discovery_summary", {}) or {}
    verdict_excerpt = discovery_summary.get("verdict_excerpt", "")[:600]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    def bullets(items: list, fallback: str = "_(none)_") -> str:
        if not items:
            return fallback
        return "\n".join(f"- {item}" for item in items)

    return f"""# Blueprint — {name}

> **Type**: `{type_}` · **Verifier**: `{verifier}` · **Status**: `{status}`
> **Generated**: {now}

## Origin

| Field | Value |
|-------|-------|
| Cycle | `{cycle_ts}` |
| Lab instance | `{lab_instance}` |
| Seed version | `{seed_version}` |
| Source finding | #{finding_idx} — {finding_title} |
| Falsifier verdict | `{falsifier_verdict}` |
| Trajectory evaluator | `{valutatore}` |

## Scope

{what or "_(empty — manifest needs refinement)_"}

### Discovery context

> {verdict_excerpt or "_(no discovery summary available)_"}

## Implementation skeleton

### Required inputs

{bullets(inputs)}

### Expected artifacts

{bullets(artifacts)}

## Acceptance criteria

### Success

{bullets(success)}

### Falsification

{bullets(falsification)}

## Test plan template

```python
# tests/test_baseline.py — verifica naive baseline produce output corretto
# tests/test_correctness.py — verifica candidate replica baseline su input set
# tests/test_performance.py — confronto wall-clock + significance test
# Esempio per benchmark verifier:

def test_correctness_subset():
    # Genera input set (es. primes_to_N) per N piccolo (smoke test)
    inputs = generate_test_set(N=1000)
    baseline = run_baseline(inputs)
    candidate = run_candidate(inputs)
    assert all(a == b for a, b in zip(baseline, candidate)), \\
        "candidate output diverges from baseline"

def test_performance_significance():
    inputs = generate_test_set(N=100_000)
    times_b = [time_baseline(inputs) for _ in range(30)]
    times_c = [time_candidate(inputs) for _ in range(30)]
    assert median(times_c) < median(times_b), "no speedup"
    p = wilcoxon(times_b, times_c).pvalue
    assert p < 0.05, f"speedup not significant (p={{p:.4f}})"
```

## Risk register

{bullets(risks)}

## References

- Manifest: `data/{lab_instance}/published/{find_published_dir.__doc__ and "<dir>"}/manifest.json`
- Lab note: `data/{lab_instance}/published/<dir>/lab-note.md`
- Cycle report: `data/{lab_instance}/published/<dir>/cycle-report.md`
- Source agent report: `data/{lab_instance}/reports/agent_{cycle_ts}.md`
- Falsifier audit: `data/{lab_instance}/reports/falsifier_{cycle_ts}.json`

---

*Auto-generated by `blueprint_generator.py` · D-ND_LAB SSP pipeline.
Refinement editorial pending. Use as scaffold, not as final spec.*
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cycle_ts")
    ap.add_argument("type", choices=["library", "kernel", "demo"])
    ap.add_argument("--domain", default=None)
    ap.add_argument("--out", default=None,
                    help="output file (default: stdout)")
    args = ap.parse_args()

    paths = _resolve_paths(args.domain)
    pub_base = paths["published"]
    pub_dir = find_published_dir(args.cycle_ts, pub_base)
    if not pub_dir:
        print(f"ERROR: no published dir per cycle {args.cycle_ts}", file=sys.stderr)
        return 2

    manifest_path = pub_dir / "manifest.json"
    if not manifest_path.exists():
        print(f"ERROR: {manifest_path} non esiste — promote_to_publish prima", file=sys.stderr)
        return 2

    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    candidates = manifest.get("applications_candidate", [])
    target = next((c for c in candidates if c.get("type") == args.type), None)
    if not target:
        print(f"ERROR: nessun candidate type={args.type} in manifest", file=sys.stderr)
        return 2

    source_meta = manifest.get("discovery_provenance", {}) or {}

    md = render_blueprint(manifest, target, source_meta)

    if args.out:
        Path(args.out).write_text(md, encoding='utf-8')
        print(f"WROTE {args.out} ({len(md)} chars)")
    else:
        sys.stdout.write(md)

    return 0


if __name__ == "__main__":
    sys.exit(main())
