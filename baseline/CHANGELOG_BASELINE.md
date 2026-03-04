=== 2026-02-28 (BRT) — Baseline/Operação ===
- Consolidado tooling de release/deploy em produção: /usr/local/sbin/noc-release
- Ajustado sanity gate do deploy: ignora 400 Bad Request; falha só em erro fatal.
- Criado cofre persistente de releases: /var/lib/noc/releases
  - SHA256SUMS gerado como telegram-bot e verificado (sha256sum -c): OK
  - CHANGELOG_RELEASES.log registrado
  - LAST_RELEASE.zip criado
- Último deploy aplicado:
  - release_zip=noc_bot_release_2026-02-28_114719.zip
  - patched_zip=noc_bot_patched.zip
  - sha256=e089a920c196f1b04e2cd677d73a034c54d50f0c4aae0b89d1f9a192ff582129
  - backup=/opt/telegram-bot.bak_2026-02-28_114719
  - runtime_start=2026-02-28 11:47:21
  - BOT_VERSION|build=2026-02-28-dm-group-ux|build=2026-02-28_094935
  - proof: commands.py sha256 matches zip (595b9fca19cf168682703d273e37e7e50aa996b1304d48be6bf232db14d08c36)

=== 2026-02-28 (BRT) — Recomendação de layout ===
- Pasta recomendada: /var/lib/noc/baseline
- Symlink recomendado: /opt/telegram-bot/00_INDEX_CANONICO.md -> /var/lib/noc/baseline/00_INDEX_CANONICO.md

=== 2026-02-28 15:04 BRT — Baseline promovido no servidor ===
baseline_dir=/var/lib/noc/baseline
symlink=/opt/telegram-bot/00_INDEX_CANONICO.md
release_vault=/var/lib/noc/releases
last_release=/var/lib/noc/releases/LAST_RELEASE.zip

=== 2026-02-28 (BRT) — Baseline integrity ===
- SHA256SUMS_BASELINE criado e verificado (sha256sum -c): OK
#TEST_FAIL Sat Feb 28 16:01:41 -03 2026
#TEST_FAIL Sat Feb 28 16:02:28 -03 2026

=== 2026-02-28 (BRT) — Integrity automation hardening ===
- noc-integrity-check.service passou a rodar como root:adm (padroniza owner/perms dos logs e arquivos rotacionados)
- logrotate: /etc/logrotate.d/noc-integrity-check (daily, rotate 30, compress, create 0660 root adm, su root adm)
- alerta Telegram em FAIL: OnFailure=noc-integrity-alert.service (Grupo NOC -1003869552711)

=== 2026-02-28 (BRT) — Integrity automation hardening ===
- noc-integrity-check.service passou a rodar como root:adm (padroniza owner/perms dos logs e arquivos rotacionados)
- logrotate: /etc/logrotate.d/noc-integrity-check (daily, rotate 30, compress, create 0660 root adm, su root adm)
- alerta Telegram em FAIL: OnFailure=noc-integrity-alert.service (Grupo NOC -1003869552711)

=== 2026-02-28 (BRT) — Bot /health (Grupo NOC) ===
- Novo comando: /health (Grupo NOC) — painel rápido (versão/build, serviços, paths, last event, integrity)
- Resposta sem parse_mode (evita 400 Bad Request por entidades)
- Fallback por Regex para capturar /health@bot em supergroup (anti-ruído)
- Integridade exposta via /var/log/noc/integrity-last.txt (readable) para consumo do bot

=== 2026-03-02 (BRT) — Runbooks sync + deploy gate fix (anti-falso positivo) ===
- Fix: sanity gate dos runbooks de deploy/bump agora ignora ruído do Telegram:
  BadRequest / 400 Bad Request / parse entities (mantém fatal: Traceback|IndentationError|SyntaxError|ERROR|CRITICAL).
  Commits: aca7258, 22b0849
- Evidence (GitHub):
  - evidence/runbooks_sync_2026-03-02_023159.txt
  - evidence/runbooks_sync_2026-03-02_023211.txt
- Evidence (Collector ubt / 192.168.88.108):
  - /var/lib/noc/evidence/runbooks_sync_2026-03-02_023824.sha256
- Runtime SHA256 (aplicado no coletor):
  - 00_bump_env_canonic.sh = 0f27f20d4f294b6e5c48a9a1c14198eb4541d26da13c4732175f6c21b75f532c
  - 20_deploy_zip_canonic.sh = 532a6f58303c878ecf57e4e41219a89307e0ac572db183c555470ad93732cf3d

=== 2026-03-02 (BRT) — SYNC_RUNBOOKS evidence (repo -> coletor) ===
- Commit (fonte de verdade / repo): ce3ce2d
- Coletor (ubt / 192.168.88.108) evidence:
  - /var/lib/noc/evidence/runbooks_sync_2026-03-02_042117.meta
  - /var/lib/noc/evidence/runbooks_sync_2026-03-02_042117.sha256
- Resultado: Drift=0 (oficial vs noc_canonic_scripts) + gate OK (ruído Telegram ignorado)
- SHA256 (runbooks):
  - 00_bump_env_canonic.sh  = 0f27f20d4f294b6e5c48a9a1c14198eb4541d26da13c4732175f6c21b75f532c
  - 20_deploy_zip_canonic.sh = 532a6f58303c878ecf57e4e41219a89307e0ac572db183c555470ad93732cf3d
