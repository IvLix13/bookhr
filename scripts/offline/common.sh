#!/usr/bin/env bash
# Shared helpers for offline bundle preparation and installation.

offline_is_install() {
  local root="${1:-}"
  [[ -f "$root/.offline-install" ]] || [[ "${OFFLINE_MODE:-}" == "1" ]]
}

offline_pip_install() {
  local venv="$1"
  local requirements="$2"
  local project_root
  project_root="$(cd "$(dirname "$venv")/.." && pwd)"
  local wheels="$project_root/vendor/wheels"

  if offline_is_install "$project_root" && [[ -d "$wheels" ]]; then
    "$venv/bin/pip" install --no-index --find-links "$wheels" pip setuptools wheel
    "$venv/bin/pip" install --no-index --find-links "$wheels" -r "$requirements"
    return
  fi

  "$venv/bin/pip" install -r "$requirements"
}

offline_require_command() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Required command not found: $cmd"
    exit 1
  fi
}

offline_check_node_version() {
  local min_major="${1:-18}"
  local current major

  current="$(node -p "process.versions.node")"
  major="${current%%.*}"

  if [[ "$major" -lt "$min_major" ]]; then
    echo "ERROR: Node.js ${current} is too old for frontend development."
    echo "Install Node.js ${min_major}+ (recommended: 20 LTS)."
    return 1
  fi

  return 0
}

offline_check_frontend_toolchain() {
  local root="${1:-}"
  local vite_pkg="$root/frontend/node_modules/vite/package.json"

  if [[ ! -f "$vite_pkg" ]]; then
    return 0
  fi

  local vite_major
  vite_major="$(node -p "require('$vite_pkg').version.split('.')[0]")"
  if [[ "$vite_major" -ge 8 ]]; then
    echo "ERROR: Bundled frontend uses Vite ${vite_major}.x, which requires Node.js 20.19+."
    echo "Current Node.js: $(node --version)"
    echo
    echo "Rebuild the offline bundle on an online machine after updating frontend dependencies,"
    echo "or run: cd frontend && npm ci && npm run dev"
    return 1
  fi

  return 0
}

offline_target_python_version() {
  echo "${OFFLINE_PYTHON_VERSION:-3.11}"
}

offline_target_python_tag() {
  local version
  version="$(offline_target_python_version)"
  version="${version//./}"
  echo "cp${version}"
}

offline_python_tag() {
  python3 - <<'PY'
import sys
print(f"cp{sys.version_info.major}{sys.version_info.minor}")
PY
}

offline_prune_foreign_python_wheels() {
  local wheels_dir="$1"
  local target_tag
  target_tag="$(offline_target_python_tag)"

  echo "Keeping wheels for ${target_tag} and pure-python packages only..."
  find "$wheels_dir" -maxdepth 1 -name '*.whl' | while read -r wheel; do
    local base
    base="$(basename "$wheel")"
    if [[ "$base" =~ -py3-none-any\.whl$ ]] || [[ "$base" =~ -py2\.py3-none-any\.whl$ ]]; then
      continue
    fi
    if [[ "$base" =~ -${target_tag}- ]]; then
      continue
    fi
    if [[ "$base" =~ -cp[0-9]+- ]]; then
      rm -f "$wheel"
    fi
  done
}

offline_download_python_wheels() {
  local pip_bin="$1"
  local wheels_dir="$2"
  shift 2
  local requirements_files=("$@")
  local py_version
  py_version="$(offline_target_python_version)"

  "$pip_bin" download pip setuptools wheel -d "$wheels_dir"

  for requirements_file in "${requirements_files[@]}"; do
    echo "Downloading wheels for Python ${py_version} from ${requirements_file}..."
    "$pip_bin" download -r "$requirements_file" -d "$wheels_dir" \
      --python-version "$py_version" \
      --platform manylinux2014_x86_64 \
      --platform manylinux_2_17_x86_64 \
      --platform any \
      --only-binary=:all:
  done

  offline_prune_foreign_python_wheels "$wheels_dir"
}

offline_bundle_python_version() {
  local install_dir="$1"
  local manifest="$install_dir/vendor/MANIFEST.json"
  if [[ -f "$manifest" ]]; then
    python3 - "$manifest" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as fh:
    data = json.load(fh)
print(data.get("python_version", "3.11"))
PY
    return
  fi
  offline_target_python_version
}

offline_python_cmd_for_version() {
  local py_version="$1"
  local major="${py_version%%.*}"
  local minor="${py_version#*.}"
  local candidate="python${major}.${minor}"

  if command -v "$candidate" >/dev/null 2>&1; then
    echo "$candidate"
    return 0
  fi

  if command -v python3 >/dev/null 2>&1; then
    local current
    current="$(python3 - <<PY
import sys
print(f"{sys.version_info.major}.{sys.version_info.minor}")
PY
)"
    if [[ "$current" == "$py_version" ]]; then
      echo python3
      return 0
    fi
  fi

  return 1
}

