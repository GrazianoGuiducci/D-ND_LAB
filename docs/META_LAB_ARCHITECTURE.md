# Meta-lab Architecture & Implementation Plan

> Documento canonico di architettura del meta-lab e del sistema MML/skill.
> Prodotto come distillazione delle decisioni operatore + analisi delle
> repo lookalike (pi-mono, hermes-agent) + ispezione del territorio
> kernel/reference + runtime esistenti.
>
> **Audience**: TM3 / TM1 / operatore + qualsiasi runtime agent (codex,
> Hermes, opencode) che debba comprendere come il sistema si articola.
>
> **Stato**: cycle 2026-05-04, post Phase 1+1.5 del meta-lab (commit
> 3b42ba3 + 5c6e48e).

---

## 1. Territorio (verificato live, non mappa)

### 1.1 Identità del sistema

```
THIA (sistema, identità totale)
│
├── KTHIA (kernel attivo)
│   ├── boot_kthia.js                       (/opt/THIA/boot_kthia.js)
│   └── kernel/reference                    (/opt/MM_D-ND/kernel/reference/)
│       ├── MMSP1/                          ← Metamasterprompt v1
│       │   ├── MMS_Master.md               (Φ.1 — system prompt master)
│       │   ├── D-ND_PrimaryRules.md
│       │   ├── 00_Assioma_di_Invarianza_Ontologica.md
│       │   └── System_Prompt_*.md          (10 entità: Aethelred, Morpheus,
│       │                                    ALAN, SACS-PS, Halo Genoma,
│       │                                    PSW, OCC, AWO, COAC, ...)
│       ├── mini_MMSP1/                     (kernel condensati v1)
│       ├── Kernel_Semantico_Autopoietico_Reiterativo_KSAR.md
│       ├── skills/                         ← agent_skills_*.md (20)
│       ├── Memorie_del_Guru/
│       └── addestramento_mms_su_pf/
│
├── D-ND_LAB (sistema lab — motore + domini)
│   ├── core/                               ← invariante runtime-agnostic
│   │   ├── llm_adapter.py                  (provider chain: claude-cli,
│   │   │                                    codex-cli, openrouter HTTP)
│   │   ├── paths.py
│   │   ├── falsifier/                      (5 lenti L1-L5)
│   │   ├── triggers/                       (finding_promoter, ssp pipeline)
│   │   └── lab_pattern.md
│   ├── domains/
│   │   ├── physics/                        (lab di dominio)
│   │   ├── editorial/                      (lab di dominio)
│   │   └── meta-lab/                       (lab di funzione, NUOVO)
│   ├── dashboard/                          (UI FastAPI + Alpine.js)
│   └── tools/                              (manage scripts)
│
└── runtime agents (esterni, plug-in, agent-agnostic)
    ├── Claude Code (oggi)
    │   └── /opt/.claude/skills/            ← 29 skill installate
    ├── codex-cli (verificato)
    │   └── CODEX_HOME=/root/.codex_lab/    ← isolated auth
    ├── opencode / Hermes (futuro)
    └── THIA standalone (futuro)
```

### 1.2 Punto chiave architetturale

`/opt/.claude/skills/` **non è la sede delle skill del sistema**. È
l'installazione runtime per Claude Code. La sorgente vive in
`/opt/MM_D-ND/kernel/reference/skills/` (20 `agent_skills_*.md`).
Il sistema ha già la separazione kernel/runtime.

`core/llm_adapter.py` è già provider-agnostic: stesso codice gira con
claude-cli, codex-cli, OpenRouter HTTP, qualsiasi endpoint OpenAI-compat.
Il sistema è già pronto a essere usato da agent runtime diversi.

### 1.3 Cosa manca (gap diagnosis)

1. **Skill format standard portatile**. Le skill kernel
   (`agent_skills_*.md`) hanno format MMSp-like ricco. Le skill runtime
   `.claude/skills/` hanno YAML+body semplice. Hermes/agentskills.io
   converge su YAML+body. Manca un format canonico THIA + un loader
   che proietti dalla sorgente al runtime path.

2. **MML (Metamasterlab) per-lab non esiste**. I lab oggi non
   dichiarano esplicitamente quali skill usano. Le skill sono caricate
   globalmente dal runtime. Manca il livello "questo lab finance usa
   scenario-projector + cascata + autoresearch ma non youtube-transcript".

3. **Meta-lab esiste ma non genera MML**. Phase 1+1.5 produce config +
   context + about + seed_tensions + assertions. Non produce mml.json.
   Phase 2 estende il meta-lab per generare anche il MML del lab figlio.

