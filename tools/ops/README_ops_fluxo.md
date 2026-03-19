# tools/ops (notebook -> VM bot)

Suíte operacional do projeto para inspecionar, reconciliar e operar o bot na VM bot a partir do notebook.

## Alvo atual

- VM_BOT_HOST=192.168.1.4
- VM_BOT_USER=bio
- REMOTE_BASE=/opt/telegram-bot
- REMOTE_SERVICE=telegram-bot.service

---

## Entry point

### botctl.sh
Wrapper principal.

Exemplos:
- tools/ops/botctl.sh status
- tools/ops/botctl.sh inspect
- tools/ops/botctl.sh restart "10 min ago" 80
- tools/ops/botctl.sh log "20 min ago" 160
- tools/ops/botctl.sh reconcile

---

## Fluxo padrão (operacional)

### 1. Status
tools/ops/botctl.sh status

### 2. Ver drift
tools/ops/botctl.sh inspect

Esperado:
STATE=IN_SYNC

### 3. Reconciliar runtime da VM → clone local
tools/ops/botctl.sh reconcile

### 4. Restart seguro
tools/ops/botctl.sh restart "10 min ago" 80

### 5. Logs
tools/ops/botctl.sh log "20 min ago" 160

---

## Scripts internos

- botstatus.sh → systemctl status remoto
- botlog.sh → journalctl remoto
- botrestart.sh → restart com py_compile gate
- reconcile-runtime.sh → sync VM ↔ local
- _cfg.sh → config central

---

## Evidências

Geradas em:
_reconcile/<timestamp>/

Contém:
- manifest local
- manifest VM
- delta
- relatório

---

## Requisitos

### SSH
Acesso:
bio@192.168.1.4

### sudoers (VM bot)

Arquivo:
 /etc/sudoers.d/noc-ops

Exemplo:
bio ALL=(root) NOPASSWD: /usr/bin/systemctl, /usr/bin/journalctl, /usr/bin/python3

---

## Observações

- Escopo: apenas noc_bot/
- Não faz push automático
- Drift é tratado via reconcile-runtime

---

## Comandos do dia a dia

tools/ops/botctl.sh status
tools/ops/botctl.sh inspect
tools/ops/botctl.sh restart "10 min ago" 80
tools/ops/botctl.sh log "20 min ago" 160
tools/ops/botctl.sh reconcile

---

## Estado validado

- botctl.sh OK
- botrestart.sh OK
- reconcile-runtime OK
- VM bot sincronizada (IN_SYNC)
