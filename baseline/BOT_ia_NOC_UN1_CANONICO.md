# BOT ia NOC — UN1 — Documento Canônico (Fonte Única)

**Unidade:** UN1  
**Timezone:** America/Sao_Paulo (BRT)  
**ATUALIZADO_EM:** 2026-03-15 (BRT)  
**DATA_BASELINE (baseline vigente):** 2026-02-25  
**BOT_VERSION|build (último observado / exemplo):** `2026-02-28-dm-group-ux|build=2026-02-28_094935`  
**Política:** este arquivo é a **única fonte da verdade** do projeto (sem anexos). Saídas “effective config” devem ser **coladas** nas seções de *snapshots* abaixo.  
**Baseline de referência (histórico, não-anexado):** `AS_BUILT_ATUAL=UN1_AS_BUILT_SNAPSHOT_2026-02-25_v11.md` | `DOC_MASTER_ATUAL=BOT_ia_NOC_UN1_Documento_Master_2026-02-25_v7.md`  
**Objetivo:** NOC operacional auditável para dual-WAN (MikroTik RouterOS 7) com ingestão confiável, histórico consultável, UX “produto” no Telegram (DM) e UX técnica no grupo.

---

## 1) Decisões e princípios (histórico do projeto)

1. **Telegram não é barramento confiável bot→bot / estado.**  
   Telegram é **front-end** (push/consulta). O barramento é o **collector**.

2. **Contrato de evento padronizado (parseável/auditável)** é obrigatório para histórico, SLA e evidência:  
   `NOC|unit=UN1|device=<id>|check=<nome>|state=UP/DOWN|host=<target>|cid=<correlation-id>`

3. **Pipeline determinístico > IA.**  
   IA é opcional para texto/recomendações. Números e estado vêm do log/DB.

4. **Governança anti-drift:**  
   - Uma fonte de verdade e ChangeLog curto.  
   - Conflito entre docs: **AS_BUILT vence** (quando existir).  
   - Se algo não estiver documentado: marcar como **N/D**.

---

## 2) Arquitetura em produção (AS-IS atual)

### 2.1 Pipeline end-to-end (produção)
**RouterOS 7 (UN1)** → **syslog remoto** → **rsyslog raw** → **SQLite** → **Bot Telegram** (AUTO: DB-first + fallback LOG)

### 2.2 Ingestão (syslog remoto)
- **Syslog UDP/514:** `192.168.10.20:514/UDP`
- **Filtro:** `$fromhost-ip == 192.168.20.1`
- **Raw log:** `/var/log/mikrotik/un1.log`

### 2.3 Persistência estruturada
- **DB SQLite (WAL):** `/var/lib/noc/noc.db`
- **State/offset tailer:** `/var/lib/noc/tailer.state.json`
- **Campo canônico do check no schema:** `check_name`

### 2.4 Serviços (produção)
- `rsyslog.service` → active (running)  
- `noc-sqlite-tailer.service` → active (running)  
- `telegram-bot.service` → active (running)  

### 2.5 Bot (modo padrão)
- **Modo AUTO**: DB-first (consulta a DB).  
- Se DB/tailer stale/indisponível: **fallback LOG**.


### 2.6 Fingerprint (10 linhas) — carimbo técnico (baseline vs effective)
- Regra: se não estiver colado do ambiente, marcar **N/D** (não inventar).
1. `telegram-bot.service ExecStart` → baseline: `/home/telegram-bot/venv/bin/python /opt/telegram-bot/bot.py` | effective: `/home/telegram-bot/venv/bin/python /opt/telegram-bot/bot.py`
2. `noc-sqlite-tailer.service ExecStart` → baseline: **N/D** | effective: **N/D**
3. `rsyslog imudp bind` → `192.168.10.20:514/UDP` (conf: `/etc/rsyslog.d/10-mikrotik.conf`) | effective: **N/D**
4. `rsyslog filter→file` → `$fromhost-ip == 192.168.20.1` → `/var/log/mikrotik/un1.log` (conf: `/etc/rsyslog.d/20-mikrotik-files.conf`) | effective: **N/D**
5. `logrotate` → `/etc/logrotate.d/mikrotik-un1` (`daily rotate 30 compress delaycompress create 0640 syslog adm postrotate HUP`) | effective: **N/D**
6. `SQLite DB` → `/var/lib/noc/noc.db` (WAL) | effective: **N/D**
7. `tailer state/offset` → `/var/lib/noc/tailer.state.json` | effective: **N/D**
8. `schema campo do check` → `check_name` | effective: **N/D**
9. `/where` → `BOT_VERSION|build` + `SOURCE=DB/LOG` + freshness + paths | effective (journal): `version=2026-02-28-dm-group-ux|build=2026-02-28_094935`
10. `release/deploy` → tooling: `/usr/local/sbin/noc-release` + cofre `/var/lib/noc/releases` (`SHA256SUMS` OK, `LAST_RELEASE.zip` OK) + backup `/opt/telegram-bot.bak_2026-02-28_114719`


