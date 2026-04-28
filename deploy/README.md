# Deploy templates

Files for exposing D-ND_LAB on a public domain (Linux host with
nginx + systemd). Adapt the values to your setup.

The reference deployment is `lab.d-nd.com/dashboard/` — public
read-only demo mode, served by uvicorn under systemd, proxied through
nginx that already terminates TLS on the parent domain.

## Files

- **`d-nd-lab-dashboard.service.example`** — systemd unit. Runs
  `python -m core.api` as a long-lived process. Sets host-correct env
  vars (avoid `EnvironmentFile=` because systemd lets it override
  `Environment=` regardless of order — the in-tree `.env` targets
  Docker so its `LAB_DATA_DIR=/data` would shadow our host path).

- **`nginx-dashboard.conf.example`** — two `location` blocks to add
  to an existing nginx server. Forwards `/dashboard/` and `/api/` to
  the systemd-managed uvicorn on `127.0.0.1:5050`. WebSocket-aware so
  the cycle log stream works.

## Setup (assumes nginx already serves your domain over HTTPS)

```bash
# 1. Install the systemd unit
sudo cp deploy/d-nd-lab-dashboard.service.example \
        /etc/systemd/system/d-nd-lab-dashboard.service
sudo nano /etc/systemd/system/d-nd-lab-dashboard.service
# adjust: WorkingDirectory, paths, DASHBOARD_DEMO_MODE (true for
# public read-only / false for operator-only over SSH tunnel)

sudo systemctl daemon-reload
sudo systemctl enable --now d-nd-lab-dashboard.service

# 2. Add the nginx blocks
# Open your existing /etc/nginx/sites-enabled/<your-domain>.conf and
# paste the content of deploy/nginx-dashboard.conf.example BEFORE the
# catch-all `location /` block.

sudo nginx -t && sudo systemctl reload nginx
```

## Verification

```bash
curl https://your-domain.com/api/health
# expect: {"status": "ok", "demo_mode": true, ...}
```

Open `https://your-domain.com/dashboard/` in a browser — you should
see the D-ND_LAB UI with the domains list.

## Demo mode vs operator mode

- **`DASHBOARD_DEMO_MODE=true`** (recommended for public deployments):
  All POST endpoints (run cycle, chat, inject_tension, modify_seed)
  return 403. Visitors browse seed/reports/trajectory/cimitero
  read-only. The dashboard becomes a live showcase of the lab nightly
  output, which is the value for visitors discovering the project.

- **`DASHBOARD_DEMO_MODE=false`** (for the operator's own machine,
  ideally bound to `127.0.0.1` or behind auth): full UI including
  cycle runner, chat with the lab, tension injection. For remote
  access, recommended pattern is SSH tunnel (`ssh -L 5050:127.0.0.1:5050
  user@host`) until magic-link auth is implemented (Phase 6 v2).

## Important: avoid `EnvironmentFile=` for the host systemd unit

The lab's `.env` is shaped for the Docker container (uses
`LAB_DATA_DIR=/data`). The host service needs a different value
(e.g. `/opt/D-ND_LAB/data`). systemd's `EnvironmentFile=` always
overrides `Environment=` regardless of order in the unit file —
documented behavior. So don't add `EnvironmentFile=` to the host
unit; pass the few vars you need via `Environment=`. In demo mode
you don't need the LLM API key at all (POST endpoints are blocked).
