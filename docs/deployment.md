# Эксплуатация Bookuchet

## Установка prod

1. Скопировать проект в `/opt/bookuchet`
2. Создать пользователя `bookuchet`
3. Выполнить `./scripts/setup-databases.sh`
4. Настроить `.env.prod`
5. `./scripts/migrate.sh prod`
6. `./scripts/build.sh production`
7. Установить systemd unit из `deploy/bookuchet.service`
8. Включить timers:
   - `bookuchet-rules.timer`
   - `bookuchet-notifications.timer`

## Секреты Nextcloud

Токен бота хранится только в EnvironmentFile, не в БД.

## LDAP (опционально)

В `.env.prod` можно включить вход через LDAP:

```
LDAP_ENABLED=true
LDAP_URI=ldaps://ad.example.com:636
LDAP_BIND_DN=CN=svc-bookuchet,OU=Service,DC=example,DC=com
LDAP_BIND_PASSWORD=...
LDAP_USER_BASE_DN=OU=Users,DC=example,DC=com
LDAP_USER_FILTER=(sAMAccountName={username})
LDAP_USE_TLS=true
LDAP_TLS_CA_FILE=/path/to/ca.pem
LDAP_ATTR_USERNAME=sAMAccountName
LDAP_ATTR_FULL_NAME=displayName
LDAP_DEFAULT_ROLE=viewer
LDAP_LOCAL_ADMIN_USERNAME=admin
```

При `LDAP_ENABLED=true` обычные пользователи проходят LDAP-проверку и создаются в БД при первом входе с ролью `LDAP_DEFAULT_ROLE`. Локальный пароль сохраняется только для пользователя `LDAP_LOCAL_ADMIN_USERNAME` (аварийный администратор).

## Резервное копирование

`deploy/backup.sh` — ежедневный pg_dump с ротацией 14 дней.

## Офлайн-разработка

1. На онлайн-машине: `./scripts/export-for-offline.sh <version>`
2. Перенести tar.gz на офлайн-машину
3. `OFFLINE_MODE=1 ./scripts/install-offline.sh <bundle.tar.gz>`
4. `sudo ./scripts/install-system-deps-offline.sh vendor/debs`
5. `OFFLINE_MODE=1 ./scripts/migrate.sh prod`

Prod может работать без Node.js, если frontend уже собран в bundle.
