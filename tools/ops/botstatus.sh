#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/_cfg.sh"

ssh_vm "sudo systemctl status ${REMOTE_SERVICE} --no-pager | sed -n '1,25p'"
