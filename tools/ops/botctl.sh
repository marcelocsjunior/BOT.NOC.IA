#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
OPS_DIR="$ROOT/tools/ops"

usage() {
  cat <<USAGE
uso: $(basename "$0") <acao> [args]

Ações:
  status                      -> status remoto do bot
  log [since] [lines]         -> journal do bot (default: "20 min ago" 160)
  restart [since] [lines]     -> restart remoto + gate + journal
  inspect                     -> drift check runtime VM bot vs clone local
  reconcile                   -> reconciliar clone local com runtime da VM bot (commit local, sem push)
  drift [tag]                 -> drift por tag (script legado)
  ship-tag <tag>              -> deploy de tag para VM bot
  deploy                      -> deploy do HEAD/working tree para VM bot
  where                       -> mostra host/user/base/service carregados de _cfg.sh
  help                        -> ajuda

Exemplos:
  $(basename "$0") status
  $(basename "$0") log "30 min ago" 200
  $(basename "$0") restart "10 min ago" 80
  $(basename "$0") inspect
  $(basename "$0") reconcile
USAGE
}

require_file() {
  local f="$1"
  [[ -f "$f" ]] || { echo "ERRO: arquivo não encontrado: $f" >&2; exit 2; }
}

ACTION="${1:-help}"
shift || true

CFG="$OPS_DIR/_cfg.sh"
require_file "$CFG"
# shellcheck source=/dev/null
source "$CFG"

run() {
  local target="$1"
  shift || true
  require_file "$target"
  "$target" "$@"
}

case "$ACTION" in
  status)
    run "$OPS_DIR/botstatus.sh" "$@"
    ;;
  log)
    run "$OPS_DIR/botlog.sh" "$@"
    ;;
  restart)
    run "$OPS_DIR/botrestart.sh" "$@"
    ;;
  inspect)
    run "$OPS_DIR/reconcile-runtime.sh" inspect "$@"
    ;;
  reconcile)
    run "$OPS_DIR/reconcile-runtime.sh" reconcile "$@"
    ;;
  drift)
    run "$OPS_DIR/drift.sh" "$@"
    ;;
  ship-tag)
    run "$OPS_DIR/ship-tag.sh" "$@"
    ;;
  deploy)
    run "$OPS_DIR/deploy.sh" "$@"
    ;;
  where)
    cat <<OUT
VM_BOT_HOST=$VM_BOT_HOST
VM_BOT_USER=$VM_BOT_USER
REMOTE_BASE=$REMOTE_BASE
REMOTE_SERVICE=$REMOTE_SERVICE
OPS_DIR=$OPS_DIR
OUT
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    echo "ERRO: ação inválida: $ACTION" >&2
    echo >&2
    usage >&2
    exit 2
    ;;
esac