4. **Niente skill loader cross-runtime**. Quando un nuovo runtime si
   attiva (codex, Hermes), bisogna tradurre le skill kernel nel format
   richiesto e installarle nel path che il runtime conosce.

---

## 2. Concetti — definizioni canoniche

### 2.1 KTHIA
Kernel attivo del sistema THIA. Contiene identità (chi è THIA), nucleo
assiomatico (modello D-ND), MMSp sorgente, KSAR, skill kernel, memorie
del guru. È invariante rispetto al runtime agent. Vive in
`/opt/MM_D-ND/kernel/reference/` + `/opt/THIA/boot_kthia.js`.

### 2.2 MMSp — Metamasterprompt
Sorgente delle entità prompt-system del sistema. Include:
- **MMS_Master** (Φ.1) — system prompt master assiomatico
- **D-ND_PrimaryRules** — regole primarie del modello
- 10 entità prompt-system named (Aethelred, Morpheus, ALAN, SACS-PS,
  Halo Genoma, PSW, OCC, AWO, COAC, ...)

Da MMSp derivano le mega skill (proiezione operativa delle entità in
skill invocabili).

### 2.3 Mega skill
Skill complesse derivate dal MMSp. Sorgente:
`/opt/MM_D-ND/kernel/reference/skills/agent_skills_*.md` (20 file).
Categorie inferite dai nomi:
- **Cognitive**: extractor, observer, navigator, harmonizer
- **Constructive**: architect, builder, factory, forgia, genesis
- **Orchestration**: conductor, matrix
- **Logic**: logic, logic-engine, daedalus, design-dnd
- **Output**: publisher
- **Optimization**: optimizer
- **Identity-projected**: morpheus, halo, guru

Skill runtime installate (Claude Code) sono trasformazioni semplificate
per uso CLI — sotto-insieme + format compatto YAML+body.

### 2.4 MML — Metamasterlab
Entità responsabile di un lab specifico. Per ogni lab di dominio
(physics, editorial, finance, biology, ...) e per il meta-lab stesso,
esiste un MML.

Compiti del MML:
- **Conosce il lab**: tensioni, cycle history, modus dominio, vincoli
  compute
- **Sceglie skill subset**: quali delle mega skill kernel sono pertinenti
  al dominio specifico
- **Materializza skill come tools a chiamata**: l'agent del cycle vede
  solo le skill che il MML ha attivato per quel lab
- **Orchestra cycle**: sostituisce/estende `dipartimento.py` come
  pattern formale per-dominio
- **Gestisce dipendenze runtime**: dichiara quale runtime agent il lab
  preferisce (claude-cli, codex-cli, OpenRouter), quali tools custom
  servono al dominio

File: `domains/<lab>/mml.json` — schema in §4.2.

### 2.5 Lab di dominio vs Lab di funzione
- **Lab di dominio**: produce findings sul materiale del dominio.
  Esempi: physics, editorial, finance, biology. Output: kernel/library/demo
  del dominio.
- **Lab di funzione**: produce strutture che servono il sistema.
  Unico esempio attuale: meta-lab. Output: template di lab + criteri
  di validità.

Il meta-lab è figlio di se stesso (può rigenerarsi). I lab di dominio
sono figli del meta-lab (o del template fisso D-ND_LAB se generati a
mano).

### 2.6 Runtime agent
Layer di esecuzione esterno al sistema. Plug-in. Agent-agnostic.

Modi di esecuzione:
1. **Embedded** in agent CLI esistente: Claude Code (oggi), codex-cli
   (verificato), opencode, Hermes (futuri)
2. **Standalone**: THIA con proprio LLM (API o locale)
3. **Service**: cliente paga subscription, sistema gira sul server
4. **Install**: cliente installa proprio THIA (clone repo + activate)

Il sistema è **già pronto** per tutti questi modi grazie a
`core/llm_adapter.py` provider-chain. Aggiunte richieste: skill loader
runtime-aware (§4.4).

---

## 3. Le 3 idee operatore — decisioni emerse

### 3.1 Idea hermes drug-discovery come pattern template

**Cosa portiamo**:
- Pattern "Quick Reference Table" (Task → API → Endpoint) nel MML
  del lab e nella tab Info dashboard
- API endpoints no-auth dichiarati nel `mml.json` come `external_apis`
  (es. lab biology: ChEMBL, PubChem, OpenFDA, OpenTargets)
- Reasoning Guidelines esplicite nel context.md del lab
- Workflow eseguibili inline (bash+python) come standard nei
  `tools/exp_*.py` generati dal meta-lab

**Cosa NON portiamo**:
- La struttura SKILL.md per ogni dominio (duplicherebbe il context.md
  del lab e i tools/exp_*.py)
