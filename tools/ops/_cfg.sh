#!/usr/bin/env bash
set -euo pipefail

# Defaults (ajuste via env se quiser)
VM_BOT_HOST="${VM_BOT_HOST:-192.168.1.4}"
VM_BOT_USER="${VM_BOT_USER:-bio}"

REMOTE_BASE="${REMOTE_BASE:-/opt/telegram-bot}"
REMOTE_SERVICE="${REMOTE_SERVICE:-telegram-bot.service}"

# sudo non-interactive (fail-fast). Evita prompt/TTY em SSH.
SUDO_VM="${SUDO_VM:-sudo -n}"

# Arquivos críticos do bot (gate)
PY_GATE_FILES=(
  "$REMOTE_BASE/noc_bot/evidence/builder.py"
  "$REMOTE_BASE/noc_bot/evidence/details.py"
  "$REMOTE_BASE/noc_bot/handlers/commands.py"
)

ssh_vm() { ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "${VM_BOT_USER}@${VM_BOT_HOST}" "$@"; }
scp_vm() { scp -o BatchMode=yes -o StrictHostKeyChecking=accept-new "$@"; }
