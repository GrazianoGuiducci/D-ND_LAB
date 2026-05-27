#!/bin/bash
# Deterministic value refresh for Finance Lab cycles.
#
# This hook refreshes the autonomy/readiness surface before the cognitive
# cycle. It does not fetch new market families, relaunch exhausted scouts, place
# orders, or open paper/live-sim. The autonomous next step remains encoded in
# finance_autonomy_opportunity_scout_latest.json.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${DND_LAB_ROOT:-$(cd "$SCRIPT_DIR/../../.." && pwd)}"
PYTHON_BIN="${PYTHON_BIN:-$ROOT/.venv/bin/python3}"
if [ ! -x "$PYTHON_BIN" ]; then
    PYTHON_BIN="python3"
fi

cd "$ROOT"

"$PYTHON_BIN" domains/finance/tools/finance_operational_health.py --write
"$PYTHON_BIN" domains/finance/tools/finance_autonomous_trading_contract.py --write
"$PYTHON_BIN" domains/finance/tools/finance_autonomy_opportunity_scout.py --write
"$PYTHON_BIN" domains/finance/tools/finance_profit_readiness.py --write
"$PYTHON_BIN" domains/finance/tools/finance_data_intake_audit.py --write
"$PYTHON_BIN" domains/finance/tools/finance_operational_health.py --write
