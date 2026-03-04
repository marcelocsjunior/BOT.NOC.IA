#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/_cfg.sh"

SINCE="${1:-20 min ago}"
LINES="${2:-160}"

ssh_vm "${SUDO_VM} journalctl -u ${REMOTE_SERVICE} --since \"${SINCE}\" --no-pager -o cat | tail -n ${LINES}"