---

## 3) Evidências e governança

### 3.1 logrotate do un1.log
- `/etc/logrotate.d/mikrotik-un1`
- Política: `daily`, `rotate 30`, `compress`, `delaycompress`, `create 0640 syslog adm`
- `postrotate`: `systemctl kill -s HUP rsyslog.service`

### 3.2 SecOps / hardening aplicado
- Redaction global do token nos logs
- Token rotacionado
- “Leak check” esperado: 0
- `.env`: manter apenas `TELEGRAM_BOT_TOKEN` (evitar duplicação/regressão)

### 3.3 Hardening pendente recomendado (RouterOS API-SSL 9005)
- API-SSL na porta **9005** (TLS) acessível via VPN
- Recomendação: allowlist em firewall e/ou `/ip service address=`

---

### 3.4 Snapshots “effective config” (cole aqui; redija segredos)
Objetivo: este canônico ser autocontido para auditoria/drift. Cole as saídas **reais** do ambiente (com token redigido).

**3.4.1 systemd (bot):**
- `systemctl cat telegram-bot` →

```ini
# /etc/systemd/system/telegram-bot.service
[Unit]
Description=Telegram AI Bot Worker (Hardened)
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=60
StartLimitBurst=8

[Service]
User=telegram-bot
Group=telegram-bot
WorkingDirectory=/opt/telegram-bot
EnvironmentFile=/opt/telegram-bot/.env
Environment=PYTHONUNBUFFERED=1
Environment=APP_DIR=/opt/telegram-bot

ExecStart=/usr/bin/python3 /opt/telegram-bot/bot.py

Restart=on-failure
RestartSec=5
TimeoutStopSec=20
KillSignal=SIGTERM

LimitNOFILE=65536
TasksMax=200
MemoryMax=512M
UMask=007

NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
MemoryDenyWriteExecute=true
LockPersonality=true
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
ReadWritePaths=/opt/telegram-bot

[Install]
WantedBy=multi-user.target

# /etc/systemd/system/telegram-bot.service.d/10-execstart.conf
[Service]
ExecStart=
ExecStart=/home/telegram-bot/venv/bin/python /opt/telegram-bot/bot.py

# /etc/systemd/system/telegram-bot.service.d/20-protecthome.conf
[Service]
ProtectHome=false

# /etc/systemd/system/telegram-bot.service.d/30-envfile.conf
[Service]
EnvironmentFile=/opt/telegram-bot/.env

# /etc/systemd/system/telegram-bot.service.d/40-startlimit.conf
[Unit]
StartLimitIntervalSec=0

[Service]
Restart=always
RestartSec=3

```

- `systemctl show telegram-bot -p User,WorkingDirectory,ExecStart,EnvironmentFiles` → **N/D**

**3.4.2 systemd (tailer):**
- `systemctl cat noc-sqlite-tailer` → **N/D**
- `systemctl show noc-sqlite-tailer -p ExecStart,WorkingDirectory` → **N/D**

**3.4.3 rsyslog:**
- `/etc/rsyslog.d/10-mikrotik.conf` (imudp + bind) → **N/D**
- `/etc/rsyslog.d/20-mikrotik-files.conf` (filtro+arquivo) → **N/D**
- `ss -lunp | grep :514` → **N/D**

