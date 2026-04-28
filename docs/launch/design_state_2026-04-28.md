# Design state — 2026-04-28 (parking note)

> **Crystallization su richiesta operatore.** Stop al ping-pong UI per non
> bloccare lo sviluppo. Lo stato attuale è funzionalmente accettabile per
> il primo test serio. Ci si tornerà in una sessione dedicata di polish
> visivo, dopo aver attaccato Phase 6 v7 (fork mode) e Phase 7 (flip
> pubblico).

## Cosa è in produzione (live https://lab.d-nd.com/dashboard/)

### Layout
- 3-col grid full-page (CAMPO sx · content · DETTAGLIO dx) — pattern Shell3Col
- Sidebars sticky `top:12px`, `max-height:calc(100vh-24px)`, scroll interno indipendente
- Sidebars resizable con drag handle pointer-event-based, persist localStorage
- Sidebar collassabili a 40px con titolo verticale (CAMPO / DETTAGLIO)
- Sidebar collapsed: hover mostra peek tooltip (s3c-tip-portal style)
- Mobile (<1024px): sidebars diventano drawer overlay con backdrop, ESC + body scroll lock, peek edge buttons

### Tab bar
5 tabs: GRAFO · BICONO · AGENTE · TASSONOMIA (era INCROCIO) · INFO

### GRAFO
- Cytoscape force-directed COSE
- Theory pillars Q/T/G/E/R: nodi grandi 42px con lettera centrale (defensive — si attivano quando teoria nodes appariranno)
- Tensione sized by intensity 12..24px
- Edge labels + pair color sui ponti tra teorie
- Labels persistono durante drag (grab/free events)
- Default `showAllLabels=true`
- Dynamic tooltip strutturato (HoverPopover-style) su hover nodo: type + label + verdict + 3 actions (Apri / Esplora / Chat)
- Click nodo → solo sidebar dx (no auto chat)
- Fullscreen modal (bottone ⛶ + tasto F + ESC close)

### BICONO
- Galleria mini-bicono 1/2/3 col responsive
- Filtro "solo completi" (tutti 4 poli parsati)
- Click card → swap a AGENTE con report aperto

### AGENTE
- 2-col grid: list (resizable 200..520, persist) + viewer
- Pane height calc(100vh-200px), scroll indipendente list+viewer
- Lista con badge n_flags + chip falsifier_coherent + 🪦 cimitero icon
- Filter segmented [Tutti / ⚠ Flagged / 🪦 Cimitero]
- Auto-collapse sidebar dx all'apertura report (evita 4-colonne dense)
- Viewer: ToC collapsible (≥3 headings) + falsifier card (diff view claim/evidence) + bicono SVG + markdown
- Empty state con icona ⊙ centrata + caption

### TASSONOMIA
- Sub-mode toggle [⬡ Tassonomia | ↗ Trajectory]
- Tassonomia: Cytoscape compound nodes, group → members, cross-group edges purple
- Backend `/taxonomy` con auto-detect mode 'pillars' (teorie presenti) vs 'flat' (per type)
- Trajectory: SVG timeline cronologica con verdict color + height ∝ n_flags + click card → AGENTE

### INFO
- Identity section (era top intro card)
- "Come si legge la dashboard" guida
- 17 movements chip list
- Reference (repo + formula + version)

### Chat (floating bottom-right)
- THIA-style fab bubble + panel 380x580
- Quick actions per dominio (physics + editorial)
- Tools attivi:
  - **READ**: list_reports, read_report, read_falsifier, read_seed_tension, list_cimitero
  - **PROPOSAL**: propose_inject_tension, propose_run_cycle (UI confirm card amber)
- tool_trace collapsible nei messaggi
- pending_actions render con [Conferma | Annulla]

### Pipeline
- 17 movements registered (incluso `report_falsifier` come terzo incluso post-agent)
- Falsifier 5 lenti tied to assiomi (A2/A4/A8/A12/A14)
- Auto-persist artifacts in `data/{domain}/artifacts/{cycle_ts}/` per ogni run_python/run_bash (no prompt change)
- Endpoint `/falsifier_summary` aggregato per per-lens summary

## Cose visibili da rivedere (NON ora — backlog)

### Layout
- [ ] Su mobile la sidebar dx in overlay potrebbe avere top padding migliore (current OK ma non perfetto)
- [ ] Header sticky potrebbe interferire con sticky sidebar in alcuni breakpoint stretti
- [ ] Tab bar mobile (<640px) ha icon nascosto — potrebbe servire icon-only quando troppo stretto
- [ ] Run-cycle modal ha bisogno di un design più curato (è ancora basic)

### Sidebars
- [ ] Sidebar campo ha un po' di stati inline (Counter-pole, Freschezza, Stats) che potrebbero essere collapsed sections invece di lista lineare
- [ ] La resize bar potrebbe avere un'animazione di "pulse" al primo load per scoprirla all'utente nuovo

