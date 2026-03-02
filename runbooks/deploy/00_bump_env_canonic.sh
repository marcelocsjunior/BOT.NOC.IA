#!/usr/bin/env bash
set -euo pipefail

APP="/opt/telegram-bot"
ENV_FILE="$APP/.env"
SVC="telegram-bot.service"

TS="$(date +%F_%H%M%S)"
BUILD_ID="$TS"

# Você pode sobrescrever via env var BOT_VER_PREFIX.
# Ex.: BOT_VER_PREFIX="2026-02-28-dm-group-ux" ./00_bump_env_canonic.sh
BOT_VER_PREFIX="${BOT_VER_PREFIX:-$(date +%F)-dm-group-ux}"
BOT_VERSION="${BOT_VER_PREFIX}|build=${BUILD_ID}"

[ -f "$ENV_FILE" ] || { echo "FATAL: não achei $ENV_FILE"; exit 2; }

echo "==> 0) Backup do .env"
cp -a "$ENV_FILE" "$ENV_FILE.bak_${TS}"

echo "==> 1) Upsert BOT_VERSION + BUILD_ID no .env"
python3 - <<PY
from pathlib import Path
import re

p = Path("$ENV_FILE")
lines = p.read_text(encoding="utf-8").splitlines()

BOT_VERSION = "${BOT_VERSION}"
BUILD_ID = "${BUILD_ID}"

keys = {"BOT_VERSION": BOT_VERSION, "BUILD_ID": BUILD_ID}

for k, v in keys.items():
    pat = re.compile(rf"^{re.escape(k)}=")
    for i, ln in enumerate(lines):
        if pat.match(ln):
            lines[i] = f"{k}={v}"
            break
    else:
        lines.append(f"{k}={v}")

p.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
print("OK:", "BOT_VERSION="+BOT_VERSION)
print("OK:", "BUILD_ID="+BUILD_ID)
PY

echo "==> 2) Restart do bot (reler .env)"
systemctl restart "$SVC"

echo "==> 3) Sanity log (5 min)"
journalctl -u "$SVC" --since "5 min ago" --no-pager -o cat \
 | egrep -i "Traceback|IndentationError|SyntaxError|ERROR|CRITICAL" \
 | egrep -vi "BadRequest|400 Bad Request|parse entities" \
 && { echo "FATAL: erros relevantes no log"; exit 1; } \
 || echo "OK: .env bump aplicado e serviço reiniciado sem erros relevantes"

echo "Backup do .env: $ENV_FILE.bak_${TS}"