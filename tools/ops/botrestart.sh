#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/_cfg.sh"

SINCE="${1:-10 min ago}"
LINES="${2:-160}"

ssh_vm "set -euo pipefail
sudo systemctl stop ${REMOTE_SERVICE} || true

# gate de sintaxe antes de subir
sudo python3 -m py_compile ${PY_GATE_FILES[*]}

sudo systemctl start ${REMOTE_SERVICE}
sudo systemctl status ${REMOTE_SERVICE} --no-pager | sed -n '1,22p'
echo '--- journal tail ---'
sudo journalctl -u ${REMOTE_SERVICE} --since \"${SINCE}\" --no-pager -o cat | tail -n ${LINES}
"
