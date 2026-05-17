# Meta-lab Skill Reading Protocol

> Protocollo operativo per leggere le skill prima di progettare un Lab figlio.
> Stato: prima cristallizzazione, 2026-05-17.

## Scopo

Il meta-lab non deve "leggere tutte le skill" in modo rituale, ne' deve
fidarsi solo di cataloghi e mappe. Deve progettare la lettura partendo
dall'intento/movimento del dominio, selezionare un set minimo di skill
candidate, leggere i corpi necessari e trasformare cio' che regge in
contratti operativi del Lab figlio.

La catena corretta e':

```text
domain_request -> movement_class -> use_dynamics -> candidate skills
-> body reading -> skill_reading_matrix -> skill_intent_map
-> context/mml/tools/assertions/ui_contract -> e2e
```

Se una skill e' solo nominata ma il suo corpo non e' stato letto o non ha
un ruolo verificabile nel ciclo, non e' una skill attiva: e' al massimo una
ipotesi di progettazione.

## Principio

La lettura delle skill e' un atto di transduzione, non di accumulo.

Si conserva il movimento della skill, non il suo contenuto di dominio, la sua
persona narrativa o la sua terminologia se contaminano il Lab figlio.

## Input

Il protocollo parte da:

- `domain_request.v1`;
- `movement_class`;
- `use_dynamics`;
- `exclusions`;
- `success_condition`;
- eventuale preset dominio;
- eventuale corpus utente;
- stato diagnostico delle skill.

## Fonti

Ordine di consultazione:

1. `docs/META_LAB_SKILL_INTENT_GUIDE.md` per tradurre intento in movimento.
2. `docs/SKILL_CATALOG.md` per trovare candidate.
3. `docs/SKILL_FIELD_MAP.md` per capire layer e collaborazioni.
4. `docs/SKILL_DIAGNOSTIC.md` per stato vivo/stub/eval/persona.
5. `docs/COGNITIVE_ARCHIVE_INTEGRATION.md` per distinguere archivi
   correnti, semi installabili e lineage storico prima di scegliere una
   fonte non standard.
6. Capsule portabili in `docs/cognitive_archives/` quando la fonte completa
   non e' disponibile o leggere tutto costerebbe troppo contesto.
7. Corpi reali delle skill candidate:
   - `/opt/.claude/skills/*.md`;
   - `/opt/MM_D-ND/kernel/reference/skills/*.md`;
   - skill THIA in `/opt/THIA/.agent/skills/` se disponibili e pertinenti.
   - `/opt/skill/agent_skills_*.md` quando serve la snapshot THIA flat;
   - `/opt/KPhi1/skills/*/SKILL.md` quando serve il seme strutturato KPhi1;
   - `/opt/d-nd_cockpit/docs/system/kernel/*` solo per lineage storico
     letto e transdotto esplicitamente.
8. `/opt/MM_D-ND/tools/data/cognitive_enzymes_archive.md` per enzimi gia'
   estratti.

Catalogo, mappa e diagnostica orientano. Il corpo della skill decide.
Gli archivi esterni al Lab non sono autorita' implicita: entrano solo con
path, profondita' di lettura, pattern estratto e rischio contaminazione.
Una capsula vale come livello `CAPSULE`: puo' restringere il campo, ma non
autorizza una skill attiva nel MML quando serve il corpo.

## Profondita' di lettura

Ogni skill candidata riceve un livello:

| Livello | Significato | Uso ammesso |
|---|---|---|
| L0 | vista solo in catalogo/mappa | ipotesi, non attivabile |
| L1 | corpo della skill letto | procedura o meta-prompt possibile |
| L2 | corpo + riferimenti/eval/tool collegati letti | skill dichiarabile in MML se coerente |
| L3 | skill esercitata in smoke/test/ciclo o con output verificato | skill autoritativa per generator/falsifier |

Regola: il `mml.json` di un nuovo Lab non dovrebbe dichiarare skill sotto L2,
salvo nota esplicita `support_only` o `needs_eval`.

## Skill Reading Matrix

Ogni generazione deve produrre una matrice ispezionabile nel report del
meta-lab o in `transduction.md`.

Schema minimo:

```json
{
  "skill_reading_matrix": [
    {
      "skill": "autologica-operativa",
      "source": "/opt/.claude/skills/autologica-operativa.md",
      "read_depth": "L1|L2|L3",
      "diagnostic_status": "VIVA|VIVA-NO_EVAL|STUB|PERSONA|UNKNOWN",
      "why_selected": "quale movimento richiede questa skill",
      "trigger": "quando il Lab figlio la invoca",
      "output_contract": "cosa deve produrre",
      "lab_role": "context|mml_layer|tool|assertion|null|baseline|ui|exclusion",
      "movement_link": "intent -> movement -> artifact",
      "contamination_risk": "cosa non va trasferito",
      "missing_capability": "cosa va creato se la skill non basta"
    }
  ]
}
```

