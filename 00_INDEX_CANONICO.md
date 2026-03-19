# 00_INDEX_CANONICO.md — ALTIS — Ponteiro Único

**Unidade:** UN1  
**Timezone:** America/Sao_Paulo (BRT)  
**DATA_BASELINE (vigente):** 2026-02-25  
**ATUALIZADO_EM:** 2026-03-19 (BRT)  
**Host (produção observado):** ubt  

---

## 1) Fonte de verdade (contrato)

**CANONICO_FULL (fonte única):** `BOT_ia_NOC_UN1_CANONICO.md`

> Política operacional: o canônico full deve ser autocontido. Qualquer “effective config” (outputs reais) deve ser colado nas seções de snapshots do canônico.  
> Regras: se faltar dado, marcar **N/D**. Não inventar.

Baseline histórico (referência, não obrigatório anexar):
- AS_BUILT_ATUAL: `UN1_AS_BUILT_SNAPSHOT_2026-02-25_v11.md`
- DOC_MASTER_ATUAL: `BOT_ia_NOC_UN1_Documento_Master_2026-02-25_v7.md`

---

## 1.1 Identidade oficial do produto

**Nome oficial:** `ALTIS`

**Assinatura oficial:** `Supervisão tecnológica com IA integrada`

**Regra de naming:** a marca do produto é `ALTIS`; `UN1` permanece apenas como contexto operacional.

---

## 2) Arquitetura em produção (resumo)

Pipeline (produção):
**RouterOS7 (UN1)** → **syslog remoto** → **rsyslog raw** → **SQLite** → **ALTIS / Telegram** (AUTO: DB-first + fallback LOG)

Ingestão:
- Syslog UDP/514: `192.168.10.20:514/UDP`
- Filtro: `$fromhost-ip == 192.168.20.1`
- Raw log: `/var/log/mikrotik/un1.log`

Persistência:
- DB: `/var/lib/noc/noc.db` (SQLite WAL)
- State: `/var/lib/noc/tailer.state.json`
- Schema: campo canônico do check = `check_name`

Serviços esperados:
- `rsyslog.service` running
- `noc-sqlite-tailer.service` running
- `telegram-bot.service` running

---

## 3) Deploy/Release (contrato)

Regra crítica:
- Deploy atualiza **somente** `noc_bot/` para preservar `bot.py/.env/venv`.

Ferramenta operacional (produção):
- `/usr/local/sbin/noc-release`
  - `sudo noc-release` (gera ZIPs em `/tmp`)
  - `sudo noc-release --deploy` (stop→backup→unzip stage→rsync noc_bot/→start→sanity)

Cofre persistente de releases (obrigatório):
- `/var/lib/noc/releases`
  - `SHA256SUMS` + validação `sha256sum -c`
  - `CHANGELOG_RELEASES.log` (1 entrada por deploy)
  - `LAST_RELEASE.zip` (symlink do último release)

---

## 4) Estado atual verificado (2026-02-28)

Último deploy aplicado:
- Timestamp: 2026-02-28 11:47 BRT
- Release: `noc_bot_release_2026-02-28_114719.zip`
- SHA256 (artefato aplicado): `e089a920c196f1b04e2cd677d73a034c54d50f0c4aae0b89d1f9a192ff582129`
- Backup: `/opt/telegram-bot.bak_2026-02-28_114719`
- Runtime start (journal): 2026-02-28 11:47:21
- BOT_VERSION|build observado: `2026-02-28-dm-group-ux|build=2026-02-28_094935`  
  (nota: build vem do `.env`; deploy canônico não altera `.env`)

Prova forense (runtime == release):
- `sha256(commands.py)` em produção == `sha256(commands.py)` dentro de `LAST_RELEASE.zip`
- Hash: `595b9fca19cf168682703d273e37e7e50aa996b1304d48be6bf232db14d08c36`

---

## 5) Localização recomendada dos documentos (produção)

Base canônica (recomendado):
- `/var/lib/noc/baseline/`
  - `00_INDEX_CANONICO.md`
  - `BOT_ia_NOC_UN1_CANONICO.md`

Atalho (symlink recomendado):
- `/opt/telegram-bot/00_INDEX_CANONICO.md` → `/var/lib/noc/baseline/00_INDEX_CANONICO.md`

---

## Fingerprint EFFECTIVE (produção) — 2026-02-28 (BRT)

1) telegram-bot ExecStart (effective):
   /home/telegram-bot/venv/bin/python /opt/telegram-bot/bot.py

2) noc-sqlite-tailer ExecStart (effective):
   /usr/local/bin/noc-sqlite-tailer.py
   User/Group=telegram-bot
   LOG_PATH=/var/log/mikrotik/un1.log
   DB_PATH=/var/lib/noc/noc.db
   STATE_PATH=/var/lib/noc/tailer.state.json
   FLUSH_EVERY_SECONDS=5 | STATE_SAVE_EVERY_SECONDS=5 | SLEEP_IDLE=0.5
   BOOTSTRAP_LINES=20000
   BACKFILL_ENABLE=1 | BACKFILL_MAX_BYTES=209715200 | BACKFILL_LINES=50000

3) rsyslog bind UDP/514 (effective):
   /etc/rsyslog.d/10-mikrotik.conf
   imudp @ 192.168.10.20:514
   Prova: rsyslogd pid=865 fd=6 (ss -lunp)

