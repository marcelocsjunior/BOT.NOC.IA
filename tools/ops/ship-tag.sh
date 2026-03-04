#!/usr/bin/env bash
# Deploy de um TAG específico (sem mexer em checkout) -> VM bot
set -euo pipefail
source "$(dirname "$0")/_cfg.sh"

TAG="${1:?uso: ship-tag.sh <tag>}"
cd "$(git rev-parse --show-toplevel)"

TS="$(date +%F_%H%M%S)"
TMP_LOCAL="$(mktemp -d)"
TAR_LOCAL="${TMP_LOCAL}/ship_${TAG}_${TS}.tar.gz"
TMP_REMOTE="/tmp/noc_ship_${TS}"
BK_REMOTE="${REMOTE_BASE}.bak_${TS}"

echo "== ship-tag =="
echo "TAG=${TAG}"
echo "VM_BOT=${VM_BOT_USER}@${VM_BOT_HOST}"
echo "BK=${BK_REMOTE}"

git archive --format=tar "${TAG}" noc_bot | gzip -9 > "${TAR_LOCAL}"

ssh_vm "set -euo pipefail
sudo systemctl stop ${REMOTE_SERVICE} || true
sudo mkdir -p \"${BK_REMOTE}\"
sudo cp -a \"${REMOTE_BASE}/noc_bot\" \"${BK_REMOTE}/\" || true
sudo mkdir -p \"${TMP_REMOTE}\"
"

scp_vm "${TAR_LOCAL}" "${VM_BOT_USER}@${VM_BOT_HOST}:${TMP_REMOTE}/ship.tar.gz"

ssh_vm "set -euo pipefail
cd \"${TMP_REMOTE}\"
tar xzf ship.tar.gz

sudo rsync -az --delete \"${TMP_REMOTE}/noc_bot/\" \"${REMOTE_BASE}/noc_bot/\"

if ! sudo python3 -m py_compile ${PY_GATE_FILES[*]}; then
  echo 'ERRO: py_compile falhou -> rollback'
  sudo rsync -az --delete \"${BK_REMOTE}/noc_bot/\" \"${REMOTE_BASE}/noc_bot/\" || true
  exit 2
fi

sudo systemctl start ${REMOTE_SERVICE}
sudo systemctl status ${REMOTE_SERVICE} --no-pager | sed -n '1,22p'
"
echo "OK: ship-tag ${TAG}"
