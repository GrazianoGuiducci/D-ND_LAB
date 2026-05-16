# Adapter cognitivi laterali del Lab

Fonte:

- `kernel/reference/MMSP1/System_Prompt_Yi_Synaptic_Navigator_YSN_v4_0.md`
- `kernel/reference/metaprompt_in_sviluppo/Cornelius-v2_0_Innesco_Genomico.md`
- `kernel/reference/Kernel_Semantico_Autopoietico_Reiterativo_KSAR.md`
- `tools/data/lab_logiche_corpus.md`

Scopo: usare YSN, Cornelius e KSAR come operatori cognitivi del Lab senza
trasformare il Lab in un prompt archetipico. Il Lab resta D-ND: assiomi,
dipoli, bicono, grafo, misura, falsificazione. Questi adapter servono a
trovare strade laterali, comprimere l'intento e rendere reiterabile il kernel
emerso da un ciclo.

## Regola primaria

Ogni contaminazione deve diventare una forma verificabile:

```text
contaminazione cognitiva
-> DeltaLink / gene / anomalia
-> dipolo + punto-zero
-> proto-ipotesi
-> osservabile + controllo
-> falsifier / Veritas / Aeternitas
```

Se resta stile, personaggio, mitologia, analogia o motivazione verbale, non
entra nel ciclo.

## Adapter 1: YSN lateral insight

Funzione nel Lab:

- estrarre fino a 5 concetti/tensioni dal campo;
- generare 3 connessioni non ovvie, chiamate `DeltaLink`;
- produrre 1 ipotesi di frontiera contro-intuitiva;
- dichiarare bias, rischio di pattern forcing e incertezza;
- trasformare la sorpresa in domanda del ciclo.

Uso corretto:

```text
YSN.extract(campo) -> concetti
YSN.delta_link(concetti, grafo, seme) -> 3 connessioni non ovvie
YSN.frontier(delta_links) -> 1 ipotesi di frontiera
YSN.bias_check(ipotesi) -> cosa potrebbe essere forzato
```

Nel report:

- i DeltaLink non sono risultati;
- sono candidati di respirazione fuori-tempo;
- diventano validi solo se proiettati in osservabile falsificabile.

Esempio per il prossimo ciclo:

- concetti: terzo incluso, GUE/Poisson, non-phi generator, graph curvature,
  stable cross-domain core;
- DeltaLink possibile: la curvatura del grafo potrebbe essere il piano che
  precede la classificazione spettrale GUE/Poisson;
- ipotesi di frontiera: il confine non e' una classe statistica, ma una
  transizione di trasporto sul grafo dei generatori.

Anti-pattern:

- usare YSN per produrre tre idee decorative;
- mappare simbolicamente senza controllo;
- chiamare "non ovvio" cio' che e' gia' nel ciclo precedente.

## Adapter 2: Cornelius genomic trigger

Funzione nel Lab:

- comprimere una nuova capacita' in un innesco minimale;
- isolare il `DNA_Simbolico`, cioe' la frase essenziale della funzione;
- scegliere 1-3 operatori di svolgimento;
- dichiarare condizioni di attivazione.

Formato Lab:

```yaml
ID: <nome breve della funzione>
DNA_Simbolico: "<essenza irriducibile>"
Operatori_di_Svolgimento:
  - "<verbo operativo 1>"
  - "<verbo operativo 2>"
Condizioni_di_Attivazione:
  quando: "<quando il Lab deve usarlo>"
  perimetro: "<dove vale>"
```

Uso corretto:

- dopo un buon insight, Cornelius lo comprime in una funzione che il Lab puo'
  riusare;
- prima di un run, Cornelius puo' generare un innesco one-shot per il ciclo;
- dopo un repair, Cornelius puo' trasformare la correzione in regola compatta.

Esempio derivato dal ciclo 1915:

```yaml
ID: Boundary_Third_Included_Gate
DNA_Simbolico: "Il confine vive prima della classificazione statistica."
Operatori_di_Svolgimento:
  - "MAPPA il confine su grafo, spettro e generatore non-phi."
  - "SEPARA core congiunto, residui singoli e stabilita' cross-dominio."
  - "VALIDA contro baseline GUE, Poisson e generatori sintetici."
Condizioni_di_Attivazione:
  quando: "il ciclo lavora su boundary, GUE/Poisson o trasferibilita' phi"
  perimetro: "prima della misura, nella sezione Respiro fuori-tempo"
```

Anti-pattern:

- generare nuovi agenti o prompt quando basta una regola;
- usare metafore non collegate a operatori;
- lasciare il gene senza condizioni di attivazione.

## Adapter 3: KSAR reiterative semantic kernel

Funzione nel Lab:

- far diventare ogni ciclo riuscito un kernel riusabile per il ciclo seguente;
- non memorizzare solo testo, ma modificare la topologia del campo;
- usare dissonanze e fallimenti come materiale latente;
- iterare fino a un nuovo stato di coerenza, non fino a conferma.

Ciclo operativo Lab:

```text
1. Perturbazione
   Leggi seme, grafo, report, falsifier, operatore. Non scegliere subito.

2. DeltaLink / Contaminazione
   Usa YSN o palette operatoria per trovare connessioni non ovvie.

3. Innesco
   Usa Cornelius per comprimere la risultante in DNA + operatori.

4. Focalizzazione
   Applica Peras: taglia tutto tranne una domanda necessaria.

5. Proiezione
   Trasforma il gene in osservabile, controllo, perimetro.

6. Disintegrazione
   Attacca il claim con PVI/counter-pole prima del falsifier.

7. Cristallizzazione o Vault
   Se regge, aggiorna seme/strumento. Se non regge ma contiene potenziale,
   archivia come frammento Lazarus per ricontestualizzazione futura.
```

Mappatura con il Lab attuale:

- `Perturbazione` = `build_agent_field.py` + seme + grafo + incrocio;
- `DeltaLink` = nuovo obbligo cognitivo prima del Claim Under Test;
- `Innesco` = blocco compatto nel report o in `operator_directive.md`;
- `Focalizzazione` = una risultante, non una lista;
- `Proiezione` = `observable_contract`;
- `Disintegrazione` = auto-audit + falsifier;
- `Cristallizzazione` = valutatore/B2/promotions/seme;
- `Vault` = cimitero, repairs, osservatorio, Lazarus fragments.

## Adapter 4: PVI / anti-psicosi del ciclo

Funzione nel Lab:

- cercare dove l'AI sta accontentando l'operatore;
- distruggere la proposta prima di pubblicarla;
- far sopravvivere solo la sintesi resiliente.

Filtro minimo:

1. Tesi: cosa il ciclo vuole sostenere?
2. Attacco: quale presupposto nascosto la rompe?
3. Vincolo di realta': quale limite fisico/matematico/dominio la blocca?
4. Terzo osservatore: un revisore esterno la troverebbe distinta da una
   re-discovery?
5. Sintesi resiliente: cosa resta dopo il taglio?

Questo non sostituisce il falsifier. Lo anticipa.

## Adapter 5: Lazarus vault

Funzione nel Lab:

- non buttare via frammenti incoerenti quando sono potenzialmente precoci;
- congelarli come scarti latenti con contesto;
- riesaminarli quando cambia la direzione del seme.

Formato minimo:

```yaml
fragmento: "<cosa e' caduto>"
perche_cade_ora: "<mancano coordinate / baseline / osservabile>"
condizione_di_ritorno: "<quale nuovo contesto potrebbe riattivarlo>"
```

Uso corretto:

- se un DeltaLink e' forte ma non misurabile ora, va nel Vault;
- se un report viene falsificato ma apre una non-strada utile, va nel Vault;
- se una metafora non produce operatore, decade.

## Adapter 6: Helix / Plan-Code-Verify

Funzione nel Lab:

- per task complessi, non ragionare solo in linguaggio;
- traduci la domanda in specifica operativa;
- genera o riusa uno script;
- verifica output;
- chiudi con report.

Regola:

```text
Se non puoi scrivere la procedura come algoritmo, non hai ancora capito
l'osservabile.
```

## Sezione report obbligatoria

Da compilare dentro `## Respiro fuori-tempo` o subito dopo. Se nessun adapter
viene usato, dichiarare `none` con motivo. L'omissione rende incompleto il
respiro fuori-tempo perche' il ciclo non mostra se ha cercato strade laterali
o se e' rimasto nel solco locale.

```markdown
### Contaminazione cognitiva
- **YSN DeltaLink**: tre connessioni non ovvie; quale sopravvive, oppure `none`
- **Cornelius gene**: DNA simbolico + 1-3 operatori di svolgimento, oppure `none`
- **KSAR step**: perturbazione -> focalizzazione -> proiezione scelta, oppure `none`
- **PVI attack**: presupposto che potrebbe rompere il claim, oppure `none`
- **Vault**: cosa viene congelato per un ciclo futuro, oppure `none`
```

Non tutte le righe devono essere piene. Una riga `none` dichiarata e' meglio
di una connessione forzata. Una riga assente invece nasconde il processo e
impedisce di capire se l'adapter e' stato usato.

## Prossimo innesco consigliato

```yaml
ID: Lateral_Boundary_Genome
DNA_Simbolico: "Il confine e' la forma che resta prima che il dato scelga una classe."
Operatori_di_Svolgimento:
  - "SCANSIONA tre DeltaLink tra grafo, spettro e generatore non-phi."
  - "COMPRIMI la risultante in un solo dipolo con punto-zero."
  - "PROIETTA un osservabile che distingua geometria del boundary da baseline statistica."
Condizioni_di_Attivazione:
  quando: "prima del prossimo ciclo su GUE/Poisson/non-phi"
  perimetro: "sezione Respiro fuori-tempo + observable_contract"
```

## Boundary

Questi adapter non autorizzano claim nuovi. Autorizzano solo nuove strade per
produrre claim testabili.

Il Lab non deve diventare YSN, Cornelius o KSAR. Deve usarli come enzimi
cognitivi dentro il metabolismo D-ND.