**3.4.4 DB/schema:**
- `sqlite3 /var/lib/noc/noc.db '.schema'` (provar `check_name`) → **N/D**
- `ls -lah /var/lib/noc/noc.db*` (provar WAL) → **N/D**

**3.4.5 /where (1 exemplo real):**
- saída do `/where` (com token redigido) → Exemplo real (2026-02-27, token redigido):
```
BOT_VERSION=2026-02-26-dm-group-ux|build=2026-02-26_031500
build=2026-02-26_031500
BUILD_ID=2026-02-26_031500
HOST=ubt
UNIT=UN1
SOURCE=DB (ok)
DB=/var/lib/noc/noc.db
LOG=/var/log/mikrotik/un1.log
last_db_ts=2026-02-27 01:54:58-0300
last_log_ts=2026-02-27 01:54:58-0300
freshness_s=779
```

**3.4.6 Release/artefatos (produção):**
- ZIP release (limpo): `/tmp/noc_bot_release_2026-02-27_022037.zip`
- ZIP padrão (deploy): `/tmp/noc_bot_patched.zip`
- SHA256 (ambos): `687c747f6f9115a7faf164aea04fe9b1dc88fd5a08085267fec9da3c78151576`
- Prova hotfix no ZIP: `noc_bot/sources.py` contém `raw_col = _detect_raw_col()` em `get_last_n_events` (linha ~201 no snippet validado via `unzip -p`).
- Prova runtime: contador `journalctl -u telegram-bot --since "5 min ago" | grep -c "NameError: name 'raw_col'"` = `0`.


---

## 4) Catálogo de checks (UN1) e severidade (produção)

### 4.1 Checks
- **MUNDIVOX (WAN1)**: target `189.91.71.217` | src-address `189.91.71.218`
- **VALENET (WAN2)**: target `187.1.49.121` | src-address `187.1.49.122`
- **ESCALLO**: `187.33.28.57`
- **Telefonia (VOIP)**: `138.99.240.49`

### 4.2 Severidade
- **SEV1:** MUNDIVOX DOWN (com/sem VALENET)
- **SEV3:** VALENET DOWN com MUNDIVOX UP
- **SEV2:** serviços (ESCALLO/VOIP) DOWN com WANs UP

---

## 5) UX “produto” (DM) — contrato atual (inclui últimas mudanças)

### 5.1 Objetivo do DM
Resposta curta, visual e consistente para supervisora/cliente (sem ruído), com botões e evidência sob demanda.

### 5.2 Tela principal (DM) — padrão
Título e status (🟢/🟠/🔴) + bloco Internet + serviços + Impacto + botões.

#### Linha “Internet” (reduz ruído e mantém semântica)
A linha pai virou texto de estado:

- Operante: `🌐 Internet — Online`
- 1 link caiu: `🌐 Internet — Backup ativo`
- 2 links caíram: `🌐 Internet — Indisponível`
- Qualidade ruim: `🌐 Internet — Instável`

**Regra de topo (head):**
- 🔴 se (inet_down OR tel_down OR esc_down)
- 🟠 se (qualidade ruim OR **one_link_down**)
- 🟢 caso contrário

**Espaçamento (respiração visual):**
- 1 linha em branco após `🌐 Internet — <modo>` antes dos links.

#### Ícones por operadora (sempre)
- `↳ Link 1 — Mundivox ✅/🔴`
- `↳ Link 2 — Valenet ✅/🔴`

#### “Agora” vs “Hoje” (evita contradição)
Quando um item estiver **DOWN agora**, a linha vira **duas linhas**:

- `Agora: FORA 🔴`
- `Hoje: xx,x% up | yy,y% qualidade — Termo`

Quando estiver UP, mantém:
- `Hoje: xx,x% up | yy,y% qualidade — Termo`

**Notas técnicas:**
- `q_part()` foi endurecido para **nunca** imprimir `None` (usa `N/D`).
- Qualidade de Internet ainda é **geral** (um `INTERNET QUALITY`). Em contingência, “qualidade excelente” pode aparecer mesmo com uma operadora fora, pois a operação segue via outro link. Evolução recomendada: QUALITY por operadora (L1/L2).

