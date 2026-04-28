# Phase 6 v2 — piano operativo

> **Crystallized brief.** Scritto prima di iniziare per resilienza
> a crash / compaction. Se la sessione si interrompe, riprendi
> da qui. Direttive operatore 28/04 mattina, dopo test della v1.

## Direttive operatore (verbatim, 28/04)

1. **Grafo/diagramma in primo piano** — funge da mappa logica del
   progetto per navigare le dinamiche, ma anche come dashboard
   operativa per fare le modifiche manuali.

2. **Click su nodo → chat contestuale** — selezionando un punto del
   grafo, il contesto specifico viene iniettato nell'assistente in
   chat. Posso fare domande sul punto selezionato.

3. **Evoluzione del Grafo del Lab di fisica esistente** — il sito
   d-nd.com ha già un grafo che fa da UI al Lab di fisica. Quella è
   la base. Trasferire layout + elementi di visualizzazione +
   integrarli in modi diversi nei punti specifici della dashboard.

4. **Affinare il bicono attuale** — il grafico è poco dinamico e
   mostra concetti fissi (vuoto/pieno) che non sempre si adattano
   alla terminologia in modo coerente. Renderlo dinamico — i 4 poli
   (radici/singolare/invariante/campo) devono adattarsi al contenuto
   del report che stanno filtrando.

5. **Cristallizzare prima di iniziare** — questo documento.

## Vincoli ereditati (memoria locale, 28/04)

- **Riuso > reinventare**: ogni progetto operatore ha già UI / auth /
  CMS / prompt funzionanti. Prima di costruire un componente, cercare
  in /opt/THIA + /opt/d-nd_com + /opt/MM_D-ND + /opt/Godel_DND +
  /opt/d-nd-seed.
- **Cascata A14**: ogni cambio chiedere "cos'altro deve cambiare?".
- **Modus**: espandi (cosa esiste), osserva (cosa il pattern dice),
  taglia (un solo passo per volta), risultante (commit incrementale).
- **Non-dual-copy**: niente apologetic hedging in copy pubblico.
- **Det=-1 sul nodo regressivo**: se trovo un bug, fix dove la
  condizione mancava, non patch sul sintomo.

## Recon obbligatorio prima del build (steps 0-2)

### Step 0 — verificare cosa è "il grafo del Lab di fisica" sul sito

L'operatore ha detto "questa UI sarebbe una evoluzione del Grafo
attuale che fa da UI al Lab di fisica". Candidati:

- `https://d-nd.com/ai-lab` — pagina pubblica del lab D-ND
- `/opt/d-nd_com/src/components/` — componenti React
- Cercare: graph, network, viz, force, knowledge, lab

### Step 1 — verificare il bicono attuale

L'operatore ha detto è statico (concetti fissi vuoto/pieno). Trovare:

- Probabilmente in `/opt/d-nd_com/src/components/`
- O in una pagina specifica che parla di bicono / dipolo

### Step 2 — produrre la mappa "componenti riusabili → punti dashboard"

Una volta visto come è fatto il grafo + bicono, scrivere una mappa:

| Pattern esistente | File | Si può portare in D-ND_LAB? | Adattamenti |
|---|---|---|---|

## Piano step-by-step (dopo recon)

### v2.1 — Grafo come elemento principale della dashboard

- **2.1a**: porta il componente grafo da d-nd.com a D-ND_LAB
  (estrazione + dipendenze). Se è React → la dashboard attuale è
  Alpine.js + Tailwind CDN. Decisione: o aggiungo React come ESM via
  CDN, o riproduco il grafo in vanilla JS / Alpine + una libreria
  graph (cytoscape.js, vis-network, d3-force).
  Preferenza: **Cytoscape.js via CDN** — niente build step, integra
  bene con Alpine, supporta layout force / hierarchical / circular.
- **2.1b**: data source — `/api/domains/{d}/lab_graph` già esiste e
  ritorna nodes + edges. Verificare che il payload sia compatibile
  con il formato Cytoscape.
- **2.1c**: layout in homepage dashboard — il grafo come hero del
  domain dashboard, sostituisce o accompagna la lista tensioni.
- **2.1d**: interazioni base — zoom, pan, hover su nodo (mostra
  label + tipo).

### v2.2 — Click su nodo → chat contestuale

- **2.2a**: click su un nodo `tensione` / `report` / `teoria` → emit
  evento Alpine `selectNode(nodeId, nodeData)`.
- **2.2b**: il chat panel riceve l'evento, prepara il messaggio con
  contesto: "Selected node: <id> (<type>) — <label>" come prefisso.
- **2.2c**: backend `/api/domains/{d}/chat` accetta nuovo campo
  `context_node` opzionale che viene iniettato nel system prompt.
- **2.2d**: UI: badge nel chat input mostrando il nodo selezionato,
  click per deselezionare.

### v2.3 — Bicono dinamico (affina l'esistente)

L'operatore ha detto: "il grafico non molto dinamico e mostra dei
concetti fissi (vuoto pieno) che a volte non si adattano alla
terminologia in modo coerente".

Lettura: il bicono attuale ha labels statiche ai 4 poli. Quando il
report parla di "primi vs Cramér" o "source vs echo", i poli
"vuoto/pieno" non adattano.

Fix: il bicono **legge il bicono nel report stesso** (ho già il
parser in `core/semantic_bridge.py:_extract_bicono`) ed estrae:
- Two roots → 2 labels per i poli orizzontali
- Singular → label centrale
- Invariant → arco
- Field of possibility → quadrante "possible / not-possible"

Ogni bicono è quindi unico per il report. Il visualizer è uno
schema SVG generico riempito coi labels parsed.

### v2.4 — Auth opt-in (magic-link)

