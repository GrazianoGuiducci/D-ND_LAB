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
import importlib.util
import json
import os
import re
import subprocess
import sys
from datetime import timedelta
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


def _load_incident_regressor():
    """Load the regressor module so assertions can reuse its scorer."""
    tool_path = os.path.join(
        os.path.dirname(__file__), "tools", "exp_incident_regressor.py"
    )
    spec = importlib.util.spec_from_file_location("ops_incident_regressor", tool_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load exp_incident_regressor.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _commit_window_specificity_metrics(use_guard: bool) -> dict[str, Any]:
    """Compare true-family evidence with a cyclic family-shuffle null."""
    regressor = _load_incident_regressor()
    files = sorted(glob.glob("/opt/MM_D-ND/tools/data/reports/incident_*.md"))
    incident_timestamps = []
    for path in files:
        with open(path, "r") as fh:
            content = fh.read()

        ts_match = re.search(r"\*\*Started\*\*:\s*(\S+)", content)
        incident_timestamps.append(
            regressor.parse_iso_timestamp(ts_match.group(1)) if ts_match else None
        )

    incidents = [
        regressor.parse_incident(path, incident_timestamps=incident_timestamps)
        for path in files
    ]
    families = [inc["recurrence_family"] for inc in incidents]
    if len(set(families)) < 2:
        return {
            "incident_count": len(incidents),
            "true_matches": 0,
            "shuffle_matches": 0,
            "detail": "Need at least 2 families for shuffle null",
        }

    true_matches = 0
    shuffle_matches = 0
    true_best_scores = []
    shuffle_best_scores = []
    for idx, inc in enumerate(incidents):
        timestamp = regressor.parse_iso_timestamp(inc.get("timestamp"))
        if timestamp is None:
            continue
        until = (
            regressor.causal_commit_window_until(timestamp, incident_timestamps)
            if use_guard
            else timestamp + timedelta(hours=regressor.DEFAULT_COMMIT_WINDOW_HOURS)
        )
        commits = regressor.git_commits_after(
            timestamp,
            hours=regressor.DEFAULT_COMMIT_WINDOW_HOURS,
            until=until,
        )

        true_scores = [
            regressor.score_commit_for_family(commit, inc["recurrence_family"])[0]
            for commit in commits
        ]
        shuffled_family = families[(idx + 1) % len(families)]
        shuffle_scores = [
            regressor.score_commit_for_family(commit, shuffled_family)[0]
            for commit in commits
        ]
        true_best = max(true_scores, default=0)
        shuffle_best = max(shuffle_scores, default=0)
        true_best_scores.append(true_best)
        shuffle_best_scores.append(shuffle_best)
        if true_best >= regressor.MIN_COMMIT_EVIDENCE_SCORE:
            true_matches += 1
        if shuffle_best >= regressor.MIN_COMMIT_EVIDENCE_SCORE:
            shuffle_matches += 1

    return {
        "incident_count": len(incidents),
        "true_matches": true_matches,
        "shuffle_matches": shuffle_matches,
        "true_best_scores": true_best_scores,
        "shuffle_best_scores": shuffle_best_scores,
        "window": "guard" if use_guard else "legacy_12h",
    }


def _test_commit_window_specificity() -> dict[str, Any]:
    """Null guard: commit evidence must survive true family and fail shuffle."""
    try:
        guard = _commit_window_specificity_metrics(use_guard=True)
        legacy = _commit_window_specificity_metrics(use_guard=False)
        n = guard["incident_count"]
        guard_specific = (
            n >= 2
            and guard["true_matches"] == n
            and guard["shuffle_matches"] == 0
        )
        legacy_would_fail = legacy["shuffle_matches"] >= guard["true_matches"]

        metric = {"guard": guard, "legacy_12h_control": legacy}
        if guard_specific and legacy_would_fail:
            return {
                "status": "PASS",
                "detail": (
                    f"guard true={guard['true_matches']}/{n}, "
                    f"shuffle={guard['shuffle_matches']}/{n}; "
                    f"legacy shuffle={legacy['shuffle_matches']}/{n}"
                ),
                "metric": metric,
            }
        return {
            "status": "FAIL",
            "detail": (
                f"Specificity not discriminating: guard true={guard['true_matches']}/{n}, "
                f"guard shuffle={guard['shuffle_matches']}/{n}, "
                f"legacy shuffle={legacy['shuffle_matches']}/{n}"
            ),
            "metric": metric,
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
    {
        "id": "OD_COMMIT_WINDOW_SPECIFICITY",
        "claim": "Commit evidence keeps true-family matches under max_4h_or_next_incident and rejects family-shuffle null; legacy 12h is the negative control",
        "source": "seed COMMIT_WINDOW_GUARD_ASSERTION_GAP",
        "test": _test_commit_window_specificity,
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
