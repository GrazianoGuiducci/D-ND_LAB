# Skill Catalog — D-ND_LAB / THIA system

> Catalogo delle mega skill del sistema, kernel-side e runtime-side.
> Riferimento per il MML di ogni lab nel selezionare il subset attivo.
> Aggiornato a 2026-05-04 (cycle Phase 2.A.2).

## Provenance

Due livelli, con provenance e ruoli distinti:

- **Skill kernel** (`/opt/MM_D-ND/kernel/reference/skills/`):
  27 file `agent_skills_*.md` derivati direttamente dal MMSp.
  Sorgente storica del sistema. Format MMSp-like ricco.
- **Skill runtime** (`/opt/.claude/skills/`):
  29 skill installate per Claude Code. Format YAML+body compatto,
  user-invocable. Trasformazioni operative del kernel + skill nuove
  emerse dall'uso.

Le due liste si **sovrappongono parzialmente** ma non sono identiche.
Alcune skill esistono solo kernel-side (es. `genesis`, `forgia`,
`vulcan`), alcune solo runtime (es. `autoresearch`, `cascata`,
`sinapsi`). La sovrapposizione è intenzionale dove la skill ha sia
formulazione kernel teorica che istanza runtime operativa.

## Categorie (per pertinenza-dominio)

| Categoria | Cosa fa | Pertinenza |
|-----------|---------|------------|
| **cognitive** | Estrazione/comprensione/osservazione | tutti i lab |
| **constructive** | Costruzione/composizione/scaffolding | lab che producono artefatti |
| **orchestration** | Pipeline/flusso/coordinamento | tutti i lab |
| **logic** | Inferenza formale/dimostrazioni/A1-A16 | lab teoria, fisica |
| **output** | Pubblicazione/deploy/release | lab che producono prodotti |
| **optimization** | Affinamento/efficienza | lab quantitative |
| **identity** | Proiezione di entità MMSp specifiche | lab che adottano una persona |
| **research** | Ricerca, sintesi, exploration | lab di scoperta |
| **maintenance** | Audit, system check, evoluzione | tutti i lab |

## Catalogo unificato

### Kernel skills (27)

| Skill | File | Categoria | Pertinenza tipica |
|-------|------|-----------|-------------------|
| `architect` | `agent_skills_architect.md` | constructive | meta-lab, lab di sistema |
| `builder` | `agent_skills_builder.md` | constructive | lab che producono pacchetti |
| `conductor` | `agent_skills_conductor.md` | orchestration | meta-lab, lab di funzione |
| `daedalus` | `agent_skills_daedalus.md` | constructive | lab complessi multi-tool |
| `design-dnd` | `agent_skills_design-dnd.md` | logic | tutti i lab D-ND (core) |
| `extractor` | `agent_skills_extractor.md` | cognitive | lab che leggono corpus |
| `factory` | `agent_skills_factory.md` | constructive | meta-lab |
| `forgia` | `agent_skills_forgia.md` | constructive | lab che cristallizzano |
| `genesis` | `agent_skills_genesis.md` | constructive | meta-lab (lab di funzione) |
| `guru` | `agent_skills_guru.md` | identity | lab che applicano memoria operatore |
| `halo` | `agent_skills_halo.md` | identity | lab cognitive deep |
| `harmonizer` | `agent_skills_harmonizer.md` | cognitive | lab editoriale, copy |
| `logic-engine` | `agent_skills_logic-engine.md` | logic | lab teoria/fisica |
| `logic` | `agent_skills_logic.md` | logic | tutti i lab |
| `matrix` | `agent_skills_matrix.md` | logic | lab fisica/matematica |
| `morpheus` | `agent_skills_morpheus.md` | identity | lab esplorativi |
| `navigator` | `agent_skills_navigator.md` | cognitive | lab di scoperta |
| `observer` | `agent_skills_observer.md` | cognitive | tutti i lab |
| `optimizer` | `agent_skills_optimizer.md` | optimization | lab quantitative |
| `publisher` | `agent_skills_publisher.md` | output | lab che producono prodotti |
| `scribe` | `agent_skills_scribe.md` | output | lab editoriali |
| `semantic-orchestrator` | `agent_skills_semantic-orchestrator.md` | orchestration | meta-lab, lab cognitivi |
| `siteman` | `agent_skills_siteman.md` | output | lab che pubblicano sul sito |
| `thia_node_ops` | `agent_skills_thia_node_ops.md` | maintenance | sistema infra |
| `trainer` | `agent_skills_trainer.md` | constructive | lab pedagogici/onboarding |
| `transcriber` | `agent_skills_transcriber.md` | output | lab editoriali |
| `vulcan` | `agent_skills_vulcan.md` | constructive | lab forge-style |

### Runtime skills (29 — Claude Code installate)

