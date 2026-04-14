# Sync report — 2026-04-14

Este arquivo registra a sincronização manual do pacote documental carregado no chat para o repositório `marcelocsjunior/BOT.NOC.IA`.

## O que foi validado

Foi confirmado que o `README.md` carregado no chat representa o conteúdo de `docs/README.md`, e não o README raiz do projeto.

Também foi identificado drift entre o `docs/README.md` já existente no repositório e a versão carregada localmente no chat.

## Pacote documental carregado no chat

- `README.md` → destino lógico: `docs/README.md`  
  sha256: `4952fd44eb8c13b4f44805aa6b595a81b812e491e16e8eeb79475e1e3cead1a0`
- `DEPLOY.md` → destino lógico: `docs/DEPLOY.md`  
  sha256: `0116982ce7b95c274eba555fbbb1183a69bc10d19aaf6e8b95de259055320dc9`
- `DM_ASSISTIVA_HIBRIDA.md` → destino lógico: `docs/DM_ASSISTIVA_HIBRIDA.md`  
  sha256: `c683d153afdab4d8de02c48d2e58413362ed20a6cb2119a20afacd27db8292ab`
- `00_INDEX_CANONICO.md` → destino lógico: `baseline/00_INDEX_CANONICO.md`  
  sha256: `29d6c8f4d7251353588e57734073e5adbf73b5f496da337ddf94c2f6f5b67816`
- `BOT_ia_NOC_UN1_CANONICO.md` → destino lógico: `baseline/BOT_ia_NOC_UN1_CANONICO.md`  
  sha256: `1e4dc7e26593d317f7ac91c7ecba35b389a0add825fb4d61bf532b8ebd38221d`
- `CONTEXTO_OPERACIONAL_PADRAO_BOT_IA_NOC_UN1_2026-03-19.md` → destino lógico: `baseline/CONTEXTO_OPERACIONAL_PADRAO_BOT_IA_NOC_UN1_2026-03-19.md`  
  sha256: `865d217a323e2062bf22f3043df8d86bdf25e14a383ae74037a23af4eb5db2d3`
- `CHANGELOG_BASELINE.log` → destino lógico: `baseline/CHANGELOG_BASELINE.log`  
  sha256: `aa56208f65ba1fefa97433f56a7b50bdc9f402cb0a5a8cb4d6f1885afefed55b`
- `SHA256SUMS_BASELINE` → destino lógico: `baseline/SHA256SUMS_BASELINE`  
  sha256: `d153f158f67f976935bc8cdfdd6e7a88c03d8b398ed3335ccf04db0571cbe3dd`

## Observação operacional

A integração GitHub disponível nesta sessão permitiu criar um artefato novo com segurança, mas não expôs a árvore Git completa necessária para eu substituir, com baixa chance de erro, os arquivos já existentes em seus caminhos finais usando um commit único e transacional.

Por isso, este sync foi registrado como artefato versionado no repositório, preservando o histórico atual e deixando rastreado o pacote documental carregado no chat.

## Próximo passo recomendado

Executar uma segunda rodada de sync in-place dos caminhos finais:

- `docs/README.md`
- `docs/DEPLOY.md`
- `docs/DM_ASSISTIVA_HIBRIDA.md`
- `baseline/00_INDEX_CANONICO.md`
- `baseline/BOT_ia_NOC_UN1_CANONICO.md`
- `baseline/CONTEXTO_OPERACIONAL_PADRAO_BOT_IA_NOC_UN1_2026-03-19.md`
- `baseline/CHANGELOG_BASELINE.log`
- `baseline/SHA256SUMS_BASELINE`

Objetivo da próxima rodada: alinhar o conteúdo vivo do repositório com o pacote documental já validado no chat, sem ambiguidade de origem nem overwrite cego.