- Il standard agentskills.io come format obbligatorio (lo seguiamo come
  compatibility, non come dipendenza)

### 3.2 Idea pi-mono come pattern di runtime

**Cosa portiamo**:
- Event-streaming pattern (`agent_start`, `turn_end`, `tool_execution`)
  come opzione futura per dashboard real-time

**Cosa NON portiamo**:
- Sostituzione del nostro `core/llm_adapter.py` (è già più ricco)
- Pi-mono non ha sistema skill — quello che noi abbiamo è già più
  evoluto (29 skill operative + 20 skill kernel sorgente + MMSp)

### 3.3 Idea MML — questa è la mossa centrale

**Decisione canonica**:
- Ogni lab di dominio acquisisce `mml.json` (schema §4.2)
- Il meta-lab estende il proprio output per generare anche il MML del
  lab figlio (Phase 2.A)
- Le skill restano in formato kernel (sorgente
  `agent_skills_*.md`) e in formato runtime semplificato per Claude
  Code o altri agent (skill loader runtime-aware §4.4)
- Il MML decide subset attivo, runtime decide format

---

## 4. Architettura proposta — definizioni operative

### 4.1 Skill format canonico THIA (proposta)

```yaml
---
# YAML frontmatter (compatibile agentskills.io + format esistente)
name: <slug>
description: <one-line>
version: 1.0.0
author: <author or "kernel">
license: MIT
metadata:
  thia:
    derived_from_mmsp: <entity name (Aethelred, Morpheus, ...) or null>
    kernel_ref: <path in /opt/MM_D-ND/kernel/reference/ if applicable>
    category: <cognitive|constructive|orchestration|logic|output|optimization|identity>
    domains_pertinence: [physics, editorial, finance, ...]
prerequisites:
  commands: [python3, curl, ...]
  python_packages: [numpy, scipy, ...]
external_apis:
  - name: <api>
    base_url: <url>
    auth_required: false
user-invocable: true
---

# Skill Title — Description

## Persona / Role
"You are ..."

## Core Workflows
... (bash + python inline come hermes pattern)

## Reasoning Guidelines
...

## Quick Reference Table
| Task | Endpoint | Notes |
| ...  | ...      | ...   |
```

Format unico. La differenza tra skill kernel (sorgente) e skill runtime
(installata) è SOLO il path di installazione + eventuale trim del body
per CLI compatto.

### 4.2 Schema mml.json

Vive in `domains/<lab>/mml.json`:

```json
{
  "$schema": "../../mml.schema.json",
  "lab": "physics",
  "version": "0.1.0-alpha",

  "identity": {
    "type": "domain | function",
    "level": "ground | meta | trans-meta",
    "responsibility": "Cosa fa questo lab — 1-2 frasi"
  },

  "kernel_refs": {
    "mmsp_entities": ["MMS_Master", "Aethelred_v3.1", ...],
    "kernel_files": [
      "kernel/reference/Kernel_Semantico_Autopoietico_Reiterativo_KSAR.md",
      "kernel/reference/MMSP1/D-ND_PrimaryRules.md"
    ]
  },

  "skills_attive": [
    {
      "name": "cascata",
      "source": "kernel/reference/skills/agent_skills_*.md or .claude/skills/cascata.md",
      "trigger": "after every significant modification",
      "rationale": "perché serve a questo lab"
    }
  ],

  "tools_custom": [
    {
      "name": "exp_two_layer_universality",
      "path": "tools/exp_two_layer_universality.py",
      "description": "..."
    }
  ],

  "external_apis": [
    {"name": "ChEMBL", "base_url": "...", "auth_required": false}
  ],

  "modus_invocation": {
    "cycle_pattern": "agent → bias_corrector → falsifier → SSP",
    "skill_invocation_strategy": "lazy (on-demand by agent) | eager (always loaded)",
    "fallback_provider_chain": ["codex-cli", "claude-cli", "openrouter"]
  },

  "conoscenza_lab": {
    "tensioni_attive_count": 8,
    "cycles_completed": 12,
    "last_finding": "...",
    "domain_specific_notes": "..."
  },

  "_generated_by": "meta-lab | manual | hand-edited",
  "_generated_at": "2026-05-04T12:00:00Z"
}
```

### 4.3 Skill loader runtime-aware

Nuovo modulo: `core/skill_loader.py`. Compiti:
1. Legge `mml.json` di un lab
2. Risolve path delle skill (sorgente kernel o `.claude/skills/`)
3. Adatta format al runtime target:
   - **Claude Code runtime**: copia/symlink in `.claude/skills/`
   - **Codex runtime**: usa `--add-dir` per esporre skill dir al sandbox
   - **THIA standalone**: registra skill in registry interno
