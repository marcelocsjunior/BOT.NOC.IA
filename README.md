# BOT ia NOC (UN1) — Coletor + Telegram Bot (AS-RUNNING)

Bot operacional de NOC para a unidade **UN1**: ingestão de eventos do **MikroTik RouterOS 7** (dual WAN), persistência e consulta via **Telegram**, com **governança de versão**, **evidências** e **anti-drift**.

> Princípio de arquitetura: **Telegram é front-end (push/consulta), não é barramento**. O barramento confiável é o **Collector** (syslog/DB).

---

## Arquitetura (produção)

Pipeline end-to-end (produção):

**RouterOS 7 (UN1)** → **Syslog remoto** → **rsyslog (raw)** → **SQLite (WAL)** → **Bot Telegram (AUTO: DB-first + fallback LOG)**

Pontos canônicos (produção):
- Syslog: `192.168.10.20:514/UDP`
- Filtro de origem (RouterOS): `192.168.20.1`
- Raw log: `/var/log/mikrotik/un1.log`
- DB: `/var/lib/noc/noc.db` (**SQLite WAL**)
- State/offset: `/var/lib/noc/tailer.state.json`
- Campo canônico no schema: `check_name`

Canal complementar (não dependência do pipeline):
- RouterOS API-SSL: **porta 9005/TLS** (útil para consultas/diagnóstico/hardening futuro)

---

## Contrato de evento (parseável/auditável)

Formato canônico (linha única):
`NOC|unit=UN1|device=<id>|check=<nome>|state=UP/DOWN|host=<target>|cid=<correlation-id>`

Objetivos:
- Timeline determinística (consulta/forense)
- Correlação por `cid`
- Evidência “prova” sem improviso

---

## Catálogo de checks (UN1) — produção

- **MUNDIVOX (WAN1)**: target `189.91.71.217` | src-address `189.91.71.218`
- **VALENET (WAN2)**: target `187.1.49.121` | src-address `187.1.49.122`
- **ESCALLO**: `187.33.28.57`
- **Telefonia (VOIP)**: `138.99.240.49`

---

## Severidade (matriz de decisão)

- **SEV1**: `MUNDIVOX` **DOWN** (com/sem `VALENET`)
- **SEV3**: `VALENET` **DOWN** com `MUNDIVOX` **UP**
- **SEV2**: serviços (`ESCALLO` / `VOIP`) **DOWN** com WANs **UP**

---

## Serviços (produção)

Esperado em execução:
- `rsyslog.service`
- `noc-sqlite-tailer.service`
- `telegram-bot.service`

Modo do bot: **AUTO**
- Primário: **DB-first**
- Fallback: **LOG** quando DB/tailer estiver stale/indisponível

---

## UX do Bot (produto vs técnico)

### DM (supervisora/coordenadora) — “produto”
- Resposta **curta (C2)** + painel resumido com status dos serviços (Link1/Link2/Telefonia/Escallo)
- Botões curtos para navegação: **Torre de Controle / Resumo 24h / Semana / Evidências / Fonte**
- Objetivo: reduzir ruído e acelerar decisão (impacto, redundância, próximo passo)

### Grupo NOC — “técnico”
- Anti-ruído: responde apenas por **@menção** ou **reply**
- Botões técnicos: **Status / Analyze 24h/7d / Timeline 50 / Evidências / Fonte**
- Objetivo: operação e troubleshooting com rastreabilidade

---

## Evidências (“prova” + texto pronto)

Trigger aceito (frase natural):
- `evidência`, `evidencias`, `evidências`, `prova`, `provas`

Regra de segurança:
- exigir o **serviço** (ex.: “evidência telefonia”) para evitar prova errada

Entrega (3 mensagens):
1) painel/seleção
2) evidência compacta + botões
3) **texto pronto** para operadora com **5 CIDs mais recentes** + nota “há mais”

---

## Versionamento e /where (diagnóstico)

Contrato do `/where` (diagnóstico):
- `BOT_VERSION=...|build=...`
- `SOURCE=DB/LOG` + freshness
- paths relevantes (DB/LOG)

Padrão no `.env`:
- `BOT_VERSION=YYYY-MM-DD-dm-group-ux|build=YYYY-MM-DD_HHMMSS`
- `BUILD_ID=YYYY-MM-DD_HHMMSS`

Exemplo (Release 0 / AS-RUNNING):
- Tag sugerida: `un1-2026-02-28-build-2026-02-28_094935`

---

## Estrutura do repositório