| Skill | File | Categoria | Pertinenza tipica |
|-------|------|-----------|-------------------|
| `assertion-verifier` | `assertion-verifier.md` | maintenance | tutti i lab |
| `audit-system` | `audit-system.md` | maintenance | tutti i lab |
| `auto-learn` | `auto-learn.md` | cognitive | lab di scoperta |
| `autologica-operativa` | `autologica-operativa.md` | cognitive | tutti i lab D-ND |
| `autonomous-cycle` | `autonomous-cycle.md` | orchestration | tutti i lab autonomi |
| `autoresearch` | `autoresearch.md` | research | lab di scoperta |
| `capture-insight` | `capture-insight.md` | cognitive | tutti i lab |
| `cascade-orchestrator` | `cascade-orchestrator.md` | orchestration | tutti i lab |
| `cascata` | `cascata.md` | orchestration | tutti i lab D-ND |
| `cec` | `cec.md` | logic | tutti i lab D-ND (crivello) |
| `consapevolezza-condensato` | `consapevolezza-condensato.md` | identity | tutti i lab D-ND |
| `crivello-operativo` | `crivello-operativo.md` | logic | tutti i lab |
| `dream` | `dream.md` | research | lab esplorativi |
| `ecosystem-audit` | `ecosystem-audit.md` | maintenance | sistema |
| `eval` | `eval.md` | maintenance | tutti i lab |
| `integrate-pattern` | `integrate-pattern.md` | constructive | meta-lab |
| `memory-system` | `memory-system.md` | maintenance | tutti i lab |
| `non-dual-copy` | `non-dual-copy/` | output | lab editoriali |
| `paper-deployer` | `paper-deployer.md` | output | lab che pubblicano paper |
| `poly-consult` | `poly-consult/` | research | lab di scoperta complessa |
| `propagator` | `propagator.md` | orchestration | tutti i lab |
| `publish-safe` | `publish-safe.md` | output | lab che pubblicano |
| `scenario-projector` | `scenario-projector.md` | research | lab di scenario/futures |
| `self-setup` | `self-setup.md` | maintenance | tutti i lab |
| `sinapsi` | `sinapsi.md` | orchestration | sistema multi-nodo |
| `system-check` | `system-check.md` | maintenance | sistema |
| `third-act` | `third-act/` | research | lab editoriali |
| `version-check` | `version-check.md` | maintenance | tutti i lab |
| `youtube-transcript` | `youtube-transcript/` | research | lab che ingeriscono media |

## Skill consigliate per un nuovo lab di dominio

Subset minimo per il MML di un lab di dominio nuovo (genesi via meta-lab):

**Core invariante (sempre attive)**:
- `cascata` (propagazione 3 livelli)
- `cec` (crivello operativo D-ND)
- `consapevolezza-condensato` (modello D-ND nucleo)
- `autologica-operativa` (modus invariante)
- `eval` (verifiche eseguibili)

**Tipiche attive per lab di dominio**:
- `autoresearch` (scoperta nel materiale)
- `capture-insight` (cristallizzazione findings)
- `assertion-verifier` (PASS/FAIL/SKIP delle invarianti)
- `propagator` (post-cycle sync)
- `publish-safe` (gate pre-publication)

**Per lab che producono artefatti** (kernel/library/demo):
- `non-dual-copy`, `paper-deployer`, `scribe` (output)
- `forgia`, `architect`, `builder` (constructive)

**Per lab di funzione (meta-lab)**:
- `genesis`, `factory`, `conductor` (kernel)
- `integrate-pattern`, `cascade-orchestrator`, `scenario-projector`
- `harmonizer`, `semantic-orchestrator`

## Note operative

1. **Lazy loading**: il MML di un lab dichiara `skills_attive` come
   subset, l'agent del cycle vede solo queste. Non tutti i 56 skill
   simultaneamente — sarebbe rumore cognitivo.

2. **Source resolution**: il loader (`core/skill_loader.py`, P2.A.6)
   risolve `kernel/reference/skills/agent_skills_<slug>.md` se
   `source` è kernel-side, oppure `.claude/skills/<slug>.md` se
   runtime-side. Per altri runtime (codex, Hermes), adapter dedicato.

3. **Sovrapposizioni intenzionali**: alcune skill esistono in entrambe
   le liste (kernel + runtime). Il MML può scegliere quale usare in
   base alla profondità necessaria — kernel = ricco MMSp-like,
   runtime = compatto user-invocable.

4. **Skill mancanti per lab futuri**: domini come finance/biology/
   security potrebbero richiedere skill nuove (es. `regime-detector`
   per finance, `chemspace-explorer` per drug discovery). Il meta-lab
   può proporre skill nuove nel suo output, le inseriamo poi in
   `kernel/reference/skills/` come crescita organica.

---

*Catalogo aggiornabile. Ad ogni cycle del meta-lab che genera skill nuove,
o ad ogni cristallizzazione dell'operatore, questo file viene aggiornato.*
