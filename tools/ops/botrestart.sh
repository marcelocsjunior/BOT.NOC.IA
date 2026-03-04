#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/_cfg.sh"

SINCE="${1:-10 min ago}"
LINES="${2:-160}"

ssh_vm "set -euo pipefail
SUDO="sudo -n"
if ! ${SUDO} -v >/dev/null 2>&1; then echo "SUDOERS DRIFT: faltam regras NOPASSWD em /etc/sudoers.d/noc-ops" >&2; exit 77; fi
sudo -n systemctl stop ${REMOTE_SERVICE} || true

# gate de sintaxe antes de subir
sudo -n python3 -m py_compile ${PY_GATE_FILES[*]}

sudo -n systemctl start ${REMOTE_SERVICE}
sudo -n systemctl status ${REMOTE_SERVICE} --no-pager | sed -n '1,22p'
echo '--- journal tail ---'
sudo -n journalctl -u ${REMOTE_SERVICE} --since \"${SINCE}\" --no-pager -o cat | tail -n ${LINES}
"
