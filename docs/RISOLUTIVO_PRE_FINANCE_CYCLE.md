# Atto risolutivo pre-cycle 1 finance

> Direttiva operatore 2026-05-05 ~13:30:
> "lanciamo quando tutto quello che possibile fare è stato fatto, deve
> essere un atto risolutivo di un'epoca, non può lasciare qualcosa di
> incompiuto · facciamo tutto"
>
> Il primo cycle del lab finance non è test sperimentale. È atto
> simbolico che chiude l'epoca dell'infrastruttura e apre l'epoca dei
> prodotti reali. Va lanciato solo quando ogni asimmetria/incompletezza
> strutturale del sistema è chiusa.

## Stato del sistema ENTRY (15 commit + 12 cristallizzazioni)

Vedi `MEMORY.md` index. In sintesi:
- D-ND_LAB sandbox: G1+G2+G3+G4 chiusi, lab finance generato e validato
- MM_D-ND lab fisico: aeternitas + universal mapping P0 portati
- Manifesto sito + direttiva self-awareness cristallizzati

## Asimmetrie/incompletezze residue

Identificate nell'audit pre-launch:

1. **Lab fisico MM_D-ND ha aeternitas ma NON trajectory_apply / NON
   veritas_score / NON promotion_proposer** — D-ND_LAB sandbox è più
   evoluto del lab production
2. **Atto E kairos quantitativo** — ρ esiste, kairos può usarlo per
   regime selection. Non implementato
3. **Self-awareness backlog**: dnd_lab_describe.sh / skill_invocation_log
   / dashboard `/labs` non costruiti
4. **Verifiche specifiche lab finance**:
   - Config movements (verifica esplicita 19 enabled corretti)
   - External APIs raggiungibili (pre-flight network)
   - bicono_extractor enabled per finance? (default disabled in
     meta-lab template, ma lab data-centric ha bicono)
5. **D-ND_BOOK**: nessuna voce su lab data-centric come pattern
6. **Sistema snapshot**: nessun marker storico "stato pre-cycle1 finance"

## Piano di esecuzione

### Fase 1 — Chiusure veloci (target ~1h)

**A. Audit config.json finance** (5 min)
- Leggere `domains/finance/config.json`
- Verificare 19 movements del default + check enabled (trajectory_apply,
  veritas_score, promotion_proposer, bicono_extractor)
- Se manca o è disabled, fix
- Re-validate M1-M6
- Commit se cambia

**B. Pre-flight network test API** (5 min)
- `curl -s --max-time 5` ai 4 endpoint hermes finance
- Output: `data/finance/preflight_apis_<ts>.json` con status code per
  ognuno
- Se 0/4 raggiungibili → flag nel context.md "no_network at cycle1"
- Se ≥3/4 raggiungibili → mantieni vincolo "no rete primo cycle" (è di
  design)

