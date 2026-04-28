# UI Audit v4 — armamenti dal sito d-nd.com per le varianti lab

> **Audit pre-implementazione.** Risposta operatore 28/04 dopo Phase 6 v3 ship:
> "per la UI ci sono diverse cose che non hai riportato dalla versione lab del
> sito... andrebbe anche fatto un audit delle specifiche per avere tutti gli
> armamenti per una UI allineata nelle diversità delle varianti lab."

Repo audited: `/opt/d-nd_com/components/` (102 componenti React 19 + Tailwind 4
+ Framer Motion 12). I pattern qui valgono per ogni variante lab futura:
physics (live), editorial (live), operativo (Phase 9), finanziario (Phase 10).

Vincoli che restano dal SIC (`/opt/d-nd_com/CLAUDE.md`):
- 5 taglie tipografiche max · phi grid · Bauhaus/Rams/Maeda · spazio come messaggio
- Vanilla HTML + Alpine + Tailwind CDN (zero build) — niente React port literal
- Coerenza palette + identità visiva
- Niente fallback statici nei contenuti — sempre da config/data

## Inventory delle feature dal sito

### A — Layout (Shell3Col.tsx, 743 righe)

| Pattern | Stato D-ND_LAB | Effort | Note |
|---|---|---|---|
| 3-col grid (sidebar sx · main · sidebar dx) | ✓ v3.1 | — | portato in vanilla CSS grid |
| Sidebar collapsible (closed↔open chevron) | ✓ v3.2 | — | toggle Alpine |
| Tabs cross-section | ✓ v3.1 | — | activeTab Alpine state |
| Mobile drawer pattern + peek + backdrop | ✓ v3.10 | — | port completo |
| **Resizable sidebars (drag handle)** | ✗ | M | `s3c-resizer` element con `cursor: col-resize`, drag verso il centro riapre se collapsed. ~80 righe JS in vanilla. |
| **Persist resize state** in localStorage | ✗ | S | save sidebarLeftWidth/sidebarRightWidth |
| **Closed-state tooltip** sui collapsed sidebars | ✗ | M | quando sidebar è chiusa, hover sul gutter mostra il content come popover (HoverPopover) |
| **Touch swipe** per aprire/chiudere drawer mobile | ✗ | M | gesture handler |

### B — Tooltip / HoverPopover (ui/HoverPopover.tsx, 295 righe)

Sistema unificato di tooltip strutturati. Content shape:
```
{ title: string, body: string, link?: {href, label}, related?: [{href, label}], funnelHook?: {href, label} }
```

| Pattern | Stato D-ND_LAB | Effort | Note |
|---|---|---|---|
| Tooltip semplici via `title` HTML | ✓ minimal | — | basic HTML title attr |
| **HoverPopover strutturato** (title/body/link/related/funnelHook) | ✗ | M | richiede positioning logic, escape key, click-outside dismiss |
| **Live data tooltip** (numeri che cambiano nel popover) | ✗ | M | per esempio: hover su "Q teoria" → mostra ultimo report che la tocca + intensity media + n_ponti |
| **Glossario ponte** (termine nostro → termine comune) | ✗ | L | sistema Glossaria del sito (27 entries) — non scope per lab |
| **Tooltip dinamici per nodi grafo** | ✗ | M | hover su nodo Cytoscape → popover con: type chip + title + verdict (se report) + actions (apri/esplora) |

L'operatore: "tooltip dinamiche che strutturano e organizzano i risultati per
una iper-navigazione" → questo è il chunk principale. I tooltip non sono
decoration, sono il livello di navigazione tra hover e click.

### C — LabGraph (LabGraph.tsx, 2497 righe)

Scelta v2: NO React port. Cytoscape.js via CDN. Manteniamo.

| Pattern | Stato D-ND_LAB | Effort | Note |
|---|---|---|---|
| Force-directed layout | ✓ v2.1 | — | cose layout |
| Type-aware node colors | ✓ v2.1 | — | NODE_TYPE_COLOR ported |
| Theory-as-letter (Q/T/G/E/R) | ✓ v3.4 | — | defensive (no teoria nel grafo attuale) |
| Click → chat context | ✓ v2.2 | — | context_node injection |
| **Fullscreen modal** | ✗ | M | LabGraph ha 2 modalità (compatta + fullscreen modale a tutta pagina). Il fullscreen aggiunge spazio per Shell3Col + dettaglio espanso. |
| **Highlight today** (nodo del giorno auto-selezionato) | ✗ | S | data.highlight_today.node_id → cy.fit() su quel nodo |
| **Edge labels** (ponti taggati con costante condivisa) | ✗ | M | quando un ponte ha una costante mostrarla sull'arco |
| **Pair color per archi tra teorie** | ✗ partial | S | abbiamo PAIR_COLOR ma non lo applichiamo a edge style |
| **Filter by maturity** (A/F/C accumulazione/falsifica/candidata) | ✗ | M | filtri toggle nella sidebar campo → grayout dei nodi non matching |
| **Time slider** (mostra il grafo a t=N) | ✗ | L | ricostruisce edges/stats da una snapshot storica |

