# Comandos úteis para coleta de evidências ALTIS

> Ajustar conforme ambiente real. Executar apenas quando fizer sentido operacional.

## [VM bot] Status dos serviços

```bash
systemctl --no-pager --full status telegram-bot.service noc-whatsapp-dm.service altis-wa-worker-poller.service
```

## [VM bot] Logs recentes sem paginação

```bash
journalctl -u telegram-bot.service -n 80 --no-pager
journalctl -u noc-whatsapp-dm.service -n 80 --no-pager
journalctl -u altis-wa-worker-poller.service -n 80 --no-pager
```

## [VM bot] Validar banco e paths principais

```bash
ls -lh /var/lib/noc/noc.db /var/log/mikrotik/un1.log 2>/dev/null
sqlite3 /var/lib/noc/noc.db '.schema events'
```

## [VM bot] Gerar schema sem dados reais

```bash
sqlite3 /var/lib/noc/noc.db '.schema' > /tmp/ALTIS_schema_sqlite_SANITIZADO.sql
```

## Observação de sanitização

Antes de usar qualquer saída em dossiê externo, revisar manualmente e remover dados sensíveis.