Backlog post-v2.3. Quando l'operatore vuole gestire la propria
dashboard sul VPS dal browser senza SSH tunnel.

## Domande aperte da chiarire DURANTE recon (non blocking)

- ~~Il grafo del Lab di fisica usa quale libreria?~~ **Risposto:**
  `/opt/d-nd_com/components/LabGraph.tsx` — 2497 righe, simulazione
  fisica custom (vx/vy/forces a mano), nessuna lib esterna. Troppo
  grosso da portare in toto. Decisione: **Cytoscape.js via CDN** per
  la dashboard, riusando i colori per pair dal sito (coerenza visiva).
- ~~Il bicono attuale è in che pagina/componente?~~ **Risposto:**
  `/opt/d-nd_com/components/diagrams/BiconoLab.tsx` — 1038 righe,
  React, già v2 (galleria di dipoli per ogni scoperta). Ha parser per
  estrarre i due poli da stringa "caldo (...) · freddo (...)". Il fix
  dell'operatore ("statico, vuoto/pieno fissi"): probabilmente è il
  **fallback** quando il bicono nel report è incompleto/assente.
  Affinamento: rimuovere i fallback statici, parsare sempre dal report.
- ~~Compatibilità lab_graph.json formato?~~ Da verificare quando
  porto il graph viz.

## Recon findings (cristallizzati 28/04)

### Pair colors da BiconoLab.tsx (riusabili)

```js
TxQ: '#34d399' (emerald)   GxQ: '#a78bfa' (purple)
ExQ: '#fbbf24' (amber)     ExT: '#f472b6' (pink)
GxT: '#22d3ee' (cyan)      GxE: '#818cf8' (indigo)
QxR: '#fb7185' (rose)      TxR: '#2dd4bf' (teal)
GxR: '#fde047' (yellow)    ExR: '#c084fc' (purple light)
```

Default: `#94a3b8`. Sono i colori per le COPPIE di teorie nel
theory crossing TQGE+R. Nel grafo D-ND_LAB li userò per gli archi
tra teorie + i nodi report che toccano una pair specifica.

### LabGraph.tsx struttura

- Nodi tipizzati: `teoria`, `tensione`, `report`, `ghost`, `discovery`
- 2 modalità: compatta (default) + fullscreen modale
- Click su nodo → apre fullscreen con dettaglio
- Has Shell3Col layout (sidebar sx Campo + grafo + sidebar dx Dettaglio)
- Force simulation custom con tipi diversi di nodo che attraggono/repellono

### BiconoLab.tsx struttura

- Per ogni `Insight` con bicono pieno → mini-bicono SVG
- Parser `parseRadici()` estrae i due poli (left/right) dalla stringa
- Fallback `dipolo` canonico della pair se bicono assente
- ⚠ I fallback statici ("vuoto/pieno", "primi/Cramér" ecc.) sono ciò
  che l'operatore vuole eliminare — usare sempre i campi parsed.

### Mappa "componenti riusabili → punti dashboard"

| Pattern esistente | File | In D-ND_LAB | Adattamento |
|---|---|---|---|
| Force-graph custom | LabGraph.tsx | NO (troppo grosso) | Cytoscape.js via CDN, riusando palette colori |
| Pair colors | BiconoLab.tsx top | SÌ verbatim | Costanti JS nel dashboard frontend |
| Bicono SVG layout | BiconoLab.tsx | SÌ semplificato | SVG inline in Alpine, parsa report markdown |
| parseRadici() | BiconoLab.tsx | SÌ | Porto la regex/parsing in JS dashboard |
| Click node → detail | LabGraph.tsx | SÌ pattern | Alpine event → chat context + side panel |
| Tipi nodo (teoria/tensione/report/ghost) | LabGraph.tsx | SÌ | Cytoscape style per type |

## Ordine di commit (incrementale, ognuno funzionante)

1. `chore(recon): map existing graph + bicono components` (note,
   no code change)
2. `feat(dashboard): port graph viz with cytoscape — physics domain`
3. `feat(dashboard): graph node click → chat context injection`
4. `feat(dashboard): editorial domain graph rendering`
5. `feat(dashboard): dynamic bicono visualizer from parsed reports`
6. `docs: update README + dashboard mockup with v2 features`

Ogni commit deve passare:
- syntax check
- dashboard restart con dati esistenti senza errori
- nessuna regressione su v1 (homepage, seed view, reports, chat)

## Cosa NON fare in v2

- NON ridisegnare il sito d-nd.com (non è scope nostro)
- NON ricostruire il grafo da zero — riusare
- NON aggiungere build step React/Vite (manteniamo zero-build)
- NON toccare il lab fisica VPS originale
- NON portare repo D-ND_LAB pubblico finché operatore non dà luce
- NON committare API keys / .env / corpus content

## Recovery dopo crash

Se la sessione si interrompe:

1. Riprendi questo file
2. Verifica ultimo commit pushato: `git -C /opt/D-ND_LAB log --oneline -5`
3. Verifica stato dashboard: `systemctl is-active d-nd-lab-dashboard`
4. Verifica live: `curl https://lab.d-nd.com/api/health`
5. Continua dal todo list o, se assente, dal punto dove i commit
   si fermano

## Stato iniziale (snapshot 28/04 dopo v1)

- D-ND_LAB repo: `b50bdaf` su main (privato)
- lab-d-nd-site repo: `e7f1196` su main (sito live)
- systemd `d-nd-lab-dashboard.service`: active, demo mode
- nginx proxy: `/dashboard/` + `/api/` → `127.0.0.1:5050`
- Live: `https://lab.d-nd.com/dashboard/` ✓
- Live: `https://lab.d-nd.com/d-nd-lab.html` ✓
- /opt/MM_D-ND/ lab fisica originale: intoccato, cron 03:30 attivo
