# Operação — BOT ia NOC (UN1) (Collector)

Runbook operacional para manter o pipeline saudável, diagnosticar incidentes e reduzir drift.
Foco: **RouterOS → syslog → rsyslog (raw) → SQLite (WAL) → Telegram Bot (AUTO DB-first + fallback LOG)**

---

## 1) Componentes e caminhos (produção)

### Serviços (systemd)
- `rsyslog.service`
- `noc-sqlite-tailer.service`
- `telegram-bot.service`

### Paths canônicos
- Raw log: `/var/log/mikrotik/un1.log`
- DB: `/var/lib/noc/noc.db` (SQLite WAL)
- State/offset tailer: `/var/lib/noc/tailer.state.json`

### Infra AS-RUNNING versionada no repo
- `infra/etc/rsyslog.d/*`
- `infra/etc/logrotate.d/*`
- `infra/etc/systemd/system/*` (unit + drop-ins)

---

## 2) Health check rápido (30–60s)

### 2.1 Serviços
- Esperado: todos **active (running)**

Sugestão de checagem:
- `systemctl status rsyslog --no-pager`
- `systemctl status noc-sqlite-tailer --no-pager`
- `systemctl status telegram-bot --no-pager`

Sinais ruins:
- restart loop no `telegram-bot` (StartLimit)
- tailer parado (DB não atualiza)
- rsyslog sem receber UDP/514 (raw log não cresce)

### 2.2 Bot (diagnóstico)
- `/where` deve mostrar:
  - `BOT_VERSION|build`
  - `SOURCE=DB/LOG`
  - freshness + paths

Esperado:
- `SOURCE=DB` quando DB/tailer estão saudáveis
- `SOURCE=LOG` só em fallback (problema de DB/tailer ou staleness)

### 2.3 Raw log está alimentando
- `tail -n 5 /var/log/mikrotik/un1.log`
- O arquivo deve conter linhas no padrão `NOC|unit=UN1|...`

### 2.4 DB está em WAL e schema ok
- `sqlite3 /var/lib/noc/noc.db "PRAGMA journal_mode;"`
  - esperado: `wal`
- `sqlite3 /var/lib/noc/noc.db ".schema" | grep -n check_name`
  - esperado: existe `check_name`

---

## 3) Diagnóstico por sintoma (playbook)

### Sintoma A — Bot não responde /where
1) Ver `telegram-bot.service`:
   - `systemctl status telegram-bot --no-pager`
2) Logs do serviço:
   - `journalctl -u telegram-bot --since "15 min ago" --no-pager`
3) Se está em restart loop:
   - revisar `infra/etc/systemd/system/telegram-bot.service.d/*` (StartLimit, EnvFile, ExecStart)
4) Verificar `.env` no runtime (NUNCA no repo):
   - token e variáveis mínimas presentes
   - `BOT_VERSION` / `BUILD_ID` coerentes

### Sintoma B — /where diz SOURCE=LOG (fallback) e não volta pra DB
1) Verificar `noc-sqlite-tailer.service`:
   - `systemctl status noc-sqlite-tailer --no-pager`
   - `journalctl -u noc-sqlite-tailer --since "15 min ago" --no-pager`
2) Verificar se DB existe e é gravável:
   - `ls -lah /var/lib/noc/noc.db`
3) Verificar state file:
   - `ls -lah /var/lib/noc/tailer.state.json`
4) Verificar se raw log está chegando (rsyslog):
   - `tail -n 50 /var/log/mikrotik/un1.log`

### Sintoma C — Raw log parou de crescer (rsyslog)
1) Ver `rsyslog.service`:
   - `systemctl status rsyslog --no-pager`
2) Validar bind/filtro no rsyslog (AS-RUNNING):
   - conferir `infra/etc/rsyslog.d/10-mikrotik.conf`
   - conferir `infra/etc/rsyslog.d/20-mikrotik-files.conf`
3) Validar logrotate não está quebrando escrita:
   - conferir `infra/etc/logrotate.d/mikrotik-un1`
   - `logrotate -d /etc/logrotate.d/mikrotik-un1` (debug dry-run)

### Sintoma D — Eventos existem no raw log, mas DB não reflete
1) Tailer parado/travado:
   - `systemctl status noc-sqlite-tailer`
2) Verificar permissões:
   - `/var/lib/noc/` gravável pelo serviço
3) Verificar WAL/locks:
   - `sqlite3 /var/lib/noc/noc.db "PRAGMA journal_mode;"`

---

## 4) Incidente e severidade (UN1)

Matriz:
- **SEV1**: MUNDIVOX DOWN (com/sem VALENET)
- **SEV3**: VALENET DOWN com MUNDIVOX UP
- **SEV2**: serviços (ESCALLO/VOIP) DOWN com WANs UP

Recomendação operacional:
- Em SEV, priorizar **linha do tempo** (/timeline), correlacionar por `cid`, e acionar **evidência** quando necessário (prova + texto pronto).

---

## 5) Evidências (provas)

Trigger no bot:
- `evidência / evidencias / evidências / prova / provas`

Regra:
- exigir serviço (ex.: “evidência telefonia”) para evitar prova errada

Entrega:
1) painel/seleção
2) evidência compacta + botões
3) texto pronto com **5 CIDs mais recentes** + nota “há mais”

---

## 6) Anti-drift (governança)

Regra de ouro:
- Mudança em produção = **commit + tag/release**
- Infra (systemd/rsyslog/logrotate) deve ser atualizada em `infra/etc` quando mudar runtime.

Recomendação:
- Antes de qualquer mudança relevante, gerar um **AS-RUNNING snapshot** (release + sha256).
- Rollback deve apontar para um release anterior conhecido.

---

## 7) Segurança (baseline)

- `.env` e segredos **não** entram no repositório.
- Token deve ser redigido em logs e rotacionado quando necessário.
- “leak check” esperado: 0 (sem token em logs/repo).

---

## 8) Checklist diário (operação NOC)

1) `telegram-bot.service` ok (sem restart loop)
2) `/where` com `BOT_VERSION|build` correto e `SOURCE=DB` (quando saudável)
3) raw log chegando (`/var/log/mikrotik/un1.log`)
4) DB em WAL e schema ok (`check_name`)
5) Sem ruído no grupo (bot responde só por menção/reply)
