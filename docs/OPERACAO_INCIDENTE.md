Sim — **`docs/OPERACAO_INCIDENTE.md`** é o próximo passo perfeito. Aqui vai o conteúdo **completo**, pronto pra você copiar e colar no GitHub (Create new file → `docs/OPERACAO_INCIDENTE.md` → Commit).

```markdown
# Operação de Incidente — BOT ia NOC (UN1)

Runbook para conduzir incidente do UN1 com padrão “NOC auditável”: triagem, severidade, timeline, evidência e comunicação (diretoria + operadora), com rollback e anti-drift.

---

## 1) Objetivo (padrão de resposta)

- Definir severidade (SEV) rapidamente
- Reduzir ruído e manter rastreabilidade
- Produzir evidência (“prova”) + texto pronto para operadora quando necessário
- Fechar com registro mínimo: causa provável / impacto / ações / próximo passo

---

## 2) Severidade (UN1) — regra canônica

Matriz:
- **SEV1**: `MUNDIVOX` **DOWN** (com/sem `VALENET`)
- **SEV3**: `VALENET` **DOWN** com `MUNDIVOX` **UP**
- **SEV2**: serviços (`ESCALLO` / `VOIP`) **DOWN** com WANs **UP**

Catálogo (produção):
- MUNDIVOX (WAN1): target `189.91.71.217` | src `189.91.71.218`
- VALENET (WAN2): target `187.1.49.121` | src `187.1.49.122`
- ESCALLO: `187.33.28.57`
- VOIP: `138.99.240.49`

---

## 3) Triagem (2–5 min)

### 3.1 Fonte de verdade (o que manda)
- O bot é front-end. O pipeline manda:
  **RouterOS → syslog → rsyslog(raw) → SQLite(WAL) → Bot(AUTO DB-first + fallback LOG)**

### 3.2 Checagens mínimas (gate)
1) No bot: `/where`
   - Confirma `BOT_VERSION|build`
   - Verifica `SOURCE=DB/LOG` + freshness
2) Serviços:
   - `telegram-bot.service`
   - `noc-sqlite-tailer.service`
   - `rsyslog.service`
3) Linha do tempo:
   - `/timeline` (ou equivalente) para correlacionar pelo `cid`

### 3.3 Classificação rápida
- **DOWN real**: sequência consistente de `state=DOWN` para o mesmo `check` (não blip)
- **Blip**: evento isolado ou curto, sem persistência
- **Flap**: alternância UP/DOWN recorrente (padrão instável)

> Dica operacional: se estiver em período muito estável e o “stale” for por idade do último evento, pode dar falso positivo. Prefira correlacionar com raw log/DB e timeline.

---

## 4) Fluxo de execução por SEV

### 4.1 SEV1 (MUNDIVOX DOWN)
**Objetivo:** recuperar link primário / contingenciar no secundário / acionar operadora com prova.

Passos:
1) Confirmar estado via timeline e (se necessário) raw log/DB
2) Checar se `VALENET` está UP (redundância ativa)
3) Comunicação imediata (diretoria) — texto C2 (modelo abaixo)
4) Acionar **Evidência Link1/Mundivox** para operadora (modelo abaixo)
5) Monitorar até estabilizar e encerrar com resumo

### 4.2 SEV3 (VALENET DOWN com MUNDIVOX UP)
**Objetivo:** restaurar redundância (risco elevado, mas operação segue pelo primário).

Passos:
1) Confirmar DOWN de `VALENET`
2) Comunicação curta informando perda de redundância
3) (Se persistir) abrir evidência para operadora do link2

### 4.3 SEV2 (ESCALLO/VOIP DOWN com WANs UP)
**Objetivo:** isolar se é serviço externo x conectividade interna x rota/DNS.

Passos:
1) Confirmar WANs UP
2) Confirmar apenas serviço afetado (ESCALLO ou VOIP)
3) Comunicação direcionada (impacto no serviço)
4) Evidência do serviço (telefonia ou escallo) para operadora/fornecedor

---

## 5) Evidência (“prova”) — quando e como

Trigger aceito no bot:
- `evidência / evidencias / evidências / prova / provas`

Regra:
- sempre informar o **serviço** para evitar prova errada:
  - “evidência link1”
  - “evidência link2”
  - “evidência telefonia”
  - “evidência escallo”

Entrega padrão:
1) painel/seleção
2) evidência compacta + botões
3) texto pronto com **5 CIDs mais recentes** + nota “há mais”

---

## 6) Modelos de comunicação (copiar/colar)

### 6.1 Diretoria / Supervisão (C2 — curto e objetivo)
> Use em DM (supervisora/coordenadora). Ajuste apenas o status real.

**SEV1 — Link1 (Mundivox) DOWN**
```

