# Session brief — 2026-05-02 (giorno dopo SSP completo)

> Stato lasciato sera 01/05: pipeline SSP end-to-end automatica, 3 prodotti
> verificati (cycle 1256 finding #2 z=12,813, kernel +68.6pp vincitore),
> tab Prodotti + sidebar contestuale + chat consapevole live, 31 commit.

## Voci aperte in ordine di leva

### 1. Decisione operatore: use case applicativo del kernel
**Contesto**: il finding `z=12,813` ha 3 PoC PASS ma il kernel cognitivo
batte la library di un ordine di magnitudine (+68.6pp vs +7.2pp). Stage 5
packaging è automatizzabile MA serve scelta del use case concreto:
- "predittore prime-gap per ottimizzare wheel factorization in algoritmi crittografici"
- "guardrail anti-loop per LLM su sequenze ripetute"
- "compressor adattivo per sequenze numeriche con struttura Markov"
- altro

Senza scelta, Stage 5 può girare ma produce scaffold "agnostic use case"
che pubblicato fuori contesto è marketing vacuo. **Action operatore**:
quale dominio applicativo per il kernel?

### 2. Stage 5 — packaging automatico (~2-3h)
Quando #1 è chiaro:
- Nuovo `core/triggers/stage5_package.py`: dato product PASS + use_case,
  genera `setup.py`/`pyproject.toml` + README con esempi + tests
  derivati da `poc.py` + LICENSE + CHANGELOG. Via claude-cli OAuth.
- Scrive in `LAB_DATA_DIR/<domain>/prodotti/<id>/package/` standalone
- Operatore poi pubblica su PyPI (richiede credenziali, no automatizzato)

### 3. Provider chain — propagazione ai 3 punti pendenti
Pattern già rodato in `core/llm_adapter.py`. Replica meccanica:
- `MM_D-ND/tools/translate_tensions.py` (gemini-2.0-flash hardcoded → chain)
- `THIA/boot_kthia.js` (DEFAULT_MODEL claude-sonnet-4.6 → chain)
- `THIA/services/siteman_*.js` (intercettore parziale già presente, completare)

Tempo: ~30 min totali, basso rischio. Atti separati per repo.

### 4. Affinamento safety guard — Autologica Preventiva applicata
**Pattern strutturale 25 hit oggi**, tutti su azioni nel flusso atteso:
- 10 SERVICE_CONTROL su restart post-edit codice del servizio
  (`d-nd-lab-dashboard.service`) in DEMO_MODE
- 4 FILE_DELETE su scaffold rigenerabili (`data/<dom>/{scoperte,prodotti}/`)
  o `/tmp/*` consumed-and-throwaway
- altri assortiti

**Whitelist concrete** da proporre al guard config:
- path: `data/<dom>/{scoperte,soluzioni,prodotti}/`, `/tmp/*`
- service control: skip per `d-nd-lab-dashboard.service` quando i file
  modificati nella sessione corrente includono codice del servizio E
  `DASHBOARD_DEMO_MODE=true`

Atto perfetto per applicare la direttiva Autologica Preventiva
cristallizzata stamattina al guard stesso.

### 5. Validazione kernel-pattern su altri finding
Se +68.6pp si replica su altri finding eligible, il sistema sta dicendo
che ogni scoperta D-ND ha un kernel come forma applicativa primaria.
Vale la pena testare su 2-3 scoperte mature aggiuntive. Richiede:
- Cycle che producono `gate_status: mature_eligible` (non `transitional`/
  `pre_discovery`)
- Multi-candidate Stage 4 automatico (già wired dal commit 593eb5f)
- Confronto delta library vs kernel su N≥3 finding

Statistica spurio se N=1. Pattern strutturale se replica.

## Voci minori

- **Bot sito starter design** (TM1 territory) — direttiva starter
  4 voci uguali ovunque + auto-popup contestuale. Memo:
  `feedback_*/project_bot_sito_starter_design.md`
- **D-ND_LAB repo public/private** — decisione strategica differita.
  Memo: `project_dnd_lab_repo_public.md`
- **Third-act artifacts pendenti** — Q9/Q10 + editorial draft per d-nd.com:
  scrivere in `docs/THIRD_ACT_2026-05-01.md` per review TM1.

## Quick start mattina

1. `cd /opt/D-ND_LAB && git pull && git log --oneline -5`
2. `cat docs/SESSION_BRIEF_2026-05-02.md` (questo file)
3. `cat docs/changelog.json` per stato 01/05
4. Verifica cycle notturno automatico:
   `ls -lt data/physics/reports/agent_*.md | head` +
   `tail -1 data/physics/trajectory_log.jsonl | jq .decision`
5. Se nuovo cycle ha prodotto Stage 4: `curl :5050/api/domains/physics/prodotti | jq`
6. Decisione operatore su #1 → procedi con #2
7. Se #1 non pronto: parti dal pattern provider chain (#3)

## Risorse di ripresa

- Repo D-ND_LAB: github.com/GrazianoGuiducci/D-ND_LAB (privato per ora)
- Repo lab-d-nd-site: github.com/GrazianoGuiducci/lab-d-nd-site
- Dashboard: https://lab.d-nd.com/dashboard/
- Sito: https://lab.d-nd.com/
- Memorie locali: `/root/.claude/projects/-opt/memory/`
- Cristallizzazioni: `/opt/CLAUDE.md` + `/opt/MM_D-ND/KERNEL_SEED.md` +
  `/opt/d-nd-seed/kernels/axioms.md`