La matrice precede `skill_intent_map`: prima si legge, poi si dichiara il
collegamento operativo.

## Procedura

### 1. Restringi il campo

Dal `domain_request.v1` estrai:

- cosa deve cambiare stato nel Lab;
- cosa puo' falsificare il movimento;
- quale output sarebbe utile solo se sopravvive;
- quali contaminazioni sono gia' note.

Non aprire tutte le skill. Seleziona candidate solo per i layer necessari.

### 2. Seleziona candidate per layer

Per ogni dinamica d'uso scegli al massimo 2-4 skill candidate per layer:

- validation;
- processing;
- observation;
- output;
- generation;
- interface;
- runtime;
- domain.

Se un layer non serve al movimento iniziale, resta vuoto o viene dichiarato
come `deferred`.

### 3. Leggi i corpi, non solo i nomi

Per ogni candidata:

- leggi il corpo della skill;
- separa procedura operativa da linguaggio/persona;
- identifica trigger, output e stop condition;
- controlla lo stato diagnostico;
- cerca eval o tool collegato solo se la skill entra nel MML.

### 4. Esponi regressivamente

Per ogni skill che resta candidata chiedi:

```text
quale intento serve?
quale movimento rende possibile?
quale artefatto cambia?
quale null/baseline/assertion la puo' falsificare?
quale evidenza E2E mostrera' che non e' solo decorativa?
```

Se non risponde, la skill viene esclusa o resta `support_only`.

### 5. Trasforma in artefatti

Una skill letta puo' diventare solo una di queste cose:

- layer MML con trigger e output;
- procedura nel `context.md`;
- tool iniziale;
- assertion;
- null/baseline;
- modulo UI;
- esclusione motivata;
- nuova capability da creare.

Non inserire skill nel MML come lista di identita'.

### 6. Fermati

La lettura si ferma quando:

- ogni `use_dynamic` ha almeno una skill/tool/null/assertion che la supporta;
- ogni gap e' dichiarato in `missing_capabilities`;
- ogni skill scelta ha rischio contaminazione esplicito;
- `skill_reading_matrix` e `skill_intent_map` sono coerenti;
- il primo E2E atteso e' descrivibile senza memoria della chat.

Leggere altre skill senza cambiare questi output e' accumulo.

## Regole di esclusione

Escludere o declassare una skill quando:

- il corpo non e' stato letto e serve piu' di L0;
- e' persona-only e non produce procedura;
- e' `STUB` o `VIVA-NO_EVAL` ma viene usata come autorita';
- trasferisce contenuto del dominio sorgente invece del movimento;
- aumenta output narrativo senza aumentare falsificabilita';
- richiede dati, segreti o runtime non disponibili nel Lab figlio;
- non ha trigger, output o stop condition.

## Esempio finance

Movimento corrente:

```text
calibration + recovery: capire perche' detector di regime producono purezza
ma non potenza recuperabile, prima di trasformarli in decisioni operative.
```

Candidate da leggere prima di ulteriori cicli finance:

- `autologica-operativa`: ridisegno senza aggiungere regole eterne;
- `cec`: filtro su condizioni/signature/laterale/inversione/cristallizzazione;
- `eval`: valutare se un output e' operabile o solo narrativo;
- `assertion-verifier`: proteggere baseline/null e test numerici;
- `audit-system`: vedere side effect e drift runtime;
- `scenario-projector`: solo se ci sono 5+ tensioni reali e serve decisione;
- `veritas`/`kairos`/`helix`: se disponibili come corpi leggibili, per veto,
  timing e iterazione.

Output atteso: non "nuova strategia finance", ma matrice skill letta,
precondizione falsificabile, baseline/null e vincolo decisionale.

## Relazione con M8

Questo protocollo non aggiunge una nuova meta-lente. Raffina M8:

- `skill_retrieval` dice cosa il sistema possiede;
- `skill_reading_matrix` dice cosa e' stato letto e come viene usato;
- `skill_intent_map` dice come quella lettura diventa movimento del Lab.

Un template puo' passare formalmente M8 con recupero skill dichiarato, ma non
va considerato pronto per un dominio nuovo se manca la matrice di lettura
quando le skill influenzano `context.md`, `mml.json`, tool, assertion o UI.
