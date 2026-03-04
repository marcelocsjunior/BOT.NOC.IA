#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/_cfg.sh"

TAG="${1:-v2026.03.04-evidence-ux}"

cd "$(git rev-parse --show-toplevel)"

files=(
  "noc_bot/evidence/builder.py"
  "noc_bot/evidence/details.py"
  "noc_bot/handlers/commands.py"
)

for f in "${files[@]}"; do
  exp="$(git show "${TAG}:${f}" | sha256sum | awk '{print $1}')"
  got="$(ssh_vm "sha256sum \"${REMOTE_BASE}/${f}\"" | awk '{print $1}')"
  status="OK"; [[ "$exp" == "$got" ]] || status="DRIFT"
  printf "%-35s  %s\n" "$f" "$status"
  [[ "$status" == "OK" ]] || {
    echo "  exp=$exp"
    echo "  got=$got"
    exit 2
  }
done

echo "DRIFT=0 (VM bot == ${TAG})"
