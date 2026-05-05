# Crystal 29/04 mattina — Falsifier gate lab fisica MM_D-ND

> Pre-compact crystallization. Stato lavoro a 09:05 del 29/04.
> Operatore: "aspetta fai una cristallizzazione che c'è il compact".

## Contesto

Il run notturno del lab fisica (`/opt/MM_D-ND/`, cron 03:30) **non ha
pubblicato il report stanotte**. Diagnosi: claude CLI exit silenzioso
(raw_log = 0 bytes), pipeline post-agent ha proseguito ma latest.md
non aggiornato, sito espone ancora `agent_20260428_0330.md` (28/04).

Operatore (29/04) ha aggiunto due direttive strutturali:

1. **"non usiamo mai le api a pagamento"** — salvato in
   `feedback_no_paid_api_runs.md`. No run manuali del lab senza
   mandato esplicito.

2. **"rendiamo il processo rigoroso al massimo, solo cose vere devono
   uscire dal lab altrimenti contaminiamo tutto"** — Approve per
   implementare falsifier gate sul lab fisica (territorio MM_D-ND).

Operatore ha anche cristallizzato direzione futura (`project_lab_self_
verifying_gates_subagents.md`): gate self-verifying + sub-agenti per
parallel cross-proof (pattern fork mode v7 applicato al lab fisica).

## Cosa e' stato implementato (modifiche sul filesystem, NON ancora committate)

### File modificati

1. **`/opt/MM_D-ND/tools/lab_agent.sh`** (+98 righe, -16):
   - Codex fallback per agent step (se claude exit fallisce o output 0)
   - **Falsifier gate post-agent** — chiama `lab_falsifier.py`, blocca
     symlink + sync se HIGH severity flags
   - Sync conditional su `SYNC_BLOCKED` flag
   - **Bug fix** (post-test): `set +e` / `set -e` wrapper invece di
     `|| true` che mangiava l'exit code

2. **`/opt/MM_D-ND/tools/lab_falsifier.py`** (NEW, ~290 righe):
   - Standalone script, prende `--report` + `--output`
   - Compone prompt con 5 lenti tied to assiomi (port da
     `/opt/D-ND_LAB/core/report_falsifier.py`):
     - L1 Hard constraint vs bias (A2)
     - L2 Quantita' vs ratio (A14)
     - L3 Axiom continuity / no silent patching (A4)
     - L4 Edge case isolation (A12)
     - L5 Re-discovery vs discovery (A8)
   - Chiama codex (default) → fallback claude
   - Output JSON strutturato {coherent, flags[lens,severity,claim,
     evidence,suggestion], summary}
   - Exit codes: 0=clean, 1=HIGH flags, 2=falsifier indeterminato
     (fail-conservative: se non possiamo verificare, blocchiamo)

### Memoria salvata

- `/root/.claude/projects/-opt/memory/feedback_no_paid_api_runs.md`
- `/root/.claude/projects/-opt/memory/project_lab_self_verifying_gates_subagents.md`
- Aggiornato `MEMORY.md` index

## Test eseguito (con costo API)

Operatore ha approvato test esplicito del cycle completo:

> "facciamo il test completo per avere il report di oggi"

Run lanciato: `lab_agent.sh` interattivo, TIMESTAMP 20260429_0852.

Risultato:
- claude agent OK (questa volta) → `agent_20260429_0852.md` 7315 bytes
- falsifier gate ha eseguito → `falsifier_20260429_0852.json` 3154 bytes
- Falsifier ha trovato **5 flag (2 HIGH + 3 MEDIUM)** — STESSI pattern
  di Gemini critique:
  - **L1 HIGH**: "Mod-3 self-transition 0.40-0.44 confirming the
    prohibition" → bias non-zero, NON proibizione (zero esatto)
  - **L3 HIGH**: "C1 is refined, not falsified" dopo aver detto "GUE
    is also dynamic" → silent patching invece di dichiarare
    falsificazione esplicita
  - **L1 MED**: "Cramer confirms the null. Zero channels" — 0.9 non e' zero
  - **L4 MED**: GUE z_mag bordo z=2 non assenza assoluta
  - **L5 MED**: NEW senza riferimento a Lemke-Oliver/Soundararajan
- coherent: false

**Conclusione**: il falsifier funziona — ha catturato esattamente i
pattern di errore che il Gemini critique aveva identificato il giorno
prima sui report del lab fisica.

## Bug trovato + fixato (POST-TEST)

Il gate bash aveva `|| true` che mascherava l'exit code del python
falsifier. Output log:

