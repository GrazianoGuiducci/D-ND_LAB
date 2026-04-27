#!/usr/bin/env bash
# D-ND_LAB installer — one-liner setup.
#
# Quick install:
#   curl -fsSL https://raw.githubusercontent.com/GrazianoGuiducci/D-ND_LAB/main/install.sh | bash
#
# What it does:
#   1. Verifies docker + docker compose are installed
#   2. Clones the repo to ~/.d-nd-lab (or $LAB_HOME if set)
#   3. Interactive prompts for: LLM_API_KEY, LLM_MODEL, LAB_DOMAIN
#   4. Generates .env from .env.example with answers filled in
#   5. Builds the image + starts services with docker compose
#   6. Prints status URLs
#
# Re-run safe: detects existing install and offers to update or reconfigure.

set -euo pipefail

# ── Constants ───────────────────────────────────────────────────────
REPO_URL="${REPO_URL:-https://github.com/GrazianoGuiducci/D-ND_LAB.git}"
LAB_HOME="${LAB_HOME:-$HOME/.d-nd-lab}"
DEFAULT_PORT="${LAB_HTTP_PORT:-8080}"

C_RESET='\033[0m'
C_BOLD='\033[1m'
C_DIM='\033[2m'
C_RED='\033[31m'
C_GREEN='\033[32m'
C_YELLOW='\033[33m'
C_BLUE='\033[34m'

say()  { printf '%b\n' "$*"; }
ok()   { say "${C_GREEN}✓${C_RESET} $*"; }
warn() { say "${C_YELLOW}!${C_RESET} $*" >&2; }
err()  { say "${C_RED}✗${C_RESET} $*" >&2; }
hdr()  { say "\n${C_BOLD}${C_BLUE}── $* ──${C_RESET}"; }

# ── Step 1: prerequisites ──────────────────────────────────────────
hdr "Checking prerequisites"

if ! command -v docker >/dev/null 2>&1; then
    err "Docker not found. Install: https://docs.docker.com/get-docker/"
    exit 1
fi
ok "docker: $(docker --version)"

if ! docker compose version >/dev/null 2>&1; then
    err "Docker Compose plugin not found. Install: https://docs.docker.com/compose/install/"
    exit 1
fi
ok "docker compose: $(docker compose version --short)"

if ! command -v git >/dev/null 2>&1; then
    err "git not found. Install via your package manager."
    exit 1
fi

# ── Step 2: clone or update ────────────────────────────────────────
hdr "Repository"

if [ -d "$LAB_HOME/.git" ]; then
    say "${C_DIM}Existing install detected at $LAB_HOME${C_RESET}"
    read -r -p "Update from upstream? [Y/n] " ans
    if [[ ! "$ans" =~ ^[Nn] ]]; then
        git -C "$LAB_HOME" pull --ff-only
        ok "Repo updated"
    fi
else
    say "Cloning to $LAB_HOME"
    git clone --depth 1 "$REPO_URL" "$LAB_HOME"
    ok "Repo cloned"
fi

cd "$LAB_HOME"

# ── Step 3: configure .env ─────────────────────────────────────────
hdr "Configuration"

if [ -f .env ]; then
    say "${C_DIM}.env already exists — keeping current values.${C_RESET}"
    say "${C_DIM}To reconfigure, delete .env and re-run.${C_RESET}"
else
    if [ ! -f .env.example ]; then
        err ".env.example missing — repository may be incomplete"
        exit 1
    fi
    cp .env.example .env

    # Prompt for required values
    say ""
    say "${C_BOLD}LLM API key${C_RESET}"
    say "${C_DIM}Get one at: https://openrouter.ai/keys (or your chosen provider)${C_RESET}"
    read -r -s -p "  Paste key (input hidden): " api_key
    say ""
    if [ -z "$api_key" ]; then
        err "API key is required."
        exit 1
    fi

    say ""
    say "${C_BOLD}Model${C_RESET}"
    say "${C_DIM}Browse current models: https://openrouter.ai/models${C_RESET}"
    say "${C_DIM}Press Enter to keep default from .env.example${C_RESET}"
    read -r -p "  LLM_MODEL [keep default]: " model

    say ""
    say "${C_BOLD}Domain${C_RESET}"
    say "${C_DIM}Available: physics, editorial${C_RESET}"
    read -r -p "  LAB_DOMAIN [physics]: " domain
    domain="${domain:-physics}"

    # Write values into .env (in-place edit, preserving comments)
    # Use Python for safe escaping rather than sed (handles special chars in keys)
    python3 - "$api_key" "$model" "$domain" .env <<'PY'
import sys
from pathlib import Path
api_key, model, domain, env_path = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
lines = Path(env_path).read_text().splitlines()
out = []
for line in lines:
    if line.startswith("LLM_API_KEY="):
        out.append(f"LLM_API_KEY={api_key}")
    elif line.startswith("LLM_MODEL=") and model:
        out.append(f"LLM_MODEL={model}")
    elif line.startswith("LAB_DOMAIN="):
        out.append(f"LAB_DOMAIN={domain}")
    else:
        out.append(line)
Path(env_path).write_text("\n".join(out) + "\n")
PY
    chmod 600 .env
    ok "Wrote .env (chmod 600 — readable only by you)"
fi

# ── Step 4: build + start ──────────────────────────────────────────
hdr "Build + start"

say "${C_DIM}Building image (first time may take 1-3 minutes)...${C_RESET}"
docker compose build --pull
ok "Image built"

say "${C_DIM}Starting services...${C_RESET}"
docker compose up -d nginx
ok "nginx running on port ${DEFAULT_PORT}"

# ── Step 5: smoke test ────────────────────────────────────────────
hdr "Smoke test"

# Validate config without spending API credits
say "Running config validation (dry-run)..."
if docker compose run --rm lab dry-run --domain "${domain:-physics}" >/tmp/dndlab-dryrun.log 2>&1; then
    ok "Dry-run cycle completed (0 errors)"
else
    warn "Dry-run had errors — see /tmp/dndlab-dryrun.log"
    tail -20 /tmp/dndlab-dryrun.log
fi

# ── Done ───────────────────────────────────────────────────────────
hdr "Done"

say "Installation complete. ${C_BOLD}D-ND_LAB${C_RESET} is ready."
say ""
say "  Working dir:  ${C_DIM}$LAB_HOME${C_RESET}"
say "  Reports URL:  ${C_BOLD}http://localhost:${DEFAULT_PORT}/data/reports/${C_RESET}"
say ""
say "Next steps:"
say "  ${C_DIM}# Run one cycle (will call your LLM provider — costs apply)${C_RESET}"
say "  cd $LAB_HOME && docker compose run --rm lab"
say ""
say "  ${C_DIM}# Enable scheduled cycles (cron mode)${C_RESET}"
say "  cd $LAB_HOME && docker compose --profile cron up -d"
say ""
say "  ${C_DIM}# Inspect domain status${C_RESET}"
say "  cd $LAB_HOME && docker compose run --rm lab status --domain ${domain:-physics}"
say ""
say "Docs: https://github.com/GrazianoGuiducci/D-ND_LAB"
