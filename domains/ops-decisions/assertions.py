"""Assertions for the ops-decisions domain — testable invariants.

Loaded by core.verify_assertions movement. Each entry is a dict with:
  - id:     short label
  - claim:  natural-language statement of what is tested
  - source: doc reference
  - test:   callable returning {'status': 'PASS'|'FAIL'|'SKIP', 'detail': str, 'metric': any}

Domain-specific: tests that the ops-decisions corpus is real, the tools
produce structured output, and the dipolar classification is non-trivial.
"""

from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
from typing import Any


def _test_corpus_exists() -> dict[str, Any]:
    """Corpus check: incident reports and operator memories exist."""
    incident_files = glob.glob("/opt/MM_D-ND/tools/data/reports/incident_*.md")
    memory_files = glob.glob("/root/.claude/projects/-opt/memory/feedback_*.md")
    cowork = "/opt/THIA/docs/memory/COWORK_CHANNEL.md"

    n_incidents = len(incident_files)
    n_memories = len(memory_files)
    cowork_exists = os.path.isfile(cowork)

    if n_incidents >= 1 and n_memories >= 10 and cowork_exists:
        return {
            "status": "PASS",
            "detail": f"incidents={n_incidents}, memories={n_memories}, cowork={cowork_exists}",
            "metric": {"incidents": n_incidents, "memories": n_memories},
        }
    return {
        "status": "FAIL",
        "detail": f"Insufficient corpus: incidents={n_incidents}, memories={n_memories}, cowork={cowork_exists}",
        "metric": {"incidents": n_incidents, "memories": n_memories},
    }


def _test_incident_regressor_runs() -> dict[str, Any]:
    """M3: exp_incident_regressor.py runs and produces valid JSON."""
    tool_path = os.path.join(
        os.path.dirname(__file__), "tools", "exp_incident_regressor.py"
    )
    if not os.path.isfile(tool_path):
        return {"status": "SKIP", "detail": "Tool not found", "metric": None}

    try:
        result = subprocess.run(
            [sys.executable, tool_path, "--json"],
            capture_output=True,
            text=True,
            timeout=90,
        )
        if result.returncode != 0:
            return {
                "status": "FAIL",
                "detail": f"Exit {result.returncode}: {result.stderr[:200]}",
                "metric": None,
            }
        data = json.loads(result.stdout)
        if "total_incidents" in data and "family_analysis" in data:
            return {
                "status": "PASS",
                "detail": f"Parsed {data['total_incidents']} incidents",
                "metric": data["total_incidents"],
            }
        return {"status": "FAIL", "detail": "Missing expected keys", "metric": None}
    except Exception as e:
        return {"status": "FAIL", "detail": str(e)[:200], "metric": None}


def _test_decision_archaeologist_runs() -> dict[str, Any]:
    """M3: exp_decision_archaeologist.py runs and produces valid JSON."""
    tool_path = os.path.join(
        os.path.dirname(__file__), "tools", "exp_decision_archaeologist.py"
    )
    if not os.path.isfile(tool_path):
        return {"status": "SKIP", "detail": "Tool not found", "metric": None}

    try:
        result = subprocess.run(
            [sys.executable, tool_path, "--json"],
            capture_output=True,
            text=True,
            timeout=90,
        )
        if result.returncode != 0:
            return {
                "status": "FAIL",
                "detail": f"Exit {result.returncode}: {result.stderr[:200]}",
                "metric": None,
            }
        data = json.loads(result.stdout)
        if "corpus_size" in data and "clusters" in data:
            return {
                "status": "PASS",
                "detail": f"Analyzed {data['corpus_size']} files, {data['clusters']['total_with_axiom_ref']} with axiom refs",
                "metric": {
                    "corpus_size": data["corpus_size"],
                    "axiom_refs": data["clusters"]["total_with_axiom_ref"],
                },
            }
        return {"status": "FAIL", "detail": "Missing expected keys", "metric": None}
    except Exception as e:
        return {"status": "FAIL", "detail": str(e)[:200], "metric": None}


def _test_dipolar_non_trivial() -> dict[str, Any]:
    """M1: Regressive node classification is non-trivial."""
    tool_path = os.path.join(
        os.path.dirname(__file__), "tools", "exp_incident_regressor.py"
    )
    if not os.path.isfile(tool_path):
        return {"status": "SKIP", "detail": "Tool not found", "metric": None}

    try:
        result = subprocess.run(
            [sys.executable, tool_path, "--json"],
            capture_output=True,
            text=True,
            timeout=90,
        )
        data = json.loads(result.stdout)
        classifications = set()
        for inc in data.get("incidents", []):
            classifications.add(inc["node_class"])

        incident_count = data.get("total_incidents", 0)
        confidence = "exploratory" if incident_count < 5 else "sample-aware"

        if len(classifications) >= 2:
            return {
                "status": "PASS",
                "detail": (
                    f"Found {len(classifications)} distinct node classes: "
                    f"{classifications} (N={incident_count}, confidence={confidence})"
                ),
                "metric": {
                    "distinct_node_classes": len(classifications),
                    "incident_count": incident_count,
                    "confidence": confidence,
                },
            }
        elif len(classifications) == 1:
            return {
                "status": "FAIL",
                "detail": (
                    f"All incidents classified as node {classifications} "
                    f"(N={incident_count}, confidence={confidence}) — no dipole"
                ),
                "metric": {
                    "distinct_node_classes": 1,
                    "incident_count": incident_count,
                    "confidence": confidence,
                },
            }
        return {"status": "SKIP", "detail": "No incidents to classify", "metric": 0}
    except Exception as e:
        return {"status": "FAIL", "detail": str(e)[:200], "metric": None}