#### Impacto (marketing + operacional)
- Normal: `Impacto: operação normal.`
- 1 link caiu: `Impacto: operação com redundância ativa.`
- 2 links caíram: `Impacto: operação com indisponibilidade de Internet.`
- Qualidade ruim: `Impacto: operação com instabilidade.`

### 5.3 Botões (DM)
Teclado DM padrão (rodapé):
- Atendimento (2h)
- Painel (Tempo real)
- Disponibilidade Hoje
- Qualidade Hoje
- Resumo 24h
- Semana
- Evidências
- Fonte (/where)

**Callback_data relevantes (contrato):**
- `sup:now`, `sup:24h`, `sup:7d`
- `dm:avail_today`, `dm:qual_today`
- `evm`, `evp:<svc>`, `evd:<svc>:<win>`, `evr:<svc>:<win>`, `evt:<svc>:<win>`
- `where`, `att:2h`

---



### 5.4 Home DM multi-unidades (Clínica) — baseline (v1)

**Objetivo:** ao abrir a DM (ou enviar “oi”), o usuário vê **um único painel executivo** com o status **AGORA** (✅/⚠️/🔴/—) por unidade, e só aprofunda ao selecionar a unidade.

**Entrada padrão:**
- `/start` (DM) → Home Clínica
- Texto livre no DM (não-comando) → Home Clínica

**Conteúdo Home (somente “Agora”):**
- **UN1 — Eldorado:**
  - `🌐 Internet — Online | Backup ativo | Indisponível | Instável`
  - `↳ Link 1 — Mundivox ✅/⚠️/🔴/—`
  - `↳ Link 2 — Valenet ✅/⚠️/🔴/—`
  - `📞 Telefonia ✅/⚠️/🔴/—`
  - `☁️ Escallo ✅/⚠️/🔴/—`
- **UN2 — Barreiro:**
  - `🌐🔒 VPN — Conectada ✅ | Instável ⚠️ | FORA 🔴 | N/D —`
- **UN3 — Alípio de Mello:**
  - `🌐🔒 VPN — Conectada ✅ | Instável ⚠️ | FORA 🔴 | N/D —`

**Regra de Instável (Home / VPN):**
- `⚠️` quando `flaps_2h >= 2` (≥2 oscilações em 2h)
- `🔴` quando state=DOWN
- `✅` quando state=UP e flaps_2h < 2
- `—` quando N/D

**Incidente/Ocorrência (banner no topo):**
- Prioridade: VPN_UN2 DOWN → VPN_UN3 DOWN → Internet UN1 indisponível → Telefonia/Escallo DOWN → Ocorrências (2h)

**Navegação (botões):**
- Home: `UN1 — Eldorado` | `UN2 — Barreiro` | `UN3 — Alípio de Mello` | `Fonte`
- Detalhe UN2/UN3: `⬅️ Clínica (início)` | `Fonte`
- Detalhe UN1: mantém teclado DM padrão + `⬅️ Clínica (início)`

**Callback_data (contrato):**
- `home` → volta Home Clínica
- `unit:UN1` / `unit:UN2` / `unit:UN3` → abre detalhe da unidade

**Anti-spam (DM produto):**
- Em callbacks, preferir **edit_message_text**.
- Se Telegram retornar `Message is not modified`, não enviar nova mensagem.

### 5.5 DM consultiva — FIX6 (2026-03-15)

Regras funcionais validadas em runtime real:
- serviço explicitamente citado na mensagem atual tem prioridade sobre contexto anterior
- mensagens de confirmação curta, como "tem certeza?", reutilizam o último contexto útil
- "status atual" é sempre tratado como status geral
- perguntas fora de escopo não acionam painel/home
- probes curtos por serviço, como "Escallo" e "Telefone", resolvem como status factual do serviço

Referências:
- PR #8 (merged)
- Merge commit: `cbce6ee`
- Commit FIX6: `c610a2a`
- Tag: `v2026.03.15-fix6-dm-consultiva`
## 6) UX “técnico” (Grupo NOC)
- Anti-ruído: responde por **@menção** ou **reply**.
- Botões técnicos: Status / Analyze / Timeline / Evidências / Fonte.
- Mesma fonte de números (DB/LOG), IA opcional só para texto.

---