offline_verify_bundle_wheels() {
  local wheels_dir="$1"
  local py_version="${2:-$(offline_target_python_version)}"
  local python_tag="cp${py_version//./}"
  local foreign_wheel=""

  foreign_wheel="$(find "$wheels_dir" -maxdepth 1 -name '*.whl' \
    | while read -r wheel; do
        base="$(basename "$wheel")"
        if [[ "$base" =~ -py3-none-any\.whl$ ]] || [[ "$base" =~ -py2\.py3-none-any\.whl$ ]]; then
          continue
        fi
        if [[ "$base" =~ -${python_tag}- ]]; then
          continue
        fi
        if [[ "$base" =~ -cp[0-9]+- ]]; then
          echo "$base"
          break
        fi
      done)"

  if [[ -n "$foreign_wheel" ]]; then
    echo "ERROR: Bundle contains wheel for another Python version: $foreign_wheel"
    echo "Expected tag: ${python_tag}"
    return 1
  fi

  if ! compgen -G "${wheels_dir}/SQLAlchemy-*-${python_tag}-*.whl" >/dev/null \
    && ! compgen -G "${wheels_dir}/SQLAlchemy-*-py3-none-any.whl" >/dev/null; then
    echo "ERROR: Missing SQLAlchemy wheel for Python ${py_version} (${python_tag})."
    return 1
  fi

  if ! compgen -G "${wheels_dir}/psycopg_binary-*-${python_tag}-*.whl" >/dev/null; then
    echo "ERROR: Missing psycopg_binary wheel for Python ${py_version} (${python_tag})."
    return 1
  fi

  return 0
}

offline_python_tag_for_cmd() {
  local python_cmd="$1"
  "$python_cmd" - <<'PY'
import sys
print(f"cp{sys.version_info.major}{sys.version_info.minor}")
PY
}

offline_check_python_wheels() {
  local wheels_dir="$1"
  local install_dir="${2:-}"
  local py_version
  local python_cmd
  local python_tag
  local target_tag

  if [[ -n "$install_dir" && -f "$install_dir/vendor/MANIFEST.json" ]]; then
    py_version="$(offline_bundle_python_version "$install_dir")"
  else
    py_version="$(offline_target_python_version)"
  fi

  offline_verify_bundle_wheels "$wheels_dir" "$py_version"

  python_cmd="$(offline_python_cmd_for_version "$py_version")" || {
    echo "ERROR: Bundle targets Python ${py_version}, but python${py_version} is not installed."
    echo "Install Python ${py_version} on the offline machine and retry."
    return 1
  }

  python_tag="$(offline_python_tag_for_cmd "$python_cmd")"
  target_tag="cp${py_version//./}"

  if [[ "$python_tag" != "$target_tag" ]]; then
    echo "ERROR: Bundle targets Python ${py_version}, but ${python_cmd} is $("$python_cmd" --version)."
    return 1
  fi

  return 0
}

offline_project_root_from_frontend() {
  local frontend_dir="$1"
  cd "$frontend_dir/.." && pwd
}

offline_npm_cache_dir() {
  local root="${1:-}"
  echo "$root/vendor/npm-cache"
}

offline_restore_node_modules() {
  local root="$1"
  local frontend="$root/frontend"
  local vendor_modules="$root/vendor/node_modules"

  if [[ ! -d "$vendor_modules" ]]; then
    echo "Bundled frontend dependencies not found: $vendor_modules"
    echo "Rebuild the offline bundle on an online machine with prepare-offline-frontend-dev.sh"
    return 1
  fi

  echo "Restoring frontend/node_modules from bundle..."
  rm -rf "$frontend/node_modules"
  cp -a "$vendor_modules" "$frontend/node_modules"
}

offline_verify_npm_cache() {
  local root="$1"
  local frontend="$root/frontend"
  local cache
  cache="$(offline_npm_cache_dir "$root")"

  if [[ ! -d "$cache" ]]; then
    echo "npm cache is missing in bundle: $cache"
    return 1
  fi

  echo "Verifying npm cache for offline frontend development..."
  (
    cd "$frontend"
    npm ci --cache "$cache" --offline --prefer-offline
  )
}

# Returns 0 when the DB schema is behind alembic heads (upgrade needed),
# 1 when already current, 2 on check failure.
offline_db_needs_upgrade() {
  local project_root="$1"
  local venv_python="${2:-$project_root/backend/.venv/bin/python}"
  local rc=0

  if [[ ! -x "$venv_python" ]]; then
    echo "Python venv not found: $venv_python" >&2
    return 2
  fi

  (
    cd "$project_root/backend"
    export FLASK_APP=wsgi:app
    "$venv_python" - <<'PY'
from __future__ import annotations

import sys

from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from flask import current_app

from wsgi import app

with app.app_context():
    migrate_cfg = current_app.extensions["migrate"]
    config = migrate_cfg.migrate.get_config()
    script = ScriptDirectory.from_config(config)
    heads = set(script.get_heads())
    if not heads:
        print("No Alembic heads found in migrations/", file=sys.stderr)
        raise SystemExit(2)

    with migrate_cfg.db.engine.connect() as connection:
        context = MigrationContext.configure(connection)
        current = set(context.get_current_heads())

    if current == heads:
        print(f"DB schema is up to date ({', '.join(sorted(heads))})")
        raise SystemExit(1)

    current_label = ", ".join(sorted(current)) if current else "(none)"
    heads_label = ", ".join(sorted(heads))
    print(f"Pending migrations: current={current_label}; heads={heads_label}")
    raise SystemExit(0)
PY
  ) || rc=$?

  return "$rc"
}

# Apply migrations via migrate.sh when the DB is behind heads.
offline_ensure_migrations() {
  local project_root="$1"
  local target="${2:-prod}"
  local venv_python="${3:-$project_root/backend/.venv/bin/python}"
  local status=0

  offline_db_needs_upgrade "$project_root" "$venv_python" || status=$?

  case "$status" in
    0)
      echo "Applying pending database migrations ($target)..."
      bash "$project_root/scripts/migrate.sh" "$target"
      ;;
    1)
      # Already current — nothing to do.
      ;;
    *)
      echo "Failed to check migration status (exit=$status)." >&2
      return "$status"
      ;;
  esac
}

