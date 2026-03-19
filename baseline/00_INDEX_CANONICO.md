# 00_INDEX_CANONICO.md — BOT ia NOC (UN1) — Ponteiro Único

**Unidade:** UN1  
**Timezone:** America/Sao_Paulo (BRT)  
**DATA_BASELINE (vigente):** 2026-03-18  
**ATUALIZADO_EM:** 2026-03-18 (BRT)  
**Host (produção observado):** ubt  

---

## 1) Fonte de verdade (contrato)

**CANONICO_FULL (fonte única):** `BOT_ia_NOC_UN1_CANONICO.md`

> Política operacional: o canônico full deve ser autocontido. Outputs reais e “effective config” devem ser colados em snapshots quando existirem.  
> Regra dura: se faltar dado, marcar **N/D**. Não inventar.

Baseline histórico (referência):
- AS_BUILT_ATUAL: `UN1_AS_BUILT_SNAPSHOT_2026-02-25_v11.md`
- DOC_MASTER_ATUAL: `BOT_ia_NOC_UN1_Documento_Master_2026-02-25_v7.md`

Documentos de apoio relevantes:
- `docs/DM_ASSISTIVA_HIBRIDA.md`
- `docs/DEPLOY.md`
- `docs/README.md`
- `tools/ops/README_ops_fluxo.md`

---

## 2) Arquitetura em produção (resumo)

Pipeline (produção):
**RouterOS7 (UN1)** → **syslog remoto** → **rsyslog raw** → **SQLite** → **Bot Telegram** (AUTO: DB-first + fallback LOG)

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

## 3) Camada DM assistiva / híbrida (estado documental)

A camada DM evoluiu além da FIX6 e agora deve ser considerada formalmente composta por:

- parser determinístico factual
- contexto curto de sessão
- clarificação mínima
- consulta factual
- triagem de incidente
- interação social básica
- ajuda simples e segura
- IA opcional para classificar ou polir texto, sem virar fonte de verdade

Rotas formais documentadas:
- `consult`
- `incident`
- `clarify`
- `social`
- `help`
- `none`

Documento detalhado:
- `docs/DM_ASSISTIVA_HIBRIDA.md`

---

## 4) Deploy/Release (contrato)

Regra crítica:
- Deploy padrão atualiza **somente** `noc_bot/` para preservar `bot.py/.env/venv`.

Ferramentas e contratos:
- deploy seguro conforme `docs/DEPLOY.md`
- toolkit operacional em `tools/ops/`
- cofre persistente de releases em `/var/lib/noc/releases`
- rollback por backup/tag/release anterior

---

## 5) Estado documental consolidado em 2026-03-18

Este baseline passa a refletir explicitamente:
- toolkit operacional notebook → VM bot
- governança anti-drift com `tools/ops/reconcile-runtime.sh`
- DM assistiva/híbrida documentada além da FIX6
- smoke test da DM integrado ao critério de deploy
- separação explícita entre **produto** (UX DM) e **motor conversacional** (roteador, contexto, IA opcional)

---

## 6) Toolkit operacional (notebook -> VM bot)

Alvo operacional atual:
- `VM_BOT_HOST=192.168.1.4`
- `VM_BOT_USER=bio`
- `REMOTE_BASE=/opt/telegram-bot`
- `REMOTE_SERVICE=telegram-bot.service`

Arquivos relevantes:
- `tools/ops/_cfg.sh`
- `tools/ops/reconcile-runtime.sh`
- `tools/ops/botctl.sh`
- `tools/ops/README_ops_fluxo.md`

Fluxo padrão:
```bash
tools/ops/botctl.sh status
tools/ops/botctl.sh inspect
tools/ops/botctl.sh restart "10 min ago" 80
tools/ops/botctl.sh log "20 min ago" 160
tools/ops/botctl.sh reconcile
```

---

## 7) Runbook — mudança no baseline

1. Alterar somente em `baseline/` e `docs/`, registrando a motivação.
2. Atualizar `README.md` quando a mudança impactar produto/arquitetura percebida.
3. Regenerar integridade do baseline, quando aplicável.
4. Validar smoke test da DM se a mudança documental refletir comportamento novo do runtime.
5. Conflito documental: **CANONICO_FULL vence**; documentos de apoio complementam, não substituem.

---

## 8) Regra de ouro

O canônico precisa descrever o que realmente existe no código e no runtime, e não só o que seria bonito dizer em reunião.

Em resumo:
- produto e UX no papel
- motor conversacional também no papel
- DB/LOG/regras continuam como juiz final da verdade operacional
