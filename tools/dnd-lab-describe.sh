#!/bin/bash
# dnd-lab-describe.sh — primo atto della direttiva self-awareness
# (memoria operatore feedback_lab_self_awareness_2026-05-05.md).
#
# Descrive un lab in modo strutturato: identità, MML, skill attive
# per layer, tools custom, external APIs, cycle history (ultimi 5),
# tensioni attive, validator status.
#
# Uso:
#   bash dnd-lab-describe.sh <lab_slug> [--json]
#   bash dnd-lab-describe.sh finance
#   bash dnd-lab-describe.sh ops-decisions --json

set -euo pipefail

LAB="${1:-}"
FORMAT="markdown"
if [ "${2:-}" = "--json" ]; then
    FORMAT="json"
fi

if [ -z "$LAB" ]; then
    echo "Usage: $0 <lab_slug> [--json]" >&2
    echo "Available labs: $(ls /opt/D-ND_LAB/domains/ | tr '\n' ' ')" >&2
    exit 1
fi

LAB_DIR="/opt/D-ND_LAB/domains/$LAB"
DATA_DIR="/opt/D-ND_LAB/data/$LAB"

if [ ! -d "$LAB_DIR" ]; then
    echo "Lab '$LAB' not found at $LAB_DIR" >&2
    echo "Available: $(ls /opt/D-ND_LAB/domains/ | tr '\n' ' ')" >&2
    exit 1
fi

python3 << EOF
import json, os, glob
from pathlib import Path

LAB = "$LAB"
LAB_DIR = Path("$LAB_DIR")
DATA_DIR = Path("$DATA_DIR")
FORMAT = "$FORMAT"

# Read MML
mml_path = LAB_DIR / "mml.json"
mml = json.loads(mml_path.read_text()) if mml_path.exists() else {}

# Read config
cfg_path = LAB_DIR / "config.json"
cfg = json.loads(cfg_path.read_text()) if cfg_path.exists() else {}

# Read seed_tensions
seedt_path = LAB_DIR / "seed_tensions.json"
seedt = json.loads(seedt_path.read_text()) if seedt_path.exists() else {}

# Read seed.json (runtime state)
seed_path = DATA_DIR / "seed.json"
seed = json.loads(seed_path.read_text()) if seed_path.exists() else {}

# Latest cycle traces (last 5)
trace_files = sorted((DATA_DIR / "" if DATA_DIR.exists() else Path("/tmp")).glob("cycle_trace_*.json"))[-5:] if DATA_DIR.exists() else []
cycles = []
for tf in trace_files:
    try:
        t = json.loads(tf.read_text())
        cyc = {
            "cycle_ts": t.get("cycle_ts"),
            "total_s": t.get("total_s"),
            "n_errors": t.get("n_errors"),
            "n_ok": t.get("n_ok"),
        }
        # Try read aeternitas + veritas from same cycle
        cycle_ts = t.get("cycle_ts", "")
        aet = DATA_DIR / "aeternitas" / f"aeternitas_{cycle_ts}.json"
        if aet.exists():
            try:
                a = json.loads(aet.read_text())
                cyc["aeternitas"] = a.get("decision")
            except Exception:
                pass
        ver = DATA_DIR / "veritas" / f"veritas_{cycle_ts}.json"
        if ver.exists():
            try:
                v = json.loads(ver.read_text())
                cyc["veritas_rho"] = v.get("rho")
                cyc["veritas_band"] = v.get("decision_band")
            except Exception:
                pass
        cycles.append(cyc)
    except Exception:
        pass

# Validator M1-M6 status (read most recent if cached, else run)
validator_status = "not_run"
try:
    import subprocess
    out = subprocess.run(
        ["python3", "/opt/D-ND_LAB/domains/meta-lab/tools/lab_template_validator.py", str(LAB_DIR)],
        capture_output=True, text=True, timeout=30,
    )
    last_lines = out.stdout.strip().splitlines()
    for line in last_lines:
        if "TEMPLATE_VALID" in line or "DOMAIN_NOT_OF_LEVERAGE" in line:
            validator_status = line.strip()
            break
except Exception as e:
    validator_status = f"error: {e}"

