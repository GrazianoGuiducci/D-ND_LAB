#!/bin/bash
# dnd-init.sh — Entry point CLI per generare un nuovo lab via meta-lab.
#
# Pattern: dialogo progressivo → seed.json con direttiva → meta-lab cycle
# (genera template + MML del lab figlio) → M1-M7 validator → opzionalmente
# primo cycle del lab generato.
#
# Pattern speculare a tools/dnd-cycle.sh ma per fase di **genesi** del
# lab nuovo, non cycle. Questo CLI codifica il pattern manuale che ho
# usato per generare ops-decisions il 2026-05-04.
#
# Uso:
#   dnd-init.sh <slug> --directive "<frase chiara di cosa il lab deve fare>"
#               [--corpus <path>] [--no-validate] [--first-cycle]
#               [--runtime claude|codex|hermes|standalone]
#
# Esempi:
#   dnd-init.sh finance --directive "Lab di dominio finance D-ND. Studia regime shift nei mercati FX. Acquirente: hedge fund + family office. Naive baseline: backtest VaR statico vs informato dal modus D-ND."
#
#   dnd-init.sh biology --directive "Lab biology drug-discovery. Studia interazione drug-target via dipoli affinità/selettività. APIs no-auth: PubChem + ChEMBL + OpenTargets." --first-cycle

set -euo pipefail

SLUG=""
DIRECTIVE=""
CORPUS=""
DO_VALIDATE=true
DO_FIRST_CYCLE=false
RUNTIME="any"

# Parse args
while [ $# -gt 0 ]; do
    case "$1" in
        --directive) DIRECTIVE="$2"; shift 2 ;;
        --corpus) CORPUS="$2"; shift 2 ;;
        --no-validate) DO_VALIDATE=false; shift ;;
        --first-cycle) DO_FIRST_CYCLE=true; shift ;;
        --runtime) RUNTIME="$2"; shift 2 ;;
        --help|-h)
            sed -n '1,30p' "$0" | grep -E '^#' | sed 's/^# *//'
            exit 0 ;;
        --*) echo "Unknown option: $1" >&2; exit 1 ;;
        *)
            if [ -z "$SLUG" ]; then SLUG="$1"; else echo "Multiple slugs?: $1" >&2; exit 1; fi
            shift ;;
    esac
done

# Validation slug
if [ -z "$SLUG" ]; then
    echo "Usage: $0 <slug> --directive \"...\" [opts]" >&2
    exit 1
fi
if ! [[ "$SLUG" =~ ^[a-z][a-z0-9_-]*$ ]]; then
    echo "Invalid slug '$SLUG' — must match ^[a-z][a-z0-9_-]*$" >&2
    exit 1
fi
RESERVED=("meta-lab" "physics" "editorial" "ops-decisions")
for r in "${RESERVED[@]}"; do
    if [ "$SLUG" = "$r" ]; then
        echo "Slug '$SLUG' is reserved (existing lab). Use different name." >&2
        exit 1
    fi
done

# Validation directive
if [ -z "$DIRECTIVE" ]; then
    echo "--directive is required (1-2 sentences describing what the lab should do)" >&2
    echo "Example: --directive \"Lab finance regime shift. Naive baseline: VaR statico vs D-ND modus.\"" >&2
    exit 1
fi

# Load env canonico
if [ -f /opt/THIA/.env ]; then
    set -a; source /opt/THIA/.env; set +a
fi
if [ -f /root/.codex_lab/auth.json ]; then
    export CODEX_HOME=/root/.codex_lab
fi
export LLM_PROVIDER_CHAIN="${LLM_PROVIDER_CHAIN:-codex-cli,claude-cli,openrouter}"

cd /opt/D-ND_LAB

# Check dominio già esiste?
if [ -d "domains/$SLUG" ]; then
    echo "Domain 'domains/$SLUG/' già esiste. Use --force? (NOT IMPLEMENTED — abort)" >&2
    exit 1
fi

# 1. Crea data dir + seed.json con direttiva
DATA_DIR="data/meta-lab"
mkdir -p "$DATA_DIR"

CORPUS_REF=""
if [ -n "$CORPUS" ] && [ -e "$CORPUS" ]; then
    CORPUS_REF=", corpus disponibile in $CORPUS"