4. Espone API: `load_skills_for_lab(lab_slug, runtime) -> list[Skill]`

Pattern speculare al `lab_template_generator.py` del meta-lab —
deterministico, fa I/O, l'intelligenza è nel MML.

### 4.4 Strategia distribuzione (3 modi)

**Modo 1 — install via curl|bash** (oggi, pattern hermes/pi):
```bash
curl -fsSL https://.../install.sh | bash
```
Clone D-ND_LAB + meta-lab + setup core. Primo `dnd init <slug>` invoca
meta-lab agent → produce template + MML → installa.

**Modo 2 — embedded in agent runtime**:
- Claude Code: già fatto, `.claude/` legge skill installate
- codex-cli: skill loader copia in `~/.codex/skills/` (path da definire)
  o usa `--add-dir`
- Hermes: skill loader esporta in format `agentskills.io` standard

**Modo 3 — THIA standalone**:
- App dedicata (futuro)
- Server FastAPI (`core/api.py` + `dashboard/`) già esiste
- LLM provider chain accetta API key proprie o LLM locale
  (`LLM_BASE_URL=http://localhost:11434/v1` per Ollama)

---

## 5. Piano di implementazione (steps numerate)

### Phase 2.A — MML + skill loader (PRIORITÀ ALTA)

**P2.A.1** Definire `mml.schema.json` formale nel root D-ND_LAB.

**P2.A.2** Categorizzare le 29 skill `.claude/skills/` + 20 skill kernel
`agent_skills_*.md` per categoria + dominio-pertinenza. Output:
`/opt/D-ND_LAB/docs/SKILL_CATALOG.md` (tabella).

**P2.A.3** Generare `mml.json` per i 3 lab esistenti:
- `domains/physics/mml.json`
- `domains/editorial/mml.json`
- `domains/meta-lab/mml.json`

(manuali, basati sul catalogo P2.A.2 + osservazione corrente lab)

**P2.A.4** Estendere `domains/meta-lab/context.md` per istruire la
generazione di mml.json nei lab figli (sezione "Output schema" → +
mml.json).

**P2.A.5** Estendere `lab_template_generator.py` per scrivere mml.json
e `lab_template_validator.py` per validarlo (M6 — MML coherence?).

**P2.A.6** Creare `core/skill_loader.py` minimale (lettura mml.json +
resolve path skill).

### Phase 2.B — Primo cycle vivo del meta-lab

**P2.B.1** Lanciare cycle del meta-lab con task = regenerate physics.
Comando:
```bash
DOMAIN=meta-lab CODEX_HOME=/root/.codex_lab \
  bash /opt/D-ND_LAB/run_full_cycle.sh
```

**P2.B.2** Confronto output del meta-lab vs `domains/physics/`
esistente. Diff strutturale + diff signature.

**P2.B.3** Verifica: il meta-lab produce anche `mml.json` valido per
physics? Se no, refactor context.md.

### Phase 2.C — Hermes pattern adoption

**P2.C.1** Aggiungere campo `external_apis` a `mml.json` schema.

**P2.C.2** Estendere il meta-lab context.md per istruire l'agent a
proporre `external_apis` no-auth quando il dominio target è
data-centric (es. biology → PubChem, finance → yfinance).

**P2.C.3** Nel template generato, aggiungere "Quick Reference Table"
nel `context.md` del lab figlio (pattern hermes adattato).

### Phase 3 — Onboarding generative (CLI + dashboard)

**P3.1** `tools/dnd_init.sh` — entry point CLI:
```bash
dnd init <slug> [--corpus <path>] [--runtime claude|codex|hermes]
```
Pattern: dialogo progressivo → meta-lab agent → validator → generator
→ primo cycle.

**P3.2** Dashboard tab "New domain" — UI generative web.

**P3.3** Sito pubblico `/lab/new` — futuro, dopo che il pattern locale
è stabile.

### Phase 4 — Multi-runtime support

**P4.1** Skill loader: format adapter per ogni runtime
(claude/codex/hermes/standalone).

**P4.2** Documentation: come integrare D-ND_LAB con codex/Hermes/altri.

**P4.3** App THIA standalone (futuro, dopo stabilizzazione).

---

## 6. Critical decisions log

**D1** (cycle 2026-05-04): Le skill `.claude/skills/` non sono la sede
del sistema — sono installazione runtime. La sorgente sta in
`kernel/reference/skills/`. Decisione operatore: il sistema deve
rimanere agent-runtime-agnostic.

