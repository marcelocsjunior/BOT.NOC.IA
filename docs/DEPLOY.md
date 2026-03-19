# Deploy seguro — BOT ia NOC (UN1)

## Objetivo

Atualizar o core do bot com risco controlado, preservando runtime, dados e previsibilidade operacional.

## Princípios

- O repositório é **fonte de verdade do código**, da infra AS-RUNNING e da documentação canônica.
- O runtime em produção mantém:
  - `.env`
  - `venv/`
  - DB e state em `/var/lib/noc/*`
  - logs em `/var/log/mikrotik/*`
- Deploy padrão atualiza **somente** o que muda:
  - `noc_bot/`
  - `bot.py` **apenas** quando houver mudança real de entrypoint/shim

## Escopo do deploy

### Muda
- `noc_bot/`
- `bot.py` (se necessário)

### Não muda
- `.env`
- `venv/`
- `/var/lib/noc/noc.db`
- `/var/lib/noc/tailer.state.json`
- `/var/log/mikrotik/un1.log`
- `rsyslog` / `logrotate` / units systemd (salvo mudança explicitamente infra)

## Gate (pré-deploy)

- evitar deploy durante incidente SEV ativo
- ter rollback real (tag/release anterior + artefato)
- confirmar que não há segredos no repo
- confirmar que a documentação está coerente com o lote implantado

## Aplicação (alto nível)

1. atualizar código no runtime (`noc_bot/` e, se necessário, `bot.py`)
2. reiniciar `telegram-bot.service`
3. validar saúde com sanity checks
4. validar smoke test da DM assistiva/híbrida

## Sanity checks (DoD)

- `telegram-bot.service` ativo e sem restart loop
- bot responde `/where` com `BOT_VERSION|build` esperado
- `/where` indica `SOURCE=DB` quando DB está saudável
- timeline/status coerentes
- DM assistiva/híbrida operando no mínimo sem regressão visível

## Smoke test pós-deploy — DM assistiva

### Social
- `Oi, boa tarde`

Esperado:
- resposta humana curta
- sem alegar checagem operacional

### Help
- `Qual é o site do speed test?`
- `Como faço para medir a velocidade da internet?`

Esperado:
- rota help
- resposta segura
- sem inventar fato operacional

### Consult
- `Telefone ok aí?`
- `Escallo`
- `falhas hoje`
- `status atual`

Esperado:
- resposta factual
- baseada em DB/LOG/regras
- sem virar frase vazia de IA

### Clarify
- `E a internet?`

Esperado:
- pergunta curta para fechar contexto/escopo
- não cair direto em resposta errada

### Incident
- `Caiu tudo agora`

Esperado:
- rota de incidente
- atendimento/triagem 2h acionável

### Evidência
- `evidência telefonia`

Esperado:
- fluxo padrão de evidência
- serviço correto
- sem prova trocada

### Callback
- home
- painel agora
- disponibilidade hoje
- qualidade hoje
- resumo 24h
- evidências
- atendimento 2h
- where

Esperado:
- callback routing sem erro
- fallback gracioso para ação desconhecida

## Testes formais

Se o bundle implantado incluir `tests/`:

1. `python -m compileall bot.py noc_bot tests`
2. executar a suíte incluída
3. só então reiniciar o serviço

Se o bundle não incluir `tests/`, o smoke test manual acima vira obrigatório.

## Flags da DM a conferir no runtime

Validar coerência de:
- `DM_ASSISTANT_ENABLED`
- `DM_ASSISTANT_ENABLE_DM_ROUTER`
- `DM_ASSISTANT_ENABLE_AI_CLASSIFIER`
- `DM_ASSISTANT_ENABLE_CLARIFY`
- `DM_ASSISTANT_ENABLE_SESSION_CONTEXT`
- `DM_ASSISTANT_ENABLE_AI_FINISH`
- `DM_ASSISTANT_ENABLE_AI_GENERAL`
- shadow modes, se utilizados

Atenção:
- shadow mode é ótimo para homologação
- é péssimo para fingir que algo está funcionando em produção quando a resposta nem está saindo para o usuário

## Rollback (contenção)

1. voltar para tag/release anterior
2. restaurar backup correspondente
3. reiniciar `telegram-bot.service`
4. validar `/where`, logs e smoke test essencial
5. registrar causa, impacto e decisão

## Regra operacional

Deploy sem smoke test da DM assistiva é pedir para descobrir regressão pelo Telegram, o que é uma forma elegante de apanhar em horário comercial.
