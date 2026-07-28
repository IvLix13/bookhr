#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

DEV_DB="${DEV_DB:-bookuchet_dev}"
DEV_USER="${DEV_USER:-bookuchet_dev_user}"
DEV_PASSWORD="${DEV_PASSWORD:-change-me-dev}"
PROD_DB="${PROD_DB:-bookuchet_prod}"
PROD_USER="${PROD_USER:-bookuchet_prod_user}"
PROD_PASSWORD="${PROD_PASSWORD:-change-me-prod}"

sudo -u postgres psql <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${DEV_USER}') THEN
    CREATE ROLE ${DEV_USER} LOGIN PASSWORD '${DEV_PASSWORD}';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${PROD_USER}') THEN
    CREATE ROLE ${PROD_USER} LOGIN PASSWORD '${PROD_PASSWORD}';
  END IF;
END
\$\$;

SELECT 'CREATE DATABASE ${DEV_DB} OWNER ${DEV_USER}'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${DEV_DB}')\\gexec

SELECT 'CREATE DATABASE ${PROD_DB} OWNER ${PROD_USER}'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${PROD_DB}')\\gexec

REVOKE ALL ON DATABASE ${PROD_DB} FROM ${DEV_USER};
REVOKE ALL ON DATABASE ${DEV_DB} FROM ${PROD_USER};
SQL

cat > .env.dev <<ENV
APP_ENV=development
SECRET_KEY=dev-secret-change-me
DATABASE_URL=postgresql+psycopg://${DEV_USER}:${DEV_PASSWORD}@localhost:5432/${DEV_DB}
TIMEZONE=Europe/Moscow
UPLOAD_DIR=${ROOT_DIR}/backend/uploads
SESSION_COOKIE_SECURE=false
NEXTCLOUD_BASE_URL=
NEXTCLOUD_BOT_TOKEN=
LDAP_ENABLED=false
LDAP_URI=
LDAP_BIND_DN=
LDAP_BIND_PASSWORD=
LDAP_USER_BASE_DN=
LDAP_USER_FILTER=(sAMAccountName={username})
LDAP_USE_TLS=false
LDAP_TLS_CA_FILE=
LDAP_ATTR_USERNAME=sAMAccountName
LDAP_ATTR_FULL_NAME=displayName
LDAP_DEFAULT_ROLE=viewer
LDAP_LOCAL_ADMIN_USERNAME=admin
ENV

cat > .env.prod <<ENV
APP_ENV=production
SECRET_KEY=prod-secret-change-me
DATABASE_URL=postgresql+psycopg://${PROD_USER}:${PROD_PASSWORD}@localhost:5432/${PROD_DB}
TIMEZONE=Europe/Moscow
UPLOAD_DIR=${ROOT_DIR}/backend/uploads
SESSION_COOKIE_SECURE=true
NEXTCLOUD_BASE_URL=
NEXTCLOUD_BOT_TOKEN=
LDAP_ENABLED=false
LDAP_URI=
LDAP_BIND_DN=
LDAP_BIND_PASSWORD=
LDAP_USER_BASE_DN=
LDAP_USER_FILTER=(sAMAccountName={username})
LDAP_USE_TLS=false
LDAP_TLS_CA_FILE=
LDAP_ATTR_USERNAME=sAMAccountName
LDAP_ATTR_FULL_NAME=displayName
LDAP_DEFAULT_ROLE=viewer
LDAP_LOCAL_ADMIN_USERNAME=admin
ENV

echo "Created .env.dev and .env.prod"
