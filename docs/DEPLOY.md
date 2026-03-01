# Deploy seguro — BOT ia NOC (UN1)

## Objetivo
Atualizar o core do bot com risco controlado, preservando runtime e dados.

## Princípios
- O repositório é **fonte de verdade do código** e do snapshot **infra AS-RUNNING**.
- O runtime em produção (Collector) mantém:
  - `.env` (segredos)
  - `venv/`
  - DB e state em `/var/lib/noc/*`
  - logs em `/var/log/mikrotik/*`
- Deploy padrão atualiza **somente** o que muda: `noc_bot/` (e `bot.py` se necessário).

## Escopo do deploy
### Muda
- `noc_bot/`
- `bot.py` (quando houver mudança de entrypoint/shim)

### Não muda
- `.env`
- `venv/`
- `/var/lib/noc/noc.db` (SQLite)
- `/var/lib/noc/tailer.state.json`
- `/var/log/mikrotik/un1.log`
- `rsyslog` / `logrotate` / units systemd (a menos que a mudança seja explicitamente infra)

## Gate (pré-deploy)
- Evitar deploy durante incidente SEV ativo.
- Ter rollback real (tag/release anterior + artefato).
- Confirmar que não há segredos no repo.

## Aplicação (alto nível)
1) Atualizar código no runtime (somente `noc_bot/` e, se necessário, `bot.py`).
2) Reiniciar `telegram-bot.service`.
3) Validar saúde com sanity checks.

## Sanity checks (DoD)
- `telegram-bot.service` ativo e sem restart loop.
- Bot responde `/where` com `BOT_VERSION|build` esperado.
- `/where` indica `SOURCE=DB` quando DB está saudável (LOG só em fallback).
- Timeline/status coerentes (DB/LOG conforme fonte).

## Rollback (contenção)
1) Voltar para tag/release anterior (código correspondente).
2) Reiniciar `telegram-bot.service`.
3) Validar `/where` + sanity checks.
4) Registrar causa/impacto e abrir ChangeLog.
