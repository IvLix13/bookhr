# Bookuchet

Кадровое веб-приложение для оперативного учёта событий: Flask + Vue 3 + PostgreSQL.

## Стек

- Backend: Python 3.11+, Flask, SQLAlchemy, Alembic
- Frontend: Vue 3, TypeScript, Vite, Pinia, Vue Router
- DB: PostgreSQL
- Deploy: Linux без Docker, Gunicorn + systemd

## Быстрый старт (dev)

```bash
chmod +x scripts/*.sh deploy/*.sh
./scripts/setup-databases.sh
./scripts/migrate.sh dev
./scripts/dev.sh
```

- Frontend dev: http://127.0.0.1:5173
- Backend API: http://127.0.0.1:5000/api
- Логин по умолчанию после seed: `admin` / `admin123`

## Prod сборка

```bash
cp .env.example .env.prod   # или используйте scripts/setup-databases.sh
./scripts/build.sh production
./scripts/migrate.sh prod
./scripts/run-prod.sh
```

## Офлайн-комплект

На машине с интернетом (Ubuntu/Debian x86_64):

```bash
./scripts/prepare-offline-bundle.sh 20260724.1
```

На офлайн-машине:

```bash
./scripts/install-offline.sh dist/offline/bookuchet-offline-20260724.1-linux-x64.tar.gz
./scripts/migrate.sh prod
./scripts/run-prod.sh
```

Проверка bundle:

```bash
./scripts/verify-offline-bundle.sh dist/offline/bookuchet-offline-20260724.1-linux-x64.tar.gz
```

## Контуры БД

- dev: `bookuchet_dev` / `bookuchet_dev_user`
- prod: `bookuchet_prod` / `bookuchet_prod_user`

Конфигурации: `.env.dev`, `.env.prod`

## Фоновые задачи

```bash
flask run-rules
flask send-notifications
```

Systemd unit/timer файлы: `deploy/`

## Модули

- Календарь и ближайшие события
- Сотрудники и история
- Импорт Excel с UUID
- Контракты, грейды, паспорта, поощрения
- Мероприятия и rule engine
- Nextcloud Talk уведомления
- RBAC: admin / hr / viewer

## Тесты

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest
```
