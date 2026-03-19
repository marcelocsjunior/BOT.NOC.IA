#!/usr/bin/env bash
# Deploy HEAD (working tree) -> VM bot (somente noc_bot/)
set -euo pipefail
source "$(dirname "$0")/_cfg.sh"

cd "$(git rev-parse --show-toplevel)"

# sanity local
python3 -m compileall -q noc_bot

TS="$(date +%F_%H%M%S)"
TMP_REMOTE="/tmp/noc_deploy_${TS}"
BK_REMOTE="${REMOTE_BASE}.bak_${TS}"

echo "== deploy =="
echo "VM_BOT=${VM_BOT_USER}@${VM_BOT_HOST}"
echo "BK=${BK_REMOTE}"

# cria backup remoto (somente noc_bot/) e prepara stage remoto gravável pelo usuário da sessão
ssh_vm "set -euo pipefail
sudo systemctl stop ${REMOTE_SERVICE} || true
sudo mkdir -p \"${BK_REMOTE}\"
sudo cp -a \"${REMOTE_BASE}/noc_bot\" \"${BK_REMOTE}/\" || true
rm -rf \"${TMP_REMOTE}\"
mkdir -p \"${TMP_REMOTE}/noc_bot\"
"

# rsync do noc_bot/ para área temporária
rsync -az --delete -e "ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new" \
  "noc_bot/" "${VM_BOT_USER}@${VM_BOT_HOST}:${TMP_REMOTE}/noc_bot/"

# aplica no destino + gate + start (rollback automático se gate falhar)
ssh_vm "set -euo pipefail
sudo rsync -az --delete \"${TMP_REMOTE}/noc_bot/\" \"${REMOTE_BASE}/noc_bot/\"

if ! sudo python3 -m py_compile ${PY_GATE_FILES[*]}; then
  echo 'ERRO: py_compile falhou -> rollback'
  sudo rsync -az --delete \"${BK_REMOTE}/noc_bot/\" \"${REMOTE_BASE}/noc_bot/\" || true
  rm -rf \"${TMP_REMOTE}\"
  sudo systemctl start ${REMOTE_SERVICE} || true
  exit 2
fi

rm -rf \"${TMP_REMOTE}\"
sudo systemctl start ${REMOTE_SERVICE}
sudo systemctl status ${REMOTE_SERVICE} --no-pager | sed -n '1,22p'
"

echo "OK: deploy"
