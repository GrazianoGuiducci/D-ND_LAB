# Lab Information Onboarding

> Contratto per acquisire informazioni in un Lab nuovo senza contaminare il
> seme, il ciclo o il dominio.
>
> Stato: prima cristallizzazione, 2026-05-17.

## Scopo

Un Lab autonomo non nasce solo da file generati. Deve sapere come acquisire
informazioni da:

- interazione umana;
- corpus forniti dall'operatore;
- contributi pubblici;
- dataset/API;
- archivi cognitivi e skill;
- runtime prodotto dai cicli precedenti.

La regola e':

```text
input -> quarantena -> pre-report -> transduzione -> gate -> seed/cycle
```

Nessuna informazione entra direttamente nel seme. Prima deve avere fonte,
scope, rischio, uso previsto e falsificazione minima.

## Canali di ingresso

### 1. Domain Request

Uso: creare o riprogettare un Lab.

Fonte tipica:

```bash
dndlab plan-domain
```

Output minimo:

- dominio/slug;
- intento come movimento;
- `movement_class`;
- `use_dynamics`;
- esclusioni;
- condizione di successo;
- eventuale preset;
- fonti/corpus disponibili.

Autorita': input di progettazione per il meta-lab, non seed operativo.

Gate:

- `DOMAIN_TRANSCENDENCE_AWARENESS`;
- `META_LAB_SKILL_INTENT_GUIDE`;
- `META_LAB_SKILL_READING_PROTOCOL`;
- `COGNITIVE_ARCHIVE_INTEGRATION`;
- validator M1-M8.

### 2. Human Clarification

Uso: chiarire intento, vincoli, costi di errore, non-ammissibile.

Tipi di domanda utili:

- quale movimento deve ripetersi senza osservatore?
- cosa deve bloccare il Lab se sembra promettente ma non regge?
- quale dato non va mai usato?
- quali decisioni non deve prendere?
- quale output sarebbe utile solo dopo falsificazione?

Autorita': modifica `domain_request`, `transduction.md`, `ui_contract` o
vincoli di `context.md`. Non modifica direttamente risultati o report.

Gate:

- ogni correzione umana che cambia regole deve dichiarare `origin`,
  `protects`, `valid_when`, `retire_when`, `evidence`.

### 3. Corpus Operatore

Uso: documenti, note, paper, archivi, dataset forniti per il dominio.

Regole:

- mettere file privati in `domains/<slug>/corpus/` o data dir ignorata da git;
- non pubblicare corpus privato nella repo;
- estrarre solo summary, osservabili, claim e vincoli trasferibili;
- distinguere materiale fonte da materiale interpretato.

Output minimo:

- `corpus_manifest.json` o sezione equivalente in `transduction.md`;
- elenco fonti con provenance;
- cosa e' pubblico, privato, sintetico o fallback;
- limiti di licenza/privacy.

Gate:

- nessun segreto;
- nessun dato personale sensibile non richiesto;
- nessuna credenziale;
- nessun dataset privato in GitHub;
- baseline/null prima dell'interpretazione.

### 4. Public Contribution Intake

Uso: visitatori, ricercatori, utenti o esperti propongono idee, fonti o
correzioni.

Flusso esistente:

```text
visitor suggestion -> contribution registry -> preport -> operator review
-> accepted contamination -> seed tension / direction / domain draft
```

Riferimento: `docs/CONTRIBUTION_PREPORT.md`.

Autorita': pre-report, mai contaminazione automatica.

Gate:

- sanitizzazione;
- rate limit;
- redazione segreti;
- `NEEDS_CLARIFICATION` se mancano fonte, ipotesi o falsificazione;
- review operatore prima di promozione.

### 5. Dataset/API Onboarding

Uso: dati numerici, API pubbliche, endpoint domain-specific.

Output minimo:

- source card: URL/path, licenza, auth, limiti;
- data-card: periodo, frequenza, campi, missing, fallback;
- leakage guard: cosa sarebbe futuro rispetto al test;
- baseline/null compatibile col dominio;
- assertion di disponibilita' e formato.

Gate:

- API con credenziali richiedono configurazione esterna, non repo;
- se il dato esterno manca, il Lab deve avere fallback sintetico/open;
- ogni metrica deve dichiarare denominatore e finestra;
- nessun lookahead per dati temporali.

### 6. Cognitive Archive Onboarding

Uso: skill, KPhi1, `/opt/skill`, cockpit/MMSp o altri archivi cognitivi.

Riferimenti:

- `docs/COGNITIVE_ARCHIVE_INTEGRATION.md`;
- `docs/cognitive_archives/*.json`;
- `archive_retrieval_json` nel generator.

Regola:

```text
capsula -> candidate pattern -> body read if needed -> transduction -> E2E
```

Autorita':

- `read_depth=CAPSULE`: orientamento, non autorita' operativa;
- `read_depth=BODY`: procedura utilizzabile se transdotta;
- `read_depth=BODY_PLUS_REFS`: ammissibile in MML con diagnostica;
- `read_depth=E2E`: pattern esercitato.

Gate:

- `archive_retrieval` obbligatorio se si citano archivi esterni;
- `body_required=true` se si usa una capsula per progettare artefatti;
- contaminazione esclusa dichiarata;
- test/E2E atteso dichiarato.

### 7. Runtime Self-Observation

Uso: il Lab impara da cio' che i cicli fanno, non solo dai report.

Input:

- cycle trace;
- report runtime;
- falsifier;
- Veritas/Aeternitas;
- trajectory evaluator;
- seed integrator;
- cimitero;
- UI usage/admin actions.

Output minimo:

- cosa e' stato letto;
- quali tool sono stati invocati;
- cosa e' stato scartato;
- quale blocco e' intervenuto;
- cosa e' accettato come autorita';
- cosa resta ispezionabile ma non autorita'.

Gate:

- ogni regola nuova deve avere `origin/protects/valid_when/retire_when`;
- cio' che cade entra nel cimitero con motivo;
- cio' che migliora il processo diventa KLI o pattern operativo.

## Schema `onboarding_contract`

Ogni nuovo Lab dovrebbe dichiarare, in `transduction.md` o in
`onboarding_contract.json`, almeno:

```json
{
  "schema": "dndlab.onboarding_contract.v1",
  "domain": "finance",
  "channels": {
    "domain_request": {"status": "present", "authority": "planning"},
    "human_clarification": {"status": "allowed", "authority": "constraints"},
    "operator_corpus": {"status": "optional", "authority": "source"},
    "public_contribution": {"status": "quarantine", "authority": "preport_only"},
    "dataset_api": {"status": "optional", "authority": "evidence_after_baseline"},
    "cognitive_archives": {"status": "capsule_first", "authority": "by_read_depth"},
    "runtime_self_observation": {"status": "required", "authority": "cycle_trace"}
  },
  "promotion_gates": [
    "source_provenance",
    "privacy_secret_scan",
    "baseline_null",
    "falsification_test",
    "operator_review_when_public_or_sensitive",
    "runtime_trace"
  ],
  "never_direct_to_seed": [
    "public contributions",
    "private corpus",
    "capsule-only archive patterns",
    "human preference without falsification"
  ]
}
```

## UI Implicazioni

Il template dashboard a tre colonne deve prevedere:

- sinistra: stato fonti, contatori contributi, corpus/data-card, warning;
- centro: vista primaria del movimento del dominio;
- destra: dettaglio fonte, pre-report, cycle trace, THIA context assistant.

Per utenti pubblici:

- contributi e feedback sono pre-report;
- nessun run cycle pubblico senza auth/admin;
- nessuna promessa di contatto realtime;
- nessun dato sensibile.

Per admin:

- review contributi;
- promozione manuale a tensione/draft dominio;
- lettura `archive_retrieval`;
- run cycle monitorato;
- visibilita' runtime trace.

## Relation To Meta-Lab

Il meta-lab deve usare questo documento prima di generare un nuovo dominio.

`domain_request.v1` dice cosa il Lab deve diventare.
`onboarding_contract` dice come il Lab potra' continuare ad acquisire
informazione dopo l'installazione.

Se manca il contratto di onboarding, il Lab puo' passare i test statici ma
rischia di dipendere sempre dall'operatore per sapere cosa leggere dopo.
