# Meta-lab Organic Growth System

> Stato: specifica di governo, prima cristallizzazione 2026-05-20.
> Effetto runtime: nessuno. Questo documento coordina logiche gia' presenti
> prima di trasformarle in registry, validator o generator.

## Scopo

Il meta-lab non deve solo generare nuovi domini. Deve organizzare la crescita
del sistema quando un Lab reale produce nuove capacita', quando un intento
ricorrente merita un sistema proprio, e quando una capacita' locale puo'
aggiornare altri Lab senza contaminarli.

La forma organica e':

```text
intento riconosciuto
  -> sistema minimo installabile
  -> osservazione runtime
  -> pattern emerso
  -> capability versionata
  -> migrazione proposta
  -> Lab aggiornato dopo review
```

Il valore non e' uniformare i Lab. Il valore e' far crescere coerenza,
strumenti e risultanti senza perdere il movimento specifico di ogni dominio.

## Fonti Coordinate

Questo documento non sostituisce i contratti esistenti. Li collega.

- `docs/META_LAB_ARCHITECTURE.md`: architettura, MML, runtime e template.
- `docs/META_LAB_CAPABILITY_STACK.md`: stack capacita' per generare Lab.
- `docs/POSSIBILITY_FIELD_REGISTRY.md`: possibilita' prima del collapse.
- `docs/LAB_THOUGHT_AND_CAPABILITY_CASCADE.md`: ciclo come pensiero e cascata.
- `docs/CONTRIBUTION_PREPORT.md`: quarantena contributi e review.
- `docs/templates/domain_preset.v1.json`: schema preset dominio.
- `docs/templates/ui_contract.v1.json`: contratto UI.
- `docs/templates/onboarding_contract.v1.json`: ingresso informazione.
- `core/domain_request_runner.py`: generazione isolata install-or-block.

## Principio Di Crescita

Ogni Lab maturo produce due risultati:

1. una superficie funzionante per il proprio dominio;
2. una traccia di cio' che insegna al meta-lab.

Esempi correnti:

- Finance insegna baseline/null, precondition boundary, data-card,
  decision bounds e non-admissible outputs.
- Bitcoin Regime Lab insegna expert intake, source robustness, timeframe
  matrix, confluence ablation, no-signal boundary e chiarimento THIA.
- Physics insegna scale sweep, finite-size guard, label shuffle e invarianti.

Il meta-lab conserva il movimento, non il contenuto. Un pattern nato in BTC
non trasferisce POC, FVG o livelli prezzo a Finance; trasferisce solo il
contratto: fonte, scala, oggetto, baseline/null, falsificatore e review.

## Intent Recognition

Un intento puo' diventare un nuovo sistema solo quando supera una soglia minima
di realta'. Non basta una domanda interessante.

Campi minimi:

```json
{
  "intent_id": "slug_stabile",
  "source": "operator|visitor|cycle|runtime|external_source",
  "problem_boundary": "quale problema circoscrive",
  "who_needs_it": "utente, operatore, dominio o sistema",
  "progress_signal": "cosa conta come progresso",
  "forbidden_promises": ["cosa non deve promettere"],
  "available_sources": ["fonti disponibili"],
  "missing_sources": ["fonti mancanti"],
  "baseline_null_possible": true,
  "review_required": true,
  "recommended_path": "extend_existing_lab|new_lab_candidate|archive_context|reject"
}
```

Condizioni positive:

- la domanda e' ricorrente o strutturalmente rilevante;
- un Lab esistente non la contiene senza distorcersi;
- esistono fonti, dati o esperti utilizzabili;
- e' possibile formulare un null, baseline o falsificatore;
- THIA puo' porre domande utili senza fingere autorita';
- il rischio etico, legale e operativo e' gestibile.

Condizioni di blocco:

- intento non falsificabile;
- dati assenti o non tracciabili;
- richiesta di claim sensibile non revisionabile;
- solo curiosita' momentanea;
- impossibilita' di definire cosa conta come progresso;
- promessa di risultato che il Lab non puo' mantenere.

