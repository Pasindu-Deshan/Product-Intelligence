#!/usr/bin/env bash
# Apply migrations in order, optionally seeding dev data.
#
#   ADMIN_DATABASE_URL=postgresql://postgres@localhost/pi ./scripts/init_db.sh --seed
#
# Migration 008 (roles) needs elevated privileges and is applied only when
# --with-roles is passed.
set -euo pipefail

DB="${ADMIN_DATABASE_URL:-${DATABASE_URL:?set ADMIN_DATABASE_URL or DATABASE_URL}}"
DB="${DB/postgresql+psycopg:\/\//postgresql://}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

for file in "$ROOT"/database/migrations/0*.sql; do
  case "$file" in
    *008_readonly_role.sql)
      [[ "${*}" == *--with-roles* ]] || { echo "skip  $(basename "$file") (pass --with-roles)"; continue; }
      ;;
  esac
  echo "apply $(basename "$file")"
  psql "$DB" -v ON_ERROR_STOP=1 -q -f "$file"
done

if [[ "${*}" == *--seed* ]]; then
  echo "seed  dev_seed.sql"
  psql "$DB" -v ON_ERROR_STOP=1 -q -f "$ROOT/database/seed/dev_seed.sql"
fi

echo "done"
