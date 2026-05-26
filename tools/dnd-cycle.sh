#!/bin/bash
# dnd-cycle.sh — Wrapper per cycle manuale del D-ND_LAB con env caricato.
#
# Carica env canonico THIA + env locale del Lab prima di invocare il CLI.
# Il fallback HTTP pagato non e' default per i cycle/test: OpenRouter va
# richiesto esplicitamente con LLM_PROVIDER_CHAIN=codex-cli,claude-cli,openrouter
# o LLM_PROVIDER_CHAIN=openrouter.
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
REQUESTED_LAB_DATA_DIR="${LAB_DATA_DIR:-}"
REQUESTED_LAB_CODEX_HOME="${LAB_CODEX_HOME:-}"
REQUESTED_CODEX_HOME="${CODEX_HOME:-}"

# Load env canonico THIA, poi env locale del Lab.
# OpenRouter resta supportato tramite OPENROUTER_API_KEY/OPENROUTER_MODEL solo
# se incluso esplicitamente nella provider chain. LLM_* resta supportato come
# compatibilita' OpenAI-compatible legacy.
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

# Codex home: use the operator's active Codex login by default. Ignore
# LAB_CODEX_HOME loaded from .env; an isolated home must be requested
# explicitly on the command line for this invocation.
if [ -n "$REQUESTED_LAB_CODEX_HOME" ]; then
    export CODEX_HOME="$REQUESTED_LAB_CODEX_HOME"
elif [ -n "$REQUESTED_CODEX_HOME" ]; then
    export CODEX_HOME="$REQUESTED_CODEX_HOME"
else
    unset CODEX_HOME
    unset LAB_CODEX_HOME
fi

# Provider chain default: only Codex CLI. Ignore LLM_PROVIDER_CHAIN loaded
# from .env; other providers are opt-in only when passed by the caller.
export LLM_PROVIDER_CHAIN="codex-cli"
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

# The production dashboard runs on the host and reads /opt/D-ND_LAB/data.
# /opt/D-ND_LAB/.env may contain LAB_DATA_DIR=/data for container installs;
# keep that only when the caller explicitly requested it for this invocation.
export LAB_DATA_DIR="${REQUESTED_LAB_DATA_DIR:-/opt/D-ND_LAB/data}"

cd /opt/D-ND_LAB
PYTHON_BIN="${PYTHON_BIN:-/opt/D-ND_LAB/.venv/bin/python3}"
if [ ! -x "$PYTHON_BIN" ]; then
    PYTHON_BIN="python3"
fi
LOG_DIR="data/$DOMAIN"
mkdir -p "$LOG_DIR/reports"
CYCLE_TS="$(date +%Y%m%d_%H%M)"
LOG_FILE="$LOG_DIR/cycle_$(date +%Y%m%d_%H%M%S).log"
PRE_CYCLE_HOOK="domains/$DOMAIN/tools/pre_cycle_value_refresh.sh"
POST_CYCLE_HOOK="domains/$DOMAIN/tools/post_cycle_closure.sh"
LOCK_DIR="$LAB_DATA_DIR/$DOMAIN/locks"
LOCK_FILE="$LOCK_DIR/cycle.lock"
mkdir -p "$LOCK_DIR"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    echo "[ERROR] cycle already running for domain=$DOMAIN (lock: $LOCK_FILE)" | tee "$LOG_FILE"
    exit 75
fi
echo "$$ $(date -Iseconds)" 1>&9

export DND_LAB_ACTIVE_CYCLE_TS="$CYCLE_TS"
export DND_LAB_ACTIVE_CYCLE_LOG="$LOG_FILE"

echo "=== D-ND_LAB cycle wrapper ===" | tee "$LOG_FILE"
echo "Domain: $DOMAIN" | tee -a "$LOG_FILE"
echo "Cycle ts: $DND_LAB_ACTIVE_CYCLE_TS" | tee -a "$LOG_FILE"
echo "Provider chain: $LLM_PROVIDER_CHAIN" | tee -a "$LOG_FILE"
echo "OpenRouter key set: $([ -n "${OPENROUTER_API_KEY:-}" ] && echo yes || echo NO)" | tee -a "$LOG_FILE"
echo "Codex home: ${CODEX_HOME:-default}" | tee -a "$LOG_FILE"
echo "Python: $PYTHON_BIN" | tee -a "$LOG_FILE"
echo "Started: $(date -Iseconds)" | tee -a "$LOG_FILE"
echo "Log: $LOG_FILE" | tee -a "$LOG_FILE"
echo "===" | tee -a "$LOG_FILE"

if [ -x "$PRE_CYCLE_HOOK" ]; then
    echo "[pre-cycle] running $PRE_CYCLE_HOOK" | tee -a "$LOG_FILE"
    "$PRE_CYCLE_HOOK" 2>&1 | tee -a "$LOG_FILE"
    echo "[pre-cycle] completed" | tee -a "$LOG_FILE"
fi

"$PYTHON_BIN" -m core.cli run --domain "$DOMAIN" 2>&1 | tee -a "$LOG_FILE"

if [ -x "$POST_CYCLE_HOOK" ]; then
    echo "[post-cycle] running $POST_CYCLE_HOOK" | tee -a "$LOG_FILE"
    "$POST_CYCLE_HOOK" 2>&1 | tee -a "$LOG_FILE"
    echo "[post-cycle] completed" | tee -a "$LOG_FILE"
fi