4) rsyslog filtro + raw log (effective):
   /etc/rsyslog.d/20-mikrotik-files.conf
   fromhost-ip=192.168.20.1 → /var/log/mikrotik/un1.log

5) logrotate un1.log (effective):
   /etc/logrotate.d/mikrotik-un1
   daily rotate 30 compress delaycompress dateext -%Y%m%d
   create 0640 syslog adm
   postrotate: HUP rsyslog.service

6) DB (effective):
   /var/lib/noc/noc.db (WAL ativo: noc.db-wal + noc.db-shm)

7) tailer state (effective):
   /var/lib/noc/tailer.state.json

8) schema (effective):
   events.check_name (campo canônico)
   raw_sha1 UNIQUE
   idx_events_ts + idx_events_unit_check_ts

9) Base canônica (produção):
   /var/lib/noc/baseline/00_INDEX_CANONICO.md
   /var/lib/noc/baseline/BOT_ia_NOC_UN1_CANONICO.md

10) Snapshots colados (referência):
   /var/lib/noc/baseline/BOT_ia_NOC_UN1_CANONICO.md
   seção: "SNAPSHOTS — Effective Config (colado) — 2026-02-28 (BRT)"


---

## Runbook — Mudança no Baseline (obrigatório)

1) Alterar SOMENTE em `/var/lib/noc/baseline/` (00_INDEX + CANONICO + changelog).  
2) Após qualquer edição, registrar no `CHANGELOG_BASELINE.log` (o que/por quê/quando).  
3) Regenerar integridade do baseline:
   `cd /var/lib/noc/baseline && sha256sum *.md *.log | sort > SHA256SUMS_BASELINE`  
4) Validar baseline:
   `cd /var/lib/noc/baseline && sha256sum -c SHA256SUMS_BASELINE`  
5) Rodar sanity operacional:
   `sudo systemctl start noc-integrity-check.service`  
6) Conferir resultado:
   `tail -n 60 /var/log/noc/integrity-check.log`  
7) Se `RESULT=FAIL`: **corrigir antes de qualquer deploy** (alerta Telegram dispara automaticamente).  
8) Mudança no código do bot: aplicar via `noc-release` (atualiza só `noc_bot/`, preserva `bot.py/.env/venv`).  
9) Após deploy: validar serviço e logs:
   `systemctl status telegram-bot --no-pager` e `journalctl -u telegram-bot --since "10 min ago" -o cat | tail -n 120`  
10) Se rollback: usar `/opt/telegram-bot.bak_YYYY-MM-DD_HHMMSS/` + reiniciar serviço.  
11) Política: `/tmp` é volátil; releases ficam em `/var/lib/noc/releases` (SHA256SUMS + LAST_RELEASE.zip).  
12) Qualquer exceção vira evidência (logs/outputs) colada no canônico full.


---

## Operação Rápida (plantão)

**Docs (baseline):**
- Ponteiro: `/var/lib/noc/baseline/00_INDEX_CANONICO.md`
- Canônico full: `/var/lib/noc/baseline/BOT_ia_NOC_UN1_CANONICO.md`
- Hash baseline: `/var/lib/noc/baseline/SHA256SUMS_BASELINE`

**Releases (deploy):**
- Cofre: `/var/lib/noc/releases/`
- Hash releases: `/var/lib/noc/releases/SHA256SUMS`
- Último release: `/var/lib/noc/releases/LAST_RELEASE.zip`
- Backup de deploy: `/opt/telegram-bot.bak_YYYY-MM-DD_HHMMSS/`

**Serviços (produção):**
- Bot: `telegram-bot.service`
- Tailer DB: `noc-sqlite-tailer.service`
- Rsyslog: `rsyslog.service`

**Comandos de plantão (copiar/colar):**
1) Timer e próximo check:
   `systemctl status noc-integrity-check.timer --no-pager`
2) Rodar integridade manual:
   `systemctl start noc-integrity-check.service`
3) Ver último resultado:
   `tail -n 60 /var/log/noc/integrity-check.log`
4) Se alertou (OnFailure):
   `journalctl -u noc-integrity-alert.service --since "24 hours ago" -o cat --no-pager | tail -n 120`
5) Status do bot:
   `systemctl status telegram-bot --no-pager`
   `journalctl -u telegram-bot --since "10 min ago" -o cat --no-pager | tail -n 120`

**Regra de ouro:**
Qualquer edição em `/var/lib/noc/baseline/` exige regenerar `SHA256SUMS_BASELINE` e rodar `noc-integrity-check.service`.

---

## Entrega — /health (Grupo NOC) + Release aplicado

**Data (BRT):** 2026-02-28 18:00:51 -0300
**Host:** ubt

**Feature: /health (Grupo NOC)**
- Comando: 
- Conteúdo: versão/build + status de serviços + paths + último evento (SQLite) + integridade (baseline/releases)
- Segurança/robustez:
  - resposta com  (evita 400 Bad Request por entidades)
  - fallback por Regex para capturar  mesmo em supergroup
  - log de prova no journal: 

**Release em produção (cofre):**
- LAST_RELEASE.zip -> noc_bot_release_2026-02-28_175228.zip
- SHA256 (release): 00b7f07e85e36f57fbb7cb257fe15725d6c95c550a1b607da0283be54f53128f
- SHA256 (patched): 00b7f07e85e36f57fbb7cb257fe15725d6c95c550a1b607da0283be54f53128f
- Backup do deploy: /opt/telegram-bot.bak_2026-02-28_175228