Status UN1: Link1 (Mundivox) 🔴 | Link2 (Valenet) ✅ (redundância ativa)
Impacto: operação segue em contingência (backup). Risco elevado se Link2 oscilar.
Ação: evidência gerada e operadora acionada. Próxima atualização em 15 min ou na normalização.

```

**SEV3 — Link2 (Valenet) DOWN**
```

Status UN1: Link1 (Mundivox) ✅ | Link2 (Valenet) 🔴
Impacto: perda de redundância (operação segue no primário).
Ação: monitoramento + acionamento da operadora se persistir.

```

**SEV2 — Telefonia/ESCALLO DOWN (WANs UP)**
```

Status UN1: Links ✅ | Serviço 🔴
Impacto: indisponibilidade parcial (serviço específico).
Ação: evidência gerada e fornecedor acionado. Próxima atualização em 15 min ou na normalização.

```

### 6.2 Operadora (texto pronto — com evidência e CIDs)
> Cole o texto pronto gerado pelo bot (mensagem 3 das evidências).  
> Padrão esperado: incluir 5 CIDs mais recentes e indicar que há mais.

Template (quando precisar complementar):
```

Prezados, segue evidência de indisponibilidade/instabilidade detectada no UN1.
Período: <INÍCIO–FIM (se aplicável)>
Serviço: <MUNDIVOX/VALENET/VOIP/ESCALLO>
CIDs (últimos 5): <CID1>, <CID2>, <CID3>, <CID4>, <CID5> (há mais disponíveis)
Solicito verificação e retorno com diagnóstico e previsão de normalização.

```

### 6.3 Grupo NOC (técnico — sem ruído)
```

[UN1][SEVx] <CHECK> <UP/DOWN>. SOURCE=<DB/LOG>. Início: <ts>.
Ação: <monitor/acionado operadora/evidência gerada>. CIDs: <top 1-2>.

```

---

## 7) Encerramento (post-mortem mínimo)

Quando estabilizar:
1) Confirmar UP sustentado (sem flap) via timeline
2) Registrar:
   - início / fim
   - serviço afetado
   - impacto (redundância ativa? indisponibilidade total?)
   - ação tomada (evidência/operadora/rollback)
   - retorno da operadora (causa/ETA) — se houve
3) Atualizar ChangeLog/registro interno se a ação gerou mudança de infra/código

---

## 8) Rollback (quando o incidente for “mudança induzida”)

Se o incidente começou após alteração:
1) Voltar para release/tag anterior (rollback real)
2) Reiniciar `telegram-bot.service`
3) Validar `/where` (BOT_VERSION|build esperado) + health check
4) Registrar: causa, impacto, decisão

---

## 9) Anti-drift (padrão de governança)

- Mudança em produção = **commit + tag/release**
- Infra AS-RUNNING (`infra/etc`) deve acompanhar mudanças reais (systemd/rsyslog/logrotate)
- Evidências e snapshots devem existir antes de mudanças relevantes
```

Se quiser, o próximo arquivo depois desse é um **`docs/OPERACAO_CHECKLIST.md`** (1 página) com checklist “pré-mudança / pós-mudança / diária”, bem estilo NOC.