**D2** (cycle 2026-05-04): Il MML è entità per-lab. Vive in
`domains/<lab>/mml.json`. Generato dal meta-lab (per lab futuri) o
manuale (per lab esistenti che riceveranno il file via Phase 2.A).

**D3** (cycle 2026-05-04): Format skill canonico è YAML frontmatter
+ body markdown, compatibile con agentskills.io ma esteso con campi
`metadata.thia.*` (derived_from_mmsp, kernel_ref, category,
domains_pertinence).

**D4** (cycle 2026-05-04): Distribuzione in 3 modi (curl|bash, embedded,
standalone). Tutti supportati dallo stesso core. App standalone è futura,
non blocca le prime 2 modalità.

**D5** (cycle 2026-05-04): Phase 2 procede prima del primo cycle vivo
del meta-lab. Il meta-lab ha bisogno di sapere che esiste il MML per
generarlo nei lab figli — context.md del meta-lab va esteso prima.

**D6** (cycle 2026-05-04 15:33): primo lab nato autonomamente dal meta-lab.
Cycle 11min 0-error ha generato `domains/ops-decisions/` (8 file + 2 tools
custom + MML completo, 10 skills attive 7 runtime + 3 kernel, 9 condensato
axioms proiettati). Falsifier meta TEMPLATE_VALID 6/6 PASS. Pattern Phase
2.A → 2.B validato end-to-end. A8 piena + A15 incarnati operativamente.
Commit `da487c9`. Le 5 cristallizzazioni emerse dal cycle (CORPUS_HAS_
AXIOMATIC_STRUCTURE, INCIDENT_CORPUS_TOO_SMALL, ...) sono state generate
dal seed_integrator del cycle stesso, non scritte a mano — il sistema
cristallizza la propria esperienza autonomamente.

**D7** (cycle 2026-05-04 18:30): gap diagnosticato — MML era costruito ma
non vivo a runtime. Phase 2.A.7 (wire MML → agent) era implicita, saltata
in fretta per validare end-to-end con 2.B. Ora chiusa esplicitamente.

Diagnosi: dopo cycle 1608 di ops-decisions, falsifier ha colpito 4 flag
(L5 prior art, L2 ratio ungrounded, L2 chi-square null, L3 F2 collision).
Ispezione `core/agent.py` ha rivelato che il system_prompt era costruito
solo da `context.md + agent_field_live.md` — `mml.json` mai letto,
`skill_loader.load_skills_for_lab` mai invocato. Le 10 skill attive
dichiarate nel MML di ops-decisions non erano viste dall'agent. I 2 tools
custom erano dichiarati nel `config.json` con path Posix
('tools/exp_*.py') ma `agent.py:83` li passava a `import_module` — che
vuole dotted name, non path. Doppio gap: skill non attive + tool non
invocabili come MCP.

Fix (commit `ed51b8b`):
- `core/agent.py` aggiunto `_build_mml_section(domain)` che legge MML
  via `skill_loader` e renderizza sezione testuale "Skills attive +
  Tools custom" iniettata nel `system_prompt` prima di field_live.
- Skills: nome + trigger + rationale + path source per ognuna.
- Tools custom: path completo + comando `python3 <full_path>`.
  Surfaced come shell-invocable, non MCP — l'agent li chiama via
  `shell_exec` quando serve evidenza eseguita anziché discorso.
- Path resolution: se `module` ha '/' o `.py`, è standalone — log
  info, skip import. Solo dotted names tentano `import_module + build`.
- MML mancante = silent fallback (lab pre-2.A.7 invariati).

Pattern: Auto-Learn applicato — detect (warning) → diagnose (codice)
→ fix structurally (wire) → verify (live test) → propagate (questo D7
+ D-ND_BOOK §III + cristallizzazione memoria + cascata su lab futuri).

Cascata: ogni lab futuro nato dal meta-lab avrà MML attivo dal primo
cycle. ops-decisions cycle 2 (lanciato 18:33) è il primo test reale.

---

## 7. Cosa NON facciamo (scope limit)

- **Non riscriviamo il MMSp**: è kernel storico, lo riferenziamo
- **Non duplichiamo le skill** in formati multipli simultanei: format
  unico canonico + adapter al loader
- **Non costringiamo** a Claude Code / codex / Hermes: agent-agnostic
- **Non promettiamo** app standalone in Phase 2-3: futuro coerente,
  non blocca presente

---

*Documento autoritativo. Aggiornato a ogni cycle del meta-lab che porta
nuove cristallizzazioni. Versione corrente: 1.0 (2026-05-04 post-meta-lab
Phase 1+1.5).*
