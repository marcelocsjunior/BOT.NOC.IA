#!/usr/bin/env bash
set -euo pipefail

# Idempotente: só aplica se SHA256 divergir (oficial + noc_canonic_scripts).
# Autônomo: puxa git, sync via scp+ssh, valida gate/diff/sha256 e grava evidência no coletor.

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

usage() {
  cat <<USAGE
Uso:
  $0 [--no-pull] [--force]

Vars (opcionais):
  REPO_DIR=...
  COLLECTOR_HOST=...
  COLLECTOR_USER=...
  REMOTE_BASE=...
  REMOTE_DUP=...
  REMOTE_EVIDENCE=...
  DUP_OWNER=...

Exemplos:
  $0
  $0 --force
  $0 --no-pull
USAGE
}

NO_PULL=0
FORCE=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-pull) NO_PULL=1; shift ;;
    --force) FORCE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Arg inválido: $1"; usage; exit 2 ;;
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

# SHA local
declare -A LSHA
for f in "${FILES[@]}"; do
  [[ -f "$f" ]] || { echo "FATAL: arquivo não encontrado no repo: $f"; exit 2; }
  LSHA["$f"]="$(sha256sum "$f" | awk '{print $1}')"
done

# SHA remoto SEM sudo (arquivos 0755; evita sudo sem TTY e "drift fantasma")
remote_sha() {
  local remote_path="$1"
  ssh "${COLLECTOR_USER}@${COLLECTOR_HOST}" "sha256sum '$remote_path' 2>/dev/null | awk '{print \$1}'" || true
}

NEED_SYNC=0
for f in "${FILES[@]}"; do
  bn="$(basename "$f")"
  r_off="$(remote_sha "${REMOTE_BASE}/${bn}")"
  r_dup="$(remote_sha "${REMOTE_DUP}/${bn}")"

  if [[ $FORCE -eq 1 ]]; then
    NEED_SYNC=1
  else
    [[ "$r_off" == "${LSHA[$f]}" ]] || NEED_SYNC=1
    [[ "$r_dup" == "${LSHA[$f]}" ]] || NEED_SYNC=1
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

# Aplica no coletor (precisa sudo lá)
ssh -tt "${COLLECTOR_USER}@${COLLECTOR_HOST}" bash -s <<REMOTE_EOF
set -euo pipefail

REMOTE_BASE="${REMOTE_BASE}"
REMOTE_DUP="${REMOTE_DUP}"
REMOTE_EVIDENCE="${REMOTE_EVIDENCE}"
DUP_OWNER="${DUP_OWNER}"
REMOTE_TMP="${REMOTE_TMP}"
TS="${TS}"
COMMIT="${COMMIT}"
HOST="ubt"
IP="${COLLECTOR_HOST}"

# aplica oficiais
sudo install -m 0755 "\$REMOTE_TMP/00_bump_env_canonic.sh" "\$REMOTE_BASE/00_bump_env_canonic.sh"
sudo install -m 0755 "\$REMOTE_TMP/20_deploy_zip_canonic.sh" "\$REMOTE_BASE/20_deploy_zip_canonic.sh"

# aplica duplicados
sudo mkdir -p "\$REMOTE_DUP"
sudo install -o "\${DUP_OWNER%:*}" -g "\${DUP_OWNER#*:}" -m 0755 \
  "\$REMOTE_BASE/00_bump_env_canonic.sh" "\$REMOTE_DUP/00_bump_env_canonic.sh"
sudo install -o "\${DUP_OWNER%:*}" -g "\${DUP_OWNER#*:}" -m 0755 \
  "\$REMOTE_BASE/20_deploy_zip_canonic.sh" "\$REMOTE_DUP/20_deploy_zip_canonic.sh"

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

# evidência garantida (tee) + owner
sudo mkdir -p "\$REMOTE_EVIDENCE"
sudo tee "\$REMOTE_EVIDENCE/runbooks_sync_\$TS.meta" >/dev/null <<EOF
SYNC_RUNBOOKS_AT=\$TS
COMMIT=\$COMMIT
HOST=\$HOST
IP=\$IP

\$SHA_OUT
