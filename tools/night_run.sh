#!/bin/bash
# night_run.sh — esecuzione sequenziale dei lab D-ND in cascata.
#
# Pattern (operatore 05/05 sera):
# - finance → 10 min → bio-rhythms → 10 min → ops-decisions → 10 min → editorial
# - meta-lab ESCLUSO (è prototipatore, non lab — vedi
#   memory/cristallo_meta_lab_is_prototyper_2026-05-05.md)
# - Telegram notify dopo ogni cycle (operatore vede progresso)
# - Lock file per evitare doppio lancio
# - Logs separati in data/<lab>/night_run_<ts>.log
# - Trap on exit per cleanup

set -u  # NIENTE -e: vogliamo continuare anche se un cycle fallisce

LOCK_FILE="/tmp/dnd_lab_night_run.lock"
LAB_DATA_DIR="/opt/D-ND_LAB/data"
RUN_TS="$(date +%Y%m%d_%H%M%S)"
PAUSE_BETWEEN_CYCLES=600   # 10 minuti, "un po'" come da operatore
LABS=(finance bio-rhythms ops-decisions editorial)

# Lock
if [ -f "$LOCK_FILE" ]; then
    echo "[ERROR] night_run already running (lock file: $LOCK_FILE, pid $(cat "$LOCK_FILE"))"
    exit 1
fi
echo $$ > "$LOCK_FILE"
trap 'rm -f "$LOCK_FILE"; echo "[$(date +%H:%M:%S)] night_run cleanup done"' EXIT

# Telegram notify helper (uses THIA api)
notify_telegram() {
    local msg="$1"
    if [ -n "${THIA_API_TOKEN:-}" ]; then
        curl -s -X POST "http://localhost:3002/api/notify" \
            -H "X-THIA-Token: $THIA_API_TOKEN" \
            -H "Content-Type: application/json" \
            -d "$(printf '{"message":%s}' "$(jq -Rsa . <<<"$msg")")" \
            >/dev/null 2>&1 || true
    fi
}

# Load env (THIA_API_TOKEN, LAB_CODEX_HOME, etc.)
set -a
source /opt/THIA/.env
set +a

cd /opt/D-ND_LAB

LAB_LIST_PRETTY=$(IFS=', '; echo "${LABS[*]}")
echo "[$(date +%H:%M:%S)] === NIGHT RUN START · ts=$RUN_TS ==="
echo "[$(date +%H:%M:%S)] Sequenza: $LAB_LIST_PRETTY (pausa ${PAUSE_BETWEEN_CYCLES}s tra cycle)"
notify_telegram "🌙 Night run avviato · sequenza: $LAB_LIST_PRETTY · ETA ~$(( (${#LABS[@]} * 5 + (${#LABS[@]} - 1) * 10) )) min"

for i in "${!LABS[@]}"; do
    LAB="${LABS[$i]}"
    LAB_LOG="$LAB_DATA_DIR/$LAB/night_run_${RUN_TS}_${LAB}.log"
    mkdir -p "$LAB_DATA_DIR/$LAB"

    CYCLE_START="$(date +%H:%M:%S)"
    echo "[$CYCLE_START] [$((i+1))/${#LABS[@]}] Starting cycle: $LAB"
    notify_telegram "🔵 Lab $LAB · cycle in corso ($((i+1))/${#LABS[@]})"

    # Run cycle (blocking)
    /opt/D-ND_LAB/.venv/bin/python3 -m core.cli run --domain "$LAB" \
        > "$LAB_LOG" 2>&1
    EXIT_CODE=$?
    CYCLE_END="$(date +%H:%M:%S)"

    # Extract verdict summary from log
    if [ $EXIT_CODE -eq 0 ]; then
        VERDETTO=$(grep -E "Cycle ended|aeternitas|veritas_score|trajectory_evaluator|narrative_writer" "$LAB_LOG" 2>/dev/null | tail -8 | sed 's/^[^]]*] //' | tr '\n' ' | ')
        SUMMARY=$(grep -E "veritas_score:|trajectory_evaluator:|aeternitas:|narrative_writer:" "$LAB_LOG" 2>/dev/null | tail -4 | sed 's/^.*INFO[^—]*— //')
        echo "[$CYCLE_END] $LAB ok"
        notify_telegram "✅ Lab $LAB chiuso · $(echo "$SUMMARY" | tr '\n' ' | ' | head -c 400)"
    else
        ERR=$(tail -20 "$LAB_LOG" 2>/dev/null | grep -E "Error|FAIL|exception|Traceback" | head -3 | tr '\n' ' | ')
        echo "[$CYCLE_END] $LAB FAILED exit=$EXIT_CODE"
        notify_telegram "❌ Lab $LAB FAILED exit=$EXIT_CODE · $(echo "$ERR" | head -c 300)"
    fi

    # Pause between cycles (skip after last)
    if [ $((i+1)) -lt ${#LABS[@]} ]; then
        echo "[$(date +%H:%M:%S)] Pausa ${PAUSE_BETWEEN_CYCLES}s..."
        sleep "$PAUSE_BETWEEN_CYCLES"
    fi
done

FINAL_TIME="$(date +%H:%M:%S)"
echo "[$FINAL_TIME] === NIGHT RUN END · ts=$RUN_TS ==="
notify_telegram "🌙 Night run completato · vedi cycle narrati: https://lab.d-nd.com/n/"

exit 0
