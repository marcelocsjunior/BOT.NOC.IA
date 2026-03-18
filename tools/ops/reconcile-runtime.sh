#!/usr/bin/env bash
# Reconcile runtime implantado na VM bot -> clone local (sem push)
# Padrão: reconcile automático + evidência + commit local
set -euo pipefail

source "$(dirname "$0")/_cfg.sh"

MODE="${1:-reconcile}"   # inspect | reconcile
RUN_ID="$(date +%F_%H%M%S)"
RECON_BASE="${RECON_BASE:-_reconcile}"
RECON_DIR="${RECON_BASE}/${RUN_ID}"
LOCAL_SNAPSHOT_DIR="${RECON_DIR}/local_before"
VM_SNAPSHOT_DIR="${RECON_DIR}/vm_runtime"
MANIFEST_DIR="${RECON_DIR}/manifests"
EVIDENCE_FILE="${RECON_DIR}/reconcile_runtime.txt"
DELTA_FILE="${RECON_DIR}/delta.txt"
TAR_VM="${RECON_DIR}/vm_runtime.tar.gz"
COMMIT_PREFIX="${COMMIT_PREFIX:-chore(reconcile)}"
IGNORE_DIRS=("__pycache__" ".pytest_cache" ".mypy_cache")

usage() {
  cat <<USAGE
uso: $(basename "$0") [inspect|reconcile]

Modos:
  inspect     baixa snapshot da VM, compara com o clone local e gera evidência
  reconcile   (padrão) baixa snapshot da VM, atualiza noc_bot/ local e faz commit local sem push

Variáveis opcionais:
  RECON_BASE     base dos artefatos locais (default: _reconcile)
  COMMIT_PREFIX  prefixo da mensagem de commit (default: chore(reconcile))
USAGE
}

log() { printf '[reconcile-runtime] %s\n' "$*"; }
fail() { printf '[reconcile-runtime] ERRO: %s\n' "$*" >&2; exit 1; }

case "$MODE" in
  inspect|reconcile) ;;
  -h|--help|help) usage; exit 0 ;;
  *) fail "modo inválido: ${MODE}" ;;
esac

cd "$(git rev-parse --show-toplevel)"

CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
CURRENT_HEAD="$(git rev-parse --short HEAD 2>/dev/null || true)"
if [[ -z "$CURRENT_BRANCH" || "$CURRENT_BRANCH" == "HEAD" ]]; then
  CURRENT_BRANCH="DETACHED"
fi

mkdir -p "$LOCAL_SNAPSHOT_DIR" "$VM_SNAPSHOT_DIR" "$MANIFEST_DIR"

# Segurança: não reconciliar em cima de alterações locais soltas em noc_bot/
if ! git diff --quiet -- noc_bot || ! git diff --cached --quiet -- noc_bot; then
  fail "clone local com alterações pendentes em noc_bot/. Commit/stash primeiro para evitar sobrescrita acidental."
fi

if [[ ! -d noc_bot ]]; then
  fail "pasta local noc_bot/ não encontrada no clone atual"
fi

manifest_dir() {
  local src="$1"
  local out="$2"
  (
    cd "$src"
    find . \
      \( -type d \( -name '__pycache__' -o -name '.pytest_cache' -o -name '.mypy_cache' \) -prune \) -o \
      \( -type f ! -name '*.pyc' -print0 \)
  ) | sort -z | while IFS= read -r -d '' f; do
    local rel="${f#./}"
    local sha
    sha="$(sha256sum "$src/$rel" | awk '{print $1}')"
    printf '%s  %s\n' "$sha" "$rel"
  done > "$out"
}

make_delta() {
  local a="$1"
  local b="$2"
  local out="$3"
  python3 - "$a" "$b" <<'PY' > "$out"
import json, os, sys
from pathlib import Path

def read_manifest(path):
    data = {}
    with open(path, 'r', encoding='utf-8') as fh:
        for line in fh:
            line = line.rstrip('\n')
            if not line:
                continue
            sha, rel = line.split('  ', 1)
            data[rel] = sha
    return data

a = read_manifest(sys.argv[1])
b = read_manifest(sys.argv[2])
all_paths = sorted(set(a) | set(b))
for p in all_paths:
    if p not in a:
        print(f"ADDED_IN_VM   {p}")
    elif p not in b:
        print(f"MISSING_IN_VM {p}")
    elif a[p] != b[p]:
        print(f"CHANGED       {p}")
PY
}

log "coletando snapshot local"
rsync -a --delete "noc_bot/" "${LOCAL_SNAPSHOT_DIR}/noc_bot/"

