# BOT ia NOC — UN1 — Documento Canônico (Fonte Única)

**Unidade:** UN1  
**Timezone:** America/Sao_Paulo (BRT)  
**ATUALIZADO_EM:** 2026-03-18 (BRT)  
**DATA_BASELINE (baseline vigente):** 2026-03-18  
**BOT_VERSION|build (último observado comprovado):** `v2026.03.15-dm-fix6|build=2026-03-15_182955`  
**Política:** este arquivo é a **única fonte da verdade** do projeto. Saídas “effective config” devem ser coladas nas seções de snapshots quando disponíveis.  
**Baseline histórico de referência:** `AS_BUILT_ATUAL=UN1_AS_BUILT_SNAPSHOT_2026-02-25_v11.md` | `DOC_MASTER_ATUAL=BOT_ia_NOC_UN1_Documento_Master_2026-02-25_v7.md`  
**Objetivo:** NOC operacional auditável para dual-WAN com ingestão confiável, histórico consultável, UX executiva na DM e camada conversacional híbrida sem romper a verdade operacional.

---

## 1) Decisões e princípios

1. **Telegram não é barramento confiável bot→bot / estado.**  
   Telegram é **front-end**. O barramento é o **collector**.

2. **Contrato de evento parseável e auditável** é obrigatório:  
   `NOC|unit=UN1|device=<id>|check=<nome>|state=UP/DOWN|host=<target>|cid=<correlation-id>`

3. **Pipeline determinístico > IA.**  
   IA conversa, interpreta e pode polir texto; números, estados, janelas, CID, severidade e evidência continuam vindo de DB/LOG/regras.

4. **Governança anti-drift.**  
   Documento canônico, toolkit ops, cofre de releases e evidências de reconciliação existem para impedir “runtime mágico”.

5. **Se faltar dado, marcar N/D.**  
   Não inventar. Nem no bot, nem na documentação.

---

## 2) Arquitetura em produção (AS-IS)

### 2.1 Pipeline end-to-end
**RouterOS 7 (UN1)** → **syslog remoto** → **rsyslog raw** → **SQLite** → **Bot Telegram** (AUTO: DB-first + fallback LOG)

### 2.2 Ingestão (syslog remoto)
- **Syslog UDP/514:** `192.168.10.20:514/UDP`
- **Filtro:** `$fromhost-ip == 192.168.20.1`
- **Raw log:** `/var/log/mikrotik/un1.log`

### 2.3 Persistência estruturada
- **DB SQLite (WAL):** `/var/lib/noc/noc.db`
- **State/offset tailer:** `/var/lib/noc/tailer.state.json`
- **Campo canônico do check:** `check_name`

### 2.4 Serviços (produção)
- `rsyslog.service` → active (running)
- `noc-sqlite-tailer.service` → active (running)
- `telegram-bot.service` → active (running)

### 2.5 Bot (modo padrão)
- **AUTO**: DB-first
- **Fallback**: LOG quando DB/tailer estiver stale/indisponível

### 2.6 Fingerprint (resumo)
1. `telegram-bot.service ExecStart` → `/home/telegram-bot/venv/bin/python /opt/telegram-bot/bot.py`
2. `noc-sqlite-tailer.service ExecStart` → `/usr/local/bin/noc-sqlite-tailer.py`
3. `rsyslog imudp bind` → `192.168.10.20:514/UDP`
4. `rsyslog filter → file` → `$fromhost-ip == 192.168.20.1` → `/var/log/mikrotik/un1.log`
5. `logrotate` → `/etc/logrotate.d/mikrotik-un1`
6. `SQLite DB` → `/var/lib/noc/noc.db` (WAL)
7. `tailer state` → `/var/lib/noc/tailer.state.json`
8. `schema campo do check` → `check_name`
9. `/where` → `BOT_VERSION|build` + `SOURCE=DB/LOG` + freshness + paths
10. `release/deploy` → `noc-release` + cofre `/var/lib/noc/releases`

---

## 3) Governaça, segurança e hardening

### 3.1 SecOps aplicado
- redaction global do token nos logs
- token rotacionado
- leak check esperado: `0`
- `.env` de runtime com segredos válidos e sem duplicação desnecessária

### 3.2 Hardening pendente recomendado
- API-SSL na porta `9005/TLS`
- allowlist em firewall input e/ou `/ip service address=`
- limitar origem a VPN / S2S / LAN de gestão

### 3.3 Regra documental
- **CANONICO_FULL vence**
- `docs/` complementa
- `README.md` resume
- `tools/ops/` operacionaliza
- conflito entre runtime e clone local deve virar evidência, não folclore

