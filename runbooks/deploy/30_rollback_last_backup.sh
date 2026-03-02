#!/usr/bin/env bash
set -euo pipefail

APP="/opt/telegram-bot"
SVC="telegram-bot.service"
PY="/home/telegram-bot/venv/bin/python"

LAST="$(ls -1dt /opt/telegram-bot.bak_* 2>/dev/null | head -n 1 || true)"
[ -n "$LAST" ] || { echo "FATAL: não achei /opt/telegram-bot.bak_*"; exit 2; }
[ -d "$LAST/noc_bot" ] || { echo "FATAL: backup sem noc_bot/: $LAST"; exit 2; }

USR="$(systemctl show -p User --value "$SVC" || true)"
[[ -n "$USR" ]] || USR="telegram-bot"

echo "==> Rollback usando: $LAST"
systemctl stop "$SVC"

rsync -a --delete "$LAST/noc_bot/" "$APP/noc_bot/"
chown -R "$USR":"$USR" "$APP/noc_bot"

"$PY" -m py_compile \
  "$APP/noc_bot/handlers/commands.py" \
  "$APP/noc_bot/ui/keyboards.py" \
  "$APP/noc_bot/evidence/builder.py" \
  "$APP/noc_bot/main.py"

systemctl start "$SVC"
echo "OK: rollback aplicado"
