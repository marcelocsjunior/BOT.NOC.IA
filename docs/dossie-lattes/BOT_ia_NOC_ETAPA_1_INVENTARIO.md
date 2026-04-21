# BOT ia NOC — Etapa 1 — Inventário de Projeto Técnico Pontuável

**Projeto:** DOSSIÊ DOCÊNCIA EPT / PRODUÇÃO TÉCNICA / LATTES  
**Arquivo:** `docs/dossie-lattes/BOT_ia_NOC_ETAPA_1_INVENTARIO.md`  
**Status:** versão inicial para dossiê profissional-acadêmico  
**Data de consolidação:** 2026-04-21  
**Autor técnico:** Marcelo  

---

## 1. Nome oficial do projeto

**BOT ia NOC — Solução autoral de monitoramento operacional para infraestrutura crítica de TI**

### Nome curto

**BOT ia NOC**

### Título técnico/acadêmico sugerido

**Desenvolvimento de solução aplicada de monitoramento operacional com MikroTik, Syslog, SQLite, Telegram Bot e Inteligência Artificial**

---

## 2. Classificação documental

| Campo | Registro recomendado |
|---|---|
| Natureza | Projeto técnico autoral aplicado |
| Área principal | Infraestrutura de TI, redes, monitoramento, automação, observabilidade e AIOps |
| Ambiente | Ambiente real corporativo/clínico privado |
| Período | Dezembro/2025 — em andamento |
| Situação | Em produção / evolução controlada |
| Autoria | Marcelo |
| Função exercida | Autor, arquiteto, desenvolvedor, implantador e responsável técnico pela evolução |
| Prioridade de formalização | Muito alta |
| Classificação no dossiê | Produção técnica + software/ferramenta técnica + projeto técnico aplicado + experiência profissional correlata |

---

## 3. Resumo executivo

O **BOT ia NOC** é um projeto técnico autoral aplicado em ambiente real corporativo/clínico privado, iniciado em dezembro de 2025, com objetivo de monitorar links e serviços críticos de infraestrutura de TI.

A solução integra equipamentos de rede MikroTik RouterOS 7, geração de eventos via Netwatch/scripts, ingestão centralizada por Syslog remoto, persistência estruturada em SQLite, automação em Python, execução controlada por systemd e interface operacional por Telegram Bot. O projeto também prevê camada opcional de inteligência artificial para interpretação textual e apoio à análise, sem substituir as fontes determinísticas de verdade operacional.

O foco do projeto é reduzir verificações manuais, acelerar a identificação de falhas, registrar histórico rastreável de incidentes, apoiar decisões técnicas e criar uma base operacional auditável para links e serviços essenciais.

---

## 4. Problema técnico enfrentado

Antes da solução, o acompanhamento de links e serviços críticos dependia de verificações pontuais, alertas isolados e interpretação manual de eventos operacionais. Esse modelo reduzia a rastreabilidade, dificultava a criação de histórico e aumentava o tempo de análise durante incidentes.

O problema central era criar um fluxo confiável para:

- capturar eventos de disponibilidade;
- registrar histórico consultável;
- separar evento real de ruído operacional;
- consultar status e timeline rapidamente;
- apoiar comunicação técnica e executiva;
- preservar governança e evidência operacional.

---

## 5. Escopo técnico

| Frente | Descrição |
|---|---|
| Monitoramento de links | Acompanhamento de links WAN e disponibilidade de conectividade |
| Monitoramento de serviços | Acompanhamento de serviços críticos como telefonia e serviços externos/cloud |
| Evento padronizado | Contrato textual parseável para eventos operacionais |
| Ingestão | Coleta por Syslog remoto em servidor Linux |
| Persistência | Gravação estruturada em SQLite |
| Interface operacional | Bot Telegram com comandos e respostas assistivas |
| Histórico | Consulta de timeline, status, análise e fonte operacional |
| Severidade | Classificação de impacto por matriz de severidade |
| IA opcional | Apoio à interpretação textual, sem alterar fatos operacionais |
| Expansão | Arquitetura preparada para múltiplas unidades |

---

## 6. Arquitetura resumida

```text
MikroTik RouterOS 7
   │
   ├── Netwatch / scripts
   │
   ├── Evento NOC|...
   │
   ▼
Syslog remoto
   │
   ▼
Collector Ubuntu / VM bot
   │
   ├── rsyslog
   ├── log bruto operacional
   ├── tailer estruturado
   └── SQLite
        │
        ▼
Telegram Bot
   │
   ├── /status
   ├── /timeline
   ├── /where
   └── /analyze
```

---

## 7. Tecnologias utilizadas

