#!/bin/bash
# Deterministic post-cycle closure checks for Bitcoin Regime Lab.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${DND_LAB_ROOT:-$(cd "$SCRIPT_DIR/../../.." && pwd)}"
PYTHON_BIN="${PYTHON_BIN:-$ROOT/.venv/bin/python3}"
if [ ! -x "$PYTHON_BIN" ]; then
    PYTHON_BIN="python3"
fi

cd "$ROOT"

"$PYTHON_BIN" domains/bitcoin-regime-lab/tools/btc_runtime_lineage_audit.py \
    --cycle-ts "${DND_LAB_ACTIVE_CYCLE_TS:-}" \
    --write \
    --json