---

## 4) Toolkit operacional (notebook → VM bot)

A suíte `tools/ops` foi consolidada para operar a VM bot a partir do notebook.

### 4.1 Alvo operacional atual
- `VM_BOT_HOST=192.168.1.4`
- `VM_BOT_USER=bio`
- `REMOTE_BASE=/opt/telegram-bot`
- `REMOTE_SERVICE=telegram-bot.service`

### 4.2 Scripts relevantes
- `tools/ops/_cfg.sh`
- `tools/ops/reconcile-runtime.sh`
- `tools/ops/botrestart.sh`
- `tools/ops/botctl.sh`
- `tools/ops/README_ops_fluxo.md`

### 4.3 Funções
- `reconcile-runtime.sh` → compara runtime da VM com o clone local e reconcilia `noc_bot/`
- `botrestart.sh` → restart remoto com gate de `py_compile`
- `botctl.sh` → wrapper de status, inspect, restart, log, reconcile, deploy, ship-tag e drift
- `_cfg.sh` → configuração central do alvo

### 4.4 Fluxo operacional recomendado
```bash
tools/ops/botctl.sh status
tools/ops/botctl.sh inspect
tools/ops/botctl.sh restart "10 min ago" 80
tools/ops/botctl.sh log "20 min ago" 160
tools/ops/botctl.sh reconcile
```

### 4.5 Governança anti-drift
- detecção explícita de drift entre runtime da VM e clone local
- reconciliação controlada de `noc_bot/`
- evidência local em `_reconcile/<timestamp>/`
- commit local sem push automático na reconciliação

---

## 5) Catálogo de checks (UN1) e severidade

### 5.1 Checks
- **MUNDIVOX (WAN1)**: target `189.91.71.217` | src-address `189.91.71.218`
- **VALENET (WAN2)**: target `187.1.49.121` | src-address `187.1.49.122`
- **ESCALLO**: `187.33.28.57`
- **Telefonia (VOIP)**: `138.99.240.49`

### 5.2 Severidade
- **SEV1:** MUNDIVOX DOWN (com/sem VALENET)
- **SEV3:** VALENET DOWN com MUNDIVOX UP
- **SEV2:** serviços (ESCALLO/VOIP) DOWN com WANs UP

---

## 6) UX “produto” (DM)

### 6.1 Objetivo da DM
Entregar uma assistente operacional curta, útil e auditável para supervisão/coordenação, sem ruído técnico desnecessário.

### 6.2 Tela principal da DM
- status executivo por unidade
- leitura de Internet, Telefonia e Escallo
- impacto resumido
- botões curtos para navegação

### 6.3 Linha “Internet”
Modo consolidado:
- `🌐 Internet — Online`
- `🌐 Internet — Backup ativo`
- `🌐 Internet — Indisponível`
- `🌐 Internet — Instável`

### 6.4 Botões principais
- Atendimento (2h)
- Painel (Tempo real)
- Disponibilidade Hoje
- Qualidade Hoje
- Resumo 24h
- Semana
- Evidências
- Fonte (/where)

### 6.5 Home DM multi-unidades
- UN1 — Eldorado
- UN2 — Barreiro
- UN3 — Alípio de Mello
- `home` como retorno ao painel inicial

---

## 7) DM consultiva (FIX6)

Regras funcionais já consolidadas:
- serviço explicitamente citado na mensagem atual vence contexto anterior
- confirmações curtas, como “tem certeza?”, reutilizam o último contexto útil
- “status atual” resolve para painel geral
- perguntas fora de escopo deixam de cair em painel/home
- probes curtos por serviço, como “Escallo” e “Telefone”, resolvem como status factual

Referências já documentadas:
- PR #8 (merged)
- Merge commit: `cbce6ee`
- Commit FIX6: `c610a2a`
- Tag: `v2026.03.15-fix6-dm-consultiva`

---

## 8) DM assistiva / híbrida (estado atual)

> Esta é a principal atualização documental de 2026-03-18.  
> A documentação agora passa a cobrir não só a FIX6, mas também o **motor conversacional atual** da DM.

### 8.1 Princípio
A DM precisa ser:
- humana na conversa
- curta na clarificação
- factual quando consultar operação
- segura quando sair do escopo
- incapaz de inventar fato operacional

### 8.2 Rotas formais da DM
Rotas implementadas:
- `consult`
- `incident`
- `clarify`
- `social`
- `help`
- `none`