| Categoria | Tecnologias |
|---|---|
| Rede | MikroTik RouterOS 7, Netwatch, VPN, dual-WAN |
| Coleta | Syslog remoto, rsyslog |
| Servidor | Ubuntu Linux |
| Persistência | SQLite, WAL |
| Automação | Python, Bash, systemd |
| Interface | Telegram Bot |
| Observabilidade | Logs, timeline, status, análise de eventos |
| IA aplicada | Camada opcional de análise textual e acabamento de resposta |
| Segurança operacional | `.env`, redaction de token, segregação entre dado, runtime e interface |

---

## 8. Contrato de evento

Formato canônico do evento operacional:

```text
NOC|unit=<unidade>|device=<origem>|check=<servico>|state=<UP/DOWN>|host=<alvo>|cid=<correlation-id>
```

### Campos principais

| Campo | Função |
|---|---|
| `unit` | Unidade operacional monitorada |
| `device` | Dispositivo ou origem do evento |
| `check` | Link, serviço ou componente monitorado |
| `state` | Estado do evento: UP ou DOWN |
| `host` | Alvo monitorado, preferencialmente sanitizado em material público |
| `cid` | Identificador de correlação para rastreabilidade |

---

## 9. Serviços monitorados — versão sanitizada

| Check | Tipo | Função no projeto |
|---|---|---|
| Link principal | WAN / conectividade | Verificar disponibilidade do acesso principal |
| Link secundário | WAN / contingência | Verificar disponibilidade de redundância |
| Serviço cloud externo | Serviço crítico | Verificar disponibilidade de dependência externa |
| Telefonia/VoIP | Serviço crítico | Verificar disponibilidade de comunicação |
| SELFTEST | Controle de pipeline | Validar freshness sem depender apenas de transição real |

> Observação: em documentos públicos, não registrar IPs, nomes de fornecedores, tokens, topologia sensível ou identificação do cliente/ambiente sem autorização formal.

---

## 10. Resultado e impacto

| Impacto | Descrição |
|---|---|
| Redução de verificações manuais | Status e histórico passaram a ser consultáveis via bot e banco estruturado |
| Alerta mais rápido | Eventos de queda/retorno de links e serviços ficam centralizados no fluxo operacional |
| Histórico rastreável | Eventos passam a ter registro bruto e estruturado, com possibilidade de timeline |
| Apoio à decisão técnica | Matriz de severidade, estado atual e histórico apoiam resposta a incidente |
| Evidência operacional | Logs, DB, comandos e outputs permitem comprovação técnica do comportamento |
| Governança | Separação entre fonte factual, camada de apresentação e IA opcional |
| Escalabilidade | Arquitetura preparada para expansão multiunidade |

### Impacto principal recomendado para edital

**Centralização e rastreabilidade de eventos de infraestrutura crítica, com redução de verificações manuais e apoio à resposta técnica a incidentes.**

---

## 11. Matriz de comprovação

| Evidência | Força documental | Situação sugerida |
|---|---:|---|
| Declaração assinada | Muito alta | Obter com responsável que possa validar autoria/aplicação |
| Relatório técnico | Muito alta | Formalizar versão sanitizada |
| Documento de arquitetura | Alta | Anexar ao dossiê privado |
| Prints do bot | Média/alta | Sanitizar nomes, IPs e dados sensíveis |
| Logs do pipeline | Média/alta | Usar trechos higienizados |
| Schema SQLite | Alta | Evidência técnica objetiva |
| Código-fonte | Alta | Usar repositório/commit/tag como rastreabilidade |
| Comandos /where, /status, /timeline | Alta | Evidenciam operação real da solução |
| Matriz de severidade | Alta | Demonstra governança operacional |
| Histórico de incidentes | Alta | Usar somente versão anonimizada |

---

## 12. Quem pode assinar declaração

| Assinante | Papel documental |
|---|---|
| Proprietária da Biotech Soluções em TI | Validação da autoria técnica, desenvolvimento e aplicação real |
| Responsável do ambiente beneficiado, quando aplicável | Validação institucional do uso/impacto |
| Marcelo | Autor técnico, para relatório e memorial descritivo, sem substituir declaração de terceiro |

### Estratégia recomendada

1. **Declaração da Biotech Soluções em TI** para autoria, execução técnica, período, escopo e tecnologias.
2. **Relatório técnico assinado** como documento principal do dossiê.
3. **Evidências sanitizadas** como anexos.
4. Se possível futuramente, **declaração do ambiente beneficiado** para reforçar aplicação real.

---

## 13. Onde lançar no Lattes