log "coletando snapshot da VM bot ${VM_BOT_USER}@${VM_BOT_HOST}:${REMOTE_BASE}/noc_bot"
ssh_vm "set -euo pipefail
if ! ${SUDO_VM} /usr/bin/tar --version >/dev/null 2>&1; then echo 'SUDOERS DRIFT: falta NOPASSWD para /usr/bin/tar em /etc/sudoers.d/noc-ops' >&2; exit 77; fi
${SUDO_VM} /usr/bin/tar -C \"${REMOTE_BASE}\" -czf - noc_bot
" > "$TAR_VM"

tar -C "$VM_SNAPSHOT_DIR" -xzf "$TAR_VM"
[[ -d "${VM_SNAPSHOT_DIR}/noc_bot" ]] || fail "snapshot remoto inválido: noc_bot/ não foi extraído"

manifest_dir "${LOCAL_SNAPSHOT_DIR}/noc_bot" "${MANIFEST_DIR}/local.manifest"
manifest_dir "${VM_SNAPSHOT_DIR}/noc_bot" "${MANIFEST_DIR}/vm.manifest"
make_delta "${MANIFEST_DIR}/local.manifest" "${MANIFEST_DIR}/vm.manifest" "$DELTA_FILE"

STATE="IN_SYNC"
if ! cmp -s "${MANIFEST_DIR}/local.manifest" "${MANIFEST_DIR}/vm.manifest"; then
  STATE="DRIFT"
fi

CHANGED_COUNT="$(wc -l < "$DELTA_FILE" | tr -d ' ')"

{
  echo "RUN_ID=${RUN_ID}"
  echo "MODE=${MODE}"
  echo "STATE=${STATE}"
  echo "VM_BOT_HOST=${VM_BOT_HOST}"
  echo "VM_BOT_USER=${VM_BOT_USER}"
  echo "REMOTE_BASE=${REMOTE_BASE}"
  echo "SERVICE=${REMOTE_SERVICE}"
  echo "SCOPE=noc_bot/"
  echo "LOCAL_BRANCH=${CURRENT_BRANCH}"
  echo "LOCAL_HEAD=${CURRENT_HEAD}"
  echo "CHANGED_FILES=${CHANGED_COUNT}"
  echo "RECON_DIR=${RECON_DIR}"
  echo "LOCAL_MANIFEST=${MANIFEST_DIR}/local.manifest"
  echo "VM_MANIFEST=${MANIFEST_DIR}/vm.manifest"
  echo "DELTA_FILE=${DELTA_FILE}"
  echo "--- DELTA ---"
  if [[ -s "$DELTA_FILE" ]]; then
    cat "$DELTA_FILE"
  else
    echo "SEM_DIFERENCAS"
  fi
} > "$EVIDENCE_FILE"

log "evidência: ${EVIDENCE_FILE}"

if [[ "$MODE" == "inspect" ]]; then
  cat "$EVIDENCE_FILE"
  if [[ "$STATE" == "DRIFT" ]]; then
    exit 10
  fi
  exit 0
fi

if [[ "$STATE" == "IN_SYNC" ]]; then
  cat "$EVIDENCE_FILE"
  log "clone local já está alinhado com o runtime da VM bot"
  exit 0
fi

log "aplicando runtime da VM bot sobre noc_bot/ local"
rsync -a --delete "${VM_SNAPSHOT_DIR}/noc_bot/" "noc_bot/"

log "gate local: compileall noc_bot"
python3 -m compileall -q noc_bot

log "git add noc_bot/"
git add --all -- noc_bot

COMMIT_MSG="${COMMIT_PREFIX}: sync noc_bot from VM bot runtime (${VM_BOT_HOST}) [no-push]"
if git diff --cached --quiet -- noc_bot; then
  log "nenhuma mudança staged após rsync; encerrando"
  cat "$EVIDENCE_FILE"
  exit 0
fi

log "commit local automático (sem push)"
git commit -m "$COMMIT_MSG" --no-verify
NEW_HEAD="$(git rev-parse --short HEAD)"

{
  echo
  echo "--- RESULTADO ---"
  echo "ACTION=RECONCILED_LOCAL"
  echo "COMMIT=${NEW_HEAD}"
  echo "COMMIT_MESSAGE=${COMMIT_MSG}"
  echo "PUSH=NAO_EXECUTADO"
} >> "$EVIDENCE_FILE"

cat "$EVIDENCE_FILE"
log "ok: clone local reconciliado com a VM bot; GitHub remoto não foi alterado"
