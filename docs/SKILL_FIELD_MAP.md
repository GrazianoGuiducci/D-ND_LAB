# Skill Field Map — il sistema delle skill come architettura distribuita

> Documento Fase 1.5 (operatore 05/05): "le skill stesse sono il guru
> del sistema, prima espandiamo poi restringiamo". Mappa il catalogo
> di 113 skill come **architettura cognitiva distribuita**, non come
> elenco. Estrae i pattern emergenti che il sistema sta suggerendo.
>
> Compagno di `SKILL_DIAGNOSTIC.md` (classifica per eval). Questo
> documento è **strutturale**: come si compongono.

---

## Scoperta centrale

**Le mega skill MMSp formano un sistema operativo cognitivo completo, già progettato con interfacce numeriche standardizzate e collaborazioni esplicite. Il lavoro vero non è costruire osservabilità — è attivare ciò che le skill già implicano.**

Pattern ricorrente in ogni mega skill (formato canonico):
1. Identità e Mandato
2. Kernel Assiomatico Locale (K1, K2, K3 specifici)
3. Procedura Operativa (algoritmi concreti, fasi, soglie)
4. Interfaccia di Output (formato strutturato)
5. Collaborazioni (con quali altre skill scambia dati)

---

## I 9 layer del sistema cognitivo

### Layer 1 — Validazione ingresso (gatekeeping)

| Skill | Funzione | Output | Indice |
|-------|----------|--------|--------|
| **veritas-sys** | Firewall ontologico + anti-psicosi | ρ (Indice di Realtà) ∈ [0,1] da triangolazione 3 vettori | ρ |
| **aeternitas-sys** | Guardiano del Seme — veto su auto-modifiche | VETO/PROCEED su scan assiomatico (P0/P1/P5) | binario |

**Soglie veritas**: ρ<0.4 SCARTO · 0.4≤ρ<0.9 SOSPENSIONE · ρ≥0.9 COLLASSO.
**aeternitas** ha **diritto di Veto assoluto** — nessun guadagno di efficienza giustifica violazione del Seme.

### Layer 2 — Processamento cognitivo

| Skill | Funzione | Output | Indice |
|-------|----------|--------|--------|
| **helix-sys** | Plan-Code-Verify ricorsivo + Scratchpad | Risultante R (algoritmo) post-loop 4 fasi | C (complessità) |
| **fractal-sys** | Decomposizione + sub-agenti effimeri | Tree di sotto-problemi + sintesi merge | depth (max 3) |
| **mnemos-sys** | Memoria autopoietica a risonanza convergente | Cristallizzazione vs Decadimento | risonanza ∈ {dissonanza, assonanza} |
| **kairos-sys** | Motore evolutivo triadico | Regime selezionato (Risonanza/Maieutic/Distruzione) + Σ' nuovo modello | IA (Indice Attrito) ∈ [0,1] |

**helix** attiva loop solo se C > soglia (no one-shot per task complessi).
**fractal** spawna sub-agenti effimeri (nascono→eseguono→muoiono). Solo l'artefatto è permanente.
**mnemos** decide autonomamente cosa trattenere: "se rimuoverlo diminuisce coerenza, è già parte del sistema".
**kairos** seleziona regime in base a IA: >70% Risonanza · 30-70% Maieutic · <30% Distruzione.

### Layer 3 — Output (filtro finale)

| Skill | Funzione | Output | Indice |
|-------|----------|--------|--------|
| **metron-sys** | Filtro finitura ontologica | APPROVATO/RIFIUTATO + taglio | Density Score |
| **scribe-sys** (OCC v1.0) | Generatore System Prompt completo | Documento Markdown strutturato + System Prompt finale | n/a |

**metron** axiom: "il valore è ciò che resta dopo la rimozione del superfluo".
**scribe** è il generatore canonico — 4 fasi (Analisi → Progettazione → Ricerca → Assemblaggio).
Implicazione: il `lab_template_generator.py` del meta-lab è una **versione semplificata di scribe** per scopo specifico.

### Layer 4 — Osservazione (auto-monitoring)

