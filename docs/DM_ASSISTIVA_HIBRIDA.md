# DM_ASSISTIVA_HIBRIDA.md — BOT ia NOC / UN1

## Objetivo

Documentar formalmente a camada **DM assistiva/híbrida** do BOT ia NOC, cobrindo comportamento real, guardrails, flags e critérios mínimos de validação.

Este documento existe para fechar um gap: o repositório já descrevia a UX da DM e a FIX6, mas o motor conversacional atual da DM já avançou além disso.

## Princípio arquitetural

A camada DM segue a regra:

- **a IA interpreta intenção e organiza a conversa**
- **DB / LOG / regras provam os fatos**
- **a IA não inventa status, causa raiz, severidade nem evidência**

Resultado:
- a DM pode ser mais humana
- a DM pode ser mais útil
- a DM não pode virar alucinação operacional

## Escopo funcional da DM

A DM atual precisa resolver, sem misturar alhos com bugalhos:

1. **Social**
   - saudações e abertura de conversa

2. **Help**
   - ajuda simples e segura fora do fato operacional

3. **Consult**
   - consulta factual sobre unidade/serviço/período

4. **Incident**
   - relato de incidente em andamento

5. **Clarify**
   - fechamento de lacunas de contexto ou escopo

6. **Fallback seguro**
   - quando nada couber, cair em comportamento previsível

## Componentes

- `noc_bot/handlers/chat.py` — entrada de texto livre na DM e no grupo
- `noc_bot/dm_router.py` — roteador principal da DM
- `noc_bot/dm_session.py` — sessão curta, contexto e pendências
- `noc_bot/dm_intents.py` — parser determinístico
- `noc_bot/dm_queries.py` — consulta factual
- `noc_bot/dm_presenter.py` — render factual
- `noc_bot/ai_client.py` — IA opcional

## Rotas formais

As rotas implementadas na DM são:

- `consult`
- `incident`
- `clarify`
- `social`
- `help`
- `none`

### 1) `social`
Casos típicos:
- `Oi`
- `Oi, boa tarde`
- `Bom dia`

Objetivo:
- responder de forma humana
- manter a DM acolhedora
- não fingir checagem operacional

Guardrail:
- resposta social não pode alegar “verifiquei DB/LOG”
- social não pode ser confundido com consulta factual

### 2) `help`
Casos típicos:
- `Qual é o site do speed test?`
- `Como faço para medir a velocidade da internet?`

Objetivo:
- responder dúvida simples e segura
- orientar o usuário sem cair em fato operacional inventado

Guardrail:
- help não pode virar falso status
- speedtest é ajuda, não prova de incidente

### 3) `consult`
Casos típicos:
- `Telefone ok aí?`
- `Escallo`
- `falhas hoje`
- `status atual`

Objetivo:
- resolver intenção, serviço e período
- consultar fonte factual real
- responder de forma objetiva

Pipeline esperado:
1. parser/intenção
2. query factual
3. presenter factual
4. IA opcional apenas para acabamento, quando permitido

### 4) `incident`
Casos típicos:
- `Caiu tudo agora`
- `Sem internet`
- `parou agora`

Objetivo:
- distinguir incidente de consulta
- acionar fluxo de atendimento/triagem
- guardar contexto útil para follow-up

### 5) `clarify`
Casos típicos:
- `E a internet?`
- `Hoje?`
- `Qual deles?`

Objetivo:
- pedir o mínimo de clarificação necessário
- fechar a lacuna sem burocracia

Tipos documentados:
- `service_scope`
- `service_select`
- `status_or_window`
- `consult_or_incident`
- `generic`

### 6) `none`
Quando nada couber:
- não forçar uma resposta factual falsa
- não cair em UX errada
- seguir fallback seguro (home, help, out-of-scope ou silêncio controlado, conforme o caso)

## Ordem de decisão (alto nível)

A ordem real do motor conversacional, em alto nível, é:

1. sessão/clarificação pendente
2. social determinístico
3. help determinístico
4. consult determinístico
5. incident determinístico
6. fallback IA classifier, se habilitado
7. fallback seguro

Essa ordem evita:
- chamar IA para o que já está claro
- tratar help/social como NOC factual
- responder incidente como se fosse conversa casual

## Contexto curto de sessão

A sessão curta guarda, quando aplicável:
- último serviço
- última intenção
- último período
- última rota
- pendência de clarificação

Objetivos:
- permitir follow-up curto
- reutilizar contexto útil
- sustentar confirmações curtas

Exemplos:
- `E a internet?` → `falhas hoje`
- `Telefone ok aí?` → `Tem certeza?`

Guardrail:
- contexto curto ajuda; ele não pode atropelar um serviço explicitamente citado na mensagem atual

## Confirmações curtas

A documentação da FIX6 já formalizou:
- serviço explícito vence contexto anterior
- `tem certeza?` reutiliza contexto útil
- `status atual` resolve como painel geral

