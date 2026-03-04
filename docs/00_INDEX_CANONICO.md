# 00_INDEX_CANONICO — BOT ia NOC (UN1) — BOT.NOC.IA

**Data baseline (AS-RUNNING):** 2026-03-01_193042  
**Runtime (build em execução no Collector UN1):**
- `BOT_VERSION=2026-02-28-dm-group-ux|build=2026-02-28_094935`
- `BUILD_ID=2026-02-28_094935`

---

## 1) Fonte de verdade (ordem de precedência)

1) **GitHub Release (AS-RUNNING snapshot + integridade)**
   - Tag: `un1-2026-02-28-build-2026-02-28_094935`
   - Assets:
     - `BOT_ia_NOC_UN1_release_20260301_193042_clean.tar.gz`
     - `BOT_ia_NOC_UN1_release_20260301_193042_clean.tar.gz.sha256`

2) **Infra AS-RUNNING versionada (repo)**
   - `infra/etc/` (systemd/rsyslog/logrotate) — reflete o que estava operando no snapshot

3) **Código versionado (repo)**
   - `bot.py`
   - `noc_bot/`

4) **Documentação e runbooks (repo)**
   - `README.md`
   - `docs/*`

> Regra de conflito: se a documentação divergir do **AS-RUNNING** (Release + `infra/etc`), o **AS-RUNNING vence**. Documentação complementa, não substitui.

---

## 2) Arquitetura canônica (produção)

Pipeline:
**RouterOS 7 (UN1)** → **Syslog remoto** → **rsyslog (raw)** → **SQLite (WAL)** → **Bot Telegram (AUTO DB-first + fallback LOG)**

Pontos canônicos:
- Syslog: `192.168.10.20:514/UDP` (origem filtrada: `192.168.20.1`)
- Raw log: `/var/log/mikrotik/un1.log`
- DB: `/var/lib/noc/noc.db` (SQLite WAL)
- State/offset: `/var/lib/noc/tailer.state.json`
- Campo canônico no schema: `check_name`

Serviços esperados:
- `rsyslog.service`
- `noc-sqlite-tailer.service`
- `telegram-bot.service`

Contrato do evento:
`NOC|unit=UN1|device=<id>|check=<nome>|state=UP/DOWN|host=<target>|cid=<correlation-id>`

---

## 3) Infra AS-RUNNING (repo) — ponteiros

- rsyslog:
  - `infra/etc/rsyslog.d/10-mikrotik.conf`
  - `infra/etc/rsyslog.d/20-mikrotik-files.conf`
- logrotate:
  - `infra/etc/logrotate.d/mikrotik-un1`
- systemd:
  - `infra/etc/systemd/system/telegram-bot.service`
  - `infra/etc/systemd/system/telegram-bot.service.d/10-execstart.conf`
  - `infra/etc/systemd/system/telegram-bot.service.d/20-protecthome.conf`
  - `infra/etc/systemd/system/telegram-bot.service.d/30-envfile.conf`
  - `infra/etc/systemd/system/telegram-bot.service.d/40-startlimit.conf`

---

## 4) Operação (docs) — índice oficial

- `docs/README.md` — índice de navegação
- `docs/OPERACAO.md` — health check + troubleshooting do Collector/pipeline
- `docs/OPERACAO_CHECKLIST.md` — checklist diário / pré/pós mudança / incidente
- `docs/OPERACAO_INCIDENTE.md` — SEV, evidência, comunicação (diretoria/operadora)
- `docs/DEPLOY.md` — deploy seguro (escopo, sanity checks, rollback)

---

## 5) Governança (anti-drift)

- Mudança em produção (código ou infra) = **commit + tag/release**
- Se **infra** mudar (systemd/rsyslog/logrotate), atualizar `infra/etc/` no repo
- Snapshot AS-RUNNING recomendado antes de mudanças relevantes (artefato + sha256)
- Rollback deve apontar para release/tag anterior conhecido e validado

---

## 6) Segurança (política)

- `docs/SECURITY.md` — política de segredos/logs/integridade/hardening
- `docs/SECURITY_CONTACT.md` — canal interno de reporte (`[SECURITY]`)

Regras duras:
- `.env` e segredos **nunca** no repo
- runtime mantém `.env`, `venv/`, DB/state e logs fora do Git
- integridade de release validada por `.sha256`

---

## 7) Releases

- Release 1 (Evidence UX v2): `v2026.03.04-evidence-ux` 
  - GitHub Release: https://github.com/marcelocsjunior/BOT.NOC.IA/releases/tag/v2026.03.04-evidence-ux
  - PR: #1 (merged)
  - Manifest: `evidence_release_manifest.txt` (main)



- Release 0 (AS-RUNNING): `un1-2026-02-28-build-2026-02-28_094935` (**Latest**)

> Este índice é o “ponteiro único” do baseline vigente. Qualquer atualização de baseline deve atualizar este arquivo.

## Integrity automation (baseline + releases)
Systemd (AS-RUNNING):
- infra/etc/systemd/system/noc-integrity-check.service
- infra/etc/systemd/system/noc-integrity-check.timer

Scripts (fonte de verdade):
- tools/integrity/noc-integrity-check.sh (valida SHA256 do baseline e do cofre de releases)
- tools/integrity/noc-integrity-alert.sh (alerta Telegram; requer rede)

Nota operacional:
- O unit `noc-integrity-check.service` roda hardenizado e pode estar sem rede (ex.: `PrivateNetwork=true`).
  O alerta Telegram deve rodar fora desse unit (ou em unit separado com rede).
