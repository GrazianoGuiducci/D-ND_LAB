# Narrative viewpoints — come dire le cose giuste a chi guarda

> **Scopo**: mappa la stessa cosa (lab autonomo D-ND_LAB) in copy
> appropriata per ognuno dei 7 viewpoint che possono incontrarla.
> Niente assoluti universali, niente apologetic hedging, niente
> silent patching del concetto su cui si parla. La stessa regola
> che applichiamo al producer del lab si applica alla copy stessa.
>
> **Versione**: bozza vivente — aggiornata mentre il sistema cresce.
> Origine: 29/04/2026, dopo che l'operatore ha chiesto "come cambia
> la descrizione di quello che facciamo per farlo capire a chi non
> sa cosa è sui diversi punti di vista".

---

## La cosa che si descrive

Un sotto-dominio (`lab.d-nd.com`) che ospita un sistema cognitivo
autonomo: un agente LLM che ogni notte sceglie una tensione di
ricerca, fa un esperimento, scrive un report, viene auto-corretto
da un secondo polo asimmetrico, viene falsificato da un terzo
polo, e il risultato che resiste viene depositato come scoperta o
archiviato come claim falsificato. La struttura è universale: il
codice è agnostico al dominio, il contenuto specifico (assiomi,
fonti, dati) viene iniettato per ogni installazione.

Sotto questa cosa singola ci sono **molti modi di dirla**.

---

## Viewpoint 1 — Visitatore casuale

**Chi è**: arriva da un link condiviso, un'AI, una ricerca SEO. Non
sa cosa sia D-ND. Ha 8 secondi di attenzione.

**Tagline**:
> "Un sistema che fa ricerca da solo. Pensa, scrive, critica se
> stesso. Quello che vedi è ciò che ha scoperto e ciò che ha
> scartato."

**3-frase pitch (top page)**:
1. Questo è un laboratorio autonomo. Ogni notte sceglie una domanda,
   prova a rispondere, e si fa criticare da un secondo cervello prima
   di pubblicare.
2. I report che vedi sono passati attraverso quel filtro. Quelli che
   non hanno superato il filtro sono nel cimitero — uno per dominio.
3. La struttura sotto è generica: lo stesso sistema può girare su
   matematica, finanza, biologia. Qui sta girando su fisica/matematica.

**Cosa NON dire qui**:
- "A8 autologica esterna" — gergo
- "det = -1 dipolare" — formula senza contesto
- "fork-mode v7" — versioning interno
- "kernel iniziale per ASI" — troppo grande troppo presto
- Liste di assiomi prima del perché

**Cosa fa: mostragli, non dirgli**. Una scoperta, un cimitero, un
falsifier flag visualizzato. Il sistema racconta la storia, non la copy.

---

## Viewpoint 2 — Curioso tecnico/scientifico

**Chi è**: legge paper, capisce LLM agents, vuole vedere
implementazione concreta vs vaporware. Ha 5 minuti.

**Tagline**:
> "Producer-critic asimmetrico con counter-pole dotato di 5 lenti
> strutturali. Output che superano il filtro entrano in un seme
> che evolve cycle-su-cycle. Codice aperto, lenti documentate."

**Pitch**:
1. **Il pattern**: agent multi-turn (producer, exploratory framing) →
   bias_corrector (skeptical framing, stesso o altro modello) →
   report_falsifier (counter-pole, 5 lenti tied to assiomi) →
   trajectory_evaluator (decide CRYSTALLIZE/REDESIGN/...). A8
   autologica iterativa.
2. **Le 5 lenti** non sono regole arbitrarie: sono modi di guardare
   tied a proprietà del modello (hard constraint vs bias, ratio vs
   absolute, axiom continuity, edge case isolation, re-discovery
   vs discovery). Filtro semantico non keyword-based.
3. **Costo**: bridge chain codex→claude→openrouter sposta i 4
   movement bare su account subscription, OpenRouter solo per
   l'agent multi-turn. ~−60% chiamate billed nei nostri test.

