#!/bin/bash
# bitcoin-refresh-value.sh — refresh value-facing Bitcoin artifacts only.
#
# This is intentionally not a cognitive Lab cycle. It runs no LLM and produces
# no report, signal, target or advice. Use it before/alongside scheduled BTC
# cycles so the dashboard and agent field can see fresh public data-card
# context.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${DND_LAB_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
PYTHON_BIN="${PYTHON_BIN:-$ROOT/.venv/bin/python3}"
if [ ! -x "$PYTHON_BIN" ]; then
    PYTHON_BIN="python3"
fi

cd "$ROOT"

echo "=== D-ND_LAB Bitcoin value refresh ==="
echo "Started: $(date -Iseconds)"
echo "Python: $PYTHON_BIN"

"$PYTHON_BIN" domains/bitcoin-regime-lab/tools/btc_market_card.py --write
"$PYTHON_BIN" domains/bitcoin-regime-lab/tools/btc_exchange_ohlcv.py --write

echo "Completed: $(date -Iseconds)"
