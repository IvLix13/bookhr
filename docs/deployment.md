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

## Резервное копирование

`deploy/backup.sh` — ежедневный pg_dump с ротацией 14 дней.

## Офлайн-разработка

1. На онлайн-машине: `./scripts/prepare-offline-bundle.sh <version>`
2. Перенести tar.gz на офлайн-машину
3. `./scripts/install-offline.sh <bundle.tar.gz>`
4. `./scripts/migrate.sh prod`

Prod может работать без Node.js, если frontend уже собран в bundle.
