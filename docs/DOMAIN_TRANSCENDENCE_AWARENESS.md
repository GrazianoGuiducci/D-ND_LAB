# Domain Transcendence Awareness

> Persistenza della consapevolezza per generare nuovi Lab D-ND senza
> perdere le logiche fini emerse nel Lab fisico.
>
> Stato: prima cristallizzazione, 2026-05-16.

## Scopo

Questo documento conserva cio' che abbiamo imparato passando dal Lab fisico
reinstallabile al meta-lab generativo.

Non e' una specifica finance, biology o monitoring. E' il contratto di
transduzione: come un Lab cambia dominio mantenendo il proprio movimento
cognitivo. Il meta-lab deve usarlo quando riceve una richiesta di nuovo
dominio, prima di generare `context.md`, `seed.json`, `assertions.py`,
tools, UI hints e `mml.json`.

La regola base:

```text
Non si copia il contenuto del Lab sorgente.
Si conserva il contratto del movimento e si sostituisce il materiale.
```

## Caso sorgente verificato

Il caso sorgente attuale e' il Lab fisico pubblicato nella repo
`D-ND_LAB`, snapshot `20260516`, con gli ultimi cinque cicli accettati
nel bootstrap reinstallabile.

Da questo caso non ereditiamo "fisica", "primi", "GUE", "RP",
"Anderson" o soglie numeriche. Ereditiamo il modo in cui il Lab ha
imparato a muoversi:

- genera una combo che contiene un movimento verso una risultante;
- non prescrive al ciclo cosa concludere;
- fornisce strumenti, null, baseline e criteri di blocco;
- produce un report di risultato e un report/runtime sul come ha ciclato;
- accetta una scoperta solo se sopravvive al falsifier e alla superficie
  di controllo;
- conserva anche cio' che cade, perche' il cimitero e' memoria del filtro.

## Principio

L'intento non e' un target statico. L'intento e' nel movimento.

Per questo la richiesta di un nuovo dominio non deve diventare una lista di
feature o una promessa di risultato. Deve diventare un campo operativo che
permette al Lab di vedere:

- quale possibilita' sta esplorando;
- quali alternative devono poterla falsificare;
- quali osservabili possono cambiare stato;
- quali strumenti mancano e devono essere creati dal sistema;
- quale output e' utile solo se sopravvive a baseline, null e runtime
  awareness.

## Invarianti da portare in ogni dominio

### Movimento prima del contenuto

Ogni nuovo Lab deve nascere con un contratto:

```text
domain_request -> transduction -> combo -> cycle -> report -> falsifier
-> runtime_awareness -> seed update -> UI surface
```

Se il dominio cambia, cambiano materiale, osservabili, tool e UI. Non
cambia il bisogno di un movimento tracciabile.

### Claim falsificabile

Ogni claim deve dichiarare in che modo puo' non reggere. Se non e'
falsificabile, non e' materiale da Lab; e' copy, intuizione o ipotesi
preliminare.

### Null e baseline prima dell'interpretazione

Il Lab non interpreta una firma prima di sapere se sopravvive a un
confronto povero, ingenuo o randomizzato.

Per ogni dominio il meta-lab deve generare almeno:

- una baseline ingenua;
- un null o shuffle coerente col dominio;
- un test out-of-sample o anti-leak quando il dominio usa dati temporali;
- una condizione di sospensione quando il segnale sembra forte ma non e'
  ancora autorita'.

### Regole adattive, non eterne

Una regola non deve nascere come dogma. Deve nascere con metadati minimi:

- `origin`: perche' e' stata introdotta;
- `protects`: quale contaminazione o rottura evita;
- `valid_when`: quando puo' essere applicata;
- `retire_when`: quando deve essere messa in discussione;
- `evidence`: quali cicli o test la sostengono.

Questo evita che una correzione locale diventi vincolo sbagliato in un
dominio nuovo.

### Runtime awareness

Il Lab deve sapere cosa e' successo nel ciclo, non solo cosa e' stato
prodotto.

Il report runtime deve poter rispondere:

- quale input ha letto;
- quali strumenti ha invocato;
- quali alternative ha scartato;
- quale blocco o sospensione e' intervenuto;
- quale superficie e' stata accettata;
- cosa resta ispezionabile ma non autorita'.

### Non interferenza

Il meta-lab non deve dire al Lab figlio quale scoperta trovare. Deve
fornire logica, strumenti e criteri perche' il Lab possa muoversi senza
osservatore continuo.

