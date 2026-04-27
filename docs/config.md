# Configuration

Two layers:

1. **Environment** (`.env`) — runtime parameters: LLM provider, API
   key, paths, schedule
2. **Domain config** (`domains/<name>/config.json`) — per-domain
   wiring: which movements run, which tools are loaded, which params

## Environment variables

Copy `.env.example` to `.env` and edit. The installer does this for
you with interactive prompts.

### LLM

| var | required | default | what it does |
|---|---|---|---|
| `LLM_BASE_URL` | yes | `https://openrouter.ai/api/v1` | OpenAI-compatible endpoint |
| `LLM_API_KEY` | yes | — | Your provider's API key |
| `LLM_MODEL` | yes | — | Model id (e.g. `deepseek/deepseek-v4-pro`) |
| `LLM_PROVIDER` | no | `openrouter` | Label only, doesn't affect the call |
| `LLM_MAX_TURNS` | no | `25` | Hard cap per cycle |
| `LLM_TIMEOUT_SECONDS` | no | `1200` | Whole-loop timeout per cycle |
| `LLM_MAX_COST_USD` | no | unset | Optional cost cap per cycle |

### Lab

| var | required | default | what it does |
|---|---|---|---|
| `LAB_DOMAIN` | yes | `physics` | Active domain (must exist under `domains/`) |
| `LAB_DATA_DIR` | yes | `/data` (in container) | Where state persists |
| `LAB_CRON_SCHEDULE` | no | `30 3 * * *` | Cron expression for `--profile cron` |

### Optional

| var | default | what it does |
|---|---|---|
| `NOTIFY_WEBHOOK_URL` | unset | POST cycle summary as JSON to this URL |
| `MCP_SERVERS` | unset | Comma-separated MCP server URLs (Phase 2.5) |
| `LAB_HTTP_PORT` | `8080` | Port nginx exposes (compose only) |

## Domain config schema

Validated by `config.schema.json` on every load. Your `config.json`
must have:

- `domain` — must match the directory name (`domains/<name>/`)
- `version` — semver string
- `model.context_file` — path to context.md (relative to domain dir)
- `context.data_dir` — subdir under `LAB_DATA_DIR/`
- `tools` — array of tool declarations
- `movements` — per-movement enabled/params

See `config.schema.json` for the full schema and
`domains/physics/config.json` / `domains/editorial/config.json` for
working examples.

### Per-movement params

Each movement entry can have `enabled` (bool) and `params` (object).

```json
"movements": {
  "agent": {
    "enabled": true,
    "params": {
      "min_report_bytes": 1024,
      "tools_override": []
    }
  },
  "structural_check": {
    "enabled": true,
    "params": {
      "inject_meta_tensions": true,
      "patterns_module": "domains.your_name.structural_patterns",
      "scan_files": []
    }
  },
  "trajectory_evaluator": {
    "enabled": true,
    "params": {
      "execute": false,
      "log_only": true,
      "max_turns": 3,
      "timeout_seconds": 300,
      "sources_module": "domains.your_name.trajectory_sources"
    }
  }
}
```

Movement-by-movement parameters (sample — see source for complete):

- `autopsy.params` — none currently
- `build_field.params` — `recent_reports_n`, `observations_path`,
  `registro_path`, `video_feed_path`, `projector_module`,
  `task_section_path`
- `agent.params` — `min_report_bytes`, `tools_override`
- `validate_seed.params` — none currently
- `verify_assertions.params` — `assertions_module`
- `structural_check.params` — `inject_meta_tensions`, `patterns_module`,
  `scan_files`
- `build_lab_data.params` — none currently
- `build_graph.params` — `graph_module`
- `sync.params` — `targets` (array of `{type, ...}`)
- `verify_endpoints.params` — `endpoints` (array of `{url, expect_status}`)
- `refiner.params` — `max_turns`, `timeout_seconds`
- `semantic_bridge.params` — none currently (mapping path is in `model`)
- `refresh_detector.params` — `staleness_days`, `ghost_threshold`,
  `bridges_threshold`, `insights_threshold`, `force`, `regen_module`
- `seed_integrator.params` — `max_tensions`
- `trajectory_evaluator.params` — `execute`, `max_turns`,
  `timeout_seconds`, `sources_module`
- `notify.params` — `webhook_url_env`, `on_success`, `on_error`

## Validation

```bash
dndlab inspect --domain <name>
```

Loads + validates the config + prints the movement table. If something
is malformed, it tells you exactly where the schema check failed.

## Provider switching without code changes

The most useful pattern: keep multiple `.env.<name>` files for
different setups, and switch with a symlink:

```bash
ln -sfn .env.economy .env       # uses DeepSeek V4 Pro
ln -sfn .env.premium .env       # uses Claude Opus 4.7
ln -sfn .env.local .env         # uses Ollama
docker compose down && docker compose up -d
```

The orchestrator and tools don't change. Only the adapter target
changes.