**Cosa NON dire qui**:
- "Fa ricerca da solo" da solo — è troppo generico, vogliono pattern
- "Sistema cognitivo autonomo" senza arch — vaporware feeling
- Slogan filosofici prima del codice

**Cosa fa: link al repo + 1 esempio concreto** di rewrites del
corrector + 1 falsifier output con coherent=False + summary tagliente.

---

## Viewpoint 3 — Imprenditore / buyer custom lab

**Chi è**: gestisce un dominio (finanza, biologia, ricerca aziendale,
strategy), cerca strumenti che producano insight ricorrenti senza
l'overhead di team dedicato. Ha 2 minuti, vuole valore traducibile
in tempo/denaro.

**Tagline**:
> "Lab autonomi per il tuo dominio. Tu definisci la domanda, il
> sistema lavora ogni notte e produce report che hanno già passato
> un filtro di critica strutturale."

**Pitch**:
1. **Cosa risolve**: serve a chi ha bisogno di esplorazione continua
   in un dominio specifico ma non può permettersi un team che ci
   pensi 24/7. Il lab gira da solo, accumula scoperte e le filtra.
2. **Dimostrazione**: questo lab.d-nd.com gira su matematica/fisica
   come prova del sistema. Stesso codice, dati e assiomi diversi,
   altro dominio. La barriera è la definizione del dominio, non la
   tecnologia.
3. **Modalità**: open-source per chi installa da sé; template +
   consulenza per chi vuole versione custom configurata sul suo
   dominio (intervista guidata, definizione assiomi, primo cycle
   supervisionato, attivazione cron).

**Cosa NON dire qui**:
- "Producer-critic asimmetrico" — gergo
- Promesse di scoperte specifiche — tu non sai cosa il loro
  dominio produrrà
- "Risolve il problema X" come assoluto — bias L1

**Cosa fa: case study di cosa il lab matematica ha trovato + scartato
in 30 cycle. Mostra i numeri, mostra il cimitero. Il fatto che il
sistema scarti cose è un asset, non un difetto.**

---

## Viewpoint 4 — Sviluppatore / AI engineer

**Chi è**: lavora con LLM, vuole capire architettura, eventualmente
forkare o contribuire. Ha tempo per il README ma non per gli slogan.

**Tagline**:
> "17 movements, domain-agnostic core, contenuti per dominio, bridge
> chain LLM, A8 autologica iterativa. MIT license. Issue tracker
> aperto."

**Pitch**:
1. **Architettura**: `core/` espone `lab_agent.py` con MOVEMENT_ORDER
   + register_movement contract. Ogni movement è un modulo Python che
   legge/scrive `CycleContext`. `domains/<dom>/` ha `context.md`,
   `assertions.py`, `seed_tensions.json`. Tutto agnostico al dominio.
2. **LLM adapter**: openai SDK con base_url configurabile. Bridge route
   per chiamate bare via THIA `/api/llm/chat/completions` (codex+claude
   subscription chain). Movement con tools restano su provider LLM
   diretto.
3. **Pattern di estensione**: nuovo movement = un file in `core/` che
   chiama `register_movement(name, fn)` + entry in MOVEMENT_ORDER.
   Nuovo dominio = una directory in `domains/` con i 4-5 file richiesti.

**Cosa NON dire qui**:
- "Rivoluzionario" — claim L1 senza dato
- Vaghezze su modelli supportati — siano specifici (deepseek, claude,
  openrouter)
- Numeri di performance senza repo dei test

**Cosa fa: link diretto al repo, alla cartella `docs/`, al
`INSTALL_PROCEDURE.md`. Diff fra ultime release. Il dev valuta dal
codice.**

---

## Viewpoint 5 — Filosofo / ricercatore di logica

**Chi è**: incontra D-ND attraverso il sito principale, ha letto il
manifesto, capisce dipolare-vs-duale. Vede il lab come prova
empirica di un'idea filosofica.

**Tagline**:
> "Un sistema che parte da un assioma dipolare e produce ciò che
> sopravvive alla propria critica. Il filtro non è imposto — è il
> contrario asimmetrico del produttore."

