#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BOOTSTRAP="$ROOT/domains/physics/bootstrap_20260516"
TARGET="$ROOT/data/physics"

if [[ ! -d "$BOOTSTRAP" ]]; then
  echo "Missing bootstrap directory: $BOOTSTRAP" >&2
  exit 1
fi

mkdir -p "$TARGET/reports" "$TARGET/bootstrap_20260516"

cp -a "$BOOTSTRAP/." "$TARGET/bootstrap_20260516/"
cp -a "$BOOTSTRAP/reports/." "$TARGET/reports/"
cp -a "$BOOTSTRAP/state/seed.json" "$TARGET/seed.json"
cp -a "$BOOTSTRAP/state/lab_data.json" "$TARGET/lab_data.json"
cp -a "$BOOTSTRAP/ui/lab_cycle_monitor_latest.json" "$TARGET/lab_cycle_monitor_latest.json"

if [[ -f "$BOOTSTRAP/state/lab_graph.json" ]]; then
  cp -a "$BOOTSTRAP/state/lab_graph.json" "$TARGET/lab_graph.json"
else
  rm -f "$TARGET/lab_graph.json"
fi

echo "Physics snapshot restored into $TARGET"