fi

NOW_TS=$(date -u +"%Y-%m-%dT%H:%M:%S+00:00")
cat > "$DATA_DIR/seed.json" <<EOF
{
  "_meta": {
    "domain": "meta-lab",
    "cycle_purpose": "generate_new_lab_${SLUG}",
    "operator_directive": "Generate template completo + MML del lab '${SLUG}'. Direttiva: ${DIRECTIVE}${CORPUS_REF}"
  },
  "timestamp": "${NOW_TS}",
  "piano": 1,
  "direzione": "Genera filesystem tree completo del lab '${SLUG}' (config.json + context.md + about.md IT+EN + seed_tensions.json + tension_to_category.json + assertions.py + tools/ + mml.json conforme a mml.schema.json + transduction.md). Direttiva operatore: ${DIRECTIVE}. Verifica falsifier meta M1-M7 prima di dichiarare TEMPLATE_VALID. Se il dominio è data-centric, includi external_apis no-auth nel MML (pattern hermes — vedi context.md sezione dedicata). Runtime preferito: ${RUNTIME}.",
  "tensioni": [
    {
      "tipo": "task",
      "id": "GENERATE_LAB_${SLUG^^}",
      "claim": "Generare template completo del lab '${SLUG}' con MML coerente e nota di transduzione. Output: domains/${SLUG}/ con tutti i file canonici. Falsifier M1-M7 deve dare TEMPLATE_VALID.",
      "intensita": 1.0,
      "porta": "operator_request",
      "condensato_ref": "A2,A8,A14"
    },
    {
      "tipo": "scoperta",
      "id": "DIRECTIVE_${SLUG^^}",
      "claim": "Direttiva operatore per ${SLUG}: ${DIRECTIVE}",
      "intensita": 0.95,
      "porta": "operator_directive",
      "condensato_ref": "A8"
    }
  ]
}
EOF

echo "=== dnd-init: meta-lab cycle to generate '${SLUG}' ==="
echo "Slug: ${SLUG}"
echo "Directive: ${DIRECTIVE}"
echo "Corpus: ${CORPUS:-none}"
echo "Runtime: ${RUNTIME}"
echo "Provider chain: ${LLM_PROVIDER_CHAIN}"
echo "Codex home: ${CODEX_HOME:-default}"
echo "Seed written to: ${DATA_DIR}/seed.json"
echo "=== Launching meta-lab cycle ==="

LOG_FILE="${DATA_DIR}/cycle_init_${SLUG}_$(date +%Y%m%d_%H%M%S).log"
python3 -m core.cli run --domain meta-lab 2>&1 | tee "$LOG_FILE"

# 2. Verifica template generato esiste
if [ ! -d "domains/$SLUG" ]; then
    echo "" >&2
    echo "FAIL: meta-lab cycle did not generate domains/${SLUG}/" >&2
    echo "Check log: ${LOG_FILE}" >&2
    exit 1
fi

# 3. Validate M1-M7
if [ "$DO_VALIDATE" = true ]; then
    echo ""
    echo "=== M1-M7 falsifier on generated template ==="
    python3 domains/meta-lab/tools/lab_template_validator.py --strict-m7 "domains/$SLUG" || {
        echo "WARN: validator non-zero exit. Template generated ma non TEMPLATE_VALID." >&2
        echo "Inspect manuale: domains/${SLUG}/" >&2
    }
fi

# 4. First cycle opzionale
if [ "$DO_FIRST_CYCLE" = true ]; then
    echo ""
    echo "=== First cycle del nuovo lab '${SLUG}' ==="
    bash /opt/D-ND_LAB/tools/dnd-cycle.sh "$SLUG"
fi

echo ""
echo "=== dnd-init complete ==="
echo "Lab '${SLUG}' generated in domains/${SLUG}/"
echo "Next steps:"
echo "  - Inspect: python3 -m core.cli inspect --domain ${SLUG}"
echo "  - First cycle: bash tools/dnd-cycle.sh ${SLUG}"
echo "  - Validator: python3 domains/meta-lab/tools/lab_template_validator.py --strict-m7 domains/${SLUG}"