def _test_axiom_coverage() -> dict[str, Any]:
    """Axiom projection: at least 3 distinct axioms referenced in corpus patterns."""
    tool_path = os.path.join(
        os.path.dirname(__file__), "tools", "exp_decision_archaeologist.py"
    )
    if not os.path.isfile(tool_path):
        return {"status": "SKIP", "detail": "Tool not found", "metric": None}

    try:
        result = subprocess.run(
            [sys.executable, tool_path, "--json"],
            capture_output=True,
            text=True,
            timeout=90,
        )
        data = json.loads(result.stdout)
        axiom_freq = data.get("clusters", {}).get("axiom_frequency", {})
        n_axioms = len(axiom_freq)

        if n_axioms >= 3:
            return {
                "status": "PASS",
                "detail": f"{n_axioms} axioms referenced: {list(axiom_freq.keys())}",
                "metric": n_axioms,
            }
        return {
            "status": "FAIL",
            "detail": f"Only {n_axioms} axioms found — insufficient projection",
            "metric": n_axioms,
        }
    except Exception as e:
        return {"status": "FAIL", "detail": str(e)[:200], "metric": None}


def _test_candidate_rules_emerge() -> dict[str, Any]:
    """M5 auto-increment: at least 1 candidate rule with frequency >= 3."""
    tool_path = os.path.join(
        os.path.dirname(__file__), "tools", "exp_decision_archaeologist.py"
    )
    if not os.path.isfile(tool_path):
        return {"status": "SKIP", "detail": "Tool not found", "metric": None}

    try:
        result = subprocess.run(
            [sys.executable, tool_path, "--json", "--min-frequency", "3"],
            capture_output=True,
            text=True,
            timeout=90,
        )
        data = json.loads(result.stdout)
        candidates = data.get("candidate_rules", [])

        if len(candidates) >= 1:
            top = candidates[0]
            return {
                "status": "PASS",
                "detail": f"{len(candidates)} candidate rules. Top: {top['axiom_cluster']} ({top['frequency']}x)",
                "metric": len(candidates),
            }
        return {
            "status": "FAIL",
            "detail": "No candidate rules emerged — loop sterile",
            "metric": 0,
        }
    except Exception as e:
        return {"status": "FAIL", "detail": str(e)[:200], "metric": None}


# --- Public API ---

ASSERTIONS = [
    {
        "id": "OD_CORPUS",
        "claim": "Corpus exists: incident reports >= 1, operator memories >= 10, COWORK channel present",
        "source": "context.md §Corpus disponibile",
        "test": _test_corpus_exists,
    },
    {
        "id": "OD_REGRESSOR_M3",
        "claim": "exp_incident_regressor.py runs sandboxed and produces valid JSON (M3)",
        "source": "meta-lab M3",
        "test": _test_incident_regressor_runs,
    },
    {
        "id": "OD_ARCHAEOLOGIST_M3",
        "claim": "exp_decision_archaeologist.py runs sandboxed and produces valid JSON (M3)",
        "source": "meta-lab M3",
        "test": _test_decision_archaeologist_runs,
    },
    {
        "id": "OD_DIPOLAR_M1",
        "claim": "Incident node_class produces >= 2 distinct regressive nodes (M1 dipole non-trivial)",
        "source": "meta-lab M1 + seed INCIDENT_CLASSIFICATION_EXECUTABLE_CONTRACT",
        "test": _test_dipolar_non_trivial,
    },
    {
        "id": "OD_AXIOM_COVERAGE",
        "claim": "Corpus patterns reference >= 3 distinct axioms (axiom projection real)",
        "source": "context.md §Assiomi proiettati",
        "test": _test_axiom_coverage,
    },
    {
        "id": "OD_CANDIDATE_RULES_M5",
        "claim": "At least 1 candidate rule emerges with frequency >= 3 (M5 auto-increment)",
        "source": "meta-lab M5",
        "test": _test_candidate_rules_emerge,
    },
]


def verifica_asserzioni() -> list[dict]:
    """Run all assertions and return structured results."""
    results = []
    for a in ASSERTIONS:
        try:
            outcome = a["test"]()
        except Exception as e:
            outcome = {"status": "FAIL", "detail": f"Exception: {e}", "metric": None}
        results.append(
            {
                "id": a["id"],
                "claim": a["claim"],
                "source": a["source"],
                **outcome,
            }
        )
    return results


if __name__ == "__main__":
    results = verifica_asserzioni()
    for r in results:
        print(f"[{r['status']}] {r['id']}: {r.get('detail', '')}")
