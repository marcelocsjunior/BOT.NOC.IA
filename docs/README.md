# Docs — BOT ia NOC (UN1)

Índice rápido da documentação versionada do projeto, incluindo baseline, deploy, segurança, operação, DM assistiva, heartbeat/SELFTEST anti-stale e toolkit operacional.

---

## 1) Produto / DM assistiva

- [DM_ASSISTIVA_HIBRIDA.md](DM_ASSISTIVA_HIBRIDA.md) — comportamento atual da DM híbrida/assistiva, rotas, guardrails, flags e smoke tests

---

## 2) Operação (NOC)

- [OPERACAO.md](OPERACAO.md) — health check e troubleshooting do collector/pipeline
- [OPERACAO_CHECKLIST.md](OPERACAO_CHECKLIST.md) — checklist diário / pré e pós mudança / incidente
- [OPERACAO_INCIDENTE.md](OPERACAO_INCIDENTE.md) — runbook de incidente (SEV, evidência, comunicação)

Notas operacionais relevantes do baseline vigente:
- heartbeat/SELFTEST local na **VM bot** mantém freshness do pipeline em períodos sem transição real
- Netwatch rogue do MUNDIVOX (`up-script=...`) foi removido em 2026-03-20 após erro `bad command name ...`

---

## 3) Deploy (mudança controlada)

- [DEPLOY.md](DEPLOY.md) — deploy seguro do bot, escopo, smoke test da DM, mudança infra-controlada (heartbeat/SELFTEST) e rollback
- [SYNC_RUNBOOKS.md](SYNC_RUNBOOKS.md) — sync notebook → coletor (VM bot) de runbooks + validação

> Regra de ouro: repo versiona **código + infra AS-RUNNING + documentação canônica**, mas produção preserva runtime e dados (`.env`, `venv`, DB/state, logs).

---

## 4) Segurança (SecOps)

- [SECURITY.md](SECURITY.md) — política de segredos, redaction, rotação e leak check
- [SECURITY_CONTACT.md](SECURITY_CONTACT.md) — contatos e canal de reporte

---

## 5) Baseline (fonte de verdade técnica)

Arquivos versionados em `baseline/`:

- [`baseline/00_INDEX_CANONICO.md`](../baseline/00_INDEX_CANONICO.md) — ponteiro único
- [`baseline/BOT_ia_NOC_UN1_CANONICO.md`](../baseline/BOT_ia_NOC_UN1_CANONICO.md) — documento canônico full
- [`baseline/SHA256SUMS_BASELINE`](../baseline/SHA256SUMS_BASELINE) — integridade do baseline
- [`baseline/archive/`](../baseline/archive/) — backups históricos

Conflito documental:
- **CANONICO_FULL vence**
- documentos em `docs/` complementam
- README resume

Observação:
- mudanças de freshness/heartbeat exigem atualização de `baseline/00_INDEX_CANONICO.md`, `baseline/BOT_ia_NOC_UN1_CANONICO.md` e `docs/DEPLOY.md`

---

## 6) Toolkit operacional (notebook → VM bot)

Fluxo operacional em:
- [`tools/ops/README_ops_fluxo.md`](../tools/ops/README_ops_fluxo.md)

Arquivos relevantes:
- `tools/ops/_cfg.sh`
- `tools/ops/reconcile-runtime.sh`
- `tools/ops/botctl.sh`

Uso padrão:
```bash
tools/ops/botctl.sh status
tools/ops/botctl.sh inspect
tools/ops/botctl.sh restart "10 min ago" 80
tools/ops/botctl.sh log "20 min ago" 160
tools/ops/botctl.sh reconcile
```

---

## 7) Integrity automation

Scripts:
- [`tools/integrity/noc-integrity-check.sh`](../tools/integrity/noc-integrity-check.sh)
- [`tools/integrity/noc-integrity-alert.sh`](../tools/integrity/noc-integrity-alert.sh)

Systemd:
- [`infra/etc/systemd/system/noc-integrity-check.service`](../infra/etc/systemd/system/noc-integrity-check.service)
- [`infra/etc/systemd/system/noc-integrity-check.timer`](../infra/etc/systemd/system/noc-integrity-check.timer)

---

## 8) Infra AS-RUNNING versionada

Referência rápida em `infra/etc/`:
- `infra/etc/rsyslog.d/`
- `infra/etc/logrotate.d/`
- `infra/etc/systemd/system/`

---

## Convenção de mudança

- mudança em produção → virar commit + release/tag + documentação correspondente
- mudança na DM assistiva → atualizar **CANONICO_FULL** e `docs/DM_ASSISTIVA_HIBRIDA.md`
- mudança no fluxo operacional → atualizar `tools/ops/README_ops_fluxo.md`
- mudança infra-controlada de freshness/SELFTEST → atualizar **CANONICO_FULL**, `baseline/00_INDEX_CANONICO.md` e `docs/DEPLOY.md`
