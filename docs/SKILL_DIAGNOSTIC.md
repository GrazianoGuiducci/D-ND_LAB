# Skill Diagnostic — Cosa producono davvero le skill?

> Documento canonico Fase 1 del piano "struttura logica osservabile per il
> flusso skill" (operatore 05/05). Prima di iniettare skill nel MML del
> lab fisico (porting Phase 2.A.7 a MM_D-ND), verifichiamo cosa ognuna
> produce, se ha eval, se è osservabile.
>
> Scope: 14 skill candidate per i MML attivi (5 core + 5 domain + 4 NO_EVAL
> dal SkillHealthCheck) + 3 kernel skills (guru/observer/forgia).
>
> Generato: 2026-05-05 mattina. Da rivedere quando il catalogo skill cambia.

---

## Classificazione operativa

5 categorie:

- **VIVA** — body operativo + eval completo (Trigger Tests + Fidelity Tests). Eligibile per MML wire immediato.
- **VIVA-NO_EVAL** — body operativo, output osservabile, ma manca sezione `## Eval`. Eligibile dopo eval gap closing.
- **STUB** — sezione `## Eval` presente ma generica/placeholder ("Appropriate prompts → activates"). Eligibile dopo eval refactor.
- **OBSOLETO** — pattern non più valido nel sistema attuale. Da riclassificare o rimuovere.
- **PERSONA-KERNEL** — kernel skill che proietta identità/voce, non procedura immediata. Eligibile con flag esplicito nel MML.

---

## Tabella di classificazione

| Skill | Sorgente | Eval | Output osservabile | Trigger univoco | Classifica |
|-------|----------|------|--------------------|-----------------|------------|
| **cascata** | runtime | ✓ Completo | Checklist 3 livelli (interna/esterna/emergente) | "cascata", "propaga", new function, CLAUDE.md mod | **VIVA** |
| **cec** | runtime | ✓ Completo | 6-step sieve verdict | "evaluate claim", "found a video", "change architecture" | **VIVA** |
| **autologica-operativa** | runtime | ✓ Completo | Regola eseguibile da correzione operatore | "autologica", correction, blocco, "che domanda" | **VIVA** |
| **eval** | runtime | ✓ Completo | X/Y Trigger + Fidelity per ogni skill | "test my skills", "run eval", "skill health" | **VIVA** |
| **autoresearch** | runtime | ✓ Completo | Baseline → mutation → re-eval report | "optimize", "skill X failing", "improve accuracy" | **VIVA** |
| **consapevolezza-condensato** | runtime | ✗ NO_EVAL | 3-6 righe verdict (procedi/riformula/fermati) | Body-only: pre/post-action, dubbio metodologico | **VIVA-NO_EVAL** |
| **audit-system** | runtime | ✗ NO_EVAL | Markdown table cross-repo | Body-only: audit cross-repo richiesto | **VIVA-NO_EVAL** |
| **scenario-projector** | runtime | ✗ NO_EVAL | 4 lenses + verdict per tensione | Body-only: 5+ tensioni decisione strategica | **VIVA-NO_EVAL** |
| **youtube-transcript** | runtime | ✗ NO_EVAL | JSON + transcript text | Body-only: URL YouTube + richiesta su contenuto | **VIVA-NO_EVAL** |
| **capture-insight** | runtime | ⚠ Stub | Note 2-3 lines + routing | "Appropriate prompts" (placeholder) | **STUB** |
| **assertion-verifier** | runtime | ⚠ Stub | PASS/FAIL/SKIP per assertion | "Appropriate prompts" (placeholder) | **STUB** |
| **paper-deployer** | runtime | ⚠ Stub | Deploy report | "Appropriate prompts" + pattern OBSOLETO (CMS API authority dal 22/04) | **OBSOLETO + STUB** |
| **guru** (kernel) | kernel | n/a (formato kernel) | Persona "Mentore" + output filosofico | array YAML: insegna, spiega, come funziona, tutorial | **PERSONA-KERNEL** |
| **observer** (kernel) | kernel | n/a (formato kernel) | Persona "Analizzatore metacognitivo" + scelta forma espressiva | array YAML: osserva, monitora, controlla, verifica stato | **PERSONA-KERNEL** |
| **forgia** (kernel) | kernel | n/a (formato kernel) | Persona "Metapromptore" + entità nuove | array YAML: forgia, crea agente, genera skill, nuova entità | **PERSONA-KERNEL** |

---

## Distribuzione

| Classifica | Count | % |
|------------|-------|---|
| VIVA | 5 | 36% |
| VIVA-NO_EVAL | 4 | 29% |
| STUB | 2 | 14% |
| OBSOLETO | 1 | 7% |
| PERSONA-KERNEL | 3 | 21% (kernel) |
| **Totale** | 14 | 100% |

Skill **immediatamente eligible** per MML wire = 5 (36%). Le altre richiedono lavoro preventivo.

---

## Gap rilevati

### 1. NO_EVAL (4 skill)

Lo Skill Health Check al boot lo segnala ogni sessione. Skill interessate:
- **`consapevolezza-condensato`** ← skill core invariant del modello D-ND. Filtro centrale per atti sistemici. Senza eval non possiamo verificare:
  - Quando l'agent dovrebbe attivarla (passo pre/post azione vs typo)
  - Se l'output rispetta il formato 3-6 righe richiesto
  - Se ha effettivamente letto il distillato (passo 2)
