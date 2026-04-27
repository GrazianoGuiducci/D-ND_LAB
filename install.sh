#!/usr/bin/env bash
# D-ND_LAB installer — Phase 0 skeleton
#
# Quick install (target Phase 3):
#   curl -fsSL https://raw.githubusercontent.com/GrazianoGuiducci/D-ND_LAB/main/install.sh | bash
#
# Phase 0: this is a placeholder. Real implementation in Phase 3 will:
#   1. Verify deps (docker, docker-compose)
#   2. Clone the repo to ~/.d-nd-lab or /opt/d-nd-lab (user choice)
#   3. Interactive prompt for: LLM provider, API key, default model, domain
#   4. Generate .env from .env.example with answers filled in
#   5. Run docker compose up -d
#   6. Wait for first health check
#   7. Print URLs for status + report endpoints
#   8. Optionally configure host cron for nightly cycles

set -euo pipefail

echo "D-ND_LAB installer — Phase 0 skeleton"
echo ""
echo "This installer is not yet functional. It is a placeholder for the"
echo "Phase 3 release. To work with the repo today:"
echo ""
echo "  git clone https://github.com/GrazianoGuiducci/D-ND_LAB.git"
echo "  cd D-ND_LAB"
echo "  cp .env.example .env  &&  edit .env"
echo "  docker compose up -d"
echo ""
echo "Track Phase 3 progress: https://github.com/GrazianoGuiducci/D-ND_LAB"
exit 0
