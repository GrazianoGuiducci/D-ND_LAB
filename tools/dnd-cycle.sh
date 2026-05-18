#!/bin/bash
# dnd-cycle.sh — Wrapper per cycle manuale del D-ND_LAB con env caricato.
#
# Carica OPENROUTER_API_KEY + altre env vars dal file canonico THIA prima
# di invocare il CLI del lab. Necessario perché il cron / shell manuali
# non leggono .env automaticamente, e senza OPENROUTER_API_KEY il 3°
# fallback (deepseek-v4-pro via OpenRouter) fallisce silenziosamente
# quando codex 401 + claude down.
#
# Pattern speculare a /opt/MM_D-ND/tools/lab_agent.sh (commit 04/05).
#
# Uso:
#   bash /opt/D-ND_LAB/tools/dnd-cycle.sh <domain>
#   bash /opt/D-ND_LAB/tools/dnd-cycle.sh meta-lab
#   bash /opt/D-ND_LAB/tools/dnd-cycle.sh ops-decisions

set -euo pipefail

DOMAIN="${1:-}"
if [ -z "$DOMAIN" ]; then
    echo "Usage: $0 <domain>" >&2
    echo "Available domains: $(ls /opt/D-ND_LAB/domains/ | tr '\n' ' ')" >&2
    exit 1
fi

# Preserve explicit one-shot overrides passed by the caller; sourced .env files
# must not erase an operator/test decision for this run.
REQUESTED_LLM_PROVIDER_CHAIN="${LLM_PROVIDER_CHAIN:-}"
REQUESTED_LLM_MODEL="${LLM_MODEL:-}"
REQUESTED_OPENROUTER_MODEL="${OPENROUTER_MODEL:-}"

# Load env canonico THIA, poi env locale del Lab.
# Il fallback HTTP usa OpenRouter tramite OPENROUTER_API_KEY/OPENROUTER_MODEL;
# LLM_* resta supportato solo come compatibilita' OpenAI-compatible legacy.
if [ -f /opt/THIA/.env ]; then
    set -a
    source /opt/THIA/.env
    set +a
fi
if [ -f /opt/D-ND_LAB/.env ]; then
    set -a
    source /opt/D-ND_LAB/.env
    set +a
fi

# Codex isolated home (refactor 04/05) per evitare race condition con
# VS Code extension chatgpt sullo stesso account ChatGPT.
if [ -f /root/.codex_lab/auth.json ]; then
    export CODEX_HOME=/root/.codex_lab
fi

# Provider chain default: codex CLI primary → claude CLI fallback →
# openrouter HTTP (deepseek-v4-pro) ultimo resort.
export LLM_PROVIDER_CHAIN="${LLM_PROVIDER_CHAIN:-codex-cli,claude-cli,openrouter}"
if [ -n "$REQUESTED_LLM_PROVIDER_CHAIN" ]; then
    export LLM_PROVIDER_CHAIN="$REQUESTED_LLM_PROVIDER_CHAIN"
fi

# Modello canonico OpenRouter (operatore 01/05): deepseek-v4-pro.
export OPENROUTER_MODEL="${OPENROUTER_MODEL:-deepseek/deepseek-v4-pro}"
if [ -n "$REQUESTED_OPENROUTER_MODEL" ]; then
    export OPENROUTER_MODEL="$REQUESTED_OPENROUTER_MODEL"
fi
export OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-${LLM_API_KEY:-}}"
if [ -n "$REQUESTED_LLM_MODEL" ]; then
    export LLM_MODEL="$REQUESTED_LLM_MODEL"
fi

cd /opt/D-ND_LAB
PYTHON_BIN="${PYTHON_BIN:-/opt/D-ND_LAB/.venv/bin/python3}"
if [ ! -x "$PYTHON_BIN" ]; then
    PYTHON_BIN="python3"
fi
LOG_DIR="data/$DOMAIN"
mkdir -p "$LOG_DIR/reports"
LOG_FILE="$LOG_DIR/cycle_$(date +%Y%m%d_%H%M%S).log"

echo "=== D-ND_LAB cycle wrapper ===" | tee "$LOG_FILE"
echo "Domain: $DOMAIN" | tee -a "$LOG_FILE"
echo "Provider chain: $LLM_PROVIDER_CHAIN" | tee -a "$LOG_FILE"
echo "OpenRouter key set: $([ -n "${OPENROUTER_API_KEY:-}" ] && echo yes || echo NO)" | tee -a "$LOG_FILE"
echo "Codex home: ${CODEX_HOME:-default}" | tee -a "$LOG_FILE"
echo "Python: $PYTHON_BIN" | tee -a "$LOG_FILE"
echo "Started: $(date -Iseconds)" | tee -a "$LOG_FILE"
echo "Log: $LOG_FILE" | tee -a "$LOG_FILE"
echo "===" | tee -a "$LOG_FILE"

"$PYTHON_BIN" -m core.cli run --domain "$DOMAIN" 2>&1 | tee -a "$LOG_FILE"