### D — Multi-view / Tassonomia (LabMultiView.tsx + AutolabView.tsx)

`LabMultiView` ha 4 ViewMode: **overview · domain · trajectory · risultati**.
Pattern tassonomico che l'operatore ha esplicitamente menzionato.

| Pattern | Stato D-ND_LAB | Effort | Note |
|---|---|---|---|
| **OverviewView** — domini come cards (count tensioni, count reports, direzione) | ✓ home v1 | — | abbiamo già la home picker |
| **DomainView** — dettaglio per dominio + multi_scale data | ✓ via tab GRAFO | — | |
| **TrajectoryView** — spirale temporale dei cicli | ✗ | M | ricostruita da reports[].mtime + verdict + bicono — visualizza cammino temporale |
| **RisultatiView** — discoveries/scoperte aggregate | ✗ | M | placeholder per ora — quando build_graph emette teorie/scoperte → cards |
| **Taxonomic graph** (raggruppamento gerarchico per pair/teoria) | ✗ | L | il "grafo d'insieme" che l'operatore ha menzionato. Da seme + condensato del lab, aggrega: tensioni → bicono pair → teoria pillar (Q/T/G/E/R). |
| **Cross-domain trajectory** (tutte le varianti lab in un'unica spirale) | ✗ | L | richiede metadati cross-domain |

### E — Bicono (BiconoLab.tsx + BiconoDiagram.tsx)

| Pattern | Stato D-ND_LAB | Effort | Note |
|---|---|---|---|
| Bicono SVG inline | ✓ v2.3 | — | 4 poli adattivi |
| Galleria mini-bicono | ✓ v3.5 | — | tab BICONO |
| **parseRadici** parser | ✓ | — | port da BiconoLab |
| **No fallback statici** | ✓ | — | regola operatore |
| **Filter per pair** | ✗ | S | dropdown "tutti / TxQ / GxR / ..." → filtra solo bicono di quella pair |
| **Bicono trajectory** (come evolve nel tempo) | ✗ | M | overlay per lo stesso conceptual axis su N report |
| **Cross-axis bicono** (1 bicono per dominio + intersezioni) | ✗ | L | per il futuro fork mode |

### F — Falsifier UI (NEW da v3 + opzione 3)

| Pattern | Stato D-ND_LAB | Effort | Note |
|---|---|---|---|
| Falsifier card sopra report viewer | ✓ post v3 | — | shipped 03b0c49 |
| **Badge nel report list** (count flag) | ✗ | S | accanto alla data nel list item, "⚠ 3 flag" |
| **Filter "show only flagged"** | ✗ | S | toggle nel tab AGENTE |
| **Per-lens summary** (quanti flag per lens nei N report ultimi) | ✗ | M | dashboard del meta-pattern |
| **Diff view** (claim vs evidence side-by-side) | ✗ | M | per ogni flag, render 2-col con highlights |

### G — Misc patterns dal sito utili al lab

| Pattern | Source | Effort | Note |
|---|---|---|---|
| **FalsifiedClaims component** | FalsifiedClaims.tsx (157 righe) | M | abbiamo un cimitero implicito ma nessuna UI dedicata. Questo componente lista discoveries falsificate con motivazione. |
| **InsightsGraphPage** layout | InsightsGraphPage.tsx | M | versione "esplora" del grafo per il pubblico — pattern da imitare per /share del lab |
| **AdminPanel** | AdminPanel.tsx | L | non scope (login + auth = v6) |
| **Theme tuner** (live CSS var manipulation) | ThemeTuner.tsx | L | non scope iniziale |
| **Breadcrumb** per navigazione cross-tab | Breadcrumb.tsx | S | piccolo aggiunta per orientamento |
| **TableOfContents** auto-generato dal markdown | TableOfContents.tsx | M | utile nel report viewer per i report lunghi |

## Effort summary

- **Small (S, ~1-2 ore)**: persist resize state, edge pair colors, filter "only flagged",
  filter per pair su BICONO, badge flag count nel list, breadcrumb,
  highlight today, "show only complete bicono" già fatto.
- **Medium (M, mezza giornata)**: resizable sidebars + drag handle, HoverPopover
  strutturato, dynamic tooltip per nodi grafo, fullscreen modal,
  trajectory view, falsifier per-lens summary, falsifier diff view,
  filter by maturity, FalsifiedClaims tab, TableOfContents.
- **Large (L, 1+ giornata)**: taxonomic graph (la "specialità" che operatore
  ha richiesto), cross-domain trajectory, bicono cross-axis, time slider.

## Dipendenze cross-feature

```
HoverPopover (B) ─┬─> Dynamic tooltip nodi grafo
                  ├─> Closed-state sidebar tooltip
                  └─> Live data tooltip (numeri che cambiano)

Resize (A) ───────┬─> Persist state localStorage
                  └─> Touch swipe mobile (separato ma sinergico)

Taxonomic graph ─┬─> Richiede aggregator backend (groupBy pair / teoria)
                  ├─> Edge labels (D + C)
                  └─> Filter by maturity (C)

Trajectory view ─┬─> Reports timeline
                  ├─> Bicono trajectory (E)
                  └─> Falsifier trend per lens (F)
```

## Scaletta v4 raccomandata

**Priorità alta — UX immediata, low/medium effort:**
1. **v4.1** Resizable sidebars (drag handle + persist) [M]
2. **v4.2** Dynamic tooltip per nodi grafo (HoverPopover-style) [M]
3. **v4.3** Closed-state tooltip per sidebars collassate [M]
4. **v4.4** Filter per pair (BICONO) + filter "only flagged" (AGENTE) + badge flag count [S]
5. **v4.5** Edge labels + pair color per ponti tra teorie [S+M]

**Priorità media — features distinte richieste:**
6. **v4.6** TrajectoryView tab (sostituisce o integra INCROCIO) [M]
7. **v4.7** FalsifiedClaims tab (cimitero esplicito) [M]
8. **v4.8** Falsifier diff view + per-lens summary [M+M]
9. **v4.9** Fullscreen graph modal (LabGraph fullscreen pattern) [M]
10. **v4.10** TableOfContents nel report viewer [M]

**Priorità lunga — la "specialità" tassonomica:**
11. **v4.11** Taxonomic graph (groupBy pair → teoria pillar) [L]
12. **v4.12** Time slider sul grafo [L]
13. **v4.13** Cross-domain trajectory (post fork mode v7) [L]

## Vincoli da preservare

1. Vanilla HTML + Alpine + Tailwind CDN — niente build step
2. Coerenza palette d-nd.com (PAIR_COLOR + NODE_TYPE_COLOR già allineati)
3. Niente fallback statici — sempre da config/data
4. Backend invariato dove possibile — preferire endpoint nuovi a refactor di esistenti
5. Mobile drawer pattern (v3.10) — ogni nuova feature deve essere mobile-first
6. Le 4 tab GRAFO/BICONO/AGENTE/INCROCIO non si moltiplicano senza necessità —
   le nuove feature stanno DENTRO le tab esistenti o sostituiscono INCROCIO
   placeholder con contenuto reale (TrajectoryView può prenderne il posto se
   parlassimo di "incrocio temporale" oltre che teorico)

## Cosa NON fare in v4

- Non portare AdminPanel / auth (v6)
- Non riscrivere lab agent prompt per supportare nuove feature UI
- Non aggiungere build step (Vite, etc.)
- Non duplicare componenti dal sito — creare versioni vanilla/Alpine equivalenti
- Non toccare il copy del sito (escalation)

## Note operatore (verbatim 28/04)

> "altro che poi emerge nell'implementazione di utile, andrebbe anche fatto un
> audit delle specifiche per avere tutti gli armamenti per una UI allineata nelle
> diversità delle varianti lab"

Le varianti lab che l'audit deve servire:
- physics (live, /opt/D-ND_LAB/domains/physics)
- editorial (live, /opt/D-ND_LAB/domains/editorial)
- operativo (Phase 9, dogfooding su THIA)
- finanziario (Phase 10, m_spectro su returns)

Ogni feature qui elencata deve funzionare per tutti e 4 senza rewrite. Se
qualcosa è specifico (es. pair colors TQGE+R sono physics-only), allora il
componente deve degradare graceful (fallback su domain default) oppure
essere skippato via config (`config.json` movement params).
