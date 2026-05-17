# Meta-lab Skill Intent Guide

> Guida operativa per trasformare un intento di dominio in scelta di skill,
> meta-prompt, strumenti, null, baseline, assertion e UI contract.
>
> Stato: prima cristallizzazione, 2026-05-17.

## Scopo

Il meta-lab non deve scegliere skill per somiglianza verbale con il dominio.
Deve prima capire quale movimento deve poter compiere il Lab figlio, poi
attivare le skill e i meta-prompt che servono a rendere quel movimento
autonomo, falsificabile e osservabile.

La catena corretta e':

```text
intent -> movement_class -> use_dynamics -> skill_layers -> meta_prompts
-> generated_artifacts -> null/baseline/assertions -> ui_contract -> e2e
```

Se un passaggio manca, il Lab puo' sembrare installato ma non sa muoversi.

## Regola primaria

L'intento non e' una categoria di mercato o una feature. L'intento e' il
movimento che il sistema deve poter ripetere senza osservatore.

Esempi:

- "finanza" non e' un intento; "riconoscere quando un detector di regime non
  ha piu' potenza recuperabile prima che diventi decisione" e' un movimento.
- "ricerca aziendale" non e' un intento; "separare insight originale da eco
  dell'archivio e trasformare solo cio' che regge in prodotto" e' un movimento.
- "monitoraggio" non e' un intento; "vedere drift, bloccare azioni non
  ammissibili e proporre recovery ispezionabile" e' un movimento.

## Output obbligatorio della guida

Ogni generazione di Lab deve produrre, in `transduction.md` o nel report del
meta-lab, un blocco `skill_intent_map` con questa struttura logica:

```json
{
  "intent": "frase dell'operatore o dell'utente",
  "movement_class": "discovery|calibration|monitoring|decision|production|meta_generation|recovery",
  "use_dynamics": ["cosa deve fare il Lab nel ciclo"],
  "skill_layers": {
    "validation_layer": [],
    "processing_layer": [],
    "output_layer": [],
    "observation_layer": [],
    "interface_layer": [],
    "generation_layer": [],
    "domain_layer": [],
    "runtime_patterns": []
  },
  "meta_prompts": ["prompt operativi da iniettare nel context.md"],
  "generated_artifacts": ["file o moduli che devono nascere"],
  "null_baseline_requirements": ["controlli minimi prima di interpretare"],
  "ui_lens": ["moduli o viste che rendono visibile il movimento"],
  "exclusions": ["skill, metafore o pattern esclusi per contaminazione"]
}
```

Non e' necessario salvare letteralmente JSON se il report e' markdown, ma
tutti i campi devono essere presenti e ispezionabili.

## Classi di movimento

### 1. Discovery

Quando usarla: il dominio e' poco strutturato, i claim non sono ancora chiari
o il valore nasce dall'estrazione di tensioni.

Dinamica d'uso:

- leggere corpus e memoria;
- estrarre dipoli falsificabili;
- distinguere segnale, eco, bias e materiale non ancora usabile;
- generare primi osservabili e primo cimitero.

Skill tipiche:

- `observer`, `navigator`, `autoresearch`, `capture-insight`;
- `cec`, `autologica-operativa`, `consapevolezza-condensato`;
- `veritas-sys` se il dominio produce claim rischiosi o facilmente narrativi.

Meta-prompt:

```text
Trova il primo dipolo falsificabile del dominio. Non promuovere intuizioni.
Per ogni tensione dichiara cosa la renderebbe falsa, quale baseline povera la
batte e quale materiale non ha ancora leva.
```

Artefatti:

- `seed_tensions.json`;
- primo `context.md`;
- `cimitero.md`;
- tool esplorativo piccolo;
- vista UI Campo/Grafo per rendere visibili tensioni e residui.

### 2. Calibration

Quando usarla: il Lab possiede gia' un detector, metrica o famiglia di test,
ma deve capire se ha potenza reale o se sta inseguendo un artefatto.

Dinamica d'uso:

