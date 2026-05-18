# Meta-lab Capability Stack

> Uso controllato dei metaprompt storici/MMSp e degli input esterni revisionati
> come banca di capacita' per generare nuovi Lab D-ND.

## Scopo

Il meta-lab non deve installare ogni logica come Lab figlio. Deve riconoscere
quale capacita' serve al movimento del dominio e trasformarla in contratto
verificabile:

```text
possibilita' cognitiva -> trigger -> contratto -> artefatto -> test -> UI lens
```

Prima di scegliere quale capacita' metabolizzare, applicare
`docs/POSSIBILITY_FIELD_REGISTRY.md`: il ciclo deve ricevere il campo delle
possibilita' disponibili da skill, MMSp, capsule, Lab sorgenti, preset e
superfici pubbliche. Quando una capacita' emerge da un ciclo vivo, applicare anche
`docs/LAB_THOUGHT_AND_CAPABILITY_CASCADE.md`: la capacita' deve dichiarare
quale domanda apre, quali nodi mancanti rende visibili, dove potrebbe
propagarsi e cosa non puo' essere trasferito senza contaminazione.

Questo documento persiste la decisione operativa nata dall'intake del
pacchetto GPT PRO in `/opt/tm7/inbox/operator_inputs/2026-05-17/metaprompt_gpt`.
Il pacchetto e' utile come mappa di possibilita', non come autorita'. Prima di
canonizzare una capacita' bisogna leggere il source body reale o una capsula
portabile gia' verificata.

## Bordo Di Autorita'

Il materiale GPT PRO e' classificato come `external_input`.

Puo' orientare:

- la scelta delle capacita' del meta-lab;
- il piano di lettura degli archivi cognitivi;
- il confronto tra candidate architecture;
- la scrittura di `skill_intent_map`, `archive_retrieval` e `transduction.md`.

Non puo' da solo:

- installare Lab figli;
- diventare regola canonica;
- entrare come prova in assertions;
- copiare prompt storici nel context di un Lab;
- sostituire la lettura dei source reali quando una capacita' modifica file,
  strumenti, MML, UI o regole di ciclo.

## Stack Minimo Per Generare Un Nuovo Lab

Questo e' lo stack raccomandato quando l'intento non e' ancora strutturato:

```text
domain_request
  -> possibility-inventory
  -> lab-thought-pass
  -> semantic-transduction
  -> cognitive-router
  -> blueprint-genesis, se l'architettura resta ambigua
  -> axiomatic-integrity
  -> knowledge-atoms, se ci sono corpus o archivi da acquisire
  -> lab_template_generator
  -> first cycle smoke test
```

Ogni passaggio deve produrre qualcosa di ispezionabile. Se non produce un
artefatto, resta solo ragionamento e non appartiene al ciclo del Lab.

## Capacita' Da Metabolizzare Presto

### `semantic-transduction`

Funzione: trasformare intento vago in materiale installabile.

Contratto:

- input: richiesta dominio, corpus opzionale, esclusioni, condizione di
  successo;
- output: osservabili domain-native, baseline/null, rischi contaminazione,
  UI lens, primo E2E;
- test: lo stesso intento senza transduzione produce meno osservabili, meno
  controlli o piu' claim narrativi.

Artefatti tipici: `transduction.md`, `skill_intent_map`,
`ui_contract.json`, seed tensions con claim falsificabili e tool esplorativo
piccolo.

### `lab-thought-pass`

Funzione: trattare il ciclo come pensiero, non solo come report o gate.

Contratto:

- input: intento, ciclo sorgente, report o capacita' candidata;
- output: `question_field`, `missing_nodes`, `capability_cascade`,
  `propagation_candidates`;
- test: il passaggio deve dire quale domanda apre e cosa serve per renderla
  osservabile; se produce solo "fare un altro test", non passa.

Artefatti tipici: sezione in `transduction.md`, report meta-lab, packet di
continuita' o card di capacita' per il preset/generatore.

### `possibility-inventory`

Funzione: esporre cio' che il sistema puo' gia' offrire prima della scelta.

Contratto:

- input: intento, dominio, preset, Lab sorgenti, capsule e archivi disponibili;
- output: `possibility_inventory` con source, possibilita', read_depth,
  artefatto candidato, trigger, test, rischio e status;
- test: il passaggio deve distinguere `available`, `needs_body_read`,
  `support_only`, `deferred` e `blocked`; se restituisce solo una lista di
  nomi skill, non passa.

Artefatti tipici: sezione in `transduction.md`, `skill_intent_map_json`,
`archive_retrieval_json`, `skill_reading_matrix` o preset aggiornato.

