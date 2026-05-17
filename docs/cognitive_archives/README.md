# Cognitive Archives

> Capsule portabili per usare archivi cognitivi esterni senza dipendere dai
> path locali del VPS e senza consumare subito tutta la finestra di contesto.

## Perche' esistono

La repo pubblica non puo' assumere che una nuova istanza abbia accesso a:

- `/opt/skill`;
- `/opt/KPhi1`;
- `/opt/d-nd_cockpit/docs/system/kernel`;
- altri archivi THIA/MMSp locali.

Queste capsule salvano nella repo il livello minimo che serve per progettare:

- provenance;
- quando consultare la fonte;
- pattern gia' estratti;
- contaminazioni da evitare;
- cosa bisogna ancora leggere se il pattern entra in un Lab reale.

Non sostituiscono i file completi. Evitano di leggerli tutti prima di sapere
quali servono.

## Regola di uso

```text
capsula -> candidate pattern -> body read if needed -> transduction -> E2E
```

Una capsula puo' orientare il meta-lab. Non puo' rendere autoritativa una
skill, un meta-prompt o una procedura se il corpo reale non e' disponibile o
non e' stato letto al livello richiesto.

## File

- `archive_capsule.v1.json`: schema logico delle capsule.
- `kphi1_omega_kernel_20260517.json`: distillato KPhi1.
- `thia_skill_snapshot_20260517.json`: distillato `/opt/skill`.
- `cockpit_mmsp_lineage_20260517.json`: mappa lineage cockpit/MMSp.

## Output nel meta-lab

Quando il meta-lab usa una capsula, deve produrre `archive_retrieval`:

```json
{
  "archive_id": "kphi1_omega_kernel",
  "capsule": "docs/cognitive_archives/kphi1_omega_kernel_20260517.json",
  "pattern": "local_genome_context",
  "read_depth": "CAPSULE|BODY|BODY_PLUS_REFS|E2E",
  "used_for": "context.md|mml.json|tool|assertion|ui_contract|new_skill|veto",
  "body_required": true,
  "body_source": "external repo/path/url or vendored source",
  "contamination_excluded": "language/persona/domain-specific content",
  "test_expected": "how the generated Lab proves the pattern is active"
}
```

## Quando creare un agente dedicato

Se una nuova istanza deve leggere molti file completi, non deve caricarli tutti
nel main context. Deve usare un agente/worker di tipo **Archive Curator**:

1. legge solo l'archivio assegnato;
2. produce una capsula aggiornata;
3. elenca quali file completi sono necessari per il dominio corrente;
4. non propone output di dominio;
5. non modifica MML/context del Lab figlio senza passare dal meta-lab.

Il main agent usa la capsula come filtro; legge i corpi completi solo per i
pattern effettivamente selezionati.
