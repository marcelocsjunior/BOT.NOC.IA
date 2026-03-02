# SYNC_RUNBOOKS — Notebook → Coletor (ubt) (UN1)

Runbook para sincronizar os scripts canônicos de deploy/bump do repositório (fonte de verdade) para o runtime no Coletor UN1 (`ubt`), garantindo **drift=0** com validações por `grep/diff/sha256` e evidência.

---

## Escopo

Sincroniza **somente**:

- `00_bump_env_canonic.sh`
- `20_deploy_zip_canonic.sh`

Nos dois locais do coletor:

- `/var/lib/noc/runbooks/deploy/` (oficiais)
- `/var/lib/noc/runbooks/deploy/noc_canonic_scripts/` (duplicados do baseline)

> Não mexe em `.env`, `venv`, DB, logs do bot, nem em serviços systemd.

---

## Ambientes e paths

### Notebook (workstation / Git)
- Repo clonado:
  - `/home/biotech/Documentos/FASE 2 - BOT_IA_NOC/BOT_ia_NOC_UN1_repo_seed`
- Scripts fonte (GitHub):
  - `runbooks/deploy/00_bump_env_canonic.sh`
  - `runbooks/deploy/20_deploy_zip_canonic.sh`

### Coletor (produção / runtime)
- Host: `ubt`
- IP: `192.168.88.108`
- Usuário: `bio`
- Paths runtime:
  - `/var/lib/noc/runbooks/deploy/00_bump_env_canonic.sh`
  - `/var/lib/noc/runbooks/deploy/20_deploy_zip_canonic.sh`
  - `/var/lib/noc/runbooks/deploy/noc_canonic_scripts/00_bump_env_canonic.sh`
  - `/var/lib/noc/runbooks/deploy/noc_canonic_scripts/20_deploy_zip_canonic.sh`

---

## Pré-check (Notebook)

Atualize o repo e valide que está limpo:

```bash
cd "/home/biotech/Documentos/FASE 2 - BOT_IA_NOC/BOT_ia_NOC_UN1_repo_seed"
git pull --rebase
git status

Sanity do “deploy gate” (deve existir o padrão):

egrep -i somente fatal

egrep -vi filtrando ruído (BadRequest|400 Bad Request|parse entities)


grep -nE 'egrep -i|egrep -vi|BadRequest|400 Bad Request|parse entities' \
  runbooks/deploy/00_bump_env_canonic.sh \
  runbooks/deploy/20_deploy_zip_canonic.sh


---

SYNC (Notebook → Coletor)

1) Copiar para /tmp no coletor (Notebook)

REPO="/home/biotech/Documentos/FASE 2 - BOT_IA_NOC/BOT_ia_NOC_UN1_repo_seed"

scp "$REPO/runbooks/deploy/00_bump_env_canonic.sh" bio@192.168.88.108:/tmp/
scp "$REPO/runbooks/deploy/20_deploy_zip_canonic.sh" bio@192.168.88.108:/tmp/

2) Instalar nos paths oficiais (Coletor)

No ubt:

sudo install -m 0755 /tmp/00_bump_env_canonic.sh /var/lib/noc/runbooks/deploy/00_bump_env_canonic.sh
sudo install -m 0755 /tmp/20_deploy_zip_canonic.sh /var/lib/noc/runbooks/deploy/20_deploy_zip_canonic.sh

3) Instalar também nos duplicados noc_canonic_scripts/ (Coletor)

Mantendo owner/group padrão telegram-bot:telegram-bot:

sudo install -o telegram-bot -g telegram-bot -m 0755 \
  /var/lib/noc/runbooks/deploy/00_bump_env_canonic.sh \
  /var/lib/noc/runbooks/deploy/noc_canonic_scripts/00_bump_env_canonic.sh

sudo install -o telegram-bot -g telegram-bot -m 0755 \
  /var/lib/noc/runbooks/deploy/20_deploy_zip_canonic.sh \
  /var/lib/noc/runbooks/deploy/noc_canonic_scripts/20_deploy_zip_canonic.sh


---

Validação (Coletor)

A) Validar o gate corrigido (grep)

grep -nE 'egrep -i|egrep -vi|BadRequest|400 Bad Request|parse entities' \
  /var/lib/noc/runbooks/deploy/00_bump_env_canonic.sh \
  /var/lib/noc/runbooks/deploy/20_deploy_zip_canonic.sh \
  /var/lib/noc/runbooks/deploy/noc_canonic_scripts/00_bump_env_canonic.sh \
  /var/lib/noc/runbooks/deploy/noc_canonic_scripts/20_deploy_zip_canonic.sh

Esperado:

egrep -i "Traceback|IndentationError|SyntaxError|ERROR|CRITICAL"

egrep -vi "BadRequest|400 Bad Request|parse entities"


B) Validar drift=0 (diff)

diff -u /var/lib/noc/runbooks/deploy/00_bump_env_canonic.sh \
       /var/lib/noc/runbooks/deploy/noc_canonic_scripts/00_bump_env_canonic.sh | head

diff -u /var/lib/noc/runbooks/deploy/20_deploy_zip_canonic.sh \
       /var/lib/noc/runbooks/deploy/noc_canonic_scripts/20_deploy_zip_canonic.sh | head

Sem output = OK.

C) Fingerprint auditável (sha256)

sudo sha256sum \
  /var/lib/noc/runbooks/deploy/00_bump_env_canonic.sh \
  /var/lib/noc/runbooks/deploy/20_deploy_zip_canonic.sh \
  /var/lib/noc/runbooks/deploy/noc_canonic_scripts/00_bump_env_canonic.sh \
  /var/lib/noc/runbooks/deploy/noc_canonic_scripts/20_deploy_zip_canonic.sh


---

Evidência (Coletor) — opcional, recomendado

Criar pasta de evidência e registrar sha256:

sudo mkdir -p /var/lib/noc/evidence
sudo chown telegram-bot:telegram-bot /var/lib/noc/evidence

TS="$(date +%F_%H%M%S)"
sudo bash -lc "sha256sum \
  /var/lib/noc/runbooks/deploy/00_bump_env_canonic.sh \
  /var/lib/noc/runbooks/deploy/20_deploy_zip_canonic.sh \
  /var/lib/noc/runbooks/deploy/noc_canonic_scripts/00_bump_env_canonic.sh \
  /var/lib/noc/runbooks/deploy/noc_canonic_scripts/20_deploy_zip_canonic.sh \
  > /var/lib/noc/evidence/runbooks_sync_${TS}.sha256"

sudo chown telegram-bot:telegram-bot /var/lib/noc/evidence/runbooks_sync_${TS}.sha256
ls -lah /var/lib/noc/evidence/runbooks_sync_${TS}.sha256


---

Evidência (GitHub) — opcional, recomendado

No notebook (repo clonado), gerar um arquivo em evidence/ com data/hora + hashes do runtime aplicados e commitar.

> Padrão: Evidence: runbooks synced to collector (sha256)




---

Notas operacionais

Esse sync não impacta o bot em execução (scripts são usados em deploy/bump).

Para sanity real do serviço do bot, use journalctl -u telegram-bot.service ... no coletor.

Ruído do Telegram (400/BadRequest/parse entities) deve ser tratado como non-fatal no deploy gate; erros de runtime/código continuam fatais.



---