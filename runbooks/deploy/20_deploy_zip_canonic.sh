#!/usr/bin/env bash
set -euo pipefail

# Deploy canônico: aplica SOMENTE noc_bot/ (preserva bot.py/.env/venv)
# Uso:
#   sudo ./20_deploy_zip_canonic.sh /tmp/noc_bot_multiunit_fixed.zip

ZIP="${1:-/tmp/noc_bot_multiunit_fixed.zip}"
APP="/opt/telegram-bot"
SVC="telegram-bot.service"
PY="/home/telegram-bot/venv/bin/python"

TS="$(date +%F_%H%M%S)"
BAK="/opt/telegram-bot.bak_${TS}"
STAGE="/tmp/noc_patch_${TS}"

command -v unzip >/dev/null
command -v rsync >/dev/null

[ -f "$ZIP" ] || { echo "FATAL: ZIP não encontrado: $ZIP"; exit 2; }
[ -d "$APP/noc_bot" ] || { echo "FATAL: não achei $APP/noc_bot"; exit 2; }
[ -x "$PY" ] || { echo "FATAL: não achei python do venv em $PY"; exit 2; }

echo "==> 0) Precheck ZIP (noc_bot/ na raiz)"
unzip -l "$ZIP" | awk '{print $4}' | grep -q '^noc_bot/' || { echo "FATAL: ZIP não contém noc_bot/ na raiz"; exit 2; }

USR="$(systemctl show -p User --value "$SVC" || true)"
[[ -n "$USR" ]] || USR="telegram-bot"

echo "==> 1) Stop service"
systemctl stop "$SVC"

echo "==> 2) Backup (preserva bot.py/.env; salva noc_bot)"
mkdir -p "$BAK"
cp -a "$APP/bot.py" "$BAK/" 2>/dev/null || true
cp -a "$APP/.env"  "$BAK/" 2>/dev/null || true
rsync -a --delete "$APP/noc_bot/" "$BAK/noc_bot/"

echo "==> 3) Stage unzip"
rm -rf "$STAGE"; mkdir -p "$STAGE"
unzip -q "$ZIP" -d "$STAGE"
[ -d "$STAGE/noc_bot" ] || { echo "FATAL: stage sem noc_bot/"; exit 2; }

echo "==> 4) Apply (rsync noc_bot -> /opt)"
rsync -a --delete "$STAGE/noc_bot/" "$APP/noc_bot/"
chown -R "$USR":"$USR" "$APP/noc_bot"

echo "==> 5) Sanity compile"
"$PY" -m py_compile \
  "$APP/noc_bot/evidence/builder.py" \
  "$APP/noc_bot/ui/keyboards.py" \
  "$APP/noc_bot/handlers/callbacks.py" \
  "$APP/noc_bot/handlers/commands.py" \
  "$APP/noc_bot/handlers/chat.py" \
  "$APP/noc_bot/ui/panels.py" \
  "$APP/noc_bot/telegram_ui.py" \
  "$APP/noc_bot/main.py"

echo "==> 6) Start + sanity logs"
systemctl start "$SVC"

journalctl -u "$SVC" --since "10 min ago" --no-pager -o cat \
 | egrep -i "Traceback|IndentationError|SyntaxError|BadRequest|400 Bad Request|parse entities|ERROR|CRITICAL" \
 && { echo "FATAL: erros relevantes no log"; exit 1; } \
 || echo "OK: deploy aplicado sem erros relevantes"

echo "Backup gerado em: $BAK"