| Seção do Lattes | Uso recomendado |
|---|---|
| Atuação profissional | Citar como atividade técnica correlata no cargo/função exercida |
| Produção técnica | Lançar como software/ferramenta técnica aplicada |
| Projetos | Lançar como projeto técnico autoral aplicado, se o campo for compatível |
| Relatório técnico | Lançar após criação de relatório formal com data e autoria |
| Apresentações de trabalho | Apenas se houver apresentação real em evento |
| Produção bibliográfica | Apenas se houver resumo/artigo/relato publicado |

---

## 14. Texto curto para Lattes

> Desenvolvimento de solução autoral de monitoramento operacional aplicada em ambiente real corporativo/clínico privado, integrando MikroTik RouterOS 7, Syslog, Ubuntu Linux, SQLite, Python, Telegram Bot e inteligência artificial para acompanhamento de links e serviços críticos de infraestrutura de TI.

---

## 15. Texto forte para edital

> Projeto técnico autoral aplicado à infraestrutura crítica de TI, desenvolvido a partir de dezembro de 2025, com integração entre equipamentos de rede, servidor Linux, banco de dados local, automação, mensageria e inteligência artificial. A solução permite centralizar eventos de disponibilidade, consultar histórico operacional, classificar severidade e apoiar a resposta técnica a incidentes em ambiente real corporativo/clínico privado.

---

## 16. Texto para resumo técnico futuro

> Este relato apresenta o desenvolvimento de uma solução aplicada de monitoramento operacional para infraestrutura crítica de TI em ambiente corporativo/clínico privado. A proposta integrou MikroTik RouterOS 7, Syslog remoto, servidor Linux, SQLite, Python, Telegram Bot e camada opcional de inteligência artificial, com objetivo de registrar eventos de disponibilidade, estruturar histórico operacional e apoiar a resposta técnica a incidentes. A solução demonstrou potencial para reduzir verificações manuais, melhorar a rastreabilidade e apoiar processos de tomada de decisão em ambientes que dependem de conectividade, telefonia e serviços digitais críticos.

---

## 17. Enquadramento como produção técnica

| Possibilidade | Entra agora? | Observação |
|---|---:|---|
| Software/ferramenta técnica | Sim | Melhor enquadramento inicial |
| Projeto técnico aplicado | Sim | Pode compor dossiê e memorial |
| Relatório técnico | A criar | Recomendado como próxima etapa |
| Produto/processo tecnológico | Possível | Depende do edital e da forma de comprovação |
| Relato técnico | Futuro | Requer texto estruturado e submissão/apresentação/publicação |
| Artigo aplicado | Futuro | Exige método, discussão e revisão mais formal |

---

## 18. Pontos sensíveis e mitigação

| Risco | Mitigação |
|---|---|
| Exposição de infraestrutura real | Usar versão pública sanitizada |
| Exposição de IPs, tokens ou nomes internos | Remover/mascarar dados sensíveis |
| Confundir IA com fonte factual | Registrar que IA é opcional e não altera fatos operacionais |
| Projeto parecer apenas bot Telegram | Enfatizar arquitetura de monitoramento e pipeline de eventos |
| Falta de comprovação externa | Obter declaração assinada e anexar evidências |
| Mistura entre projeto autoral e cliente | Usar “ambiente real corporativo/clínico privado” em material público |

---

## 19. Checklist de formalização

| Item | Status |
|---|---|
| Nome oficial definido | Concluído |
| Período definido | Concluído |
| Natureza do projeto definida | Concluído |
| Ambiente definido como privado/sanitizado | Concluído |
| Impacto principal definido | Concluído |
| Tecnologias listadas | Concluído |
| Local no Lattes mapeado | Concluído |
| Declaração assinada | Pendente |
| Relatório técnico formal | Pendente |
| Evidências sanitizadas | Pendente |
| Versão para apresentação | Pendente |
| Resumo/relato para publicação futura | Pendente |

---

## 20. Próximos produtos documentais recomendados

1. **Declaração de autoria e aplicação técnica** assinada pela Biotech Soluções em TI.
2. **Relatório técnico formal** do projeto, com problema, objetivo, metodologia, arquitetura, resultados e evidências.
3. **Pacote de evidências sanitizadas** com prints, logs, comandos e diagrama.
4. **Texto final para Lattes** em formato de produção técnica/software.
5. **Resumo expandido ou relato técnico** para submissão futura em evento de TI/EPT.

---

## 21. Observação de governança

Este documento não substitui o baseline operacional do projeto. Ele traduz o projeto técnico para finalidade de dossiê profissional-acadêmico, Lattes, produção técnica e preparação para editais.

Regra: **não inventar resultado, publicação, certificado ou validação institucional.** Tudo que for usado em edital deve ter evidência, assinatura, data, escopo e versão sanitizada quando necessário.