## Lab Lifecycle

Ogni Lab attraversa stati espliciti:

```text
captured_intent
  -> candidate
  -> installed_reference
  -> active_alpha
  -> mature_reference
  -> maintenance
  -> suspended|retired
```

### `captured_intent`

L'intento esiste come richiesta o preport. Non ha ancora autorita' di dominio.

Requisiti:

- source e confine;
- domanda primaria;
- esclusioni;
- decisione: dominio esistente o nuovo candidato.

### `candidate`

Il meta-lab genera un candidato isolato, non installato.

Requisiti:

- `context.md`;
- `transduction.md`;
- `ui_contract.json`;
- `onboarding_contract.json`;
- `mml.json` quando applicabile;
- smoke tool o primo artifact;
- validazione install-or-block.

### `installed_reference`

Il Lab e' installato come riferimento, ma non e' ancora maturo.

Requisiti:

- seed iniziale;
- tool minimo;
- dashboard non vuota;
- confini non-ammissibili;
- THIA contestuale;
- nessuna promozione automatica.

### `active_alpha`

Il Lab produce cicli, artifact e feedback.

Requisiti:

- runtime trace;
- falsifier visibile;
- contribution/review path;
- changelog dominio;
- capability cascade quando emerge una capacita'.

### `mature_reference`

Il Lab e' abbastanza stabile da insegnare al meta-lab.

Requisiti:

- baseline/null consolidati;
- dati o fonti tracciati;
- UI leggibile;
- THIA nel ruolo corretto;
- persistenza review;
- almeno un pattern trasferibile formalizzato o un motivo esplicito per cui
  non ne produce.

## Capability Registry

Una capability e' una funzione/logica riusabile che puo' essere installata in
piu' domini tramite adapter.

Schema logico:

```json
{
  "capability_id": "human_method_intake_card",
  "version": "1.0.0",
  "status": "draft|active|deprecated|retired",
  "source_lab": "bitcoin-regime-lab",
  "purpose": "trasformare materiale umano in metodo revisionabile",
  "use_when": ["esperto", "fonti parziali", "metodo ambiguo"],
  "do_not_use_when": ["richiesta non revisionabile", "dati sensibili"],
  "requires": ["source_provenance", "review_quarantine"],
  "runtime_effects": ["optional_file_intake", "admin_record"],
  "ui_surfaces": ["THIA chat", "intake form", "admin"],
  "persisted_data": ["labFile", "review_card_md"],
  "minimum_checks": ["no_direct_seed", "source_limits_visible"],
  "valid_when": "produce scheda con fonte, limite, null/falsificatore",
  "retire_when": "diventa scorciatoia per promuovere opinioni"
}
```

Capability iniziali candidate:

- `lab_review_card`;
- `human_method_intake_card`;
- `value_artifact_before_cycle`;
- `host_side_pre_cycle_refresh`;
- `source_robustness_gate`;
- `scale_or_timeframe_matrix`;
- `confluence_ablation`;
- `review_quarantine`;
- `no_signal_boundary`;
- `THIA_contextual_assistant`;
- `markdown_admin_review`.

## Lab Registry

Ogni Lab deve dichiarare quali capability usa, quali sono candidate e quali
sono escluse.

Schema logico:

```json
{
  "lab": "bitcoin-regime-lab",
  "lab_version": "0.4.0",
  "spec_version": "lab_spec.v1",
  "lifecycle_state": "active_alpha",
  "capabilities": {
    "source_robustness_gate": "1.0.0",
    "human_method_intake_card": "1.0.0",
    "scale_or_timeframe_matrix": "1.0.0"
  },
  "candidate_capabilities": ["lab_review_card"],
  "excluded_capabilities": [
    {
      "capability": "publish_signal",
      "reason": "high-risk no-signal domain"
    }
  ],
  "last_review": "2026-05-20",
  "compatibility_status": "current|upgrade_available|needs_review|blocked"
}
```