Una direzione e' valida quando apre il campo. Diventa contaminante quando
obbliga la risultante.

## Cosa non va trasferito

Dal Lab fisico non vanno copiati:

- formule, soglie o operatori specifici del dominio fisico;
- nomi di tensioni nati da prime/GUE/RP/Anderson;
- categorie UI che hanno senso solo per quel materiale;
- report come esempi da imitare semanticamente;
- cicli vecchi contaminati o logiche ripristinate perche' nate su una
  calibrazione sbagliata.

Il Lab fisico serve come sorgente di metodo, non come dizionario.

## Procedura di transduzione

### 1. Richiesta dominio

Il meta-lab parte da `domain_request.v1`: dominio, intento/movimento,
materiale disponibile, vincoli, output utile, rischi noti.

La domanda non e' "che report vuoi?". La domanda e':

```text
quale movimento deve poter compiere un sistema autonomo in questo dominio?
```

### 2. Diagnosi del materiale

Prima di generare tool o UI, il meta-lab deve capire:

- quali oggetti sono osservabili;
- quali oggetti sono decisioni;
- quali oggetti sono rumore, bias o leakage;
- quali pattern possono essere stressati;
- quali parti del dominio non hanno ancora leva sufficiente.

### 2b. Recupero skill ed enzimi

Prima di progettare il Lab figlio, il meta-lab deve interrogare il campo
skill/enzimi gia' disponibile:

- `docs/SKILL_CATALOG.md`;
- `docs/SKILL_FIELD_MAP.md`;
- `docs/SKILL_DIAGNOSTIC.md`;
- `/opt/MM_D-ND/tools/data/cognitive_enzymes_archive.md`;
- eventuali skill domain-specific gia' presenti in `/opt/.claude/skills/`,
  `/opt/MM_D-ND/kernel/reference/skills/` o archivi THIA.

Output minimo della fase:

- skill candidate per layer MML;
- enzimi cognitivi rilevanti con source;
- skill escluse per rischio contaminazione;
- capacita' mancanti che devono diventare tool, null, baseline, assertion
  o nuova skill.

Questo passaggio serve a evitare una perdita di logiche fini: non si
generalizza cancellando le skill, si sceglie quali parti del sistema gia'
esistente devono essere attivate nel nuovo dominio.

### 3. Mappa degli osservabili

Gli osservabili devono essere domain-native. Non si traducono i termini
fisici in sinonimi; si cercano le grandezze reali del dominio.

Esempi:

- finance: return, volatilita', drawdown, liquidita', correlazioni,
  regime persistence, slippage;
- editorial: archivi, ricezione, pubblicabilita', novelty, densita'
  argomentativa, coerenza con audience;
- monitoring: eventi, soglie adattive, drift, causalita' operativa,
  recovery time.

### 4. Baseline e null

Il meta-lab deve generare null e baseline propri del dominio.

Esempio finance:

- random walk;
- shuffled returns;
- block bootstrap;
- walk-forward split;
- benchmark buy-and-hold;
- transaction cost/slippage baseline;
- survivorship e lookahead bias checks.

Questi non sono risultati; sono il terreno minimo per impedire che il Lab
si racconti una storia.

### 5. Assertions eseguibili

Ogni nuovo Lab deve nascere con assertion eseguibili, anche se semplici.

Le assertion non devono dimostrare il valore del dominio. Devono impedire
che il Lab parta senza struttura:

- dataset o fallback presente;
- baseline calcolabile;
- output riproducibile;
- nessun uso di dati futuri in un test temporale;
- almeno una tensione produce PASS/FAIL/SKIP numerico.

### 6. Tools iniziali

I tools iniziali devono servire il primo ciclo, non una roadmap ideale.

Devono essere piccoli, invocabili out-of-box e capaci di produrre una
traccia verificabile. Se un dominio richiede dati esterni, deve avere un
fallback sintetico o open.

### 7. UI contract

La UI deve cambiare col dominio. Non basta esporre report.

Il frame comune resta il template a tre colonne:

```text
sinistra -> campo, stato, contatori, tensioni, filtri, alert
centro   -> vista primaria del movimento del dominio
destra   -> dettaglio, runtime, spiegazione, THIA/context assistant
```

Ogni dominio deve dichiarare come riempie questo frame in:

```text
domains/<slug>/ui_contract.json
```

Il processo canonico e' in `docs/UI_COGNITIVE_PROCESS.md`; il template
riusabile e' `docs/templates/ui_contract.v1.json`.

