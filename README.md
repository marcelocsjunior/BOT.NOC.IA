# ALTIS

ALTIS é a camada de produto de uma plataforma de **supervisão tecnológica com IA integrada**, com **fonte de verdade determinística** (DB/LOG/regras) e **camada conversacional híbrida** na DM.

## Princípio de arquitetura

- **IA interpreta intenção e organiza a conversa**
- **DB, LOG e regras provam os fatos**
- **IA não inventa status, causa raiz, severidade nem evidência**

Essa separação é o que impede a plataforma de virar um poeta perigoso de incidente.

## Componentes principais

- `noc_bot/handlers/chat.py` — entrada de texto livre
- `noc_bot/dm_router.py` — decisão da rota da DM (social, help, consult, incident, clarify)
- `noc_bot/dm_session.py` — contexto curto e clarificação
- `noc_bot/dm_intents.py` — parser determinístico factual
- `noc_bot/dm_queries.py` — consultas em fonte real
- `noc_bot/dm_presenter.py` — resposta factual base
- `noc_bot/handlers/callbacks.py` — callback routing do teclado inline
- `noc_bot/telegram_ui.py` — teclados públicos
- `noc_bot/ui/panels.py` — painéis/UX da DM

## Escopo da DM híbrida

A DM precisa lidar com três camadas sem misturar alhos, bugalhos e produção:

### 1. Social
Exemplos:
- `Oi, boa tarde`
- `Bom dia`

### 2. Ajuda simples e segura
Exemplos:
- `Como faço para medir a velocidade da internet?`
- `Qual é o site do speed test?`

### 3. Operação auditável
Exemplos:
- `Telefone ok aí?`
- `Teve falha hoje?`
- `Caiu tudo agora`
- `Me manda a evidência`

## Guardrails

### A IA pode
- interpretar linguagem natural
- responder saudações
- orientar dúvidas simples
- pedir clarificação curta
- modular o tom da resposta

### A IA não pode
- inventar fatos operacionais
- afirmar incidente sem base
- alterar CID, horário, severidade ou estado
- usar humor em cenário crítico

## Fluxo resumido da DM

1. `chat.py` recebe a mensagem
2. `dm_router.py` decide a rota
3. se a rota for factual, `dm_intents.py` + `dm_queries.py` resolvem a consulta
4. `dm_presenter.py` monta a base da resposta
5. `ai_client.py` só entra quando permitido pela política

## Freshness do pipeline

Em produção, o pipeline factual principal segue:

**RouterOS 7 (UN1)** → **syslog remoto** → **rsyslog raw** → **SQLite** → **Bot Telegram**

Para evitar `db_stale` em períodos sem transição real de Netwatch, existe uma camada auxiliar de freshness:

**VM bot** → **`altis-heartbeat.timer` / `altis-heartbeat.service`** → **logger local (`noc_heartbeat`)** → **rsyslog local** → **`/var/log/mikrotik/un1.log`** → **SQLite**

Regras do `SELFTEST`:
- usa o contrato canônico `NOC|...`
- entra no mesmo raw/DB oficial
- mantém a fonte fresca
- **não deve virar incidente, recomendação ou destaque executivo**
- é tratado como ruído operacional filtrável

## UX do produto (DM)

O teclado inline cobre:
- clínica / home
- painel agora
- atendimento 2h
- evidências
- disponibilidade hoje
- qualidade hoje
- resumo 24h / 7d
- fonte (/where)

## Variáveis de ambiente

Use `.env.example` como baseline. O runtime real deve manter apenas segredos válidos no `.env`.

Pontos importantes:
- `TELEGRAM_BOT_TOKEN`
- `DM_ASSISTANT_*`
- `AI_ENABLED` e credenciais Cloudflare, quando aplicável
- paths do DB/LOG/tailer

## Testes formais da DM

A validação operacional do pacote atual deve cobrir, no mínimo:
- compile dos módulos Python alterados
- checagem de branding/UX no runtime
- smoke test da DM híbrida
- verificação de guardrails de humor/verdade operacional

## Smoke test recomendado pós-implantação

### DM
- `Oi, boa tarde`
- `Qual é o site do speed test?`
- `Como faço para medir a velocidade da internet?`
- `Telefone ok aí?`
- `E a internet?`
- `falhas hoje`
- `Caiu tudo agora`
- `evidência telefonia`

### Callback
- home
- painel agora
- disponibilidade hoje
- qualidade hoje
- resumo 24h
- evidências
- atendimento 2h
- where

## Operação segura

Com snapshot da VM bot e janela sem usuário, a estratégia recomendada é:

1. backup / snapshot
2. aplicar lote validado
3. `python -m compileall bot.py noc_bot`
4. smoke test no Telegram
5. restart do serviço
6. validar `/where`, UX e logs
7. rollback se necessário

## Frase de visão

**A IA da DM do ALTIS deve ser humana na conversa, inteligente na interpretação e rigorosa na verdade operacional.**