**Pitch**:
1. **Il modus**: il producer cerca pattern (det=+1, costruttivo). Il
   counter-pole cerca inconsistenze (det=−1, destruttivo). La
   risultante è ciò che resiste a entrambi. È dipolare nella
   struttura, non nelle intenzioni.
2. **Il cimitero**: ciò che il sistema scarta non scompare. Resta
   come memoria del filtro. Un sistema senza cimitero non sa
   calibrarsi — sa solo confermare.
3. **L'autologica**: il bias_corrector applica le stesse lenti del
   counter-pole **internamente**, prima del verdetto. Producer →
   self-critic → counter-pole. Tre poli che lavorano sulla stessa
   risultante. È A8 — il sistema chiede a se stesso la stessa
   domanda da angoli diversi.

**Cosa NON dire qui**:
- Pure tech speak — perde il punto
- "Produce verità" — bias L1, il sistema produce ciò-che-resiste
- Entusiasmo senza sostanza

**Cosa fa: collega il lab al manifesto. Mostra come la teoria si
incarna nel codice. Cita i 16 assiomi quando rilevante.**

---

## Viewpoint 6 — Sistema (futuro lab generato, agente esterno)

**Chi è**: un altro lab nel network, un agente AI che consulta il
lab via API, una pipeline esterna. Vuole contract, schema, latenza,
SLA.

**Tagline**:
> "OpenAPI 3 endpoint live su `/api/`. CycleContext schema
> stabile. Bridge chain documentata. Rate limits pubblici."

**Pitch**:
1. **API surface**: 21+ endpoint REST. `/api/domains/<d>/seed`,
   `/reports`, `/falsifier_summary`, `/corrector_summary`,
   `/biconi`, `/cimitero`, `/lab_graph`, `/digest` (futuro).
   WebSocket `/cycles/<id>/log` per streaming.
2. **Auth**: X-THIA-Token o admin session. Rate limits per provider
   downstream (OpenRouter token bucket, bridge concurrency 2).
3. **Stabilità contract**: schema versioning in
   `/api/health` (`version: 0.1.0-alpha`). Movement registry
   stabile, nuovi movement aggiunti tail-of-list senza rotture.

**Cosa NON dire qui**:
- Marketing copy — irrelevant
- Storia / contesto — bypass

**Cosa fa: OpenAPI spec auto-generata, link a `docs/api.md`, esempi
curl + risposte JSON.**

---

## Viewpoint 7 — Potenziale collaboratore D-ND

**Chi è**: ha letto il manifesto, vuole contribuire al progetto.
Filosofo, dev, ricercatore. Cerca dove agganciarsi.

**Tagline**:
> "Codice aperto, modello in evoluzione, primi N lab in collaudo
> con l'operatore. Punti d'aggancio: assiomi del modello, lenti
> del falsifier, domini di applicazione."

**Pitch**:
1. **Cosa serve**: estensione delle lenti del falsifier (oggi 5,
   tied a A2/A4/A8/A12/A14 — ne mancano per A6, A11, A14, A16).
   Domini diversi (finance, biology, linguistica) con assertions.py
   e tensioni iniziali di ricercatori del campo.
2. **Come contribuire**: PR sul repo, issue per discussione,
   intervista LLM-guided per definire un nuovo dominio (in arrivo
   su `dev.d-nd.com/labs/new`).
3. **Modus**: prima di proporre, applica le 5 lenti al tuo
   contributo. Se il tuo claim non resiste alle stesse lenti che
   applichiamo ai report, va al cimitero come tutti gli altri.

**Cosa NON dire qui**:
- Promesse di compenso senza struttura
- Inviti vaghi — sii specifico su cosa serve

**Cosa fa: pagina contribute con assi precisi (lenti / domini /
codice / docs), link al CONTRIBUTING.md, info su come parlare con
l'operatore (mailto:info@d-nd.com).**

---

## Cosa cambia tra viewpoint — la vista a colpo d'occhio