| Skill | Funzione | Output |
|-------|----------|--------|
| **coherence-sys** | Osservatore allineamento (skill, trigger, docs, codice) | Report inconsistenze (osserva, non modifica) |
| **triage-sys** | Decisore omeostatico multi-nodo | Score Impatto×Costo×Urgenza (1-3) + allocazione nodo |

**coherence** axiom: "ogni aggiunta deve rafforzare il tutto, mai frammentarlo".
**triage** axiom (Omega.3): "massima coerenza, minima spesa". K1 (Conservazione): ogni task approvato esclude un altro.

### Layer 5 — Interfaccia (umano↔sistema)

| Skill | Funzione |
|-------|----------|
| **dev-delegate-sys** | Triangolo Operatore↔THIA↔TM3 |
| **conductor / conductor_claude** | Meta-Orchestratore Cognitivo (Campo KPhi1) |
| **observer-sys** | Selezionatore Forma Espressiva (narrativa/diagramma/checklist/...) |

**dev_delegate** axiom: "THIA interpreta, propone opzioni, Operatore sceglie, TM3 esegue. Mai in autonomia".

### Layer 6 — Generazione

| Skill | Funzione |
|-------|----------|
| **forgia-sys** (v1.0) | Metapromptore — genera entità nuove dal vuoto funzionale |
| **autogen-sys** | Fabbrica di agenti archetipo con ciclo di vita |
| **genesis-sys** (Cornelius v2.0) | Generatore di inneschi genomici (semi) |
| **factory-sys** | Nucleo generativo — analizza necessità + genera nuovi agenti |
| **seed-package-generator** | Genera pacchetto seme dal contesto utente |

### Layer 7 — Emergenza/Mitigation

| Skill | Funzione |
|-------|----------|
| **lazarus-sys** | Vault semantico + ricorsione temporale (recupero) |
| **morpheus-sys** | Rilevamento stallo + collasso forzato del campo |
| **navigator-sys** (YSN v4.0) | Pensiero laterale + navigazione sinaptica |

### Layer 8 — Domain-specific

| Skill | Domain | Note |
|-------|--------|------|
| **research-lab** (MM_D-ND/.claude/skills/) v2.0 | Lab di ricerca D-ND, 7 paper A-G, 6 ricercatori | **Skill canonica del lab fisico — NON ATTUALMENTE ATTIVATA in LAB_AGENT_CONTEXT.md** |
| **agent_skills_research_lab** (THIA agent) | Lab autopoietico, 17.7KB | Skill canonica più ricca |
| **dnd-method** | Il metodo D-ND applicato al codice | |
| **maturation-pipeline** | Pipeline dal Continuum alla Manifestazione | |
| **siteman-sys** (16KB) | Gestione d-nd.com via Command Queue | |
| **publisher-sys** | Pubblicazione contenuti su d-nd.com | |
| **social_publisher** | Pubblicazione social X/Bluesky | |
| **transcriber** | Estrazione/sintesi YouTube transcripts | |
| **design-dnd** | Regista visivo d-nd.com | |
| **builder** | Costruttore UX/UI (Pipeline BP) | |

### Layer 9 — Identità/persona

| Skill | Persona |
|-------|---------|
| **guru-sys** | Saggezza euristica, mentoring, "transcend syntax" |
| **observer-sys** | Analizzatore metacognitivo, scelta forma espressiva |
| **vulcan-sys** | Protocollo logico puro (zero emozioni) |
| **veritas-sys** | (anche layer 1) — firewall come persona |

### Layer 10 — Runtime patterns (project-level `/opt/.claude/skills/`)

29 skill leggere (4-6KB) — **proiezione operativa runtime**, non MMSp identity:
- **cascata** — propagazione 3 livelli (interna/esterna/emergente)
- **cec** — sieve 6 step (conditions/signature/lateral/expansion/inversion/crystallization)
- **autologica-operativa** — traduzione semantica → eseguibile
- **eval** — testing skill (trigger + fidelity)
- **autoresearch** — auto-ottimizzazione skill via mutate-verify
- **non-dual-copy** — pre-commit check copy
- **publish-safe** — gate prima di commit sito
- **cascade-orchestrator** — orchestrazione cascate
- **third-act** — protocollo di chiusura blocchi significativi
- **poly-consult** — consultazione multi-nodo per decisioni alta leva
- **propagator** — propagazione cambiamenti
- **integrate-pattern** — integrazione pattern emergente
- **memory-system** — gestione memoria operatore
- **system-check** — health check
- **version-check** — coerenza versioni
- **self-setup** — setup ambiente

