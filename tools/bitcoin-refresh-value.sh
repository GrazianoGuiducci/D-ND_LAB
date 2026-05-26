#!/bin/bash
# bitcoin-refresh-value.sh — refresh value-facing Bitcoin artifacts only.
#
# This is intentionally not a cognitive Lab cycle. It runs no LLM and produces
# no report and executes no real orders. It may refresh paper-trading /
# simulation evidence, but it does not publish advice or touch capital. Use it
# before/alongside scheduled BTC cycles so the dashboard and agent field can see
# fresh public data-card context.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${DND_LAB_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
PYTHON_BIN="${PYTHON_BIN:-$ROOT/.venv/bin/python3}"
if [ ! -x "$PYTHON_BIN" ]; then
    PYTHON_BIN="python3"
fi

cd "$ROOT"

export DND_LAB_LINEAGE_SESSION="btc_value_refresh"
export DND_LAB_VALUE_REFRESH_TS="$(date -u +%Y%m%d_%H%M%S)"
unset DND_LAB_ACTIVE_CYCLE_TS
unset DND_LAB_ACTIVE_CYCLE_LOG

echo "=== D-ND_LAB Bitcoin value refresh ==="
echo "Started: $(date -Iseconds)"
echo "Refresh ts: $DND_LAB_VALUE_REFRESH_TS"
echo "Python: $PYTHON_BIN"

"$PYTHON_BIN" domains/bitcoin-regime-lab/tools/btc_market_card.py --write
"$PYTHON_BIN" domains/bitcoin-regime-lab/tools/btc_exchange_ohlcv.py --write
"$PYTHON_BIN" domains/bitcoin-regime-lab/tools/btc_daily_closed_evidence_gate.py --write
"$PYTHON_BIN" domains/bitcoin-regime-lab/tools/btc_first_hypothesis.py --write
"$PYTHON_BIN" domains/bitcoin-regime-lab/tools/btc_timeframe_matrix.py --write
"$PYTHON_BIN" domains/bitcoin-regime-lab/tools/btc_method_intake_card.py --write
"$PYTHON_BIN" domains/bitcoin-regime-lab/tools/btc_daily_inefficiency_candidate.py --write
"$PYTHON_BIN" domains/bitcoin-regime-lab/tools/btc_fill_rule_sensitivity.py --write
"$PYTHON_BIN" domains/bitcoin-regime-lab/tools/btc_auto_ignite.py --write
"$PYTHON_BIN" domains/bitcoin-regime-lab/tools/btc_volume_profile_lvn_proxy.py --write
"$PYTHON_BIN" domains/bitcoin-regime-lab/tools/btc_policy_simulator.py --write
"$PYTHON_BIN" domains/bitcoin-regime-lab/tools/btc_paper_simulation_ledger.py --write
"$PYTHON_BIN" domains/bitcoin-regime-lab/tools/btc_policy_mutation_contract.py --write
"$PYTHON_BIN" domains/bitcoin-regime-lab/tools/btc_autology_artifacts.py --write
"$PYTHON_BIN" domains/bitcoin-regime-lab/tools/btc_retention_regime_selector.py --write
"$PYTHON_BIN" domains/bitcoin-regime-lab/tools/btc_daily_method_pressure_test.py --write
"$PYTHON_BIN" domains/bitcoin-regime-lab/tools/btc_cognitive_state.py --write
"$PYTHON_BIN" domains/bitcoin-regime-lab/tools/btc_producer_trace_sink.py --write
"$PYTHON_BIN" domains/bitcoin-regime-lab/tools/btc_operational_health.py --write

echo "Completed: $(date -Iseconds)"
