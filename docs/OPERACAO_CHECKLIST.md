# Operação — Checklist (BOT ia NOC UN1)

Checklist “sem frescura” para manter o UN1 auditável: rotina diária, pré-mudança, pós-mudança e resposta rápida a incidente.

---

## 1) Checklist diário (NOC) — 2 a 5 minutos

### 1.1 Bot e pipeline (saúde)
- [ ] `telegram-bot.service` **active (running)** (sem restart loop)
- [ ] `noc-sqlite-tailer.service` **active (running)**
- [ ] `rsyslog.service` **active (running)**
- [ ] `/where` retorna:
  - [ ] `BOT_VERSION|build` coerentes
  - [ ] `SOURCE=DB` (quando saudável) / `SOURCE=LOG` apenas em fallback
  - [ ] freshness e paths coerentes

### 1.2 Ingestão e persistência (sanidade)
- [ ] Raw log chegando: `/var/log/mikrotik/un1.log` tem eventos recentes `NOC|unit=UN1|...`
- [ ] DB em WAL:
  - [ ] `PRAGMA journal_mode` = `wal`
- [ ] Schema ok:
  - [ ] existe `check_name`

### 1.3 Ruído / UX (higiene)
- [ ] Grupo NOC: bot responde só por **@menção** ou **reply**
- [ ] DM: painel “produto” ok (resposta curta C2)
- [ ] Evidência: trigger e fluxo de 3 mensagens ok (painel → evidência → texto pronto com 5 CIDs)

---

## 2) Pré-mudança (Change Control) — 5 a 10 minutos

### 2.1 Gate (antes de tocar em produção)
- [ ] Não há SEV ativo (ou mudança aprovada como parte do incidente)
- [ ] Snapshot/Release “antes” existe (artefato `.tar.gz` + `.sha256`)
- [ ] Escopo definido:
  - [ ] **Código** (noc_bot/, bot.py) ou
  - [ ] **Infra** (systemd/rsyslog/logrotate) ou
  - [ ] ambos (explicitamente)
- [ ] Rollback definido (tag/release anterior conhecido)

### 2.2 Segurança
- [ ] `.env` **não** será versionado (nunca)
- [ ] Não há tokens/segredos nos commits
- [ ] `.gitignore` protege runtime (DB/log/state/venv)

---

## 3) Pós-mudança (DoD) — 3 a 8 minutos

### 3.1 Serviços
- [ ] `telegram-bot.service` ativo e estável (sem StartLimit)
- [ ] (se tocou no tailer) `noc-sqlite-tailer.service` ativo
- [ ] (se tocou no rsyslog) `rsyslog.service` ativo

### 3.2 Validação funcional
- [ ] `/where` mostra `BOT_VERSION|build` esperado (novo build)
- [ ] `/where` mostra `SOURCE=DB` quando DB saudável
- [ ] `/status` e `/timeline` coerentes com eventos recentes
- [ ] Evidência “prova” funciona e gera texto pronto com 5 CIDs

### 3.3 Anti-drift
- [ ] Mudança virou commit
- [ ] Mudança virou tag/release (se impacta produção)
- [ ] Se infra mudou, atualizar `infra/etc` no repo

---

## 4) Incidente (resposta rápida) — 2 minutos para enquadrar

### 4.1 Classificação (UN1)
- [ ] SEV1: `MUNDIVOX` DOWN (com/sem `VALENET`)
- [ ] SEV3: `VALENET` DOWN com `MUNDIVOX` UP
- [ ] SEV2: `ESCALLO`/`VOIP` DOWN com WANs UP

### 4.2 Triagem mínima
- [ ] `/where` (BOT_VERSION|build + SOURCE DB/LOG + freshness)
- [ ] `/timeline` (correlacionar por `cid`)
- [ ] Confirmar se é blip / flap / DOWN sustentado

### 4.3 Comunicação e evidência
- [ ] Diretoria (C2): status + impacto + ação + próxima atualização
- [ ] Operadora: acionar **evidência** do serviço correto:
  - [ ] link1 (Mundivox)
  - [ ] link2 (Valenet)
  - [ ] telefonia (VOIP)
  - [ ] escallo
- [ ] Texto pronto: incluir 5 CIDs mais recentes + “há mais”

---

## 5) Rollback (mudança induzida) — 5 minutos

- [ ] Identificar a mudança que antecedeu o incidente (commit/tag)
- [ ] Voltar para release/tag anterior
- [ ] Reiniciar `telegram-bot.service`
- [ ] Validar `/where` + health check diário (seção 1)
- [ ] Registrar causa/impacto/decisão no ChangeLog

---

## 6) Rotina semanal (manutenção leve) — 10 a 20 minutos

- [ ] Verificar retenção do raw log (logrotate ok; sem erro)
- [ ] Verificar crescimento/saúde do DB (sem corrupção; WAL ok)
- [ ] Revisar ruído e UX (DM/grupo) e ajustar se necessário
- [ ] Revisar hardening pendente (API-SSL 9005 allowlist)
- [ ] Validar “leak check” (sem tokens em logs/repo)

---