Resumo:
- **consult** → consulta factual baseada em intenção/serviço/período
- **incident** → trata relato de incidente e direciona para atendimento 2h
- **clarify** → fecha lacunas de escopo/contexto
- **social** → saudações e contato humano leve
- **help** → ajuda simples segura, fora do fato operacional
- **none** → sem rota tratável; aplica fallback seguro

### 8.3 Ordem de decisão (alto nível)
1. sessão pendente / clarificação em aberto
2. social determinístico
3. help determinístico
4. consult determinístico
5. incidente determinístico
6. fallback por classificador IA, se habilitado
7. fallback seguro por clarificação / home / out-of-scope

### 8.4 Componentes internos da DM
- `noc_bot/handlers/chat.py` — gateway da mensagem livre
- `noc_bot/dm_router.py` — decisão de rota
- `noc_bot/dm_session.py` — contexto curto e pendências
- `noc_bot/dm_intents.py` — parser factual
- `noc_bot/dm_queries.py` — consulta à fonte real
- `noc_bot/dm_presenter.py` — render factual
- `noc_bot/ai_client.py` — IA opcional para classificar ou polir

### 8.5 Social
Exemplos:
- `Oi`
- `Oi, boa tarde`
- `Bom dia`

Comportamento:
- responde de forma humana
- não afirma DB/LOG/checagem operacional
- não simula verificação que não ocorreu

### 8.6 Help
Exemplos:
- `Qual é o site do speed test?`
- `Como faço para medir a velocidade da internet?`

Comportamento:
- ajuda simples e segura
- pode citar o Speedtest
- não converte ajuda simples em fato operacional

### 8.7 Consult
Exemplos:
- `Telefone ok aí?`
- `Escallo`
- `falhas hoje`
- `status atual`

Comportamento:
- intenção é resolvida
- consulta vai para DB/LOG/regras
- presenter monta a base factual
- IA só pode polir a frase quando permitido

### 8.8 Incident
Exemplos:
- `Caiu tudo agora`
- `Sem internet`
- `parou agora`

Comportamento:
- incidente forte → rota `incident`
- atendimento 2h / triagem é acionado
- contexto útil do serviço pode ser salvo para follow-up

### 8.9 Clarify
Tipos documentados:
- `service_scope`
- `service_select`
- `status_or_window`
- `consult_or_incident`
- `generic`

Uso:
- pedir clarificação curta
- fechar se o usuário quer status atual, falha hoje ou resumo da semana
- diferenciar consulta versus incidente em andamento
- escolher serviço quando a pergunta veio vaga demais

### 8.10 Contexto curto
A sessão curta guarda:
- último serviço
- última intenção
- último período
- última rota
- pendência de clarificação

Objetivos:
- suportar follow-up curto
- responder “tem certeza?”
- suportar retomadas curtas como `e a internet?` → `falhas hoje`

### 8.11 Fora de escopo
Perguntas fora do escopo operacional da DM devem:
- evitar cair em painel/home indevidamente
- responder com orientação curta de escopo
- não gerar consulta factual fake

### 8.12 IA opcional e flags
A família `DM_ASSISTANT_*` controla a superfície da DM.

Flags relevantes já presentes no código:
- `DM_ASSISTANT_ENABLED`
- `DM_ASSISTANT_SHADOW_MODE`
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

Papel da IA:
- classificar quando o determinismo não fechou bem
- modular tom ou acabamento textual
- responder help/social quando permitido

Limite da IA:
- não gerar fato operacional
- não alterar CID, severidade, horário, fonte ou estado
- não usar humor em cenário crítico

### 8.13 Guardrails
A IA pode:
- interpretar linguagem natural
- pedir clarificação curta
- responder saudações
- orientar ajuda simples
- modular tom da resposta

A IA não pode:
- inventar status operacional
- afirmar incidente sem base
- trocar severidade, CID ou estado
- transformar help/social em suposta verificação real

### 8.14 Testes e smoke tests
Casos mínimos já assumidos pela documentação atual:
- `Oi, boa tarde`
- `Qual é o site do speed test?`
- `Como faço para medir a velocidade da internet?`
- `Telefone ok aí?`
- `E a internet?`
- `falhas hoje`
- `Caiu tudo agora`
- `evidência telefonia`

Se o bundle implantado incluir `tests/`, recomenda-se executar a suíte antes do restart.

Observação: o runtime analisado inclui `tests/test_dm_router.py`, `tests/test_dm_guardrails.py`, `tests/test_callbacks.py` e `tests/test_dm_session.py`.

