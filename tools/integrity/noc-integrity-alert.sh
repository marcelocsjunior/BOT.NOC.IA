#!/usr/bin/env bash
set -euo pipefail

MODE="${MODE:-FAIL}"                       # FAIL | TEST
CHAT_ID="${CHAT_ID:?CHAT_ID not set}"
LOG_PATH="${LOG_PATH:-/var/log/noc/integrity-check.log}"
ENV_FILE="${ENV_FILE:-/opt/telegram-bot/.env}"

# Token: preferir env (systemd EnvironmentFile), senão ler direto do .env
TOKEN="${TELEGRAM_BOT_TOKEN:-}"
if [[ -z "${TOKEN}" && -r "${ENV_FILE}" ]]; then
  TOKEN="$(grep -E '^TELEGRAM_BOT_TOKEN=' "${ENV_FILE}" | tail -n 1 | cut -d= -f2-)"
fi

# Sanitização: CR/whitespace/aspas externas
TOKEN="$(printf '%s' "${TOKEN}" | tr -d '\r' | sed -e 's/^[[:space:]]*//; s/[[:space:]]*$//')"
if [[ "${TOKEN:0:1}" == '"' && "${TOKEN: -1}" == '"' ]]; then TOKEN="${TOKEN:1:${#TOKEN}-2}"; fi
if [[ "${TOKEN:0:1}" == "'" && "${TOKEN: -1}" == "'" ]]; then TOKEN="${TOKEN:1:${#TOKEN}-2}"; fi
[[ -n "${TOKEN}" ]] || { echo "FATAL: TELEGRAM_BOT_TOKEN vazio" >&2; exit 2; }

HOST="$(hostname)"
TS="$(date '+%F %T %z')"

# DETAILS: pega SOMENTE o último ciclo (do último "=== " até o fim)
DETAILS="$(
  awk 'BEGIN{buf=""} /^=== /{buf=""} {buf=buf $0 "\n"} END{printf "%s", buf}' "$LOG_PATH" \
  | egrep -n "FAILED|WARNING|did NOT match|NOT match|No such file|Permission denied" || true
)"
[[ -n "${DETAILS}" ]] || DETAILS="N/D (sem linhas FAILED/WARNING no último ciclo do log)"

if [[ "${MODE}" == "TEST" ]]; then
  ICON="🟦"
  TITLE="NOC Integrity ALERT (TEST)"
else
  ICON="🔴"
  TITLE="NOC Integrity FAIL"
fi

MSG="$(cat <<MSGEOF
${ICON} ${TITLE}
UN1 | host=${HOST}
TS=${TS}

${DETAILS}

Log: ${LOG_PATH}
Ação: sudo systemctl start noc-integrity-check.service
MSGEOF
)"

curl -fsS \
  --data-urlencode "chat_id=${CHAT_ID}" \
  --data-urlencode "text=${MSG}" \
  "https://api.telegram.org/bot${TOKEN}/sendMessage" >/dev/null