A camada híbrida mantém isso e adiciona:
- sessão curta formal
- clarificação guiada
- resposta mais humana em social/help
- AI classifier opcional quando o determinismo não fecha bem

## Fora de escopo

Perguntas fora do escopo operacional devem:
- evitar cair em painel/home de forma errada
- responder com orientação curta de escopo
- não produzir fato operacional inexistente

Exemplo de linha segura:
- “Isso foge do escopo operacional deste bot. Aqui eu respondo status, falhas, CID, resumo e evidências...”

## IA opcional — o que pode e o que não pode

### A IA pode
- interpretar linguagem natural
- classificar rota quando o determinismo estiver incerto
- modular tom
- responder social/help
- polir uma resposta factual pronta

### A IA não pode
- inventar status operacional
- criar incidente do nada
- afirmar causa raiz sem base
- alterar severidade, CID, horário ou fonte
- trocar uma resposta factual por prosa bonita e vazia

## Flags relevantes (`DM_ASSISTANT_*`)

Família relevante já existente no código:

- `DM_ASSISTANT_ENABLED`
- `DM_ASSISTANT_SHADOW_MODE`
- `DM_ASSISTANT_ALLOWED_CHAT_IDS`
- `DM_ASSISTANT_STYLE`
- `DM_ASSISTANT_MAX_REPLY_LINES`
- `DM_ASSISTANT_MIN_CONFIDENCE`
- `DM_ASSISTANT_ENABLE_AI_FINISH`
- `DM_ASSISTANT_ENABLE_DM_ROUTER`
- `DM_ASSISTANT_ENABLE_AI_CLASSIFIER`
- `DM_ASSISTANT_CLASSIFIER_SHADOW_MODE`
- `DM_ASSISTANT_ENABLE_CLARIFY`
- `DM_ASSISTANT_ENABLE_SESSION_CONTEXT`
- `DM_ASSISTANT_SESSION_TTL_S`
- `DM_ASSISTANT_MAX_CLARIFY_TURNS`
- `DM_ASSISTANT_ENABLE_SOCIAL`
- `DM_ASSISTANT_ENABLE_GENERAL_HELP`
- `DM_ASSISTANT_ENABLE_AI_GENERAL`
- `DM_ASSISTANT_HUMOR_ENABLED`

### Leitura prática das flags
- **router** liga/desliga a superfície híbrida principal
- **classifier** chama IA quando o determinismo não fechou bem
- **AI finish** só entra no acabamento textual de resposta factual
- **AI general** cobre help/social
- **shadow modes** servem para homologação/observação sem responder de fato

## Guardrails operacionais

### Guardrails duros
- resposta factual tem de vir de DB/LOG/regras
- social/help não podem se travestir de checagem operacional
- incidente não pode ser tratado como small talk
- clarificação não pode virar interrogatório infinito
- serviço explícito na frase atual vence contexto antigo

### Guardrails de UX
- respostas curtas
- clarificação mínima
- foco em ação
- zero burocracia desnecessária
- nada de humor em cenário crítico

## Testes formais observados no bundle de runtime

O runtime analisado inclui:

- `tests/test_dm_router.py`
- `tests/test_dm_guardrails.py`
- `tests/test_callbacks.py`
- `tests/test_dm_session.py`

Cenários já cobertos:
- social route
- help route (Speedtest)
- clarify por service scope
- incident route
- clarify seguido de consult
- IA classifier não chamado quando o determinístico resolve
- social não pode fingir checagem operacional
- callbacks desconhecidos com fallback gracioso
- TTL da sessão

## Smoke test manual mínimo

### Social
- `Oi, boa tarde`

### Help
- `Qual é o site do speed test?`
- `Como faço para medir a velocidade da internet?`

### Consult
- `Telefone ok aí?`
- `Escallo`
- `falhas hoje`
- `status atual`

### Clarify
- `E a internet?` → follow-up: `falhas hoje`

### Incident
- `Caiu tudo agora`

### Evidência
- `evidência telefonia`

### Callback
- home
- analyze:7d
- where
- evidências

## Limitações atuais conhecidas

O estado documental e os próprios status operacionais já apontam pontos de lapidação conversacional:

- follow-up curto ainda pode exigir ajuste fino
- contexto útil pode se perder em perguntas elípticas mais longas
- respostas binárias diretas ainda podem sair genéricas demais
- tom pode evoluir sem sacrificar objetividade

Esses pontos são de **polimento conversacional**, não de reconstrução da base.

## Decisão documental

A partir de 2026-03-18, qualquer mudança relevante na camada DM assistiva deve atualizar:
- `baseline/BOT_ia_NOC_UN1_CANONICO.md`
- `docs/DM_ASSISTIVA_HIBRIDA.md`
- `docs/DEPLOY.md` se o smoke test ou critério de aceite mudar
- `README.md` se houver impacto de arquitetura/percepção externa

Em resumo:
- produto no README
- contrato no canônico
- detalhes da DM aqui
- aceite operacional no DEPLOY

Sem isso, o código anda mais rápido que o papel — e essa conta sempre chega.
