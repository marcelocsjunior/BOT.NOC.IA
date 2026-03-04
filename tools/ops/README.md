# tools/ops (notebook -> VM bot)

Defaults:
- VM_BOT_HOST=192.168.88.108
- VM_BOT_USER=bio
Override:
  export VM_BOT_HOST=...
  export VM_BOT_USER=...

Comandos:
- tools/ops/botstatus.sh
- tools/ops/botlog.sh ["20 min ago"] [linhas]
- tools/ops/botrestart.sh ["10 min ago"] [linhas]
- tools/ops/deploy.sh               (deploy HEAD noc_bot/)
- tools/ops/ship-tag.sh <tag>       (deploy de tag sem checkout)
- tools/ops/drift.sh [tag]          (sha256 tag vs VM bot)