Per installazioni piu' veloci il meta-lab puo' partire da preset opzionali in
`docs/templates/domain_presets/`, descritti in `docs/DOMAIN_PRESETS.md`. Il
preset accelera la scelta di osservabili, null, falsifier e moduli UI, ma non
sostituisce la transduzione: deve essere adattato al dominio e poi validato.

Ogni UI di Lab dovrebbe mostrare almeno:

- ipotesi o tensione attiva;
- evidenza contro baseline;
- cosa e' sospeso;
- cosa e' non-ammissibile o non-possibile;
- dinamica runtime del ciclo;
- ultimo stato del seed;
- dove il sistema sta creando strumenti nuovi.

Nel finance, per esempio, l'output utile non e' "segnale buy/sell". E':
vincolo decisionale, assunzione falsificata, regime sospetto, esposizione
non ammessa finche' il test non regge.

## Esempio: Finance Lab

Intento di valore:

```text
Rilevare cambi di regime e falsificare assunzioni operative prima che
diventino decisioni di esposizione.
```

Movimento corretto:

- osservare quando un'ipotesi smette di reggere;
- separare segnale da rumore, leakage e overfit;
- produrre vincoli decisionali, non promesse predittive;
- creare strumenti quando il dominio mostra una rottura non ancora
  misurabile.

Materiale minimo:

- serie temporali open o sintetiche;
- calendario dei test;
- benchmark ingenuo;
- costi e slippage;
- split temporale;
- cimitero di assunzioni fallite.

Anti-contaminazioni:

- lookahead bias;
- overfitting;
- survivorship bias;
- data snooping;
- metriche scelte dopo aver visto il risultato;
- UI che trasforma una sospensione in segnale operativo.

## Requisito per il meta-lab

Quando il meta-lab genera un nuovo dominio deve produrre anche una nota di
transduzione:

```text
domains/<slug>/transduction.md
```

La nota deve dichiarare:

- quali invarianti D-ND sono stati portati;
- quali elementi del Lab sorgente sono stati esclusi;
- quali osservabili domain-native sostituiscono il materiale sorgente;
- quali null/baseline proteggono il dominio;
- quali regole adattive sono state introdotte e quando vanno ritirate;
- quale UI contract serve al dominio e dove vive `ui_contract.json`;
- quali test E2E dimostrano che il Lab gira senza osservatore.

Questa nota e' parte del seme del Lab figlio. Se manca, il nuovo Lab e'
generato ma non ancora consapevole della propria transduzione.

## Meta-lente aggiunta: M7

Alle lenti M1-M6 del meta-lab si aggiunge:

**M7 — Integrita' di transduzione**

Un Lab generato passa M7 solo se:

- non copia contenuto dominio-specifico dal Lab sorgente;
- conserva i contratti di movimento;
- dichiara osservabili, null, baseline e UI domain-native;
- ha almeno una assertion che protegge da contaminazione specifica del
  dominio;
- produce `transduction.md`;
- puo' essere reinstallato e ispezionato da una nuova istanza senza
  memoria della chat.

M7 serve a impedire la generalizzazione povera: quella che conserva parole
e perde movimento.

## Meta-lente aggiunta: M8

**M8 — Recupero skill/enzimi prima dell'installazione**

Un Lab generato passa M8 solo se:

- dichiara nel report o in `transduction.md` quali skill/enzimi sono stati
  consultati prima della progettazione;
- produce un `mml.json` in formato layered object, non solo lista piatta;
- motiva per ogni skill scelta il layer, il trigger e il ruolo nel dominio;
- dichiara quali skill/enzimi sono stati esclusi per evitare contaminazione;
- dichiara le capacita' mancanti come strumenti/null/gate da creare, invece
  di nasconderle nella copy.

M8 serve a impedire la seconda forma di generalizzazione povera: quella che
ricostruisce da zero cio' che il sistema possiede gia' come skill, perdendo
architettura e memoria operativa.

## Persistenza

Ogni volta che un ciclo monitorato rivela una logica utile per generare
altri Lab, va classificata in una di queste forme:

- **invariante**: vale in tutti i domini;
- **adattatore**: traduce un invariante in un dominio;
- **protezione**: blocca una contaminazione nota;
- **ritiro**: indica quando una regola va sospesa;
- **UI lens**: rende visibile il movimento senza trasformarlo in copy;
- **E2E lens**: verifica che il Lab funzioni senza memoria esterna.

La prossima istanza deve poter riprendere da qui senza sapere cosa e'
successo in chat.