- **`audit-system`** — utility cross-repo. Eval banale da scrivere.
- **`scenario-projector`** — usata da `dnd_scenario.py` cron. Eval può testare le 4 lenses verdicts.
- **`youtube-transcript`** — utility skill. Eval può testare URL parsing.

Eval gap closing è atto Auto, ~30-60 min totali per le 4.

### 2. STUB eval generico (2 skill)

`capture-insight` e `assertion-verifier` hanno sezione `## Eval` ma con placeholder:
```
## Trigger Tests
# Appropriate prompts for this skill -> activates
# Unrelated prompts -> does NOT activate

## Fidelity Tests
# Given valid input: produces expected output
# Given edge case: handles gracefully
# Always reports what was done
```

Tecnicamente il SkillHealthCheck non li flagga perché c'è la sezione, ma sono **non testabili**. Da riscrivere con trigger ed esempi concreti.

### 3. OBSOLETO

`paper-deployer` segue il vecchio pattern direct ssh+scp+update pages.json. Ma dal 22/04 l'autorità del content sito è il **Siteman CMS API** (memoria `feedback_protocollo_content_cms_authority`). Il pattern paper-deployer va o riscritto via CMS API o riclassificato come "ref doc per emergency manual deploy" — non come skill agent-attiva.

### 4. PERSONA-KERNEL ≠ skill operativa

`guru`/`observer`/`forgia` sono kernel skills MMSp-derived. Proiettano **identità**, non eseguono procedura immediata. Quando il MML le dichiara come "skills_attive", l'agent attiva una persona, non un operatore. Nel MML serve flag distintivo (es. `category: "identity"` vs `category: "procedural"`) per non confonderli con skill come cascata/cec.

---

## Conseguenze sui MML attuali

### MML ops-decisions (cycle 1608, 1833, 1942)

Dichiara 13 skill (10 runtime + 3 kernel). Stato post-diagnostica:

| Skill nel MML | Classifica | Effetto reale al cycle |
|---------------|-----------|------------------------|
| consapevolezza-condensato | VIVA-NO_EVAL | Body letto, eval mancante — l'agent non sa se il body è applicato correttamente |
| cascata | VIVA | Effetto verificabile via eval |
| cec | VIVA | Effetto verificabile |
| autologica-operativa | VIVA | Effetto verificabile |
| eval | VIVA | Effetto verificabile |
| capture-insight | STUB | Effetto incerto (eval generico) |
| auto-learn | (non analizzato qui) | da verificare |
| guru | PERSONA-KERNEL | Proietta identità, non esegue procedura |
| observer | PERSONA-KERNEL | Idem |
| forgia | PERSONA-KERNEL | Idem |

Cycle 2 ops-decisions (1833) ha avuto **0 falsifier flags** — risultato strutturalmente buono. Cycle 3 (DSV4 1942) ha avuto **3 flags** — ma su modello diverso (deepseek-v4-pro più severo). Difficile attribuire il delta a singole skill senza osservabilità.

### MML physics + editorial (retrofit 04/05)

12-13 skill ognuno. Stesso pattern. Stesso problema osservabilità.

---

## Punti di leva

### A. Eval gap closing (FASE 3)
4 skill NO_EVAL → scrivere eval. ~30-60 min. Atto Auto.

### B. Stub refactor (FASE 3 estesa)
2 skill STUB → riscrivere eval con trigger concreti. ~30 min.

### C. Skill invocation log (FASE 2)
File `data/skill_invocations.jsonl` con append per ogni invocazione:
```json
{"ts": "20260505_0635", "cycle_ts": "20260505_0330", "domain": "physics",
 "skill": "cec", "trigger_text": "...", "output_summary": "...", "verifiable": true}
```
Aggregator giornaliero → conteggio invocazioni per skill, frequenza fuso, skill morte (mai invocate). Permette in 7 giorni di vedere il flusso reale.

### D. Dashboard tab "Skill flow" (FASE 2 estesa)
UI che legge skill_invocations.jsonl + diagnostico, mostra:
- Skill viva (verde) / NO_EVAL (giallo) / morta (grigio)
- Heat map invocazioni per skill × cycle
- Drill-down per skill: ultimo output, eval pass rate, esempi

### E. MML attribute `_diagnostic_status`
Per ogni skill nel MML, aggiungere campo opzionale:
```json
{
  "name": "consapevolezza-condensato",
  "_diagnostic_status": "viva-no_eval",
  "rationale": "..."
}
```
Trasparenza: il MML dichiara fede nel body, segnala eval gap. Quando eval scritto → status updated a "viva".

---

## Decisioni proposte

1. **Bloccare il porting MM_D-ND MML wire finché non chiusa Fase 3** sulle skill core (cascata, cec, consapevolezza-condensato, autologica-operativa, eval). 4/5 sono VIVA, solo consapevolezza-condensato manca eval. Eval da scrivere → ~15 min.

2. **Riscrivere `paper-deployer`** o riclassificare come "ref doc". Atto Approve.

3. **Costruire skill invocation log** come MVP osservabilità. Atto Auto, ~1h. Dashboard tab successivo (Approve).

4. **Cristallizzare regola**: il MML dichiara solo skill con eval verificato. Skill VIVA-NO_EVAL diventano dichiarabili dopo che ottengono eval. Skill STUB richiedono refactor eval prima.

5. **Memoria operatore**: cristallizzare gap diagnostico come pattern strutturale ("dichiarare ≠ verificare attivamente").

---

*Documento autoritativo Fase 1. Aggiornare quando il catalogo skill cambia.*