- confrontare metrica candidata contro null e baseline;
- isolare precondizioni del detector;
- fermare sweep ripetitivi quando non producono potenza;
- produrre vincoli decisionali, non solo punteggi.

Skill tipiche:

- `optimizer`, `logic`, `logic-engine`, `assertion-verifier`;
- `veritas-sys`, `kairos-sys`, `helix-sys`;
- `eval`, `cec`, `autologica-operativa`.

Meta-prompt:

```text
Dato un detector falsificato o debole, non aggiungere un altro strato
residuale. Identifica la precondizione mancante che deve reggere prima di
ogni aggregazione successiva. Disegna un esperimento che testa la
precondizione contro baseline e null espliciti.
```

Artefatti:

- `tools/exp_*.py` con output JSON o markdown leggibile;
- assertion numeriche;
- registro osservabili se ci sono 2+ script con metriche condivise;
- UI con `BaselineComparison`, `DataCard`, `DecisionBounds`.

### 3. Monitoring

Quando usarla: il valore e' osservare un sistema vivo, riconoscere drift,
rotture, accumuli o recovery.

Dinamica d'uso:

- raccogliere stato corrente;
- distinguere evento, drift, errore runtime e contaminazione;
- aprire alert solo se azionabili;
- produrre runtime awareness e punto di ripristino.

Skill tipiche:

- `system-check`, `audit-system`, `coherence-sys`, `triage-sys`;
- `memory-system`, `propagator`, `cascata`;
- `lazarus-sys` se serve recupero.

Meta-prompt:

```text
Osserva il sistema vivo prima di interpretare. Dichiara stato, side effect,
punto di rollback, cosa e' autorita' e cosa resta solo ispezionabile.
```

Artefatti:

- `runtime_monitor.json`;
- trace per ciclo;
- cron/on-demand runner;
- UI con stato, alert, azioni admin e cron visibility.

### 4. Decision

Quando usarla: il Lab deve aiutare a scegliere o a vietare azioni in un campo
complesso, senza fingere previsione totale.

Dinamica d'uso:

- trasformare ipotesi in vincoli;
- proiettare scenari;
- dichiarare cosa non e' ammissibile;
- separare raccomandazione, sospensione e veto.

Skill tipiche:

- `scenario-projector`, `triage-sys`, `veritas-sys`, `aeternitas-sys`;
- `conductor`, `semantic-orchestrator`;
- `metron-sys` per rimuovere output superfluo.

Meta-prompt:

```text
Non scegliere al posto dell'operatore. Riduci lo spazio delle azioni
ammissibili: cosa e' vietato, cosa resta sospeso, cosa ha evidenza
sufficiente e quale costo di errore stiamo accettando.
```

Artefatti:

- `decision_bounds.json`;
- `non_admissible.md`;
- scenario table;
- UI con vincoli, alternative e ragioni del blocco.

### 5. Production

Quando usarla: il Lab deve trasformare risultati maturi in paper, copy,
prodotto, demo o pacchetto riusabile.

Dinamica d'uso:

- filtrare cio' che e' pubblicabile;
- separare scoperta, claim, copy e applicazione;
- applicare gate di densita' e sicurezza;
- produrre artefatti senza perdere il tracciato del ciclo.

Skill tipiche:

- `scribe`, `metron-sys`, `publish-safe`, `non-dual-copy`;
- `publisher`, `siteman`, `paper-deployer` solo se aggiornato alla procedura
  corrente;
- `forgia`, `builder`, `architect` per pacchetti o UI.

Meta-prompt:

```text
Trasforma solo cio' che ha superato falsifier, baseline e runtime awareness.
Rendi distinguibili finding, claim, caveat e uso pubblico. Elimina tutto cio'
che aumenta superficie narrativa senza aumentare verifica.
```

Artefatti:

- pipeline SSP;
- product cards;
- public claim register;
- UI Prodotti con maturita', caveat e next verification.

### 6. Meta-generation

Quando usarla: il dominio richiesto non deve essere studiato direttamente,
ma convertito in un Lab autonomo installabile.