## 7) Evidências (prova) — contrato de entrega
Trigger aceito (texto natural): `evidência`, `evidencias`, `prova`, `provas`.

**Regra de segurança:** exigir o serviço (evita prova errada).  
Exemplos: `evidência telefonia`, `evidência escallo`, `evidência link 1`, `evidência link 2`.

Entrega em 3 mensagens (padrão):
1) Painel/Contexto
2) Evidência compacta + botões
3) Texto pronto para operadora com **5 CIDs** mais recentes (+ nota “há mais”)

---

## 8) Comandos operacionais do bot (principais)
- `/where` → exibe `BOT_VERSION|build`, `SOURCE=DB/LOG`, freshness e paths
- `/status` → estado atual por serviço
- `/timeline N` → últimos N eventos
- `/analyze 24h|7d|30d` → resumo interpretado (sem inventar números)
- Atendimento (2h) via botão ou gatilho por texto (reclamação)

---

## 9) Deploy seguro (padrão oficial)

### 9.1 Conceito
O deploy é **ZIP → unzip stage → rsync espelho**.  
Para não apagar entrypoint nem env/venv: atualizar **somente** `/opt/telegram-bot/noc_bot/`.

### 9.2 Deploy seguro (somente `noc_bot/`)
**Pré:** ZIP em `/tmp/noc_bot_patched.zip`

```bash
sudo bash -lc '
set -euo pipefail
ZIP="/tmp/noc_bot_patched.zip"
APP="/opt/telegram-bot"
SVC="telegram-bot.service"
TS="$(date +%F_%H%M%S)"
BAK="/opt/telegram-bot.bak_${TS}"
STAGE="/tmp/noc_patch_${TS}"

command -v unzip >/dev/null
command -v rsync >/dev/null

USR="$(systemctl show -p User --value "$SVC" || true)"
[[ -n "$USR" ]] || USR="telegram-bot"

systemctl stop "$SVC"

mkdir -p "$BAK"
cp -a "$APP/bot.py" "$BAK/" 2>/dev/null || true
rsync -a --delete "$APP/noc_bot/" "$BAK/noc_bot/"

rm -rf "$STAGE"; mkdir -p "$STAGE"
unzip -q "$ZIP" -d "$STAGE"
rsync -a --delete "$STAGE/noc_bot/" "$APP/noc_bot/"
chown -R "$USR":"$USR" "$APP/noc_bot"

# sanity compile
PYTHONDONTWRITEBYTECODE=1 /home/telegram-bot/venv/bin/python -B -m py_compile   "$APP/noc_bot/ui/panels.py"   "$APP/noc_bot/ui/keyboards.py"   "$APP/noc_bot/handlers/callbacks.py"   "$APP/noc_bot/handlers/commands.py"

systemctl start "$SVC"

# sanity logs
journalctl -u "$SVC" --since "15 min ago" --no-pager -o cat  | egrep -i "Traceback|IndentationError|SyntaxError|ModuleNotFoundError|ImportError|can\x27t parse entities|CRITICAL"  || echo "OK: sem erros fatais"
'
```

### 9.3 Rollback
```bash
sudo bash -lc '
set -euo pipefail
APP="/opt/telegram-bot"
SVC="telegram-bot.service"
BAK="$(ls -1dt /opt/telegram-bot.bak_* 2>/dev/null | head -n 1)"
[[ -n "$BAK" ]] || { echo "FATAL: não achei backup"; exit 2; }

systemctl stop "$SVC"
rsync -a --delete "$BAK/noc_bot/" "$APP/noc_bot/"
cp -a "$BAK/bot.py" "$APP/bot.py" 2>/dev/null || true
systemctl start "$SVC"
systemctl --no-pager --full status "$SVC" | sed -n "1,14p"
'
```

**Nota crítica:** hotfix feito direto no servidor deve virar “release ZIP” ou será sobrescrito por ZIP antigo.

---


### 9.4 Release/Deploy padronizado (produção): `noc-release`

Para reduzir passos manuais e manter rastreabilidade, o deploy em produção pode (e deve) ser feito pelo wrapper:

- Script: `/usr/local/sbin/noc-release`
- Release (gera artefatos em `/tmp`): `sudo noc-release`
- Deploy seguro (stop→backup→unzip stage→rsync noc_bot/→start→sanity): `sudo noc-release --deploy`