| Viewpoint | Cosa è | Perché interessa | Cosa fai con loro |
|-----------|--------|------------------|-------------------|
| 1 Casuale | "sistema che pensa da solo" | curiosità | mostragli un esempio |
| 2 Tecnico | "producer-critic asimmetrico" | implementazione | rimandi al repo + esempio |
| 3 Buyer | "lab custom per il tuo dominio" | valore tradotto | case study + intervista |
| 4 Dev | "17 movements + bridge chain" | architettura | repo + docs + diff |
| 5 Filosofo | "incarnazione del dipolare" | prova empirica | collega al manifesto |
| 6 Sistema | "21 endpoint REST" | contract | OpenAPI + esempi |
| 7 Collaboratore | "punti d'aggancio aperti" | come unirsi | contribute page |

Stessa cosa, sette story, sette CTA. La copy giusta è quella che
**non confonde** un viewpoint con un altro.

---

## Anti-pattern di copy (le 5 lenti applicate alla narrazione)

Le stesse lenti che il falsifier usa sui report del lab si applicano
alla copy che descrive il lab. Niente di speciale: è auto-applicazione.

**L1 — Assoluto su biased data (copy)**:
- ❌ "Il sistema produce sempre scoperte verificate"
- ✓ "Il sistema produce report; quelli che superano il counter-pole
  entrano nel seme; quelli che non lo superano vanno al cimitero"

**L2 — Ratio vs absolute (copy)**:
- ❌ "60% di efficienza in più rispetto al lavoro manuale"
  (rispetto a cosa esattamente, su quale base?)
- ✓ "−60% chiamate OpenRouter rispetto al cycle senza bridge chain
  (cycle 1 vs 2 sul demo, 23 vs 9 chiamate)"

**L3 — Silent patching (copy)**:
- ❌ Pagina parte promettendo "ricerca scientifica autonoma", finisce
  parlando di "framework filosofico"
- ✓ Se il framing si sposta, dichiararlo: "il lab è applicazione del
  modello D-ND filosofico in dominio scientifico — i due livelli
  vivono insieme"

**L4 — Edge case rounded (copy)**:
- ❌ "Tutti i lab installati funzionano in autonomia"
- ✓ "I lab installati con la procedura completa funzionano in
  autonomia; il primo cycle controllato dall'operatore valida la
  configurazione"

**L5 — Re-discovery vs discovery (copy)**:
- ❌ "Sistema cognitivo autonomo — primo nel suo genere"
- ✓ "Sistema cognitivo autonomo nel pattern producer-critic
  asimmetrico applicato con 5 lenti tied to model axioms. La
  letteratura ha cose simili (constitutional AI, debate, ...);
  cosa è specifico qui è il counter-pole tied to D-ND axioms"

---

## Note operative

### Quando una copy va in più viewpoint

A volte la stessa pagina viene letta da viewpoint diversi. Strategia:

1. **Layered disclosure**: hero per Viewpoint 1, sezione tecnica
   apribile per Viewpoint 2, link laterale per Viewpoint 4.
2. **Tagline universale + body specifico**: la tagline può essere
   astratta abbastanza da non escludere nessuno ("un sistema che
   pensa e si critica") ma la body si specializza per chi continua
   a leggere.
3. **Testimonianze targeted**: una testimonianza di un buyer (V3)
   convince più del pitch sui buyer. Una citazione di un dev (V4)
   convince più del pitch sui dev.

### Cosa evitare in TUTTI i viewpoint

- Sigle senza spiegazione (CEC, A8, V7, Bicono — espandi prima volta)
- Promesse non misurate ("efficienza", "potenza", "rivoluzione")
- Hedge apologetico ("forse", "in qualche modo", "potrebbe")
- Ego del sistema ("io penso che", "il lab crede che" — il lab non crede,
  produce report che resistono)

### Aggiornamento del documento

Ogni volta che il sistema cresce (nuovo movement, nuova capability,
nuovo dominio), questo doc si aggiorna. La narrazione non è statica
— evolve con il prodotto. Ma evolve **dichiarando il cambiamento**,
non per silent patching.

---

*Origine: 29/04/2026, dopo che il cycle test del demo physics era in
corso e l'operatore ha chiesto di mappare la narrazione multi-lente
mentre aspettavamo. La stessa regola del lab applicata alla copy del lab.*