Dinamica d'uso:

- leggere richiesta e corpus;
- recuperare skill/enzimi;
- produrre transduzione;
- generare seme, context, tools, assertions, MML e UI contract;
- validare M1-M8 prima dell'installazione.

Skill tipiche:

- `genesis`, `factory`, `conductor`, `semantic-orchestrator`;
- `integrate-pattern`, `scenario-projector`;
- `consapevolezza-condensato`, `cascata`, `cec`, `eval`.

Meta-prompt:

```text
Genera il Lab, non il risultato del Lab. Conserva il contratto del movimento,
sostituisci materiale e osservabili, dichiara skill recuperate, esclusioni,
capacita' mancanti e test M1-M8.
```

Artefatti:

- `domain_request.v1`;
- `transduction.md`;
- `context.md`;
- `seed_tensions.json`;
- `mml.json`;
- `ui_contract.json`;
- `assertions.py`;
- `tools/`.

### 7. Recovery

Quando usarla: cicli ripetuti non avanzano, una regola locale e' diventata
vincolo sbagliato, il seme e' contaminato o il sistema deve ripartire da un
punto corretto.

Dinamica d'uso:

- identificare ultimo punto valido;
- separare runtime, seed, report e UI;
- decidere cosa decade e cosa va cristallizzato;
- proporre ripristino senza cancellare memoria del filtro.

Skill tipiche:

- `lazarus-sys`, `morpheus-sys`, `mnemos-sys`, `coherence-sys`;
- `audit-system`, `memory-system`, `autologica-operativa`;
- `aeternitas-sys` se il seme rischia modifica impropria.

Meta-prompt:

```text
Non correggere aggiungendo regole permanenti. Trova origine, valid_when,
retire_when e ultimo stato affidabile. Conserva nel cimitero cio' che deve
restare memoria del filtro.
```

Artefatti:

- recovery packet;
- snapshot restore;
- rule ledger con `origin`, `protects`, `valid_when`, `retire_when`;
- runtime report sul come e' avvenuta la rottura.

## Collegamento skill -> dinamica d'uso

Le skill vanno dichiarate nel MML solo se hanno una funzione nel ciclo.

| Bisogno del Lab | Layer | Skill candidate | Cosa produce |
|---|---|---|---|
| Validare realta' di un claim | validation | `veritas-sys`, `cec` | score, sospensione, veto semantico |
| Proteggere il seme | validation | `aeternitas-sys` | VETO/PROCEED su modifica |
| Iterare esperimento complesso | processing | `helix-sys`, `fractal-sys`, `optimizer` | piano, test, decomposizione |
| Decidere evoluzione del ciclo | processing | `kairos-sys`, `trajectory_evaluator` | NEXT/REDESIGN/CRYSTALLIZE |
| Cristallizzare memoria utile | processing | `mnemos-sys`, `memory-system` | cosa resta e cosa decade |
| Rendere leggibile l'output | output | `metron-sys`, `scribe`, `capture-insight` | densita', report, finding |
| Osservare coerenza del sistema | observation | `coherence-sys`, `audit-system` | drift, incoerenze, side effect |
| Assegnare priorita' | observation | `triage-sys` | impatto/costo/urgenza |
| Costruire un nuovo Lab | generation | `genesis`, `factory`, `forgia`, `architect` | seme, scaffold, agenti |
| Coordinare skill e interfacce | interface | `conductor`, `semantic-orchestrator`, `observer` | routing cognitivo |
| Far girare il Lab | runtime | `autonomous-cycle`, `cascata`, `propagator` | ciclo, cascade, sync |

Se una skill e' `VIVA-NO_EVAL`, `STUB` o `PERSONA-KERNEL`, il meta-lab puo'
dichiararla solo con nota di stato diagnostico e trigger esplicito. Dichiarare
una skill non equivale ad averla resa operativa.

## Pattern meta-prompt canonici

### intent_to_movement

