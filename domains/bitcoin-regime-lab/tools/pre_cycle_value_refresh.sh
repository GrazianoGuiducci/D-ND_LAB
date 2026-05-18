#!/bin/bash
# Deterministic host-side value refresh for Bitcoin Regime Lab cycles.
#
# This hook runs before the cognitive agent. It keeps public market/feed
# artifacts in the same LAB_DATA_DIR consumed by the dashboard and by the
# agent field, without relying on the agent shell to resolve external APIs.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${DND_LAB_ROOT:-$(cd "$SCRIPT_DIR/../../.." && pwd)}"
PYTHON_BIN="${PYTHON_BIN:-$ROOT/.venv/bin/python3}"
if [ ! -x "$PYTHON_BIN" ]; then
    PYTHON_BIN="python3"
fi

cd "$ROOT"

"$PYTHON_BIN" domains/bitcoin-regime-lab/tools/btc_market_card.py --write
"$PYTHON_BIN" domains/bitcoin-regime-lab/tools/btc_exchange_ohlcv.py --write
"$PYTHON_BIN" domains/bitcoin-regime-lab/tools/btc_first_hypothesis.py --write
"$PYTHON_BIN" domains/bitcoin-regime-lab/tools/btc_timeframe_matrix.py --write
