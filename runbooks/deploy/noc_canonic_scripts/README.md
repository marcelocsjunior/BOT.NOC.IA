# Runbooks canônicos — Deploy BOT ia NOC (UN1)

Este pacote contém scripts **separados** (padrão canônico / auditável):

- `00_bump_env_canonic.sh`  → atualiza `BOT_VERSION` + `BUILD_ID` no `.env` (com backup) e reinicia o serviço.
- `10_build_release_zip_canonic.sh` → cria release ZIP (staging → patches → compile → zip).
- `20_deploy_zip_canonic.sh` → deploy canônico (aplica **somente** `noc_bot/`, preserva `bot.py/.env/venv`).
- `30_rollback_last_backup.sh` → rollback rápido usando o último `/opt/telegram-bot.bak_*`.

## Onde guardar (persistente)
Recomendado: `/var/lib/noc/runbooks/deploy/`

```bash
sudo install -d -m 0755 /var/lib/noc/runbooks/deploy
sudo cp -a ./*.sh /var/lib/noc/runbooks/deploy/
sudo cp -a ./patches /var/lib/noc/runbooks/deploy/
sudo chmod +x /var/lib/noc/runbooks/deploy/*.sh
```

## Fluxo canônico (recomendado)

### 1) Bump de versão (.env)
```bash
sudo /var/lib/noc/runbooks/deploy/00_bump_env_canonic.sh
# ou
sudo BOT_VER_PREFIX="$(date +%F)-dm-group-ux" /var/lib/noc/runbooks/deploy/00_bump_env_canonic.sh
```

### 2) Build do release ZIP
```bash
sudo /var/lib/noc/runbooks/deploy/10_build_release_zip_canonic.sh /tmp/noc_bot_multiunit_fixed.zip
```

### 3) Deploy do ZIP
```bash
sudo /var/lib/noc/runbooks/deploy/20_deploy_zip_canonic.sh /tmp/noc_bot_multiunit_fixed.zip
```

### Rollback (se necessário)
```bash
sudo /var/lib/noc/runbooks/deploy/30_rollback_last_backup.sh
```

## Patches
Os patches em `./patches/*.patch` são aplicados automaticamente no build do release.

- `01_add_vpn_svcs.patch`
- `02_add_vpn_evidence_menu.patch`
- `03_vpn_evidence_labels.patch`