```text
Riscrivi l'intento come movimento autonomo del Lab. Non usare il nome del
dominio come risposta. Specifica cosa deve poter cambiare stato, cosa puo'
falsificare il movimento e quale output sarebbe utile solo se sopravvive.
```

### skill_retrieval

```text
Cerca nel catalogo skill e nell'archivio enzimi quali capacita' sono gia'
presenti. Per ogni skill candidata dichiara layer, trigger, output atteso,
stato diagnostico e rischio di contaminazione. Se manca una capacita',
decidi se deve diventare tool, assertion, baseline, null o nuova skill.
```

### artifact_contract

```text
Trasforma il movimento in artefatti minimi: context, seed, tools, assertions,
mml, ui_contract, transduction. Ogni artefatto deve servire un passaggio del
ciclo e avere una verifica E2E.
```

### contamination_check

```text
Elenca cosa stai copiando dal Lab sorgente e rimuovi cio' che e' contenuto
di dominio. Conserva solo contratto del movimento, struttura di controllo,
runtime awareness e pattern di falsificazione.
```

### ui_movement_lens

```text
Progetta la UI come superficie del movimento. Sinistra: stato e campo.
Centro: vista primaria domain-native. Destra: dettaglio, trace, THIA e
azioni ammissibili. Ogni modulo deve ricevere dati reali dal ciclo o restare
esplicitamente vuoto.
```

### regressive_exposure_pass

```text
Prima di dichiarare il template pronto, torna indietro dalla UI e dagli
artefatti verso l'intento. Per ogni elemento esposto chiedi: quale intento
serve, quale movimento rende possibile, quale skill/meta-prompt lo ha
generato, quale regola o assioma lo protegge, quale null/baseline lo puo'
falsificare, quale evidenza E2E mostra che esiste nel Lab installato.
Se un elemento non risponde a questa catena, rimuovilo o mettilo in
missing_capabilities.
```

Questo passaggio e' autologica regressiva in forma operativa: non aggiunge una
nuova meta-lente, ma obbliga ogni superficie prodotta a esporre la propria
origine nel movimento.

## Esempio: finance corrente

Il finance lab attuale non e' piu' in puro discovery. Dopo i cicli recenti,
la classe dominante e':

```text
calibration + recovery leggero
```

Movimento:

```text
capire perche' i detector di regime producono purezza ma non potenza
recuperabile, prima di trasformarli in vincoli decisionali.
```

Skill da preferire:

- validation: `veritas-sys`, `cec`;
- processing: `optimizer`, `helix-sys`, `kairos-sys`;
- observation: `coherence-sys`, `audit-system`;
- runtime: `eval`, `autologica-operativa`, `cascata`;
- output: `metron-sys`, `capture-insight`.

Meta-prompt adatto:

```text
Non cercare un altro parametro del detector. Trova la precondizione che deve
essere vera prima che un detector di regime abbia potenza recuperabile.
Confronta target, baseline VaR/RV e null block-preserving senza introdurre
lookahead. Se la precondizione non regge, produrre NO_DELTA e vincolo di
ridisegno, non una nuova promessa.
```

UI lens:

- Regime Gate;
- Baseline / Null;
- Data-card;
- Non ammissibile;
- Cycle trace con durata, movement e skip/fail.

## Cosa manca ancora

Questa guida non sostituisce il generatore. Serve a impedire al generatore di
perdere logiche fini.

Stato operativo attuale:

- il meta-lab legge questa guida prima di generare nuovi domini;
- `tools/lab_template_generator.py` richiede `skill_intent_map_json`;
- il generator appende `skill_intent_map` a `transduction.md` se l'agent
  lo ha prodotto solo come JSON specs;
- il validator M8 controlla skill/enzyme retrieval, MML layered e
  `skill_intent_map`.
- `dndlab plan-domain` puo' raccogliere `movement_class`, `use_dynamics`,
  `exclusions` e `success_condition` per ridurre inferenza cieca nella fase
  meta-lab.

I prossimi passi naturali sono:

- usare il finance lab come primo caso valutativo della guida;
- aggiornare il seed autoinstallante quando la procedura regge in E2E.