**C. D-ND_BOOK voce nuova** (15 min)
- Nuova sezione/sottosezione in `D-ND_BOOK.md` (probabile sez VI
  "Architettura business" o sez III "Pattern di costruzione del
  sistema")
- Titolo: "Lab data-centric come prodotto del modello"
- Riferimento manifesto + finance come primo esempio
- Pattern: meta-lab + MML multi-layer + hermes APIs + 4 livelli
  osservabilità (aeternitas + veritas + falsifier + promotion)

**D. System snapshot pre-cycle1** (15 min)
- Nuovo file `data/system_snapshot_pre_finance_cycle1.json`
- Stato strutturale: 5 lab attivi (slug + status), 113 skill catalogo,
  ~20 movements registrati, 5+ provider chain, 16 commit di sessione
- Primo step direttiva self-awareness — dimostra che sistema può
  enumerare se stesso
- File è atto simbolico + dato operativo

**E. Cristallo "atto risolutivo"** (10 min)
- File `cristallo_atto_risolutivo_finance_cycle1_2026-05-05.md` in memoria
- Contesto: pre/post epoch
- Pronostico esplicito (già in commit `a5b2b8e`)
- Cosa significa se va bene/se va male
- Marca momento storico (3 livelli osservabilità + 5 lab + auto-genesi)

### Fase 2 — Strutturali (target ~3-5h)

**F. Port veritas + promotion + trajectory_apply a MM_D-ND lab fisico** (~1.5h)

Adattamento di:
- `core/veritas_score.py` → `tools/lab_veritas.py` standalone Python
- `core/promotion_proposer.py` → `tools/lab_promotion.py` standalone
- `core/trajectory_apply.py` → `tools/lab_trajectory_apply.py` standalone

Wire in `lab_agent.sh`:
- Step 0.5: `lab_trajectory_apply.py` (dopo autopsy, prima di build_field)
- Step 12.6: `lab_veritas.py` (dopo aeternitas step 12.5)
- Step 13.6: `lab_promotion.py` (dopo trajectory_evaluator step 13)

Ogni script:
- Standalone Python (no core/ dependency)
- Legge state da `tools/data/seme.json` + log relativi
- Output a `tools/data/<veritas|promotion|trajectory>/`
- Modalità warn (no block production)

Test pre-deploy:
- `bash test_cron_exact.sh` PASS
- Smoke run di ognuno standalone

Risultato atteso: lab fisico ha la stessa osservabilità di D-ND_LAB.
Cron 03:30 di domani notte avrà:
- aeternitas log (già attivo)
- veritas log (NEW)
- promotion proposals (NEW, se finding eligible)
- trajectory applied auto (NEW)

**G. Atto E kairos quantitativo** (~1.5h)

Refactor `core/trajectory_evaluator.py` per usare ρ (veritas) come
input nella regime selection:

- Calcolo IA (Indice di Attrito) dal cycle:
  - 1 - ρ (more attrito if quality low)
  - + n_high_flags / n_total_flags
  - + (1 if aeternitas VETO else 0) * 0.3
- Decision band → regime selection:
  - IA > 0.7 → Regime DISTRUZIONE (sistema compiacente, distruggi
    presupposti)
  - 0.3 < IA ≤ 0.7 → Regime MAIEUTIC (zona grigia, forza emergenza)
  - IA ≤ 0.3 → Regime RISONANZA (sistema solido, evolution costruttiva)
- Decision space resta lo stesso (NEXT_CYCLE/REDESIGN/CRYSTALLIZE/
  STOP_FOR_REVIEW/ESCALATE), ma ora è guidato da regime quantitativo

Backward compat: se ρ non disponibile (cycle senza veritas_score), usa
keyword-based logic precedente. Non rompe lab non-aggiornati.

**H. dnd_lab_describe.sh** (~1h)

Primo atto del backlog self-awareness. Tool che descrive ogni lab:

```bash
bash /opt/D-ND_LAB/tools/dnd_lab_describe.sh <lab>
```

Output strutturato (JSON o markdown):
- Lab identity (da MML)
- Skills attive per layer
- Tools custom + status (importable / executable)
- External APIs dichiarate
- Cycle history (ultimi 5 cycle con ρ/aeternitas/coherent)
- Tensioni attive (da seed.json)
- File system tree
- Validator M1-M6 status

Modalità:
- `--json`: machine-readable
- default: markdown leggibile per operatore

Test: `dnd_lab_describe.sh finance` produce report comprensivo.

### Fase 3 — Re-validate finale (~30 min)

- Tutti i 5 lab D-ND_LAB passano M1-M6:
  - meta-lab, physics, editorial, ops-decisions, finance
- Lab fisico MM_D-ND: aeternitas + nuovi 3 movement girano standalone OK
- D-ND_BOOK consistente
- MEMORY.md aggiornato con cristalli sessione
- Sistema snapshot riflette stato finale

Comandi finali:
```bash
for lab in meta-lab physics editorial ops-decisions finance; do
    python3 domains/meta-lab/tools/lab_template_validator.py domains/$lab
done

bash /opt/MM_D-ND/tools/test_cron_exact.sh  # check pre-cycle MM_D-ND

# verifica self-awareness funziona
bash /opt/D-ND_LAB/tools/dnd_lab_describe.sh finance
```

### Fase 4 — Lancio cycle finance

Solo quando Fase 1-3 completate.

```bash
bash /opt/D-ND_LAB/tools/dnd-cycle.sh finance
```

Pronostico esplicito:
- Tempo: 8-15 min (cycle data-centric, possibile shell_exec verso APIs
  no rete come da step 0)
- Provider: codex-cli primary, fallback claude-cli, fallback OR ($0.10-0.15)
- Falsifier coherent=True ~70% (post-affinamenti)
- Aeternitas PROCEED ~85%
- Veritas ρ 0.85-0.95 → SOSPENSIONE alta o COLLASSO
- Trajectory: REDESIGN "passare a yfinance live cycle 2"
- Promotion: 1-2 proposals se eligible

Post-cycle:
- Confronto pronostico vs realtà
- Cristallo cycle 1 finance + lessons learned
- Decisione: cycle 2 (dati reali) o consolidamento

## Criteri di completamento "atto risolutivo"

Il piano è completo quando:
1. Ogni atto A-H ha un commit
2. M1-M6 pass su tutti i 5 lab D-ND_LAB
3. Lab fisico MM_D-ND ha gli stessi 3 livelli observability del D-ND_LAB
4. dnd_lab_describe.sh produce output coerente per ogni lab
5. D-ND_BOOK ha voce data-centric
6. System snapshot consistente
7. Memoria operatore ha pickup post-compact aggiornato + cristallo
   atto risolutivo

Solo allora si lancia cycle 1 finance.

## Se emergono miglioramenti durante esecuzione

Direttiva operatore:
> "durante il lavoro naturalmente se emergono miglioramenti possibili
> li valutiamo"

Approccio: se durante atti A-H emerge un miglioramento non in piano,
- valuto leva vs costo
- se leva alta + costo basso (< 15 min) → faccio
- se leva alta + costo alto → segnalo, decidiamo
- se leva media/bassa → annoto in backlog, non eseguo

## Pickup post-compact

Se compact arriva durante esecuzione:
- File `session_pickup_post_compact_2026-05-05.md` (memoria operatore)
  ha lo stato della sessione mattutina + piano corrente
- Questo file (`docs/RISOLUTIVO_PRE_FINANCE_CYCLE.md`) ha il dettaglio
  operativo
- TodoWrite list ha lo stato in_progress dell'atto corrente
- Git log ha l'ultimo commit completato → riprendi dall'atto seguente
