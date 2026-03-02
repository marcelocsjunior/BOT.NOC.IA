#!/usr/bin/env bash
set -u

LOG="/var/log/noc/integrity-check.log"
LAST="/var/log/noc/integrity-last.txt"
TS="$(date '+%F %T %z')"
HOST="$(hostname)"

BASELINE_DIR="/var/lib/noc/baseline"
RELEASES_DIR="/var/lib/noc/releases"

baseline_rc=0
releases_rc=0
result="OK"

{
  echo "=== ${TS} ==="
  echo "HOST=${HOST}"

  echo "--- BASELINE ---"
  if cd "$BASELINE_DIR" 2>/dev/null; then
    if sha256sum -c SHA256SUMS_BASELINE; then
      baseline_rc=0
    else
      baseline_rc=$?
    fi
  else
    echo "BASELINE_DIR: FAILED (cd)"
    baseline_rc=2
  fi

  echo "--- RELEASES ---"
  if cd "$RELEASES_DIR" 2>/dev/null; then
    if sha256sum -c SHA256SUMS; then
      releases_rc=0
    else
      releases_rc=$?
    fi
  else
    echo "RELEASES_DIR: FAILED (cd)"
    releases_rc=2
  fi

  if [[ $baseline_rc -eq 0 && $releases_rc -eq 0 ]]; then
    result="OK"
    echo "RESULT=OK"
  else
    result="FAIL"
    echo "RESULT=FAIL baseline_rc=${baseline_rc} releases_rc=${releases_rc}"
  fi
  echo
} | tee -a "$LOG"

# status “curto” para consumo do bot (sem vazar nada)
{
  echo "TS=${TS}"
  echo "HOST=${HOST}"
  echo "RESULT=${result}"
  echo "BASELINE_RC=${baseline_rc}"
  echo "RELEASES_RC=${releases_rc}"
} > "$LAST"

chown root:adm "$LAST" 2>/dev/null || true
chmod 0644 "$LAST" 2>/dev/null || true

if [[ "${result}" == "OK" ]]; then
  exit 0
fi
exit 1