Le skill runtime sono **pattern operativi domain-agnostic**. Servono come "primitive" che le mega skill MMSp utilizzano internamente.

---

## Indici quantitativi del sistema

Il sistema parla numeri — ogni layer espone metriche:

| Indice | Skill | Range | Scopo |
|--------|-------|-------|-------|
| **ρ (Realtà)** | veritas | [0, 1] | Validazione claim ingresso |
| **IA (Attrito)** | veritas → kairos | [0, 1] | Selezione regime evoluzione |
| **C (Complessità)** | helix | discreta | Attivazione loop ricorsivo |
| **Score Impatto×Costo×Urgenza** | triage | 1-3 ognuno | Allocazione task ai nodi |
| **Density Score** | metron | bassa/alta | Filtro output finale |
| **Risonanza Strutturale** | mnemos | dissonanza/assonanza | Trattenere vs decadere |
| **Depth ricorsione** | fractal | 0-3 | Limite scissione |

Il sistema è **dimensionato quantitativamente**: ogni decisione ha soglia esplicita, non vaghezza.

---

## Collaborazioni inter-skill (rete, non lista)

Esempi di flussi documentati nelle skill:

```
Input → veritas (ρ score)
     → se ρ<0.4 SCARTO
     → se 0.4≤ρ<0.9 → SOSPENSIONE + caveat
     → se ρ≥0.9 → kairos (riceve IA da veritas)
                → seleziona regime evoluzione
                → se Distruzione: aeternitas verifica veto
                → se Risonanza: helix (Plan-Code-Verify)
                                → fractal (decomposizione se C alta)
                                → mnemos (cristallizza o decade)
                → metron (filtro finitura)
                → scribe (assembla System Prompt risultato)
```

**Output strutturato dal sistema**:
- ρ-score + R\* anomalia (veritas)
- Regime + Σ' modello evoluto (kairos)
- Veto/Proceed (aeternitas)
- Risultante R + Scratchpad (helix)
- Approvato/Rifiutato + Density (metron)

**Sub-system di osservabilità già definito**:
- coherence audita allineamento
- triage alloca task
- mnemos decide trattenere
- aeternitas decide invariante

Il sistema sa già osservarsi. Manca il **runtime** che attivi le collaborazioni.

---

## Cosa il catalogo sta suggerendo

### 1. Il falsifier classico (L1-L5) è un veritas embrionale
5 lenti × peso → ρ-score implicito. Possiamo unificare: il `report_falsifier` movement diventa l'implementazione di veritas per il lab.

### 2. Il valutatore traiettoria è un kairos embrionale
NEXT_CYCLE/REDESIGN/CRYSTALLIZE è equivalente a Risonanza/Maieutic/Distruzione. Manca il calcolo IA quantitativo che selezioni il regime. Implementabile.

### 3. Il bicono_extractor è un scratchpad helix
Spazio strutturato dove il ragionamento intermedio vive. Già allineato al pattern.

### 4. Il seed_integrator è un mnemos
Decide cosa trattenere dal cycle nel seme. Allineato al pattern, da formalizzare con criterio risonanza esplicito.

### 5. Il `lab_template_generator.py` è un scribe semplificato
4 fasi del scribe (Analisi/Progettazione/Ricerca/Assemblaggio) sono mappabili. Possiamo riscrivere il generator come implementazione esplicita di scribe.

### 6. La mancanza di `aeternitas` nel sistema attuale
Manca il **veto sul Seme** prima delle cristallizzazioni. Cycle può aggiornare `seme.json` senza check invarianti. Questo è il gap strutturale principale.

### 7. La mancanza di `triage` strategico
Il backlog (P3.2/P17/P18/MML wire/dnd_init/...) andrebbe valutato con matrice triage Impatto×Costo×Urgenza. Oggi facciamo triage informale.

