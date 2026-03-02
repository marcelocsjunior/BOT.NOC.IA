# Security — BOT ia NOC (UN1)

Este documento define práticas e controles de segurança do projeto **BOT ia NOC (UN1)**, com foco em: **segredos**, **logs**, **integridade de releases** e **hardening operacional**.

> Princípio: o repositório é **código + infra AS-RUNNING versionada**. O runtime (Collector) mantém segredos e dados fora do Git.

---

## 1) Escopo e premissas

### O que este repositório contém
- Código do bot: `bot.py`, `noc_bot/`
- Infra AS-RUNNING versionada: `infra/etc/` (systemd/rsyslog/logrotate)
- Documentação e runbooks: `docs/`
- Hashes/snapshots: `release/` + GitHub Releases (assets `.tar.gz` + `.sha256`)

### O que NÃO deve estar no repositório
- `.env` (segredos)
- `venv/` / `.venv/`
- DB e state: `/var/lib/noc/*` (ex.: `noc.db`, `tailer.state.json`)
- Logs: `/var/log/mikrotik/*` (ex.: `un1.log`)

---

## 2) Gestão de segredos (Secrets)

### Regra de ouro
- **Nunca** commitar tokens, chaves, senhas ou endpoints sensíveis.
- O arquivo `.env` existe **somente no runtime** (Collector).

### Variáveis permitidas / padrão
- Manter **apenas** `TELEGRAM_BOT_TOKEN` no `.env` (reduz risco de regressão por duplicidade).
- `BOT_VERSION` e `BUILD_ID` devem refletir o build em execução (rastreabilidade).

### Modelo
- Use `.env.example` como base (placeholders).  
  **Placeholders não são segredos**.

---

## 3) Logs, redaction e vazamento de token

### Objetivo
Impedir que tokens e credenciais apareçam em logs, prints, tracebacks ou evidências.

### Controles esperados (baseline)
- Redaction de token aplicada nos logs (ex.: mascaramento de `TELEGRAM_BOT_TOKEN`/strings de bot).
- Token rotacionado quando necessário.
- “Leak check” esperado: **0** (nenhum segredo em repo/logs).

### Política
- Logs devem registrar **metadados e estado**, não segredos.
- Ao compartilhar logs/evidências: redigir qualquer token/Authorization/cookie.

---

## 4) Integridade de releases (AS-RUNNING snapshot)

### Por que existe
Releases são usados como **prova de estado em execução** (AS-RUNNING) e para rollback/forense.

### Regras
- Todo snapshot relevante deve ter:
  - asset `.tar.gz`
  - asset `.sha256`
- O `.sha256` valida integridade (anti-corrupção / anti-download incompleto).
- Tags devem ser “Git-friendly” e rastreáveis por `BUILD_ID`.

---

## 5) Hardening operacional (Collector)

### Componentes críticos
- `rsyslog.service` (ingestão UDP/514 + filtro)
- `noc-sqlite-tailer.service` (raw → SQLite)
- `telegram-bot.service` (bot em modo AUTO DB-first + fallback LOG)

### Recomendações
- Minimizar superfície: serviços somente no necessário, sem portas desnecessárias expostas.
- Restringir origens/ACLs (especialmente para API-SSL 9005, se habilitada).
- Manter o runtime segregado do repo (deploy controlado).

---

## 6) Dependências e cadeia de suprimentos

### Política
- Evitar dependências não necessárias.
- Preferir versões fixadas quando aplicável.
- Revisar mudanças antes de deploy em produção.

### GitHub (recomendado)
- Ativar alertas de vulnerabilidade (Dependabot / Security alerts) quando disponível.
- Manter o repo privado enquanto a maturidade do pipeline evolui.

---

## 7) Processo de reporte de vulnerabilidade

Se você identificar vulnerabilidade (token exposto, bypass de auth, injeção, etc.):

1) **Não** abra Issue pública com detalhes sensíveis.
2) Rotacione tokens afetados e trate como incidente.
3) Registre a correção via commit + tag/release e documente o impacto no ChangeLog.

---

## 8) Regras de contribuição (guardrails)

Antes de qualquer commit:
- Garantir que `.gitignore` bloqueia `.env`, `venv/`, `*.db`, `*.log`, `tailer.state.json`.
- Não incluir dumps de DB/logs no repo.
- Documentar mudanças operacionais (infra) em `infra/etc` para evitar drift.

---

## 9) Status atual (baseline)

- Tokens e segredos não versionados.
- Infra AS-RUNNING versionada para auditoria.
- Releases com artefato + checksum para integridade.
- Objetivo de “leak check”: **0**.