- `bot.py` — entrypoint/shim do bot
- `noc_bot/` — core do bot (handlers, UI, parsers, evidências, sources)
- `infra/etc/` — snapshot **AS-RUNNING** de produção:
  - `rsyslog.d/*`
  - `logrotate.d/*`
  - `systemd/system/*` (unit + drop-ins)
- `release/` — hashes/artefatos do snapshot (prova do AS-RUNNING)
 - `docs/` — documentação operacional (índice: [docs/README.md](docs/README.md); sync: [docs/SYNC_RUNBOOKS.md](docs/SYNC_RUNBOOKS.md))
- `.env.example` — modelo de variáveis (sem segredos)
- `.gitignore` — bloqueia runtime (DB/logs/state/venv)

> Nota: `infra/etc/` é **foto do que está em produção** (governança/forense). Mudança de infra deve ser tratada como Change Control (commit + release/tag) para evitar drift silencioso.

---

## Configuração

Use `.env.example` como base e crie o `.env` **somente no runtime** (não versionar).

Regras:
- Nunca commitar `.env` nem tokens.
- Manter apenas `TELEGRAM_BOT_TOKEN` no `.env` (reduz risco de regressão por variáveis duplicadas).
- `BOT_VERSION` e `BUILD_ID` devem refletir o build em execução.

---

## Runbook rápido — Deploy seguro (sem quebra em produção)

### Objetivo
Atualizar o **core do bot** com risco controlado, preservando runtime e dados.

### Escopo do deploy (o que muda)
- **Muda:** `noc_bot/` (e, quando necessário, `bot.py`)
- **Não muda:** `.env`, `venv/`, `/var/lib/noc/*` (DB/state), `/var/log/mikrotik/*` (logs), unidades systemd/rsyslog/logrotate (a menos que a mudança seja explicitamente infra)

### Gate (pré-deploy)
- Evitar deploy durante incidente ativo (SEV em andamento)
- Snapshot/release do estado “antes” disponível (rollback real)
- Confirmação de que não há segredos versionados

### Sanity checks pós-deploy (DoD)
- `telegram-bot.service` ativo e sem restart loop (StartLimit ok)
- Bot responde `/where` com `BOT_VERSION|build` esperado
- `/where` indica `SOURCE=DB` quando DB está saudável (LOG só em fallback)
- Timeline/Status coerentes (DB/LOG conforme fonte)

### Rollback (contenção)
- Voltar para tag/release anterior
- Restart do `telegram-bot.service`
- Validar `/where` + sanity checks
- Registrar ChangeLog (causa/impacto/decisão)

---

## Operação e troubleshooting (atalhos)

### Health do runtime (serviços)
- `rsyslog.service` deve estar **active (running)** e recebendo UDP/514
- `noc-sqlite-tailer.service` deve estar **active (running)** e alimentando SQLite
- `telegram-bot.service` deve estar **active (running)** e respondendo comandos

### DB (sanidade)
- DB em WAL (esperado): `journal_mode = wal`
- Schema deve conter `check_name` (campo canônico)

> Observação operacional: usar “staleness por idade do último evento” pode dar falso positivo em períodos estáveis. Recomendação: implementar heartbeat/SELFTEST periódico (1–5 min) e excluir SELFTEST de KPIs.

---

## Segurança e hardening (baseline)

- Redaction global do token nos logs (evita vazamento)
- Token rotacionado
- “Leak check” esperado: **0**
- Hardening recomendado (API-SSL 9005):
  - allowlist no firewall input e/ou `/ip service address=`
  - limitar origem a VPN/S2S/LAN mgmt (não expor na internet)

---

## Governança (anti-drift)

- Este repo representa **fonte auditável** (código + snapshot AS-RUNNING + evidências/hashes).
- Mudança em produção deve virar **commit + tag/release**.
- Conflitos de documentação: **AS-RUNNING/AS-BUILT vence**; documentação complementa, não substitui.

---

## Releases

**Release 0 (AS-RUNNING)**:
- Tag sugerida: `un1-2026-02-28-build-2026-02-28_094935`
- Assets: `.tar.gz` + `.sha256` (snapshot do que estava rodando, com prova de integridade)

---

## Roadmap (próximos passos NOC)
1) Anti-flap na fonte (RouterOS / Netwatch): debounce + cooldown  
2) Hardening API-SSL 9005: allowlist no firewall e/ou `/ip service address=`  
3) Multi-unidade (UN2/UN3): replicar contrato e core modular mantendo DM “produto” por unidade
