# Audit — repo ZIP vs pacote documental carregado no chat (2026-04-14)

Este relatório **supera operacionalmente** o registro provisório em `sync/SYNC_REPORT_2026-04-14.md`.

## Escopo comparado

Fontes comparadas:

1. export do repositório `marcelocsjunior/BOT.NOC.IA` recebido como `BOT.NOC.IA-main.zip`
2. pacote documental solto carregado anteriormente no chat

Objetivo:
- verificar se o repositório estava defasado
- evitar overwrite cego de arquivos mais novos no repo
- promover apenas artefatos faltantes

## Conclusão executiva

O repositório **não estava genericamente defasado**.

Achados:
- parte relevante de `docs/` e `baseline/` no ZIP/repo está **mais nova** do que o pacote documental solto carregado antes no chat
- `docs/DM_ASSISTIVA_HIBRIDA.md` e `baseline/SHA256SUMS_BASELINE` estavam alinhados
- dois artefatos do pacote do chat **não existiam no ZIP/repo** e foram promovidos nesta trilha:
  - `baseline/CONTEXTO_OPERACIONAL_PADRAO_BOT_IA_NOC_UN1_2026-03-19.md`
  - `sync/inbox/CHANGELOG_BASELINE_2026-03-18.log`

## Matriz de comparação

| pacote do chat | destino lógico | status | fonte mais nova / válida | ação |
|---|---|---|---|---|
| `README.md` | `docs/README.md` | diferente | ZIP/repo | não sobrescrever |
| `DEPLOY.md` | `docs/DEPLOY.md` | diferente | ZIP/repo | não sobrescrever |
| `DM_ASSISTIVA_HIBRIDA.md` | `docs/DM_ASSISTIVA_HIBRIDA.md` | igual | - | nenhuma |
| `00_INDEX_CANONICO.md` | `baseline/00_INDEX_CANONICO.md` | diferente | ZIP/repo | não sobrescrever |
| `BOT_ia_NOC_UN1_CANONICO.md` | `baseline/BOT_ia_NOC_UN1_CANONICO.md` | diferente | ZIP/repo | não sobrescrever |
| `CONTEXTO_OPERACIONAL_PADRAO_BOT_IA_NOC_UN1_2026-03-19.md` | `baseline/CONTEXTO_OPERACIONAL_PADRAO_BOT_IA_NOC_UN1_2026-03-19.md` | ausente no ZIP/repo | pacote do chat | promover |
| `CHANGELOG_BASELINE.log` | `baseline/CHANGELOG_BASELINE.log` | ausente no ZIP/repo | pacote do chat | preservar como inbox, sem conflitar com `baseline/CHANGELOG_BASELINE.md` |
| `SHA256SUMS_BASELINE` | `baseline/SHA256SUMS_BASELINE` | igual | - | nenhuma |

## Hashes observados

| arquivo | sha256 pacote chat | sha256 ZIP/repo |
|---|---|---|
| `README.md` | `4952fd44eb8c13b4f44805aa6b595a81b812e491e16e8eeb79475e1e3cead1a0` | `24ec12e117f9ec03dbeb25f3344259565cddbf4466b929883e87581fc19d13be` |
| `DEPLOY.md` | `0116982ce7b95c274eba555fbbb1183a69bc10d19aaf6e8b95de259055320dc9` | `51788b665c5b475ebbc2a9b11e4d5306f6920e8978f37296a3f1f1bc31d3a5eb` |
| `DM_ASSISTIVA_HIBRIDA.md` | `c683d153afdab4d8de02c48d2e58413362ed20a6cb2119a20afacd27db8292ab` | `c683d153afdab4d8de02c48d2e58413362ed20a6cb2119a20afacd27db8292ab` |
| `00_INDEX_CANONICO.md` | `29d6c8f4d7251353588e57734073e5adbf73b5f496da337ddf94c2f6f5b67816` | `e12258bd370348a8cf26acbe33c65d56e4fb34004dfdea2ea63ed27d1a5a87c2` |
| `BOT_ia_NOC_UN1_CANONICO.md` | `1e4dc7e26593d317f7ac91c7ecba35b389a0add825fb4d61bf532b8ebd38221d` | `95b4e488a4c9246cf804ff6aa22e75cc99905f6abe678594ad71a7e0c0f9b476` |
| `CONTEXTO_OPERACIONAL_PADRAO_BOT_IA_NOC_UN1_2026-03-19.md` | `865d217a323e2062bf22f3043df8d86bdf25e14a383ae74037a23af4eb5db2d3` | `-` |
| `CHANGELOG_BASELINE.log` | `aa56208f65ba1fefa97433f56a7b50bdc9f402cb0a5a8cb4d6f1885afefed55b` | `-` |
| `SHA256SUMS_BASELINE` | `e7e01bbd744a7bd1f44553636a8025ce5f97d12add6e73ff63f21468443630a1` | `e7e01bbd744a7bd1f44553636a8025ce5f97d12add6e73ff63f21468443630a1` |

## Decisão aplicada nesta trilha

1. **Não** regredir `docs/` e `baseline/` com o pacote solto mais antigo
2. **Preservar** no GitHub os artefatos ausentes, sem conflitar com o canônico já versionado
3. **Registrar** que o diagnóstico inicial de “repo possivelmente defasado” ficou superado após a análise do ZIP completo

## Resultado esperado

Depois deste commit/PR:
- fica documentado que o repo estava mais novo em pontos críticos
- o contexto operacional estável de 2026-03-19 passa a ficar versionado
- o changelog avulso carregado no chat fica preservado como artefato de inbox/evidência, sem substituir o changelog markdown canônico do repo