### GRAFO
- [ ] Quando il grafo è denso, le label si sovrappongono — manca un'algoritmo anti-overlap (LabGraph del sito ha simulation custom per questo)
- [ ] Highlight today (auto-select del nodo del giorno) non implementato — feature da LabGraph.tsx
- [ ] Pair color edges si attivano solo quando arriveranno ponti tra teorie (defensive ora)
- [ ] Il fullscreen modal è semplice — non ha pannelli laterali (LabGraph fullscreen ha Shell3Col interno con sidebars sx Campo + dx Dettaglio)

### AGENTE
- [ ] Il viewer empty state è migliorato ma la transition list→viewer su mobile è abrupta
- [ ] La lista non ha sort options (è solo per mtime desc)
- [ ] Manca la search/filter per testo nel report

### BICONO
- [ ] Filter per pair non implementato (richiede tag pair nei report → escalation operatore se necessario)
- [ ] Bicono trajectory (come evolve nel tempo) non implementato
- [ ] **Bicono attuale è label-visualizer, non logic-visualizer** — operatore (28/04 sera): "il diagramma del bicono fornisce la logica emergente del ciclo? No". Diagramma SVG strutturalmente invariante (3 cerchi + arco identici per ogni report), solo le 4 label cambiano. Per renderlo emergente serve refactor dinamico: cerchi proporzionali al peso semantico, arc adattivo all'invariante, link visivi alle tensioni d'origine.
- [ ] **Per-domain UI variants**: operatore: "ogni dominio dovrebbe avere una UI studiata per il tipo di esperimento". Quando portiamo un nuovo dominio (operativo, finanziario, ecc.), il bicono e l'intera UI dei tab si specializzano per il tipo di esperimento — non un visualizer universale, ma componenti per-dominio configurabili via `domains/<d>/ui.json` o equivalente.

### TASSONOMIA
- [ ] In flat mode (no teoria), il grafo è banale (solo 2 gruppi) — utile solo quando teoria nodes appariranno
- [ ] Trajectory mode non ha smoothing/clustering quando ci sono molti report
- [ ] Manca il time slider (filtro temporale) sul grafo principale

### Chat
- [ ] Il chat agent ha 6 tool ma solo 2 mutation. Si potrebbe aggiungere `propose_archive_tension` (cimitero), `propose_set_direction` (override seed direction)
- [ ] tool_trace è collapsed di default — alcuni utenti potrebbero volerlo expanded
- [ ] La chat non persiste cross-session (chatMessages state è in memoria, non in storage)

### Falsifier
- [ ] Per-lens summary è in sidebar campo ma richiede n_total_flags > 0 per mostrarsi — aggiungere zero state friendly
- [ ] Diff view (claim vs evidence) è side-by-side ma su mobile collapsa a stack — la visualizzazione 1-col perde l'effetto contrasto
- [ ] Manca un'aggregator endpoint che mostri trend dei flag nel tempo

### Info tab
- [ ] La sezione "Come si legge la dashboard" è hardcoded — potrebbe leggere da `domains/<d>/docs/howto.md`
- [ ] La 17-movements chip list è statica — potrebbe legarsi al config dei movements abilitati per dominio
- [ ] Mancano link a /falsifier_summary, /trajectory, etc. come API explorer

### Generale
- [ ] Niente skeleton/loading state durante fetch iniziale — appare un flash di empty
- [ ] Niente error boundary — se un'API fallisce, l'utente vede silenzio
- [ ] Niente keyboard shortcuts oltre F (fullscreen) e ESC — potrebbero essere utili numeri 1-5 per le tab
- [ ] Theme tuner non implementato (operatore non l'ha richiesto)
- [ ] Glossaria-style tooltip su termini D-ND nel content (kernel, det=−1, etc.) non implementato

## Cosa decisamente NON fare in questa sessione

- Polish iterativo della UI con micro-aggiustamenti
- Inseguire pixel-perfect match al sito d-nd.com (sono prodotti diversi)
- Aggiungere feature non richieste solo perché "il sito ce le ha"
- Refactor del grafo Cytoscape → custom force sim (LabGraph.tsx è 2497 righe, troppo expensive da portare)

## Direzione

Il prodotto è funzionalmente completo per:
- Operatore che usa la dashboard come sostituto del CLI
- Test della pipeline counter-pole (falsifier + opzione 3 artifacts)
- Test della chat operatore con proposal pattern
- Demo a terzi della UI

I prossimi step (per priorità):
1. **Phase 6 v7 — Fork mode** (la specialità — N domini paralleli + convergence map)
2. **Phase 7 — Repo flip privato → pubblico** (decisione operatore)
3. **Phase 8 — Lancio** (README finale + announcement social + HN)
4. Tornare al backlog UI sopra DOPO che il prodotto è stabile e testato

## Riferimenti

- v3_plan.md (Phase 6 v3 piano originale)
- v2_plan.md (Phase 6 v2 piano)
- ui_audit_v4.md (audit completo dei pattern dal sito)
- /opt/d-nd_com/components/Shell3Col.tsx (pattern layout 3-col)
- /opt/d-nd_com/components/LabGraph.tsx (riferimento grafo, 2497 righe)