### `cognitive-router`

Funzione: scegliere la combo minima di skill, archivi e strumenti.

Contratto:

- input: movimento richiesto, classe di movimento, rischi del dominio;
- output: skill layers, archivi da leggere, capacita' mancanti, esclusioni;
- test: il router non deve restituire un catalogo piatto; deve giustificare
  perche' una capacita' entra o resta fuori.

Artefatti tipici: `skill_retrieval`, `mml.json.skills_attive`,
`archive_retrieval_json` e `missing_capabilities`.

### `axiomatic-integrity`

Funzione: impedire che il Lab nasca da contaminazione, contraddizione o
lineage drift.

Contratto:

- input: bozza di Lab o modifica significativa;
- output: PASS/FAIL/SKIP con motivo, contaminazioni escluse, regole ritirabili;
- test: se un source storico e' usato come linguaggio invece che come
  procedura, il gate deve bloccare o declassare.

Artefatti tipici: assertions, `contamination_exclusions`, `valid_when` /
`retire_when` per nuove regole e decisione `do_not_install_default`.

### `knowledge-atoms`

Funzione: acquisire corpus, note, contributi e archivi come atomi promuovibili
invece che come seed injection.

Contratto:

- input: documento, contributo, skill, capsule o report runtime;
- output: atomo con source, claim, uso, rischio, gate e stato;
- test: nessun input entra direttamente nel seme senza quarantine e gate.

Artefatti tipici: `onboarding_contract.json`, `corpus_manifest.json`,
pre-report, source/data cards, cimitero o seed update motivato.

### `blueprint-genesis`

Funzione: quando l'intento puo' produrre architetture diverse, generare piu'
blueprint prima del collapse.

Contratto:

- input: intento con ambiguita' reale;
- output: 2-4 blueprint con oggetti osservati, null, rischio, UI e costo;
- test: la scelta finale deve indicare perche' gli altri blueprint sono stati
  scartati o rimandati.

Artefatti tipici: `blueprint_candidates.md`, decisione del meta-falsifier,
seed finale ed eventuale `cimitero.md` per architetture escluse.

## Capsule / Review Only

Le seguenti possibilita' restano capsule finche' non compare bisogno
ricorrente:

- `prompt-factory`
- `deep-synthesis`
- `inference-stability`
- `oracle-risk`
- `agent-tool-ui-architect`
- `training-dataset`
- `semantic-command-supervisor`
- `expression-form`
- `value-ledger`
- `meta-coder-guardian`
- `cockpit-ux-pipeline`

Regola: se una capacita' serve una sola volta, si trasduce nel Lab corrente.
Diventa Lab figlio solo se ha cicli propri, stato proprio, falsifier proprio e
valore ricorrente.

## Kernel Storici Da Non Installare Come Lab

Questi materiali sono lineage cross-cutting:

- MMS Master
- D-ND PrimaryRules
- materiale simbolico YSN
- overlap SACS/Halo/Morpheus/ALAN quando serve solo coerenza

Uso corretto:

```text
source storico -> pattern -> contratto -> test
```

Uso scorretto:

```text
source storico -> copia nel context -> autorita'
```

## Regola Di Lettura

Profondita' minima:

- `CAPSULE`: orientamento e pruning iniziale;
- `BODY`: richiesto se la capacita' modifica `context.md`, `mml.json`, tool,
  assertions, UI o regole di ciclo;
- `BODY_PLUS_REFS`: richiesto se la capacita' diventa gate, veto o procedura
  comune;
- `E2E`: richiesto prima di dichiarare la capacita' autonoma.

Ogni uso deve comparire in `archive_retrieval` con:

- source/capsule;
- read_depth;
- pattern estratto;
- artefatto modificato;
- contaminazione esclusa;
- test previsto.

## Applicazione Al Prossimo Dominio

Per un nuovo dominio di valore, ad esempio `research-radar`, il meta-lab deve
usare questo stack per evitare due fallimenti opposti:

- Lab generico che copia tab, parole e report senza dominio reale;
- Lab troppo custom che perde falsifier, null, runtime awareness e UI contract.

Sequenza pratica:

1. acquisire `domain_request`;
2. produrre `semantic_transduction`;
3. passare da `cognitive_router`;
4. usare `blueprint_genesis` solo se il dominio ha piu' forme plausibili;
5. applicare `axiomatic_integrity`;
6. progettare onboarding con `knowledge_atoms`;
7. generare template;
8. fare un ciclo smoke E2E;
9. promuovere solo cio' che sopravvive al falsifier.