Contratos do tooling (produção):
- Gera:
  - `/tmp/noc_bot_release_YYYY-MM-DD_HHMMSS.zip`
  - `/tmp/noc_bot_patched.zip` (cópia padrão para deploy)
- Backup do deploy:
  - `/opt/telegram-bot.bak_YYYY-MM-DD_HHMMSS/`
- Sanity gate pós-deploy (ajuste 2026-02-28):
  - `py_compile` sem bytecode (evita `__pycache__` owned por root)
  - Gate do journal só para erros fatais (NÃO usar `400 Bad Request` como critério de rollback)

### 9.5 Cofre persistente de releases (produção)

> `/tmp` é volátil. Para auditoria e rollback, manter cofre persistente.

- Diretório: `/var/lib/noc/releases` (owner `telegram-bot`, mode `0750`)
- Ponteiro do último release aplicado:
  - `/var/lib/noc/releases/LAST_RELEASE.zip`
- Integridade:
  - `/var/lib/noc/releases/SHA256SUMS` (verificação: `sha256sum -c SHA256SUMS` rodando como `telegram-bot`)
- Governança:
  - `/var/lib/noc/releases/CHANGELOG_RELEASES.log` (1 entrada por deploy aplicado)

**Último deploy aplicado (2026-02-28 11:47 BRT):**
- `LAST_RELEASE.zip` → `noc_bot_release_2026-02-28_114719.zip`
- `SHA256 (artefato aplicado)`:
  - `e089a920c196f1b04e2cd677d73a034c54d50f0c4aae0b89d1f9a192ff582129`
- Backup:
  - `/opt/telegram-bot.bak_2026-02-28_114719`
- Prova forense (runtime == release):
  - `sha256(commands.py)=595b9fca19cf168682703d273e37e7e50aa996b1304d48be6bf232db14d08c36` (filesystem == zip)

---

## 10) Troubleshooting rápido (produção)

### 10.1 Bot reiniciando em loop
- Verificar `ExecStart` e se existe `bot.py` no path esperado.
- `journalctl -u telegram-bot -o cat -n 80`

### 10.2 “DB stale”
- Verificar `noc-sqlite-tailer.service`
- Verificar escrita em `/var/lib/noc/noc.db`
- Bot em AUTO deve cair para LOG quando necessário.

### 10.3 Formatação quebrada / “None”
- `py_compile` no arquivo alterado
- Helpers:
  - `q_part()` deve retornar string sempre (`N/D` quando faltar dado)
  - `today_line()` deve formatar DOWN com duas linhas (`Agora` + `Hoje`)

---

## 11) Changelog (últimas mudanças relevantes)

- 2026-02-28 — Release/Deploy: `noc-release` (produção) padroniza release ZIP + deploy seguro com rollback e sanity gate (ignora `400 Bad Request`; falha só em erro fatal).
- 2026-02-28 — Cofre persistente: `/var/lib/noc/releases` com `SHA256SUMS`, `CHANGELOG_RELEASES.log` e symlink `LAST_RELEASE.zip`.
- 2026-02-28 — Evidência: integridade verificada (hash de arquivo em produção bate com arquivo dentro de `LAST_RELEASE.zip`).

- 2026-02-26 — DM: linha pai Internet virou modo texto (`Online/Backup ativo/Indisponível/Instável`), reduzindo ruído visual.  
- 2026-02-26 — DM: adicionada linha em branco após cabeçalho Internet (melhor legibilidade).  
- 2026-02-26 — DM: quando DOWN agora, adiciona `Agora: FORA 🔴` e separa em duas linhas (evita contradição com % do dia).  
- 2026-02-26 — Impacto: linguagem comercial `operação com redundância ativa` em contingência.  
- 2026-02-26 — Deploy: padrão oficial passou a atualizar **somente** `noc_bot/` (preserva `bot.py/.env/venv`).  
- 2026-02-26 — Correção: `q_part()` não imprime `None` (usa `N/D`).

