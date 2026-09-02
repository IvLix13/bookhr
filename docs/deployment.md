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

## Обновление из GitHub

Репозиторий: `https://github.com/IvLix13/bookhr` (ветка `main`).

Перед обновлением сохраните локальные файлы, которые не лежат в git: `.env.dev`, `.env.prod`, `backend/uploads/`, `backups/`.

### 1. Машина с git-клоном (сборка, export, dev)

```bash
cd /path/to/bookuchet
git fetch origin
git checkout main
git pull origin main
```

После pull:

- **dev:** `./scripts/dev.sh` (или перезапустите уже запущенный процесс)
- **повторный offline-export:** `./scripts/export-for-offline.sh $(date +%Y%m%d.%H%M%S)`
- **prod на этой же машине:** см. шаг 2

Если каталог ставили копированием без `.git`, один раз привяжите его к GitHub:

```bash
cd /opt/bookuchet
git init
git remote add origin https://github.com/IvLix13/bookhr.git
git fetch origin
git checkout -B main origin/main
```

Либо скачайте ZIP с `main` и распакуйте поверх проекта, не затирая `.env*` и `uploads/`.

### 2. Prod после обновления файлов

```bash
cd /opt/bookuchet
./scripts/migrate.sh prod
./scripts/build.sh production
sudo systemctl restart bookuchet
sudo systemctl restart bookuchet-rules.timer bookuchet-notifications.timer
```

`migrate.sh prod` сам делает `pg_dump` в `backups/` до применения миграций.

### 3. Офлайн-контур

На офлайн-машине GitHub недоступен. Обновление только новым bundle:

1. На онлайн-машине: `git pull origin main`, затем `./scripts/export-for-offline.sh <version>`
2. Перенести архив на офлайн-хост
3. Установить поверх `/opt/bookuchet` и выполнить `OFFLINE_MODE=1 ./scripts/migrate.sh prod`
4. `sudo systemctl restart bookuchet`

Подробности: [offline-deployment.md](offline-deployment.md#обновление-версии)

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

## Копирование БД: dev → prod

Скрипт `./scripts/copy-db-dev-to-prod.sh` полностью заменяет содержимое PostgreSQL из `.env.prod` данными из `.env.dev`.

Что делает:

1. Проверяет доступность обеих БД и печатает счётчики строк
2. Делает бэкап prod в `backups/bookuchet_prod_pre_copy_<TS>.sql`
3. Делает dump dev и восстанавливает его в prod (`--clean --if-exists`, без owner/ACL — объекты принадлежат prod-пользователю)
4. Опционально копирует `UPLOAD_DIR` и останавливает systemd-сервисы

```bash
./scripts/copy-db-dev-to-prod.sh --dry-run
./scripts/copy-db-dev-to-prod.sh --yes
./scripts/copy-db-dev-to-prod.sh --yes --stop-services --with-uploads
```

Важно:

- Операция **разрушающая** для prod: все текущие данные prod будут заменены
- Перед запуском желательно, чтобы оба контура были на одной схеме (`./scripts/migrate.sh dev` и `./scripts/migrate.sh prod`); иначе prod станет копией схемы/данных из source dump
- Секреты из `.env.prod` (SECRET_KEY, Nextcloud, LDAP) **не** копируются — меняются только таблицы PostgreSQL
- Пользователи и пароли из таблицы `users` тоже приедут из dev

## Резервное копирование

`deploy/backup.sh` — ежедневный pg_dump с ротацией 14 дней.

## Офлайн-разработка

1. На онлайн-машине: `./scripts/export-for-offline.sh <version>`
2. Перенести tar.gz на офлайн-машину
3. `OFFLINE_MODE=1 ./scripts/install-offline.sh <bundle.tar.gz>`
4. `sudo ./scripts/install-system-deps-offline.sh vendor/debs`
5. `OFFLINE_MODE=1 ./scripts/migrate.sh prod`

Prod может работать без Node.js, если frontend уже собран в bundle.
