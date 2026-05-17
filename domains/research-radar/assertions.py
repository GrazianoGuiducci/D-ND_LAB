"""Assertions for Research Radar Lab."""
from __future__ import annotations

import json
from pathlib import Path


def _domain_dir() -> Path:
    return Path(__file__).resolve().parent


def _load_seed() -> dict:
    return json.loads((_domain_dir() / "seed_tensions.json").read_text(encoding="utf-8"))


def _check_claims_have_refs() -> dict:
    seed = _load_seed()
    tensions = seed.get("tensioni", [])
    with_refs = [t for t in tensions if t.get("condensato_ref")]
    status = "PASS" if len(with_refs) >= 3 else "FAIL"
    return {
        "id": "RR1",
        "status": status,
        "detail": f"{len(with_refs)}/{len(tensions)} tensions carry D-ND refs",
        "metric": len(with_refs),
    }


def _check_context_declares_baseline() -> dict:
    text = (_domain_dir() / "context.md").read_text(encoding="utf-8").lower()
    signals = ["baseline", "null", "naive", "control"]
    hits = sum(1 for s in signals if s in text)
    return {
        "id": "RR2",
        "status": "PASS" if hits >= 3 else "FAIL",
        "detail": f"baseline/null signals={hits}/4",
        "metric": hits,
    }


def _check_tool_exists() -> dict:
    path = _domain_dir() / "tools" / "exp_claim_radar.py"
    return {
        "id": "RR3",
        "status": "PASS" if path.exists() else "FAIL",
        "detail": "exp_claim_radar.py present" if path.exists() else "missing exp_claim_radar.py",
        "metric": int(path.exists()),
    }


def _check_onboarding_contract() -> dict:
    path = _domain_dir() / "onboarding_contract.json"
    if not path.exists():
        return {"id": "RR4", "status": "FAIL", "detail": "onboarding_contract.json missing", "metric": 0}
    data = json.loads(path.read_text(encoding="utf-8"))
    channels = data.get("channels", {})
    required = {"domain_request", "operator_corpus", "public_contribution", "dataset_api", "runtime_self_observation"}
    hits = len(required.intersection(channels))
    return {
        "id": "RR4",
        "status": "PASS" if hits == len(required) else "FAIL",
        "detail": f"{hits}/{len(required)} required channels declared",
        "metric": hits,
    }


def verifica_asserzioni() -> list[dict]:
    return [
        _check_claims_have_refs(),
        _check_context_declares_baseline(),
        _check_tool_exists(),
        _check_onboarding_contract(),
    ]


ASSERTIONS = [
    {"id": "RR1", "test": _check_claims_have_refs},
    {"id": "RR2", "test": _check_context_declares_baseline},
    {"id": "RR3", "test": _check_tool_exists},
    {"id": "RR4", "test": _check_onboarding_contract},
]
