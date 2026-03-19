# BOT ia NOC (UN1) — Coletor + Telegram Bot

Bot operacional de NOC para a unidade **UN1**, com ingestão confiável dos eventos do **MikroTik RouterOS 7**, persistência estruturada e consulta via **Telegram**, preservando um princípio simples:

- **a IA interpreta a intenção e organiza a conversa**
- **DB, LOG e regras provam os fatos**
- **a IA não inventa status, causa raiz, severidade nem evidência**

Essa separação é o que impede o bot de virar um poeta perigoso de incidente.

## Arquitetura (produção)

Pipeline end-to-end em produção:

**RouterOS 7 (UN1)** → **syslog remoto** → **rsyslog (raw)** → **SQLite (WAL)** → **Bot Telegram (AUTO: DB-first + fallback LOG)**

Pontos canônicos:
- Syslog: `192.168.10.20:514/UDP`
- Filtro de origem (RouterOS): `192.168.20.1`
- Raw log: `/var/log/mikrotik/un1.log`
- DB: `/var/lib/noc/noc.db`
- State/offset: `/var/lib/noc/tailer.state.json`
- Campo canônico no schema: `check_name`

Canal complementar:
- RouterOS API-SSL: `9005/TLS`

## Contrato de evento

Formato canônico:
`NOC|unit=UN1|device=<id>|check=<nome>|state=UP/DOWN|host=<target>|cid=<correlation-id>`

Objetivos:
- timeline determinística
- correlação por `cid`
- evidência operacional auditável
- leitura executiva sem improviso

## Catálogo de checks (UN1)

- **MUNDIVOX (WAN1)**: target `189.91.71.217` | src-address `189.91.71.218`
- **VALENET (WAN2)**: target `187.1.49.121` | src-address `187.1.49.122`
- **ESCALLO**: `187.33.28.57`
- **Telefonia (VOIP)**: `138.99.240.49`

## Severidade (matriz de decisão)

- **SEV1**: MUNDIVOX DOWN (com ou sem VALENET)
- **SEV3**: VALENET DOWN com MUNDIVOX UP
- **SEV2**: serviços (ESCALLO/VOIP) DOWN com WANs UP

## Camada DM assistiva / híbrida

A DM atual já opera em superfície híbrida, com seis rotas formais:

- `social`
- `help`
- `consult`
- `incident`
- `clarify`
- `none`

Resumo do papel de cada uma:
- **social**: saudações e interação leve
- **help**: ajuda simples e segura, sem afirmar fatos operacionais
- **consult**: consulta factual em cima de DB/LOG/regras
- **incident**: triagem operacional e atendimento 2h
- **clarify**: pergunta curta para fechar contexto/escopo
- **none**: nada aplicável; fluxo padrão assume fallback seguro

Módulos centrais:
- `noc_bot/handlers/chat.py` — entrada de texto livre
- `noc_bot/dm_router.py` — decisão de rota na DM
- `noc_bot/dm_session.py` — contexto curto e clarificação
- `noc_bot/dm_intents.py` — parser determinístico factual
- `noc_bot/dm_queries.py` — consultas em fonte real
- `noc_bot/dm_presenter.py` — resposta factual base
- `noc_bot/ai_client.py` — IA opcional para classificar ou polir texto

Documento detalhado da camada DM:
- [`docs/DM_ASSISTIVA_HIBRIDA.md`](docs/DM_ASSISTIVA_HIBRIDA.md)

## UX do bot

### DM (produto)
- resposta curta e objetiva
- painel executivo da unidade
- botões para resumo, evidências, atendimento e fonte
- contexto curto para follow-up
- clarificação mínima quando necessário

### Grupo NOC (técnico)
- anti-ruído por @menção ou reply
- timeline, analyze, evidências e where
- mesma fonte factual da DM

## Evidências

Triggers aceitos:
- `evidência`
- `evidencias`
- `evidências`
- `prova`
- `provas`

Regra:
- exigir o serviço para evitar prova errada

Entrega padrão:
1. painel/contexto
2. evidência compacta
3. texto pronto para operadora com até 5 CIDs recentes

## Toolkit operacional (`tools/ops`)

A operação remota do bot ficou padronizada em `tools/ops`:

```bash
tools/ops/botctl.sh status
tools/ops/botctl.sh inspect
tools/ops/botctl.sh restart "10 min ago" 80
tools/ops/botctl.sh log "20 min ago" 160
tools/ops/botctl.sh reconcile
```

Alvo operacional atual:
- VM bot: `192.168.1.4`
- usuário: `bio`
- base remota: `/opt/telegram-bot`
- serviço remoto: `telegram-bot.service`

Principais componentes:
- `tools/ops/_cfg.sh`
- `tools/ops/reconcile-runtime.sh`
- `tools/ops/botctl.sh`
- `tools/ops/README_ops_fluxo.md`

## Configuração

Use `.env.example` como baseline. O runtime real deve manter apenas segredos válidos no `.env`.

Pontos relevantes:
- `TELEGRAM_BOT_TOKEN`
- `BOT_VERSION`
- `BUILD_ID`
- `NOC_DB_PATH`
- `NOC_LOG_PATH`
- família `DM_ASSISTANT_*`
- `AI_ENABLED` e credenciais Cloudflare, quando aplicável

## Deploy seguro

Deploy padrão:
- atualiza **somente** `noc_bot/`
- `bot.py` só muda quando houver alteração real de entrypoint/shim
- `.env`, `venv`, DB/state e logs não devem ser tocados no ciclo padrão

Documento de deploy:
- [`docs/DEPLOY.md`](docs/DEPLOY.md)

## Testes e smoke test

A documentação e o runtime atual já pressupõem validação da DM híbrida por:
- smoke tests manuais na DM
- callbacks
- atendimento/evidência
- checks de logs pós-restart
- testes formais, quando o bundle implantado os incluir

Casos mínimos recomendados:
- `Oi, boa tarde`
- `Qual é o site do speed test?`
- `Como faço para medir a velocidade da internet?`
- `Telefone ok aí?`
- `E a internet?`
- `falhas hoje`
- `Caiu tudo agora`
- `evidência telefonia`

## Estrutura documental recomendada

- `baseline/00_INDEX_CANONICO.md` — ponteiro único
- `baseline/BOT_ia_NOC_UN1_CANONICO.md` — fonte única consolidada
- `docs/DM_ASSISTIVA_HIBRIDA.md` — comportamento da DM atual
- `docs/DEPLOY.md` — deploy seguro + smoke test
- `docs/README.md` — índice rápido
- `tools/ops/README_ops_fluxo.md` — fluxo notebook → VM bot

## Roadmap

1. anti-flap na fonte (RouterOS / Netwatch)
2. hardening da API-SSL 9005
3. qualidade por operadora (L1/L2)
4. expansão multi-unidade (UN2/UN3)
5. refinamento fino de contexto, clarificação e respostas binárias na DM

## Frase de visão

**A IA da DM do BOT ia NOC deve ser humana na conversa, inteligente na interpretação e rigorosa na verdade operacional.**