Questa mappa serve a vedere subito:

- quali Lab sono fuori sync;
- quali capability sono obsolete;
- quali migrazioni sono possibili;
- quali domini non devono ricevere un pattern.

## Migration Registry

Una nuova capability non modifica altri Lab automaticamente. Produce una
proposta di migrazione.

Schema logico:

```json
{
  "migration_id": "20260520_human_method_intake_to_finance",
  "capability": "human_method_intake_card@1.0.0",
  "source_lab": "bitcoin-regime-lab",
  "target_lab": "finance",
  "status": "proposed|reviewing|installed|deferred|rejected",
  "reason": "Finance puo' ricevere review di ipotesi regime da esperti",
  "domain_adapter_required": true,
  "required_changes": [
    "finance_regime_review_card",
    "admin render",
    "THIA finance role prompt"
  ],
  "risk": "medium",
  "non_admissible_transfer": [
    "copiare campi BTC",
    "promuovere opinioni a regime finding"
  ],
  "verification": [
    "form salva scheda",
    "admin mostra fonti",
    "nessuna seed contamination"
  ]
}
```

Stati:

- `proposed`: idea documentata, nessun file target modificato;
- `reviewing`: adattamento letto e valutato;
- `installed`: patch applicata e verificata;
- `deferred`: utile ma non ora;
- `rejected`: non compatibile o troppo rischiosa.

## Versioning E Changelog

Ogni cambiamento che puo' influenzare altri Lab deve avere changelog semantico,
non solo git diff.

Livelli:

- `lab_version`: maturita' del dominio;
- `spec_version`: versione del contratto Lab;
- `capability_version`: versione della capacita';
- `migration_version`: applicazione di una capability a un target.

Regola:

```text
patch = correzione senza nuovo comportamento concettuale
minor = nuova capability o nuova superficie review compatibile
major = cambio di lifecycle, promozione, runtime o contratto epistemico
```

Changelog minimi:

- dominio: `domains/<lab>/CHANGELOG.md` o sezione equivalente;
- meta-lab: `docs/meta-lab/CHANGELOG.md` o registro centrale futuro;
- capability: voce nel capability registry;
- migrazione: nota nel migration registry.

## Review, Quarantine E Persistenza

Contributi pubblici, file esperti, note e chat non entrano mai direttamente nel
seed.

Flusso:

```text
visitor/expert/operator input
  -> intake THIA
  -> scheda revisionabile
  -> admin/quarantine
  -> preport o review
  -> accepted contamination
  -> seed tension / tool / doc / new domain draft
```

Persistenza richiesta:

- fonte o allegato;
- estrazione disponibile e limiti;
- identita' contributore quando disponibile;
- ruolo: visitor, expert, operator, imported source;
- scheda `.md` o JSON review;
- stato review;
- boundary: nessuna promozione automatica.

## THIA Role Contract

THIA non deve confondere visitatore, esperto, admin e operatore.

Ruoli:

- `visitor`: chiede, esplora, contribuisce;
- `expert_unverified`: porta materiale o metodo, ma non autorita';
- `operator`: decide review, commit, migrazione e promozione;
- `admin_surface`: mostra quarantena e strumenti, non decide da sola;
- `lab_agent`: produce cicli sotto contratti del dominio.

Regole:

- THIA chiarisce e struttura, non promuove;
- THIA deve dichiarare fonti mancanti e limiti;
- THIA deve usare il dominio attivo e la tab attiva;
- THIA deve proporre una domanda minima quando mancano dati;
- THIA non deve dire "ho aggiornato il Lab" se ha solo salvato un intake.

## Runtime E Value Artifacts

I dati value-facing dovrebbero essere artifact tracciati prima del ciclo quando
il dominio usa fonti esterne.

Pattern:

```text
host-side refresh
  -> value artifact/data-card
  -> dashboard visibility
  -> cycle reads artifact
  -> report/falsifier
```

Motivo:

- riduce drift tra network host e network agente;
- rende i dati ispezionabili prima dell'interpretazione;
- permette a THIA e UI di leggere la stessa superficie;
- evita che il ciclo trasformi fetch opachi in autorita'.

## UI E Frontend Contract

La UI di un Lab deve rendere visibile il movimento, non solo mostrare tab.

Ogni dominio dovrebbe dichiarare:

- stato/campo;
- evidenza o artifact primari;
- baseline/null;
- falsifier;
- runtime trace;
- contributi/review;
- cosa e' `test`, `watch`, `blocked`, `rejected`;
- confini non-ammissibili;
- ruolo THIA.

`ui_contract.json` resta l'autorita' tecnica iniziale. Questo documento chiede
che il futuro registry sappia leggere anche quali capability UI sono attive.

## Transfer Rules

Regole di trasferimento cross-lab:

1. trasferire il movimento, non il contenuto;
2. sostituire osservabili, null e UI lens nel dominio target;
3. non aggiornare seed target senza review;
4. non portare un pattern se manca il dato richiesto;
5. non generalizzare una capability usata una sola volta;
6. se il dominio e' sensibile, rendere visibile no-advice/no-signal;
7. se una capability modifica runtime, UI o persistenza, serve migrazione
   esplicita;
8. ogni trasferimento deve produrre `valid_when` e `retire_when`.

## Organic Growth Loop

Loop operativo:

```text
1. Osserva il Lab sorgente.
2. Identifica pattern emerso.
3. Classifica: specifico, trasferibile, o da scartare.
4. Scrivi capability cascade card.
5. Se trasferibile, crea/aggiorna capability registry.
6. Trova Lab candidati via Lab Registry.
7. Crea proposta di migrazione.
8. Adatta al dominio target.
9. Verifica runtime/UI/persistenza.
10. Aggiorna changelog e versioni.
```

## Applicazione Corrente: BTC -> Finance -> Meta-lab

Stato corrente:

- BTC e' sorgente di pattern su intake esperto, fonti parziali, timeframe e
  robustezza.
- Finance e' target maturo per testare il trasferimento, ma solo con adapter
  regime finance.
- Meta-lab deve ricevere capability generiche, non codice BTC hardcoded.

Primo trasferimento proponibile:

```text
lab_review_card
  -> btc_expert_method_card
  -> finance_regime_review_card
  -> capability registry
  -> installer skeleton opzionale
```

Non trasferire:

- livelli BTC;
- POC/FVG/LVN come contenuto finance;
- qualunque linguaggio trading-signal;
- promozione automatica da admin a seed.

## Primo Incremento Implementabile

Questa specifica autorizza solo il prossimo incremento documentale:

1. creare registry markdown o JSON draft per capability, Lab e migrazioni;
2. inizializzare le capability emerse da BTC e Finance;
3. aggiungere changelog semantico meta-lab;
4. solo dopo aggiornare runner/generator/installer.

Nessun runtime cambia finche' registry e migrazioni non sono leggibili e
revisionabili.

## Registry Draft Iniziali

Prima cristallizzazione:

- `docs/meta-lab/CAPABILITY_REGISTRY.json`
- `docs/meta-lab/LAB_REGISTRY.json`
- `docs/meta-lab/MIGRATION_REGISTRY.json`
- `docs/meta-lab/CHANGELOG.md`

Stato:

- draft;
- nessun effetto runtime;
- validi come JSON leggibile;
- non ancora consumati da runner, validator o generator.

Contenuto iniziale:

- capability emerse da BTC e Finance;
- Lab registry per Finance, BTC, Physics, Research Radar e Meta-lab;
- migration proposals per BTC -> Finance, Physics -> Meta-lab e safety guard;
- capability di sicurezza candidate:
  - `source_provenance_guard`;
  - `role_boundary_guard`;
  - `secret_redaction_guard`.

Regola: questi registry diventano operativi solo dopo una migrazione esplicita
che aggiorna tool/validator/generator e aggiunge verifiche.