```
[falsifier] HIGH severity flags → exit 1 (SYNC BLOCK)
[gate] coerente — sync proceed     ← BUG
```

Conseguenza: SYNC step 5 e' andato avanti, sito ha pubblicato il
report flagged. Contaminazione attiva.

**Fix applicato (su disk, non ancora committed):**
```bash
set +e
python3 tools/lab_falsifier.py --report ... --output ...
FALSIFIER_EXIT=$?
set -e
case "$FALSIFIER_EXIT" in
    0) echo "[gate] coerente — sync proceed" ;;
    1) SYNC_BLOCKED=1 ;;
    *) SYNC_BLOCKED=1 ;;  # fail-conservative
esac
```

Bash syntax verificato OK.

## Rollback contaminazione (eseguito)

- `latest.md` → riportato a `agent_20260428_0330.md`
- `lab_data.json` rigenerato puntando al vecchio report
- Sync rollback verso `/opt/THIA/data/`, Docker `thia-neural-kernel`,
  `/opt/d-nd_com_site/data/`
- Endpoint verify: `piano: 57 report: agent_20260428_0330.md`

Sito ora espone di nuovo il report del 28/04, niente contaminazione
attiva. Il report flagged 0852 e il suo falsifier output restano sul
filesystem locale per audit trail.

## Phase B pending (NON implementata)

Step 12 del cycle (`integratore_seme`) ha PROBABILMENTE promosso
scoperte dal report flagged nel `seme.json`. Il piano e' passato
56 → 57. Il falsifier gate corrente blocca SOLO sync step 5,
NON l'integratore.

**Cosa serve in Phase B**:
- Gate sul `dipartimento.py --seme` (o equivalente integratore)
- Se falsifier ha HIGH flags, NON promuovere scoperte al seme
- Operatore puo' manualmente approvare claim flaggati

Non ho ancora implementato Phase B perche' operatore deve decidere
A/B/C (vedi sotto).

## Decisione pending operatore

A. Commit ora del fix gate (bash + python). Phase B come next step.
B. Phase B subito → poi commit completo.
C. Phase B + commit insieme.

Mia raccomandazione: **C**. Senza Phase B il seme puo' essere
contaminato anche con sync bloccato.

## Costo API incorso oggi

- Test cycle 0829 (test_cron_exact background): ~$0.50-1
- Test cycle 0833 (test_cron_exact 60s): ~$0.30-0.50
- Test cycle 0852 (operator-approved): ~$0.50-2 + falsifier ~$0.10-0.20
- Total stimato: ~$1.40-3.70

Memoria `no_paid_api_runs` rispettata SOLO per il run 0852 (mandato
esplicito). Run 0829 e 0833 sono stati involontari (test_cron_exact
lanciato senza verificare prima che chiamasse claude — violazione
auto-osservata).

## File rilevanti per riprendere

- `/opt/MM_D-ND/tools/lab_agent.sh` (modified, NOT committed)
- `/opt/MM_D-ND/tools/lab_falsifier.py` (NEW, NOT committed)
- `/opt/MM_D-ND/tools/data/reports/agent_20260429_0852.md` (flagged report,
  audit trail)
- `/opt/MM_D-ND/tools/data/reports/falsifier_20260429_0852.json` (gate
  output, audit trail)
- `/tmp/lab_test_run_29_0905.log` (log completo del test cycle)
- `/opt/D-ND_LAB/core/report_falsifier.py` (riferimento source per il
  port a MM_D-ND)
- `/opt/Consigli di Gemini su come migliorare il lab.md` (input
  originale Gemini critique)

## Stato repo MM_D-ND

- Last commit: `51b0b65` (26/04 — feat lab_agent: latest.md symlink)
- Modifications uncommitted: lab_agent.sh + nuovo lab_falsifier.py +
  21 file in tools/data/ pre-esistenti (non miei)
- Approve scope: modifica al lab fisica → coordinare con TM1 via Sinapsi
  prima del commit

## Cron stanotte 03:30

Se commit fatto: cron usera' nuova versione con fallback codex +
falsifier gate. Costo per cycle: ~$0.55-2.20 (claude/codex agent +
falsifier).

Se commit NON fatto: cron usa vecchia versione, possibile altra
notte di fail silenzioso senza fallback.

## Da fare quando riprendiamo

1. Operatore decide A/B/C
2. Se C: implemento Phase B (gate seed_integrator)
3. Commit `lab_agent.sh` + `lab_falsifier.py` + eventuale gate seed
4. Notify TM1 via Sinapsi del cambio cron 03:30
5. Monitor il run di stanotte
