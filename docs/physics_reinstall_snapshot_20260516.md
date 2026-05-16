# Physics Lab Reinstall Snapshot — 2026-05-16

This document defines the first standalone extraction of the live D-ND Physics
Lab from the THIA/MM-DND workspace into `D-ND_LAB`.

Goal: make the physics Lab reinstallable from a clean clone before generalizing
it into the meta-lab template.

## Boundary

Included:

- active domain: `domains/physics/`
- reusable tool surface: `domains/physics/tools/`
- tracked bootstrap: `domains/physics/bootstrap_20260516/`
- local runtime restore target: `data/physics/`
- optional UI/dashboard support already present in `D-ND_LAB`

Excluded:

- THIA runtime state not needed by the Lab
- dirty MM-DND working tree volume
- local credentials, `.env`, tokens, auth files
- public-site deployment changes

## Bootstrap Cycles

The snapshot uses the last five accepted cycles from the live physics Lab:

| cycle | report | experiment artifact |
|---|---|---|
| `20260516_1117` | `agent_20260516_1117.md` | `anderson3d_mobility_edge_two_reader_audit_20260516_1117.json` |
| `20260516_1135` | `agent_20260516_1135.md` | `anderson3d_comparable_null_audit_20260516_1135.json` |
| `20260516_1148` | `agent_20260516_1148.md` | `boundary_prime_label_null_audit_20260516_1148.json` |
| `20260516_1206` | `agent_20260516_1206.md` | `boundary_residue_label_count_null_audit_20260516_1206.json` |
| `20260516_1230` | `agent_20260516_1230.md` | `boundary_graph_mechanism_ablation_20260516_1230.json` |

Each cycle includes report, falsifier, loop guard, aeternitas, bicono,
incrocio, graph completion, promotion, evolution note and cycle monitor.

## Reinstall Contract

A clean install must be able to:

1. load `physics` as an active domain;
2. restore `data/physics/seed.json`, `lab_data.json` and the latest runtime
   monitor from the bootstrap;
3. inspect the five cycle reports without THIA/MM-DND paths;
4. run `dndlab list`, `dndlab inspect --domain physics` and a dry-run cycle;
5. serve the optional dashboard/UI from the normal `D-ND_LAB` app surface.

## Current Methodology Captured

The extraction carries the methodology learned during the monitored cycles:

- intent lives in movement, not in an externally imposed target;
- combo is the minimal movement container, not a task list;
- local rules are adaptive contracts, not permanent D-ND invariants;
- operational E2E means combo -> cycle -> report -> falsifier -> runtime monitor
  -> UI/public surface;
- the Lab should receive logic and tools, not a prescribed result.

## Restore

From repo root:

```bash
bash scripts/restore_physics_snapshot.sh
python -m core.cli list
python -m core.cli inspect --domain physics
```

Inside Docker, use the CLI command so the snapshot is copied into the Docker
data volume:

```bash
docker compose run --rm lab restore-snapshot --domain physics --snapshot 20260516
docker compose run --rm lab inspect --domain physics
```

The restore script only copies tracked bootstrap files into ignored local
runtime paths under `data/physics/`.

`lab_graph.json` is intentionally not tracked in this snapshot: the live file
contained historical graph content beyond the five-cycle bootstrap. A fresh
runtime should rebuild the graph from reports and current seed state.

## Next Generalization Step

After the physics copy is verified as reinstallable, derive the meta-lab
template from this concrete app:

- domain package contract;
- domain/intention intake contract;
- bootstrap-cycle contract;
- combo/movement contract;
- runtime-awareness report contract;
- optional UI contract;
- public researcher repo packaging.