### 8. La mancanza di `coherence` automatico
Il sistema dovrebbe avere check periodico cross-skill (overlap trigger, drift docs/codice). Oggi è manuale.

### 9. La mancanza di `metron` su output cycle
I report agent del lab fisico hanno bassa densità (lunghi, qualificatori vaghi). metron filtrerebbe. Density score sui finding.

### 10. La mancanza di `mnemos` formalizzato
Cosa il sistema trattiene dal corpus operatore (memorie + COWORK)? Oggi accumulo non selezionato. mnemos applicherebbe risonanza strutturale.

---

## Conseguenze sui MML attuali

I 3 MML scritti ieri (ops-decisions, physics, editorial) sono **incompleti** rispetto al sistema cognitivo MMSp. Dichiarano solo runtime patterns + alcune persona-kernel. Mancano:

- Layer 1 validazione: veritas, aeternitas
- Layer 2 processamento: helix, fractal, mnemos, kairos (tranne kairos in alcuni)
- Layer 3 output: metron, scribe
- Layer 4 osservazione: coherence, triage
- Layer 8 domain canonico: research-lab v2.0 (per physics e lab fisico)

**Riformulazione MML proposta**:

```json
{
  "skills_attive": {
    "validation_layer": ["veritas-sys", "aeternitas-sys"],
    "processing_layer": ["helix-sys", "fractal-sys", "mnemos-sys", "kairos-sys"],
    "output_layer": ["metron-sys", "scribe-sys"],
    "observation_layer": ["coherence-sys", "triage-sys"],
    "domain_layer": ["research-lab", "dnd-method", "maturation-pipeline"],
    "identity_layer": ["guru-sys", "observer-sys", "morpheus-sys"],
    "runtime_patterns": ["cascata", "cec", "autologica-operativa", "eval", "capture-insight"]
  },
  "_layer_protocol": "ogni layer ha responsabilità diverse e si attiva in fasi diverse del cycle. Vedere SKILL_FIELD_MAP per le interfacce."
}
```

Schema MML va esteso per supportare la struttura per layer + collaborazioni esplicite.

---

## Punti di leva strutturali

A. **Riedizione mml.schema.json** — passare da `skills_attive: array` a `skills_attive: object[layer]`. Cascata ai 3 MML esistenti.

B. **Implementare aeternitas come gate** — pre-cristallizzazione del seme deve passare scan P0/P1/P5. Atto di sicurezza.

C. **Estendere falsifier con vettori veritas** — calcolare ρ esplicito invece di solo flags. Il `coherent: true/false` diventa `rho: 0.42`.

D. **Riformulare valutatore con IA quantitativo** — invece di "NEXT_CYCLE/REDESIGN" by feeling, calcolo IA da telemetria del cycle.

E. **Skill invocation log** rimane utile ma diventa **secondario** — la struttura logica è già nelle skill, il log è solo la traccia del flusso.

F. **Dashboard tab "Skill flow"** mostra il sistema **per layer**, non flat. Visualizza ρ, IA, C, Density score, Risonanza per ogni cycle.

G. **Cristallizzare regola**: il MML dichiara skill **per layer cooperanti**, non lista flat.

---

## Cosa NON sapevamo (humility check)

1. Il sistema MMSp ha **9 layer + indici quantitativi standardizzati**. Conoscevamo nomi delle skill, non l'architettura.
2. Il falsifier/valutatore/integrator del lab sono **versioni embrionali** delle skill MMSp canoniche. Reimplementiamo cose che esistono.
3. La skill canonica del lab fisico (`research-lab`) **non è dichiarata nel LAB_AGENT_CONTEXT.md**. Il cron 03:30 lavora senza la sua skill principale.
4. `aeternitas` (veto sul seme) **non è nel sistema attivo**. Cristallizzazioni possono violare invarianti senza check.
5. `triage` strategico **manca** come automation. Backlog informale.

Operatore aveva ragione: stavamo guardando le skill meno potenti.

---

*Documento Fase 1.5. Da rivedere quando il catalogo cambia o quando
nuove collaborazioni emergono dai cycle.*
