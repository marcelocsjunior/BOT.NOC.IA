#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-/home/biotech/Documentos/FASE 2 - BOT_IA_NOC/BOT_ia_NOC_UN1_repo_seed}"
COLLECTOR_HOST="${COLLECTOR_HOST:-192.168.88.108}"
COLLECTOR_USER="${COLLECTOR_USER:-bio}"

REMOTE_BASE="${REMOTE_BASE:-/var/lib/noc/runbooks/deploy}"
REMOTE_DUP="${REMOTE_DUP:-/var/lib/noc/runbooks/deploy/noc_canonic_scripts}"
REMOTE_EVIDENCE="${REMOTE_EVIDENCE:-/var/lib/noc/evidence}"

DUP_OWNER="${DUP_OWNER:-telegram-bot:telegram-bot}"

FILES=(
  "runbooks/deploy/00_bump_env_canonic.sh"
  "runbooks/deploy/20_deploy_zip_canonic.sh"
)

NO_PULL=0
FORCE=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-pull) NO_PULL=1; shift ;;
    --force)   FORCE=1; shift ;;
    -h|--help)
      echo "Uso: $0 [--no-pull] [--force]"
      exit 0
      ;;
    *) echo "Arg inválido: $1"; exit 2 ;;
  esac
done

cd "$REPO_DIR"

if [[ $NO_PULL -eq 0 ]]; then
  git pull --rebase
fi

COMMIT="$(git rev-parse --short HEAD)"
TS="$(date +%F_%H%M%S)"

echo "==> Repo:   $REPO_DIR"
echo "==> HEAD:   $COMMIT"
echo "==> Target: ${COLLECTOR_USER}@${COLLECTOR_HOST}"
echo "==> TS:     $TS"

declare -A LSHA
for f in "${FILES[@]}"; do
  [[ -f "$f" ]] || { echo "FATAL: não encontrei $f"; exit 2; }
  LSHA["$f"]="$(sha256sum "$f" | awk '{print $1}')"
done

# SHA remoto sem sudo (evita sudo sem TTY / drift fantasma)
remote_sha() {
  local p="$1"
  ssh "${COLLECTOR_USER}@${COLLECTOR_HOST}" "sha256sum '$p' 2>/dev/null | awk '{print \$1}'" || true
}

NEED_SYNC=0
for f in "${FILES[@]}"; do
  bn="$(basename "$f")"
  r1="$(remote_sha "${REMOTE_BASE}/${bn}")"
  r2="$(remote_sha "${REMOTE_DUP}/${bn}")"
  if [[ $FORCE -eq 1 ]]; then
    NEED_SYNC=1
  else
    [[ "$r1" == "${LSHA[$f]}" ]] || NEED_SYNC=1
    [[ "$r2" == "${LSHA[$f]}" ]] || NEED_SYNC=1
  fi
done

if [[ $NEED_SYNC -eq 0 ]]; then
  echo "OK: coletor já está alinhado (SHA256 igual em oficial + noc_canonic_scripts). Nada a fazer."
  exit 0
fi

echo "==> Drift detectado (ou --force). Aplicando sync..."

REMOTE_TMP="/tmp/runbooks_sync_${TS}"
ssh "${COLLECTOR_USER}@${COLLECTOR_HOST}" "mkdir -p '$REMOTE_TMP'"

for f in "${FILES[@]}"; do
  scp "$f" "${COLLECTOR_USER}@${COLLECTOR_HOST}:${REMOTE_TMP}/"
done

ssh -tt "${COLLECTOR_USER}@${COLLECTOR_HOST}" bash -s <<REMOTE_SCRIPT
set -euo pipefail

REMOTE_BASE='${REMOTE_BASE}'
REMOTE_DUP='${REMOTE_DUP}'
REMOTE_EVIDENCE='${REMOTE_EVIDENCE}'
REMOTE_TMP='${REMOTE_TMP}'
TS='${TS}'
COMMIT='${COMMIT}'
HOST='ubt'
IP='${COLLECTOR_HOST}'
DUP_USER='${DUP_OWNER%:*}'
DUP_GROUP='${DUP_OWNER#*:}'

# oficiais
sudo install -m 0755 "\$REMOTE_TMP/00_bump_env_canonic.sh" "\$REMOTE_BASE/00_bump_env_canonic.sh"
sudo install -m 0755 "\$REMOTE_TMP/20_deploy_zip_canonic.sh" "\$REMOTE_BASE/20_deploy_zip_canonic.sh"

# duplicados
sudo mkdir -p "\$REMOTE_DUP"
sudo install -o "\$DUP_USER" -g "\$DUP_GROUP" -m 0755 "\$REMOTE_BASE/00_bump_env_canonic.sh" "\$REMOTE_DUP/00_bump_env_canonic.sh"
sudo install -o "\$DUP_USER" -g "\$DUP_GROUP" -m 0755 "\$REMOTE_BASE/20_deploy_zip_canonic.sh" "\$REMOTE_DUP/20_deploy_zip_canonic.sh"

echo "==> Gate check (fatal - noise)"
grep -nE 'egrep -i|egrep -vi|BadRequest|400 Bad Request|parse entities' \
  "\$REMOTE_BASE/00_bump_env_canonic.sh" \
  "\$REMOTE_BASE/20_deploy_zip_canonic.sh" \
  "\$REMOTE_DUP/00_bump_env_canonic.sh" \
  "\$REMOTE_DUP/20_deploy_zip_canonic.sh"

echo "==> Drift=0 (oficial vs dup)"
diff -u "\$REMOTE_BASE/00_bump_env_canonic.sh" "\$REMOTE_DUP/00_bump_env_canonic.sh" | head -n 5 || true
diff -u "\$REMOTE_BASE/20_deploy_zip_canonic.sh" "\$REMOTE_DUP/20_deploy_zip_canonic.sh" | head -n 5 || true

SHA_OUT=\$(sha256sum \
  "\$REMOTE_BASE/00_bump_env_canonic.sh" \
  "\$REMOTE_BASE/20_deploy_zip_canonic.sh" \
  "\$REMOTE_DUP/00_bump_env_canonic.sh" \
  "\$REMOTE_DUP/20_deploy_zip_canonic.sh")

# evidência (tee) + owner
sudo mkdir -p "\$REMOTE_EVIDENCE"

sudo tee "\$REMOTE_EVIDENCE/runbooks_sync_\$TS.meta" >/dev/null <<META_EOF
SYNC_RUNBOOKS_AT=\$TS
COMMIT=\$COMMIT
HOST=\$HOST
IP=\$IP

\$SHA_OUT
META_EOF

printf '%s\n' "\$SHA_OUT" | sudo tee "\$REMOTE_EVIDENCE/runbooks_sync_\$TS.sha256" >/dev/null
sudo chown "\$DUP_USER:\$DUP_GROUP" "\$REMOTE_EVIDENCE/runbooks_sync_\$TS.meta" "\$REMOTE_EVIDENCE/runbooks_sync_\$TS.sha256"
sudo ls -lah "\$REMOTE_EVIDENCE/runbooks_sync_\$TS."*

echo "OK: sync aplicado. Evidence: \$REMOTE_EVIDENCE/runbooks_sync_\$TS.(meta|sha256)"
REMOTE_SCRIPT

echo "OK: sync finalizado (commit=$COMMIT)."