# Compose result
result = {
    "lab": LAB,
    "identity": mml.get("identity", {}),
    "title": cfg.get("title"),
    "description": cfg.get("description"),
    "mml": {
        "format": "layered" if isinstance(mml.get("skills_attive"), dict) else ("flat_array" if isinstance(mml.get("skills_attive"), list) else "missing"),
        "kernel_refs": mml.get("kernel_refs", {}),
    },
    "skills_summary": {},
    "tools_custom": [t.get("name") for t in mml.get("tools_custom", []) if isinstance(t, dict)],
    "external_apis": [a.get("name") for a in mml.get("external_apis", []) if isinstance(a, dict)],
    "movements": {
        "total": len(cfg.get("movements", {})),
        "enabled": sum(1 for v in cfg.get("movements", {}).values() if isinstance(v, dict) and v.get("enabled")),
    },
    "tensions_initial": [
        {"id": t.get("id"), "tipo": t.get("tipo"), "intensita": t.get("intensita") or t.get("intensità"), "ref": t.get("condensato_ref")}
        for t in seedt.get("tensioni", []) if isinstance(t, dict)
    ],
    "tensions_current": [
        {"id": t.get("id"), "tipo": t.get("tipo")}
        for t in seed.get("tensioni", []) if isinstance(t, dict)
    ],
    "current_piano": seed.get("piano"),
    "current_direzione": (seed.get("direzione") or "")[:200],
    "cycles_recent": cycles,
    "validator_m6": validator_status,
}

# Skills summary by layer
sa = mml.get("skills_attive")
if isinstance(sa, dict):
    for layer, skills in sa.items():
        if layer.startswith("_") or not isinstance(skills, list):
            continue
        result["skills_summary"][layer] = [s.get("name") for s in skills if isinstance(s, dict)]
elif isinstance(sa, list):
    result["skills_summary"]["flat"] = [s.get("name") for s in sa if isinstance(s, dict)]

if FORMAT == "json":
    print(json.dumps(result, indent=2, ensure_ascii=False))
else:
    # Markdown human-readable
    print(f"# Lab: {result['lab']}")
    print()
    if result.get("title"):
        print(f"**{result['title']}**")
    if result.get("description"):
        print()
        print(result["description"])
    print()
    print(f"## Identità")
    print(f"- type: {result['identity'].get('type', '?')}")
    print(f"- level: {result['identity'].get('level', '?')}")
    if result['identity'].get('responsibility'):
        print(f"- responsibility: {result['identity']['responsibility'][:300]}")
    print()
    print(f"## MML format: {result['mml']['format']}")
    kr = result['mml'].get('kernel_refs', {}) or {}
    if kr:
        print(f"- mmsp_entities: {', '.join(kr.get('mmsp_entities', [])) or '-'}")
        print(f"- condensato_axioms: {', '.join(kr.get('condensato_axioms_used', [])) or '-'}")
    print()
    print(f"## Skills attive (per layer)")
    if result['skills_summary']:
        for layer, names in result['skills_summary'].items():
            print(f"- **{layer}** ({len(names)}): {', '.join(names)}")
    else:
        print("_(no skills_attive)_")
    print()
    print(f"## Tools custom: {', '.join(result['tools_custom']) if result['tools_custom'] else '_(none)_'}")
    print(f"## External APIs: {', '.join(result['external_apis']) if result['external_apis'] else '_(none)_'}")
    print()
    print(f"## Movements: {result['movements']['enabled']}/{result['movements']['total']} enabled")
    print()
    print(f"## Tensioni iniziali (seed_tensions.json)")
    for t in result['tensions_initial']:
        print(f"- {t['id']:35s} [{t['tipo']:18s}] intensità={t['intensita']:.2f} ref={t['ref'] or '-'}")
    if result['current_piano']:
        print()
        print(f"## Stato runtime (seed.json)")
        print(f"- piano: {result['current_piano']}")
        if result['current_direzione']:
            print(f"- direzione: {result['current_direzione']}")
        print(f"- tensioni attive: {len(result['tensions_current'])}")
    print()
    print(f"## Cycle recenti")
    if result['cycles_recent']:
        for c in result['cycles_recent']:
            ae = c.get('aeternitas', '?')
            v = f"ρ={c.get('veritas_rho')}/{c.get('veritas_band')}" if c.get('veritas_rho') is not None else "no veritas"
            print(f"- {c.get('cycle_ts'):20s} {c.get('total_s', 0):.1f}s · {c.get('n_ok', 0)}ok / {c.get('n_errors', 0)}err · aet={ae} · {v}")
    else:
        print("_(no cycles run yet)_")
    print()
    print(f"## Validator M1-M6")
    print(f"  {result['validator_m6']}")
EOF
