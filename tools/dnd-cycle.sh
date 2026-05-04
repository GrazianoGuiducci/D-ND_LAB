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

# Load env canonico
if [ -f /opt/THIA/.env ]; then
    set -a
    source /opt/THIA/.env
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

# Modello canonico OpenRouter (operatore 01/05): deepseek-v4-pro.
export OPENROUTER_MODEL="${OPENROUTER_MODEL:-deepseek/deepseek-v4-pro}"

cd /opt/D-ND_LAB
LOG_DIR="data/$DOMAIN"
mkdir -p "$LOG_DIR/reports"
LOG_FILE="$LOG_DIR/cycle_$(date +%Y%m%d_%H%M%S).log"

echo "=== D-ND_LAB cycle wrapper ===" | tee "$LOG_FILE"
echo "Domain: $DOMAIN" | tee -a "$LOG_FILE"
echo "Provider chain: $LLM_PROVIDER_CHAIN" | tee -a "$LOG_FILE"
echo "OpenRouter key set: $([ -n "${OPENROUTER_API_KEY:-}" ] && echo yes || echo NO)" | tee -a "$LOG_FILE"
echo "Codex home: ${CODEX_HOME:-default}" | tee -a "$LOG_FILE"
echo "Started: $(date -Iseconds)" | tee -a "$LOG_FILE"
echo "Log: $LOG_FILE" | tee -a "$LOG_FILE"
echo "===" | tee -a "$LOG_FILE"

python3 -m core.cli run --domain "$DOMAIN" 2>&1 | tee -a "$LOG_FILE"