### 8.15 Documento detalhado de apoio
- `docs/DM_ASSISTIVA_HIBRIDA.md`

---

## 9) UX “técnico” (Grupo NOC)
- anti-ruído: responde por @menção ou reply
- botões técnicos: status / analyze / timeline / evidências / fonte
- mesma fonte factual da DM
- IA opcional continua sem poder inventar número ou estado

---

## 10) Evidências (prova) — contrato
Triggers aceitos:
- `evidência`
- `evidencias`
- `prova`
- `provas`

Regra:
- exigir o serviço para evitar prova errada

Entrega padrão:
1. painel/contexto
2. evidência compacta
3. texto pronto para operadora com até 5 CIDs recentes

---

## 11) Comandos operacionais do bot
- `/where`
- `/status`
- `/timeline N`
- `/analyze 24h|7d|30d`
- Atendimento (2h)
- Evidência por texto natural

---

## 12) Deploy seguro (padrão)

### 12.1 Conceito
Deploy padrão é **ZIP → unzip stage → rsync espelho**.  
No fluxo seguro, atualiza-se **somente** `noc_bot/` para preservar `bot.py`, `.env`, `venv`, DB/state e logs.

### 12.2 Princípios
- evitar deploy durante incidente ativo
- ter rollback real
- não versionar segredos
- validar serviço e logs pós-deploy
- incluir smoke test da DM híbrida no critério de aceite

### 12.3 Smoke test pós-deploy (mínimo)
DM:
- `Oi, boa tarde`
- `Qual é o site do speed test?`
- `Telefone ok aí?`
- `E a internet?`
- `falhas hoje`
- `Caiu tudo agora`
- `evidência telefonia`

Callbacks:
- home
- painel agora
- disponibilidade hoje
- qualidade hoje
- resumo 24h
- evidências
- atendimento 2h
- where

### 12.4 Testes formais
Se o bundle implantado incluir `tests/`:
- rodar `python -m compileall bot.py noc_bot tests`
- executar a suíte disponível antes do restart
- só depois reiniciar `telegram-bot.service`

### 12.5 Rollback
- voltar para tag/release anterior
- restaurar backup
- reiniciar serviço
- validar `/where`, logs e smoke test essencial

---

## 13) Troubleshooting rápido

### 13.1 Bot em loop
- conferir `ExecStart`
- conferir presença de `bot.py`
- `journalctl -u telegram-bot -o cat -n 80`

### 13.2 DM respondendo estranho
- conferir flags `DM_ASSISTANT_*`
- verificar shadow modes
- validar se o texto caiu em `social`, `help`, `consult`, `incident` ou `clarify`
- revisar logs do roteador / presenter / AI finish

### 13.3 “DB stale”
- conferir `noc-sqlite-tailer.service`
- conferir escrita em `/var/lib/noc/noc.db`
- lembrar que o bot em AUTO deve cair para LOG quando necessário

### 13.4 Clarificação inesperada
- revisar contexto curto
- revisar TTL da sessão
- revisar se a pergunta ficou sem serviço, sem janela ou ambígua

---

## 14) Changelog consolidado

- 2026-03-18 — documentação oficial passa a cobrir formalmente a **DM assistiva/híbrida** além da FIX6.
- 2026-03-18 — criado `docs/DM_ASSISTIVA_HIBRIDA.md` para fechar o gap entre código e documentação.
- 2026-03-18 — `README.md`, `docs/README.md`, `docs/DEPLOY.md`, `baseline/00_INDEX_CANONICO.md` e este canônico foram atualizados para refletir a camada DM atual.
- 2026-03-18 — toolkit `tools/ops` consolidado como parte explícita da governança.
- 2026-03-15 — PR #8 mergeada em `main`, consolidando a DM consultiva com parser determinístico, query factual, presenter e roteamento consultivo.
- 2026-03-15 — FIX6 homologada em runtime real e tagueada como `v2026.03.15-fix6-dm-consultiva`.
- 2026-02-28 — `noc-release` padroniza release ZIP + deploy seguro + rollback e sanity gate.
- 2026-02-28 — cofre persistente de releases em `/var/lib/noc/releases`.
- 2026-02-27 — padronização de evidência, patch em `sources.py` e validação operacional da DM.
- 2026-02-26 — melhorias de UX na DM, incluindo modos da Internet e contingência.

---

## 15) Próximos passos recomendados
1. anti-flap na fonte (RouterOS / Netwatch)
2. hardening API-SSL 9005 (allowlist)
3. qualidade por operadora (L1/L2)
4. expansão multi-unidade (UN2 / UN3)
5. refinamento fino de clarificação, continuidade de contexto e respostas binárias diretas

