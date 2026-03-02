# Docs — BOT ia NOC (UN1)

Índice rápido da documentação e dos artefatos versionados do Collector UN1 (código, infra AS-RUNNING, baseline e runbooks).

---

## 1) Operação (NOC)

- [OPERACAO.md](OPERACAO.md) — Health check e troubleshooting do Collector/pipeline
- [OPERACAO_CHECKLIST.md](OPERACAO_CHECKLIST.md) — Checklist diário / pré e pós mudança / incidente
- [OPERACAO_INCIDENTE.md](OPERACAO_INCIDENTE.md) — Runbook de incidente (SEV, evidência, comunicação)

---

## 2) Deploy (mudança controlada)

- [DEPLOY.md](DEPLOY.md) — Deploy seguro (escopo, sanity checks, rollback)

- [SYNC_RUNBOOKS.md](SYNC_RUNBOOKS.md) — Sync Notebook → Coletor (ubt) dos runbooks + validação (grep/diff/sha256) + evidência

> Regra de ouro: repo versiona **có0digo + infra AS-RUNNING**, mas produção preserva runtime e dados (`.env`, `venv`, DB/state, logs).

---

## 3) Segurança (SecOps)

- [SECURITY.md](SECURITY.md) — política de segredos, redaction, rotação e leak check
- [SECURITY_CONTACT.md](SECURITY_CONTACT.md) — contatos e canal de reporte

---

## 4) Baseline (fonte de verdade técnica)

Baseline do Collector (UN1) versionado no diretório `baseline/`:

- [`baseline/00_INDEX_CANONICO.md`](../baseline/00_INDEX_CANONICO.md) — ponteiro único (fonte de verdade do baseline)
- [`baseline/BOT_ia_NOC_UN1_CANONICO.md`](../baseline/BOT_ia_NOC_UN1_CANONICO.md) — CANÔNICO FULL (snapshot efetivo + evidências)
- [`baseline/SHA256SUMS_BASELINE`](../baseline/SHA256SUMS_BASELINE) — integridade dos artefatos do baseline
- [`baseline/UN1_AS_BUILT_SNAPSHOT.md`](../baseline/UN1_AS_BUILT_SNAPSHOT.md) — placeholder (AS_BUILT aponta para CANONICO FULL)
- [`baseline/BOT_ia_NOC_UN1_Documento_Master.md`](../baseline/BOT_ia_NOC_UN1_Documento_Master.md) — placeholder (Master aponta para CANONICO FULL)
- `baseline/archive/` — backups históricos (`.bak_*`) arquivados

---

## 5) Runbooks (scripts canônicos do coletor)

Runbooks versionados no diretório `runbooks/`:

- [`runbooks/deploy/README.md`](../runbooks/deploy/README.md) — visão do fluxo (bump/build/deploy/rollback)
- [`runbooks/deploy/00_bump_env_canonic.sh`](../runbooks/deploy/00_bump_env_canonic.sh)
- [`runbooks/deploy/10_build_release_zip_canonic.sh`](../runbooks/deploy/10_build_release_zip_canonic.sh)
- [`runbooks/deploy/20_deploy_zip_canonic.sh`](../runbooks/deploy/20_deploy_zip_canonic.sh)
- [`runbooks/deploy/30_rollback_last_backup.sh`](../runbooks/deploy/30_rollback_last_backup.sh)
- [`runbooks/deploy/patches/`](../runbooks/deploy/patches/) — patches aplicáveis (quando necessário)

---

## 6) Integrity automation (baseline + releases)

Scripts (fonte de verdade) em `tools/integrity/`:
- [`tools/integrity/noc-integrity-check.sh`](../tools/integrity/noc-integrity-check.sh) — valida SHA256 do baseline e do cofre de releases
- [`tools/integrity/noc-integrity-alert.sh`](../tools/integrity/noc-integrity-alert.sh) — alerta Telegram (requer rede)

Systemd (AS-RUNNING) em `infra/etc/systemd/system/`:
- [`infra/etc/systemd/system/noc-integrity-check.service`](../infra/etc/systemd/system/noc-integrity-check.service)
- [`infra/etc/systemd/system/noc-integrity-check.timer`](../infra/etc/systemd/system/noc-integrity-check.timer)

Nota operacional:
- O `noc-integrity-check.service` roda hardenizado e pode estar sem rede (`PrivateNetwork=true`).
- O alerta Telegram deve rodar fora desse unit (ou em unit separado com rede).

---

## 7) Infra AS-RUNNING versionada (referência rápida)

Arquivos em `infra/etc/` (representam a configuração efetiva esperada em produção):

- `infra/etc/rsyslog.d/`
  - [`10-mikrotik.conf`](../infra/etc/rsyslog.d/10-mikrotik.conf) — bind UDP/514 (Collector)
  - [`20-mikrotik-files.conf`](../infra/etc/rsyslog.d/20-mikrotik-files.conf) — filtro origem (RouterOS) → `/var/log/mikrotik/un1.log`
- `infra/etc/logrotate.d/`
  - [`mikrotik-un1`](../infra/etc/logrotate.d/mikrotik-un1) — rotação e compressão do `un1.log`
- `infra/etc/systemd/system/`
  - `telegram-bot.service` + drop-ins (harden, envfile, startlimit)

---

## 8) Releases (evidência “AS-RUNNING”)

- Releases são publicadas via **GitHub Releases** (tag + artefato `.tar.gz` + `.sha256`) para rastreabilidade.
- O cofre local de releases no coletor é validado pelo integrity-check (baseline + releases).

---

## Convenção de mudança (anti-drift)

- Mudança em produção → virar commit + registro (docs/baseline/runbook), mantendo o “AS-RUNNING” alinhado.
- Conflito: CANONICO FULL (`baseline/BOT_ia_NOC_UN1_CANONICO.md`) vence.