#!/usr/bin/env bash
set -euo pipefail

# Build release ZIP canônico (staging → patches → compile → zip)
# Default OUT: /tmp/noc_bot_multiunit_fixed.zip
# Default SRC: /opt/telegram-bot/noc_bot (diretório)
# Alternativa SRC: informe um ZIP como 2º argumento.

OUT_ZIP="${1:-/tmp/noc_bot_multiunit_fixed.zip}"
SRC="${2:-/opt/telegram-bot/noc_bot}"

APP="/opt/telegram-bot"
PY="/home/telegram-bot/venv/bin/python"

TS="$(date +%F_%H%M%S)"
STAGE="/tmp/noc_release_${TS}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PATCH_DIR="$SCRIPT_DIR/patches"

command -v rsync >/dev/null
command -v unzip >/dev/null
command -v zip >/dev/null
command -v patch >/dev/null

[ -x "$PY" ] || { echo "FATAL: não achei python do venv em $PY"; exit 2; }

rm -rf "$STAGE"; mkdir -p "$STAGE"

echo "==> 1) Staging source -> $STAGE"
if [ -f "$SRC" ]; then
  echo "SRC=ZIP: $SRC"
  unzip -q "$SRC" -d "$STAGE"
else
  echo "SRC=DIR: $SRC"
  [ -d "$SRC" ] || { echo "FATAL: SRC não existe: $SRC"; exit 2; }
  mkdir -p "$STAGE/noc_bot"
  rsync -a --delete "$SRC/" "$STAGE/noc_bot/"
fi

[ -d "$STAGE/noc_bot" ] || { echo "FATAL: staging sem noc_bot/"; exit 2; }

echo "==> 2) Aplicando patches (canônico)"
if [ -d "$PATCH_DIR" ]; then
  shopt -s nullglob
  patches=("$PATCH_DIR"/*.patch)
  if [ ${#patches[@]} -eq 0 ]; then
    echo "(sem patches)"
  else
    for p in "${patches[@]}"; do
      echo " - patch: $(basename "$p")"
      (
        cd "$STAGE"
        rc=0
        out="$(patch -p0 -N --batch --reject-file=/dev/null < "$p" 2>&1)" || rc=$?
        if [ "$rc" -eq 0 ]; then
          :
        elif echo "$out" | grep -qiE "previously applied|Reversed"; then
          echo " - patch ja aplicado: $(basename "$p")"
        else
          echo "$out" >&2
          exit 2
        fi
      )
    done
  fi
else
  echo "(sem patch dir: $PATCH_DIR)"
fi

echo "==> 3) Sanity compile (staging)"
"$PY" -m py_compile \
  "$STAGE/noc_bot/evidence/builder.py" \
  "$STAGE/noc_bot/ui/keyboards.py" \
  "$STAGE/noc_bot/handlers/callbacks.py" \
  "$STAGE/noc_bot/handlers/commands.py" \
  "$STAGE/noc_bot/handlers/chat.py" \
  "$STAGE/noc_bot/ui/panels.py" \
  "$STAGE/noc_bot/telegram_ui.py" \
  "$STAGE/noc_bot/main.py"

echo "==> 4) Gerando release ZIP limpo: $OUT_ZIP"
rm -f "$OUT_ZIP"
( cd "$STAGE" && zip -qr "$OUT_ZIP" noc_bot -x "*.pyc" "*__pycache__/*" "*.bak" "*.orig" "*.swp" )

echo "OK: release pronto"
ls -lah "$OUT_ZIP"
unzip -l "$OUT_ZIP" | head -n 20