---

## SNAPSHOTS — Effective Config (colado) — 2026-02-28 (BRT)

### systemd (noc-sqlite-tailer) — `systemctl cat noc-sqlite-tailer`
```ini
# /etc/systemd/system/noc-sqlite-tailer.service
[Unit]
Description=NOC SQLite Tailer (ingest NOC| events into SQLite)
After=network.target
Wants=network.target

[Service]
Type=simple
User=telegram-bot
Group=telegram-bot
Environment=LOG_PATH=/var/log/mikrotik/un1.log
Environment=DB_PATH=/var/lib/noc/noc.db
Environment=STATE_PATH=/var/lib/noc/tailer.state.json
Environment=BOOTSTRAP_LINES=20000
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/local/bin/noc-sqlite-tailer.py
Restart=always
RestartSec=2
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/noc
ReadOnlyPaths=/var/log/mikrotik/un1.log

[Install]
WantedBy=multi-user.target

# /etc/systemd/system/noc-sqlite-tailer.service.d/20-rwpaths.conf
[Service]
ReadWritePaths=/var/lib/noc /var/log/mikrotik

# /etc/systemd/system/noc-sqlite-tailer.service.d/40-paths.conf
[Service]
SupplementaryGroups=adm
ReadWritePaths=/var/lib/noc
ReadOnlyPaths=/var/log/mikrotik

# /etc/systemd/system/noc-sqlite-tailer.service.d/50-noc-state.conf
[Service]
User=telegram-bot
Group=telegram-bot
StateDirectory=noc
StateDirectoryMode=0750
Environment=LOG_PATH=/var/log/mikrotik/un1.log
Environment=DB_PATH=/var/lib/noc/noc.db
Environment=STATE_PATH=/var/lib/noc/tailer.state.json
Environment=FLUSH_EVERY_SECONDS=5
Environment=STATE_SAVE_EVERY_SECONDS=5
Environment=SLEEP_IDLE=0.5
Environment=BOOTSTRAP_LINES=20000
Environment=BACKFILL_ENABLE=1
Environment=BACKFILL_MAX_BYTES=209715200
Environment=BACKFILL_LINES=50000
```

### rsyslog — bind UDP/514 (`/etc/rsyslog.d/10-mikrotik.conf`)
```conf
module(load="imudp")
input(type="imudp" address="192.168.10.20" port="514")
```

### rsyslog — filtro + raw log (`/etc/rsyslog.d/20-mikrotik-files.conf`)
```conf
if ($fromhost-ip == "192.168.20.1") then {
  action(type="omfile" file="/var/log/mikrotik/un1.log")
  stop
}
```

### logrotate (`/etc/logrotate.d/mikrotik-un1`)
```conf
/var/log/mikrotik/un1.log {
  daily
  rotate 30
  missingok
  notifempty
  compress
  delaycompress
  dateext
  dateformat -%Y%m%d
  create 0640 syslog adm
  sharedscripts
  postrotate
    systemctl kill -s HUP rsyslog.service >/dev/null 2>&1
    true
  endscript
}
```

### prova do socket UDP/514 (`ss -lunp | grep :514`)
```text
UNCONN 0      0                         192.168.10.20:514        0.0.0.0:*    users:(("rsyslogd",pid=865,fd=6))
```

### SQLite schema (`sqlite3 /var/lib/noc/noc.db .schema`)
```sql
CREATE TABLE events (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ts TEXT NOT NULL,
      sys_host TEXT,
      unit TEXT,
      device TEXT,
      check_name TEXT,
      state TEXT,
      host TEXT,
      cid TEXT,
      raw TEXT NOT NULL,
      raw_sha1 TEXT NOT NULL UNIQUE
    );
CREATE TABLE sqlite_sequence(name,seq);
CREATE INDEX idx_events_ts ON events(ts);
CREATE INDEX idx_events_unit_check_ts ON events(unit, check_name, ts);
```

### prova WAL (`ls -lah /var/lib/noc/noc.db*`)
```text
-rw-r----- 1 telegram-bot telegram-bot 44K Feb 28 13:19 /var/lib/noc/noc.db
-rw-r----- 1 telegram-bot telegram-bot 32K Feb 28 15:09 /var/lib/noc/noc.db-shm
-rw-r----- 1 telegram-bot telegram-bot 69K Feb 28 15:02 /var/lib/noc/noc.db-wal
```
