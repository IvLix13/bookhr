# Офлайн-развёртывание Bookuchet

Инструкция для переноса проекта на машину без доступа в интернет.

## Принцип

1. На **онлайн-машине** собирается полный комплект: исходники, собранный frontend, Python wheels, npm cache, node_modules и локальные `.deb` пакеты.
2. Комплект переносится на офлайн-машину (USB, SCP через промежуточный хост, и т.д.).
3. На **офлайн-машине** установка выполняется только из локальных файлов. `pip`, `npm` и `apt` не обращаются к интернету.

## Требования

### Онлайн-машина (сборка комплекта)

- Ubuntu/Debian x86_64 (желательно та же версия, что и на офлайн-машине)
- `python3`, `python3-venv`, `npm`, `node` (18+), `rsync`, `tar`
- доступ в интернет

### Оффлайн-мachine (развёртывание)

- Ubuntu/Debian x86_64 той же major-версии, что и машина сборки
- `python3`, `python3-venv`, `rsync`, `tar`, `postgresql`
- `nodejs` 18+ (Vite 8 не поддерживается; в bundle используется Vite 6)
- права root для установки системных пакетов и systemd

## 1. Сборка комплекта на онлайн-машине

```bash
cd /path/to/bookuchet
chmod +x scripts/*.sh scripts/offline/*.sh deploy/*.sh

# Полный цикл: сборка + проверка
./scripts/export-for-offline.sh 20260728.1
```

Или по шагам:

```bash
./scripts/prepare-offline-bundle.sh 20260728.1
./scripts/verify-offline-bundle.sh dist/offline/bookuchet-offline-20260728.1-linux-x64.tar.gz
```

Результат:

```
dist/offline/bookuchet-offline-<version>-linux-x64.tar.gz
```

## 2. Перенос на офлайн-машину

```bash
scp dist/offline/bookuchet-offline-20260728.1-linux-x64.tar.gz user@offline-host:/tmp/
```

## 3. Развёртывание на офлайн-машине

### Вариант A: автоматически (prod)

```bash
sudo OFFLINE_MODE=1 INSTALL_DIR=/opt/bookuchet \
  ./scripts/deploy-offline-prod.sh /tmp/bookuchet-offline-20260728.1-linux-x64.tar.gz
```

Скрипт:

- распакует комплект;
- установит Python-зависимости из локальных wheels (`--no-index`);
- восстановит `node_modules` из комплекта;
- установит `.deb` пакеты из `vendor/debs` (если запущен от root);
- создаст `.env.prod` и базы через `setup-databases.sh`;
- выполнит миграции;
- установит systemd unit-файлы.

### Вариант B: по шагам

```bash
export OFFLINE_MODE=1
INSTALL_DIR=/opt/bookuchet

./scripts/install-offline.sh /tmp/bookuchet-offline-20260728.1-linux-x64.tar.gz
sudo ./scripts/install-system-deps-offline.sh /opt/bookuchet/vendor/debs
cd /opt/bookuchet
./scripts/setup-databases.sh
./scripts/migrate.sh prod
./scripts/run-prod.sh
```

## Что входит в комплект

| Каталог / файл | Назначение |
|---|---|
| `app/` | исходники проекта |
| `app/backend/static/` | собранный frontend |
| `vendor/wheels/` | Python wheels для offline `pip install` |
| `vendor/npm-cache/` | npm cache |
| `vendor/node_modules/` | frontend dependencies |
| `vendor/debs/` | локальные `.deb` для PostgreSQL и базовых утилит |
| `vendor/MANIFEST.json` | метаданные комплекта |
| `SHA256SUMS` | контрольные суммы |

## Гарантии offline-режима

После установки создаётся файл `.offline-install`. Скрипты `migrate.sh`, `run-prod.sh` и `build.sh` в offline-режиме:

- используют `pip install --no-index --find-links vendor/wheels`;
- не запускают `npm ci` / `npm install`;
- не пересобирают frontend без локальных зависимостей.

Переменная окружения `OFFLINE_MODE=1` включает тот же режим принудительно.

## Systemd

После `deploy-offline-prod.sh` будут установлены:

- `bookuchet.service`
- `bookuchet-rules.timer`
- `bookuchet-notifications.timer`

Проверка:

```bash
systemctl status bookuchet
curl http://127.0.0.1:3005/api/me
```

## Проверка комплекта перед переносом

```bash
./scripts/verify-offline-bundle.sh dist/offline/bookuchet-offline-<version>-linux-x64.tar.gz
```

Скрипт проверяет checksum, наличие wheels/static и (если доступно) установку Python-зависимостей в network namespace без сети.

## Важные замечания

1. Собирайте комплект на той же ОС и архитектуре (`linux x86_64`), что и офлайн-машина.
2. Если `vendor/debs` пуст, установите PostgreSQL и `python3-venv` вручную до запуска миграций.
3. Prod-развёртывание не требует Node.js: frontend уже собран в `backend/static`.
4. Для dev на офлайн-машине `node_modules` восстанавливаются из комплекта.

## Frontend-разработка offline

### На онлайн-машине

Скрипт `prepare-offline-frontend-dev.sh` автоматически вызывается из `prepare-offline-bundle.sh` и:

- устанавливает frontend-зависимости;
- сохраняет npm cache;
- копирует `node_modules` в `vendor/node_modules`;
- проверяет offline `npm ci`;
- проверяет `npm run build`, `typecheck`, `test`.

Отдельный запуск:

```bash
./scripts/prepare-offline-frontend-dev.sh dist/offline/.staging/vendor
```

### На офлайн-машине

```bash
cd /opt/bookuchet
OFFLINE_MODE=1 ./scripts/setup-offline-frontend-dev.sh
OFFLINE_MODE=1 ./scripts/dev-offline.sh
```

`setup-offline-frontend-dev.sh`:

- восстанавливает `frontend/node_modules` из bundle;
- проверяет npm cache без интернета;
- готовит окружение для `vite dev` и offline `npm run build`.

`dev-offline.sh` запускает backend Flask и Vite dev server без скачивания зависимостей.

Пересборка prod-static offline:

```bash
cd /opt/bookuchet/frontend
npm run build
rsync -a dist/ ../backend/static/
```

## Обновление версии

1. На онлайн-машине собрать новый bundle с новой версией.
2. Перенести архив на офлайн-машину.
3. Установить поверх существующего каталога или в новый `INSTALL_DIR`.
4. Выполнить:

```bash
cd /opt/bookuchet
OFFLINE_MODE=1 ./scripts/migrate.sh prod
sudo systemctl restart bookuchet
```