- 2026-02-27 — DM (padronização): `cmd_evidence_request` passou a usar **somente** `build_evidence_compact` (`noc_bot.evidence.builder`) + `evidence_kb`; `cmd_supervisor_summary` passou a usar `build_dm_panel_un1_v2` (`noc_bot.ui.panels`) + última ocorrência + próxima ação; removidos shims/try/except e defs locais em `handlers/commands.py`.
- 2026-02-27 — Deploy: aplicado patch via ZIP limpo (sem `.bak/.orig/.pyc/__pycache__`) no fluxo oficial “atualiza somente `noc_bot/`”.
- 2026-02-27 — HOTFIX (DB-first): corrigido `NameError: raw_col is not defined` em `sources.py` (`get_last_n_events` e `get_prefetch_before`) adicionando `raw_col = _detect_raw_col()` após `check_col = _detect_check_col()`. Evidência: contador `journalctl | grep -c "NameError: name 'raw_col'"` = `0` após restart.
- 2026-02-27 — Release oficial (limpo): gerado `/tmp/noc_bot_release_2026-02-27_022037.zip` (cópia padrão `/tmp/noc_bot_patched.zip`) com SHA256 `687c747f6f9115a7faf164aea04fe9b1dc88fd5a08085267fec9da3c78151576`.
- 2026-02-27 — Validação DM (operacional): `sup:now`, `evidência link 1` (compacta), `evidência completa` (organizada/operadora), `texto pronto (operadora)` (até 5 CIDs mais recentes, ou menos se não existirem 5 na janela), `sup:24h` (painel v2 + última ocorrência + próxima ação) — OK.

---

## 12) Próximos passos recomendados (NOC)
1) Anti-flap na fonte (RouterOS Netwatch): debounce/cooldown  
2) Hardening API-SSL 9005 (allowlist)  
3) Qualidade por operadora (L1/L2) para remover “qualidade geral” em contingência  
4) Multi-unidade (UN2/UN3) reaproveitando contrato e core


## SNAPSHOTS — Effective Config (colado) — 2026-02-28 (BRT)

### 10.2 systemd (noc-sqlite-tailer) — systemctl cat noc-sqlite-tailer

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
# hardening básico
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

# systemd cria e garante owner/perms (para DB + state)
StateDirectory=noc
StateDirectoryMode=0750

Environment=LOG_PATH=/var/log/mikrotik/un1.log
Environment=DB_PATH=/var/lib/noc/noc.db
Environment=STATE_PATH=/var/lib/noc/tailer.state.json

# blindagem contra baixo volume (definitivo)
Environment=FLUSH_EVERY_SECONDS=5
Environment=STATE_SAVE_EVERY_SECONDS=5
Environment=SLEEP_IDLE=0.5

# bootstrap/backfill
Environment=BOOTSTRAP_LINES=20000
Environment=BACKFILL_ENABLE=1
Environment=BACKFILL_MAX_BYTES=209715200
Environment=BACKFILL_LINES=50000
```

### 10.3 rsyslog — bind UDP/514 (/etc/rsyslog.d/10-mikrotik.conf)

```conf
module(load="imudp")
input(type="imudp" address="192.168.10.20" port="514")
```

### 10.3 rsyslog — filtro + raw log (/etc/rsyslog.d/20-mikrotik-files.conf)

```conf
if ($fromhost-ip == "192.168.20.1") then {
  action(type="omfile" file="/var/log/mikrotik/un1.log")
  stop
}
```

### 10.3 logrotate (/etc/logrotate.d/mikrotik-un1)

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

### 10.3 prova do socket UDP/514 (ss -lunp | grep :514)

```text
UNCONN 0      0                         192.168.10.20:514        0.0.0.0:*    users:(("rsyslogd",pid=865,fd=6))        
```

### 10.4 SQLite schema (sqlite3 /var/lib/noc/noc.db .schema)

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

### 10.4 prova WAL (ls -lah /var/lib/noc/noc.db*)

```text
-rw-r----- 1 telegram-bot telegram-bot 44K Feb 28 13:19 /var/lib/noc/noc.db
-rw-r----- 1 telegram-bot telegram-bot 32K Feb 28 15:09 /var/lib/noc/noc.db-shm
-rw-r----- 1 telegram-bot telegram-bot 69K Feb 28 15:02 /var/lib/noc/noc.db-wal
```

