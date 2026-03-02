# Security Contact — BOT ia NOC (UN1)

Este arquivo define o canal padrão para reporte de vulnerabilidades e incidentes de segurança relacionados ao projeto **BOT ia NOC (UN1)**.

## 1) Canal oficial de reporte (preferencial)
- **Abrir uma Issue no repositório** com o prefixo: **`[SECURITY]`**
  - Ex.: `[SECURITY] Possível vazamento de token em log`
  - Regras:
    - **Nunca** cole tokens/segredos.
    - Use apenas **evidências redigidas** (sem `TELEGRAM_BOT_TOKEN`, sem headers `Authorization`, sem dumps de `.env`).

> Observação: como o repositório é **privado**, Issues funcionam bem como canal interno e auditável.

## 2) Prioridade e SLA interno (referência)
- **Crítico (P0)**: token exposto, bypass de auth, execução remota, vazamento de dados  
  Ação imediata: **conter + rotacionar token + revogar acessos**.
- **Alto (P1)**: exposição de informação sensível, falha de hardening que aumenta superfície
- **Médio (P2)**: falhas de configuração com mitigação simples, risco limitado
- **Baixo (P3)**: melhorias e hardening recomendado

## 3) Informações mínimas no reporte (sem segredos)
Inclua:
- Data/hora (BRT)
- Ambiente: **Collector UN1**
- Versão: `BOT_VERSION` e `BUILD_ID` (via `/where`)
- Fonte: `SOURCE=DB/LOG`
- Passos para reproduzir (se aplicável)
- Evidência redigida (logs/prints sem segredos)
- Impacto e escopo estimado

## 4) Contenção rápida (checklist)
Se houver suspeita de vazamento de token/segredo:
1) Rotacionar `TELEGRAM_BOT_TOKEN`
2) Validar redaction nos logs
3) Rodar “leak check” (buscar padrões de token em logs/artefatos)
4) Registrar correção via commit + tag/release
5) Atualizar `SECURITY.md`/ChangeLog se necessário
